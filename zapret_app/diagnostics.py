"""Диагностика системы: аналог «Run Diagnostics» и «Check Status» из service.bat."""
import subprocess
from dataclasses import dataclass

from . import engine, paths

CREATE_NO_WINDOW = 0x08000000
PROXY_KEY = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
CONFLICT_SERVICES = ["GoodbyeDPI", "discordfix_zapret", "winws1", "winws2"]
KEYWORD_WARNINGS = [
    ("Killer", "Найдены службы Killer. Они могут мешать обходу"),
    ("Intel", "Найдены службы Intel Connectivity. Они могут мешать обходу"),
    ("TracSrvWrapper", "Найдена служба TracSrvWrapper (Trace Sensor). Она может мешать обходу"),
    ("EPWD", "Найдена служба EPWD (Check Point). Она может мешать обходу"),
    ("SmartByte", "Найдена служба SmartByte. Она может мешать обходу"),
]


@dataclass
class Check:
    level: str  # ok | warn | error | info
    text: str


def _run(args) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, errors="replace",
                          creationflags=CREATE_NO_WINDOW)


def parse_services(text: str) -> list:
    """Разбирает вывод «sc query» в список пар (служба, отображаемое имя)."""
    services = []
    name = None
    for line in text.splitlines():
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith("SERVICE_NAME:"):
            name = stripped.split(":", 1)[1].strip()
        elif upper.startswith("DISPLAY_NAME:") and name is not None:
            services.append((name, stripped.split(":", 1)[1].strip()))
            name = None
    return services


def proxy_enabled(reg_output: str) -> bool:
    return "0x1" in reg_output


def tcp_timestamps_enabled(netsh_output: str) -> bool:
    for line in netsh_output.lower().splitlines():
        if "timestamps" in line and "enabled" in line:
            return True
    return False


def run_checks() -> list:
    checks = [Check("info", f"Папка программы: {paths.BASE_DIR}")]

    bfe = _run(["sc", "query", "BFE"]).stdout
    if "RUNNING" in bfe:
        checks.append(Check("ok", "Служба фильтрации (BFE) работает"))
    else:
        checks.append(Check("error", "Служба BFE не запущена. Без неё обход не работает"))

    proxy = _run(["reg", "query", PROXY_KEY, "/v", "ProxyEnable"]).stdout
    if proxy_enabled(proxy):
        checks.append(Check("warn", "Включён системный прокси. Проверьте, нужен ли он вам"))
    else:
        checks.append(Check("ok", "Системный прокси выключен"))

    timestamps = _run(["netsh", "interface", "tcp", "show", "global"]).stdout
    if tcp_timestamps_enabled(timestamps):
        checks.append(Check("ok", "TCP timestamps включены"))
    else:
        _run(["netsh", "interface", "tcp", "set", "global", "timestamps=enabled"])
        checks.append(Check("ok", "TCP timestamps были выключены, программа их включила"))

    if (paths.BIN_DIR / "WinDivert64.sys").exists():
        checks.append(Check("ok", "Драйвер WinDivert64.sys на месте"))
    else:
        checks.append(Check("error", "Не найден файл bin\\WinDivert64.sys. Переустановите программу"))

    active = parse_services(_run(["sc", "query"]).stdout)
    names = {s.lower() for s, _ in active}
    conflicts = [c for c in CONFLICT_SERVICES if c.lower() in names]
    if conflicts:
        checks.append(Check("error", "Конфликтующие службы: " + ", ".join(conflicts)
                            + ". Их нужно удалить или остановить"))
    else:
        checks.append(Check("ok", "Конфликтующих служб не найдено"))

    if "AdguardSvc.exe" in _run(["tasklist", "/FI", "IMAGENAME eq AdguardSvc.exe"]).stdout:
        checks.append(Check("warn", "Запущен Adguard. Он может мешать обходу"))

    for keyword, message in KEYWORD_WARNINGS:
        if any(keyword.lower() in f"{s} {d}".lower() for s, d in active):
            checks.append(Check("warn", message))

    vpn = [d for s, d in active if "vpn" in f"{s} {d}".lower()]
    if vpn:
        checks.append(Check("warn", "Запущены VPN-службы: " + ", ".join(vpn) + ". Они могут мешать обходу"))

    running = engine.is_running()
    if "WinDivert" in names and not running:
        checks.append(Check("warn", "Драйвер WinDivert запущен без обхода. Удалите службы в разделе «Сервис»"))
    checks.append(Check("info", "Обход работает" if running else "Обход сейчас не запущен"))
    return checks


def service_report() -> list:
    installed = engine.service_installed()
    lines = []
    if installed:
        state = "работает" if engine.service_running() else "остановлена"
        lines.append(f"Служба zapret: установлена, {state}")
    else:
        lines.append("Служба zapret: не установлена")
    lines.append("winws.exe: запущен" if engine.is_running() else "winws.exe: не запущен")
    lines.append("WinDivert64.sys: " + ("есть" if (paths.BIN_DIR / "WinDivert64.sys").exists() else "НЕТ"))
    return lines
