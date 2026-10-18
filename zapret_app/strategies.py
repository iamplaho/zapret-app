"""Стратегии обхода: загрузка из runtime/strategies.json и сборка аргументов для winws.exe."""
import json
import os
import shlex

from . import paths

GAME_PORTS = "1024-65535"
GAME_PORTS_OFF = "12"  # то же значение, что использует оригинальный service.bat


def load_all() -> list[dict]:
    data = json.loads(paths.STRATEGIES_FILE.read_text(encoding="utf-8"))
    return data["strategies"]


def get(strategy_id: str) -> dict:
    for item in load_all():
        if item["id"] == strategy_id:
            return item
    raise KeyError(f"Стратегия не найдена: {strategy_id}")


def build_argv(strategy_id: str, game_filter: bool) -> list[str]:
    """Возвращает список аргументов для winws.exe (без имени самого exe)."""
    template = get(strategy_id)["args"]
    ports = GAME_PORTS if game_filter else GAME_PORTS_OFF
    replacements = {
        "%BIN%": str(paths.BIN_DIR) + os.sep,
        "%LISTS%": str(paths.LISTS_DIR) + os.sep,
        "%GameFilterTCP%": ports,
        "%GameFilterUDP%": ports,
    }
    argv = []
    # Сначала разбираем шаблон, потом подставляем пути — так пробелы в путях не ломают аргументы.
    for token in shlex.split(template):
        for placeholder, value in replacements.items():
            token = token.replace(placeholder, value)
        argv.append(token)
    return argv
