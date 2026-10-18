"""Монохромная палитра и цвета журнала."""

BG = "#09090b"
CARD = "#18181b"
CARD_HI = "#25252b"
BORDER = "#2a2a30"
TRACK = "#3f3f46"
MUTED = "#9494a0"
SOFT = "#b8b8c2"
TEXT = "#fafafa"
WHITE = "#fafafa"
BLACK = "#09090b"
FONT = "Segoe UI"

# цвета журнала
LOG_COLORS = {
    "default": "#fafafa",   # обычные строки — белые
    "ok": "#4ade80",        # успех, работает, хорошо — зелёный
    "warn": "#facc15",      # предупреждение, средний результат — жёлтый
    "err": "#f87171",       # ошибка, плохо — красный
    "update": "#7dd3fc",    # версии, списки, обновления — голубой
}


def hex_to_rgb(color: str) -> tuple:
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in rgb)


def lerp(a, b, t: float) -> tuple:
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def blend(a: str, b: str, t: float) -> str:
    return rgb_to_hex(lerp(hex_to_rgb(a), hex_to_rgb(b), t))
