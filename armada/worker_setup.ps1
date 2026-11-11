param([Parameter(Mandatory=$true)][string]$Request)
$ErrorActionPreference='Stop'
$cfg=Get-Content -LiteralPath $Request -Raw | ConvertFrom-Json
trap {
 $cfg | Add-Member -NotePropertyName setup_error -NotePropertyValue $_.Exception.Message -Force
 $cfg | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Request -Encoding UTF8
 exit 1
}
$principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Account setup needs elevation.'}
if($cfg.username -notmatch '^ArmadaW_[a-f0-9]{8}$'){throw 'Invalid worker account.'}
$existing=Get-LocalUser -Name $cfg.username -ErrorAction SilentlyContinue
if($existing -and $existing.SID.Value -ne $cfg.sid){throw 'Refusing to reuse an unrelated Windows account.'}
Add-Type -AssemblyName System.Security
$bytes=[Security.Cryptography.ProtectedData]::Unprotect([Convert]::FromBase64String($cfg.password),$null,[Security.Cryptography.DataProtectionScope]::CurrentUser)
$secret=[Text.Encoding]::UTF8.GetString($bytes) | ConvertTo-SecureString -AsPlainText -Force
[Array]::Clear($bytes,0,$bytes.Length)
$account=if($existing){$existing}else{New-LocalUser -Name $cfg.username -Password $secret -AccountNeverExpires -PasswordNeverExpires -UserMayNotChangePassword -Description 'ARMADA isolated agent worker'}
$sid=$account.SID.Value
$cfg | Add-Member -NotePropertyName sid -NotePropertyValue $sid -Force
$cfg | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Request -Encoding UTF8
$users=Get-LocalGroup -SID 'S-1-5-32-545'
if(-not @(Get-LocalGroupMember -Group $users | Where-Object SID -eq $sid).Count){Add-LocalGroupMember -Group $users -Member $account}
# Do not retain any unexpected privileged group membership.
$groups=Get-LocalGroup | Where-Object { @(Get-LocalGroupMember -Group $_ -ErrorAction SilentlyContinue | Where-Object SID -eq $sid).Count -gt 0 }
if(@($groups | Where-Object SID -ne 'S-1-5-32-545').Count){throw 'The worker must belong only to Users.'}
Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class ArmadaProfile {
 [DllImport("userenv.dll", CharSet=CharSet.Unicode)] public static extern int CreateProfile(string sid,string user,StringBuilder path,uint size);
}
'@
$profile=[Text.StringBuilder]::new(260)
$profileKey="HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\$sid"
if(Test-Path -LiteralPath $profileKey){$homePath=(Get-ItemProperty -LiteralPath $profileKey).ProfileImagePath}
else{
 $hr=[ArmadaProfile]::CreateProfile($sid,$cfg.username,$profile,260)
 if($hr -ne 0){throw ('Could not create the worker profile. HRESULT '+$hr)}
 $homePath=$profile.ToString()
}
function Set-PrivateFolder([string]$Path,[bool]$WorkerWrite){
 New-Item -ItemType Directory -Path $Path -Force | Out-Null
 $acl=[Security.AccessControl.DirectorySecurity]::new()
 $acl.SetAccessRuleProtection($true,$false)
 foreach($identity in @($cfg.owner_sid,'S-1-5-18','S-1-5-32-544')){
  $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($identity),'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
 }
 $rights=if($WorkerWrite){'FullControl'}else{'ReadAndExecute'}
 $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($account.SID,$rights,'ContainerInherit,ObjectInherit','None','Allow'))
 if(-not $WorkerWrite){
  $denyWrites=[Security.AccessControl.FileSystemRights]::Write -bor [Security.AccessControl.FileSystemRights]::Delete -bor [Security.AccessControl.FileSystemRights]::DeleteSubdirectoriesAndFiles -bor [Security.AccessControl.FileSystemRights]::ChangePermissions -bor [Security.AccessControl.FileSystemRights]::TakeOwnership
  $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($account.SID,$denyWrites,'ContainerInherit,ObjectInherit','None','Deny'))
 }
 Set-Acl -LiteralPath $Path -AclObject $acl
}
Set-PrivateFolder $cfg.root $false
Set-PrivateFolder $homePath $true
$launches=Join-Path $cfg.root 'launches'
Set-PrivateFolder $launches $false
$bootstrap=Join-Path $cfg.root 'worker_bootstrap.py'
Copy-Item -LiteralPath $cfg.bootstrap_source -Destination $bootstrap -Force
Copy-Item -LiteralPath (Join-Path (Split-Path -Parent $cfg.bootstrap_source) 'worker_terminal.py') -Destination (Join-Path $cfg.root 'worker_terminal.py') -Force
Copy-Item -LiteralPath (Join-Path (Split-Path -Parent $cfg.bootstrap_source) 'worker_console.py') -Destination (Join-Path $cfg.root 'worker_console.py') -Force
$stationScript=Join-Path $cfg.root 'worker_station.ps1'
if(Get-ScheduledTask -TaskName $cfg.station_task -ErrorAction SilentlyContinue){Stop-ScheduledTask -TaskName $cfg.station_task}
Copy-Item -LiteralPath (Join-Path (Split-Path -Parent $cfg.bootstrap_source) 'worker_station.ps1') -Destination $stationScript -Force
$stationConfig=Join-Path $cfg.root 'station.json'
@{station=$cfg.station;sid=$sid;owner_sid=$cfg.owner_sid} | ConvertTo-Json | Set-Content -LiteralPath $stationConfig -Encoding UTF8
$taskAction=New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "'+$stationScript+'" -Config "'+$stationConfig+'"')
$taskPrincipal=New-ScheduledTaskPrincipal -UserId $cfg.owner_sid -LogonType Interactive -RunLevel Highest
$taskTrigger=New-ScheduledTaskTrigger -AtLogOn -User $cfg.owner_sid
$taskSettings=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName $cfg.station_task -Action $taskAction -Principal $taskPrincipal -Trigger $taskTrigger -Settings $taskSettings -Force | Out-Null
Start-ScheduledTask -TaskName $cfg.station_task
foreach($path in $cfg.protected_roots){
 if(Test-Path -LiteralPath $path){
  & "$env:SystemRoot\System32\icacls.exe" $path /deny "*${sid}:(OI)(CI)F" | Out-Null
  if($LASTEXITCODE){throw 'Could not protect owner credentials.'}
 }
}
foreach($path in $cfg.runtime_roots){
 & "$env:SystemRoot\System32\icacls.exe" $path /grant:r "*${sid}:(OI)(CI)RX" | Out-Null
 if($LASTEXITCODE){throw 'Could not share a runtime read-only.'}
 & "$env:SystemRoot\System32\icacls.exe" $path /deny "*${sid}:(OI)(CI)(WD,AD,WEA,WA,DE,DC,WDAC,WO)" | Out-Null
 if($LASTEXITCODE){throw 'Could not protect a shared runtime.'}
}
# No ancestor ACLs are changed. Owner-side verification rejects activation when
# trusted application/control locations could be replaced by the worker.
# The worker can load installed Armada MCP bridge code but cannot alter the app,
# update/signing code or source repository. It never receives write access here.
& "$env:SystemRoot\System32\icacls.exe" $cfg.app_root /grant:r "*${sid}:(OI)(CI)RX" | Out-Null
if($LASTEXITCODE){throw 'Could not share the public application code read-only.'}
& "$env:SystemRoot\System32\icacls.exe" $cfg.app_root /deny "*${sid}:(OI)(CI)(WD,AD,WEA,WA,DE,DC,WDAC,WO)" | Out-Null
if($LASTEXITCODE){throw 'Could not protect the application.'}
foreach($path in $cfg.previous_roots){
 if($path -notin $cfg.allowed_roots -and (Test-Path -LiteralPath $path)){
  & "$env:SystemRoot\System32\icacls.exe" $path /remove:g "*$sid" | Out-Null
  if($LASTEXITCODE){throw 'Could not remove a previous worker folder grant.'}
 }
}
foreach($path in $cfg.allowed_roots){
 if(-not (Test-Path -LiteralPath $path -PathType Container)){throw 'A worker folder disappeared.'}
 & "$env:SystemRoot\System32\icacls.exe" $path /grant:r "*${sid}:(OI)(CI)M" | Out-Null
 if($LASTEXITCODE){throw 'Could not share a worker folder.'}
}
New-Item -ItemType Directory -Path (Join-Path $homePath '.codex'),(Join-Path $homePath '.claude'),(Join-Path $homePath 'AppData\Local\Temp') -Force | Out-Null
$cfg | Add-Member -NotePropertyName sid -NotePropertyValue $sid -Force
$cfg | Add-Member -NotePropertyName home -NotePropertyValue $homePath -Force
$cfg | Add-Member -NotePropertyName launches -NotePropertyValue $launches -Force
$cfg | Add-Member -NotePropertyName bootstrap -NotePropertyValue $bootstrap -Force
$temporary=$Request+'.setup.tmp'
$cfg | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $temporary -Encoding UTF8
Move-Item -LiteralPath $temporary -Destination $Request -Force
exit 0
