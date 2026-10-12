param([ValidateRange(1,65535)][int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$TailscalePath = Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'
if (-not (Test-Path -LiteralPath $TailscalePath)) {
    $TailscalePath = (Get-Command tailscale -ErrorAction Stop).Source
}
$TailnetStatus = (& $TailscalePath status --json | ConvertFrom-Json)
if ($TailnetStatus.BackendState -ne 'Running') {
    throw 'Connect this PC to Tailscale before enabling Folio HTTPS.'
}
Write-Output 'Enabling private HTTPS for Folio. This does not enable public Funnel access.'
Write-Output 'If an admin link is displayed, enable Serve/HTTPS there and return to this command.'
& $TailscalePath serve --bg --yes "http://127.0.0.1:$Port"
if ($LASTEXITCODE -ne 0) { throw 'Tailscale Serve setup did not complete.' }
& $TailscalePath serve status
