; ARMADA — Windows installer (launch plan 5.2, ADR-009). Compiled by tools/build_installer.py:
;   ISCC /DAppVersion=<version> /DStage=<build\installer\ARMADA> /O<dist> installer\armada.iss
;
; Per-user, no admin: installs to %LOCALAPPDATA%\Programs\ARMADA. The payload is the staged folder:
;   python\          the python.org embeddable Python + the pinned packages (ADR-009)
;   armada\          the app — the one folder the updater (5.4) replaces
;   installed.json   the marker that makes the updater treat this as an installed copy
;   licenses\, LICENSE, THIRD_PARTY_NOTICES.md, armada.ico
; Never touches ~\.armada or any realm: those are the user's, and survive uninstalling.

#ifndef AppVersion
  #error Pass /DAppVersion=<version> (tools/build_installer.py does)
#endif
#ifndef Stage
  #define Stage "..\build\installer\ARMADA"
#endif
#ifndef Redist
  #define Redist "..\build\installer\redist"
#endif

#define AppName "ARMADA"
; Must match armada/app.py's _APP_ID: the Start-menu shortcut carrying it is what lets Windows show
; ARMADA's own name and icon on its notifications and taskbar button.
#define AppUserModelID "Stamih.ARMADA.App"
#define PyW "{app}\python\pythonw.exe"

[Setup]
AppId={{C7FEBEB8-88A6-442A-B1EB-22BD3E9D2BCD}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion} (beta)
AppPublisher=Mihai Stanculescu
AppPublisherURL=https://github.com/smikees/armada
AppSupportURL=mailto:armada@stamih.com
AppUpdatesURL=https://github.com/smikees/armada/releases
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
UsedUserAreasWarning=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Windows 10 1809, the oldest Windows Claude Code supports.
MinVersion=10.0.17763
LicenseFile={#Stage}\LICENSE
SetupIconFile={#Stage}\armada.ico
UninstallDisplayIcon={app}\armada.ico
UninstallDisplayName={#AppName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
OutputBaseFilename=ARMADA-Setup-{#AppVersion}
; We stop ARMADA's own processes ourselves (StopArmada below); Restart Manager would ask about every
; python.exe on the machine.
CloseApplications=no

[Messages]
FinishedLabel=ARMADA is installed. It will guide you through choosing a folder for your realms the first time it opens.

[Tasks]
Name: "desktopicon"; Description: "Put an ARMADA shortcut on the desktop"
Name: "scheduler"; Description: "Run scheduled jobs in the background when I sign in to Windows (recommended)"

[InstallDelete]
; A clean program folder each time: the updater may have replaced armada\ since the last install,
; and a stale python\ could keep a package this version no longer ships.
Type: filesandordirs; Name: "{app}\armada"
Type: filesandordirs; Name: "{app}\armada.staged"
Type: filesandordirs; Name: "{app}\armada.staging-tmp"
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\licenses"

[Files]
Source: "{#Stage}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Microsoft's WebView2 bootstrapper, unpacked (and run, below) only when the runtime is missing.
; Without WebView2 the window falls back to Internet Explorer's engine and can't draw the app.
Source: "{#Redist}\MicrosoftEdgeWebview2Setup.exe"; Flags: dontcopy

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{#PyW}"; Parameters: "-m armada app"; WorkingDir: "{app}"; \
  IconFilename: "{app}\armada.ico"; AppUserModelID: "{#AppUserModelID}"; Comment: "Your standing team of AI agents"
Name: "{autodesktop}\{#AppName}"; Filename: "{#PyW}"; Parameters: "-m armada app"; WorkingDir: "{app}"; \
  IconFilename: "{app}\armada.ico"; Comment: "Your standing team of AI agents"; Tasks: desktopicon

[Registry]
; The scheduler at sign-in (moved here from 5.5): jobs keep running after a reboot without the window
; being opened. With no realm yet it exits straight away; the window starts it once there is one.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
  ValueName: "ARMADA Scheduler"; ValueData: """{#PyW}"" -m armada schedule --engine claude"; \
  Flags: uninsdeletevalue; Tasks: scheduler
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; \
  ValueName: "ARMADA Scheduler"; Flags: deletevalue; Tasks: not scheduler

[Run]
Filename: "{#PyW}"; Parameters: "-m armada app"; WorkingDir: "{app}"; Description: "Open ARMADA now"; \
  Flags: postinstall nowait skipifsilent

[UninstallDelete]
; What the app and the updater created after install. ~\.armada and the realms are not here, on purpose.
Type: filesandordirs; Name: "{app}\armada"
Type: filesandordirs; Name: "{app}\armada.staged"
Type: filesandordirs; Name: "{app}\armada.previous"
Type: filesandordirs; Name: "{app}\armada.staging-tmp"
Type: filesandordirs; Name: "{app}\python"
Type: dirifempty; Name: "{app}"

[Code]
const
  WebView2Client = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function HasVersion(Root: Integer; Key: String): Boolean;
var
  V: String;
begin
  Result := RegQueryStringValue(Root, Key, 'pv', V) and (V <> '') and (V <> '0.0.0.0');
end;

{ Microsoft's documented check: a "pv" version under EdgeUpdate\Clients, machine-wide or per user. }
function WebView2Installed(): Boolean;
begin
  Result := HasVersion(HKLM32, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + WebView2Client)
    or HasVersion(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\' + WebView2Client);
end;

{ ARMADA finds Claude Code on the PATH, like a terminal would. }
function ClaudeFound(): Boolean;
var
  P: String;
begin
  P := GetEnv('PATH');
  Result := (FileSearch('claude.exe', P) <> '') or (FileSearch('claude.cmd', P) <> '')
    or FileExists(ExpandConstant('{%USERPROFILE}\.local\bin\claude.exe'));
end;

{ Stop ARMADA's own window and scheduler — only processes running this install's Python, never any
  other Python on the machine — so their files can be replaced or removed. }
procedure StopArmada(Dir: String);
var
  Rc: Integer;
begin
  if not DirExists(Dir) then
    Exit;
  Log('Stopping ARMADA processes running from ' + Dir);
  Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    '-NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "' +
    'Get-Process python,pythonw -ErrorAction SilentlyContinue | ' +
    'Where-Object { $_.Path -and $_.Path.StartsWith(''' + Dir + '\python\'', ''OrdinalIgnoreCase'') } | ' +
    'Stop-Process -Force; Start-Sleep -Milliseconds 500"',
    '', SW_HIDE, ewWaitUntilTerminated, Rc);
  Log('Stop exit code: ' + IntToStr(Rc));
end;

{ WebView2, when it's missing (rare on Windows 11; possible on Windows 10 or a trimmed image).
  Microsoft's bootstrapper installs it for this user, without admin rights, unless the machine has
  a machine-wide Edge updater, in which case it must go in for all users, and that needs admin rights
  (seen in Windows Sandbox: error 0x80040902 unelevated). So: try quietly first; if it's still
  missing, ask, and run it again with Windows' admin prompt. A silent install can't ask, so it leaves
  the app to explain (it refuses to open without WebView2 and says where to get it). }
procedure InstallWebView2();
var
  Exe: String;
  Rc: Integer;
begin
  if WebView2Installed() then
    Exit;
  ExtractTemporaryFile('MicrosoftEdgeWebview2Setup.exe');
  Exe := ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe');
  WizardForm.StatusLabel.Caption := 'Installing Microsoft Edge WebView2 (ARMADA''s window uses it)...';
  Exec(Exe, '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, Rc);
  Log('WebView2 bootstrapper (this user): exit code ' + IntToStr(Rc));
  if WebView2Installed() or WizardSilent() then
    Exit;
  if MsgBox('ARMADA''s window needs Microsoft Edge WebView2, a free part of Windows from Microsoft. ' +
      'On this computer it has to be installed for all users, so Windows will ask you to allow it.' + #13#10#13#10 +
      'Install it now?', mbConfirmation, MB_YESNO) = IDYES then
  begin
    if ShellExec('runas', Exe, '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, Rc) then
      Log('WebView2 bootstrapper (all users): exit code ' + IntToStr(Rc))
    else
      Log('WebView2 bootstrapper (all users): not started, error ' + IntToStr(Rc));
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    InstallWebView2();
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopArmada(ExpandConstant('{app}'));
  Result := '';
end;

procedure CurPageChanged(CurPageID: Integer);
var
  Notes: String;
begin
  if CurPageID = wpFinished then
  begin
    Notes := '';
    if not WebView2Installed() then
      Notes := Notes + #13#10#13#10 + 'One thing first: ARMADA''s window needs Microsoft Edge WebView2, ' +
        'and it isn''t installed yet (it needs the internet, and on some computers permission to ' +
        'install for all users). It''s free from Microsoft: ' +
        'https://developer.microsoft.com/microsoft-edge/webview2/';
    if not ClaudeFound() then
      Notes := Notes + #13#10#13#10 + 'ARMADA runs your agents through Claude Code, which isn''t installed yet. ' +
        'Install it (https://code.claude.com/docs/en/setup) and sign in with your own Claude account; ' +
        'ARMADA picks it up when it next starts, and shows you how to sign in.';
    if Notes <> '' then
      WizardForm.FinishedLabel.Caption := WizardForm.FinishedLabel.Caption + Notes;
  end;
end;

function InitializeUninstall(): Boolean;
begin
  StopArmada(ExpandConstant('{app}'));
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent() then
    MsgBox('ARMADA has been removed. Your realms and your settings folder (.armada in your user folder) ' +
      'were left exactly as they were, so reinstalling picks up where you left off. Delete them yourself ' +
      'if you don''t want them any more.', mbInformation, MB_OK);
end;
