"""Проверка стратегий — аналог «Run Tests» из оригинала.

Для каждой стратегии запускается winws.exe, затем проверяются HTTPS-адреса из
runtime/targets.txt. Балл стратегии — сколько адресов ответили.
Ping-only цели (PING:...) пропускаются: для них нужен ICMP.
"""
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from . import engine, paths, strategies

TIMEOUT = 4
WORKERS = 8
LINE_RE = re.compile(r'^\s*(\w+)\s*=\s*"(https?://[^"]+)"\s*$')


@dataclass
class StrategyResult:
    id: str
    name: str
    score: int
    total: int


@dataclass
class Report:
    results: list = field(default_factory=list)
    best: object = None
    cancelled: bool = False


def load_targets(path=None):
    path = path or paths.TARGETS_FILE
    targets = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = LINE_RE.match(line)
        if match:
            targets.append((match.group(1), match.group(2)))
    return targets


def check_url(url: str, timeout: int = TIMEOUT) -> bool:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except urllib.error.HTTPError:
        return True  # сервер ответил кодом ошибки, значит соединение есть
    except Exception:  # noqa: BLE001
        return False


def _score(targets, cancel) -> int:
    urls = [url for _, url in targets]
    ok = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(check_url, url) for url in urls]
        for future in futures:
            if cancel.is_set():
                break
            if future.result():
                ok += 1
    return ok


def run(strategy_ids, game, was_running, selected_id, all_mode, progress, cancel) -> Report:
    """game = (mode, tcp_range, udp_range). В конце возвращает обход в прежнее состояние."""
    targets = load_targets()
    if not targets:
        raise RuntimeError("В runtime/targets.txt нет адресов для проверки")
    names = {s["id"]: s["name"] for s in strategies.load_all()}
    report = Report()
    try:
        for index, sid in enumerate(strategy_ids, 1):
            if cancel.is_set():
                break
            progress(f"Проверка {index} из {len(strategy_ids)}: {names.get(sid, sid)}")
            engine.start(sid, *game)
            score = _score(targets, cancel)
            report.results.append(StrategyResult(sid, names.get(sid, sid), score, len(targets)))
    finally:
        report.cancelled = cancel.is_set()
        if report.results:
            report.best = max(report.results, key=lambda r: r.score)
        if was_running:
            finished = all_mode and report.best is not None and not report.cancelled
            engine.start(report.best.id if finished else selected_id, *game)
        else:
            engine.stop()
    return report
