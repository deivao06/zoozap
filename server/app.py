import hmac
import json
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

DB_PATH = os.environ.get("ZOOZAP_DB", "zoozap.db")
KEY_PATH = os.path.join(os.path.dirname(DB_PATH) or ".", "key")

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender TEXT,
    title TEXT,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    last_seen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deliveries (
    message_id INTEGER NOT NULL REFERENCES messages(id),
    client_id TEXT NOT NULL REFERENCES clients(id),
    read_at TEXT,
    PRIMARY KEY (message_id, client_id)
);
"""


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def message_payload(row: sqlite3.Row) -> dict:
    return {
        "type": "message",
        "id": row["id"],
        "sender": row["sender"],
        "title": row["title"],
        "text": row["text"],
    }


def load_key() -> str:
    if not os.path.exists(KEY_PATH):
        with open(KEY_PATH, "w", encoding="utf-8") as f:
            f.write(secrets.token_urlsafe(16))
    with open(KEY_PATH, encoding="utf-8") as f:
        return f.read().strip()


def valid_key(headers, query) -> bool:
    auth = headers.get("authorization", "")
    given = auth[len("Bearer "):] if auth.startswith("Bearer ") else query.get("key")
    return given is not None and hmac.compare_digest(given.encode(), KEY.encode())


async def require_key(request: Request) -> None:
    if not valid_key(request.headers, request.query_params):
        raise HTTPException(status_code=401, detail="chave inválida")


conn = db()
conn.executescript(SCHEMA)
conn.close()

KEY = load_key()
print(f"zoozap: chave {KEY}", flush=True)

app = FastAPI(title="zoozap")
connections: dict[str, WebSocket] = {}
sleeping: set[str] = set()


class Notify(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    title: str | None = None
    sender: str | None = None
    to: list[str] | None = None
    sender_look: Any = None


@app.post("/notify", status_code=201, dependencies=[Depends(require_key)])
async def notify(msg: Notify):
    conn = db()
    with conn:
        clients = conn.execute("SELECT id, name FROM clients").fetchall()
        unknown = []
        if msg.to is None:
            targets = {c["id"] for c in clients}
        else:
            targets = set()
            for t in msg.to:
                matched = {c["id"] for c in clients if t in (c["id"], c["name"])}
                if not matched:
                    unknown.append(t)
                targets |= matched
        cur = conn.execute(
            "INSERT INTO messages (sender, title, text, created_at) VALUES (?, ?, ?, ?)",
            (msg.sender, msg.title, msg.text, now()),
        )
        message_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO deliveries (message_id, client_id) VALUES (?, ?)",
            [(message_id, cid) for cid in targets],
        )
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    conn.close()

    payload = message_payload(row)
    for cid in targets:
        ws = connections.get(cid)
        if ws is not None:
            try:
                await ws.send_json(payload)
            except Exception:
                pass

    return {"id": message_id, "unknown": unknown}


@app.get("/clients", dependencies=[Depends(require_key)])
async def list_clients():
    conn = db()
    rows = conn.execute("SELECT id, name FROM clients ORDER BY name").fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"], "online": r["id"] in connections, "asleep": r["id"] in sleeping} for r in rows]


@app.get("/history", dependencies=[Depends(require_key)])
async def history(id: str):
    conn = db()
    rows = conn.execute(
        """
        SELECT m.*, d.read_at FROM messages m
        JOIN deliveries d ON d.message_id = m.id
        WHERE d.client_id = ? AND d.read_at IS NOT NULL
        ORDER BY d.read_at DESC
        LIMIT 50
        """,
        (id,),
    ).fetchall()
    conn.close()
    return [
        {"id": r["id"], "sender": r["sender"], "title": r["title"], "text": r["text"], "read_at": r["read_at"]}
        for r in rows
    ]


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket, id: str, name: str):
    if not valid_key(ws.headers, ws.query_params):
        await ws.close(code=1008)
        return
    await ws.accept()

    old = connections.get(id)
    if old is not None:
        try:
            await old.close()
        except Exception:
            pass
    connections[id] = ws

    conn = db()
    with conn:
        conn.execute(
            """
            INSERT INTO clients (id, name, last_seen) VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET name = excluded.name, last_seen = excluded.last_seen
            """,
            (id, name, now()),
        )
    pending = conn.execute(
        """
        SELECT m.* FROM messages m
        JOIN deliveries d ON d.message_id = m.id
        WHERE d.client_id = ? AND d.read_at IS NULL
        ORDER BY m.id
        """,
        (id,),
    ).fetchall()
    conn.close()

    try:
        for row in pending:
            await ws.send_json(message_payload(row))

        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
                if data.get("type") == "sleep":
                    if data.get("asleep"):
                        sleeping.add(id)
                    else:
                        sleeping.discard(id)
                    continue
                if data.get("type") != "read":
                    continue
                message_id = int(data["id"])
            except (ValueError, KeyError, TypeError, AttributeError):
                continue
            conn = db()
            with conn:
                conn.execute(
                    "UPDATE deliveries SET read_at = ? WHERE message_id = ? AND client_id = ? AND read_at IS NULL",
                    (now(), message_id, id),
                )
            conn.close()
    except WebSocketDisconnect:
        pass
    finally:
        if connections.get(id) is ws:
            del connections[id]
            sleeping.discard(id)
            conn = db()
            with conn:
                conn.execute("UPDATE clients SET last_seen = ? WHERE id = ?", (now(), id))
            conn.close()
