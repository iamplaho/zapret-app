"""Пути к файлам приложения."""
import os
import shutil
import sys
from pathlib import Path

APP_NAME = "zapret-app"


def _base_dir() -> Path:
    # В собранном приложении (PyInstaller) файлы лежат в _MEIPASS, в разработке — в корне проекта.
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


BASE_DIR = _base_dir()
RUNTIME_DIR = BASE_DIR / "runtime"
BIN_DIR = RUNTIME_DIR / "bin"
BUNDLED_LISTS_DIR = RUNTIME_DIR / "lists"
STRATEGIES_FILE = RUNTIME_DIR / "strategies.json"
WINWS_EXE = BIN_DIR / "winws.exe"

ASSETS_DIR = BASE_DIR / "assets"
ICON_ICO = ASSETS_DIR / "icon.ico"
ICON_PNG = ASSETS_DIR / "icon.png"

# Всё, что меняется во время работы, хранится в %APPDATA%, а не рядом с exe.
DATA_DIR = Path(os.environ.get("APPDATA") or Path.home()) / APP_NAME
LISTS_DIR = DATA_DIR / "lists"
SETTINGS_FILE = DATA_DIR / "settings.json"
APP_LOG_FILE = DATA_DIR / "app.log"
WINWS_LOG_FILE = DATA_DIR / "winws.log"


def ensure_data_dirs() -> None:
    """Создаёт папки данных и копирует стартовые списки, если их ещё нет."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LISTS_DIR.mkdir(parents=True, exist_ok=True)
    if BUNDLED_LISTS_DIR.exists():
        for src in BUNDLED_LISTS_DIR.iterdir():
            dst = LISTS_DIR / src.name
            if not dst.exists():
                shutil.copy2(src, dst)
