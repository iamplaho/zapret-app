"""Панель журнала: цветные строки, подсветка новых строк и кнопки «Развернуть» / «Очистить»."""
import customtkinter as ctk

from .theme import BG, CARD, CARD_HI, FONT, LOG_COLORS, SOFT, TEXT, TRACK, WHITE, hex_to_rgb, lerp, rgb_to_hex


def _font(size, weight="normal"):
    return ctk.CTkFont(family=FONT, size=size, weight=weight)


def small_button():
    return dict(fg_color=CARD_HI, hover_color=TRACK, text_color=TEXT, font=_font(11), corner_radius=0)


class LogPanel(ctk.CTkFrame):
    FADE_STEPS = 10
    FADE_MS = 36

    def __init__(self, master, on_toggle, on_clear):
        super().__init__(master, fg_color=CARD, corner_radius=0)
        header = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0)
        header.pack(fill="x", padx=14, pady=(10, 0))
        ctk.CTkLabel(header, text="Журнал (log)", font=_font(11, "bold"), text_color=SOFT).pack(side="left")
        ctk.CTkButton(header, text="Очистить", width=88, height=26,
                      command=on_clear, **small_button()).pack(side="right")
        self.expand_btn = ctk.CTkButton(header, text="Развернуть", width=104, height=26,
                                        command=on_toggle, **small_button())
        self.expand_btn.pack(side="right", padx=(0, 6))
        self.box = ctk.CTkTextbox(self, height=70, corner_radius=0, fg_color=BG, border_width=0,
                                  text_color=TEXT, font=ctk.CTkFont(family="Consolas", size=11), state="disabled")
        self.box.pack(fill="both", expand=True, padx=12, pady=(8, 12))
        self._text = self.box._textbox  # tk.Text: нужен для цветных тегов и подсветки
        self._n = 0
        for tag, color in LOG_COLORS.items():
            self._text.tag_configure(tag, foreground=color)

    def append(self, line: str, tag: str = "default") -> None:
        base_tag = tag if tag in LOG_COLORS else "default"
        base = hex_to_rgb(LOG_COLORS[base_tag])
        flash = lerp(base, hex_to_rgb(WHITE), 0.65)
        self._n += 1
        fade_tag = f"fade{self._n}"
        self._text.tag_configure(fade_tag, foreground=rgb_to_hex(flash))
        self.box.configure(state="normal")
        self._text.insert("end", line, (base_tag, fade_tag))
        self._text.see("end")
        self.box.configure(state="disabled")
        for step in range(1, self.FADE_STEPS + 1):
            t = step / self.FADE_STEPS
            color = rgb_to_hex(lerp(flash, base, t))
            self.after(step * self.FADE_MS,
                       lambda c=color, tg=fade_tag: self._safe_tag(tg, c))

    def _safe_tag(self, tag, color):
        try:
            self._text.tag_configure(tag, foreground=color)
        except Exception:  # noqa: BLE001  окно могло закрыться
            pass

    def set_text(self, text: str) -> None:
        self.box.configure(state="normal")
        self._text.delete("1.0", "end")
        self.box.configure(state="disabled")

    def set_expanded(self, flag: bool) -> None:
        self.expand_btn.configure(text="Свернуть" if flag else "Развернуть")
