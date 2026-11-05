param([Parameter(Mandatory=$true)][string]$InstallRoot,
      [Parameter(Mandatory=$true)][string]$Manifest,
      [Parameter(Mandatory=$true)][string]$Report)
$ErrorActionPreference = 'Stop'
function FileDigest([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose(); $stream.Dispose() }
}
try {
    $root = [IO.Path]::GetFullPath($InstallRoot).TrimEnd('\') + '\'
    $inventory = Get-Content -LiteralPath $Manifest -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($inventory.format -ne 1 -or @($inventory.files).Count -eq 0) { throw 'Invalid installer inventory.' }
    foreach ($file in $inventory.files) {
        $target = [IO.Path]::GetFullPath((Join-Path $root $file.path))
        if (-not $target.StartsWith($root, [StringComparison]::OrdinalIgnoreCase) -or
            $file.sha256 -notmatch '^[a-f0-9]{64}$') { throw 'Invalid installer inventory path or hash.' }
        if (-not (Test-Path -LiteralPath $target -PathType Leaf) -or
            (FileDigest $target) -ne $file.sha256) {
            throw "Setup could not verify $($file.path). A required file is missing or different. Close applications using ARMADA files and run Setup again; do not skip files."
        }
    }
    [IO.File]::WriteAllText($Report, '', (New-Object Text.UTF8Encoding($false)))
    exit 0
} catch {
    [IO.File]::WriteAllText($Report, $_.Exception.Message, (New-Object Text.UTF8Encoding($false)))
    exit 1
}
