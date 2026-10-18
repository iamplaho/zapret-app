"""Запуск, остановка и проверка процесса winws.exe."""
import subprocess
import time

from . import paths, strategies

CREATE_NO_WINDOW = 0x08000000
PROCESS_NAME = "winws.exe"
MAX_LOG_BYTES = 2 * 1024 * 1024


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, capture_output=True, text=True, errors="replace", creationflags=CREATE_NO_WINDOW
    )


def is_running() -> bool:
    out = _run(["tasklist", "/FI", f"IMAGENAME eq {PROCESS_NAME}", "/NH"]).stdout
    return PROCESS_NAME.lower() in out.lower()


def stop() -> None:
    _run(["taskkill", "/F", "/IM", PROCESS_NAME, "/T"])


def _rotate_log() -> None:
    try:
        if paths.WINWS_LOG_FILE.stat().st_size > MAX_LOG_BYTES:
            paths.WINWS_LOG_FILE.unlink()
    except OSError:
        pass


def start(strategy_id: str, game_filter: bool) -> bool:
    """Запускает обход. Возвращает True, если процесс жив через пару секунд."""
    if not paths.WINWS_EXE.exists():
        raise FileNotFoundError(f"Не найден файл {paths.WINWS_EXE}")
    stop()
    argv = strategies.build_argv(strategy_id, game_filter)
    _rotate_log()
    with open(paths.WINWS_LOG_FILE, "a", encoding="utf-8") as log:
        subprocess.Popen(
            [str(paths.WINWS_EXE), *argv],
            cwd=str(paths.BIN_DIR),
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=CREATE_NO_WINDOW,
        )
    time.sleep(1.5)
    return is_running()
