import html
import json
import math
import os
import sys

if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from PySide6.QtCore import QPointF, QRect, Qt, QTimer, QUrl, QUrlQuery
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QRegion, QTransform
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWebSockets import QWebSocket
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMenu,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

import config
import sprite
from states import Capivara, State

W = max(sprite.WALK_W + 160, sprite.PEEK_W + 60, sprite.PEEK_H + 60)
H = max(sprite.WALK_H, sprite.PEEK_H, sprite.PEEK_W) + 30
STRIP = 120
STEP = 0.06
WALK_STEP = 0.015
REST = 30

class Note(QWidget):
    def __init__(self, on_done):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(
            "QWidget { background: #fffbe6; color: #222; }"
            "QLabel#sender { color: #777; }"
            "QPushButton { padding: 4px 16px; }"
        )
        self.setFixedWidth(280)
        self.sender_label = QLabel(objectName="sender")
        self.title_label = QLabel()
        bold = self.title_label.font()
        bold.setBold(True)
        self.title_label.setFont(bold)
        self.text_label = QLabel()
        for label in (self.sender_label, self.title_label, self.text_label):
            label.setWordWrap(True)
            label.setTextFormat(Qt.PlainText)
        button = QPushButton("Lido")
        button.clicked.connect(on_done)
        layout = QVBoxLayout(self)
        layout.addWidget(self.sender_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.text_label)
        layout.addWidget(button, alignment=Qt.AlignRight)

    def show_message(self, msg: dict, anchor: QRect) -> None:
        sender, title = msg.get("sender"), msg.get("title")
        self.sender_label.setText(f"de {sender}" if sender else "")
        self.sender_label.setVisible(bool(sender))
        self.title_label.setText(title or "")
        self.title_label.setVisible(bool(title))
        self.text_label.setText(msg["text"])
        self.adjustSize()
        screen = QGuiApplication.primaryScreen().availableGeometry()
        x = min(max(anchor.center().x() - self.width() // 2, screen.left()), screen.right() - self.width())
        y = max(anchor.top() - self.height() - 8, screen.top())
        self.move(x, y)
        self.show()
        self.raise_()


class History(QTextBrowser):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Capivara — histórico")
        self.resize(420, 480)

    def show_items(self, items: list[dict]) -> None:
        if not items:
            self.setHtml("<p><i>Nenhuma mensagem lida ainda.</i></p>")
        else:
            parts = []
            for m in items:
                head = " · ".join(html.escape(v) for v in (m.get("sender"), m.get("title")) if v)
                when = html.escape((m.get("read_at") or "")[:16].replace("T", " "))
                parts.append(
                    f"<p><small style='color:#777'>{when} {head}</small><br>{html.escape(m['text'])}</p>"
                )
            self.setHtml("<hr>".join(parts))
        self.show()
        self.raise_()


class Window(QWidget):
    def __init__(self, cfg: config.Config):
        super().__init__(
            None,
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
            | Qt.X11BypassWindowManagerHint,
        )
        self.cfg = cfg
        self.capivara = Capivara()
        self.reveal = 0.0
        self.ticks = 0
        self.pixmaps = sprite.frames()
        self.connected = False
        self.backoff = 1

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(W, H)
        self.place()

        self.note = Note(self.on_note_done)
        self.history = History()
        self.http = QNetworkAccessManager(self)

        self.ws = QWebSocket()
        self.ws.connected.connect(self.on_connected)
        self.ws.disconnected.connect(self.on_disconnected)
        self.ws.textMessageReceived.connect(self.on_text)
        self.reconnect_timer = QTimer(self, singleShot=True)
        self.reconnect_timer.timeout.connect(self.open_socket)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)

        self.update_mask()
        self.open_socket()

    def place(self) -> None:
        g = QGuiApplication.primaryScreen().availableGeometry()
        if self.cfg.edge == "bottom":
            self.move(g.right() - W + 1, g.bottom() - H + 1)
        elif self.cfg.edge == "right":
            self.move(g.right() - W + 1, g.bottom() - H - 60)
        else:
            self.move(g.left(), g.bottom() - H - 60)

    def strip_rect(self) -> QRect:
        if self.cfg.edge == "bottom":
            return QRect((W - sprite.PEEK_W) // 2, H - 8, sprite.PEEK_W, 8)
        if self.cfg.edge == "right":
            return QRect(W - 8, H - STRIP, 8, STRIP)
        return QRect(0, H - STRIP, 8, STRIP)

    def peeking(self) -> bool:
        return self.capivara.state == State.PEEKING

    def moving(self) -> bool:
        return self.capivara.state in (State.ENTERING, State.LEAVING)

    def pixmap(self):
        if self.peeking():
            frames = self.pixmaps[f"peek_{self.cfg.edge}"]
            return frames[self.ticks // sprite.PEEK_TICKS % sprite.FRAMES]
        walk = self.pixmaps["walk"]
        return walk[self.ticks // sprite.WALK_TICKS % sprite.FRAMES] if self.moving() else walk[0]

    def frame_transform(self) -> QTransform:
        pix = self.pixmap()
        w, h = pix.width(), pix.height()
        r = self.reveal
        t = QTransform()
        if self.peeking():
            if self.cfg.edge == "bottom":
                t.translate((W - w) // 2, round(H - h * r))
            elif self.cfg.edge == "right":
                t.translate(round(W - w * r), H - h)
            else:
                t.translate(round(-w + w * r), H - h)
            return t
        if self.cfg.edge == "left":
            x = round(-w + (W - REST) * r)
        else:
            x = round(W - (W - REST) * r)
        t.translate(x, H - h + sprite.SINK)
        if (self.cfg.edge == "left") != (self.capivara.state == State.LEAVING):
            t.translate(w, 0)
            t.scale(-1, 1)
        return t

    def capivara_rect(self) -> QRect:
        pix = self.pixmap()
        return self.frame_transform().mapRect(QRect(0, 0, pix.width(), pix.height())).intersected(self.rect())

    def badge_rect(self) -> QRect:
        center = self.frame_transform().map(QPointF(*sprite.BADGE_POS))
        return QRect(int(center.x()) - 11, max(int(center.y()) - 11, 0), 22, 22)

    def update_mask(self) -> None:
        region = QRegion(self.strip_rect())
        if self.capivara.state != State.HIDDEN:
            region = region.united(QRegion(self.capivara_rect()))
            if self.capivara.pile:
                region = region.united(QRegion(self.badge_rect()))
        self.setMask(region)

    def target(self) -> float:
        return {
            State.HIDDEN: 0.0,
            State.PEEKING: 1.0,
            State.ENTERING: 1.0,
            State.WAITING: 1.0,
            State.READING: 1.0,
            State.LEAVING: 0.0,
        }[self.capivara.state]

    def tick(self) -> None:
        goal = self.target()
        step = WALK_STEP if self.moving() else STEP
        before = self.pixmap()
        changed = self.reveal != goal
        if changed:
            self.reveal = goal if abs(goal - self.reveal) <= step else self.reveal + math.copysign(step, goal - self.reveal)
        if self.reveal == goal and self.moving():
            self.capivara.arrived()
            self.capivara.gone()
            changed = True
        if self.capivara.state != State.HIDDEN:
            self.ticks += 1
        if changed or self.pixmap() is not before:
            self.update_mask()
            self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.strip_rect(), QColor(0, 0, 0, 1))
        if self.capivara.state == State.HIDDEN and self.reveal == 0:
            return
        p.save()
        p.setTransform(self.frame_transform())
        p.drawPixmap(0, 0, self.pixmap())
        p.restore()
        if self.capivara.pile:
            badge = self.badge_rect()
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#d33"))
            p.drawEllipse(badge)
            p.setPen(Qt.white)
            p.setFont(QFont(self.font().family(), 9, QFont.Bold))
            p.drawText(badge, Qt.AlignCenter, str(len(self.capivara.pile)))

    def enterEvent(self, event) -> None:
        self.capivara.hover_in()
        self.update_mask()

    def leaveEvent(self, event) -> None:
        self.capivara.hover_out()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.capivara.click()
            if self.capivara.state == State.READING:
                self.note.show_message(self.capivara.current, self.geometry())
        elif event.button() == Qt.RightButton and self.capivara.state in (State.PEEKING, State.WAITING):
            self.show_menu(event.globalPosition().toPoint())

    def show_menu(self, pos) -> None:
        menu = QMenu()
        status = f"conectado como {self.cfg.name}" if self.connected else "desconectado"
        menu.addAction(status).setEnabled(False)
        menu.addSeparator()
        menu.addAction("Histórico", self.load_history)
        menu.addAction("Sair", QApplication.quit)
        menu.exec(pos)

    def on_note_done(self) -> None:
        self.note.hide()
        read = self.capivara.note_closed()
        if read is not None and self.connected:
            self.ws.sendTextMessage(json.dumps({"type": "read", "id": read["id"]}))
        self.update_mask()
        self.update()

    def open_socket(self) -> None:
        url = QUrl(self.cfg.ws_url + "/ws")
        query = QUrlQuery()
        query.addQueryItem("id", self.cfg.client_id)
        query.addQueryItem("name", self.cfg.name)
        url.setQuery(query)
        self.ws.open(url)

    def on_connected(self) -> None:
        self.connected = True
        self.backoff = 1

    def on_disconnected(self) -> None:
        self.connected = False
        self.reconnect_timer.start(self.backoff * 1000)
        self.backoff = min(self.backoff * 2, 30)

    def on_text(self, raw: str) -> None:
        try:
            data = json.loads(raw)
        except ValueError:
            return
        if data.get("type") != "message":
            return
        was_peeking = self.peeking()
        self.capivara.message(data)
        if was_peeking and not self.peeking():
            self.reveal = 0.0
        self.update_mask()
        self.update()

    def load_history(self) -> None:
        url = QUrl(self.cfg.server.rstrip("/") + "/history")
        query = QUrlQuery()
        query.addQueryItem("id", self.cfg.client_id)
        url.setQuery(query)
        reply = self.http.get(QNetworkRequest(url))
        reply.finished.connect(lambda: self.on_history(reply))

    def on_history(self, reply: QNetworkReply) -> None:
        if reply.error() == QNetworkReply.NoError:
            self.history.show_items(json.loads(bytes(reply.readAll())))
        else:
            self.history.setHtml("<p><i>Não consegui falar com o servidor.</i></p>")
            self.history.show()
        reply.deleteLater()


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("capivara")
    app.setQuitOnLastWindowClosed(False)
    window = Window(config.load())
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
