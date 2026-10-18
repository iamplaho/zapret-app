"""Фейковые пакеты (fake payload): какие .bin используются для Discord и игр.

Как в оригинале («Replace active fakes»): активные файлы ACTIVE_DISCORD_UDP.bin и
ACTIVE_GAME_UDP.bin — это копии выбранного .bin из папки bin.
"""
import hashlib
import shutil

from . import paths

ACTIVE = {"discord": "ACTIVE_DISCORD_UDP.bin", "game": "ACTIVE_GAME_UDP.bin"}


def list_fakes() -> list[str]:
    if not paths.BIN_DIR.exists():
        return []
    return sorted(p.name for p in paths.BIN_DIR.glob("*.bin") if not p.name.startswith("ACTIVE_"))


def _sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current(kind: str):
    """Имя фейка, который сейчас стоит в ACTIVE-файле, или None."""
    active = paths.BIN_DIR / ACTIVE[kind]
    if not active.exists():
        return None
    digest = _sha(active)
    for name in list_fakes():
        if _sha(paths.BIN_DIR / name) == digest:
            return name
    return None


def apply(kind: str, name: str) -> None:
    src = paths.BIN_DIR / name
    if not src.exists():
        raise FileNotFoundError(f"Нет файла {name}")
    shutil.copyfile(src, paths.BIN_DIR / ACTIVE[kind])
