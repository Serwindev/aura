# A.U.R.A. Android app (`mobile/`)

Native Android shell (Capacitor 7) around the mobile web app in `server/app/web` — one source for both. Decision: `docs/decisions/004-android-app.md` (D-35). Autofill: `docs/decisions/003-autofill.md` (D-34 step 3).

## Build and run
```powershell
.\make.ps1 apk        # copies server/app/web -> mobile/www, cap sync, JVM tests, debug APK
.\make.ps1 apk-run    # phone on USB: install APK, adb reverse 8000, start the server
.\make.ps1 apk-wifi   # or: server on 0.0.0.0:8000; set the laptop address in the app (login screen / Settings)
```
APK: `mobile/android/app/build/outputs/apk/debug/app-debug.apk`. Needs Node 20+, Android SDK (API 35), JDK 21 (Android Studio's `jbr` is picked up).

## What is native
| Piece | Where |
|---|---|
| Microphone permission (WebView recording) | `AndroidManifest.xml` (RECORD_AUDIO, MODIFY_AUDIO_SETTINGS) |
| Share form text / report files (PDF, XLSX) | `@capacitor/share`, `AuraAutofillPlugin.shareFile` |
| Autofill service + SIMULATED test form | `android/app/src/main/java/org/aura/asha/autofill/` |
| Server address setting | `server/app/web/native.js`, login screen and Settings |

## Autofill demo (SIMULATED)
1. Record and confirm an HBNC note → Saved → **View in form order** → **Get ready for autofill**.
2. **Turn on autofill** → pick "A.U.R.A. visit autofill" in Android settings (once).
3. **Open test form** (SIMULATED) → tap any field → pick "A.U.R.A. visit: fill N answers" → check each answer → Submit (does nothing).

Only the SIMULATED test form is allow-listed. No government app is filled until its terms are checked (D-34 condition 1).
