# Windows task runner mirroring the Makefile.  Usage: .\make.ps1 test
param([Parameter(Mandatory = $true)][string]$Target)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

function Invoke-InServer([string[]]$UvArgs) {
    Push-Location (Join-Path $root 'server')
    try { & uv @UvArgs; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } } finally { Pop-Location }
}

switch ($Target) {
    'setup'        { Invoke-InServer @('sync') }
    'test'         { Invoke-InServer @('run', 'pytest') }
    'lint'         { Invoke-InServer @('run', 'ruff', 'check', '.') }
    'secrets-scan' {
        Push-Location $root
        try { & uv run --project server python scripts/secret_scan.py; exit $LASTEXITCODE } finally { Pop-Location }
    }
    { $_ -in 'server', 'app', 'eval', 'db-reset' } { Write-Host "not built yet: $Target"; exit 1 }
    default        { Write-Host "unknown target: $Target"; exit 1 }
}
