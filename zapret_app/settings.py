"""Настройки пользователя (settings.json в папке данных)."""
import json
import os

from . import paths

DEFAULTS = {
    "strategy": "general",
    "game_mode": "off",          # off | all | tcp | udp
    "game_tcp": "1024-65535",
    "game_udp": "1024-65535",
    "auto_update": True,         # обновление списков
    "auto_update_app": True,     # обновление самой программы
    "autostart": False,
    "close_to_tray": True,
    "resume_bypass": False,      # включить обход после перезапуска (нужно для обновления)
    "lists_version": "",
    "last_check": "",
}


def load() -> dict:
    data = dict(DEFAULTS)
    try:
        stored = json.loads(paths.SETTINGS_FILE.read_text(encoding="utf-8"))
        if isinstance(stored, dict):
            # старая настройка game_filter=true переходит в режим «TCP и UDP»
            if "game_mode" not in stored and stored.get("game_filter"):
                stored["game_mode"] = "all"
            data.update({k: v for k, v in stored.items() if k in DEFAULTS})
    except (OSError, json.JSONDecodeError):
        pass
    return data


def save(data: dict) -> None:
    paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = paths.SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, paths.SETTINGS_FILE)
