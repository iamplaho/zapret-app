"""Круглая кнопка включения: меняет цвет по статусу и плавно анимируется."""
import math
import tkinter as tk

from .theme import BG, BLACK, MUTED, TRACK, WHITE, hex_to_rgb, lerp, rgb_to_hex

SIZE = 200
RADIUS = 64
FRAME_MS = 33
PULSE_HIGH = "#e4e4e7"


class PowerCircle(tk.Canvas):
    """Состояния: off, starting, on, stopping."""

    def __init__(self, master, command):
        super().__init__(master, width=SIZE, height=SIZE, bg=BG, highlightthickness=0, bd=0, cursor="hand2")
        self._command = command
        self._state = "off"
        self._core = hex_to_rgb(TRACK)
        self._halo = hex_to_rgb(BG)
        self._phase = 0.0
        self.bind("<Button-1>", lambda _event: self._command())
        self._tick()

    def set_state(self, state: str) -> None:
        self._state = state

    def _tick(self) -> None:
        self._phase += 0.09
        bg_rgb = hex_to_rgb(BG)
        if self._state in ("starting", "stopping"):
            k = (math.sin(self._phase) + 1) / 2
            self._core = lerp(hex_to_rgb(TRACK), hex_to_rgb(PULSE_HIGH), k)
            self._halo = lerp(bg_rgb, hex_to_rgb(WHITE), 0.05 + 0.07 * k)
        else:
            on = self._state == "on"
            core_target = hex_to_rgb(WHITE) if on else hex_to_rgb(TRACK)
            halo_target = lerp(bg_rgb, hex_to_rgb(WHITE), 0.10) if on else bg_rgb
            self._core = lerp(self._core, core_target, 0.2)
            self._halo = lerp(self._halo, halo_target, 0.2)
        self._draw()
        self.after(FRAME_MS, self._tick)

    def _draw(self) -> None:
        self.delete("all")
        c = SIZE / 2
        r = RADIUS
        core = rgb_to_hex(self._core)
        halo = rgb_to_hex(self._halo)
        ring = rgb_to_hex(lerp(self._core, hex_to_rgb(BG), 0.55))
        self.create_oval(c - r - 20, c - r - 20, c + r + 20, c + r + 20, fill=halo, outline="")
        self.create_oval(c - r - 7, c - r - 7, c + r + 7, c + r + 7, outline=ring, width=1)
        self.create_oval(c - r, c - r, c + r, c + r, fill=core, outline="")
        glyph = BLACK if self._state == "on" else MUTED
        g = 22
        # значок питания: дуга с разрывом сверху и вертикальная черта
        self.create_arc(c - g, c - g + 4, c + g, c + g + 4, start=120, extent=300,
                        style=tk.ARC, outline=glyph, width=4)
        self.create_line(c, c - g - 2, c, c - 4, fill=glyph, width=4, capstyle=tk.ROUND)
