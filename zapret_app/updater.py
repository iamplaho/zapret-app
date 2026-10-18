"""Обновление списков из официального репозитория flowseal/zapret-discord-youtube.

Обновляются только текстовые списки. Бинарники (winws.exe, WinDivert) не трогаются:
их обновление требует отдельного проверенного релиза.
Пользовательские файлы (*-user.txt) не перезаписываются.
"""
import os
import urllib.request
from dataclasses import dataclass, field

from . import paths

REPO_RAW = "https://raw.githubusercontent.com/flowseal/zapret-discord-youtube/main/"
VERSION_PATH = ".service/version.txt"
TIMEOUT = 20

# путь в репозитории -> имя файла в папке lists/
REMOTE_FILES = {
    "lists/list-general.txt": "list-general.txt",
    "lists/list-google.txt": "list-google.txt",
    "lists/list-exclude.txt": "list-exclude.txt",
    "lists/ipset-exclude.txt": "ipset-exclude.txt",
    ".service/ipset-service.txt": "ipset-all.txt",
}


@dataclass
class UpdateResult:
    version: str
    changed: list[str] = field(default_factory=list)


def _fetch(path: str) -> bytes:
    req = urllib.request.Request(REPO_RAW + path, headers={"User-Agent": "zapret-app"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def _atomic_write(dst, data: bytes) -> None:
    tmp = dst.with_name(dst.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, dst)


def update_lists() -> UpdateResult:
    version = _fetch(VERSION_PATH).decode("utf-8", errors="replace").strip()

    # Сначала скачиваем всё, потом пишем: при ошибке сети локальные списки не портятся.
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
    return result
