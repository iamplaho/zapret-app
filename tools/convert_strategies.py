#!/usr/bin/env python3
"""Конвертирует стратегии (.bat) из оригинального репозитория в runtime/strategies.json.

Использование:
    python tools/convert_strategies.py <папка_оригинального_репозитория> <файл_вывода>

Пример:
    python tools/convert_strategies.py ../zapret-discord-youtube runtime/strategies.json
"""
import json
import re
import sys
from pathlib import Path

PLACEHOLDERS = {"%BIN%", "%LISTS%", "%GameFilterTCP%", "%GameFilterUDP%"}


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1251"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def extract_args(text: str):
    """Возвращает строку аргументов winws.exe из .bat-файла."""
    joined = re.sub(r"\^\r?\n", " ", text)  # склеиваем строки с продолжением '^'
    for line in joined.splitlines():
        low = line.lower()
        idx = low.find("winws.exe")
        if idx == -1 or "start" not in low:
            continue
        rest = line[idx + len("winws.exe"):].strip()
        if rest.startswith('"'):
            rest = rest[1:]
        return " ".join(rest.split())
    return None


def make_id(stem: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")


def natural_key(path: Path):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", path.stem.lower())]


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    repo, out = Path(sys.argv[1]), Path(sys.argv[2])
    strategies = []
    for bat in sorted(repo.glob("general*.bat"), key=natural_key):
        args = extract_args(read_text(bat))
        if not args:
            print(f"ПРОПУСК {bat.name}: не найдена команда winws.exe")
            continue
        unknown = set(re.findall(r"%[^%\s\"]+%", args)) - PLACEHOLDERS
        if unknown:
            print(f"ВНИМАНИЕ {bat.name}: неизвестные переменные {sorted(unknown)}")
        for rel in re.findall(r"%BIN%([^\"\s]+)", args):
            if not (repo / "bin" / rel).exists():
                print(f"ВНИМАНИЕ {bat.name}: нет файла bin/{rel}")
        strategies.append({"id": make_id(bat.stem), "name": bat.stem, "args": args})

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"source": "flowseal/zapret-discord-youtube", "strategies": strategies},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Готово: {len(strategies)} стратегий -> {out}")


if __name__ == "__main__":
    main()
