"""Стратегии обхода: чтение runtime/strategies.json и сборка аргументов winws.exe.

Игровой фильтр и порты работают так же, как в оригинале (service.bat):
режим off/all/tcp/udp; в выключенном порту ставится значение 12.
"""
import json
import os
import re
import shlex

from . import paths

GAME_OFF = "12"
MODES = ("off", "all", "tcp", "udp")
RANGE_RE = re.compile(r"^(\d{1,5})-(\d{1,5})$")


def load_all() -> list[dict]:
    data = json.loads(paths.STRATEGIES_FILE.read_text(encoding="utf-8"))
    return data["strategies"]


def get(strategy_id: str) -> dict:
    for item in load_all():
        if item["id"] == strategy_id:
            return item
    raise KeyError(f"Стратегия не найдена: {strategy_id}")


def valid_range(text: str) -> bool:
    match = RANGE_RE.match(text.strip())
    if not match:
        return False
    start, end = int(match.group(1)), int(match.group(2))
    return 1 <= start <= end <= 65535


def game_ports(mode: str, tcp_range: str, udp_range: str) -> tuple:
    """Возвращает (порты TCP, порты UDP) для %GameFilterTCP% и %GameFilterUDP%."""
    if mode == "all":
        return tcp_range, udp_range
    if mode == "tcp":
        return tcp_range, GAME_OFF
    if mode == "udp":
        return GAME_OFF, udp_range
    return GAME_OFF, GAME_OFF


def build_argv(strategy_id: str, tcp_ports: str = GAME_OFF, udp_ports: str = GAME_OFF) -> list[str]:
    """Список аргументов winws.exe (без имени самого exe)."""
    template = get(strategy_id)["args"]
    replacements = {
        "%BIN%": str(paths.BIN_DIR) + os.sep,
        "%LISTS%": str(paths.LISTS_DIR) + os.sep,
        "%GameFilterTCP%": tcp_ports,
        "%GameFilterUDP%": udp_ports,
    }
    argv = []
    # Сначала разбираем шаблон, потом подставляем пути — пробелы в путях не ломают аргументы.
    for token in shlex.split(template):
        for placeholder, value in replacements.items():
            token = token.replace(placeholder, value)
        argv.append(token)
    return argv


def winws_args(strategy_id: str, mode: str, tcp_range: str, udp_range: str) -> list[str]:
    return build_argv(strategy_id, *game_ports(mode, tcp_range, udp_range))
