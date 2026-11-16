/* Native shell glue (Android app built with Capacitor, mobile/). In a normal browser NATIVE is false and nothing here runs.
   The app's pages are bundled inside the APK; only /v1 API calls go to the A.U.R.A. server (default: the laptop over USB). */
const NATIVE = !!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform());
const DEFAULT_SERVER = "http://localhost:8000"; // phone on USB with `adb reverse tcp:8000 tcp:8000` (make.ps1 apk-run)

function serverBase() {
  if (!NATIVE) return ""; // web app: same origin
  let s = null;
  try { s = localStorage.getItem("aura.server"); } catch { /* storage blocked */ }
  return (s || DEFAULT_SERVER).replace(/\/+$/, "");
}

/* Accepts "192.168.1.5:8000" or a full http(s) URL; returns a clean base URL or null. */
function normaliseServer(input) {
  let v = String(input || "").trim();
  if (!v) return DEFAULT_SERVER;
  if (!/^https?:\/\//i.test(v)) v = "http://" + v;
  try {
    const u = new URL(v);
    if (u.pathname !== "/" || u.search || u.hash || u.username || u.password) return null;
    return u.origin;
  } catch { return null; }
}

function nativeCall(plugin, method, options = {}) {
  return window.Capacitor.nativePromise(plugin, method, options);
}

/* Share text with the Android share sheet (WhatsApp etc.). */
function nativeShareText(text) {
  return nativeCall("Share", "share", { title: "A.U.R.A.", text, dialogTitle: "A.U.R.A." });
}

/* Save a downloaded report: the WebView cannot download blobs, so the app writes it to its cache and opens the share sheet. */
async function nativeShareFile(blob, filename) {
  const b64 = await new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",")[1] || "");
    r.onerror = () => reject(r.error);
    r.readAsDataURL(blob);
  });
  return nativeCall("AuraAutofill", "shareFile", { name: filename, mime: blob.type || "application/octet-stream", data: b64 });
}

/* Autofill (D-34 ladder step 3). Only answered rows of a CONFIRMED record are handed to Android; blank stays blank. */
function autofillPayload(f, noteId) {
  const fields = [];
  for (const s of f.sections) for (const r of s.rows) if (r.value !== null) fields.push({ id: r.id, label: r.question, value: String(r.value) });
  return { noteId: String(noteId), title: f.title, form: f.form || "hbnc_home_visit", fields };
}
