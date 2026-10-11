param([int]$Port = 8765, [string]$ListenAddress = '0.0.0.0')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$BundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (Test-Path -LiteralPath $BundledPython) {
    & $BundledPython server.py --host $ListenAddress --port $Port
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 server.py --host $ListenAddress --port $Port
} else {
    python server.py --host $ListenAddress --port $Port
}
