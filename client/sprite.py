from pathlib import Path

from PySide6.QtGui import QImage, QPixmap, QTransform

ASSETS = Path(__file__).parent / "assets"
FRAMES = 8
SINK = 10
BADGE_POS = (150, 20)
PEEK_TICKS = 6
WALK_TICKS = 3


def load(name: str) -> list[QPixmap]:
    return [QPixmap.fromImage(QImage(str(ASSETS / f"{name}_{i}.png"))) for i in range(FRAMES)]


def size(name: str) -> tuple[int, int]:
    image = QImage(str(ASSETS / f"{name}_0.png"))
    return image.width(), image.height()


WALK_W, WALK_H = size("walk")
PEEK_W, PEEK_H = size("peek")


def frames() -> dict[str, list[QPixmap]]:
    peek = load("peek")
    return {
        "walk": load("walk"),
        "peek_bottom": peek,
        "peek_right": [p.transformed(QTransform().rotate(-90)) for p in peek],
        "peek_left": [p.transformed(QTransform().rotate(90)) for p in peek],
    }
