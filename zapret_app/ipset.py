"""Режимы IPSet как в оригинальном service.bat.

loaded — полный список IP из официального репозитория (по умолчанию);
none   — IP-фильтр отключён (файл содержит один фиктивный адрес, как в оригинале);
any    — фильтр применяется ко всем IP (файл пустой).

Официальный список хранится в ipset-loaded.txt и обновляется загрузчиком списков.
Активный файл ipset-all.txt создаётся из него по выбранному режиму.
"""
import os

from . import paths

MODES = ("loaded", "none", "any")
DUMMY_IP = "203.0.113.113/32"
LOADED_FILE = paths.LISTS_DIR / "ipset-loaded.txt"
ACTIVE_FILE = paths.LISTS_DIR / "ipset-all.txt"


def build_content(mode: str, loaded: bytes) -> bytes:
    if mode == "loaded":
        return loaded
    if mode == "none":
        return (DUMMY_IP + "\n").encode("utf-8")
    if mode == "any":
        return b""
    raise ValueError(f"Неизвестный режим IPSet: {mode}")


def apply(mode: str) -> None:
    """Пересоздаёт активный файл ipset-all.txt под выбранный режим."""
    loaded = LOADED_FILE.read_bytes() if LOADED_FILE.exists() else b""
    content = build_content(mode, loaded)
    tmp = ACTIVE_FILE.with_name(ACTIVE_FILE.name + ".tmp")
    tmp.write_bytes(content)
    os.replace(tmp, ACTIVE_FILE)
