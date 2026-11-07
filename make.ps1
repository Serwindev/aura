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
    'eval' {
        Push-Location $root
        try {
            $env:PYTHONIOENCODING = 'utf-8'
            & uv run --project server python eval/harness.py --notes eval/data/notes.yaml --out eval/results/latest/dev
            & uv run --project server python eval/harness.py --notes eval/data/notes_holdout.yaml --out eval/results/latest/holdout
        } finally { Pop-Location }
    }
    'models' {
        $dir = Join-Path $root 'server\models'; New-Item -ItemType Directory -Force $dir | Out-Null
        $zip = Join-Path $dir 'vosk-hi.zip'
        Invoke-WebRequest 'https://alphacephei.com/vosk/models/vosk-model-small-hi-0.22.zip' -OutFile $zip
        Expand-Archive $zip -DestinationPath $dir -Force; Remove-Item $zip
    }
    { $_ -in 'server', 'app', 'db-reset' } { Write-Host "not built yet: $Target"; exit 1 }
    default        { Write-Host "unknown target: $Target"; exit 1 }
}
