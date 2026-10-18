"""Главное окно zapret-app: фиксированный размер, монохромный стиль, цветной журнал."""
import datetime as dt
import os
import queue
import sys
import threading
import time
import tkinter as tk

import customtkinter as ctk

from . import __version__, app_updater, diagnostics, engine, fakes, hosts, paths, settings, strategies
from . import system, tester, updater
from .logpanel import LogPanel, small_button
from .widgets import ScrollArea, TabBar, ToggleSwitch
from .power_circle import PowerCircle
from .theme import BG, BLACK, CARD, CARD_HI, FONT, MUTED, SOFT, TEXT, TRACK, WHITE

try:
    from .tray import Tray
except Exception:  # noqa: BLE001  pystray недоступен — работаем без трея
    Tray = None

WIDTH, HEIGHT = 440, 760
WATCHDOG_MS = 10 * 60 * 1000
CHECK_INTERVAL = 6 * 3600          # автоматическая проверка не чаще раза в 6 часов
NEUTRAL_URL = "https://www.gstatic.com/generate_204"

STATE_TEXT = {"off": "Выключено", "starting": "Запуск…", "on": "Работает", "stopping": "Остановка…"}
STATE_HINT = {
    "off": "Нажмите на круг, чтобы включить обход",
    "starting": "Подождите, обход запускается",
    "on": "Обход работает. Нажмите на круг, чтобы выключить",
    "stopping": "Останавливаю обход",
}
GAME_LABELS = {"off": "Выключен (off)", "all": "TCP и UDP (all)",
               "tcp": "Только TCP (tcp)", "udp": "Только UDP (udp)"}
GAME_SHORT = {"off": "выкл", "all": "TCP+UDP", "tcp": "TCP", "udp": "UDP"}
IPSET_LABELS = {"loaded": "Полный список (loaded)", "none": "Выключен (none)", "any": "Любые IP (any)"}
IPSET_SHORT = {"loaded": "полный", "none": "выкл", "any": "любые"}
CHECK_KIND = {"ok": "ok", "warn": "warn", "error": "err", "info": "default"}
CHECK_PREFIX = {"ok": "[ОК]", "warn": "[!]", "error": "[X]", "info": "[i]"}
SWITCHES = [
    ("start_bypass", "Включать при открытии (start on launch)",
     "Обход запускается сам, когда вы открываете программу"),
    ("auto_fix", "Чинить сам (auto-fix)",
     "Если Discord и YouTube перестали открываться, стратегия подберётся заново"),
    ("auto_update", "Обновлять списки (lists update)",
     "Домены и IP берутся из официального репозитория"),
    ("auto_update_app", "Обновлять программу (self-update)",
     "Новые версии с GitHub ставятся сами"),
    ("autostart", "Запускать с Windows (autostart)",
     "Программа стартует в трее и включает обход"),
    ("close_to_tray", "Сворачивать в трей (tray)",
     "Крестик скрывает окно, обход продолжает работать"),
]
WRAP = 330


def font(size, weight="normal"):
    return ctk.CTkFont(family=FONT, size=size, weight=weight)


def primary_button(bg=BG):
    return dict(fg_color=WHITE, hover_color="#e4e4e7", text_color=BLACK, font=font(13, "bold"),
                corner_radius=0, bg_color=bg)


def secondary_button(bg=BG):
    return dict(fg_color=CARD_HI, hover_color=TRACK, text_color=TEXT, font=font(13),
                corner_radius=0, bg_color=bg)


def switch_style(bg=CARD):
    return dict(fg_color=TRACK, progress_color=SOFT, button_color=WHITE,
                button_hover_color="#e4e4e7", text_color=TEXT, font=font(13), bg_color=bg)


def menu_style(bg=CARD):
    return dict(fg_color=CARD_HI, button_color=TRACK, button_hover_color="#52525b", text_color=TEXT,
                dropdown_fg_color=CARD, dropdown_hover_color=CARD_HI, dropdown_text_color=TEXT,
                font=font(13), dropdown_font=font(13), corner_radius=0, bg_color=bg)


def entry_style(bg=CARD):
    return dict(fg_color=CARD_HI, border_width=0, text_color=TEXT, font=font(13),
                corner_radius=0, bg_color=bg)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.configure(fg_color=BG)
        self.title("zapret-app")
        self.geometry(f"{WIDTH}x{HEIGHT}")
        self.resizable(False, False)
        self.after(300, lambda: self._set_icon(self))

        try:
            paths.ensure_data_dirs()
        except OSError as exc:
            print(f"Не удалось создать папки данных: {exc}")
        self.cfg = settings.load()
        self.cfg["autostart"] = system.autostart_enabled()
        self.strategy_list = strategies.load_all()

        self._running = False
        self._service = False
        self._busy = False
        self._test_running = False
        self._then_start = False
        self._busy_update = False
        self._busy_app = False
        self._latest = None
        self._log_expanded = False
        self._log_anim_job = None
        self._log_normal_h = 150
        self._tab = "Главная"
        self._ipset_mode = updater.ipset_mode()
        self._cancel = threading.Event()
        self._queue = queue.Queue()
        self._pending_update = None
        self._lines = []
        self.vars = {}
        self.switches = {}
        self.switch_titles = {}
        self.tray = None

        self._build()
        self.after(100, self._pump)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._start_tray()

        self.log(f"Приложение запущено, версия {__version__}", "update")
        if not system.is_admin():
            self.log("Нет прав администратора: обход не запустится. Запустите программу от имени администратора.", "err")

        self._set_visual("off")
        self._refresh_status()
        self._update_summary()
        now = time.time()
        if self.cfg["auto_update"] and now - self.cfg["last_list_ts"] > CHECK_INTERVAL:
            self.after(1000, lambda: self._check_lists(silent=True))
        if self.cfg["auto_update_app"] and now - self.cfg["last_app_ts"] > CHECK_INTERVAL:
            self.after(2000, lambda: self._check_app(manual=False))
        self.after(2500, self._startup_actions)
        self.after(WATCHDOG_MS, self._watchdog)
        self.after(5000, self._poll)
        self.bind("<Unmap>", self._on_unmap)
        self.bind("<Map>", self._on_map)

    # ---------- окно, иконка, трей ----------

    def _set_icon(self, window):
        if paths.ICON_ICO.exists():
            try:
                window.iconbitmap(str(paths.ICON_ICO))
            except tk.TclError:
                pass

    def _start_tray(self):
        if Tray is None:
            return
        try:
            self.tray = Tray(
                on_open=lambda: self._from_tray(self._show),
                on_toggle=lambda: self._from_tray(self.toggle),
                on_quit=lambda: self._from_tray(self._quit),
            )
            self.tray.start()
        except Exception as exc:  # noqa: BLE001
            self.tray = None
            self.log(f"Значок в трее недоступен: {exc}", "warn")

    def _from_tray(self, fn):
        self._post(fn)

    def _show(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _on_close(self):
        if self.cfg["close_to_tray"] and self.tray:
            self.withdraw()
        else:
            self._quit()

    def _quit(self):
        if self.tray:
            self.tray.stop()
        self.destroy()

    def _on_unmap(self, event):
        if event.widget is self:
            self.circle.set_active(False)

    def _on_map(self, event):
        if event.widget is self:
            self.circle.set_active(self._tab == "Главная" and not self._log_expanded)

    def _startup_actions(self):
        if "--autostart" in sys.argv and self.tray:
            self.withdraw()
        if self.cfg.get("resume_bypass"):
            self.cfg["resume_bypass"] = False
            settings.save(self.cfg)
            self._start_if_idle("Возобновляю обход после обновления…")
        elif self.cfg["first_run"]:
            self.log("Первый запуск: подбираю лучшую стратегию для вашей сети. Это займёт несколько минут.")
            self._run_test(all_mode=True, then_start=True)
        elif self.cfg["start_bypass"] or "--autostart" in sys.argv:
            self._start_if_idle("Включаю обход…")

    # ---------- компоновка ----------

    def _build(self):
        self.tabs = TabBar(self, ["Главная", "Настройки", "Сервис"], self._on_tab_click)
        self.logpanel = LogPanel(self, on_toggle=self.toggle_log, on_clear=self.clear_log)
        self.container = tk.Frame(self, bg=BG)
        self.frames = {
            "Главная": self._build_main(),
            "Настройки": self._build_settings(),
            "Сервис": self._build_service(),
        }
        self._tab = None
        self._cur_frame = None
        self._slide_job = None
        self._show_tab("Главная", animate=False)
        self._layout()

    def _layout(self):
        """Порядок элементов: вкладки, журнал внизу, содержимое. Журнал можно раскрыть на всё окно."""
        for widget in (self.tabs, self.logpanel, self.container):
            widget.pack_forget()
        if self._log_expanded:
            self.logpanel.pack(fill="both", expand=True, padx=20, pady=16)
        else:
            self.tabs.pack(fill="x", padx=20, pady=(16, 10))
            self.logpanel.pack(side="bottom", fill="x", padx=20, pady=(0, 16))
            self.container.pack(fill="both", expand=True, padx=20, pady=(0, 10))

    def toggle_log(self):
        """Журнал плавно растягивается на всё окно или возвращается вниз.

        Анимация только через pack (высота текстовой области), без place:
        смешивание place и pack раньше ломало отображение журнала.
        """
        if self._log_anim_job is not None:
            return
        expanding = not self._log_expanded
        self._log_expanded = expanding
        self.logpanel.set_expanded(expanding)
        self.circle.set_active(False)
        self._log_anim_job = True  # блокируем повторные нажатия на время анимации
        if expanding:
            self._log_normal_h = max(self.logpanel.box.winfo_height(), 70)
            start = self._log_normal_h
            target = max(self.winfo_height() - 150, 200)
        else:
            start = self.logpanel.box.winfo_height()
            target = self._log_normal_h
            self.tabs.pack(fill="x", padx=20, pady=(16, 10))
            self.container.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        self._anim_log(start, target, 0)

    def _anim_log(self, start, target, step):
        steps = 18
        t = min(1.0, step / steps)
        eased = 1 - (1 - t) ** 3
        height = start + (target - start) * eased
        self.logpanel.box.configure(height=max(int(height), 40))
        if t >= 1.0:
            self._log_anim_job = None
            self._layout()
            self.circle.set_active(self._tab == "Главная" and self.winfo_viewable() and not self._log_expanded)
            return
        self._log_anim_job = self.after(14, lambda: self._anim_log(start, target, step + 1))

    def _on_tab_click(self, name):
        self._show_tab(name)

    def _show_tab(self, name, animate=True):
        if name == self._tab:
            return
        old = self._cur_frame
        new = self.frames[name]
        self._cancel_slide(keep=new)
        self._tab = name
        self._cur_frame = new
        self.tabs.set(name)
        self.circle.set_active(name == "Главная" and self.winfo_viewable() and not self._log_expanded)
        if not animate or old is None:
            if old is not None:
                old.place_forget()
            new.place(x=0, y=0, relwidth=1, relheight=1)
            new.lift()
            return
        height = max(self.container.winfo_height(), 1)
        new.place(x=0, y=-height, relwidth=1, relheight=1)
        new.lift()
        self._slide_step(new, old, -height, 0, 0)

    def _slide_step(self, new, old, start, end, step):
        """Страница выплывает сверху вниз: быстро в начале, мягко в конце."""
        steps = 16
        t = min(1.0, step / steps)
        eased = 1 - (1 - t) ** 3
        y = start + (end - start) * eased
        new.place_configure(y=y)
        if t >= 1.0:
            if old is not None:
                old.place_forget()
            new.place_configure(y=0)
            self._slide_job = None
            return
        self._slide_job = self.after(14, lambda: self._slide_step(new, old, start, end, step + 1))

    def _cancel_slide(self, keep):
        if self._slide_job is not None:
            self.after_cancel(self._slide_job)
            self._slide_job = None
        for frame in self.frames.values():
            if frame is not keep:
                frame.place_forget()
        if keep is not None:
            keep.place_configure(x=0, y=0)

    def _scroll(self):
        return ScrollArea(self.container, bg=BG)

    def _card(self, parent, **pack):
        frame = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=0)
        frame.pack(fill="x", **pack)
        return frame

    def _section(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=font(11, "bold"), text_color=MUTED).pack(
            anchor="w", padx=18, pady=(14, 4))

    def _label(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=font(11), text_color=MUTED, anchor="w",
                     justify="left", wraplength=WRAP).pack(anchor="w", padx=18, pady=(0, 6))

    def _build_main(self):
        f = ctk.CTkFrame(self.container, fg_color=BG, corner_radius=0)
        self.status_label = ctk.CTkLabel(f, text="", font=font(22, "bold"), text_color=TEXT)
        self.status_label.pack(pady=(2, 0))
        self.hint_label = ctk.CTkLabel(f, text="", font=font(12), text_color=SOFT)
        self.hint_label.pack(pady=(2, 0))
        self.summary_label = ctk.CTkLabel(f, text="", font=font(11), text_color=MUTED)
        self.summary_label.pack(pady=(2, 4))
        self.circle = PowerCircle(f, self.toggle)
        self.circle.pack(pady=(0, 4))

        self.progress = ctk.CTkProgressBar(f, mode="indeterminate", height=4, corner_radius=0,
                                           progress_color=WHITE, fg_color=CARD_HI, bg_color=BG)

        card = self._card(f, pady=(4, 10))
        ctk.CTkLabel(card, text="СТРАТЕГИЯ (strategy)", font=font(11, "bold"), text_color=MUTED).pack(
            anchor="w", padx=18, pady=(14, 6))
        self.strategy_menu = ctk.CTkOptionMenu(
            card, values=[s["name"] for s in self.strategy_list], command=self.on_strategy_change,
            width=360, height=44, font=font(14), dropdown_font=font(13), fg_color=CARD_HI,
            button_color=TRACK, button_hover_color="#52525b", text_color=TEXT,
            dropdown_fg_color=CARD, dropdown_hover_color=CARD_HI, dropdown_text_color=TEXT)
        self.strategy_menu.pack(fill="x", padx=18, pady=(0, 16))
        self.strategy_menu.set(self._name_by_id(self.cfg["strategy"]))

        btn_row = tk.Frame(f, bg=BG)
        btn_row.pack(fill="x")
        self.test_btn = ctk.CTkButton(btn_row, text="Проверить стратегию", width=176, height=44,
                                      command=self.test_current, **secondary_button())
        self.test_btn.pack(side="left", padx=(0, 4))
        self.best_btn = ctk.CTkButton(btn_row, text="Подобрать лучшую", width=176, height=44,
                                      command=self.test_all, **secondary_button())
        self.best_btn.pack(side="right", padx=(4, 0))

        self.banner = ctk.CTkFrame(f, fg_color=CARD, corner_radius=0)
        self.banner_label = ctk.CTkLabel(self.banner, text="", font=font(12), text_color=TEXT,
                                         justify="left", anchor="w")
        self.banner_label.pack(side="left", padx=16, pady=12, fill="x", expand=True)
        ctk.CTkButton(self.banner, text="Установить", width=110, height=32,
                      command=self._install_pending, **primary_button(CARD)).pack(side="right", padx=12)
        return f

    def _build_settings(self):
        area = self._scroll()
        f = area.inner

        card = self._card(f, pady=(0, 12))
        self._section(card, "ОБХОД (bypass)")
        self._label(card, "Игровой фильтр (Game Filter) ускоряет игровые серверы и голосовой чат.")
        self.game_menu = ctk.CTkOptionMenu(card, values=list(GAME_LABELS.values()),
                                           command=self.on_game_mode, width=346, height=40, **menu_style())
        self.game_menu.pack(fill="x", padx=18, pady=(0, 10))
        self.game_menu.set(GAME_LABELS[self.cfg["game_mode"]])
        row = ctk.CTkFrame(card, fg_color=CARD, corner_radius=0)
        row.pack(fill="x", padx=18, pady=(0, 10))
        self.tcp_entry = self._range_entry(row, "game_tcp", "TCP порты (GameFilterTCP)", "left")
        self.udp_entry = self._range_entry(row, "game_udp", "UDP порты (GameFilterUDP)", "right")
        self._label(card, "IPSet (ipset-all.txt) — IP-адреса, для которых работает обход. "
                          "Обычно оставьте «Полный список».")
        self.ipset_menu = ctk.CTkOptionMenu(card, values=list(IPSET_LABELS.values()),
                                            command=self.on_ipset_mode, width=346, height=40, **menu_style())
        self.ipset_menu.pack(fill="x", padx=18, pady=(0, 16))
        self.ipset_menu.set(IPSET_LABELS.get(self._ipset_mode, IPSET_LABELS["loaded"]))

        card = self._card(f, pady=(0, 12))
        self._section(card, "АВТОМАТИКА (automation)")
        for key, title, desc in SWITCHES:
            self._switch(card, key, title, desc)
        ctk.CTkFrame(card, height=8, fg_color=CARD).pack()

        card = self._card(f, pady=(0, 12))
        self._section(card, "ОБНОВЛЕНИЯ (updates)")
        self.list_info = ctk.CTkLabel(card, text="", font=font(12), text_color=SOFT, justify="left", anchor="w")
        self.list_info.pack(anchor="w", padx=18, pady=(0, 6))
        self.list_btn = ctk.CTkButton(card, text="Обновить списки (lists update)", height=40,
                                      command=lambda: self._check_lists(silent=False), **secondary_button(CARD))
        self.list_btn.pack(fill="x", padx=18, pady=(0, 14))
        self.app_info = ctk.CTkLabel(card, text="", font=font(12), text_color=SOFT, justify="left", anchor="w")
        self.app_info.pack(anchor="w", padx=18, pady=(0, 6))
        self.app_btn = ctk.CTkButton(card, text="Проверить программу (self-update)", height=40,
                                     command=lambda: self._check_app(manual=True), **secondary_button(CARD))
        self.app_btn.pack(fill="x", padx=18, pady=(0, 16))
        self._refresh_update_labels()

        card = self._card(f, pady=(0, 12))
        self._section(card, "ПАПКИ (folders)")
        self._label(card, "Списки доменов и IP можно править вручную. Свои домены добавляйте в файлы *-user.txt.")
        row = ctk.CTkFrame(card, fg_color=CARD, corner_radius=0)
        row.pack(fill="x", padx=18, pady=(0, 16))
        ctk.CTkButton(row, text="Папка списков (lists)", height=40, command=lambda: self._open_folder(paths.LISTS_DIR),
                      **secondary_button(CARD)).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(row, text="Папка данных (AppData)", height=40, command=lambda: self._open_folder(paths.DATA_DIR),
                      **secondary_button(CARD)).pack(side="right", fill="x", expand=True, padx=(4, 0))
        return area

    def _range_entry(self, parent, key, caption, side):
        box = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=0)
        box.pack(side=side, fill="x", expand=True, padx=(0 if side == "left" else 8, 0))
        ctk.CTkLabel(box, text=caption, font=font(11), text_color=MUTED).pack(anchor="w")
        entry = ctk.CTkEntry(box, width=160, height=38, **entry_style(CARD))
        entry.insert(0, self.cfg[key])
        entry.pack(fill="x")
        entry.bind("<Return>", lambda _e: self.on_range_commit(key, entry))
        entry.bind("<FocusOut>", lambda _e: self.on_range_commit(key, entry))
        return entry

    def _switch(self, parent, key, title, desc):
        self.switch_titles[key] = title
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", padx=18, pady=7)
        var = tk.BooleanVar(value=bool(self.cfg[key]))
        self.vars[key] = var
        sw = ToggleSwitch(row, var, command=lambda: self.on_switch(key), bg=CARD)
        sw.pack(side="left", anchor="n", pady=2)
        self.switches[key] = sw
        text = tk.Frame(row, bg=CARD)
        text.pack(side="left", fill="x", expand=True, padx=(12, 0))
        tk.Label(text, text=title, bg=CARD, fg=TEXT, font=(FONT, 12), anchor="w", justify="left").pack(anchor="w")
        tk.Label(text, text=desc, bg=CARD, fg=MUTED, font=(FONT, 10), anchor="w", justify="left",
                 wraplength=290).pack(anchor="w")

    def _build_service(self):
        area = self._scroll()
        f = area.inner

        card = self._card(f, pady=(0, 12))
        self._section(card, "СЛУЖБА WINDOWS (service)")
        self._label(card, "Служба (sc create zapret) запускает обход при загрузке системы, даже до входа "
                          "в учётную запись. Пока она установлена, круг на главной управляет ею.")
        ctk.CTkButton(card, text="Установить службу (Install Service)", height=44,
                      command=self.install_service_ui, **primary_button(CARD)).pack(fill="x", padx=18, pady=(4, 8))
        row = ctk.CTkFrame(card, fg_color=CARD, corner_radius=0)
        row.pack(fill="x", padx=18, pady=(0, 16))
        ctk.CTkButton(row, text="Удалить (Remove)", height=40, command=self.remove_service_ui,
                      **secondary_button(CARD)).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(row, text="Статус (Check Status)", height=40, command=self.status_ui,
                      **secondary_button(CARD)).pack(side="right", fill="x", expand=True, padx=(4, 0))

        card = self._card(f, pady=(0, 12))
        self._section(card, "ИНСТРУМЕНТЫ (tools)")
        ctk.CTkButton(card, text="Диагностика системы (Run Diagnostics)", height=42, command=self.diagnostics_ui,
                      **secondary_button(CARD)).pack(fill="x", padx=18, pady=(2, 8))
        ctk.CTkButton(card, text="Обновить список IPSet (Update IPSet List)", height=42, command=self.update_ipset_ui,
                      **secondary_button(CARD)).pack(fill="x", padx=18, pady=(0, 8))
        ctk.CTkButton(card, text="Обновить hosts (Update Hosts File)", height=42, command=self.update_hosts_ui,
                      **secondary_button(CARD)).pack(fill="x", padx=18, pady=(0, 16))

        card = self._card(f, pady=(0, 12))
        self._section(card, "ФЕЙКОВЫЕ ПАКЕТЫ (fake payload)")
        self._label(card, "Файл из папки bin (*.bin), который подменяет трафик. Меняйте, если стратегия "
                          "не работает (Replace active fakes).")
        options = fakes.list_fakes() or ["нет файлов"]
        ctk.CTkLabel(card, text="Для Discord (ACTIVE_DISCORD_UDP.bin)", font=font(11), text_color=MUTED,
                     anchor="w").pack(anchor="w", padx=18)
        self.fake_discord = ctk.CTkOptionMenu(card, values=options, width=346, height=40, **menu_style())
        self.fake_discord.pack(fill="x", padx=18, pady=(4, 10))
        ctk.CTkLabel(card, text="Для игр (ACTIVE_GAME_UDP.bin)", font=font(11), text_color=MUTED,
                     anchor="w").pack(anchor="w", padx=18)
        self.fake_game = ctk.CTkOptionMenu(card, values=options, width=346, height=40, **menu_style())
        self.fake_game.pack(fill="x", padx=18, pady=(4, 10))
        for kind, menu in (("discord", self.fake_discord), ("game", self.fake_game)):
            current = fakes.current(kind)
            if current and current in options:
                menu.set(current)
        ctk.CTkButton(card, text="Применить фейки (Apply)", height=42, command=self.apply_fakes,
                      **secondary_button(CARD)).pack(fill="x", padx=18, pady=(0, 16))
        return area

    # ---------- журнал ----------

    def log(self, msg: str, kind: str = "default"):
        line = f"[{dt.datetime.now():%H:%M:%S}] {msg}\n"
        self._lines.append(line)
        self.logpanel.append(line, kind)
        try:
            paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(paths.APP_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            pass

    def clear_log(self):
        self._lines.clear()
        self.logpanel.set_text("")

    def _percent_kind(self, score: int, total: int) -> str:
        share = score / total if total else 0
        if share >= 0.7:
            return "ok"
        if share >= 0.4:
            return "warn"
        return "err"

    # ---------- служебные функции ----------

    def _name_by_id(self, sid):
        for s in self.strategy_list:
            if s["id"] == sid:
                return s["name"]
        return self.strategy_list[0]["name"]

    def _id_by_name(self, name):
        for s in self.strategy_list:
            if s["name"] == name:
                return s["id"]
        return self.strategy_list[0]["id"]

    def _update_summary(self):
        name = self._name_by_id(self.cfg["strategy"])
        game = GAME_SHORT.get(self.cfg["game_mode"], "")
        ipset = IPSET_SHORT.get(self._ipset_mode, "")
        self.summary_label.configure(text=f"{name}   ·   игры: {game}   ·   IPSet: {ipset}")

    def _refresh_update_labels(self):
        last_list = self.cfg["last_check"] or "никогда"
        self.list_info.configure(text=f"Версия списков: {self.cfg['lists_version'] or '—'}\n"
                                      f"Последняя проверка: {last_list}")
        latest = self._latest or "не проверялась"
        self.app_info.configure(text=f"Установлена: {__version__}\nПоследний релиз на GitHub: {latest}")

    def _open_folder(self, path):
        try:
            path.mkdir(parents=True, exist_ok=True)
            os.startfile(str(path))
        except (AttributeError, OSError) as exc:
            self.log(f"Не удалось открыть папку {path}: {exc}", "err")

    def _post(self, fn):
        self._queue.put((lambda *_: fn(), None, None))

    def _bg(self, fn, done):
        def worker():
            try:
                result, error = fn(), None
            except Exception as exc:  # noqa: BLE001
                result, error = None, exc
            self._queue.put((done, result, error))
        threading.Thread(target=worker, daemon=True).start()

    def _set_busy(self, flag: bool):
        self._busy = flag
        if flag:
            self.progress.pack(fill="x", padx=40, pady=(0, 10), before=self.test_btn)
            self.progress.start()
        else:
            self.progress.stop()
            self.progress.pack_forget()

    def _job(self, note, fn, on_done=None):
        if self._busy:
            self.log("Подождите: предыдущее действие ещё выполняется", "warn")
            return
        self._set_busy(True)
        self.log(note)

        def done(result, error):
            self._set_busy(False)
            if error:
                self.log(f"Ошибка: {error}", "err")
            elif on_done:
                on_done(result)
            self._refresh_status()

        self._bg(fn, done)

    def _pump(self):
        while True:
            try:
                done, result, error = self._queue.get_nowait()
            except queue.Empty:
                break
            done(result, error)
        self.after(100, self._pump)

    def _poll(self):
        if not self._busy:
            self._refresh_status()
        self.after(5000, self._poll)

    # ---------- круг и статус ----------

    def _set_visual(self, state: str):
        self.circle.set_state(state)
        self.status_label.configure(text=STATE_TEXT[state])
        self.hint_label.configure(text=STATE_HINT[state])

    def _refresh_status(self):
        self._bg(lambda: {"running": engine.is_running(), "service": engine.service_installed()},
                 self._on_probe)

    def _on_probe(self, data, error):
        if error or data is None:
            return
        self._service = data["service"]
        self._set_running(data["running"])

    def _set_running(self, running: bool):
        self._running = running
        if not self._busy:
            self._set_visual("on" if running else "off")

    def _game_args(self):
        return (self.cfg["game_mode"], self.cfg["game_tcp"], self.cfg["game_udp"])

    def _start_engine(self):
        return engine.start(self.cfg["strategy"], *self._game_args())

    def _start_if_idle(self, note):
        if not self._busy and not self._running:
            self._start_action(note)

    def _start_action(self, note: str):
        self._set_busy(True)
        self.log(note)
        self._set_visual("starting")
        self._bg(self._start_engine, self._after_start)

    def _after_start(self, running, error):
        self._set_busy(False)
        if error:
            self.log(f"Ошибка запуска: {error}", "err")
        elif running:
            self.log("Обход включён", "ok")
        else:
            self.log("Обход не запустился: проверьте права администратора и файл winws.log", "err")
        self._running = bool(running) and error is None
        self._set_visual("on" if self._running else "off")
        self._refresh_status()

    def toggle(self):
        if self._busy:
            return
        if self._running:
            self._set_busy(True)
            self.log("Выключаю обход…")
            self._set_visual("stopping")
            self._bg(engine.stop, lambda _r, err: self._finish_stop(err))
        else:
            self._start_action("Запускаю обход…")

    def _finish_stop(self, error):
        self._set_busy(False)
        if error:
            self.log(f"Ошибка остановки: {error}", "err")
        else:
            self.log("Обход выключен")
        self._running = False
        self._set_visual("off")
        self._refresh_status()

    def _settings_changed(self, note):
        if self._busy:
            return
        if self._running:
            self._start_action(note)
        elif self._service:
            self._job("Обновляю параметры службы…",
                      lambda: engine.sync_service(self.cfg["strategy"], *self._game_args()))

    # ---------- настройки обхода ----------

    def on_strategy_change(self, name):
        self.cfg["strategy"] = self._id_by_name(name)
        settings.save(self.cfg)
        self.log(f"Выбрана стратегия: {name}")
        self._update_summary()
        self._settings_changed("Перезапускаю обход с новой стратегией…")

    def on_game_mode(self, label):
        mode = next(k for k, v in GAME_LABELS.items() if v == label)
        if mode == self.cfg["game_mode"]:
            return
        self.cfg["game_mode"] = mode
        settings.save(self.cfg)
        self.log(f"Игровой фильтр: {label}")
        self._update_summary()
        self._settings_changed("Перезапускаю обход с учётом игрового фильтра…")

    def on_range_commit(self, key, entry):
        text = entry.get().strip()
        if text == self.cfg[key]:
            return
        if not strategies.valid_range(text):
            self.log(f"Неверный диапазон портов «{text}». Нужен вид 1024-65535", "err")
            entry.delete(0, "end")
            entry.insert(0, self.cfg[key])
            return
        self.cfg[key] = text
        settings.save(self.cfg)
        self.log(f"Порты обновлены: {text}")
        self._settings_changed("Перезапускаю обход с новыми портами…")

    def on_ipset_mode(self, label):
        mode = next(k for k, v in IPSET_LABELS.items() if v == label)
        if mode == updater.ipset_mode():
            return

        def after(_result):
            self._ipset_mode = mode
            self._update_summary()
            self.log(f"IPSet: {label}")
            self._settings_changed("Перезапускаю обход с новым режимом IPSet…")

        self._job("Меняю режим IPSet…", lambda: updater.set_ipset_mode(mode), on_done=after)

    def on_switch(self, key):
        value = bool(self.vars[key].get())
        if key == "autostart":
            try:
                system.set_autostart(value)
            except Exception as exc:  # noqa: BLE001
                self.log(f"Автозапуск: {exc}", "err")
                self.switches[key].set(not value)
                return
        self.cfg[key] = value
        settings.save(self.cfg)
        self.log(f"{self.switch_titles[key]}: {'вкл' if value else 'выкл'}", "update")

    # ---------- сервис и инструменты ----------

    def install_service_ui(self):
        def done(running):
            if running:
                self.log("Служба установлена и запущена. Обход стартует сам при загрузке Windows.", "ok")
            else:
                self.log("Служба установлена, но не запустилась. Смотрите winws.log", "err")
            self._service = True

        self._job("Устанавливаю службу Windows…",
                  lambda: engine.install_service(self.cfg["strategy"], *self._game_args()), on_done=done)

    def remove_service_ui(self):
        def done(_result):
            self.log("Службы zapret и WinDivert удалены", "ok")
            self._service = False

        self._job("Удаляю службы…", engine.remove_service, on_done=done)

    def status_ui(self):
        self._job("Проверяю состояние…", diagnostics.service_report,
                  on_done=lambda lines: [self.log(line) for line in lines])

    def diagnostics_ui(self):
        self._job("Запускаю диагностику системы…", diagnostics.run_checks, on_done=self._show_checks)

    def _show_checks(self, checks):
        for check in checks:
            self.log(f"{CHECK_PREFIX.get(check.level, '')} {check.text}", CHECK_KIND.get(check.level, "default"))
        self.log("Диагностика завершена", "update")

    def update_ipset_ui(self):
        def done(changed):
            if changed:
                self.log("Список IPSet обновлён", "update")
                if self._running:
                    self._start_action("Перезапускаю обход с новым списком IPSet…")
            else:
                self.log("Список IPSet уже актуален", "update")

        self._job("Обновляю список IPSet…", updater.update_ipset, on_done=done)

    def update_hosts_ui(self):
        def done(added):
            self.log(f"hosts обновлён: добавлено записей {added}" if added else "hosts уже актуален",
                     "ok" if added else "default")

        self._job("Обновляю файл hosts…", hosts.update_hosts, on_done=done)

    def apply_fakes(self):
        discord_name = self.fake_discord.get()
        game_name = self.fake_game.get()
        if "нет файлов" in (discord_name, game_name):
            self.log("В папке bin нет файлов фейков", "warn")
            return

        def job():
            was_running = engine.is_running()
            if was_running:
                engine.stop()
            fakes.apply("discord", discord_name)
            fakes.apply("game", game_name)
            if was_running:
                engine.start(self.cfg["strategy"], *self._game_args())
            return was_running

        self._job("Применяю фейковые пакеты…", job,
                  on_done=lambda was: self.log("Фейки применены" + (", обход перезапущен" if was else ""), "ok"))

    # ---------- проверка стратегий и автоматика ----------

    def _set_test_buttons(self):
        if self._test_running:
            self.test_btn.configure(text="Остановить проверку", state="normal")
            self.best_btn.configure(state="disabled")
        else:
            self.test_btn.configure(text="Проверить стратегию", state="normal")
            self.best_btn.configure(state="normal")

    def test_current(self):
        self._run_test(all_mode=False)

    def test_all(self):
        self._run_test(all_mode=True)

    def _run_test(self, all_mode: bool, then_start: bool = False):
        if self._test_running:
            self._cancel.set()
            self.hint_label.configure(text="Останавливаю проверку…")
            return
        if self._busy:
            return
        self._test_running = True
        self._then_start = then_start
        self._set_busy(True)
        self._cancel.clear()
        self._set_test_buttons()
        was_running = self._running
        selected = self.cfg["strategy"]
        ids = [s["id"] for s in self.strategy_list] if all_mode else [selected]
        if all_mode:
            self.log("Проверяю все стратегии. Это займёт несколько минут.", "update")
        else:
            self.log(f"Проверяю стратегию «{self._name_by_id(selected)}»", "update")
        self.circle.set_state("starting")
        self.status_label.configure(text="Проверка")
        game = self._game_args()

        def progress(msg):
            self._post(lambda: self._on_test_progress(msg))

        def job():
            return tester.run(ids, game, was_running, selected, all_mode, progress, self._cancel)

        self._bg(job, lambda report, err: self._after_test(report, err, all_mode))

    def _on_test_progress(self, msg):
        self.hint_label.configure(text=msg)
        self.log(msg)

    def _after_test(self, report, error, all_mode):
        self._test_running = False
        self._set_busy(False)
        self._set_test_buttons()
        start_after = self._then_start
        self._then_start = False
        if error:
            self.log(f"Ошибка проверки: {error}", "err")
        elif report is not None:
            for r in report.results:
                self.log(f"{r.name}: доступно {r.score} из {r.total}",
                         self._percent_kind(r.score, r.total))
            if report.cancelled:
                self.log("Проверка остановлена", "warn")
            elif all_mode and report.best:
                self.cfg["strategy"] = report.best.id
                self.cfg["first_run"] = False
                settings.save(self.cfg)
                self.strategy_menu.set(report.best.name)
                self._update_summary()
                self.log(f"Лучшая стратегия: «{report.best.name}» ({report.best.score} из "
                         f"{report.best.total}). Выбрана автоматически.",
                         self._percent_kind(report.best.score, report.best.total))
        self._refresh_status()
        if start_after and report is not None and not report.cancelled and report.best:
            self._start_action("Запускаю обход с выбранной стратегией…")

    def _probe_bypass(self):
        """None — интернета нет; True — обход не работает; False — всё в порядке."""
        if not tester.check_url(NEUTRAL_URL):
            return None
        urls = [url for key, url in tester.load_targets()
                if key.lower().startswith(("discord", "youtube"))][:3]
        if not urls:
            return None
        return not any(tester.check_url(url) for url in urls)

    def _watchdog(self):
        if self.cfg["auto_fix"] and self._running and not self._busy and not self._test_running:
            self._bg(self._probe_bypass, self._on_watchdog)
        self.after(WATCHDOG_MS, self._watchdog)

    def _on_watchdog(self, broken, error):
        if error or broken is not True or self._busy:
            return
        self.log("Discord и YouTube не открываются. Автоматически подбираю стратегию заново…", "warn")
        self._run_test(all_mode=True)

    # ---------- обновления списков и программы (раздельно) ----------

    def _check_lists(self, silent=False):
        if self._busy_update:
            return
        self._busy_update = True
        self.list_btn.configure(state="disabled")
        if not silent:
            self.log("Проверяю обновления списков…", "update")
        self._bg(updater.update_lists, lambda res, err: self._after_lists(res, err, silent))

    def _after_lists(self, result, error, silent):
        self._busy_update = False
        self.list_btn.configure(state="normal")
        if error:
            self.log(f"Не удалось обновить списки: {error}", "err")
            return
        now = time.time()
        self.cfg["lists_version"] = result.version
        self.cfg["last_check"] = dt.datetime.now().strftime("%d.%m.%Y %H:%M")
        self.cfg["last_list_ts"] = now
        settings.save(self.cfg)
        self._refresh_update_labels()
        if result.changed:
            self.log(f"Списки обновлены: файлов {len(result.changed)}, версия {result.version}", "update")
            if self._running and not self._busy:
                self._start_action("Перезапускаю обход с новыми списками…")
        elif not silent:
            self.log(f"Списки уже актуальны, версия {result.version}", "update")

    def _check_app(self, manual: bool):
        if self._busy_app:
            return
        self._busy_app = True
        self.app_btn.configure(state="disabled")
        if manual:
            self.log("Проверяю новую версию программы на GitHub…", "update")
        self._bg(app_updater.check_latest, lambda res, err: self._after_app_check(res, err, manual))

    def _after_app_check(self, res, error, manual):
        self._busy_app = False
        self.app_btn.configure(state="normal")
        if error:
            self.log(f"Не удалось проверить программу: {error}", "err")
            return
        self.cfg["last_app_ts"] = time.time()
        settings.save(self.cfg)
        self._latest = res.tag.lstrip("v") if res.tag else None
        self._refresh_update_labels()
        if res.info is None:
            if manual or res.tag:
                self.log(res.note, "warn")
            return
        local = __version__
        dev_note = " (dev-сборка, не релиз)" if app_updater.parse_version(local) is None else ""
        if not app_updater.is_newer(res.info.version, local):
            if manual:
                self.log(f"Установлена {local}{dev_note}, последний релиз {res.tag}: "
                         "обновление не нужно", "update")
            return
        self._pending_update = res.info
        self.log(f"Доступна версия {res.info.version} (установлена {local}{dev_note})", "update")
        if self.cfg["auto_update_app"]:
            self._install_update(res.info)
        else:
            self.banner_label.configure(text=f"Доступна версия {res.info.version}. Установить?")
            self.banner.pack(fill="x", pady=(10, 0))

    def _install_pending(self):
        if self._pending_update:
            self._install_update(self._pending_update)

    def _install_update(self, info):
        if self._busy:
            self.log("Сейчас выполняется другое действие, обновление отложено", "warn")
            return
        self.banner.pack_forget()
        self._set_busy(True)
        self.cfg["resume_bypass"] = self._running
        settings.save(self.cfg)
        self.log(f"Скачиваю zapret-app {info.version}…", "update")
        self._bg(lambda: app_updater.download(info), self._on_downloaded)

    def _on_downloaded(self, path, error):
        if error:
            self._set_busy(False)
            self.cfg["resume_bypass"] = False
            settings.save(self.cfg)
            self.log(f"Не удалось скачать обновление: {error}", "err")
            return
        try:
            app_updater.launch_installer(path)
        except Exception as exc:  # noqa: BLE001
            self._set_busy(False)
            self.log(f"Не удалось запустить установщик: {exc}", "err")
            return
        self.log("Устанавливаю обновление. Программа закроется и откроется новая версия.", "update")
        self.after(800, self._quit)
