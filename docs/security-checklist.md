# Security checklist (T-064) — DRAFT, not yet signed

> Written 2026-11-16 by Claude from the code in this repo. Each line says where it is enforced. "Gap" lines are honest limits of the **demo** build.
> **Sign-off:** ☐ Lead ☐ Second reviewer — tick and date when checked. This is a checklist, not a penetration test.

## Accounts and access
| # | Check | Status | Where |
|---|---|---|---|
| A1 | Login is phone + one-time code; code expires in 5 min; max 5 tries | ✅ (code is **SIMULATED**: shown on screen, no SMS) | `server/app/api/routes.py` (`OTP_ATTEMPTS`, `timedelta(minutes=5)`) |
| A2 | API calls need a signed token (JWT HS256, 30 days); bad/expired token → 401 → app logs out | ✅ | `routes.py` `current_user`, `TOKEN_DAYS` |
| A3 | Token secret generated per install, kept out of git | ✅ | `core/settings.py` `_jwt_secret` → `server/data/jwt.secret` (git-ignored) |
| A4 | Every note, person, task and report is filtered by owner; another ASHA's note → 404 | ✅ | `own_note`, `people_for(db, user.id)`; tests `test_forms.py`, `test_api.py` |
| A5 | No government credentials are read, stored or sent | ✅ | autofill skips password/OTP/PIN fields (`FillPlanner.isSensitive`, tested) |
| A6 | Gap: no token revocation list (logout deletes the token on the phone only) | ⚠️ demo | — |

## Input handling
| # | Check | Status | Where |
|---|---|---|---|
| I1 | Upload limits: audio ≤ 12 MB and ≤ 180 s; typed note ≤ 2,000 chars | ✅ | `routes.py` `MAX_AUDIO_BYTES`, `MAX_AUDIO_SECONDS`, `MAX_TEXT_CHARS` |
| I2 | Confirmed records are re-validated on the server (schema, ranges, schedule, known danger codes); evidence is server-owned | ✅ | `services.py` `confirm_note`, `_check_record` |
| I3 | LLM output is untrusted: same validator, evidence quote must be in the transcript, model cannot set `matched_id` | ✅ | `extraction/validate.py`, `extraction/llm.py` |
| I4 | All dynamic text in the web app is escaped (`esc()`); no `eval`, no third-party scripts | ✅ | `server/app/web/app.js`; privacy audit check "third-party scripts" |
| I5 | Duplicate sends are idempotent (same key → same note, also under a race) | ✅ | `create_note` idempotency; `test_api.py` |

## Transport and browser
| # | Check | Status | Where |
|---|---|---|---|
| T1 | Headers: `X-Content-Type-Options: nosniff`, `Permissions-Policy` microphone only, `Cache-Control: no-store` on API | ✅ | `main.py` middleware |
| T2 | CORS: only the Android app origin `http://localhost`; no cookies (token in header) | ✅ | `main.py` `APP_ORIGINS`; `tests/test_cors_app.py` |
| T3 | Gap: demo uses plain http (USB/Wi-Fi) or a self-signed certificate; the APK allows cleartext | ⚠️ demo | `mobile/.../network_security_config.xml` — must be HTTPS with a real certificate before any field use |

## Data on the phone (Android app)
| # | Check | Status | Where |
|---|---|---|---|
| P1 | Permissions: internet, microphone, notifications (+ reboot/wake-lock for reminders) only | ✅ | `docs/privacy-audit.md` (checks plugin manifests too) |
| P2 | No cloud backup / device transfer of app data | ✅ | `AndroidManifest.xml` `allowBackup=false`, `data_extraction_rules.xml` |
| P3 | Autofill service can only be bound by Android; she enables it in Android settings; allow-list = SIMULATED form only | ✅ | manifest `BIND_AUTOFILL_SERVICE`; `FillPlanner.ALLOW_LIST` |
| P4 | Autofill answers expire after 12 h; cleared on logout and "Delete my data" | ✅ | `VisitStore`, `app.js` `logout` |
| P5 | Reminder notifications show only a count, no names | ✅ | `app.js` `scheduleReminders` |
| P6 | Gap: unsent notes (IndexedDB) and the login token (localStorage) are not encrypted at rest beyond Android's own app sandbox / device encryption | ⚠️ demo | T-041 (SQLCipher) not done |
| P7 | Gap: debug APK, not signed with a release key; WebView debugging is on in debug builds | ⚠️ demo | release signing needed before distribution |

## Server data
| # | Check | Status | Where |
|---|---|---|---|
| S1 | Audio deleted on confirm/discard; 7-day cap | ✅ | `purge_expired_audio`; D-07 |
| S2 | "Delete my data" removes her notes, audio, people, task actions and audit events (account row stays for login) | ✅ | `wipe_owner_data`; tests |
| S3 | Logs carry no transcript text or names | ✅ | privacy audit "PII-free logging" check |
| S4 | Audit events: draft created, confirmed, discarded, person added/updated/removed, demo loaded/removed | ✅ | `AuditEvent` rows in `services.py` (wiped with her data on request) |
| S5 | Secret scan in CI (local script + gitleaks) | ✅ | `.github/workflows/ci.yml` |
| S6 | Gap: SQLite file on the laptop is not encrypted; no backups; single machine | ⚠️ demo | D-13; Postgres + disk encryption for any pilot |
| S7 | Gap: no rate limiting on login/notes beyond the 5-try OTP cap | ⚠️ demo | add before any internet-facing deployment |

## Before any real-world use (not only demo)
HTTPS with a real certificate · release-signed APK · rate limiting · encrypted storage on phone and server · real SMS OTP via an approved provider · DPDP-compliant consent and retention notice · clinician-reviewed rules · written permission before any government-app autofill (D-34).
