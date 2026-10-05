from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap, QTransform

ASSETS = Path(__file__).parent / "assets"
SHEET = ASSETS / "spritesheet.png"
ROWS = {"peek": 0, "walk": 1, "sleep": 2, "run": 3}
FRAMES = 8
WALK_SCALE = 0.8
SINK = round(10 * WALK_SCALE)
BADGE_POS = (150 * WALK_SCALE, 20 * WALK_SCALE)
PEEK_TICKS = 6
WALK_TICKS = 3
RUN_TICKS = 2
PEEK_SCALE = 0.6


def bounds(img: QImage, cell: QRect) -> QRect:
    bits = bytes(img.constBits())
    line = img.bytesPerLine()
    top = bottom = left = right = None
    for y in range(cell.top(), cell.bottom() + 1):
        row = bits[y * line + cell.left() * 4 : y * line + (cell.right() + 1) * 4]
        if not row.strip(b"\0"):
            continue
        top = y if top is None else top
        bottom = y
        start = (len(row) - len(row.lstrip(b"\0"))) // 4
        end = (len(row.rstrip(b"\0")) + 3) // 4
        left = start if left is None else min(left, start)
        right = end if right is None else max(right, end)
    return QRect(cell.left() + left, top, right - left, bottom - top + 1)


def sheet() -> dict[str, list[QImage]]:
    img = QImage(str(SHEET)).convertToFormat(QImage.Format_ARGB32_Premultiplied)
    w, h = img.width() // FRAMES, img.height() // len(ROWS)
    crops = {
        name: [img.copy(bounds(img, QRect(i * w, row * h, w, h))) for i in range(FRAMES)]
        for name, row in ROWS.items()
    }
    groups = (("walk",), ("run",), ("peek", "sleep"))
    out = {}
    for group in groups:
        frames = [f for name in group for f in crops[name]]
        cw, ch = max(f.width() for f in frames), max(f.height() for f in frames)
        for name in group:
            out[name] = []
            for f in crops[name]:
                canvas = QImage(cw, ch, QImage.Format_ARGB32_Premultiplied)
                canvas.fill(Qt.transparent)
                p = QPainter(canvas)
                p.drawImage((cw - f.width()) // 2, ch - f.height(), f)
                p.end()
                out[name].append(canvas)
    return out


IMAGES = sheet()


def image(name: str, i: int, scale: float) -> QImage:
    img = IMAGES[name][i]
    return img if scale == 1 else img.scaledToWidth(round(img.width() * scale), Qt.SmoothTransformation)


def load(name: str, scale: float = 1) -> list[QPixmap]:
    return [QPixmap.fromImage(image(name, i, scale)) for i in range(FRAMES)]


def size(name: str, scale: float = 1) -> tuple[int, int]:
    img = image(name, 0, scale)
    return img.width(), img.height()


WALK_W, WALK_H = size("walk", WALK_SCALE)
PEEK_W, PEEK_H = size("peek", PEEK_SCALE)


def frames() -> dict[str, list[QPixmap]]:
    out = {"walk": load("walk", WALK_SCALE), "run": load("run", WALK_SCALE)}
    for name in ("peek", "sleep"):
        pix = load(name, PEEK_SCALE)
        out[f"{name}_bottom"] = pix
        out[f"{name}_right"] = [p.transformed(QTransform().rotate(-90)) for p in pix]
        out[f"{name}_left"] = [p.transformed(QTransform().rotate(90)) for p in pix]
    return out
