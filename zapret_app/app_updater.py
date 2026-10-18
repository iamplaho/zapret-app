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
FEED_URL = f"https://github.com/{REPO}/releases.atom"
DOWNLOAD_BASE = f"https://github.com/{REPO}/releases/download/"
ASSET_PREFIX = "zapret-app-setup-"
TIMEOUT = 20
MIN_INSTALLER_SIZE = 1_000_000
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
TAG_RE = re.compile(r"/releases/tag/([^/?#]+)$")
TAG_IN_FEED = re.compile(r"/releases/tag/(v\d+\.\d+\.\d+[^\"<>\s?#]*)")


@dataclass
class ReleaseInfo:
    version: str
    name: str
    url: str


def parse_version(text):
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text or "")
    return tuple(int(x) for x in match.groups()) if match else None


def is_newer(remote: str, local: str = __version__) -> bool:
    """True, если релиз remote новее установленной версии local.

    Сборка dev-<коммит> (не релиз) считается старее любого релиза.
    """
    r = parse_version(remote)
    if r is None:
        return False
    l = parse_version(local)
    if l is None:
        return True
    return r > l


def tag_from_url(url: str):
    """Достаёт тег релиза из адреса вида .../releases/tag/v0.4.0."""
    match = TAG_RE.search(url or "")
    return match.group(1) if match else None


def _open(url: str, method: str = "HEAD"):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": "zapret-app"})
    return urllib.request.urlopen(req, timeout=TIMEOUT)


@dataclass
class LatestCheck:
    tag: object          # тег последнего релиза или None
    info: object         # ReleaseInfo, если установщик найден, иначе None
    note: str            # понятное объяснение результата


def parse_feed_tags(text: str) -> list:
    """Теги релизов из ленты releases.atom, от новой версии к старой.

    В ленте есть и pre-release, в отличие от /releases/latest.
    """
    tags = []
    for match in TAG_IN_FEED.finditer(text or ""):
        tag = match.group(1)
        if tag not in tags and parse_version(tag):
            tags.append(tag)
    tags.sort(key=lambda t: parse_version(t), reverse=True)
    return tags


def check_latest() -> LatestCheck:
    """Проверяет самый новый релиз (включая pre-release) и наличие установщика."""
    try:
        with _open(FEED_URL, method="GET") as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return LatestCheck(None, None, "Репозиторий не найден или релизов пока нет")
        raise
    tags = parse_feed_tags(text)
    if not tags:
        return LatestCheck(None, None, "На GitHub не найдено ни одного релиза с номером версии")
    tag = tags[0]
    version = tag.lstrip("v")
    name = f"{ASSET_PREFIX}{version}.exe"
    url = f"{DOWNLOAD_BASE}{tag}/{name}"
    try:
        with _open(url):
            pass
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return LatestCheck(tag, None,
                               f"Релиз {tag} есть, но файла {name} в нём нет. "
                               "Проверьте, что сборка в Actions прошла успешно")
        raise
    return LatestCheck(tag, ReleaseInfo(version=version, name=name, url=url), "ok")


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
