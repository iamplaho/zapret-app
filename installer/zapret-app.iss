; Скрипт установщика Inno Setup 6.
; Сборка: ISCC.exe /DAppVersion=0.2.0 installer\zapret-app.iss
; Нужна папка dist\zapret-app, которую создаёт PyInstaller (zapret-app.spec).

#ifndef AppVersion
  #define AppVersion "0.2.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\zapret-app"
#endif

[Setup]
AppId={{B3F1C7E2-5A4D-4C8B-9E21-7F0D2A6C9B11}
AppName=zapret-app
AppVersion={#AppVersion}
AppVerName=zapret-app {#AppVersion}
AppPublisher=zapret-app contributors
AppPublisherURL=https://github.com/flowseal/zapret-discord-youtube
DefaultDirName={autopf}\zapret-app
DefaultGroupName=zapret-app
DisableProgramGroupPage=yes
OutputDir=..\installer-output
OutputBaseFilename=zapret-app-setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\zapret-app.exe
UninstallDisplayName=zapret-app
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
LicenseFile=..\LICENSE.txt
VersionInfoProductName=zapret-app

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать значок на рабочем столе"; GroupDescription: "Дополнительно:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\zapret-app"; Filename: "{app}\zapret-app.exe"
Name: "{group}\Удалить zapret-app"; Filename: "{uninstallexe}"
Name: "{autodesktop}\zapret-app"; Filename: "{app}\zapret-app.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\zapret-app.exe"; Description: "Запустить zapret-app"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Убираем задачу автозапуска. Ошибка, если задачи нет, не должна мешать удалению.
Filename: "{cmd}"; Parameters: "/c schtasks /Delete /TN zapret-app-autostart /F >nul 2>&1 & exit /b 0"; Flags: runhidden; RunOnceId: "RemoveAutostart"

[Code]
procedure StopBypass();
var
  ResultCode: Integer;
begin
  // Процесс winws.exe живёт отдельно от приложения и блокирует файлы — останавливаем его.
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM winws.exe /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopBypass();
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  StopBypass();
  Result := True;
end;
