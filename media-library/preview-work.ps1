param([int]$Port = 8766)
$ErrorActionPreference = 'Stop'
if ($Port -lt 1 -or $Port -gt 65535) { throw 'Choose a port between 1 and 65535.' }
$previewStatic = Join-Path $PSScriptRoot 'static'
$previewPython = (Get-Command python -ErrorAction Stop).Source
Write-Host "Folio preview: http://localhost:$Port/prototypes/work/"
Write-Host 'Static preview only. No Folio server, database or import jobs are started.'
Write-Host 'Press Ctrl+C to stop. If the port is busy, reuse the existing preview or choose -Port.'
& $previewPython -m http.server $Port --bind 127.0.0.1 --directory $previewStatic
