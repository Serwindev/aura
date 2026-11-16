# 004 — Android app now, as a native shell around the web app (D-35)

**Date:** 2026-11-16 · **Status:** native app now = **confirmed** (human: "make Android app … change everything into native app format … if anything goes wrong, we can still use the web app"); Capacitor as the framework = **proposed** by Claude (reversible) · **Supersedes:** D-16 "Flutter deferred" and D-27 (proposed) for the Android form factor

## Decision
- Build the Android app with **Capacitor 7** (`mobile/`), not Flutter. The APK bundles the same mobile web app (`server/app/web`, single source, copied by `mobile/copy-web.mjs`) and adds native pieces: microphone permission, share sheet, report files, and the **Android Autofill service** (D-34 step 3).
- The server stays the same FastAPI app on the laptop. The app's pages load from inside the APK (`http://localhost` origin), so it opens with no connection; only `/v1` calls go to the server (default `http://localhost:8000` via `adb reverse`; Wi-Fi address settable on the login screen / Settings). CORS allows only `http://localhost`.
- The web app keeps working unchanged in a browser (`NATIVE` is false there) — the fallback the human asked for.

## Why not Flutter now
A Flutter rewrite of ~1,300 lines of tested UI + offline queue would take days and re-open bugs; Capacitor reuses all of it today. Flutter remains possible later if native UI performance is needed.

## Limits (honest)
- Debug APK only (no Play Store, no signing key). Not yet run on a real phone or emulator (this laptop has no emulator hypervisor). Verified: Gradle build, JVM tests for the fill rules, and the web layer in headless Edge with a fake native bridge.
- Plain http to the demo server (network security config allows cleartext) — fine for synthetic data, must become HTTPS before any field use.
- Service worker is not used in the app (pages are already inside the APK).
- Background sync when the app is closed is still not built (the outbox flushes while the app is open).
