@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [1/3] Установка зависимостей...
python -m pip install -r requirements.txt pyinstaller || goto :error

echo [2/3] Сборка приложения (PyInstaller)...
python -m PyInstaller --noconfirm --clean zapret-app.spec || goto :error

echo [3/3] Сборка установщика (нужен Inno Setup 6)...
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" (
  "%ISCC%" installer\zapret-app.iss || goto :error
  echo Установщик: installer-output\zapret-app-setup-*.exe
) else (
  echo Inno Setup 6 не найден — установщик пропущен. Портативная версия: dist\zapret-app\zapret-app.exe
)
pause
exit /b 0

:error
echo.
echo Сборка не удалась. Проверьте, что установлен Python 3.10+ с PATH.
pause
exit /b 1
