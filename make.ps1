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
        $zip = Join-Path $dir 'vosk-en.zip'
        Invoke-WebRequest 'https://alphacephei.com/vosk/models/vosk-model-small-en-in-0.4.zip' -OutFile $zip
        Expand-Archive $zip -DestinationPath $dir -Force; Remove-Item $zip
    }
    'server' {
        Write-Host 'Open http://localhost:8000 on this laptop'
        Invoke-InServer @('run', 'uvicorn', 'app.main:app_factory', '--factory', '--host', '127.0.0.1', '--port', '8000')
    }
    'phone' {
        Push-Location $root
        try { & uv run --project server python scripts/make_cert.py } finally { Pop-Location }
        Invoke-InServer @('run', 'uvicorn', 'app.main:app_factory', '--factory', '--host', '0.0.0.0', '--port', '8443',
            '--ssl-keyfile', 'data/certs/key.pem', '--ssl-certfile', 'data/certs/cert.pem')
    }
    'phone-usb' {
        # Phone on USB: it opens http://localhost:8000, which browsers treat as secure, so the microphone,
        # offline start (service worker) and "Install app" all work. No certificate warning, no Wi-Fi needed.
        Write-Host @'
Phone over USB (Android + Chrome):
  1. Phone: Settings > About phone > tap "Build number" 7 times; then Developer options > USB debugging ON.
  2. Connect the USB cable and allow debugging on the phone.
  3. Laptop Chrome or Edge: open chrome://inspect/#devices (edge://inspect/#devices)
     > "Port forwarding..." > add 8000 -> localhost:8000 > tick "Enable port forwarding" > Done.
     (Or, with Android platform-tools: adb reverse tcp:8000 tcp:8000)
  4. Phone Chrome: open http://localhost:8000  (keep the inspect tab open on the laptop)
  5. Phone Chrome menu > "Add to Home screen / Install app" for an app icon.
'@
        Invoke-InServer @('run', 'uvicorn', 'app.main:app_factory', '--factory', '--host', '127.0.0.1', '--port', '8000')
    }
    'db-reset' {
        Remove-Item (Join-Path $root 'server\data\aura.db') -ErrorAction SilentlyContinue
        Remove-Item (Join-Path $root 'server\data\audio\*') -ErrorAction SilentlyContinue
        Write-Host 'Demo database and audio cleared'
    }
    'apk' {
        # Android app (mobile/, Capacitor): bundles server/app/web into a debug APK. Needs Node + Android SDK.
        $jbr = 'C:\Program Files\Android\Android Studio\jbr'
        if (Test-Path $jbr) { $env:JAVA_HOME = $jbr }
        Push-Location (Join-Path $root 'mobile')
        try {
            if (-not (Test-Path 'node_modules')) { & npm ci; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
            & node copy-web.mjs; & npx cap sync android; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            Push-Location 'android'
            try { & .\gradlew.bat testDebugUnitTest assembleDebug; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } } finally { Pop-Location }
            Write-Host "APK: mobile\android\app\build\outputs\apk\debug\app-debug.apk"
        } finally { Pop-Location }
    }
    'apk-run' {
        # Install the APK on a phone on USB, forward port 8000, and start the server. The app talks to
        # http://localhost:8000 = this laptop (change it on the login screen or in Settings for Wi-Fi).
        $adb = Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe'
        $apk = Join-Path $root 'mobile\android\app\build\outputs\apk\debug\app-debug.apk'
        if (-not (Test-Path $apk)) { Write-Host 'No APK yet: run .\make.ps1 apk first'; exit 1 }
        & $adb install -r $apk; if ($LASTEXITCODE -ne 0) { Write-Host 'Phone not found: enable USB debugging and allow this laptop'; exit 1 }
        & $adb reverse tcp:8000 tcp:8000
        Write-Host 'Installed. Open "A.U.R.A." on the phone. Server starting on http://localhost:8000 ...'
        Invoke-InServer @('run', 'uvicorn', 'app.main:app_factory', '--factory', '--host', '127.0.0.1', '--port', '8000')
    }
    'apk-wifi' {
        # Server for the Android app over Wi-Fi (plain http, synthetic demo data only). In the app set the
        # server to this laptop's Wi-Fi address, e.g. 192.168.1.5:8000. Allow Windows Firewall if asked.
        Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
            ForEach-Object { Write-Host ("App server address: {0}:8000" -f $_.IPAddress) }
        Invoke-InServer @('run', 'uvicorn', 'app.main:app_factory', '--factory', '--host', '0.0.0.0', '--port', '8000')
    }
    'app' { Write-Host 'Android app: .\make.ps1 apk (build) then .\make.ps1 apk-run (install on a USB phone)'; exit 1 }
    default        { Write-Host "unknown target: $Target"; exit 1 }
}
