"""Обновление списков из официального репозитория flowseal/zapret-discord-youtube.

Текстовые списки обновляются сразу. Список IPSet учитывает режим:
  loaded — полный список (файл ipset-all.txt);
  none   — выключен: в файле только заглушка, полный список лежит в ipset-all.txt.backup;
  any    — любые IP: файл пустой, полный список тоже в backup.
Пользовательские файлы *-user.txt не перезаписываются. Бинарники не обновляются.
"""
import os
import shutil
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from . import paths

REPO_RAW = "https://raw.githubusercontent.com/flowseal/zapret-discord-youtube/main/"
VERSION_PATH = ".service/version.txt"
IPSET_PATH = ".service/ipset-service.txt"
TIMEOUT = 20
IPSET_NAME = "ipset-all.txt"
IPSET_BACKUP = "ipset-all.txt.backup"
IPSET_PLACEHOLDER = "203.0.113.113/32"
IPSET_MODES = ("loaded", "none", "any")

REMOTE_FILES = {
    "lists/list-general.txt": "list-general.txt",
    "lists/list-google.txt": "list-google.txt",
    "lists/list-exclude.txt": "list-exclude.txt",
    "lists/ipset-exclude.txt": "ipset-exclude.txt",
}


@dataclass
class UpdateResult:
    version: str
    changed: list[str] = field(default_factory=list)


def _fetch(path: str) -> bytes:
    req = urllib.request.Request(REPO_RAW + path, headers={"User-Agent": "zapret-app"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def _atomic_write(dst: Path, data: bytes) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, dst)


def _ipset_files() -> tuple:
    return paths.LISTS_DIR / IPSET_NAME, paths.LISTS_DIR / IPSET_BACKUP


def ipset_mode() -> str:
    active, _ = _ipset_files()
    if not active.exists():
        return "none"
    content = active.read_text(encoding="utf-8", errors="replace")
    if not content.strip():
        return "any"
    if IPSET_PLACEHOLDER in content:
        return "none"
    return "loaded"


def set_ipset_mode(mode: str) -> None:
    if mode not in IPSET_MODES:
        raise ValueError(f"неизвестный режим IPSet: {mode}")
    active, backup = _ipset_files()
    current = ipset_mode()
    if mode == current:
        return
    if current == "loaded":
        shutil.copyfile(active, backup)  # сохраняем полный список перед отключением
    if mode == "loaded":
        if backup.exists():
            shutil.copyfile(backup, active)
        else:
            _atomic_write(active, _fetch(IPSET_PATH))
    elif mode == "none":
        _atomic_write(active, (IPSET_PLACEHOLDER + "\n").encode("ascii"))
    else:
        _atomic_write(active, b"")


def update_ipset() -> bool:
    """Скачивает полный список IPSet. Пишет в активный файл, если режим loaded, иначе в backup."""
    data = _fetch(IPSET_PATH)
    if not data.strip():
        raise RuntimeError("Получен пустой список IPSet, обновление отменено")
    active, backup = _ipset_files()
    target = active if ipset_mode() == "loaded" else backup
    if target.exists() and target.read_bytes() == data:
        return False
    _atomic_write(target, data)
    return True


def update_lists() -> UpdateResult:
    version = _fetch(VERSION_PATH).decode("utf-8", errors="replace").strip()
    fresh = {name: _fetch(remote) for remote, name in REMOTE_FILES.items()}
    for name, data in fresh.items():
        if not data.strip():
            raise RuntimeError(f"Получен пустой файл {name}, обновление отменено")
    result = UpdateResult(version=version)
    paths.LISTS_DIR.mkdir(parents=True, exist_ok=True)
    for name, data in fresh.items():
        dst = paths.LISTS_DIR / name
        if dst.exists() and dst.read_bytes() == data:
            continue
        _atomic_write(dst, data)
        result.changed.append(name)
    if update_ipset():
        result.changed.append(IPSET_NAME)
    return result
