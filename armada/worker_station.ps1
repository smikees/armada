param([Parameter(Mandatory=$true)][string]$Config)
$ErrorActionPreference='Stop'
$cfg=Get-Content -LiteralPath $Config -Raw | ConvertFrom-Json
if($cfg.station -notmatch '^ArmadaWorker_[a-f0-9]{24}$'){throw 'Invalid private station name.'}
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class ArmadaStation {
 [StructLayout(LayoutKind.Sequential)] public struct SA {public int length; public IntPtr descriptor; public int inherit;}
 [DllImport("advapi32.dll", CharSet=CharSet.Unicode,SetLastError=true)] public static extern bool ConvertStringSecurityDescriptorToSecurityDescriptor(string s,uint revision,out IntPtr descriptor,IntPtr size);
 [DllImport("user32.dll", CharSet=CharSet.Unicode,SetLastError=true)] public static extern IntPtr CreateWindowStation(string name,uint flags,uint access,ref SA security);
 [DllImport("user32.dll",SetLastError=true)] public static extern bool SetProcessWindowStation(IntPtr station);
 [DllImport("user32.dll")] public static extern IntPtr GetProcessWindowStation();
 [DllImport("user32.dll", CharSet=CharSet.Unicode,SetLastError=true)] public static extern IntPtr CreateDesktop(string name,IntPtr device,IntPtr mode,uint flags,uint access,ref SA security);
 [DllImport("kernel32.dll")] public static extern IntPtr LocalFree(IntPtr memory);
 [DllImport("kernelbase.dll",CharSet=CharSet.Unicode,SetLastError=true)] public static extern bool DeriveCapabilitySidsFromName(string name,out IntPtr groups,out uint ng,out IntPtr caps,out uint nc);
 [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)] public static extern bool ConvertSidToStringSid(IntPtr sid,out IntPtr text);
 public static string DraftCapability() {
  IntPtr groups=IntPtr.Zero,caps=IntPtr.Zero,text=IntPtr.Zero;uint ng=0,nc=0;
  try {
   if(!DeriveCapabilitySidsFromName("lpacFileRead",out groups,out ng,out caps,out nc)||nc!=1)throw new InvalidOperationException("Draft capability unavailable.");
   if(!ConvertSidToStringSid(Marshal.ReadIntPtr(caps),out text))throw new InvalidOperationException("Draft capability conversion failed.");
   return Marshal.PtrToStringUni(text);
  } finally {
   if(text!=IntPtr.Zero)LocalFree(text);
   for(int i=0;i<ng;i++)LocalFree(Marshal.ReadIntPtr(groups,i*IntPtr.Size));
   for(int i=0;i<nc;i++)LocalFree(Marshal.ReadIntPtr(caps,i*IntPtr.Size));
   if(groups!=IntPtr.Zero)LocalFree(groups);if(caps!=IntPtr.Zero)LocalFree(caps);
  }
 }
}
'@
$descriptor=[IntPtr]::Zero
$draftSid=[ArmadaStation]::DraftCapability()
$sddl="D:P(A;;0xF037F;;;SY)(A;;0xF037F;;;$($cfg.owner_sid))(A;;0xF037F;;;$($cfg.sid))(A;;0x20327;;;$draftSid)"
if(-not [ArmadaStation]::ConvertStringSecurityDescriptorToSecurityDescriptor($sddl,1,[ref]$descriptor,[IntPtr]::Zero)){throw 'Could not describe the private station.'}
$sa=[ArmadaStation+SA]::new();$sa.length=[Runtime.InteropServices.Marshal]::SizeOf($sa);$sa.descriptor=$descriptor
# CWF_CREATE_ONLY: never change permissions on a pre-existing station.
$station=[ArmadaStation]::CreateWindowStation($cfg.station,1,0xF037F,[ref]$sa)
[ArmadaStation]::LocalFree($descriptor) | Out-Null
if($station -eq [IntPtr]::Zero){throw 'Could not create a new dedicated station.'}
$original=[ArmadaStation]::GetProcessWindowStation()
try{
 if(-not [ArmadaStation]::SetProcessWindowStation($station)){throw 'Could not select the dedicated station.'}
 $sddl="D:P(A;;0xF01FF;;;SY)(A;;0xF01FF;;;$($cfg.owner_sid))(A;;0xF01FF;;;$($cfg.sid))"
 if(-not [ArmadaStation]::ConvertStringSecurityDescriptorToSecurityDescriptor($sddl,1,[ref]$descriptor,[IntPtr]::Zero)){throw 'Could not describe the private desktop.'}
 $sa.descriptor=$descriptor
 $desktop=[ArmadaStation]::CreateDesktop('Agent',[IntPtr]::Zero,[IntPtr]::Zero,0,0xF01FF,[ref]$sa)
 [ArmadaStation]::LocalFree($descriptor) | Out-Null
 if($desktop -eq [IntPtr]::Zero){throw 'Could not create the dedicated desktop.'}
 $sddl="D:P(A;;0xF01FF;;;SY)(A;;0xF01FF;;;$($cfg.owner_sid))(A;;0x201FF;;;$draftSid)"
 if(-not [ArmadaStation]::ConvertStringSecurityDescriptorToSecurityDescriptor($sddl,1,[ref]$descriptor,[IntPtr]::Zero)){throw 'Could not describe the draft desktop.'}
 $sa.descriptor=$descriptor
 $draft=[ArmadaStation]::CreateDesktop('Draft',[IntPtr]::Zero,[IntPtr]::Zero,0,0xF01FF,[ref]$sa)
 [ArmadaStation]::LocalFree($descriptor) | Out-Null
 if($draft -eq [IntPtr]::Zero){throw 'Could not create the isolated draft desktop.'}
}finally{[ArmadaStation]::SetProcessWindowStation($original) | Out-Null}
# This fixed keeper has no listener, provider credentials, launch password or command
# channel. Windows ends it when this owner's interactive logon session ends.
while($true){Start-Sleep -Seconds 60}
