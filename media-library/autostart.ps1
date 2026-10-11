param([switch]$Disable, [ValidateRange(1,65535)][int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$StartupFolder = [Environment]::GetFolderPath('Startup')
if (-not $StartupFolder) { throw 'Windows could not locate your Startup folder.' }
$ShortcutPath = Join-Path $StartupFolder 'Folio Personal Media Library.lnk'
$LauncherPath = Join-Path $PSScriptRoot 'start-hidden.vbs'
$HostPath = Join-Path $env:SystemRoot 'System32\wscript.exe'
$ShortcutShell = New-Object -ComObject WScript.Shell
if (Test-Path -LiteralPath $ShortcutPath) {
    $ExistingShortcut = $ShortcutShell.CreateShortcut($ShortcutPath)
    if ($ExistingShortcut.TargetPath -ne $HostPath -or -not $ExistingShortcut.Arguments.Contains(('"' + $LauncherPath + '"'))) {
        throw 'A different Folio startup shortcut already exists. It has been left unchanged.'
    }
}
if ($Disable) {
    if (Test-Path -LiteralPath $ShortcutPath) { Remove-Item -LiteralPath $ShortcutPath }
    Write-Output 'Folio automatic startup disabled. The currently running server is unchanged.'
    exit 0
}
if (-not (Test-Path -LiteralPath $HostPath) -or -not (Test-Path -LiteralPath $LauncherPath)) {
    throw 'The hidden startup launcher is unavailable.'
}
New-Item -ItemType Directory -Path $StartupFolder -Force | Out-Null
$Shortcut = $ShortcutShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $HostPath
$Shortcut.Arguments = ('"' + $LauncherPath + '" ' + $Port)
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.Description = "Start the local Folio server silently at Windows sign-in (port $Port)."
$Shortcut.Save()
Write-Output "Folio will start automatically when you sign into Windows: $ShortcutPath"
