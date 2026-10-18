"""Зона включения: круг по центру и летающие частицы вокруг него.

Частицы считаются только когда зона видна (главная вкладка, окно не свёрнуто).
В трее и на других вкладках анимация полностью останавливается, чтобы не нагружать ПК.
"""
import math
import random
import tkinter as tk

from .theme import BG, BLACK, MUTED, TRACK, WHITE, hex_to_rgb, lerp, rgb_to_hex

W = 404
H = 220
CX = W / 2
CY = H / 2
RADIUS = 56
PARTICLES = 30
FRAME_MS = 33
PULSE_HIGH = "#e4e4e7"


class PowerCircle(tk.Canvas):
    """Состояния: off, starting, on, stopping."""

    def __init__(self, master, command):
        super().__init__(master, width=W, height=H, bg=BG, highlightthickness=0, bd=0, cursor="hand2")
        self._command = command
        self._state = "off"
        self._core = hex_to_rgb(TRACK)
        self._halo = hex_to_rgb(BG)
        self._phase = 0.0
        self._press = 0.0
        self._active = False
        self._job = None
        self._particles = [self._new_particle() for _ in range(PARTICLES)]
        self.bind("<Button-1>", self._on_click)
        self._draw()

    # ---------- управление анимацией ----------

    def set_state(self, state: str) -> None:
        self._state = state

    def set_active(self, flag: bool) -> None:
        """Включает или выключает анимацию. Выключенная анимация не тратит ресурсы."""
        if flag and not self._active:
            self._active = True
            self._tick()
        elif not flag and self._active:
            self._active = False
            if self._job is not None:
                self.after_cancel(self._job)
                self._job = None

    def _on_click(self, _event):
        self._press = 1.0
        self._command()

    # ---------- частицы ----------

    def _new_particle(self, anywhere: bool = True) -> dict:
        return {
            "x": random.uniform(0, W),
            "y": random.uniform(0, H) if anywhere else H + random.uniform(0, 20),
            "vx": random.uniform(-0.16, 0.16),
            "vy": random.uniform(-0.38, -0.10),
            "r": random.uniform(0.9, 2.6),
            "phase": random.uniform(0, math.tau),
        }

    def _move_particles(self) -> None:
        for p in self._particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["phase"] += 0.05
            if p["y"] < -6 or p["x"] < -6 or p["x"] > W + 6:
                p.update(self._new_particle(anywhere=False))

    def _particle_color(self, p: dict) -> str:
        wave = (math.sin(p["phase"]) + 1) / 2
        if self._state == "on":
            alpha = 0.22 + 0.34 * wave
        elif self._state in ("starting", "stopping"):
            alpha = 0.18 + 0.30 * wave
        else:
            alpha = 0.08 + 0.12 * wave
        return rgb_to_hex(lerp(hex_to_rgb(BG), hex_to_rgb(WHITE), alpha))

    # ---------- кадр ----------

    def _tick(self) -> None:
        if not self._active:
            return
        self._phase += 0.09
        self._press *= 0.80
        self._move_particles()
        bg_rgb = hex_to_rgb(BG)
        if self._state in ("starting", "stopping"):
            k = (math.sin(self._phase) + 1) / 2
            self._core = lerp(hex_to_rgb(TRACK), hex_to_rgb(PULSE_HIGH), k)
            self._halo = lerp(bg_rgb, hex_to_rgb(WHITE), 0.05 + 0.07 * k)
        else:
            on = self._state == "on"
            breath = (math.sin(self._phase * 0.45) + 1) / 2 if on else 0.0
            core_target = hex_to_rgb(WHITE) if on else hex_to_rgb(TRACK)
            halo_target = lerp(bg_rgb, hex_to_rgb(WHITE), (0.07 + 0.07 * breath) if on else 0.0)
            self._core = lerp(self._core, core_target, 0.2)
            self._halo = lerp(self._halo, halo_target, 0.2)
        self._draw()
        self._job = self.after(FRAME_MS, self._tick)

    def _draw(self) -> None:
        self.delete("all")
        for p in self._particles:
            r = p["r"]
            self.create_oval(p["x"] - r, p["y"] - r, p["x"] + r, p["y"] + r,
                             fill=self._particle_color(p), outline="")
        r = RADIUS - 4 * self._press
        core = rgb_to_hex(self._core)
        halo = rgb_to_hex(self._halo)
        ring = rgb_to_hex(lerp(self._core, hex_to_rgb(BG), 0.55))
        self.create_oval(CX - r - 18, CY - r - 18, CX + r + 18, CY + r + 18, fill=halo, outline="")
        self.create_oval(CX - r - 6, CY - r - 6, CX + r + 6, CY + r + 6, outline=ring, width=1)
        self.create_oval(CX - r, CY - r, CX + r, CY + r, fill=core, outline="")
        glyph = BLACK if self._state == "on" else MUTED
        g = 20
        self.create_arc(CX - g, CY - g + 4, CX + g, CY + g + 4, start=120, extent=300,
                        style=tk.ARC, outline=glyph, width=4)
        self.create_line(CX, CY - g - 2, CX, CY - 4, fill=glyph, width=4, capstyle=tk.ROUND)
