"""Главное окно zapret-app: монохромный интерфейс фиксированного размера."""
import datetime as dt
import os
import queue
import sys
import threading
import tkinter as tk

import customtkinter as ctk

from . import __version__, app_updater, diagnostics, engine, fakes, hosts, paths, settings, strategies
from . import system, tester, updater
from .logpanel import LogPanel, small_button
from .power_circle import PowerCircle
from .theme import BG, BORDER, CARD, CARD_HI, FONT, MUTED, SOFT, TEXT, TRACK, WHITE, BLACK

try:
    from .tray import Tray
except Exception:  # noqa: BLE001  pystray недоступен — работаем без трея
    Tray = None

WIDTH, HEIGHT = 440, 760
WATCHDOG_MS = 10 * 60 * 1000
NEUTRAL_URL = "https://www.gstatic.com/generate_204"

STATE_TEXT = {"off": "Выключено", "starting": "Запуск…", "on": "Работает", "stopping": "Остановка…"}
STATE_HINT = {
    "off": "Нажмите на круг, чтобы включить обход",
    "starting": "Подождите, обход запускается",
    "on": "Обход работает. Нажмите на круг, чтобы выключить",
    "stopping": "Останавливаю обход",
}
GAME_LABELS = {"off": "Выключен (off)", "all": "TCP и UDP (all)", "tcp": "Только TCP (tcp)", "udp": "Только UDP (udp)"}
GAME_SHORT = {"off": "выкл", "all": "TCP+UDP", "tcp": "TCP", "udp": "UDP"}
IPSET_LABELS = {"loaded": "Полный список (loaded)", "none": "Выключен (none)", "any": "Любые IP (any)"}
IPSET_SHORT = {"loaded": "полный", "none": "выкл", "any": "любые"}
CHECK_PREFIX = {"ok": "[ОК]", "warn": "[!]", "error": "[X]", "info": "[i]"}
SWITCHES = [
    ("start_bypass", "Включать обход при открытии (start on launch)",
     "Обход запускается сам, когда вы открываете программу"),
    ("auto_fix", "Чинить сам (auto-fix)",
     "Если Discord и YouTube перестали открываться, программа заново подберёт стратегию"),
    ("auto_update", "Обновлять списки (lists update)",
     "Домены и IP берутся из официального репозитория"),
    ("auto_update_app", "Обновлять программу (self-update)",
     "Новые версии с GitHub ставятся сами"),
    ("autostart", "Запускать с Windows (autostart)",
     "Программа стартует в трее и включает обход"),
    ("close_to_tray", "Сворачивать в трей (tray)",
     "Крестик скрывает окно, обход продолжает работать"),
]


def font(size, weight="normal"):
    return ctk.CTkFont(family=FONT, size=size, weight=weight)


def primary_button():
    return dict(fg_color=WHITE, hover_color="#e4e4e7", text_color=BLACK, font=font(13, "bold"), corner_radius=14)


def secondary_button():
    return dict(fg_color=CARD_HI, hover_color=TRACK, text_color=TEXT, font=font(13), corner_radius=14)


def switch_style():
    return dict(fg_color=TRACK, progress_color=SOFT, button_color=WHITE,
                button_hover_color="#e4e4e7", text_color=TEXT, font=font(13))


def menu_style():
    return dict(fg_color=CARD_HI, button_color=TRACK, button_hover_color="#52525b", text_color=TEXT,
                dropdown_fg_color=CARD, dropdown_hover_color=CARD_HI, dropdown_text_color=TEXT,
                font=font(13), dropdown_font=font(13), corner_radius=12)


def entry_style():
    return dict(fg_color=CARD_HI, border_width=0, text_color=TEXT, font=font(13), corner_radius=12)


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
        self._cancel = threading.Event()
        self._queue = queue.Queue()
        self._pending_update = None
        self._lines = []
        self._tab = "Главная"
        self._ipset_mode = updater.ipset_mode()
        self._full_top = None
        self._full_box = None
        self.vars = {}
        self.switch_titles = {}
        self.tray = None

        self._build()
        self.after(100, self._pump)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._start_tray()

        self.log(f"Приложение запущено, версия {__version__}")
        if not system.is_admin():
            self.log("Нет прав администратора: обход не запустится. Запустите программу от имени администратора.")

        self._set_visual("off")
        self._refresh_status()
        if self.cfg["auto_update"]:
            self.after(1000, lambda: self._check_lists(silent=True))
        if self.cfg["auto_update_app"]:
            self.after(2000, lambda: self._check_app(manual=False))
        self.after(2500, self._startup_actions)
        self.after(WATCHDOG_MS, self._watchdog)
        self.after(5000, self._poll)

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
            self.log(f"Значок в трее недоступен: {exc}")

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
        if self._full_top is not None:
            self._close_full_log()
        self.destroy()

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

    # ---------- построение интерфейса ----------

    def _build(self):
        self.tabs = ctk.CTkSegmentedButton(
            self, values=["Главная", "Настройки", "Сервис"], command=self._show_tab, height=38,
            corner_radius=14, font=font(13), fg_color=CARD, selected_color=TRACK,
            selected_hover_color="#52525b", unselected_color=CARD, unselected_hover_color=CARD_HI,
            text_color=TEXT, border_width=0)
        self.tabs.pack(fill="x", padx=20, pady=(16, 10))

        self.logpanel = LogPanel(self, on_expand=self.open_full_log, on_clear=self.clear_log)
        self.logpanel.pack(side="bottom", fill="x", padx=20, pady=(0, 16))

        self.container = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.container.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        self.frames = {
            "Главная": self._build_main(),
            "Настройки": self._build_settings(),
            "Сервис": self._build_service(),
        }
        self.tabs.set("Главная")
        self._show_tab("Главная")
        self.bind("<Unmap>", self._on_unmap)
        self.bind("<Map>", self._on_map)
        self._update_summary()

    def _show_tab(self, name):
        self._tab = name
        for frame in self.frames.values():
            frame.pack_forget()
        self.frames[name].pack(fill="both", expand=True)
        self.circle.set_active(name == "Главная" and self.winfo_viewable())

    def _on_unmap(self, event):
        if event.widget is self:
            self.circle.set_active(False)

    def _on_map(self, event):
        if event.widget is self:
            self.circle.set_active(self._tab == "Главная")

    def _update_summary(self):
        name = self._name_by_id(self.cfg["strategy"])
        game = GAME_SHORT.get(self.cfg["game_mode"], "")
        ipset = IPSET_SHORT.get(self._ipset_mode, "")
        self.summary_label.configure(text=f"{name}   ·   игры: {game}   ·   IPSet: {ipset}")

    def _scroll(self):
        return ctk.CTkScrollableFrame(self.container, fg_color=BG, corner_radius=0,
                                      scrollbar_button_color=TRACK, scrollbar_button_hover_color="#52525b")

    def _card(self, parent, **pack):
        frame = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=18)
        frame.pack(fill="x", **pack)
        return frame

    def _section(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=font(11, "bold"), text_color=MUTED).pack(
            anchor="w", padx=18, pady=(14, 4))

    def _label(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=font(11), text_color=MUTED, anchor="w",
                     justify="left", wraplength=372).pack(anchor="w", padx=18, pady=(0, 6))

    def _build_main(self):
        f = ctk.CTkFrame(self.container, fg_color=BG, corner_radius=0)
        self.status_label = ctk.CTkLabel(f, text="", font=font(22, "bold"), text_color=TEXT)
        self.status_label.pack(pady=(4, 0))
        self.hint_label = ctk.CTkLabel(f, text="", font=font(12), text_color=SOFT)
        self.hint_label.pack(pady=(2, 0))
        self.summary_label = ctk.CTkLabel(f, text="", font=font(11), text_color=SOFT)
        self.summary_label.pack(pady=(2, 6))
        self.circle = PowerCircle(f, self.toggle)
        self.circle.pack(pady=(10, 10))

        self.progress = ctk.CTkProgressBar(f, mode="indeterminate", height=4, corner_radius=2,
                                           progress_color=WHITE, fg_color=CARD_HI)

        card = self._card(f, pady=(0, 10))
        ctk.CTkLabel(card, text="СТРАТЕГИЯ (strategy)", font=font(11, "bold"), text_color=MUTED).pack(
            anchor="w", padx=18, pady=(14, 6))
        self.strategy_menu = ctk.CTkOptionMenu(
            card, values=[s["name"] for s in self.strategy_list], command=self.on_strategy_change,
            height=40, **menu_style())
        self.strategy_menu.pack(fill="x", padx=18, pady=(0, 16))
        self.strategy_menu.set(self._name_by_id(self.cfg["strategy"]))

        self.test_btn = ctk.CTkButton(f, text="Проверить стратегию (test)", height=42,
                                      command=self.test_current, **secondary_button())
        self.test_btn.pack(fill="x", pady=(0, 8))
        self.best_btn = ctk.CTkButton(f, text="Подобрать лучшую (test all)", height=42,
                                      command=self.test_all, **secondary_button())
        self.best_btn.pack(fill="x")

        self.banner = ctk.CTkFrame(f, fg_color=CARD, corner_radius=16)
        self.banner_label = ctk.CTkLabel(self.banner, text="", font=font(12), text_color=TEXT,
                                         justify="left", anchor="w")
        self.banner_label.pack(side="left", padx=16, pady=12, fill="x", expand=True)
        ctk.CTkButton(self.banner, text="Установить", width=110, height=32,
                      command=self._install_pending, **primary_button()).pack(side="right", padx=12)
        return f

    def _build_settings(self):
        f = self._scroll()

        card = self._card(f, pady=(0, 12))
        self._section(card, "ОБХОД")
        self._label(card, "Игровой фильтр (Game Filter) ускоряет игровые серверы и голосовой чат. "
                          "Порты задают GameFilterTCP и GameFilterUDP.")
        self.game_menu = ctk.CTkOptionMenu(card, values=list(GAME_LABELS.values()),
                                           command=self.on_game_mode, height=40, **menu_style())
        self.game_menu.pack(fill="x", padx=18, pady=(0, 10))
        self.game_menu.set(GAME_LABELS[self.cfg["game_mode"]])
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(0, 10))
        self.tcp_entry = self._range_entry(row, "game_tcp", "TCP порты (GameFilterTCP)", "left")
        self.udp_entry = self._range_entry(row, "game_udp", "UDP порты (GameFilterUDP)", "right")
        self._label(card, "IPSet (ipset-all.txt) — IP-адреса, для которых работает обход. "
                          "Обычно оставьте «Полный список».")
        self.ipset_menu = ctk.CTkOptionMenu(card, values=list(IPSET_LABELS.values()),
                                            command=self.on_ipset_mode, height=40, **menu_style())
        self.ipset_menu.pack(fill="x", padx=18, pady=(0, 16))
        self.ipset_menu.set(IPSET_LABELS.get(updater.ipset_mode(), IPSET_LABELS["loaded"]))

        card = self._card(f, pady=(0, 12))
        self._section(card, "АВТОМАТИКА (automation)")
        for key, title, desc in SWITCHES:
            self._switch(card, key, title, desc)
        ctk.CTkFrame(card, height=8, fg_color="transparent").pack()

        card = self._card(f, pady=(0, 12))
        self._section(card, "О ПРОГРАММЕ")
        self.info_label = ctk.CTkLabel(card, text=self._info_text(), font=font(12), text_color=SOFT,
                                       justify="left", anchor="w")
        self.info_label.pack(anchor="w", padx=18, pady=(0, 10))
        self.check_btn = ctk.CTkButton(card, text="Проверить обновления (Check for Updates)", height=40,
                                       command=self.check_updates_manual, **secondary_button())
        self.check_btn.pack(fill="x", padx=18, pady=(0, 8))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(0, 16))
        ctk.CTkButton(row, text="Папка списков (lists)", height=38, command=lambda: self._open_folder(paths.LISTS_DIR),
                      **secondary_button()).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(row, text="Папка данных (AppData)", height=38, command=lambda: self._open_folder(paths.DATA_DIR),
                      **secondary_button()).pack(side="right", fill="x", expand=True, padx=(4, 0))
        return f

    def _range_entry(self, parent, key, caption, side):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.pack(side=side, fill="x", expand=True, padx=(0 if side == "left" else 8, 0))
        ctk.CTkLabel(box, text=caption, font=font(11), text_color=MUTED).pack(anchor="w")
        entry = ctk.CTkEntry(box, height=36, **entry_style())
        entry.insert(0, self.cfg[key])
        entry.pack(fill="x")
        entry.bind("<Return>", lambda _e: self.on_range_commit(key, entry))
        entry.bind("<FocusOut>", lambda _e: self.on_range_commit(key, entry))
        return entry

    def _switch(self, parent, key, title, desc):
        self.switch_titles[key] = title
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(6, 6))
        var = tk.BooleanVar(value=bool(self.cfg[key]))
        self.vars[key] = var
        ctk.CTkSwitch(row, text=title, variable=var, command=lambda: self.on_switch(key),
                      **switch_style()).pack(anchor="w")
        ctk.CTkLabel(row, text=desc, font=font(11), text_color=MUTED, anchor="w",
                     justify="left", wraplength=340).pack(anchor="w", padx=(50, 0))

    def _build_service(self):
        f = self._scroll()

        card = self._card(f, pady=(0, 12))
        self._section(card, "СЛУЖБА WINDOWS (service)")
        self._label(card, "Служба (sc create zapret) запускает обход при загрузке системы, даже до входа в учётную запись. "
                          "Пока она установлена, круг на главной управляет ею.")
        ctk.CTkButton(card, text="Установить службу (Install Service)", height=42, command=self.install_service_ui,
                      **primary_button()).pack(fill="x", padx=18, pady=(4, 8))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(0, 16))
        ctk.CTkButton(row, text="Удалить службы (Remove)", height=38, command=self.remove_service_ui,
                      **secondary_button()).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(row, text="Статус (Check Status)", height=38, command=self.status_ui,
                      **secondary_button()).pack(side="right", fill="x", expand=True, padx=(4, 0))

        card = self._card(f, pady=(0, 12))
        self._section(card, "ИНСТРУМЕНТЫ")
        ctk.CTkButton(card, text="Диагностика системы (Run Diagnostics)", height=40, command=self.diagnostics_ui,
                      **secondary_button()).pack(fill="x", padx=18, pady=(2, 8))
        ctk.CTkButton(card, text="Обновить список IPSet (Update IPSet List)", height=40, command=self.update_ipset_ui,
                      **secondary_button()).pack(fill="x", padx=18, pady=(0, 8))
        ctk.CTkButton(card, text="Обновить hosts (Update Hosts File)", height=40,
                      command=self.update_hosts_ui, **secondary_button()).pack(fill="x", padx=18, pady=(0, 16))

        card = self._card(f, pady=(0, 12))
        self._section(card, "ФЕЙКОВЫЕ ПАКЕТЫ (fake payload)")
        self._label(card, "Файл из папки bin (*.bin), который подменяет трафик. Меняйте, если стратегия не работает. "
                          "Replace active fakes.")
        options = fakes.list_fakes() or ["нет файлов"]
        ctk.CTkLabel(card, text="Для Discord (ACTIVE_DISCORD_UDP.bin)", font=font(11), text_color=MUTED, anchor="w").pack(
            anchor="w", padx=18)
        self.fake_discord = ctk.CTkOptionMenu(card, values=options, height=38, **menu_style())
        self.fake_discord.pack(fill="x", padx=18, pady=(4, 10))
        ctk.CTkLabel(card, text="Для игр (ACTIVE_GAME_UDP.bin)", font=font(11), text_color=MUTED, anchor="w").pack(anchor="w", padx=18)
        self.fake_game = ctk.CTkOptionMenu(card, values=options, height=38, **menu_style())
        self.fake_game.pack(fill="x", padx=18, pady=(4, 10))
        for kind, menu in (("discord", self.fake_discord), ("game", self.fake_game)):
            current = fakes.current(kind)
            if current and current in options:
                menu.set(current)
        ctk.CTkButton(card, text="Применить фейки (Apply)", height=40, command=self.apply_fakes,
                      **secondary_button()).pack(fill="x", padx=18, pady=(0, 16))
        return f

    # ---------- журнал ----------

    def log(self, msg: str):
        line = f"[{dt.datetime.now():%H:%M:%S}] {msg}\n"
        self._lines.append(line)
        self.logpanel.append(line)
        if self._full_box is not None:
            self._append_full(line)
        try:
            paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(paths.APP_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            pass

    def _append_full(self, line):
        self._full_box.configure(state="normal")
        self._full_box.insert("end", line)
        self._full_box.see("end")
        self._full_box.configure(state="disabled")

    def clear_log(self):
        self._lines.clear()
        self.logpanel.set_text("")
        if self._full_box is not None:
            self._full_box.configure(state="normal")
            self._full_box.delete("1.0", "end")
            self._full_box.configure(state="disabled")

    def open_full_log(self):
        if self._full_top is not None:
            self._full_top.lift()
            return
        top = ctk.CTkToplevel(self)
        top.title("Журнал zapret-app")
        top.geometry("600x560")
        top.configure(fg_color=BG)
        top.after(250, lambda: self._set_icon(top))
        bar = ctk.CTkFrame(top, fg_color="transparent")
        bar.pack(fill="x", padx=16, pady=(14, 8))
        ctk.CTkLabel(bar, text="Журнал", font=font(15, "bold"), text_color=TEXT).pack(side="left")
        ctk.CTkButton(bar, text="Очистить", width=100, height=32, command=self.clear_log,
                      **secondary_button()).pack(side="right")
        box = ctk.CTkTextbox(top, font=ctk.CTkFont(family="Consolas", size=12), fg_color=CARD,
                             text_color=SOFT, corner_radius=16, state="disabled")
        box.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        box.configure(state="normal")
        box.insert("end", "".join(self._lines))
        box.see("end")
        box.configure(state="disabled")
        self._full_top, self._full_box = top, box
        top.protocol("WM_DELETE_WINDOW", self._close_full_log)

    def _close_full_log(self):
        if self._full_top is not None:
            self._full_top.destroy()
        self._full_top = None
        self._full_box = None

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

    def _info_text(self):
        return (f"Установлена версия: {__version__}\n"
                f"Последний релиз на GitHub: {self._latest or 'проверяю…'}\n"
                f"Версия списков: {self.cfg['lists_version'] or '—'}\n"
                f"Последняя проверка: {self.cfg['last_check'] or '—'}")

    def _open_folder(self, path):
        try:
            path.mkdir(parents=True, exist_ok=True)
            os.startfile(str(path))
        except (AttributeError, OSError) as exc:
            self.log(f"Не удалось открыть папку {path}: {exc}")

    def _post(self, fn):
        """Ставит действие в очередь главного потока (безопасно из фоновых потоков)."""
        self._queue.put((lambda *_: fn(), None, None))

    def _bg(self, fn, done):
        """Выполняет fn в фоне; done(result, error) вызывается в главном потоке."""
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
        """Действие в фоне с блокировкой остальных. on_done(result) — в главном потоке."""
        if self._busy:
            self.log("Подождите: предыдущее действие ещё выполняется")
            return
        self._set_busy(True)
        self.log(note)

        def done(result, error):
            self._set_busy(False)
            if error:
                self.log(f"Ошибка: {error}")
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
            self.log(f"Ошибка запуска: {error}")
        elif running:
            self.log("Обход включён")
        else:
            self.log("Обход не запустился: проверьте права администратора и файл winws.log")
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
        self.log(f"Ошибка остановки: {error}" if error else "Обход выключен")
        self._running = False
        self._set_visual("off")
        self._refresh_status()

    def _settings_changed(self, note):
        """После смены настроек обхода: перезапуск, если работает; иначе обновить службу."""
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
            self.log(f"Неверный диапазон портов «{text}». Нужен вид 1024-65535")
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
                self.log(f"Автозапуск: {exc}")
                self.vars[key].set(not value)
                return
        self.cfg[key] = value
        settings.save(self.cfg)
        self.log(f"{self.switch_titles[key]}: {'вкл' if value else 'выкл'}")

    # ---------- сервис и инструменты ----------

    def install_service_ui(self):
        def done(running):
            self.log("Служба установлена и запущена. Обход стартует сам при загрузке Windows."
                     if running else "Служба установлена, но не запустилась. Смотрите winws.log")
            self._service = True

        self._job("Устанавливаю службу Windows…",
                  lambda: engine.install_service(self.cfg["strategy"], *self._game_args()), on_done=done)

    def remove_service_ui(self):
        def done(_result):
            self.log("Службы zapret и WinDivert удалены")
            self._service = False

        self._job("Удаляю службы…", engine.remove_service, on_done=done)

    def status_ui(self):
        self._job("Проверяю состояние…", diagnostics.service_report,
                  on_done=lambda lines: [self.log(line) for line in lines])

    def diagnostics_ui(self):
        self._job("Запускаю диагностику системы…", diagnostics.run_checks, on_done=self._show_checks)

    def _show_checks(self, checks):
        for check in checks:
            self.log(f"{CHECK_PREFIX.get(check.level, '')} {check.text}")
        self.log("Диагностика завершена")

    def update_ipset_ui(self):
        def done(changed):
            self.log("Список IPSet обновлён" if changed else "Список IPSet уже актуален")
            if changed and self._running:
                self._start_action("Перезапускаю обход с новым списком IPSet…")

        self._job("Обновляю список IPSet…", updater.update_ipset, on_done=done)

    def update_hosts_ui(self):
        def done(added):
            self.log(f"hosts обновлён: добавлено записей {added}" if added else "hosts уже актуален")

        self._job("Обновляю файл hosts…", hosts.update_hosts, on_done=done)

    def apply_fakes(self):
        discord_name = self.fake_discord.get()
        game_name = self.fake_game.get()
        if "нет файлов" in (discord_name, game_name):
            self.log("В папке bin нет файлов фейков")
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
                  on_done=lambda was: self.log("Фейки применены" + (", обход перезапущен" if was else "")))

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
            self.log("Проверяю все стратегии. Это займёт несколько минут.")
        else:
            self.log(f"Проверяю стратегию «{self._name_by_id(selected)}»")
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
            self.log(f"Ошибка проверки: {error}")
        elif report is not None:
            for r in report.results:
                self.log(f"{r.name}: доступно {r.score} из {r.total}")
            if report.cancelled:
                self.log("Проверка остановлена")
            elif all_mode and report.best:
                self.cfg["strategy"] = report.best.id
                self.cfg["first_run"] = False
                settings.save(self.cfg)
                self.strategy_menu.set(report.best.name)
                self._update_summary()
                self.log(f"Лучшая стратегия: «{report.best.name}» ({report.best.score} из "
                         f"{report.best.total}). Выбрана автоматически.")
        self._refresh_status()
        if start_after and report is not None and not report.cancelled and report.best:
            self._start_action("Запускаю обход с выбранной стратегией…")

    def _probe_bypass(self):
        """None — интернета нет (чинить нечего); True — обход не работает; False — всё в порядке."""
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
        self.log("Discord и YouTube не открываются. Автоматически подбираю стратегию заново…")
        self._run_test(all_mode=True)

    # ---------- обновления списков и программы ----------

    def check_updates_manual(self):
        self._check_lists(silent=False)
        self._check_app(manual=True)

    def _check_lists(self, silent=False):
        if self._busy_update:
            return
        self._busy_update = True
        self.check_btn.configure(state="disabled")
        if not silent:
            self.log("Проверяю обновления списков…")
        self._bg(updater.update_lists, lambda res, err: self._after_lists(res, err, silent))

    def _after_lists(self, result, error, silent):
        self._busy_update = False
        self.check_btn.configure(state="normal")
        if error:
            self.log(f"Не удалось обновить списки: {error}")
            return
        self.cfg["lists_version"] = result.version
        self.cfg["last_check"] = dt.datetime.now().strftime("%d.%m.%Y %H:%M")
        settings.save(self.cfg)
        self.info_label.configure(text=self._info_text())
        if result.changed:
            self.log(f"Обновлено файлов: {len(result.changed)}, версия списков {result.version}")
            if self._running and not self._busy:
                self._start_action("Перезапускаю обход с новыми списками…")
        elif not silent:
            self.log("Списки уже актуальны")

    def _check_app(self, manual: bool):
        if self._busy_app:
            return
        self._busy_app = True
        if manual:
            self.log("Проверяю новую версию программы на GitHub…")
        self._bg(app_updater.fetch_latest, lambda info, err: self._after_app_check(info, err, manual))

    def _after_app_check(self, info, error, manual):
        self._busy_app = False
        if error:
            self.log(f"Не удалось проверить версию программы: {error}")
            return
        self._latest = info.version if info else None
        self.info_label.configure(text=self._info_text())
        if info is None or not app_updater.is_newer(info.version):
            if manual:
                self.log(f"Программа актуальна: {__version__}")
            return
        self._pending_update = info
        if self.cfg["auto_update_app"]:
            self.log(f"Найдена версия {info.version}, устанавливаю автоматически")
            self._install_update(info)
        else:
            self.banner_label.configure(text=f"Доступна версия {info.version}")
            self.banner.pack(fill="x", pady=(10, 0))

    def _install_pending(self):
        if self._pending_update:
            self._install_update(self._pending_update)

    def _install_update(self, info):
        if self._busy:
            self.log("Сейчас выполняется другое действие, обновление отложено")
            return
        self.banner.pack_forget()
        self._set_busy(True)
        self.cfg["resume_bypass"] = self._running
        settings.save(self.cfg)
        self.log(f"Скачиваю zapret-app {info.version}…")
        self._bg(lambda: app_updater.download(info), self._on_downloaded)

    def _on_downloaded(self, path, error):
        if error:
            self._set_busy(False)
            self.cfg["resume_bypass"] = False
            settings.save(self.cfg)
            self.log(f"Не удалось скачать обновление: {error}")
            return
        try:
            app_updater.launch_installer(path)
        except Exception as exc:  # noqa: BLE001
            self._set_busy(False)
            self.log(f"Не удалось запустить установщик: {exc}")
            return
        self.log("Устанавливаю обновление. Программа закроется и откроется новая версия.")
        self.after(800, self._quit)
