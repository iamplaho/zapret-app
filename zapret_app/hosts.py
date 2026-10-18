"""Обновление файла hosts из репозитория (как «Update Hosts File» в оригинале).

Отличие: оригинал только показывает, что нужно скопировать вручную, а здесь записи
дописываются автоматически. Старый файл сохраняется как hosts.zapret-app.bak.
Дописываются только строки, которых ещё нет в файле.
"""
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path

HOSTS_PATH = Path(os.environ.get("SystemRoot") or r"C:\Windows") / "System32" / "drivers" / "etc" / "hosts"
HOSTS_URL = "https://raw.githubusercontent.com/flowseal/zapret-discord-youtube/main/.service/hosts"
MARKER = "# zapret-app: added automatically"
CREATE_NO_WINDOW = 0x08000000


def missing_entries(current: str, repo: str) -> list[str]:
    have = {line.strip().lower() for line in current.splitlines()}
    missing = []
    for line in repo.splitlines():
        entry = line.strip()
        if entry and not entry.startswith("#") and entry.lower() not in have:
            if entry not in missing:
                missing.append(entry)
    return missing


def build_block(entries: list[str]) -> bytes:
    text = "\r\n" + MARKER + "\r\n" + "\r\n".join(entries) + "\r\n"
    return text.encode("ascii", errors="replace")


def update_hosts() -> int:
    with urllib.request.urlopen(HOSTS_URL, timeout=20) as resp:
        repo = resp.read().decode("utf-8", errors="replace")
    current = HOSTS_PATH.read_bytes().decode("utf-8", errors="replace")
    entries = missing_entries(current, repo)
    if not entries:
        return 0
    backup = HOSTS_PATH.with_name("hosts.zapret-app.bak")
    if not backup.exists():
        shutil.copyfile(HOSTS_PATH, backup)
    with open(HOSTS_PATH, "ab") as f:  # дописываем в конец, существующее содержимое не трогаем
        f.write(build_block(entries))
    subprocess.run(["ipconfig", "/flushdns"], capture_output=True, creationflags=CREATE_NO_WINDOW)
    return len(entries)
