param([Parameter(Mandatory=$true)][string]$InstallRoot,
      [Parameter(Mandatory=$true)][string]$Report)
$ErrorActionPreference = 'Stop'
# Read-only preflight. Never terminate an application or change an installed file.
try {
    if (Test-Path -LiteralPath $InstallRoot) {
        if ((Get-Item -LiteralPath $InstallRoot).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw 'Setup cannot replace a linked installation directory.'
        }
        foreach ($entry in Get-ChildItem -LiteralPath $InstallRoot -Force -Recurse -ErrorAction Stop) {
            if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Setup cannot replace a linked installation path: $($entry.FullName)"
            }
            if ($entry.PSIsContainer) { continue }
            # Inno's own uninstaller may be running; it is not part of our payload.
            if ($entry.DirectoryName -eq $InstallRoot -and $entry.Name -match '^unins[0-9]+\.(exe|dat|msg)$') { continue }
            $stream = $null
            try {
                $stream = [IO.File]::Open($entry.FullName, [IO.FileMode]::Open,
                    [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
            } catch {
                throw "Setup cannot replace this file yet: $($entry.FullName). Finish active work, quit ARMADA from its tray menu, and close any provider or browser helper still using it. Then retry Setup. No installed files have been changed."
            } finally { if ($null -ne $stream) { $stream.Dispose() } }
        }
    }
    [IO.File]::WriteAllText($Report, '', (New-Object Text.UTF8Encoding($false)))
    exit 0
} catch {
    [IO.File]::WriteAllText($Report, $_.Exception.Message, (New-Object Text.UTF8Encoding($false)))
    exit 1
}
