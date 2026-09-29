from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QTransform

ASSETS = Path(__file__).parent / "assets"
FRAMES = 8
WALK_SCALE = 0.8
SINK = round(10 * WALK_SCALE)
BADGE_POS = (150 * WALK_SCALE, 20 * WALK_SCALE)
PEEK_TICKS = 6
WALK_TICKS = 3
PEEK_SCALE = 0.6


def image(name: str, i: int, scale: float) -> QImage:
    img = QImage(str(ASSETS / f"{name}_{i}.png"))
    return img if scale == 1 else img.scaledToWidth(round(img.width() * scale), Qt.SmoothTransformation)


def load(name: str, scale: float = 1) -> list[QPixmap]:
    return [QPixmap.fromImage(image(name, i, scale)) for i in range(FRAMES)]


def size(name: str, scale: float = 1) -> tuple[int, int]:
    img = image(name, 0, scale)
    return img.width(), img.height()


WALK_W, WALK_H = size("walk", WALK_SCALE)
PEEK_W, PEEK_H = size("peek", PEEK_SCALE)


def frames() -> dict[str, list[QPixmap]]:
    peek = load("peek", PEEK_SCALE)
    return {
        "walk": load("walk", WALK_SCALE),
        "peek_bottom": peek,
        "peek_right": [p.transformed(QTransform().rotate(-90)) for p in peek],
        "peek_left": [p.transformed(QTransform().rotate(90)) for p in peek],
    }
