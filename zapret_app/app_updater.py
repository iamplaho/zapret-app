"""Автообновление самой программы через страницу релиза на GitHub.

Не используется GitHub API: у него жёсткий лимит запросов (403 rate limit).
Вместо этого программа открывает /releases/latest, узнаёт тег последнего релиза
по адресу перенаправления и скачивает установщик по известному имени файла.
"""
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
LATEST_URL = f"https://github.com/{REPO}/releases/latest"
DOWNLOAD_BASE = f"https://github.com/{REPO}/releases/download/"
ASSET_PREFIX = "zapret-app-setup-"
TIMEOUT = 20
MIN_INSTALLER_SIZE = 1_000_000
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
TAG_RE = re.compile(r"/releases/tag/([^/?#]+)$")


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


def tag_from_url(url: str):
    """Достаёт тег релиза из адреса вида .../releases/tag/v0.4.0."""
    match = TAG_RE.search(url or "")
    return match.group(1) if match else None


def _open(url: str, method: str = "HEAD"):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": "zapret-app"})
    return urllib.request.urlopen(req, timeout=TIMEOUT)


def fetch_latest():
    """Возвращает ReleaseInfo или None, если релиза с установщиком нет."""
    try:
        with _open(LATEST_URL) as resp:
            tag = tag_from_url(resp.geturl())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    if not tag:
        return None
    version = tag.lstrip("v")
    name = f"{ASSET_PREFIX}{version}.exe"
    url = f"{DOWNLOAD_BASE}{tag}/{name}"
    try:
        with _open(url):
            pass
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None  # релиз есть, а установщика в нём нет
        raise
    return ReleaseInfo(version=version, name=name, url=url)


def download(info: ReleaseInfo) -> Path:
    folder = Path(tempfile.gettempdir()) / "zapret-app-update"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / info.name
    tmp = dest.with_suffix(".part")
    with _open(info.url, method="GET") as resp, open(tmp, "wb") as out:
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
