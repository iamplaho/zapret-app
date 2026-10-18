"""Работа с Windows: права администратора, автозапуск, единственный экземпляр, сообщения."""
import ctypes
import subprocess
import sys

TASK_NAME = "zapret-app-autostart"
CREATE_NO_WINDOW = 0x08000000
ERROR_ALREADY_EXISTS = 183
MB_ICONINFORMATION = 0x40

_mutex_handle = None  # храним ссылку, чтобы мьютекс жил всё время работы


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def acquire_single_instance() -> bool:
    """True, если это первый экземпляр приложения."""
    global _mutex_handle
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    except (AttributeError, OSError):
        return True
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    _mutex_handle = kernel32.CreateMutexW(None, False, "Local\\zapret-app-single-instance")
    return ctypes.get_last_error() != ERROR_ALREADY_EXISTS


def show_message(text: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(0, text, "zapret-app", MB_ICONINFORMATION)
    except (AttributeError, OSError):
        print(text)


def _run(args) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, capture_output=True, text=True, errors="replace", creationflags=CREATE_NO_WINDOW
    )


def autostart_enabled() -> bool:
    try:
        return _run(["schtasks", "/Query", "/TN", TASK_NAME]).returncode == 0
    except OSError:
        return False


def set_autostart(enabled: bool) -> None:
    if enabled:
        if not getattr(sys, "frozen", False):
            raise RuntimeError("Автозапуск работает только в собранной версии (exe).")
        # Запуск с --autostart: приложение стартует в трее и сразу включает обход.
        # RL HIGHEST запускает задачу с правами администратора без окна UAC.
        task_run = f'\\"{sys.executable}\\" --autostart'
        cmd = f'schtasks /Create /TN "{TASK_NAME}" /TR "{task_run}" /SC ONLOGON /RL HIGHEST /F'
        result = subprocess.run(
            cmd, capture_output=True, text=True, errors="replace", creationflags=CREATE_NO_WINDOW
        )
    else:
        result = _run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip() or "Ошибка планировщика задач")
