import os
import socket
import sys
import tomllib
import uuid
from dataclasses import dataclass
from pathlib import Path

EDGES = ("bottom", "left", "right")


@dataclass
class Config:
    server: str
    name: str
    edge: str
    client_id: str

    @property
    def ws_url(self) -> str:
        base = self.server.rstrip("/")
        if base.startswith("https://"):
            base = "wss://" + base[len("https://"):]
        elif base.startswith("http://"):
            base = "ws://" + base[len("http://"):]
        return base


def config_dir() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "capivara"


def load() -> Config:
    folder = config_dir()
    folder.mkdir(parents=True, exist_ok=True)

    config_file = folder / "config.toml"
    if not config_file.exists():
        config_file.write_text(
            'server = "http://localhost:8000"\n'
            f'name = "{socket.gethostname()}"\n'
            'edge = "bottom"   # bottom | left | right\n',
            encoding="utf-8",
        )
    data = tomllib.loads(config_file.read_text(encoding="utf-8"))

    id_file = folder / "client_id"
    if not id_file.exists():
        id_file.write_text(str(uuid.uuid4()), encoding="utf-8")
    client_id = id_file.read_text(encoding="utf-8").strip()

    edge = data.get("edge", "bottom")
    if edge not in EDGES:
        edge = "bottom"

    return Config(
        server=data.get("server", "http://localhost:8000"),
        name=data.get("name", socket.gethostname()),
        edge=edge,
        client_id=client_id,
    )
