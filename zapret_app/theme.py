"""Монохромная палитра и функции для работы с цветами."""

BG = "#09090b"
CARD = "#18181b"
CARD_HI = "#222226"
BORDER = "#27272a"
TRACK = "#3f3f46"
MUTED = "#71717a"
SOFT = "#a1a1aa"
TEXT = "#fafafa"
WHITE = "#fafafa"
BLACK = "#09090b"
FONT = "Segoe UI"


def hex_to_rgb(color: str) -> tuple:
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in rgb)


def lerp(a, b, t: float) -> tuple:
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def blend(a: str, b: str, t: float) -> str:
    return rgb_to_hex(lerp(hex_to_rgb(a), hex_to_rgb(b), t))
