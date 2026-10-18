"""Значок в системном трее (pystray)."""
import threading

import pystray
from PIL import Image

from . import paths


class Tray:
    def __init__(self, on_open, on_toggle, on_quit):
        image = Image.open(paths.ICON_PNG).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
        menu = pystray.Menu(
            pystray.MenuItem("Открыть zapret-app", lambda icon, item: on_open(), default=True),
            pystray.MenuItem("Включить / выключить обход", lambda icon, item: on_toggle()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Выход (обход продолжит работать)", lambda icon, item: on_quit()),
        )
        self._icon = pystray.Icon("zapret-app", image, "zapret-app", menu)

    def start(self):
        threading.Thread(target=self._icon.run, daemon=True).start()

    def stop(self):
        try:
            self._icon.stop()
        except Exception:  # noqa: BLE001
            pass
