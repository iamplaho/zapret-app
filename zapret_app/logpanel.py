"""Нижняя панель журнала: последние события, кнопки «Развернуть» и «Очистить»."""
import customtkinter as ctk

from .theme import BG, CARD, CARD_HI, FONT, SOFT, TEXT, TRACK


def _font(size, weight="normal"):
    return ctk.CTkFont(family=FONT, size=size, weight=weight)


def small_button():
    return dict(fg_color=CARD_HI, hover_color=TRACK, text_color=TEXT, font=_font(11), corner_radius=8)


class LogPanel(ctk.CTkFrame):
    def __init__(self, master, on_expand, on_clear):
        super().__init__(master, fg_color=CARD, corner_radius=16)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(10, 0))
        ctk.CTkLabel(header, text="Журнал", font=_font(11, "bold"), text_color=SOFT).pack(side="left")
        ctk.CTkButton(header, text="Очистить", width=84, height=24,
                      command=on_clear, **small_button()).pack(side="right")
        ctk.CTkButton(header, text="Развернуть", width=96, height=24,
                      command=on_expand, **small_button()).pack(side="right", padx=(0, 6))
        self.box = ctk.CTkTextbox(self, height=84, corner_radius=10, fg_color=BG, text_color=SOFT,
                                  font=ctk.CTkFont(family="Consolas", size=11), state="disabled")
        self.box.pack(fill="both", expand=True, padx=10, pady=(6, 10))

    def append(self, line: str) -> None:
        self.box.configure(state="normal")
        self.box.insert("end", line)
        self.box.see("end")
        self.box.configure(state="disabled")

    def set_text(self, text: str) -> None:
        self.box.configure(state="normal")
        self.box.delete("1.0", "end")
        self.box.insert("end", text)
        self.box.see("end")
        self.box.configure(state="disabled")
