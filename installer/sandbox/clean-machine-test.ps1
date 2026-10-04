# Clean-machine test of the installer (launch plan 5.2 / 5.10), run INSIDE Windows Sandbox.
# tools/sandbox_test.py starts the sandbox with dist\ mapped read-only at C:\armada-dist and a results
# folder mapped writable at C:\armada-results, then runs this script at logon.
#
# Install silently → check what landed → open the app and screenshot it → check the welcome page →
# uninstall → check the program folder is gone and ~\.armada is kept → reinstall and verify the
# existing realm, then shut down the disposable VM after saving evidence.
param([Parameter(Mandatory=$true)][string]$InstallerName)
if ($env:USERNAME -ne 'WDAGUtilityAccount' -or -not (Test-Path 'C:\armada-results')) { throw 'Run only inside the configured Windows Sandbox' }
$ErrorActionPreference = 'Continue'
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
$out = 'C:\armada-results'
$log = Join-Path $out 'report.txt'
Set-Content $log "ARMADA clean-machine test  $(Get-Date -Format s)"
function Say($ok, $what) { $m = ('{0}  {1}' -f ($(if ($ok) { 'PASS' } else { 'FAIL' })), $what); Add-Content $log $m }
function Note($what) { Add-Content $log "      $what" }
function SaveDependencyLogs {
  $locations = @("$env:ALLUSERSPROFILE\Microsoft\EdgeUpdate\Log\MicrosoftEdgeUpdate.log",
    "$env:LOCALAPPDATA\Temp\MicrosoftEdgeUpdate.log", "$env:WINDIR\Temp\msedge_installer.log",
    "$env:LOCALAPPDATA\Temp\msedge_installer.log")
  $index = 0
  foreach ($location in $locations) {
    $index++
    if (Test-Path -LiteralPath $location) { Copy-Item -LiteralPath $location -Destination "$out\webview-$index.log" }
  }
}

$setup = Get-Item -LiteralPath (Join-Path 'C:\armada-dist' $InstallerName)
Note ('SHA256: ' + (Get-FileHash -LiteralPath $setup.FullName -Algorithm SHA256).Hash.ToLower())
Note "installer: $($setup.Name)  ($([math]::Round($setup.Length/1MB,1)) MB)"
Note "Windows: $((Get-CimInstance Win32_OperatingSystem).Caption) $((Get-CimInstance Win32_OperatingSystem).Version)"
$wv = (Get-ItemProperty 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}' -ErrorAction SilentlyContinue).pv
Note "WebView2 runtime: $(if ($wv) { $wv } else { 'not installed' })"
Note "Claude Code on PATH: $([bool](Get-Command claude -ErrorAction SilentlyContinue))"
if (-not $wv -and (Test-Path 'C:\armada-redist\MicrosoftEdgeWebView2RuntimeInstallerX64.exe')) {
  # Optional offline dependency avoids relying on the bootstrapper's download service in the VM.
  $offline = 'C:\armada-redist\MicrosoftEdgeWebView2RuntimeInstallerX64.exe'
  $signature = Get-AuthenticodeSignature -LiteralPath $offline
  if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') { throw 'Invalid WebView2 publisher' }
  $localInstaller = Join-Path $env:TEMP 'MicrosoftEdgeWebView2RuntimeInstallerX64.exe'
  Copy-Item -LiteralPath $offline -Destination $localInstaller
  Note "VM free disk bytes: $((Get-PSDrive C).Free)"
  $dependency = Start-Process -WindowStyle Hidden -Verb RunAs $localInstaller -ArgumentList '/silent','/install' -Wait -PassThru
  Note "standalone WebView2 installer exit: $($dependency.ExitCode)"
  SaveDependencyLogs
}

# 1. install silently
$t0 = Get-Date
$p = Start-Process -WindowStyle Hidden $setup.FullName -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/TASKS="desktopicon"',"/LOG=`"$out\setup.log`"" -Wait -PassThru
Say ($p.ExitCode -eq 0) "installer exit code $($p.ExitCode) in $([int]((Get-Date)-$t0).TotalSeconds)s"
$wv2 = (Get-ItemProperty 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}' -ErrorAction SilentlyContinue).pv
if (-not $wv2) { $wv2 = (Get-ItemProperty 'HKCU:\Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}' -ErrorAction SilentlyContinue).pv }
if (-not $wv2) {
  # Sandbox has a machine Edge updater: exercise the same elevated dependency install offered by
  # the interactive installer. This is confined to the disposable VM, never the host machine.
  $bootstrap = 'C:\armada-redist\MicrosoftEdgeWebview2Setup.exe'
  $signature = Get-AuthenticodeSignature -LiteralPath $bootstrap
  if ($signature.Status -eq 'Valid' -and $signature.SignerCertificate.Subject -match 'O=Microsoft Corporation') {
    $dependency = Start-Process -WindowStyle Hidden -Verb RunAs $bootstrap -ArgumentList '/silent','/install' -Wait -PassThru
    Note "elevated WebView2 bootstrapper exit: $($dependency.ExitCode)"
    $wv2 = (Get-ItemProperty 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}' -ErrorAction SilentlyContinue).pv
  }
}
Say ([bool]$wv2) "WebView2 runtime present after install: $wv2"
SaveDependencyLogs
$app = Join-Path $env:LOCALAPPDATA 'Programs\ARMADA'
Say (Test-Path "$app\python\pythonw.exe") "private Python at $app\python"
Say (Test-Path "$app\python\ARMADA.exe") "branded ARMADA launcher installed"
Say (Test-Path "$app\armada\__init__.py") "app package installed"
Say (Test-Path "$app\installed.json") "installed.json marker (the updater's 'this is an install')"
Say (-not (Test-Path "$app\armada\support_key.txt")) "No report sending key in the client"
Say (Test-Path "$app\armada_bootstrap.py") "Stable update-recovery bootstrap installed"
Say (Test-Path "$app\licenses") "third-party licences shipped"
$lnk = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\ARMADA.lnk'
Say (Test-Path $lnk) "Start menu shortcut"
Say (Test-Path (Join-Path ([Environment]::GetFolderPath('Desktop')) 'ARMADA.lnk')) "desktop shortcut"
$run = (Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -ErrorAction SilentlyContinue).'ARMADA Scheduler'
Say (-not $run) "scheduler does not start independently at sign-in"

# 2. the bundled Python runs the app
$py = & "$app\python\python.exe" -c "import sys, armada, webview; from armada import updater; print(armada.__version__, updater.installed(), sys.executable)" 2>&1
Say ($LASTEXITCODE -eq 0) "bundled Python imports ARMADA: $py"
$tz = & "$app\python\python.exe" -c "from zoneinfo import ZoneInfo; from datetime import datetime; assert datetime(2026,10,3,12,tzinfo=ZoneInfo('UTC')).astimezone(ZoneInfo('America/New_York')).hour == 8; print('New York timezone verified')" 2>&1
Say ($LASTEXITCODE -eq 0) "bundled timezone data: $tz"

# 3. open it the way the shortcut does, then look
Start-Process -WindowStyle Hidden "$app\python\ARMADA.exe" -ArgumentList '-m','armada','app' -WorkingDirectory $app
if ($wv2) {
  $page = $null
  for ($i = 0; $i -lt 60 -and -not $page; $i++) {
    Start-Sleep 2
    try {
      $auth = Get-Content -LiteralPath "$env:USERPROFILE\.armada\local-auth\8756.json" -Raw | ConvertFrom-Json
      $page = (Invoke-WebRequest 'http://127.0.0.1:8756/' -Headers @{Authorization=('Bearer ' + $auth.token)} -UseBasicParsing -TimeoutSec 3).Content
    } catch {}
  }
  Say ([bool]$page) "the authenticated app answers on 127.0.0.1:8756"
  $rejected = $false
  try { Invoke-WebRequest 'http://127.0.0.1:8756/api/instance' -UseBasicParsing -TimeoutSec 3 | Out-Null }
  catch { $rejected = ([int]$_.Exception.Response.StatusCode -eq 401) }
  Say $rejected "unauthenticated API requests are rejected"
  Say ($page -match 'Welcome|welcome') "first run lands on the welcome page"
  Start-Sleep 8
  $win = Get-Process ARMADA -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle }
  Say ([bool]$win) "a window is open: '$($win.MainWindowTitle -join ', ')'"
  Say ([bool]$win -and $win.ProcessName -eq 'ARMADA') "Task Manager process name is ARMADA"
} else {
  # No WebView2 (a silent install can't ask for the admin rights it needs here): the app must say
  # so in plain words rather than open a broken Internet Explorer window.
  $win = $null
  for ($i = 0; $i -lt 20 -and -not $win; $i++) {
    Start-Sleep 2
    $win = Get-Process ARMADA -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like '*cannot start*' }
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
if ($wv2) {
  $probe = & "$app\python\python.exe" 'C:\armada-test\realm-probe.py' create 2>&1
  $probe | ForEach-Object { Note "probe: $_" }
  Say ($LASTEXITCODE -eq 0) 'setup services, first command job and browser authentication'
}

# 4. uninstall: the program goes, the user's data stays
$un = Get-ChildItem "$app\unins*.exe" | Select-Object -First 1
$p = Start-Process -WindowStyle Hidden $un.FullName -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',"/LOG=`"$out\uninstall.log`"" -Wait -PassThru
# The uninstaller hands itself off to a copy in %TEMP% and returns at once; wait for that copy.
for ($i = 0; $i -lt 60 -and (Get-Process -Name '_iu*' -ErrorAction SilentlyContinue); $i++) { Start-Sleep 1 }
Start-Sleep 3
Get-Process python,pythonw,ARMADA -ErrorAction SilentlyContinue | ForEach-Object { Note "still running: $($_.Name) $($_.Id) $($_.Path)" }
Say ($p.ExitCode -eq 0) "uninstaller exit code $($p.ExitCode)"
Say (-not (Get-Process ARMADA -ErrorAction SilentlyContinue)) "ARMADA's processes were stopped"
Say (-not (Test-Path "$app\armada") -and -not (Test-Path "$app\python")) "program folder removed"
Say (-not (Test-Path $lnk)) "Start menu shortcut removed"
$run = (Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -ErrorAction SilentlyContinue).'ARMADA Scheduler'
Say (-not $run) "sign-in entry removed"
Say (Test-Path "$env:USERPROFILE\.armada") "~\.armada kept (the user's data)"

# 5. reinstall and verify the existing realm
$p = Start-Process -WindowStyle Hidden $setup.FullName -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/TASKS="desktopicon"',"/LOG=`"$out\reinstall.log`"" -Wait -PassThru
Say ($p.ExitCode -eq 0) "reinstall after uninstalling"
Start-Process -WindowStyle Hidden "$app\python\ARMADA.exe" -ArgumentList '-m','armada','app' -WorkingDirectory $app
if ($wv2) {
  $probe = & "$app\python\python.exe" 'C:\armada-test\realm-probe.py' reopen 2>&1
  $probe | ForEach-Object { Note "probe: $_" }
  Say ($LASTEXITCODE -eq 0) 'existing realm reopens after reinstall'
}
Add-Content $log 'DONE'
Start-Process -WindowStyle Hidden shutdown.exe -ArgumentList '/s','/t','10'
