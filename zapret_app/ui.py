"""Главное окно приложения."""
import datetime as dt
import queue
import sys
import tkinter as tk

import customtkinter as ctk
from PIL import Image

from . import __version__, engine, paths, settings, strategies, system, updater

try:
    from .tray import Tray
except Exception:  # noqa: BLE001  pystray недоступен — приложение работает без трея
    Tray = None

GREEN = "#22c55e"
RED = "#ef4444"
MUTED = "#94a3b8"
CARD = "#1e293b"
ACCENT = "#6366f1"

SWITCH_LABELS = {
    "game_filter": "Игровой фильтр",
    "auto_update": "Автообновление списков",
    "autostart": "Автозапуск",
    "close_to_tray": "Сворачивание в трей",
}


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title(f"zapret-app {__version__}")
        self.geometry("580x760")
        self.minsize(580, 760)
        self.after(300, self._apply_icon)  # CustomTkinter сбрасывает иконку при старте — ставим с задержкой

        paths.ensure_data_dirs()
        self.cfg = settings.load()
        self.cfg["autostart"] = system.autostart_enabled()
        self.strategy_list = strategies.load_all()

        self._running = False
        self._busy = False
        self._busy_update = False
        self._queue: queue.Queue = queue.Queue()
        self.vars: dict[str, tk.BooleanVar] = {}
        self.tray = None

        self._build()
        self.after(100, self._pump)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._start_tray()

        self.log("Приложение запущено")
        if not system.is_admin():
            self.log("Нет прав администратора. Обход не запустится: закройте приложение и запустите его от имени администратора.")

        self._refresh_status()
        if self.cfg["auto_update"]:
            self.after(1000, lambda: self.check_updates(silent=True))
        if "--autostart" in sys.argv:
            self.after(2000, self._autostart_engine)
            if self.tray:
                self.withdraw()  # при автозапуске стартуем свёрнутыми в трей
        self.after(5000, self._poll)

    # ---------- окно, трей, иконка ----------

    def _apply_icon(self):
        if paths.ICON_ICO.exists():
            try:
                self.iconbitmap(str(paths.ICON_ICO))
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
        """Вызов из потока трея: передаём действие в главный поток через очередь."""
        self._queue.put((lambda *_: fn(), None, None))

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

    # ---------- построение интерфейса ----------

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 6))
        if paths.ICON_PNG.exists():
            logo = Image.open(paths.ICON_PNG).resize((112, 112), Image.Resampling.LANCZOS)
            img = ctk.CTkImage(light_image=logo, dark_image=logo, size=(56, 56))
            ctk.CTkLabel(header, image=img, text="").pack(side="left", padx=(0, 14))
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(titles, text="zapret-app", font=ctk.CTkFont(size=28, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(titles, text="Обход блокировок Discord и YouTube", text_color=MUTED,
                     font=ctk.CTkFont(size=13)).pack(anchor="w")

        card = self._card()
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=18)
        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        self.status_label = ctk.CTkLabel(left, text="Проверка…", font=ctk.CTkFont(size=20, weight="bold"), anchor="w")
        self.status_label.pack(anchor="w")
        self.status_hint = ctk.CTkLabel(left, text="", text_color=MUTED, font=ctk.CTkFont(size=12),
                                        anchor="w", justify="left", wraplength=340)
        self.status_hint.pack(anchor="w")
        self.toggle_btn = ctk.CTkButton(row, text="Включить", width=150, height=46, corner_radius=12,
                                        font=ctk.CTkFont(size=15, weight="bold"),
                                        fg_color=ACCENT, hover_color="#4f46e5", command=self.toggle)
        self.toggle_btn.pack(side="right")
        self.toggle_btn.configure(state="disabled")

        card = self._card()
        self._section_title(card, "Стратегия обхода")
        names = [s["name"] for s in self.strategy_list]
        self.strategy_menu = ctk.CTkOptionMenu(card, values=names, command=self.on_strategy_change, height=36)
        self.strategy_menu.pack(fill="x", padx=20, pady=(0, 16))
        self.strategy_menu.set(self._name_by_id(self.cfg["strategy"]))

        card = self._card()
        self._section_title(card, "Настройки")
        self._switch(card, "game_filter", "Игровой фильтр (ускорение игровых серверов)")
        self._switch(card, "auto_update", "Автообновление списков из официального репозитория")
        self._switch(card, "autostart", "Запускать вместе с Windows")
        self._switch(card, "close_to_tray", "Сворачивать в трей при закрытии окна")
        ctk.CTkFrame(card, height=6, fg_color="transparent").pack()

        card = self._card()
        self._section_title(card, "Обновления")
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 16))
        self.update_info = ctk.CTkLabel(row, text=self._update_text(), text_color=MUTED,
                                        font=ctk.CTkFont(size=12), anchor="w", justify="left")
        self.update_info.pack(side="left", fill="x", expand=True)
        self.update_btn = ctk.CTkButton(row, text="Проверить", width=120,
                                        command=lambda: self.check_updates(silent=False))
        self.update_btn.pack(side="right")

        card = self._card(expand=True)
        self._section_title(card, "Журнал")
        self.log_box = ctk.CTkTextbox(card, height=150, font=ctk.CTkFont(family="Consolas", size=12),
                                      state="disabled")
        self.log_box.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        ctk.CTkLabel(self, text="Основано на flowseal/zapret-discord-youtube · лицензия MIT",
                     text_color=MUTED, font=ctk.CTkFont(size=11)).pack(pady=(4, 10))

    def _card(self, expand=False):
        frame = ctk.CTkFrame(self, corner_radius=16, fg_color=CARD)
        frame.pack(fill="both" if expand else "x", expand=expand, padx=24, pady=6)
        return frame

    def _section_title(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=20, pady=(16, 6))

    def _switch(self, parent, key, text):
        var = tk.BooleanVar(value=bool(self.cfg[key]))
        self.vars[key] = var
        ctk.CTkSwitch(parent, text=text, variable=var,
                      command=lambda: self.on_switch(key)).pack(anchor="w", padx=20, pady=6)

    def _update_text(self):
        return (f"Версия списков: {self.cfg['lists_version'] or '—'}\n"
                f"Последняя проверка: {self.cfg['last_check'] or '—'}")

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

    def log(self, msg: str):
        line = f"[{dt.datetime.now():%H:%M:%S}] {msg}\n"
        self.log_box.configure(state="normal")
        self.log_box.insert("end", line)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        try:
            with open(paths.APP_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            pass

    def _bg(self, fn, done):
        """Выполняет fn в фоне; done(result, error) вызывается в главном потоке."""
        import threading

        def worker():
            try:
                result, error = fn(), None
            except Exception as exc:  # noqa: BLE001
                result, error = None, exc
            self._queue.put((done, result, error))
        threading.Thread(target=worker, daemon=True).start()

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

    # ---------- статус и управление обходом ----------

    def _refresh_status(self):
        self._bg(engine.is_running, lambda running, err: self._set_running(bool(running)))

    def _set_running(self, running: bool):
        self._running = running
        self.toggle_btn.configure(state="disabled" if self._busy else "normal")
        if running:
            self.status_label.configure(text="● Работает", text_color=GREEN)
            self.status_hint.configure(text="Обход активен. Он продолжит работать после закрытия окна, пока вы его не выключите.")
            self.toggle_btn.configure(text="Выключить", fg_color=RED, hover_color="#dc2626")
        else:
            self.status_label.configure(text="● Выключено", text_color=MUTED)
            self.status_hint.configure(text="Нажмите «Включить», чтобы начать обход.")
            self.toggle_btn.configure(text="Включить", fg_color=ACCENT, hover_color="#4f46e5")

    def _start_engine(self):
        return engine.start(self.cfg["strategy"], self.cfg["game_filter"])

    def _start_action(self, note: str):
        self._busy = True
        self.toggle_btn.configure(state="disabled")
        self.log(note)
        self._bg(self._start_engine, self._after_start)

    def toggle(self):
        if self._busy:
            return
        if self._running:
            self._busy = True
            self.toggle_btn.configure(state="disabled")
            self.log("Выключаю обход…")
            self._bg(engine.stop, lambda _r, err: self._finish_action("Обход выключен", err))
        else:
            self._start_action("Запускаю обход…")

    def _finish_action(self, message, error):
        self._busy = False
        self.log(f"Ошибка: {error}" if error else message)
        self._refresh_status()

    def _after_start(self, running, error):
        self._busy = False
        if error:
            self.log(f"Ошибка запуска: {error}")
        elif running:
            self.log("Обход включён")
        else:
            self.log("winws не запустился. Проверьте права администратора и файл winws.log в папке zapret-app.")
        self._refresh_status()

    def _autostart_engine(self):
        if not self._running and not self._busy:
            self.toggle()

    # ---------- реакции на настройки ----------

    def on_strategy_change(self, name):
        self.cfg["strategy"] = self._id_by_name(name)
        settings.save(self.cfg)
        self.log(f"Выбрана стратегия: {name}")
        if self._running and not self._busy:
            self._start_action("Перезапускаю обход с новой стратегией…")

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
        self.log(f"{SWITCH_LABELS[key]}: {'вкл' if value else 'выкл'}")
        if key == "game_filter" and self._running and not self._busy:
            self._start_action("Перезапускаю обход с учётом игрового фильтра…")

    # ---------- обновления списков ----------

    def check_updates(self, silent=False):
        if self._busy_update:
            return
        self._busy_update = True
        self.update_btn.configure(state="disabled")
        if not silent:
            self.log("Проверяю обновления списков…")
        self._bg(updater.update_lists, lambda res, err: self._after_update(res, err, silent))

    def _after_update(self, result, error, silent):
        self._busy_update = False
        self.update_btn.configure(state="normal")
        if error:
            self.log(f"Не удалось обновить списки: {error}")
            return
        self.cfg["lists_version"] = result.version
        self.cfg["last_check"] = dt.datetime.now().strftime("%d.%m.%Y %H:%M")
        settings.save(self.cfg)
        self.update_info.configure(text=self._update_text())
        if result.changed:
            self.log(f"Обновлено файлов: {len(result.changed)}, версия списков {result.version}")
            if self._running and not self._busy:
                self._start_action("Перезапускаю обход с новыми списками…")
        elif not silent:
            self.log("Списки уже актуальны")
