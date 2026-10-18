"""Настройки пользователя (settings.json в папке данных)."""
import json
import os

from . import paths

DEFAULTS = {
    "strategy": "general",
    "game_filter": False,
    "auto_update": True,
    "autostart": False,
    "close_to_tray": True,
    "lists_version": "",
    "last_check": "",
}


def load() -> dict:
    data = dict(DEFAULTS)
    try:
        stored = json.loads(paths.SETTINGS_FILE.read_text(encoding="utf-8"))
        if isinstance(stored, dict):
            data.update({k: v for k, v in stored.items() if k in DEFAULTS})
    except (OSError, json.JSONDecodeError):
        pass
    return data


def save(data: dict) -> None:
    paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = paths.SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, paths.SETTINGS_FILE)
