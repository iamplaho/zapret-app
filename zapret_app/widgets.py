"""Собственные виджеты на обычном Tk: без скруглений и без артефактов CustomTkinter.

ToggleSwitch — переключатель с плавной анимацией ползунка.
ScrollArea   — прокручиваемая область (колесо мыши, перетаскивание полосы).
TabBar       — вкладки с бегущей полоской под активной вкладкой.
"""
import tkinter as tk

from .theme import BG, CARD, CARD_HI, FONT, SOFT, TEXT, TRACK, WHITE, BLACK, hex_to_rgb, lerp, rgb_to_hex

KNOB_OFF = "#a1a1aa"


class ToggleSwitch(tk.Canvas):
    W, H = 46, 24

    def __init__(self, master, variable, command=None, bg=CARD):
        super().__init__(master, width=self.W, height=self.H, bg=bg, highlightthickness=0, bd=0,
                         cursor="hand2")
        self.var = variable
        self._command = command
        self._pos = 1.0 if variable.get() else 0.0
        self._target = self._pos
        self._job = None
        self.bind("<Button-1>", self._on_click)
        self._draw()

    def _on_click(self, _event=None):
        self.var.set(not self.var.get())
        self._target = 1.0 if self.var.get() else 0.0
        self._animate()
        if self._command:
            self._command()

    def set(self, flag: bool) -> None:
        """Устанавливает положение с анимацией, без вызова команды."""
        self.var.set(flag)
        self._target = 1.0 if flag else 0.0
        self._animate()

    def _animate(self):
        if self._job is None:
            self._step()

    def _step(self):
        diff = self._target - self._pos
        if abs(diff) < 0.02:
            self._pos = self._target
            self._draw()
            self._job = None
            return
        self._pos += diff * 0.28
        self._draw()
        self._job = self.after(16, self._step)

    def _draw(self):
        self.delete("all")
        pos = self._pos
        track = rgb_to_hex(lerp(hex_to_rgb(TRACK), hex_to_rgb(WHITE), pos))
        self.create_rectangle(0, 0, self.W, self.H, fill=track, outline="")
        pad = 3
        size = self.H - 2 * pad
        x = pad + (self.W - 2 * pad - size) * pos
        knob = rgb_to_hex(lerp(hex_to_rgb(KNOB_OFF), hex_to_rgb(BLACK), pos))
        self.create_rectangle(x, pad, x + size, pad + size, fill=knob, outline="")


class ScrollArea(tk.Frame):
    """Прокрутка: внутрь кладите виджеты в self.inner."""

    BAR_W = 6

    def __init__(self, master, bg=BG):
        super().__init__(master, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.bar = tk.Canvas(self, width=self.BAR_W, bg=bg, highlightthickness=0, bd=0)
        self.bar.pack(side="right", fill="y", padx=(6, 0))
        self._thumb = None
        self.canvas.configure(yscrollcommand=self._on_scroll)
        self.inner.bind("<Configure>", self._on_inner)
        self.canvas.bind("<Configure>", self._on_canvas)
        self.inner.bind("<Enter>", lambda _e: self._bind_wheel(True))
        self.inner.bind("<Leave>", lambda _e: self._bind_wheel(False))
        self.bar.bind("<Button-1>", self._drag)
        self.bar.bind("<B1-Motion>", self._drag)

    def _on_inner(self, event):
        self.canvas.configure(scrollregion=(0, 0, event.width, event.height))

    def _on_canvas(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)

    def _on_scroll(self, first, last):
        first, last = float(first), float(last)
        self.bar.delete("all")
        height = self.bar.winfo_height() or 1
        if last - first >= 0.999:
            return  # прокрутка не нужна
        top = first * height
        bottom = last * height
        self.bar.create_rectangle(0, top, self.BAR_W, bottom, fill=TRACK, outline="")

    def _drag(self, event):
        height = self.bar.winfo_height() or 1
        self.canvas.yview_moveto(max(0.0, min(1.0, event.y / height)))

    def _bind_wheel(self, on: bool):
        if on:
            self.bind_all("<MouseWheel>", self._wheel)
        else:
            self.unbind_all("<MouseWheel>")

    def _wheel(self, event):
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")


class TabBar(tk.Frame):
    """Вкладки. Полоска под активной вкладкой плавно уезжает к новой."""

    def __init__(self, master, names, command):
        super().__init__(master, bg=CARD)
        self._names = list(names)
        self._command = command
        self._cells = {}
        self._active = None
        self._relx = 0.0
        self._job = None
        row = tk.Frame(self, bg=CARD)
        row.pack(fill="x")
        for i, name in enumerate(self._names):
            label = tk.Label(row, text=name, bg=CARD, fg=SOFT, font=(FONT, 12), pady=11, cursor="hand2")
            label.grid(row=0, column=i, sticky="nsew")
            row.columnconfigure(i, weight=1)
            label.bind("<Button-1>", lambda _e, n=name: self._command(n))
            label.bind("<Enter>", lambda _e, l=label: l.configure(bg=CARD_HI) if l.cget("fg") != TEXT else None)
            label.bind("<Leave>", lambda _e, l=label: l.configure(bg=CARD))
            self._cells[name] = label
        self._bar = tk.Frame(self, bg=WHITE, height=2)
        self._bar.place(relx=0.0, rely=1.0, anchor="sw", relwidth=1 / len(self._names), height=2)

    def set(self, name: str) -> None:
        for n, label in self._cells.items():
            active = n == name
            label.configure(fg=TEXT if active else SOFT, bg=CARD_HI if active else CARD)
        target = self._names.index(name) / len(self._names)
        if self._active is None:
            self._relx = target
            self._bar.place_configure(relx=target)
        else:
            self._glide(self._relx, target, 0)
        self._active = name

    def _glide(self, start, end, step):
        if self._job is not None:
            self.after_cancel(self._job)
        t = min(1.0, step / 12)
        eased = 1 - (1 - t) ** 3
        self._relx = start + (end - start) * eased
        self._bar.place_configure(relx=self._relx)
        if t < 1.0:
            self._job = self.after(16, lambda: self._glide(start, end, step + 1))
        else:
            self._job = None
