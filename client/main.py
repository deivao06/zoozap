import html
import json
import math
import os
import random
import socket
import sys

if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from PySide6.QtCore import QPointF, QRect, QSize, Qt, QTimer, QUrl, QUrlQuery
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon, QPainter, QPixmap, QRegion, QTransform
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWebSockets import QWebSocket
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import config
import sprite
from states import Capivara, State

W = max(sprite.WALK_W + 160, sprite.PEEK_W + 60, sprite.PEEK_H + 60)
H = max(sprite.WALK_H, sprite.PEEK_H, sprite.PEEK_W) + 30
STRIP = 120
STEP = 0.09
WALK_STEP = 0.015
HIDE_STEP = 0.045
BUBBLE_EVERY = 150
BUBBLE_FIRST = 30
BUBBLE_LIFE = 60
BUBBLE_GAP = 12
BUBBLE_RISE = 50
BUBBLE_PX = 3
BUBBLE_BIG = (".XXX.", "X..OX", "X...X", "X...X", ".XXX.")
BUBBLE_SMALL = (".X.", "X.X", ".X.")
BUBBLE_POP = ("X.X", "...", "X.X")
BUBBLE_INK = QColor(210, 240, 255, 220)
BUBBLE_SHINE = QColor(255, 255, 255)
SNORE = (
    ".....XXXX",
    "........X",
    ".......X.",
    "XXX...X..",
    "..X..XXXX",
    ".X.......",
    "XXX......",
)
REST = 30
LIFT = 250
PEEK_SINK = 8

PX = 4
TAIL = 3
PAPER = "#fff4d6"
INK = "#3b2414"
MUTED = "#8a5a2b"
ACCENT = "#c8742c"
SHADOW = QColor(0, 0, 0, 70)

ICON_SCALE = 3
GEAR = (
    "....X....",
    ".X.XXX.X.",
    "..XXXXX..",
    ".XXX.XXX.",
    "XXX...XXX",
    ".XXX.XXX.",
    "..XXXXX..",
    ".X.XXX.X.",
    "....X....",
)
CLOCK = (
    "..XXXXX..",
    ".X.....X.",
    "X...X...X",
    "X...X...X",
    "X...XXX.X",
    "X.......X",
    "X.......X",
    ".X.....X.",
    "..XXXXX..",
)
ENVELOPE = (
    ".........",
    "XXXXXXXXX",
    "XX.....XX",
    "X.X...X.X",
    "X..X.X..X",
    "X...X...X",
    "X.......X",
    "X.......X",
    "XXXXXXXXX",
)
MOON = (
    "...XXXX..",
    ".XXX.....",
    "XXX......",
    "XX.......",
    "XX.......",
    "XX.......",
    "XXX......",
    ".XXX.....",
    "...XXXX..",
)
CROSS = (
    "XX.....XX",
    "XXX...XXX",
    ".XXX.XXX.",
    "..XXXXX..",
    "...XXX...",
    "..XXXXX..",
    ".XXX.XXX.",
    "XXX...XXX",
    "XX.....XX",
)

EDGE_LEFT = (
    "XXXXXXXXX",
    "XXX.....X",
    "XXX.....X",
    "XXX.....X",
    "XXX.....X",
    "XXX.....X",
    "XXX.....X",
    "XXX.....X",
    "XXXXXXXXX",
)
EDGE_BOTTOM = (
    "XXXXXXXXX",
    "X.......X",
    "X.......X",
    "X.......X",
    "X.......X",
    "X.......X",
    "XXXXXXXXX",
    "XXXXXXXXX",
    "XXXXXXXXX",
)
EDGE_RIGHT = (
    "XXXXXXXXX",
    "X.....XXX",
    "X.....XXX",
    "X.....XXX",
    "X.....XXX",
    "X.....XXX",
    "X.....XXX",
    "X.....XXX",
    "XXXXXXXXX",
)
DOT = (".XXX.", "XXXXX", "XXXXX", "XXXXX", ".XXX.")
ONLINE = "#4caf50"
OFFLINE = "#d33333"


def local_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except OSError:
            return ""


def pixel_pixmap(rows: tuple[str, ...], color: str = INK, scale: int = ICON_SCALE) -> QPixmap:
    pix = QPixmap(len(rows[0]) * scale, len(rows) * scale)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    for y, row in enumerate(rows):
        for x, cell in enumerate(row):
            if cell == "X":
                p.fillRect(x * scale, y * scale, scale, scale, QColor(color))
    p.end()
    return pix


def pixel_icon(rows: tuple[str, ...]) -> QIcon:
    return QIcon(pixel_pixmap(rows))


def icon_button(rows: tuple[str, ...], text: str) -> QToolButton:
    button = QToolButton()
    button.setIcon(pixel_icon(rows))
    button.setIconSize(QSize(len(rows[0]) * ICON_SCALE, len(rows) * ICON_SCALE))
    button.setText(text)
    button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
    return button


class Balloon(QWidget):
    def __init__(self, flags=Qt.Tool | Qt.WindowStaysOnTopHint):
        super().__init__(None, flags | Qt.FramelessWindowHint | Qt.X11BypassWindowManagerHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.tail_x = 0
        font = QFont("monospace", 10)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        self.setStyleSheet(
            f"QLabel {{ color: {INK}; background: transparent; }}"
            f"QLabel#muted {{ color: {MUTED}; }}"
            f"QPushButton {{ color: {INK}; background: transparent; border: none; font-weight: bold; padding: 2px 0; }}"
            f"QPushButton:hover {{ color: {ACCENT}; }}"
            f"QPushButton#ip {{ color: {MUTED}; font-weight: normal; }}"
            f"QPushButton#ip:hover {{ color: {ACCENT}; }}"
            f"QPushButton#person {{ font-weight: normal; text-align: left; padding: {PX}px {2 * PX}px; }}"
            f"QPushButton#person:checked {{ background: #ecd29a; font-weight: bold; }}"
            f"QPlainTextEdit, QLineEdit {{ color: {INK}; background: #fffaf0; border: {PX // 2}px solid {INK}; padding: {PX}px; }}"
            f"QToolButton {{ color: {INK}; background: transparent; border: none; font-weight: bold; padding: {PX}px; }}"
            f"QToolButton:hover {{ background: #f3e2b8; }}"
            f"QToolButton:checked {{ background: #ecd29a; }}"
            f"QToolButton:disabled {{ color: {MUTED}; }}"
            f"QTextBrowser {{ color: {INK}; background: transparent; border: none; }}"
            f"QScrollBar:vertical {{ background: transparent; width: {2 * PX}px; }}"
            f"QScrollBar::handle:vertical {{ background: {INK}; min-height: {4 * PX}px; }}"
            "QScrollBar::add-line, QScrollBar::sub-line { height: 0; }"
            "QScrollBar::add-page, QScrollBar::sub-page { background: none; }"
        )
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(3 * PX, 3 * PX, 4 * PX, 4 * PX + TAIL * PX)

    def body_rect(self) -> QRect:
        return QRect(0, 0, self.width() - PX, self.height() - PX - TAIL * PX)

    def shape(self, inset: int) -> QRegion:
        body = self.body_rect()
        b = body.adjusted(inset, inset, -inset, -inset)
        region = QRegion(b.adjusted(PX, 0, -PX, 0)).united(QRegion(b.adjusted(0, PX, 0, -PX)))
        bottom = body.y() + body.height()
        for i in range(TAIL):
            half = (TAIL - i) * PX - inset
            if half > 0:
                region = region.united(QRegion(self.tail_x - half, bottom - inset + i * PX, 2 * half, PX))
        return region

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        for region, color in (
            (self.shape(0).translated(PX, PX), SHADOW),
            (self.shape(0), QColor(INK)),
            (self.shape(PX), QColor(PAPER)),
        ):
            p.setClipRegion(region)
            p.fillRect(self.rect(), color)

    def show_at(self, anchor: QRect) -> None:
        self.adjustSize()
        screen = (QGuiApplication.screenAt(anchor.center()) or QGuiApplication.primaryScreen()).availableGeometry()
        x = min(max(anchor.center().x() - self.width() // 2, screen.left()), screen.right() - self.width())
        y = max(anchor.top() - self.height() + PX, screen.top())
        edge = (TAIL + 2) * PX
        self.tail_x = min(max(anchor.center().x() - x, edge), self.width() - PX - edge)
        self.move(x, y)
        self.show()
        self.raise_()
        self.update()


class Note(Balloon):
    def __init__(self, on_done):
        super().__init__()
        self.setFixedWidth(300)
        self.sender_label = QLabel(objectName="muted")
        self.title_label = QLabel()
        bold = self.title_label.font()
        bold.setBold(True)
        self.title_label.setFont(bold)
        self.text_label = QLabel()
        for label in (self.sender_label, self.title_label, self.text_label):
            label.setWordWrap(True)
            label.setTextFormat(Qt.PlainText)
        button = QPushButton("▶ LIDO")
        button.clicked.connect(on_done)
        self.box.addWidget(self.sender_label)
        self.box.addWidget(self.title_label)
        self.box.addWidget(self.text_label)
        self.box.addWidget(button, alignment=Qt.AlignRight)

    def show_message(self, msg: dict, anchor: QRect) -> None:
        sender, title = msg.get("sender"), msg.get("title")
        self.sender_label.setText(f"de {sender}" if sender else "")
        self.sender_label.setVisible(bool(sender))
        self.title_label.setText((title or "").upper())
        self.title_label.setVisible(bool(title))
        self.text_label.setText(msg["text"])
        self.show_at(anchor)


class Menu(Balloon):
    def __init__(self, on_send, on_config, on_history, on_sleep, on_closed):
        super().__init__(Qt.Popup)
        self.on_closed = on_closed
        self.picked = False
        self.status_label = QLabel()
        bold = self.status_label.font()
        bold.setBold(True)
        self.status_label.setFont(bold)
        self.ip = ""
        self.ip_button = QPushButton(objectName="ip")
        self.ip_button.setCursor(Qt.PointingHandCursor)
        self.ip_button.clicked.connect(self.copy_ip)
        self.dot = QLabel()
        header = QHBoxLayout()
        header.addWidget(self.dot)
        header.addWidget(self.status_label)
        header.addStretch()
        header.addWidget(self.ip_button)
        row = QHBoxLayout()
        for icon, text, action in (
            (ENVELOPE, "ENVIAR", on_send),
            (GEAR, "CONFIG", on_config),
            (CLOCK, "HISTÓRICO", on_history),
            (MOON, "DORMIR", on_sleep),
            (CROSS, "SAIR", QApplication.quit),
        ):
            button = icon_button(icon, text)
            button.clicked.connect(lambda _=False, a=action: self.pick(a))
            row.addWidget(button)
            if action is on_sleep:
                self.sleep_button = button
        self.box.addLayout(header)
        self.box.addSpacing(3 * PX)
        self.box.addLayout(row)

    def show_menu(self, name: str, connected: bool, ip: str, asleep: bool, anchor: QRect) -> None:
        self.picked = False
        self.sleep_button.setText("ACORDAR" if asleep else "DORMIR")
        self.dot.setPixmap(pixel_pixmap(DOT, ONLINE if connected else OFFLINE, 2))
        self.status_label.setText(name if connected else "desconectado")
        self.ip = ip
        self.ip_button.setText(ip)
        self.ip_button.setVisible(bool(ip))
        self.show_at(anchor)

    def copy_ip(self) -> None:
        QGuiApplication.clipboard().setText(self.ip)
        self.ip_button.setText("copiado!")
        QTimer.singleShot(1000, lambda: self.ip_button.setText(self.ip))

    def pick(self, action) -> None:
        self.picked = True
        self.hide()
        action()

    def hideEvent(self, event) -> None:
        self.on_closed(self.picked)


class Composer(Balloon):
    def __init__(self, on_send, on_done):
        super().__init__()
        self.setFixedWidth(320)
        self.on_send = on_send
        self.confirming = False
        title = QLabel("ENVIAR")
        bold = title.font()
        bold.setBold(True)
        title.setFont(bold)
        self.people = QVBoxLayout()
        self.people.setSpacing(0)
        self.empty = QLabel("ninguém online")
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText("escreva aqui…")
        self.text.setFixedHeight(90)
        back = QPushButton("◀ VOLTAR")
        back.clicked.connect(on_done)
        self.send_button = QPushButton("▶ ENVIAR")
        self.send_button.clicked.connect(self.send)
        buttons = QHBoxLayout()
        buttons.addWidget(back)
        buttons.addStretch()
        buttons.addWidget(self.send_button)
        self.box.addWidget(title)
        self.box.addWidget(QLabel("PARA", objectName="muted"))
        self.box.addLayout(self.people)
        self.box.addWidget(self.empty)
        self.box.addSpacing(2 * PX)
        self.box.addWidget(self.text)
        self.box.addLayout(buttons)

    def person_buttons(self) -> list[QPushButton]:
        return [self.people.itemAt(i).widget() for i in range(self.people.count())]

    def show_people(self, people: list[dict], anchor: QRect) -> None:
        for button in self.person_buttons():
            button.deleteLater()
        while self.people.count():
            self.people.takeAt(0)
        for person in people:
            name = person["name"] + (" zz" if person.get("asleep") else "")
            button = QPushButton(f"□ {name}", objectName="person", checkable=True)
            button.toggled.connect(lambda on, b=button, n=name: b.setText(f"{'■' if on else '□'} {n}"))
            button.setProperty("cid", person["id"])
            button.setProperty("asleep", bool(person.get("asleep")))
            button.setChecked(len(people) == 1)
            self.people.addWidget(button)
        self.empty.setVisible(not people)
        self.text.clear()
        self.send_button.setText("▶ ENVIAR")
        self.confirming = False
        self.show_at(anchor)
        self.activateWindow()
        self.text.setFocus()

    def send(self) -> None:
        ids = [b.property("cid") for b in self.person_buttons() if b.isChecked()]
        text = self.text.toPlainText().strip()
        if not ids or not text:
            self.flash("escolha alguém" if not ids else "escreva algo")
            return
        if not self.confirming and any(b.property("asleep") for b in self.person_buttons() if b.isChecked()):
            self.confirming = True
            self.send_button.setText("dormindo! enviar mesmo?")
            return
        self.send_button.setText("enviando…")
        self.on_send(ids, text)

    def flash(self, text: str) -> None:
        self.send_button.setText(text)
        QTimer.singleShot(1500, lambda: self.send_button.setText("▶ ENVIAR"))


class Settings(Balloon):
    def __init__(self, on_edge, on_name, on_invite, on_done):
        super().__init__()
        title = QLabel("CONFIG")
        bold = title.font()
        bold.setBold(True)
        title.setFont(bold)
        row = QHBoxLayout()
        self.edge_buttons = {}
        for edge, icon, text in (
            ("left", EDGE_LEFT, "ESQUERDA"),
            ("bottom", EDGE_BOTTOM, "BAIXO"),
            ("right", EDGE_RIGHT, "DIREITA"),
        ):
            button = icon_button(icon, text)
            button.setCheckable(True)
            button.clicked.connect(lambda _=False, e=edge: on_edge(e))
            row.addWidget(button)
            self.edge_buttons[edge] = button
        self.on_name = on_name
        self.name_edit = QLineEdit()
        self.name_edit.returnPressed.connect(self.save_name)
        self.on_invite = on_invite
        self.server_label = QLabel()
        self.invite_button = QPushButton("▶ COLAR CONVITE")
        self.invite_button.clicked.connect(self.paste_invite)
        button = QPushButton("◀ VOLTAR")
        button.clicked.connect(on_done)
        self.box.addWidget(title)
        self.box.addWidget(QLabel("BORDA", objectName="muted"))
        self.box.addLayout(row)
        self.box.addSpacing(2 * PX)
        self.box.addWidget(QLabel("NOME", objectName="muted"))
        self.box.addWidget(self.name_edit)
        self.box.addSpacing(2 * PX)
        self.box.addWidget(QLabel("SERVIDOR", objectName="muted"))
        self.box.addWidget(self.server_label)
        self.box.addWidget(self.invite_button, alignment=Qt.AlignLeft)
        self.box.addWidget(button, alignment=Qt.AlignRight)

    def show_settings(self, edge: str, server: str, anchor: QRect) -> None:
        for e, button in self.edge_buttons.items():
            button.setChecked(e == edge)
        self.server_label.setText(server)
        self.show_at(anchor)
        self.activateWindow()

    def save_name(self) -> None:
        self.name_edit.setText(self.on_name(self.name_edit.text()))
        self.name_edit.clearFocus()

    def paste_invite(self) -> None:
        server = self.on_invite(QGuiApplication.clipboard().text())
        if server:
            self.server_label.setText(server)
        self.invite_button.setText("colado!" if server else "convite inválido")
        QTimer.singleShot(1500, lambda: self.invite_button.setText("▶ COLAR CONVITE"))


class History(Balloon):
    def __init__(self, on_done, on_clear):
        super().__init__()
        self.on_clear = on_clear
        self.setFixedWidth(340)
        title = QLabel("HISTÓRICO")
        bold = title.font()
        bold.setBold(True)
        title.setFont(bold)
        self.browser = QTextBrowser()
        self.clear_button = QPushButton("LIMPAR")
        self.clear_button.clicked.connect(self.clear)
        button = QPushButton("◀ VOLTAR")
        button.clicked.connect(on_done)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.clear_button)
        buttons.addWidget(button)
        self.box.addWidget(title)
        self.box.addWidget(self.browser)
        self.box.addLayout(buttons)

    def clear(self) -> None:
        if self.clear_button.text() == "LIMPAR":
            self.clear_button.setText("limpar mesmo?")
            return
        self.clear_button.setText("limpando…")
        self.on_clear()

    def show_html(self, body: str, anchor: QRect) -> None:
        self.clear_button.setText("LIMPAR")
        self.browser.setHtml(body)
        doc = self.browser.document()
        doc.setDocumentMargin(0)
        doc.setTextWidth(self.width() - 9 * PX)
        self.browser.setFixedHeight(min(int(doc.size().height()) + 4, 320))
        self.show_at(anchor)

    def show_items(self, items: list[dict], anchor: QRect) -> None:
        if not items:
            self.show_html("<p><i>Nenhuma mensagem lida ainda.</i></p>", anchor)
            return
        parts = []
        for m in items:
            head = " · ".join(html.escape(v) for v in (m.get("sender"), m.get("title")) if v)
            when = html.escape((m.get("read_at") or "")[:16].replace("T", " "))
            parts.append(
                f"<p style='margin-bottom:10px'><span style='color:{MUTED}'>{when} {head}</span><br>{html.escape(m['text'])}</p>"
            )
        self.show_html("".join(parts), anchor)


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
        self.clock = 0
        self.bubbles: list[tuple[int, int, tuple[str, ...]]] = []
        self.next_wave = BUBBLE_FIRST
        self.pixmaps = sprite.frames()
        self.connected = False
        self.backoff = 1

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(*self.edge_size())
        self.place()

        self.note = Note(self.on_note_done)
        self.history = History(self.on_history_done, self.clear_history)
        self.settings = Settings(self.set_edge, self.use_name, self.use_invite, self.show_menu)
        self.composer = Composer(self.post_message, self.show_menu)
        self.menu = Menu(self.load_clients, self.show_settings, self.load_history, self.toggle_sleep, self.on_menu_closed)
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

    def edge_size(self) -> tuple[int, int]:
        return (W, H) if self.cfg.edge == "bottom" else (H, W + LIFT)

    def place(self) -> None:
        g = QGuiApplication.primaryScreen().availableGeometry()
        x = g.left() if self.cfg.edge == "left" else g.right() - self.width() + 1
        self.move(x, g.bottom() - self.height() + 1)

    def strip_rect(self) -> QRect:
        sw, sh = self.width(), self.height()
        if self.cfg.edge == "bottom":
            return QRect((sw - sprite.PEEK_W) // 2, sh - 8, sprite.PEEK_W, 8)
        if self.cfg.edge == "right":
            return QRect(sw - 8, sh - LIFT - STRIP, 8, STRIP)
        return QRect(0, sh - LIFT - STRIP, 8, STRIP)

    def bubble_rects(self) -> list[tuple[QRect, tuple[str, ...]]]:
        strip = self.strip_rect()
        out = []
        for birth, along, rows in self.bubbles:
            age = self.clock - birth
            if not 0 <= age < BUBBLE_LIFE:
                continue
            if age >= BUBBLE_LIFE - 4:
                rows = BUBBLE_POP
            size = len(rows) * BUBBLE_PX
            d = 4 + BUBBLE_RISE * age // BUBBLE_LIFE
            a = along + round(2 * math.sin(age / 5))
            if self.cfg.edge == "bottom":
                x, y = strip.left() + a, self.height() - d - size
            elif self.cfg.edge == "right":
                x, y = self.width() - d - size, strip.top() + a
            else:
                x, y = d, strip.top() + a
            out.append((QRect(x, y, size, size), rows))
        return out

    def peeking(self) -> bool:
        return self.capivara.state == State.PEEKING or (self.capivara.state == State.HIDDEN and self.reveal > 0)

    def moving(self) -> bool:
        return self.capivara.state in (State.ENTERING, State.LEAVING)

    def pixmap(self):
        if self.peeking():
            frames = self.pixmaps[f"peek_{self.cfg.edge}"]
            if self.capivara.state != State.PEEKING or self.reveal < 1:
                return frames[0]
            return frames[self.ticks // sprite.PEEK_TICKS % sprite.FRAMES]
        walk = self.pixmaps["walk"]
        return walk[self.ticks // sprite.WALK_TICKS % sprite.FRAMES] if self.moving() else walk[0]

    def frame_transform(self) -> QTransform:
        pix = self.pixmap()
        w, h = pix.width(), pix.height()
        sw, sh = self.width(), self.height()
        r = self.reveal
        t = QTransform()
        if self.peeking():
            if self.cfg.edge == "bottom":
                t.translate((sw - w) // 2, round(sh - h * r) + PEEK_SINK)
            elif self.cfg.edge == "right":
                t.translate(round(sw - w * r) + PEEK_SINK, sh - h - LIFT)
            else:
                t.translate(round(-w + w * r) - PEEK_SINK, sh - h - LIFT)
            return t
        if self.cfg.edge == "bottom":
            t.translate(round(sw - (sw - REST) * r), sh - h + sprite.SINK)
            if self.capivara.state == State.LEAVING:
                t.translate(w, 0)
                t.scale(-1, 1)
            return t
        if self.cfg.edge == "right":
            t.translate(sw - h + sprite.SINK, round(sh - (sh - REST) * r))
        else:
            t.translate(h - sprite.SINK, round(sh - (sh - REST) * r))
            t.scale(-1, 1)
        if self.capivara.state == State.LEAVING:
            t.translate(0, w)
            t.scale(1, -1)
        return QTransform(0, 1, 1, 0, 0, 0) * t

    def capivara_rect(self) -> QRect:
        pix = self.pixmap()
        return self.frame_transform().mapRect(QRect(0, 0, pix.width(), pix.height())).intersected(self.rect())

    def anchor(self) -> QRect:
        reveal, self.reveal = self.reveal, self.target()
        rect = self.capivara_rect()
        self.reveal = reveal
        return rect.translated(self.pos())

    def badge_rect(self) -> QRect:
        center = self.frame_transform().map(QPointF(*sprite.BADGE_POS))
        return QRect(int(center.x()) - 11, max(int(center.y()) - 11, 0), 22, 22)

    def snore_rect(self) -> QRect:
        r = self.capivara_rect()
        w, h = len(SNORE[0]) * BUBBLE_PX, len(SNORE) * BUBBLE_PX
        if self.cfg.edge == "bottom":
            return QRect(r.center().x() + 10, r.top() - h, w, h)
        if self.cfg.edge == "right":
            return QRect(r.left() - w, r.top(), w, h)
        return QRect(r.right() + 1, r.top(), w, h)

    def snoring(self) -> bool:
        return self.capivara.asleep and self.peeking() and self.reveal > 0

    def update_mask(self) -> None:
        region = QRegion(self.strip_rect())
        for rect, _ in self.bubble_rects():
            region = region.united(QRegion(rect))
        if self.capivara.state != State.HIDDEN or self.reveal > 0:
            region = region.united(QRegion(self.capivara_rect()))
            if self.capivara.pile:
                region = region.united(QRegion(self.badge_rect()))
            if self.snoring():
                region = region.united(QRegion(self.snore_rect()))
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
        self.clock += 1
        if self.capivara.state == State.HIDDEN and self.reveal == 0:
            if self.clock >= self.next_wave:
                self.next_wave = self.clock + BUBBLE_EVERY
                strip = self.strip_rect()
                span = strip.width() if self.cfg.edge == "bottom" else strip.height()
                self.bubbles = [
                    (self.clock + i * BUBBLE_GAP, random.randint(6, span - 12), random.choice((BUBBLE_BIG, BUBBLE_SMALL)))
                    for i in range(3)
                ]
            if self.bubbles:
                if self.clock - self.bubbles[-1][0] >= BUBBLE_LIFE:
                    self.bubbles = []
                self.update_mask()
                self.update()
        else:
            self.bubbles = []
            self.next_wave = self.clock + BUBBLE_FIRST
        goal = self.target()
        step = WALK_STEP if self.moving() else HIDE_STEP if self.capivara.state == State.HIDDEN else STEP
        before = self.pixmap()
        changed = self.reveal != goal
        if changed:
            self.reveal = goal if abs(goal - self.reveal) <= step else self.reveal + math.copysign(step, goal - self.reveal)
            if self.reveal == 1 and self.peeking():
                self.ticks = 0
        if self.reveal == goal and self.moving():
            self.capivara.arrived()
            self.capivara.gone()
            changed = True
        if self.capivara.state != State.HIDDEN:
            self.ticks += 1
        if changed or self.pixmap() is not before:
            if changed:
                self.raise_()
            self.update_mask()
            self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.strip_rect(), QColor(0, 0, 0, 1))
        for rect, rows in self.bubble_rects():
            for y, row in enumerate(rows):
                for x, cell in enumerate(row):
                    if cell != ".":
                        color = BUBBLE_SHINE if cell == "O" else BUBBLE_INK
                        p.fillRect(rect.x() + x * BUBBLE_PX, rect.y() + y * BUBBLE_PX, BUBBLE_PX, BUBBLE_PX, color)
        if self.capivara.state == State.HIDDEN and self.reveal == 0:
            return
        p.save()
        p.setTransform(self.frame_transform())
        p.drawPixmap(0, 0, self.pixmap())
        p.restore()
        if self.snoring():
            p.drawPixmap(self.snore_rect().topLeft(), pixel_pixmap(SNORE, BUBBLE_INK.name(), BUBBLE_PX))
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
        if not any(b.isVisible() for b in (self.history, self.menu, self.settings, self.composer)):
            self.capivara.hover_out()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        if self.peeking():
            self.show_menu()
            return
        self.capivara.click()
        if self.capivara.state == State.READING:
            self.history.hide()
            self.note.show_message(self.capivara.current, self.anchor())

    def on_note_done(self) -> None:
        self.note.hide()
        read = self.capivara.note_closed()
        if read is not None and self.connected:
            self.ws.sendTextMessage(json.dumps({"type": "read", "id": read["id"]}))
        self.update_mask()
        self.update()

    def show_menu(self) -> None:
        self.history.hide()
        self.settings.hide()
        self.composer.hide()
        self.capivara.hold()
        self.menu.show_menu(self.cfg.name, self.connected, local_ip(), self.capivara.asleep, self.anchor())

    def show_settings(self) -> None:
        self.capivara.hover_in()
        self.update_mask()
        self.settings.name_edit.setText(self.cfg.name)
        self.settings.show_settings(self.cfg.edge, self.cfg.server, self.anchor())

    def use_invite(self, text: str) -> str:
        invite = config.parse_invite(text)
        if invite is None:
            return ""
        self.cfg.server, self.cfg.key = invite
        config.save(server=self.cfg.server, key=self.cfg.key)
        self.reconnect()
        return self.cfg.server

    def use_name(self, text: str) -> str:
        name = text.replace('"', "").replace("\\", "").strip()
        if name and name != self.cfg.name:
            self.cfg.name = name
            config.save(name=name)
            self.reconnect()
        return self.cfg.name

    def reconnect(self) -> None:
        self.backoff = 1
        self.ws.close()
        if self.reconnect_timer.isActive():
            self.reconnect_timer.start(0)

    def set_edge(self, edge: str) -> None:
        self.settings.show_settings(self.cfg.edge, self.cfg.server, self.anchor())
        if edge == self.cfg.edge:
            return
        self.cfg.edge = edge
        config.save(edge=edge)
        self.setFixedSize(*self.edge_size())
        self.place()
        self.reveal = 0.0
        self.update_mask()
        self.update()
        self.settings.show_settings(edge, self.cfg.server, self.anchor())

    def on_history_done(self) -> None:
        self.show_menu()

    def on_menu_closed(self, picked: bool) -> None:
        if not self.underMouse() and not self.history.isVisible():
            self.capivara.hover_out()
        if not picked:
            self.release()
        self.update_mask()
        self.update()

    def toggle_sleep(self) -> None:
        self.capivara.toggle_sleep()
        self.send_sleep()
        self.release()
        self.update_mask()
        self.update()

    def release(self) -> None:
        was_peeking = self.peeking()
        self.capivara.release()
        if was_peeking and not self.peeking():
            self.reveal = 0.0

    def open_socket(self) -> None:
        url = QUrl(self.cfg.ws_url + "/ws")
        query = QUrlQuery()
        query.addQueryItem("id", self.cfg.client_id)
        query.addQueryItem("name", self.cfg.name)
        query.addQueryItem("key", self.cfg.key)
        url.setQuery(query)
        self.ws.open(url)

    def on_connected(self) -> None:
        self.connected = True
        self.backoff = 1
        self.send_sleep()

    def send_sleep(self) -> None:
        if self.connected:
            self.ws.sendTextMessage(json.dumps({"type": "sleep", "asleep": self.capivara.asleep}))

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

    def api(self, path: str) -> QNetworkRequest:
        request = QNetworkRequest(QUrl(self.cfg.server.rstrip("/") + path))
        request.setRawHeader(b"Authorization", f"Bearer {self.cfg.key}".encode())
        return request

    def load_clients(self) -> None:
        self.capivara.hover_in()
        self.update_mask()
        reply = self.http.get(self.api("/clients"))
        reply.finished.connect(lambda: self.on_clients(reply))

    def on_clients(self, reply: QNetworkReply) -> None:
        people = []
        if reply.error() == QNetworkReply.NoError:
            people = [
                c for c in json.loads(bytes(reply.readAll()))
                if c["online"] and c["id"] != self.cfg.client_id
            ]
        self.composer.show_people(people, self.anchor())
        reply.deleteLater()

    def send_off(self) -> None:
        self.composer.hide()
        self.capivara.send_off()
        self.reveal = 1.0
        self.release()
        self.update_mask()
        self.update()

    def post_message(self, ids: list[str], text: str) -> None:
        request = self.api("/notify")
        request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")
        body = json.dumps({"text": text, "sender": self.cfg.name, "to": ids}).encode()
        reply = self.http.post(request, body)
        reply.finished.connect(lambda: self.on_posted(reply))

    def on_posted(self, reply: QNetworkReply) -> None:
        if reply.error() == QNetworkReply.NoError:
            self.send_off()
        else:
            self.composer.flash("erro ao enviar")
        reply.deleteLater()

    def load_history(self) -> None:
        self.capivara.hover_in()
        self.update_mask()
        url = QUrl(self.cfg.server.rstrip("/") + "/history")
        query = QUrlQuery()
        query.addQueryItem("id", self.cfg.client_id)
        query.addQueryItem("key", self.cfg.key)
        url.setQuery(query)
        reply = self.http.get(QNetworkRequest(url))
        reply.finished.connect(lambda: self.on_history(reply))

    def on_history(self, reply: QNetworkReply) -> None:
        if reply.error() == QNetworkReply.NoError:
            self.history.show_items(json.loads(bytes(reply.readAll())), self.anchor())
        else:
            self.history.show_html("<p><i>Não consegui falar com o servidor.</i></p>", self.anchor())
        reply.deleteLater()

    def clear_history(self) -> None:
        reply = self.http.deleteResource(self.api(f"/history?id={self.cfg.client_id}"))
        reply.finished.connect(lambda: self.on_history_cleared(reply))

    def on_history_cleared(self, reply: QNetworkReply) -> None:
        if reply.error() == QNetworkReply.NoError:
            self.history.show_items([], self.anchor())
        else:
            self.history.clear_button.setText("erro ao limpar")
        reply.deleteLater()


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("zoozap")
    app.setQuitOnLastWindowClosed(False)
    window = Window(config.load())
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
