# Clean-machine test of the installer (launch plan 5.2 / 5.10), run INSIDE Windows Sandbox.
# tools/sandbox_test.py starts the sandbox with dist\ mapped read-only at C:\armada-dist and a results
# folder mapped writable at C:\armada-results, then runs this script at logon.
#
# Install silently → check what landed → open the app and screenshot it → check the welcome page →
# uninstall → check the program folder is gone and ~\.armada is kept → reinstall and leave ARMADA
# open, so whoever is watching can click around a machine that has never seen it.
$ErrorActionPreference = 'Continue'
$out = 'C:\armada-results'
$log = Join-Path $out 'report.txt'
Set-Content $log "ARMADA clean-machine test  $(Get-Date -Format s)"
function Say($ok, $what) { $m = ('{0}  {1}' -f ($(if ($ok) { 'PASS' } else { 'FAIL' })), $what); Add-Content $log $m }
function Note($what) { Add-Content $log "      $what" }

$setup = Get-ChildItem 'C:\armada-dist\ARMADA-Setup-*.exe' | Sort-Object LastWriteTime | Select-Object -Last 1
Note "installer: $($setup.Name)  ($([math]::Round($setup.Length/1MB,1)) MB)"
Note "Windows: $((Get-CimInstance Win32_OperatingSystem).Caption) $((Get-CimInstance Win32_OperatingSystem).Version)"
$wv = (Get-ItemProperty 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}' -ErrorAction SilentlyContinue).pv
Note "WebView2 runtime: $(if ($wv) { $wv } else { 'not installed' })"
Note "Claude Code on PATH: $([bool](Get-Command claude -ErrorAction SilentlyContinue))"

# 1. install, silently, with both tasks
$t0 = Get-Date
$p = Start-Process $setup.FullName -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/TASKS="desktopicon,scheduler"',"/LOG=`"$out\setup.log`"" -Wait -PassThru
Say ($p.ExitCode -eq 0) "installer exit code $($p.ExitCode) in $([int]((Get-Date)-$t0).TotalSeconds)s"
$wv2 = (Get-ItemProperty 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}' -ErrorAction SilentlyContinue).pv
if (-not $wv2) { $wv2 = (Get-ItemProperty 'HKCU:\Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}' -ErrorAction SilentlyContinue).pv }
Say ([bool]$wv2) "WebView2 runtime present after install: $wv2"
$app = Join-Path $env:LOCALAPPDATA 'Programs\ARMADA'
Say (Test-Path "$app\python\pythonw.exe") "private Python at $app\python"
Say (Test-Path "$app\armada\__init__.py") "app package installed"
Say (Test-Path "$app\installed.json") "installed.json marker (the updater's 'this is an install')"
Say (Test-Path "$app\armada\support_key.txt") "Report-an-issue send key shipped"
Say (Test-Path "$app\licenses") "third-party licences shipped"
$lnk = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\ARMADA.lnk'
Say (Test-Path $lnk) "Start menu shortcut"
Say (Test-Path (Join-Path ([Environment]::GetFolderPath('Desktop')) 'ARMADA.lnk')) "desktop shortcut"
$run = (Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -ErrorAction SilentlyContinue).'ARMADA Scheduler'
Say ([bool]$run) "scheduler starts at sign-in: $run"

# 2. the bundled Python runs the app
$py = & "$app\python\python.exe" -c "import sys, armada, webview; from armada import updater; print(armada.__version__, updater.installed(), sys.executable)" 2>&1
Say ($LASTEXITCODE -eq 0) "bundled Python imports ARMADA: $py"

# 3. open it the way the shortcut does, then look
Start-Process "$app\python\pythonw.exe" -ArgumentList '-m','armada','app' -WorkingDirectory $app
if ($wv2) {
  $page = $null
  for ($i = 0; $i -lt 60 -and -not $page; $i++) {
    Start-Sleep 2
    try { $page = (Invoke-WebRequest 'http://127.0.0.1:8756/' -UseBasicParsing -TimeoutSec 3).Content } catch {}
  }
  Say ([bool]$page) "the app answers on 127.0.0.1:8756"
  Say ($page -match 'Welcome|welcome') "first run lands on the welcome page"
  Start-Sleep 8
  $win = Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle }
  Say ([bool]$win) "a window is open: '$($win.MainWindowTitle -join ', ')'"
} else {
  # No WebView2 (a silent install can't ask for the admin rights it needs here): the app must say
  # so in plain words rather than open a broken Internet Explorer window.
  $win = $null
  for ($i = 0; $i -lt 20 -and -not $win; $i++) {
    Start-Sleep 2
    $win = Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like '*cannot start*' }
  }
  Say ([bool]$win) "without WebView2 the app explains instead of opening a broken window: '$($win.MainWindowTitle)'"
  Say (-not (Get-NetTCPConnection -LocalPort 8756 -State Listen -ErrorAction SilentlyContinue)) "and leaves no server running behind the message"
}
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
[System.Drawing.Graphics]::FromImage($bmp).CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
$bmp.Save("$out\first-run.png"); Note "screenshot: first-run.png"
Say (Test-Path "$env:USERPROFILE\.armada") "~\.armada created by the first run"
Get-Content "$env:USERPROFILE\.armada\logs\armada.log" -ErrorAction SilentlyContinue | Select-Object -Last 15 | ForEach-Object { Note "log: $_" }

# 4. uninstall: the program goes, the user's data stays
$un = Get-ChildItem "$app\unins*.exe" | Select-Object -First 1
$p = Start-Process $un.FullName -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',"/LOG=`"$out\uninstall.log`"" -Wait -PassThru
# The uninstaller hands itself off to a copy in %TEMP% and returns at once; wait for that copy.
for ($i = 0; $i -lt 60 -and (Get-Process -Name '_iu*' -ErrorAction SilentlyContinue); $i++) { Start-Sleep 1 }
Start-Sleep 3
Get-Process python,pythonw -ErrorAction SilentlyContinue | ForEach-Object { Note "still running: $($_.Name) $($_.Id) $($_.Path)" }
Say ($p.ExitCode -eq 0) "uninstaller exit code $($p.ExitCode)"
Say (-not (Get-Process pythonw -ErrorAction SilentlyContinue)) "ARMADA's processes were stopped"
Say (-not (Test-Path "$app\armada") -and -not (Test-Path "$app\python")) "program folder removed"
Say (-not (Test-Path $lnk)) "Start menu shortcut removed"
$run = (Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -ErrorAction SilentlyContinue).'ARMADA Scheduler'
Say (-not $run) "sign-in entry removed"
Say (Test-Path "$env:USERPROFILE\.armada") "~\.armada kept (the user's data)"

# 5. reinstall and leave it open for a human to try
$p = Start-Process $setup.FullName -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/TASKS="desktopicon,scheduler"',"/LOG=`"$out\reinstall.log`"" -Wait -PassThru
Say ($p.ExitCode -eq 0) "reinstall after uninstalling"
Start-Process "$app\python\pythonw.exe" -ArgumentList '-m','armada','app' -WorkingDirectory $app
Add-Content $log 'DONE'
