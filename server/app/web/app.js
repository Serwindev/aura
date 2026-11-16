/* A.U.R.A. mobile web app. No framework and no external requests. All dynamic text goes through esc(). */
const $ = (sel, root = document) => root.querySelector(sel);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* private window */ } },
  del(k) { try { localStorage.removeItem(k); } catch { /* private window */ } },
};

const S = { token: store.get("aura.token"), lang: store.get("aura.lang") || "hi", user: null, meta: null, view: "home", task: null, note: null, draft: null, errors: {}, showAllVitals: false, recorder: null, noteLang: null, reportMonth: null };
const t = (k) => STRINGS[S.lang][k] ?? k;
const VIEW = () => $("#view");

class ApiError extends Error {
  constructor(status, body) { super(body?.error?.message || "error"); this.status = status; this.code = body?.error?.code; this.details = body?.error?.details || []; }
}

async function api(path, { method = "GET", json, form, blob } = {}) {
  const headers = {};
  if (S.token) headers.Authorization = "Bearer " + S.token;
  if (json !== undefined) headers["Content-Type"] = "application/json";
  let res;
  try {
    res = await fetch(serverBase() + "/v1" + path, { method, headers, body: json !== undefined ? JSON.stringify(json) : form });
  } catch {
    throw new ApiError(0, { error: { message: t("conn_error"), code: "OFFLINE" } });
  }
  if (res.status === 401 && S.token) { logout(); throw new ApiError(401, {}); }
  if (!res.ok) throw new ApiError(res.status, await res.json().catch(() => ({})));
  return blob ? res.blob() : res.json();
}

function toast(msg, action) {
  const el = $("#toast");
  el.innerHTML = `<span>${esc(msg)}</span>` + (action ? `<button id="toast-act">${esc(action.label)}</button>` : "");
  el.hidden = false;
  clearTimeout(toast.timer);
  if (action) $("#toast-act").onclick = () => { el.hidden = true; action.run(); };
  toast.timer = setTimeout(() => { el.hidden = true; }, action ? 6000 : 3500);
}
const fail = (e) => { if (e.status !== 401) toast(e.message || t("conn_error")); };
function busy(on, text) { $("#busy").hidden = !on; $("#busy-text").textContent = text || ""; }
function fmtDate(iso) { return new Date(iso + "T00:00:00").toLocaleDateString(S.lang === "hi" ? "hi-IN" : "en-IN", { day: "numeric", month: "short" }); }
const todayIso = () => { const d = new Date(); return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10); };

const ICONS = {
  home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/></svg>',
  mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>',
  stop: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>',
  doc: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 3h9l4 4v14H6z"/><path d="M9 12h7M9 16h7"/></svg>',
  people: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><circle cx="17" cy="9" r="2.5"/><path d="M16 14.2c2.8.3 5 2.6 5 5.8"/></svg>',
  gear: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/></svg>',
};

function renderNav() {
  const nav = $("#nav");
  nav.hidden = !S.user;
  if (!S.user) return;
  const items = [["home", "nav_home", "home"], ["record", "nav_record", "mic"], ["people", "nav_people", "people"], ["reports", "nav_reports", "doc"], ["settings", "nav_settings", "gear"]];
  const active = S.view === "review" || S.view === "saved" ? "record" : S.view;
  nav.innerHTML = items.map(([v, k, i]) => `<button data-nav="${v}" ${v === active ? 'aria-current="page"' : ""}>${ICONS[i]}<span>${esc(t(k))}</span></button>`).join("");
}

function go(view, data = {}) {
  stopRecorder();
  stopSpeaking();
  Object.assign(S, { view }, data);
  document.documentElement.lang = S.lang;
  renderNav();
  window.scrollTo(0, 0);
  ({ login: viewLogin, home: viewHome, record: viewRecord, review: viewReview, saved: viewSaved, form: viewForm, people: viewPeople, reports: viewReports, settings: viewSettings }[view])();
}

function logout() {
  stopRecorder();
  S.token = S.user = null;
  if (NATIVE) { nativeCall("AuraAutofill", "clearVisit").catch(() => {}); store.del("aura.reminders"); scheduleReminders([]); } // her session only
  store.del("aura.token");
  go("login");
}

/* ---- login ---- */
function viewLogin() {
  VIEW().className = "bare";
  VIEW().innerHTML = `
    <h1>A.U.R.A.</h1><p class="muted">${esc(t("tagline"))}</p>
    <div class="chips" style="margin:12px 0">${langChips("ui")}</div>
    <div class="banner">${esc(t("synthetic_only"))}</div>
    ${NATIVE ? serverCard() : ""}
    <form id="f-phone" class="card">
      <label class="field"><span>${esc(t("phone"))}</span><input name="phone" inputmode="numeric" autocomplete="off" maxlength="10" required></label>
      <button class="primary wide">${esc(t("send_code"))}</button>
    </form><div id="otp-area"></div>`;
  bindServerCard();
  $("#f-phone").onsubmit = async (e) => {
    e.preventDefault();
    const phone = e.target.phone.value;
    try {
      const r = await api("/auth/otp/request", { method: "POST", json: { phone } });
      $("#otp-area").innerHTML = `
        <form id="f-otp" class="card">
          <p><span class="tag sim">SIMULATED</span> ${esc(t("sim_otp"))} <strong dir="ltr">${esc(r.otp)}</strong></p>
          <label class="field"><span>${esc(t("code"))}</span><input name="otp" inputmode="numeric" autocomplete="one-time-code" maxlength="6" required></label>
          <label class="field"><span>${esc(t("name"))}</span><input name="name" autocomplete="off"></label>
          <label class="field"><span>${esc(t("asha_id"))}</span><input name="asha_id" autocomplete="off"></label>
          <button class="primary wide">${esc(t("login"))}</button>
        </form>`;
      $("#f-otp").onsubmit = async (ev) => {
        ev.preventDefault();
        const f = ev.target;
        try {
          const v = await api("/auth/otp/verify", { method: "POST", json: { phone, otp: f.otp.value, name: f.name.value, asha_id: f.asha_id.value, lang: S.lang } });
          S.token = v.token; S.user = v.user; S.lang = v.user.lang;
          store.set("aura.token", v.token);
          store.set("aura.lang", S.lang);
          store.set("aura.cache.user", JSON.stringify(v.user));
          go("home"); flushOutbox(); scheduleFlush();
        } catch (err) { fail(err); }
      };
      $("#f-otp").otp.focus();
    } catch (err) { fail(err); }
  };
}

function langChips(kind) {
  const cur = kind === "ui" ? S.lang : S.noteLang;
  return [["hi", "हिन्दी"], ["en", "English"]].map(([l, n]) => `<button class="chip" data-${kind}-lang="${l}" aria-pressed="${l === cur}">${n}</button>`).join("");
}

async function setUiLang(lang) {
  S.lang = lang;
  store.set("aura.lang", lang);
  if (S.user) { try { S.user = await api("/me", { method: "PATCH", json: { lang } }); } catch (e) { fail(e); } }
  go(S.view);
}

/* ---- home ---- */
async function viewHome() {
  VIEW().className = "";
  VIEW().innerHTML = `<h1>${esc(t("today_tasks"))}</h1><div class="empty"><div class="spinner" style="margin:auto"></div></div>`;
  let tasks, drafts, offline = false, queued = [];
  const cacheKey = "aura.cache.home." + owner();
  try {
    [tasks, drafts] = await Promise.all([api("/tasks"), api("/notes?status=draft")]);
    store.set(cacheKey, JSON.stringify({ tasks, drafts }));
  } catch (e) {
    const cached = JSON.parse(store.get(cacheKey) || "null");
    if (!retryable(e) || !cached) return fail(e);
    ({ tasks } = cached); drafts = []; offline = true; // drafts need the server to open, so hide them offline
  }
  try { queued = await Outbox.list(owner()); } catch { /* no storage */ }
  if (S.view !== "home") return;
  S.tasks = mergeVaccines(tasks);
  if (NATIVE && !offline) scheduleReminders(S.tasks);
  const byArea = store.get("aura.homeGroup") === "area";
  const ORDER = { overdue: 0, due: 1, due_soon: 2 };
  const groups = byArea
    ? [...new Set(S.tasks.map((x) => x.area || ""))].sort((a, b) => (a === "") - (b === "") || a.localeCompare(b))
      .map((a) => [a || t("no_area"), S.tasks.filter((x) => (x.area || "") === a)
        .sort((p, q) => ORDER[p.status] - ORDER[q.status] || p.due_date.localeCompare(q.due_date))])
    : ["overdue", "due", "due_soon"].map((s) => [t(s), S.tasks.filter((x) => x.status === s)]).filter(([, l]) => l.length);
  const hello = S.user.name ? `${t("hello")}, ${S.user.name}` : t("hello");
  VIEW().innerHTML = `
    <p class="muted">${esc(hello)}</p><h1>${esc(t("today_tasks"))}</h1>
    ${offline ? `<div class="banner warn">${esc(t("offline_cached"))}</div>` : ""}
    <div class="banner">${esc(t("advisory"))}</div>
    ${queued.length ? `<h2>${esc(t("outbox_title"))} (${queued.length})</h2><p class="small muted">${esc(t("outbox_hint"))}</p>`
      + queued.map(outboxCard).join("") + `<button class="primary wide" data-outbox-send="1">${esc(t("send_now"))}</button>` : ""}
    ${drafts.length ? `<h2>${esc(t("drafts"))}</h2>` + drafts.map((d) => `
      <div class="card"><p>${esc(d.transcript.slice(0, 90))}${d.transcript.length > 90 ? "…" : ""}</p>
      <button class="wide" data-open-note="${esc(d.id)}">${esc(t("open_draft"))}</button></div>`).join("") : ""}
    ${S.tasks.length ? `<div class="chips" role="group" aria-label="${esc(t("group_by"))}"><button class="chip" data-home-group="status" aria-pressed="${!byArea}">${esc(t("group_status"))}</button><button class="chip" data-home-group="area" aria-pressed="${byArea}">${esc(t("group_area"))}</button></div>` : ""}
    ${groups.length ? groups.map(([g, list]) => `<h2>${esc(g)} (${list.length})</h2>` + list.map((x) => taskCard(x, byArea)).join("")).join("") : `<div class="card empty">${esc(t("no_tasks"))}</div>`}
    <button class="primary record-fab" data-nav="record">${ICONS.mic}<span>${esc(t("record_fab"))}</span></button>`;
}

/* One visit, one card: vaccines due together for a child are given together. */
function mergeVaccines(tasks) {
  const out = [], byKey = new Map();
  for (const x of tasks) {
    const key = `${x.beneficiary_id}|${x.status}|${x.due_date}`;
    const first = x.programme === "UIP" ? byKey.get(key) : null;
    if (first) {
      first.ids.push(x.id);
      first.reasons.push(x.reason);
    } else {
      const card = { ...x, ids: [x.id], reasons: [x.reason] };
      if (x.programme === "UIP") byKey.set(key, card);
      out.push(card);
    }
  }
  for (const c of out) if (c.reasons.length > 1) {
    const names = c.reasons.map((r) => r.replace(/^[^:]*:\s*/, "").replace(/\s*\(.*$/, ""));
    c.reason = c.reasons[0].replace(/:.*?(\s*\()/, `: ${names.join(", ")}$1`);
  }
  return out;
}

function taskCard(x, showStatus = false) {
  return `<article class="card status-${esc(x.status)}">
    <div class="task-head"><span class="task-name">${esc(x.label)}</span><span class="due">${showStatus ? `<span class="pill ${esc(x.status)}">${esc(t(x.status))}</span> ` : ""}${esc(fmtDate(x.due_date))}</span></div>
    <p class="muted" style="margin:4px 0 0">${esc(x.reason)}</p>
    <div class="task-actions" id="act-${esc(x.id.replace(":", "-"))}">
      <button class="primary" data-task-note="${esc(x.id)}">${ICONS.mic.replace("<svg", '<svg width="20" height="20"')} ${esc(t("speak_note"))}</button>
      <button data-task-later="${esc(x.id)}">${esc(t("later"))}</button>
      <button data-task-dismiss="${esc(x.id)}">${esc(t("dismiss"))}</button>
    </div></article>`;
}

function taskUrl(id) { const [b, r] = id.split(":"); return `/tasks/${encodeURIComponent(b)}/${encodeURIComponent(r)}/action`; }

function idsOf(id) { return S.tasks.find((x) => x.id === id)?.ids || [id]; }

function taskLater(id) {
  const box = $("#act-" + id.replace(":", "-"));
  const min = new Date(Date.now() + 86400000 * 1.5).toISOString().slice(0, 10);
  box.innerHTML = `<label style="flex:1"><span class="small">${esc(t("later_when"))}</span><input type="date" min="${min}" value="${min}" id="later-date"></label>
    <button class="primary" id="later-save">${esc(t("save"))}</button>`;
  box.style.alignItems = "flex-end";
  $("#later-save").onclick = async () => {
    try {
      await Promise.all(idsOf(id).map((i) => api(taskUrl(i), { method: "POST", json: { action: "reschedule", until: $("#later-date").value } })));
      toast(t("rescheduled"));
      viewHome();
    } catch (e) { fail(e); }
  };
}

async function taskDismiss(id) {
  const ids = idsOf(id);
  const send = (action) => Promise.all(ids.map((i) => api(taskUrl(i), { method: "POST", json: { action } })));
  try {
    await send("dismiss");
    viewHome();
    toast(t("dismissed"), { label: t("undo"), run: async () => { await send("restore").catch(fail); viewHome(); } });
  } catch (e) { fail(e); }
}

/* ---- record ---- */
const EXAMPLES = {
  hi: ["आज सुनीता की बच्ची का नवजात भ्रमण दिन 3 किया। वजन 2 किलो 800 ग्राम है, बुखार नहीं है।", "ईशान को आज एमआर 1 का टीका लगाया।", "रेखा के बेटे को बुखार है और दूध नहीं पी रहा। नवजात भ्रमण किया।", "पूजा यादव गर्भवती हैं, बीपी 120/80, हीमोग्लोबिन 10.5, आयरन की गोली दी।"],
  en: ["Visited Sunita Devi baby today, newborn visit day 3. Weight is 2.8 kg, no fever.", "Ishaan vaccination done, MR 1 given today.", "Rekha baby has fever and is not feeding. Newborn visit done.", "Pooja Yadav pregnant, BP 120/80, hemoglobin 10.5, iron tablets given."],
};

/* Guided mode: a short list of what to say for this kind of visit; "Next" moves the highlight while she talks.
   It only prompts. The note is still one free recording and she still checks every field. */
const GUIDE = {
  HBNC: ["g_who", "g_day", "weight_kg", "temp_c", "g_feeding", "g_danger", "g_services"],
  HBYC: ["g_who", "g_month", "weight_kg", "g_feeding", "g_danger", "g_services"],
  UIP: ["g_who", "g_vaccine", "g_next"],
  ANC: ["g_who", "g_anc", "g_bp", "weight_kg", "g_services", "g_danger"],
  "": ["g_who", "g_what", "g_danger", "g_services", "g_next"],
};
function guideKeys() { return GUIDE[S.task?.programme] || GUIDE[""]; }
function guideList() {
  const step = S.guideStep || 0;
  return guideKeys().map((k, i) => `<li class="${i < step ? "done" : i === step ? "on" : ""}">${esc(t(k))}</li>`).join("");
}
function guideCard() {
  return `<section class="card"><div class="task-head"><span class="field-label" style="margin:0">${esc(t("guide_title"))}</span>
    <button class="link" data-guide-next="1">${esc(t("guide_next"))} ›</button></div>
    <ol class="guide" id="guide">${guideList()}</ol></section>`;
}

function stopRecorder() { if (S.recorder) { S.recorder.release(); S.recorder = null; } }

function viewRecord() {
  VIEW().className = "";
  if (S.guideFor !== (S.task?.id || "")) { S.guideFor = S.task?.id || ""; S.guideStep = 0; }
  if (!S.noteLang) S.noteLang = S.lang;
  const taskBox = S.task ? `<div class="banner ok">${esc(t("for_task"))}: <strong>${esc(S.task.label)}</strong><br><span class="small">${esc(S.task.reason)}</span></div>` : "";
  const noModel = S.meta && !S.meta.stt.languages.includes(S.noteLang);
  VIEW().innerHTML = `
    <h1>${esc(t("record_title"))}</h1>${taskBox}
    <span class="field-label">${esc(t("speak_lang"))}</span>
    <div class="chips">${langChips("note")}</div>
    <div class="mic-wrap">
      <button id="mic" class="mic" aria-label="${esc(t("tap_to_speak"))}" ${noModel ? "disabled" : ""}>${ICONS.mic}</button>
      <div class="timer" id="timer" aria-live="off"></div>
      <div id="mic-label" style="font-weight:600">${esc(noModel ? t("no_stt") : t("tap_to_speak"))}</div>
    </div>
    <p class="muted" style="text-align:center">${esc(t("record_hint"))}</p>
    ${guideCard()}
    <div class="banner">${esc(t("synthetic_only"))}</div>
    <label class="btn file-btn wide">${esc(t("upload"))}<input type="file" id="audio-file" accept="audio/*"></label>
    <div class="divider">${esc(t("or"))}</div>
    <label class="field"><span>${esc(t("type_note"))}</span><textarea id="note-text" maxlength="2000"></textarea></label>
    <button class="primary wide" id="send-text">${esc(t("process_text"))}</button>
    <h2>${esc(t("examples"))}</h2>
    ${EXAMPLES[S.noteLang].map((x, i) => `<button class="example" data-example="${i}">${esc(x)}</button>`).join("")}`;
  $("#mic").onclick = toggleRecord;
  $("#send-text").onclick = () => { const v = $("#note-text").value.trim(); if (v) submitNote({ text: v }); else $("#note-text").focus(); };
  $("#audio-file").onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    busy(true, t("listening"));
    try { const wav = await AuraAudio.fileToWav(f); await submitNote({ wav }); } catch { busy(false); toast(t("bad_file")); }
  };
}

async function toggleRecord() {
  const mic = $("#mic");
  if (S.recorder) {
    const rec = S.recorder;
    S.recorder = null;
    busy(true, t("listening"));
    const wav = await rec.stop();
    return submitNote({ wav });
  }
  const rec = new AuraAudio.Recorder((sec, level, limit) => {
    const el = $("#timer"); const m = $("#mic");
    if (!el || !m) return;
    el.textContent = `${Math.floor(sec / 60)}:${String(Math.floor(sec) % 60).padStart(2, "0")}`;
    m.style.setProperty("--level", level.toFixed(2));
    if (limit && S.recorder === rec) toggleRecord();
  });
  try {
    await rec.start();
  } catch (e) {
    rec.release();
    return toast(e.message === "insecure" ? t("insecure_mic") : t("no_mic"));
  }
  S.recorder = rec;
  mic.classList.add("on");
  mic.innerHTML = ICONS.stop;
  mic.setAttribute("aria-label", t("tap_to_stop"));
  $("#mic-label").textContent = t("tap_to_stop");
}

/* ---- notes: send now, or keep on the phone and send later (outbox.js) ---- */
const uid = () => (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(16).slice(2));
const owner = () => S.user && String(S.user.id ?? S.user.phone);
/* No connection, server error or rate limit: worth retrying. Anything else (bad input) is not. */
const retryable = (e) => e.status === 0 || e.status === 429 || e.status >= 500;

function noteForm(item) {
  const form = new FormData();
  form.append("language", item.language);
  form.append("idempotency_key", item.id);
  form.append("recorded_on", item.recorded_on);
  if (item.task) { form.append("beneficiary_id", item.task.beneficiary_id); form.append("programme", item.task.programme); form.append("rule_id", item.task.rule_id); }
  if (item.wav) form.append("audio", item.wav, "note.wav"); else form.append("text", item.text);
  return form;
}

async function submitNote({ text, wav }) {
  const task = S.task ? { beneficiary_id: S.task.beneficiary_id, programme: S.task.programme, rule_id: S.task.rule_id, label: S.task.label } : null;
  const item = { id: uid(), owner: owner(), language: S.noteLang, recorded_on: todayIso(), created_at: new Date().toISOString(),
                 task, text: wav ? null : text, wav: wav || null, seconds: wav ? Math.max(0, (wav.size - 44) / 32000) : 0, status: "pending", attempts: 0 };
  busy(true, t("listening"));
  try {
    const note = await api("/notes", { method: "POST", form: noteForm(item) });
    await openNote(note);
  } catch (e) {
    if (retryable(e) && await queueNote(item)) return;
    if (S.view === "record") viewRecord();
    fail(e);
  } finally { busy(false); }
}

async function queueNote(item) {
  try { await Outbox.put(item); } catch { return false; } // private window / no storage: show the error instead
  toast(t("queued"));
  go("home", { task: null });
  scheduleFlush();
  return true;
}

let flushing = false;
async function flushOutbox({ manual = false } = {}) {
  if (flushing || !S.token || !S.user) return;
  let items;
  try { items = (await Outbox.list(owner())).filter((x) => manual || x.status === "pending"); } catch { return; }
  if (!items.length) return;
  flushing = true;
  let sent = 0;
  try {
    for (const item of items) {
      try {
        await api("/notes", { method: "POST", form: noteForm(item) });
        await Outbox.remove(item.id);
        sent++;
      } catch (e) {
        if (e.status === 401) return;
        if (retryable(e)) { item.attempts++; await Outbox.put(item); break; } // still offline: stop, keep order
        Object.assign(item, { status: "failed", error: e.message, attempts: item.attempts + 1 });
        await Outbox.put(item);
      }
    }
  } finally {
    flushing = false;
    if (sent) toast(t("sent_n").replace("{n}", sent));
    if (S.view === "home" && (sent || manual)) viewHome();
  }
}

let flushTimer = null;
function scheduleFlush() {
  clearInterval(flushTimer);
  flushTimer = setInterval(async () => {
    let left = [];
    try { left = (await Outbox.list(owner())).filter((x) => x.status === "pending"); } catch { /* no storage */ }
    if (!left.length) return clearInterval(flushTimer);
    flushOutbox();
  }, 20000);
}
window.addEventListener("online", () => flushOutbox());
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") flushOutbox(); });

function outboxCard(x) {
  const what = x.wav ? `${t("voice_note")} · ${Math.floor(x.seconds / 60)}:${String(Math.round(x.seconds) % 60).padStart(2, "0")}`
                     : `${t("typed_note")}: ${x.text.slice(0, 70)}${x.text.length > 70 ? "…" : ""}`;
  return `<div class="card ${x.status === "failed" ? "status-overdue" : ""}">
    <div class="task-head"><span>${esc(what)}</span><span class="due">${esc(fmtDate(x.recorded_on))}</span></div>
    ${x.task ? `<p class="small muted" style="margin:4px 0 0">${esc(x.task.label)}</p>` : ""}
    ${x.status === "failed" ? `<p class="small" style="margin:4px 0 0"><strong>${esc(t("outbox_failed"))}:</strong> ${esc(x.error || "")}</p>` : ""}
    <div class="task-actions"><button data-outbox-del="${esc(x.id)}">${esc(t("delete"))}</button></div></div>`;
}

/* ---- review ---- */
async function openNote(note) {
  if (!S.people) S.people = await api("/beneficiaries");
  go("review", { note, draft: JSON.parse(JSON.stringify(note.record)), errors: {}, showAllVitals: false });
}

const VITALS_BY_TYPE = { HBNC: ["weight_kg", "temp_c"], HBYC: ["weight_kg", "temp_c"], IMMUNIZATION: [], ANC: ["weight_kg", "bp_sys", "bp_dia", "hb_g_dl"], PNC: ["temp_c", "bp_sys", "bp_dia"] };

function flagText(f) { return FLAG_TEXT[S.lang][f.code] || f.message; }
function fieldName(path) {
  const leaf = path.replace(/\[\d+\]$/, "").split(".").pop();
  const map = { matched_id: "person", mention: "person", services_given: "services", needed: "referral_needed" };
  const k = map[leaf] || leaf;
  return STRINGS[S.lang][k] || k;
}
function evidenceBtn(path) {
  const q = S.note.record.evidence?.[path]?.quote;
  return q ? `<button type="button" class="evidence" data-quote="${esc(q)}">${esc(t("heard_quote"))}: “${esc(q)}”</button>` : "";
}
function flagsFor(path) { return (S.note.flags || []).filter((f) => f.path === path); }
function fieldNote(path) {
  const parts = [];
  for (const f of flagsFor(path)) if (f.severity === "info") parts.push(`<div class="muted small">${esc(flagText(f))}</div>`);
  const fe = S.errors[path];
  if (fe) parts.push(`<div class="field-error">${esc(FLAG_TEXT[S.lang][fe.code] || fe.message)}</div>`);
  return evidenceBtn(path) + parts.join("");
}
function isBad(path) { return S.errors[path] || flagsFor(path).some((f) => f.severity === "error") ? "bad" : ""; }

function highlight(text, quote) {
  if (!quote) return esc(text);
  const i = text.indexOf(quote);
  return i < 0 ? esc(text) : esc(text.slice(0, i)) + "<mark>" + esc(quote) + "</mark>" + esc(text.slice(i + quote.length));
}

function options(map, value, placeholder) {
  return (placeholder ? `<option value="">${esc(placeholder)}</option>` : "") +
    Object.entries(map).map(([k, v]) => `<option value="${esc(k)}" ${k === value ? "selected" : ""}>${esc(v)}</option>`).join("");
}

function dangerLabel(code) {
  for (const group of Object.values(S.meta.danger_signs)) if (group[code]) return group[code][S.lang];
  return code;
}

function viewReview() {
  VIEW().className = "";
  const n = S.note, d = S.draft;
  const top = (n.flags || []).filter((f) => f.severity !== "info");
  const candIds = new Set((n.candidates || []).map((c) => c.id));
  const people = [...S.people].sort((a, b) => candIds.has(b.id) - candIds.has(a.id));
  const shown = S.showAllVitals ? Object.keys(d.vitals) : Object.keys(d.vitals).filter((k) => d.vitals[k] !== null || (VITALS_BY_TYPE[d.visit_type] || []).includes(k) || flagsFor(`vitals.${k}`).length || S.errors[`vitals.${k}`]);
  const danger = d.danger_signs.some((x) => x.present);
  VIEW().innerHTML = `
    <h1>${esc(t("review_title"))}</h1>
    <section class="card">
      <span class="field-label">${esc(t("heard"))} ${n.stt_provider ? `<span class="tag">${esc(n.stt_provider)}</span>` : ""}</span>
      <div class="transcript" id="transcript">${esc(n.transcript)}</div>
      <div id="audio-slot"></div>
      ${speakBtn("draft")}
    </section>
    ${notSaid(d)}
    <section>
      ${top.length ? `<h2>${esc(t("check_first"))}</h2>` + top.map((f) => `<button type="button" class="flag ${esc(f.severity)}" data-scroll="${esc(f.path)}"><strong>${esc(fieldName(f.path))}:</strong> ${esc(flagText(f))}${f.proposed !== null && typeof f.proposed !== "object" ? ` (${esc(f.proposed)})` : ""}</button>`).join("") : `<div class="banner ok">${esc(t("all_clear"))}</div>`}
    </section>
    ${danger ? `<div class="banner danger" role="alert">${esc(t("danger_alert"))}</div>` : ""}
    <section class="card">
      <label class="field ${isBad("beneficiary.matched_id")}" data-path="beneficiary.matched_id"><span>${esc(t("person"))}</span>
        <select data-bind="beneficiary.matched_id">${options(Object.fromEntries(people.map((p) => [p.id, p.label])), d.beneficiary.matched_id, t("choose"))}</select>
        ${fieldNote("beneficiary.mention")}${fieldNote("beneficiary.matched_id")}</label>
      <label class="field ${isBad("visit_type")}" data-path="visit_type"><span>${esc(t("visit_type"))}</span>
        <select data-bind="visit_type" data-rerender>${options(VISIT_TYPES[S.lang], d.visit_type, t("choose"))}</select>${fieldNote("visit_type")}</label>
      <label class="field ${isBad("visit_date")}" data-path="visit_date"><span>${esc(t("visit_date"))}</span>
        <input type="date" data-bind="visit_date" max="${todayIso()}" value="${esc(d.visit_date || "")}">${fieldNote("visit_date")}</label>
      ${d.visit_type === "HBNC" ? `<label class="field ${isBad("visit_index.hbnc_day")}" data-path="visit_index.hbnc_day"><span>${esc(t("hbnc_day"))}</span><select data-bind="visit_index.hbnc_day" data-num>${options(Object.fromEntries([1, 3, 7, 14, 21, 28, 42].map((x) => [x, x])), String(d.visit_index.hbnc_day ?? ""), t("choose"))}</select>${fieldNote("visit_index.hbnc_day")}</label>` : ""}
      ${d.visit_type === "HBYC" ? `<label class="field ${isBad("visit_index.hbyc_month")}" data-path="visit_index.hbyc_month"><span>${esc(t("hbyc_month"))}</span><select data-bind="visit_index.hbyc_month" data-num>${options(Object.fromEntries([3, 6, 9, 12, 15].map((x) => [x, x])), String(d.visit_index.hbyc_month ?? ""), t("choose"))}</select>${fieldNote("visit_index.hbyc_month")}</label>` : ""}
      ${d.visit_type === "ANC" ? `<label class="field" data-path="visit_index.anc_number"><span>${esc(t("anc_number"))}</span><input type="number" min="1" max="12" data-bind="visit_index.anc_number" data-num value="${esc(d.visit_index.anc_number ?? "")}">${fieldNote("visit_index.anc_number")}</label>` : ""}
    </section>
    <section class="card">
      <span class="field-label">${esc(t("vitals"))}</span>
      <div class="grid2">${shown.map((k) => `<label class="field ${isBad("vitals." + k)}" data-path="vitals.${k}"><span>${esc(t(k))}</span><input type="number" step="any" inputmode="decimal" data-bind="vitals.${k}" data-num value="${esc(d.vitals[k] ?? "")}">${fieldNote("vitals." + k)}</label>`).join("")}</div>
      ${S.showAllVitals ? "" : `<button class="link" data-act="more-vitals">${esc(t("more"))}</button>`}
    </section>
    <section class="card" data-path="danger_signs">
      <span class="field-label">${esc(t("danger_signs"))}</span>
      ${d.danger_signs.map((x, i) => `<div class="item ${x.present ? "present" : ""}" data-path="danger_signs[${i}]"><span class="item-name">${esc(dangerLabel(x.code))}</span>
        <span class="seg yes"><button data-danger="${i}" data-val="1" aria-pressed="${x.present === true}">${esc(t("yes"))}</button><button data-danger="${i}" data-val="0" aria-pressed="${x.present === false}">${esc(t("no"))}</button></span>
        <button class="icon-x" data-remove="danger_signs" data-i="${i}" aria-label="remove">✕</button><div style="flex-basis:100%">${evidenceBtn(`danger_signs[${i}]`)}</div></div>`).join("")}
      <select id="add-danger" aria-label="${esc(t("add_danger"))}"><option value="">+ ${esc(t("add_danger"))}</option>${Object.entries(S.meta.danger_signs).map(([, g]) => Object.entries(g).filter(([c]) => !d.danger_signs.some((x) => x.code === c)).map(([c, l]) => `<option value="${esc(c)}">${esc(l[S.lang])}</option>`).join("")).join("")}</select>
    </section>
    <section class="card" data-path="services_given">
      <span class="field-label">${esc(t("services"))}</span>
      ${d.services_given.map((x, i) => `<div class="item" data-path="services_given[${i}]">
        <select style="flex:1 1 120px" data-list="services_given" data-i="${i}" data-key="type">${options(SERVICE_TYPES[S.lang], x.type)}</select>
        <input style="flex:1 1 120px" placeholder="${esc(t("service_detail"))}" data-list="services_given" data-i="${i}" data-key="detail" value="${esc(x.detail ?? "")}" list="vaccines">
        <button class="icon-x" data-remove="services_given" data-i="${i}" aria-label="remove">✕</button><div style="flex-basis:100%">${evidenceBtn(`services_given[${i}]`)}</div></div>`).join("")}
      <datalist id="vaccines">${(S.meta.vaccines || []).map((v) => `<option value="${esc(v)}">`).join("")}</datalist>
      <button class="link" data-act="add-service">+ ${esc(t("add_service"))}</button>
    </section>
    <section class="card">
      <span class="field-label">${esc(t("referral_needed"))}</span>
      <span class="seg"><button data-ref="1" aria-pressed="${d.referral.needed === true}">${esc(t("yes"))}</button><button data-ref="0" aria-pressed="${d.referral.needed === false}">${esc(t("no"))}</button></span>
      <span class="muted small">${d.referral.needed === null ? esc(t("not_stated")) : ""}</span>${evidenceBtn("referral.needed")}
      ${d.referral.needed ? `<label class="field"><span>${esc(t("facility"))}</span><input data-bind="referral.facility" value="${esc(d.referral.facility ?? "")}">${fieldNote("referral.facility")}</label>` : ""}
    </section>
    <section class="card">
      <span class="field-label">${esc(t("next_due"))}</span>
      ${d.next_due.map((x, i) => `<div class="item"><input style="flex:1 1 130px" aria-label="${esc(t("due_what"))}" data-list="next_due" data-i="${i}" data-key="what" value="${esc(x.what)}"><input style="flex:1 1 130px" type="date" aria-label="${esc(t("due_date"))}" data-list="next_due" data-i="${i}" data-key="date" value="${esc(x.date ?? "")}"><button class="icon-x" data-remove="next_due" data-i="${i}" aria-label="remove">✕</button><div style="flex-basis:100%">${evidenceBtn(`next_due[${i}]`)}</div></div>`).join("")}
      <button class="link" data-act="add-due">+ ${esc(t("add_due"))}</button>
    </section>
    <div class="sticky"><button class="primary wide" id="confirm">${esc(t("confirm"))}</button></div>
    <button class="danger wide" id="discard" style="margin-top:8px">${esc(t("discard"))}</button>`;
  if (n.has_audio) loadAudio(n.id);
  updateConfirm();
}

/* What the visit type usually needs but the note did not say, so she can ask before confirming. */
function notSaid(d) {
  const keys = (VITALS_BY_TYPE[d.visit_type] || []).filter((k) => d.vitals[k] === null);
  if ((d.visit_type === "HBNC" || d.visit_type === "HBYC") && !d.danger_signs.length) keys.push("danger_signs");
  if (!keys.length) return "";
  return `<div class="banner warn"><strong>${esc(t("not_said"))}:</strong> ${keys.map((k) => esc(t(k))).join(", ")}<br><span class="small">${esc(t("not_said_hint"))}</span></div>`;
}

/* Read aloud with the phone's own voice. Only on-device voices are used, so the text never leaves the phone. */
function speakBtn(which) {
  return "speechSynthesis" in window ? `<button class="wide" data-speak="${which}" style="margin-top:8px">🔊 ${esc(t("read_aloud"))}</button>` : "";
}
function stopSpeaking() { if ("speechSynthesis" in window) speechSynthesis.cancel(); S.speaking = false; }
async function localVoice(lang) {
  let all = speechSynthesis.getVoices();
  if (!all.length) {
    await new Promise((r) => { speechSynthesis.addEventListener("voiceschanged", r, { once: true }); setTimeout(r, 1500); });
    all = speechSynthesis.getVoices();
  }
  const mine = all.filter((v) => v.localService && v.lang.toLowerCase().startsWith(lang));
  return mine.find((v) => /-in$/i.test(v.lang)) || mine[0] || null;
}
function recordSpeech(r) {
  const L = S.lang, parts = [];
  const plain = (s) => String(s).replace(/\s*\(.*?\)/g, "");
  const who = (S.people || []).find((p) => p.id === r.beneficiary.matched_id)?.label;
  if (who) parts.push(who);
  if (r.visit_type) parts.push(plain(VISIT_TYPES[L][r.visit_type]));
  if (r.visit_index?.hbnc_day) parts.push(`${t("hbnc_day")} ${r.visit_index.hbnc_day}`);
  if (r.visit_index?.hbyc_month) parts.push(`${t("hbyc_month")} ${r.visit_index.hbyc_month}`);
  for (const [k, v] of Object.entries(r.vitals || {})) if (v !== null) parts.push(`${plain(t(k))} ${v}`);
  const signs = r.danger_signs.filter((x) => x.present).map((x) => dangerLabel(x.code));
  parts.push(signs.length ? `${t("danger_signs")}: ${signs.join(", ")}` : t("no_danger_marked"));
  for (const s of r.services_given) parts.push(`${SERVICE_TYPES[L][s.type] || s.type}${s.detail ? " " + s.detail : ""}`);
  if (r.referral.needed) parts.push(t("referral_needed") + (r.referral.facility ? ": " + r.referral.facility : ""));
  return parts.join(". ");
}
async function speak(which, btn) {
  if (S.speaking) return stopSpeaking();
  const v = await localVoice(S.lang);
  if (!v) return toast(t("no_voice"));
  const u = new SpeechSynthesisUtterance(recordSpeech(which === "draft" ? S.draft : S.note.record));
  Object.assign(u, { voice: v, lang: v.lang, rate: 0.9 });
  u.onend = u.onerror = () => { S.speaking = false; if (btn) btn.textContent = "🔊 " + t("read_aloud"); };
  S.speaking = true;
  if (btn) btn.textContent = "■ " + t("stop_reading");
  speechSynthesis.speak(u);
}

async function loadAudio(id) {
  try {
    const blob = await api(`/notes/${id}/audio`, { blob: true });
    const slot = $("#audio-slot");
    if (slot) slot.innerHTML = `<audio controls src="${URL.createObjectURL(blob)}"></audio>`;
  } catch { /* playback is optional */ }
}

function updateConfirm() {
  const b = $("#confirm");
  if (!b) return;
  const d = S.draft;
  const ready = d.visit_type && d.visit_date && d.beneficiary.matched_id;
  b.disabled = !ready;
  b.textContent = ready ? t("confirm") : t("confirm_needs");
}

function setPath(obj, path, value) {
  const parts = path.split(".");
  let cur = obj;
  for (const p of parts.slice(0, -1)) cur = cur[p];
  cur[parts[parts.length - 1]] = value;
}

function scrollToPath(path) {
  const el = document.querySelector(`[data-path="${CSS.escape(path)}"]`) || document.querySelector(`[data-path="${CSS.escape(path.replace(/\[\d+\]$/, ""))}"]`);
  if (el) { el.scrollIntoView({ behavior: "smooth", block: "center" }); const f = el.querySelector("input,select"); if (f) f.focus({ preventScroll: true }); }
}

async function confirmNote() {
  const b = $("#confirm");
  b.disabled = true;
  try {
    const done = await api(`/notes/${S.note.id}/confirm`, { method: "POST", json: { record: S.draft } });
    go("saved", { note: done, task: null });
  } catch (e) {
    if (e.details?.length) {
      S.errors = Object.fromEntries(e.details.map((x) => [x.path, x]));
      viewReview();
      toast(t("fix_fields"));
      scrollToPath(e.details[0].path);
    } else { fail(e); b.disabled = false; }
  }
}

/* ---- saved ---- */
function viewSaved() {
  VIEW().className = "";
  const r = S.note.record;
  const signs = r.danger_signs.filter((x) => x.present);
  const who = (S.people || []).find((p) => p.id === r.beneficiary.matched_id)?.label;
  VIEW().innerHTML = `
    <h1>${esc(t("saved_title"))}</h1>
    <div class="card"><p class="task-name">${esc(who)}</p><p>${esc(VISIT_TYPES[S.lang][r.visit_type])} · ${esc(fmtDate(r.visit_date))}</p></div>
    ${signs.length ? `<div class="banner danger" role="alert">${esc(t("danger_alert"))}<ul class="plain">${signs.map((x) => `<li>• ${esc(dangerLabel(x.code))}</li>`).join("")}</ul></div>` : ""}
    ${speakBtn("saved")}
    ${r.visit_type === "HBNC" ? `<button class="wide" data-nav="form" style="margin-top:8px">${esc(t("form_view"))}</button>` : ""}
    <div class="banner ok">${esc(t("saved_only_here"))}${S.note.audio_deleted ? " " + esc(t("audio_deleted")) : ""}</div>
    <button class="primary wide" data-nav="home">${esc(t("go_home"))}</button>
    <button class="wide" data-nav="record" style="margin-top:10px">${esc(t("another"))}</button>`;
}

/* ---- form view: her confirmed record in the order of the official paper form (she copies it herself) ---- */
async function viewForm() {
  VIEW().className = "";
  VIEW().innerHTML = `<div class="empty"><div class="spinner" style="margin:auto"></div></div>`;
  let f;
  try { f = await api(`/notes/${S.note.id}/form?lang=${S.lang}`); } catch (e) { return fail(e); }
  if (S.view !== "form") return;
  S.formText = formText(f);
  S.formData = f;
  VIEW().innerHTML = `
    <h1>${esc(f.title)}</h1>
    <div class="banner">${esc(t("form_hint"))}</div>
    <p class="small">${esc(t("form_copy_hint"))}</p>
    <p class="small muted">${esc(f.filled)} / ${esc(f.total)} ${esc(t("form_filled"))}</p>
    <div class="row"><button data-copy-form="1">${esc(t("copy_all"))}</button><button data-share-form="1">${esc(t("share_form"))}</button></div>
    ${NATIVE ? `<section class="card"><div class="task-head"><strong>${esc(t("af_title"))}</strong></div>
      <p class="small">${esc(t("af_hint"))}</p>
      <button class="primary wide" data-autofill="1">${esc(t("af_ready"))}</button>
      <div class="row" style="margin-top:8px"><button data-af-settings="1">${esc(t("af_enable"))}</button><button data-af-test="1">${esc(t("af_test"))} <span class="tag sim">SIMULATED</span></button></div>
      <p class="small muted" id="af-status"></p></section>` : ""}
    ${f.sections.map((s) => `<section class="card"><span class="field-label">${esc(s.title)}</span>
      <ul class="plain">${s.rows.map((r) => `<li class="form-row"><span>${esc(r.question)}</span>
        ${r.value !== null ? `<strong>${esc(r.value)}</strong><button class="copy-btn" data-copy="${esc(r.value)}" aria-label="${esc(t("copy") + ": " + r.question)}">${esc(t("copy"))}</button>` : `<span class="muted small">${esc(r.captured ? t("form_not_said") : t("form_fill_self"))}</span>`}
        ${r.note ? `<span class="small muted" style="flex-basis:100%">${esc(r.note)}</span>` : ""}</li>`).join("")}</ul></section>`).join("")}
    <p class="small muted">${esc(t("form_source"))}</p>
    <button class="primary wide" data-nav="saved">${esc(t("back"))}</button>`;
}

/* Only answered rows, in form order: what she would type into the official app or register. */
function formText(f) {
  const lines = [f.title];
  for (const s of f.sections) {
    const rows = s.rows.filter((r) => r.value !== null);
    if (rows.length) lines.push("", s.title, ...rows.map((r) => `${r.question}: ${r.value}`));
  }
  return lines.join("\n");
}

async function copyText(text) {
  try { await navigator.clipboard.writeText(text); }
  catch { // no clipboard API (e.g. plain http on the LAN): old-style copy
    const ta = document.createElement("textarea");
    ta.value = text; ta.setAttribute("readonly", ""); ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select(); document.execCommand("copy"); ta.remove();
  }
  toast(t("copied"));
}

async function shareForm() {
  if (NATIVE) {
    try { await nativeShareText(S.formText); return; } catch { /* fall back to copy */ }
  }
  if (navigator.share) {
    try { await navigator.share({ title: "A.U.R.A.", text: S.formText }); return; } catch (e) { if (e.name === "AbortError") return; }
  }
  copyText(S.formText); // no share sheet: copy instead
}

/* ---- reports ---- */
async function viewReports() {
  VIEW().className = "";
  const month = S.reportMonth || todayIso().slice(0, 7);
  VIEW().innerHTML = `<h1>${esc(t("reports_title"))}</h1><div class="empty"><div class="spinner" style="margin:auto"></div></div>`;
  let s, m, ed;
  try {
    [s, m, ed] = await Promise.all([api(`/reports/claims?month=${month}&lang=${S.lang}`), api(`/reports/monthly?month=${month}&lang=${S.lang}`), api(`/reports/edits?month=${month}`)]);
  } catch (e) { return fail(e); }
  if (S.view !== "reports") return;
  VIEW().innerHTML = `
    <h1>${esc(t("reports_title"))}</h1>
    <label class="field"><span>${esc(t("month"))}</span><input type="month" id="month" value="${esc(month)}"></label>
    <section class="card">
      <h2 style="margin:0 0 4px">${esc(t("monthly_title"))}</h2>
      <p class="small muted" style="margin:0 0 8px">${esc(t("monthly_hint"))}</p>
      <ul class="plain">${m.summary.map((r) => `<li class="task-head"><span>${esc(r.label)}</span><strong>${esc(r.value)}</strong></li>`).join("")}</ul>
      <div class="row" style="margin-top:10px"><button class="primary" data-rdl="pdf">${esc(t("download_pdf"))}</button><button class="primary" data-rdl="xlsx">${esc(t("download_xlsx"))}</button></div>
    </section>
    <h2>${esc(t("claims_title"))}</h2>
    <div class="banner">${esc(s.warning)}</div>
    <div class="card"><span class="muted">${esc(t("est_total"))}</span><div class="money">₹${esc(s.total)}</div></div>
    <div class="row"><button data-dl="pdf">${esc(t("download_pdf"))}</button><button data-dl="xlsx">${esc(t("download_xlsx"))}</button></div>
    ${s.rows.length ? s.rows.map((r) => `<article class="card">
      <div class="task-head"><span class="task-name">${esc(r.label)}</span><span class="pill ${esc(r.status)}">${esc(t(r.status))}</span></div>
      <p class="muted" style="margin:4px 0">${esc(r.programme)} · ${esc(t("visits"))}: ${esc(r.detail)}${r.amount ? ` · ₹${esc(r.amount)}` : ""}</p>
      ${r.dates.length ? `<p class="small muted" style="margin:0">${r.dates.map((x) => esc(fmtDate(x))).join(", ")}</p>` : ""}
      ${r.conditions ? `<p class="small" style="margin:6px 0 0">${esc(r.conditions)}</p>` : ""}
      ${r.seeded ? `<p style="margin:6px 0 0"><span class="tag sim">SIMULATED</span> <span class="small muted">${esc(t("demo_row"))}</span></p>` : ""}
    </article>`).join("") : `<div class="card empty">${esc(t("nothing_month"))}</div>`}
    <p class="muted small">${esc(s.not_computed)}</p>
    <section class="card">
      <h2 style="margin:0 0 4px">${esc(t("edits_title"))}</h2>
      <p class="small muted" style="margin:0 0 8px">${esc(t("edits_hint"))}</p>
      ${ed.notes ? `<p style="margin:0 0 6px"><strong>${esc(ed.unchanged)} / ${esc(ed.notes)}</strong> ${esc(t("edits_unchanged"))}</p>
        <ul class="plain">${ed.fields.slice(0, 6).map((f) => `<li class="task-head"><span>${esc(fieldName(f.path))}</span><strong>${esc(f.edited)} ${esc(t("times"))}</strong></li>`).join("")}</ul>`
        : `<p class="small muted" style="margin:0">${esc(t("edits_none"))}</p>`}
    </section>`;
  $("#month").onchange = (e) => { if (e.target.value) { S.reportMonth = e.target.value; viewReports(); } };
}

async function download(path, filename) {
  try {
    const blob = await api(path, { blob: true });
    if (NATIVE) { await nativeShareFile(blob, filename); return; }
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 30000);
  } catch (e) { fail(e); }
}

/* ---- people (T-045): she registers a newborn, child or pregnant woman herself ---- */
const PCATS = ["newborn", "child", "pregnant", "other"];

async function viewPeople() {
  VIEW().className = "";
  let list;
  try { list = await api("/beneficiaries"); } catch (e) { return fail(e); }
  if (S.view !== "people") return;
  S.people = list;
  const cat = S.newCat || "newborn";
  const kid = cat === "newborn" || cat === "child";
  const mothers = list.filter((p) => p.category === "pregnant" || p.category === "other");
  const own = list.filter((p) => p.own), demo = list.filter((p) => !p.own);
  const row = (p) => `<div class="card"><div class="task-head"><span class="task-name">${esc(p.label)}</span>
      ${p.own ? "" : '<span class="tag sim">SIMULATED</span>'}</div>
      <p class="small muted" style="margin:4px 0 0">${esc(t("cat_" + p.category))}${p.dob ? " · " + esc(t("born")) + " " + esc(fmtDate(p.dob)) : ""}${p.mother_label ? " · " + esc(t("mother")) + ": " + esc(p.mother_label) : ""}${p.area ? " · " + esc(p.area) : ""}${p.at_risk ? ` <span class="tag warn">${esc(t("at_risk_tag"))}</span>` : ""}</p>
      ${p.own ? `<div class="task-actions">${ssbskOn() && p.category === "newborn" ? `<button data-person-risk="${esc(p.id)}">${esc(p.at_risk ? t("at_risk_clear") : t("at_risk_mark"))}</button>` : ""}<button data-person-del="${esc(p.id)}">${esc(t("delete"))}</button></div>` : ""}</div>`;
  VIEW().innerHTML = `
    <h1>${esc(t("people_title"))}</h1>
    <p class="muted">${esc(t("people_hint"))}</p>
    <form class="card" id="f-person">
      <span class="field-label">${esc(t("who"))}</span>
      <div class="chips">${PCATS.map((c) => `<button type="button" class="chip" data-pcat="${c}" aria-pressed="${c === cat}">${esc(t("cat_" + c))}</button>`).join("")}</div>
      <label class="field"><span>${esc(t("name_hi"))}${cat === "newborn" ? " " + esc(t("optional")) : ""}</span><input name="name_hi" lang="hi" autocomplete="off" maxlength="60"></label>
      <label class="field"><span>${esc(t("name_en"))}${cat === "newborn" ? " " + esc(t("optional")) : ""}</span><input name="name_en" lang="en" autocomplete="off" maxlength="60"></label>
      ${kid ? `
        <label class="field"><span>${esc(t("dob"))}</span><input type="date" name="dob" max="${todayIso()}" value="${cat === "newborn" ? todayIso() : ""}" required></label>
        <label class="field"><span>${esc(t("mother"))}</span><select name="mother_id">
          <option value="">${esc(t("mother_new"))}</option>
          ${mothers.map((m) => `<option value="${esc(m.id)}">${esc(m.label)}</option>`).join("")}</select></label>
        <div id="new-mother">
          <label class="field"><span>${esc(t("mother_name_hi"))}</span><input name="mother_name_hi" lang="hi" autocomplete="off" maxlength="60"></label>
          <label class="field"><span>${esc(t("mother_name_en"))}</span><input name="mother_name_en" lang="en" autocomplete="off" maxlength="60"></label>
        </div>` : ""}
      ${cat === "newborn" ? `
        <span class="field-label">${esc(t("birth_place"))}</span>
        <div class="chips"><label class="chip"><input type="radio" name="delivery_place" value="institution" checked> ${esc(t("place_institution"))}</label>
        <label class="chip"><input type="radio" name="delivery_place" value="home"> ${esc(t("place_home"))}</label></div>
        ${ssbskOn() ? `<label class="chip" style="margin-top:8px"><input type="checkbox" name="at_risk"> ${esc(t("at_risk_label"))}</label>
        <p class="small muted">${esc(t("at_risk_hint"))}</p>` : ""}` : ""}
      <label class="field"><span>${esc(t("area"))}</span><input name="area" list="areas" autocomplete="off" maxlength="40"></label>
      <datalist id="areas">${[...new Set(list.map((p) => p.area).filter(Boolean))].map((a) => `<option value="${esc(a)}">`).join("")}</datalist>
      <p class="small muted">${esc(t("two_scripts"))}</p>
      <button class="primary wide">${esc(t("add_person"))}</button>
    </form>
    ${own.length ? `<h2>${esc(t("people_mine"))} (${own.length})</h2>` + own.map(row).join("") : ""}
    ${demo.length ? `<h2>${esc(t("people_demo"))} (${demo.length})</h2>` + demo.map(row).join("") : ""}`;
  const f = $("#f-person");
  if (f.mother_id) f.mother_id.onchange = () => { $("#new-mother").hidden = !!f.mother_id.value; };
  f.onsubmit = async (e) => {
    e.preventDefault();
    const v = (n) => (f[n] && f[n].value.trim()) || null;
    const body = { category: cat, name_hi: v("name_hi"), name_en: v("name_en"), area: v("area") };
    if (kid) Object.assign(body, { dob: v("dob"), mother_id: v("mother_id"), mother_name_hi: v("mother_name_hi"), mother_name_en: v("mother_name_en") });
    if (cat === "newborn") body.delivery_place = f.querySelector("input[name=delivery_place]:checked")?.value || null;
    if (cat === "newborn" && f.at_risk) body.at_risk = f.at_risk.checked;
    try {
      await api("/beneficiaries", { method: "POST", json: body });
      S.people = null; S.newCat = null;
      toast(kid ? t("person_added_tasks") : t("person_added"));
      viewPeople();
    } catch (err) { fail(err); }
  };
}

function ssbskOn() { return !!(S.user && S.user.schedule === "ssbsk2026"); }

async function togglePersonRisk(id) {
  const p = (S.people || []).find((x) => x.id === id);
  if (!p) return;
  try {
    await api(`/beneficiaries/${encodeURIComponent(id)}`, { method: "PATCH",
      json: { name_hi: null, name_en: null, dob: p.dob, delivery_place: p.delivery_place, at_risk: !p.at_risk } });
    S.people = null; toast(t("saved")); viewPeople();
  } catch (e) { fail(e); }
}

async function setSchedule(value) {
  try {
    S.user = await api("/me", { method: "PATCH", json: { schedule: value } });
    store.set("aura.cache.user", JSON.stringify(S.user));
    toast(t("saved")); viewSettings();
  } catch (e) { fail(e); }
}

/* ---- settings ---- */
async function viewSettings() {
  VIEW().className = "";
  let p, demo;
  let queued = 0;
  try { [p, demo] = await Promise.all([api("/privacy/summary"), api("/demo")]); } catch (e) { return fail(e); }
  try { queued = (await Outbox.list(owner())).length; } catch { /* no storage */ }
  if (S.view !== "settings") return;
  const u = S.user, m = S.meta;
  VIEW().innerHTML = `
    <h1>${esc(t("settings_title"))}</h1>
    <span class="field-label">${esc(t("language"))}</span><div class="chips">${langChips("ui")}</div>
    <section class="card">
      <div class="task-head"><strong>${esc(t("demo_title"))}</strong><span class="tag sim">SIMULATED</span></div>
      <p class="small muted" style="margin:6px 0 10px">${esc(demo.active ? t("demo_on").replace("{n}", demo.beneficiaries) : t("demo_off"))}</p>
      <button class="wide ${demo.active ? "" : "primary"}" id="demo-toggle">${esc(demo.active ? t("demo_remove") : t("demo_load"))}</button>
    </section>
    <h2>${esc(t("profile"))}</h2>
    <form class="card" id="f-profile">
      <label class="field"><span>${esc(t("name"))}</span><input name="name" value="${esc(u.name ?? "")}" autocomplete="off"></label>
      <label class="field"><span>${esc(t("asha_id"))}</span><input name="asha_id" value="${esc(u.asha_id ?? "")}" autocomplete="off"></label>
      <button class="wide">${esc(t("save"))}</button>
    </form>
    <h2>${esc(t("sched_title"))}</h2>
    <section class="card">
      <div class="chips" role="group" aria-label="${esc(t("sched_title"))}">
        <button class="chip" data-schedule="hbnc2014" aria-pressed="${!ssbskOn()}">${esc(t("sched_2014"))}</button>
        <button class="chip" data-schedule="ssbsk2026" aria-pressed="${ssbskOn()}">${esc(t("sched_ssbsk"))}</button></div>
      <p class="small muted">${esc(ssbskOn() ? t("sched_ssbsk_hint") : t("sched_2014_hint"))}</p>
    </section>
    <h2>${esc(t("privacy"))}</h2>
    <div class="card">
      <span class="field-label">${esc(t("stored"))}</span>
      <ul class="plain">
        <li>${esc(t("notes_confirmed"))}: <strong>${p.confirmed_notes}</strong></li>
        <li>${esc(t("notes_draft"))}: <strong>${p.draft_notes}</strong></li>
        <li>${esc(t("audio_files"))}: <strong>${p.audio_files}</strong></li>
        <li>${esc(t("outbox_privacy"))}: <strong>${queued}</strong></li>
        <li>${esc(t("demo_history"))} <span class="tag sim">SIMULATED</span>: <strong>${p.demo_history_notes}</strong></li>
      </ul>
      <p class="small muted">${esc(t("audio_policy"))}</p>
      <p class="small muted">${esc(t("outbox_policy"))}</p>
      ${S.meta && S.meta.stt.provider === "sarvam" ? `<p class="small">${esc(t("stt_cloud"))}</p>` : ""}
      ${S.meta && S.meta.extractor_cloud ? `<p class="small">${esc(t("llm_cloud").replace("{p}", S.meta.extractor_provider))}</p>` : ""}
      ${NATIVE ? `<p class="small">${esc(t("af_privacy"))}</p>` : ""}
      <span class="field-label">${esc(t("never"))}</span><p class="small">${esc(t("never_list"))}</p>
      <p class="small"><strong>${esc(t("perms"))}</strong></p>
      <div class="row"><button id="export">${esc(t("export_data"))}</button><button class="danger" id="delete">${esc(t("delete_data"))}</button></div>
    </div>
    ${NATIVE ? `<h2>${esc(t("rem_title"))}</h2><section class="card"><p class="small">${esc(t("rem_hint"))}</p>
      <button class="wide ${remindersOn() ? "" : "primary"}" id="rem-toggle">${esc(remindersOn() ? t("rem_disable") : t("rem_enable"))}</button></section>` : ""}
    ${NATIVE ? `<h2>${esc(t("server_title"))}</h2>${serverCard()}` : ""}
    <h2>${esc(t("about"))}</h2>
    <div class="card small">
      <p>${esc(t("speech"))}: <strong>${esc(m.stt.provider)}</strong> (${esc(m.stt.languages.join(", ") || "-")})</p>
      <p>${esc(t("extractor"))}: ${esc(m.extractor.startsWith("llm:") ? t("extractor_llm").replace("{m}", m.extractor.slice(4)) : t("extractor_v"))}</p>
      <p><span class="tag sim">SIMULATED</span> ${esc(t("sim_items"))}</p>
      <p>${esc(t("advisory"))}</p><p>${esc(t("no_gov"))}</p><p>${esc(t("synthetic_only"))}</p>
    </div>
    <button class="wide" id="logout">${esc(t("logout"))}</button>`;
  bindServerCard();
  if ($("#rem-toggle")) $("#rem-toggle").onclick = toggleReminders;
  $("#f-profile").onsubmit = async (e) => {
    e.preventDefault();
    try { S.user = await api("/me", { method: "PATCH", json: { name: e.target.name.value, asha_id: e.target.asha_id.value } }); toast(t("saved")); } catch (err) { fail(err); }
  };
  $("#export").onclick = () => download("/privacy/export", "aura-export.json");
  $("#delete").onclick = async () => {
    if (!confirm(t("delete_q"))) return;
    try {
      await api("/privacy/data", { method: "DELETE" });
      if (NATIVE) { nativeCall("AuraAutofill", "clearVisit").catch(() => {}); scheduleReminders([]); }
      await Outbox.clear(owner()).catch(() => {});
      store.del("aura.cache.home." + owner());
      S.people = null; toast(t("deleted")); viewSettings();
    } catch (e) { fail(e); }
  };
  $("#demo-toggle").onclick = async () => {
    if (demo.active && !confirm(t("demo_remove_q"))) return;
    try {
      await api("/demo", { method: "POST", json: { action: demo.active ? "remove" : "load" } });
      S.people = null; S.tasks = [];
      toast(demo.active ? t("demo_removed") : t("demo_loaded"));
      viewSettings();
    } catch (e) { fail(e); }
  };
  $("#logout").onclick = logout;
}

/* ---- delegated events ---- */
document.addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  const d = b.dataset;
  if (d.copy !== undefined) return copyText(d.copy);
  if (d.copyForm) return copyText(S.formText);
  if (d.shareForm) return shareForm();
  if (d.autofill) return autofillReady();
  if (d.schedule) return setSchedule(d.schedule);
  if (d.personRisk) return togglePersonRisk(d.personRisk);
  if (d.afSettings) return nativeCall("AuraAutofill", "openSettings").catch(fail);
  if (d.afTest) return nativeCall("AuraAutofill", "openTestForm").catch(fail);
  if (d.nav) return go(d.nav, { task: null });
  if (d.uiLang) return setUiLang(d.uiLang);
  if (d.noteLang) { S.noteLang = d.noteLang; return viewRecord(); }
  if (d.taskNote) return go("record", { task: S.tasks.find((x) => x.id === d.taskNote) });
  if (d.taskLater) return taskLater(d.taskLater);
  if (d.taskDismiss) return taskDismiss(d.taskDismiss);
  if (d.openNote) return api(`/notes/${d.openNote}`).then(openNote).catch(fail);
  if (d.pcat) { S.newCat = d.pcat; return viewPeople(); }
  if (d.homeGroup) { store.set("aura.homeGroup", d.homeGroup); return viewHome(); }
  if (d.speak) return speak(d.speak, b);
  if (d.guideNext) { S.guideStep = Math.min((S.guideStep || 0) + 1, guideKeys().length); const g = $("#guide"); if (g) g.innerHTML = guideList(); return; }
  if (d.personDel) {
    if (!confirm(t("delete_person_q"))) return;
    return api(`/beneficiaries/${encodeURIComponent(d.personDel)}`, { method: "DELETE" }).then(() => { S.people = null; viewPeople(); }).catch(fail);
  }
  if (d.outboxSend) { b.disabled = true; b.textContent = t("sending"); return flushOutbox({ manual: true }); }
  if (d.outboxDel) { if (!confirm(t("delete_queued_q"))) return; return Outbox.remove(d.outboxDel).then(viewHome).catch(fail); }
  if (d.example !== undefined) { $("#note-text").value = EXAMPLES[S.noteLang][+d.example]; return $("#note-text").scrollIntoView({ block: "center" }); }
  if (d.rdl) return download(`/reports/monthly?month=${S.reportMonth || todayIso().slice(0, 7)}&format=${d.rdl}&lang=${S.lang}`, `aura-monthly-report-${S.reportMonth || todayIso().slice(0, 7)}.${d.rdl}`);
  if (d.dl) return download(`/reports/claims?month=${S.reportMonth || todayIso().slice(0, 7)}&format=${d.dl}&lang=${S.lang}`, `claim-support-${S.reportMonth || todayIso().slice(0, 7)}.${d.dl}`);
  if (S.view !== "review") return;
  if (b.id === "confirm") return confirmNote();
  if (b.id === "discard") {
    if (!confirm(t("discard_q"))) return;
    return api(`/notes/${S.note.id}/discard`, { method: "POST" }).then(() => go("home", { task: null })).catch(fail);
  }
  if (d.quote) { $("#transcript").innerHTML = highlight(S.note.transcript, d.quote); return $("#transcript").scrollIntoView({ behavior: "smooth", block: "center" }); }
  if (d.scroll) return scrollToPath(d.scroll);
  if (d.danger !== undefined) { S.draft.danger_signs[+d.danger].present = d.val === "1"; return viewReview(); }
  if (d.ref) { S.draft.referral.needed = d.ref === "1"; if (!S.draft.referral.needed) S.draft.referral.facility = null; return viewReview(); }
  if (d.remove) { S.draft[d.remove].splice(+d.i, 1); dropIndexedEvidence(d.remove); return viewReview(); }
  if (d.act === "more-vitals") { S.showAllVitals = true; return viewReview(); }
  if (d.act === "add-service") { S.draft.services_given.push({ type: "VACCINE", detail: null }); return viewReview(); }
  if (d.act === "add-due") { S.draft.next_due.push({ what: "", date: null }); return viewReview(); }
});

/* After removing a list row the quote indexes no longer line up, so hide those quotes. */
function dropIndexedEvidence(list) {
  for (const k of Object.keys(S.note.record.evidence || {})) if (k.startsWith(list + "[")) delete S.note.record.evidence[k];
}

document.addEventListener("change", (e) => {
  const el = e.target;
  if (el.id === "add-danger" && el.value) { S.draft.danger_signs.push({ code: el.value, present: true }); return viewReview(); }
  if (S.view !== "review") return;
  if (el.dataset.bind) {
    const raw = el.value.trim();
    const value = raw === "" ? null : el.dataset.num !== undefined ? Number(raw) : raw;
    setPath(S.draft, el.dataset.bind, value);
    delete S.errors[el.dataset.bind];
    if (el.dataset.rerender !== undefined) return viewReview();
    updateConfirm();
  } else if (el.dataset.list) {
    S.draft[el.dataset.list][+el.dataset.i][el.dataset.key] = el.value.trim() || null;
  }
});

/* ---- Android app only: server address and autofill ---- */
function serverCard() {
  return `<form id="f-server" class="card"><label class="field"><span>${esc(t("server_addr"))}</span>
    <input name="server" inputmode="url" autocomplete="off" value="${esc(serverBase())}"></label>
    <p class="small muted">${esc(t("server_hint"))}</p><button class="wide">${esc(t("save"))}</button></form>`;
}

function bindServerCard() {
  const f = $("#f-server");
  if (!f) return;
  f.onsubmit = (e) => {
    e.preventDefault();
    const v = normaliseServer(f.server.value);
    if (!v) { toast(t("server_bad")); return; }
    store.set("aura.server", v);
    location.reload();
  };
}

/* Android back button (MainActivity calls this). Returns true when it handled the press. */
const BACK_TO = { record: "home", review: "home", saved: "home", form: "saved", people: "home", reports: "home", settings: "home" };
function auraBack() {
  if (!$("#busy").hidden) return true; // a send is in progress: ignore
  const to = BACK_TO[S.view];
  if (!to) return false; // Home / Login: Android puts the app in the background
  if (S.view === "review" && !confirm(t("back_review"))) return true;
  if (S.view === "record" && S.recorder && S.recorder.samples > 0 && !confirm(t("back_recording"))) return true;
  go(to);
  return true;
}

/* Daily visit reminder (Android app, opt-in): a local notification at 8 am with only the NUMBER of visits due —
   no names on the lock screen. Planned from the task list she last loaded; nothing is sent anywhere. */
const REMINDER_IDS = [101, 102, 103];
function remindersOn() { return store.get("aura.reminders") === "1"; }

function localIso(d) { return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10); }

function reminderPlan(tasks, now = new Date()) {
  const first = new Date(now); first.setHours(8, 0, 0, 0);
  if (first <= now) first.setDate(first.getDate() + 1);
  const plan = [];
  for (let i = 0; i < REMINDER_IDS.length; i++) {
    const at = new Date(first); at.setDate(first.getDate() + i);
    const day = localIso(at);
    const n = (tasks || []).filter((x) => x.due_date && x.due_date <= day).length;
    if (n > 0) plan.push({ id: REMINDER_IDS[i], at, n });
  }
  return plan;
}

async function scheduleReminders(tasks) {
  if (!NATIVE) return;
  try {
    await nativeCall("LocalNotifications", "cancel", { notifications: REMINDER_IDS.map((id) => ({ id })) });
    if (!remindersOn()) return;
    const notifications = reminderPlan(tasks).map((r) => ({
      id: r.id, title: "A.U.R.A.", body: t("rem_body").replace("{n}", r.n),
      schedule: { at: r.at.toISOString(), allowWhileIdle: true },
    }));
    if (notifications.length) await nativeCall("LocalNotifications", "schedule", { notifications });
  } catch { /* reminders are a convenience; never block the app */ }
}

async function toggleReminders() {
  if (remindersOn()) {
    store.del("aura.reminders");
    await scheduleReminders([]);
    toast(t("rem_off"));
  } else {
    let r;
    try { r = await nativeCall("LocalNotifications", "requestPermissions"); } catch (e) { return fail(e); }
    if (!r || r.display !== "granted") { toast(t("rem_denied")); return; }
    store.set("aura.reminders", "1");
    await scheduleReminders(S.tasks || []);
    toast(t("rem_on"));
  }
  if (S.view === "settings") viewSettings();
}

async function autofillReady() {
  const f = S.formData;
  if (!f || !S.note) return;
  try {
    const r = await nativeCall("AuraAutofill", "setVisit", autofillPayload(f, S.note.id));
    const st = $("#af-status");
    if (st) st.textContent = (r.serviceEnabled ? t("af_set") : t("af_set_off")).replace("{n}", r.fields);
    toast(t("af_set").replace("{n}", r.fields));
  } catch (e) { fail(e); }
}

/* ---- start ---- */
(async function start() {
  document.documentElement.lang = S.lang;
  /* App shell for opening with no connection. Browsers allow this only on localhost or a trusted HTTPS
     certificate; with the self-signed demo certificate registration fails and the app simply works online. */
  if (!NATIVE && "serviceWorker" in navigator && window.isSecureContext) navigator.serviceWorker.register("sw.js").catch(() => {});
  try {
    S.meta = await api("/meta");
    store.set("aura.cache.meta", JSON.stringify(S.meta));
  } catch {
    // Offline start: if she was logged in before, open Home from the last saved data so she can still record.
    S.meta = JSON.parse(store.get("aura.cache.meta") || "null");
    S.user = JSON.parse(store.get("aura.cache.user") || "null");
    if (S.token && S.meta && S.user) { go("home"); scheduleFlush(); return; }
    busy(false); toast(t("conn_error"));
    if (NATIVE) go("login"); // she can fix the server address there
    return;
  }
  if (S.token) {
    try {
      S.user = await api("/me"); S.lang = S.user.lang; store.set("aura.lang", S.lang);
      store.set("aura.cache.user", JSON.stringify(S.user));
      go("home"); flushOutbox(); scheduleFlush(); return;
    } catch { /* falls through to login */ }
  }
  go("login");
})();
