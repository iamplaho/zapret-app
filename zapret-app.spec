# -*- mode: python ; coding: utf-8 -*-
# Сборка: pyinstaller --noconfirm --clean zapret-app.spec
import os
from PyInstaller.utils.hooks import collect_all

ROOT = SPECPATH  # noqa: F821  (переменная, которую PyInstaller задаёт сам)

datas = [
    (os.path.join(ROOT, "runtime"), "runtime"),
    (os.path.join(ROOT, "assets"), "assets"),
]
binaries = []
hiddenimports = ["pystray._win32"]

ctk_datas, ctk_binaries, ctk_hidden = collect_all("customtkinter")
datas += ctk_datas
binaries += ctk_binaries
hiddenimports += ctk_hidden

a = Analysis(  # noqa: F821
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["matplotlib", "numpy", "pandas"],
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="zapret-app",
    console=False,            # без чёрного окна консоли
    uac_admin=True,           # запрос прав администратора при запуске
    icon=os.path.join(ROOT, "assets", "icon.ico"),
)
coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    name="zapret-app",
)
