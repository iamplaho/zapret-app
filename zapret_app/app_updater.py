"""Автообновление самой программы через GitHub Releases.

Программа берёт последний релиз репозитория, скачивает установщик
zapret-app-setup-<версия>.exe и запускает его. Установщик сам останавливает обход
и заменяет файлы программы. Скачивать разрешено только с адреса этого репозитория.
"""
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import __version__

REPO = "iamplaho/zapret-app"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET_PREFIX = "zapret-app-setup-"
DOWNLOAD_PREFIX = f"https://github.com/{REPO}/releases/download/"
TIMEOUT = 20
MIN_INSTALLER_SIZE = 1_000_000
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200


@dataclass
class ReleaseInfo:
    version: str
    name: str
    url: str


def parse_version(text):
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text or "")
    return tuple(int(x) for x in match.groups()) if match else None


def is_newer(remote: str, local: str = __version__) -> bool:
    r, l = parse_version(remote), parse_version(local)
    return r is not None and l is not None and r > l


def pick_asset(assets):
    for asset in assets or []:
        name = asset.get("name", "")
        url = asset.get("browser_download_url", "")
        if name.startswith(ASSET_PREFIX) and name.endswith(".exe") and url.startswith(DOWNLOAD_PREFIX):
            return asset
    return None


def _get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "zapret-app",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_latest():
    """Возвращает ReleaseInfo или None, если релизов с установщиком нет."""
    try:
        data = _get_json(API_LATEST)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    asset = pick_asset(data.get("assets"))
    if asset is None:
        return None
    return ReleaseInfo(version=str(data.get("tag_name", "")).lstrip("v"),
                       name=asset["name"], url=asset["browser_download_url"])


def download(info: ReleaseInfo) -> Path:
    folder = Path(tempfile.gettempdir()) / "zapret-app-update"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / info.name
    tmp = dest.with_suffix(".part")
    req = urllib.request.Request(info.url, headers={"User-Agent": "zapret-app"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp, open(tmp, "wb") as out:
        while True:
            chunk = resp.read(64 * 1024)
            if not chunk:
                break
            out.write(chunk)
    if tmp.stat().st_size < MIN_INSTALLER_SIZE:
        tmp.unlink(missing_ok=True)
        raise RuntimeError("загруженный файл слишком мал, загрузка, возможно, прервалась")
    os.replace(tmp, dest)
    return dest


def launch_installer(path: Path) -> None:
    subprocess.Popen(
        [str(path), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )
