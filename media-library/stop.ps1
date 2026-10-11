$ErrorActionPreference = 'Stop'
$PidFile = Join-Path $PSScriptRoot 'data\server.pid'
if (-not (Test-Path -LiteralPath $PidFile)) { Write-Output 'No recorded Folio process.'; exit 0 }
$RecordedProcessId = [int](Get-Content -LiteralPath $PidFile -Raw)
$LibraryProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $RecordedProcessId" -ErrorAction SilentlyContinue
if ($LibraryProcess -and $LibraryProcess.CommandLine.Contains((Join-Path $PSScriptRoot 'server.py'))) {
    Stop-Process -Id $RecordedProcessId
    Write-Output 'Folio stopped.'
} else {
    Write-Output 'The recorded Folio process is no longer running.'
}
Remove-Item -LiteralPath $PidFile
