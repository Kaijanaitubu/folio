param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$RootDirectory = $PSScriptRoot
# Explorer/startup tasks can inherit an older environment after a user setting
# changes. Read the persisted backup destination when this process has none.
if (-not $env:MEDIA_BACKUPS) {
    $SavedBackupDirectory = [Environment]::GetEnvironmentVariable('MEDIA_BACKUPS', 'User')
    if ($SavedBackupDirectory) { $env:MEDIA_BACKUPS = $SavedBackupDirectory }
}
$RuntimePath = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path -LiteralPath $RuntimePath)) {
    $RuntimePath = (Get-Command python -ErrorAction Stop).Source
}
$DataDirectory = Join-Path $RootDirectory 'data'
New-Item -ItemType Directory -Path $DataDirectory -Force | Out-Null
$PidFile = Join-Path $DataDirectory 'server.pid'
if (Test-Path -LiteralPath $PidFile) {
    $RecordedProcessId = [int](Get-Content -LiteralPath $PidFile -Raw)
    $ExistingProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $RecordedProcessId" -ErrorAction SilentlyContinue
    if ($ExistingProcess -and $ExistingProcess.CommandLine.Contains((Join-Path $RootDirectory 'server.py'))) {
        Write-Output "Folio is already running at http://localhost:$Port"
        exit 0
    }
}
$Arguments = @(('"' + (Join-Path $RootDirectory 'server.py') + '"'), '--host', '0.0.0.0', '--port', "$Port")
$PortListener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($PortListener) { throw "Port $Port is already in use. Stop the running server before starting Folio." }
$LibraryProcess = Start-Process -FilePath $RuntimePath -ArgumentList $Arguments -WorkingDirectory $RootDirectory -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $DataDirectory 'server.log') -RedirectStandardError (Join-Path $DataDirectory 'server-error.log')
$LibraryProcess.Id | Set-Content -LiteralPath $PidFile
Write-Output "Folio started: http://localhost:$Port (process $($LibraryProcess.Id))"
