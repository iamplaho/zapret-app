"""Панель журнала: цветные строки, кнопки «Развернуть» и «Очистить»."""
import customtkinter as ctk

from .theme import BG, CARD, CARD_HI, FONT, LOG_COLORS, SOFT, TEXT, TRACK


def _font(size, weight="normal"):
    return ctk.CTkFont(family=FONT, size=size, weight=weight)


def small_button():
    return dict(fg_color=CARD_HI, hover_color=TRACK, text_color=TEXT, font=_font(11),
                corner_radius=10, bg_color=CARD)


class LogPanel(ctk.CTkFrame):
    def __init__(self, master, on_toggle, on_clear):
        super().__init__(master, fg_color=CARD, corner_radius=18)
        header = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0)
        header.pack(fill="x", padx=14, pady=(10, 0))
        ctk.CTkLabel(header, text="Журнал (log)", font=_font(11, "bold"), text_color=SOFT).pack(side="left")
        ctk.CTkButton(header, text="Очистить", width=88, height=26,
                      command=on_clear, **small_button()).pack(side="right")
        self.expand_btn = ctk.CTkButton(header, text="Развернуть", width=104, height=26,
                                        command=on_toggle, **small_button())
        self.expand_btn.pack(side="right", padx=(0, 6))
        self.box = ctk.CTkTextbox(self, corner_radius=12, fg_color=BG, border_width=0,
                                  text_color=TEXT, bg_color=CARD,
                                  font=ctk.CTkFont(family="Consolas", size=11), state="disabled")
        self.box.pack(fill="both", expand=True, padx=12, pady=(8, 12))
        self._text = self.box._textbox  # tk.Text: нужен для цветных тегов
        for tag, color in LOG_COLORS.items():
            self._text.tag_configure(tag, foreground=color)

    def append(self, line: str, tag: str = "default") -> None:
        self.box.configure(state="normal")
        self._text.insert("end", line, tag if tag in LOG_COLORS else "default")
        self._text.see("end")
        self.box.configure(state="disabled")

    def set_text(self, text: str) -> None:
        self.box.configure(state="normal")
        self._text.delete("1.0", "end")
        self.box.configure(state="disabled")

    def set_expanded(self, flag: bool) -> None:
        self.expand_btn.configure(text="Свернуть" if flag else "Развернуть")
