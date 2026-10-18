"""Запуск и остановка обхода: процесс winws.exe или служба Windows «zapret»."""
import subprocess
import time

from . import paths, strategies

CREATE_NO_WINDOW = 0x08000000
PROCESS_NAME = "winws.exe"
SERVICE_NAME = "zapret"
MAX_LOG_BYTES = 2 * 1024 * 1024


def _run(args) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, errors="replace",
                          creationflags=CREATE_NO_WINDOW)


def _sc(*args) -> subprocess.CompletedProcess:
    return _run(["sc", *args])


def is_running() -> bool:
    out = _run(["tasklist", "/FI", f"IMAGENAME eq {PROCESS_NAME}", "/NH"]).stdout
    return PROCESS_NAME.lower() in out.lower()


def service_installed() -> bool:
    return _sc("query", SERVICE_NAME).returncode == 0


def service_running() -> bool:
    return "RUNNING" in _sc("query", SERVICE_NAME).stdout


def _kill_process() -> None:
    _run(["taskkill", "/F", "/IM", PROCESS_NAME, "/T"])


def _binpath(args: list[str]) -> str:
    return subprocess.list2cmdline([str(paths.WINWS_EXE), *args])


def _rotate_log() -> None:
    try:
        if paths.WINWS_LOG_FILE.stat().st_size > MAX_LOG_BYTES:
            paths.WINWS_LOG_FILE.unlink()
    except OSError:
        pass


def sync_service(strategy: str, mode: str, tcp: str, udp: str) -> bool:
    """Обновляет параметры службы (если она установлена). Не запускает её."""
    if not service_installed():
        return False
    args = strategies.winws_args(strategy, mode, tcp, udp)
    res = _sc("config", SERVICE_NAME, "binPath=", _binpath(args))
    if res.returncode != 0:
        raise RuntimeError(res.stdout.strip() or res.stderr.strip() or "не удалось обновить службу")
    return True


def install_service(strategy: str, mode: str, tcp: str, udp: str) -> bool:
    """Ставит службу Windows: обход стартует сам при загрузке системы."""
    if not paths.WINWS_EXE.exists():
        raise FileNotFoundError(f"Не найден файл {paths.WINWS_EXE}")
    args = strategies.winws_args(strategy, mode, tcp, udp)
    _kill_process()
    if service_installed():
        _sc("stop", SERVICE_NAME)
        time.sleep(1)
        _sc("delete", SERVICE_NAME)
        time.sleep(1)
    res = _sc("create", SERVICE_NAME, "binPath=", _binpath(args),
              "start=", "auto", "DisplayName=", "zapret")
    if res.returncode != 0:
        raise RuntimeError(res.stdout.strip() or res.stderr.strip() or "не удалось создать службу")
    _sc("description", SERVICE_NAME, "Обход блокировок Discord и YouTube (zapret-app)")
    _sc("start", SERVICE_NAME)
    time.sleep(2)
    return service_running() or is_running()


def remove_service() -> bool:
    """Удаляет службу zapret и драйвер WinDivert, как «Remove Services» в оригинале."""
    _kill_process()
    if service_installed():
        _sc("stop", SERVICE_NAME)
        time.sleep(1)
        _sc("delete", SERVICE_NAME)
    for name in ("WinDivert", "WinDivert14"):
        _sc("stop", name)
        _sc("delete", name)
    return True


def start(strategy: str, mode: str, tcp: str, udp: str) -> bool:
    """Запускает обход. True, если он работает через пару секунд."""
    if not paths.WINWS_EXE.exists():
        raise FileNotFoundError(f"Не найден файл {paths.WINWS_EXE}")
    if service_installed():
        _kill_process()
        sync_service(strategy, mode, tcp, udp)
        _sc("start", SERVICE_NAME)
        time.sleep(1.5)
        return is_running() or service_running()
    _kill_process()
    args = strategies.winws_args(strategy, mode, tcp, udp)
    _rotate_log()
    with open(paths.WINWS_LOG_FILE, "a", encoding="utf-8") as log:
        subprocess.Popen(
            [str(paths.WINWS_EXE), *args],
            cwd=str(paths.BIN_DIR),
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=CREATE_NO_WINDOW,
        )
    time.sleep(1.5)
    return is_running()


def stop() -> None:
    if service_installed():
        _sc("stop", SERVICE_NAME)
    _kill_process()
