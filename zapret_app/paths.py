"""Пути к файлам приложения."""
import os
import shutil
import sys
from pathlib import Path

APP_NAME = "zapret-app"


def _base_dir() -> Path:
    # В собранной программе файлы лежат в _MEIPASS, при разработке — в корне проекта.
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


BASE_DIR = _base_dir()
RUNTIME_DIR = BASE_DIR / "runtime"
BIN_DIR = RUNTIME_DIR / "bin"
BUNDLED_LISTS_DIR = RUNTIME_DIR / "lists"
STRATEGIES_FILE = RUNTIME_DIR / "strategies.json"
TARGETS_FILE = RUNTIME_DIR / "targets.txt"
WINWS_EXE = BIN_DIR / "winws.exe"

ASSETS_DIR = BASE_DIR / "assets"
ICON_ICO = ASSETS_DIR / "icon.ico"
ICON_PNG = ASSETS_DIR / "icon.png"

# Настройки и журналы — для пользователя (%APPDATA%).
DATA_DIR = Path(os.environ.get("APPDATA") or Path.home()) / APP_NAME
SETTINGS_FILE = DATA_DIR / "settings.json"
APP_LOG_FILE = DATA_DIR / "app.log"
WINWS_LOG_FILE = DATA_DIR / "winws.log"

# Списки — общие для системы (%ProgramData%), чтобы их читала и служба Windows (она работает под SYSTEM).
SHARED_DIR = Path(os.environ.get("ProgramData") or r"C:\ProgramData") / APP_NAME
LISTS_DIR = SHARED_DIR / "lists"


def ensure_data_dirs() -> None:
    """Создаёт папки, переносит списки из старой версии и копирует стартовые списки."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LISTS_DIR.mkdir(parents=True, exist_ok=True)
    old_lists = DATA_DIR / "lists"
    if old_lists.exists():
        for src in old_lists.iterdir():
            dst = LISTS_DIR / src.name
            if src.is_file() and not dst.exists():
                shutil.copy2(src, dst)
    if BUNDLED_LISTS_DIR.exists():
        for src in BUNDLED_LISTS_DIR.iterdir():
            dst = LISTS_DIR / src.name
            if not dst.exists():
                shutil.copy2(src, dst)
