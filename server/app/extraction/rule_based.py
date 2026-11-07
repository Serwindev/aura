"""Rule-based extractor (no API key, fully offline). Produces the SAME raw shape an LLM would
(fields + evidence quotes) and goes through the same validator. It is the v1 default until an
LLM key exists, and later the offline fallback / baseline in the bake-off.

Works on clean text (punctuation, digits) and on raw ASR output (no punctuation, number words).
Known weak spots (by design, measured in eval): self-corrections ("2.5 नहीं नहीं 2.7"), several
people in one note, free-text referral reasons, anything phrased outside the cue lists.
"""

from __future__ import annotations

import re
from datetime import date

from .dates_hi import iter_date_phrases
from .names import Person, resolve_beneficiary
from .normalize import (
    _ordinal_value,
    extract_quantities,
    find_bp,
    fold,
    fold_pattern,
    fold_with_map,
    weight_kg_candidates,
)

_L = r"a-z0-9ऀ-ॿ"
_B = rf"(?<![{_L}])"
_E = rf"(?![{_L}])"


def _rx(pattern: str, prefix: bool = False) -> re.Pattern:
    tail = rf"[{_L}]*" if prefix else _E  # prefix cues still quote the whole word
    return re.compile(_B + "(?:" + fold_pattern(pattern) + ")" + tail)


VISIT_TYPES = [  # priority order
    ("HBNC", _rx(r"hbnc|एचबीएनसी|नवजात|newborn")),
    ("HBYC", _rx(r"hbyc|एचबीवाईसी")),
    ("ANC", _rx(r"anc|एएनसी|गर्भवती|प्रसव पूर्व|pregnant|antenatal")),
    ("PNC", _rx(r"pnc|पीएनसी|प्रसव के बाद")),
    ("IMMUNIZATION", _rx(r"टीका|टीके|टीकाकरण|vaccin|tika|teeka|teekakaran|tikakaran", prefix=True)),
    ("FAMILY_PLANNING", _rx(r"परिवार नियोजन|family planning|कंडोम|condom|कॉपर टी|अंतरा")),
    ("TB_FOLLOWUP", _rx(r"टीबी|tb|क्षय रोग")),
    ("NCD_FOLLOWUP", _rx(r"शुगर|डायबिटीज|ncd|diabetes")),
]

VITAL_CUES = {
    "weight_kg": _rx(r"वजन|weight|वेट"),
    "temp_c": _rx(r"तापमान|temperature|temp|टेम्परेचर|बुखार|bukhar|fever"),
    "bp": _rx(r"बीपी|bp|ब्लड प्रेशर|blood pressure|रक्तचाप"),
    "hb_g_dl": _rx(r"एचबी|hb|हीमोग्लोबिन|haemoglobin|hemoglobin"),
    "pulse": _rx(r"पल्स|नब्ज|नाडी|pulse|धडकन"),
    "resp_rate": _rx(r"सांस की दर|श्वसन दर|breathing rate|respiratory rate"),
}

# (code by group, pattern, negatable). Groups: newborn (HBNC), child (HBYC/IMMUNIZATION),
# mother (ANC/PNC). A positive-by-construction cue ("दूध नहीं पी") is not negatable.
DANGER_CUES: list[tuple[dict[str, str], re.Pattern, bool, bool | None]] = [
    ({"newborn": "NB_NOT_FEEDING", "child": "CH_UNABLE_TO_DRINK"},
     _rx(r"दूध (ठीक से )?नहीं पी|स्तनपान नहीं|not feeding|doodh nahi pi", prefix=True), False, True),
    ({"newborn": "NB_NOT_FEEDING", "child": "CH_UNABLE_TO_DRINK"},
     _rx(r"दूध (ठीक से )?पी (रहा|रही)|feeding well|doodh (theek se )?pi (raha|rahi)"), False, False),
    ({"newborn": "NB_FEVER", "mother": "M_HIGH_FEVER"}, _rx(r"बुखार|fever|bukhar"), True, None),
    ({"newborn": "NB_JAUNDICE"}, _rx(r"पीलिया|jaundice|peeliya|आंखें पीली|त्वचा पीली"), True, None),
    ({"newborn": "NB_CONVULSIONS", "child": "CH_CONVULSIONS", "mother": "M_CONVULSIONS"},
     _rx(r"झटके|दौरे पड|दौरा पड|convulsion|fits|jhatke", prefix=True), True, None),
    ({"newborn": "NB_FAST_BREATHING", "child": "CH_FAST_BREATHING"},
     _rx(r"तेज सांस|सांस तेज|fast breathing|tez saans|saans tez"), True, None),
    ({"newborn": "NB_COLD"}, _rx(r"(शरीर|बच्चा|बच्ची) ठंडा|ठंडा लग|body cold|hypothermia"), True, None),
    ({"newborn": "NB_LETHARGIC", "child": "CH_LETHARGIC"}, _rx(r"सुस्त|बेहोश|lethargic|sust"), True, None),
    ({"newborn": "NB_CORD_INFECTION"}, _rx(r"नाल[^।.]{0,25}?(मवाद|लाली|लाल|पस)|cord[^.]{0,20}?(pus|red)"), True, None),
    ({"newborn": "NB_SKIN_PUSTULES"}, _rx(r"फुंसी|फुंसियां|pustule", prefix=True), True, None),
    ({"newborn": "NB_CHEST_INDRAWING"}, _rx(r"छाती (धंस|अंदर)|chest indrawing"), True, None),
    ({"mother": "M_HEAVY_BLEEDING"}, _rx(r"(ज्यादा|अधिक|बहुत) (खून|रक्तस्राव)|heavy bleeding"), True, None),
    ({"mother": "M_SWELLING"}, _rx(r"सूजन|swelling"), True, None),
    ({"mother": "M_SEVERE_HEADACHE"}, _rx(r"सिर ?(में )?दर्द|सरदर्द|धुंधला|headache|blurred"), True, None),
    ({"mother": "M_FOUL_DISCHARGE"}, _rx(r"बदबूदार|foul"), True, None),
    ({"mother": "M_REDUCED_FETAL_MOVEMENT"},
     _rx(r"(बच्चे की )?हलचल कम|बच्चा कम हिल|reduced (fetal )?movement"), True, None),
    ({"mother": "M_BREATHLESSNESS"}, _rx(r"सांस फूल|breathless"), True, None),
    ({"child": "CH_VOMITS_EVERYTHING"}, _rx(r"सब कुछ उल्टी|उल्टी|vomit", prefix=True), True, None),
    ({"child": "CH_DIARRHOEA_DEHYDRATION"}, _rx(r"दस्त|diarrh", prefix=True), True, None),
]
_GROUP = {"HBNC": "newborn", "HBYC": "child", "IMMUNIZATION": "child", "ANC": "mother", "PNC": "mother"}

VACCINES = [  # (canonical, pattern)
    ("BCG", r"bcg|बीसीजी"), ("OPV", r"opv|ओपीवी|पोलियो|polio"), ("Penta", r"penta|पेंटा"),
    ("Rota", r"rota|रोटा"), ("PCV", r"pcv|पीसीवी"), ("fIPV", r"fipv|ipv|आईपीवी|एफआईपीवी"),
    ("MR", r"mr|एमआर|खसरा|खसरे"), ("Hep B", r"hep b|hepatitis b|हेपेटाइटिस( बी)?|हेप बी"),
    ("DPT", r"dpt|डीपीटी"), ("JE", r"je|जेई"), ("Vitamin A", r"vitamin a|विटामिन ए"),
    ("TT", r"tt|td|टीटी|टिटनेस"),
]
_VACCINE_RX = [(name, _rx(p)) for name, p in VACCINES]
SERVICE_CUES = [
    ("IFA", _rx(r"आयरन|ifa|आईएफए|फोलिक|iron"), True),
    ("CALCIUM", _rx(r"कैल्शियम|calcium"), True),
    ("ORS", _rx(r"ओआरएस|ors"), True),
    ("ZINC", _rx(r"जिंक|zinc"), True),
    ("COUNSELLING", _rx(r"समझाया|सलाह|परामर्श|counsel|samjhaya|salah", prefix=True), False),
]
OTHER_SERVICE_CUES = [("Condom", _rx(r"कंडोम|condom", prefix=True))]
GIVEN = {fold(w) for w in ["दी", "दीं", "दिया", "दिए", "दिये", "दी_गई", "लगाया", "लगाए", "लगा", "लगवाया", "लगवाए", "पिलाया", "पिलाई", "पिलाए", "खिलाई", "खिलाया", "दिलाया", "दिलवाया", "given", "gave", "diya", "diye", "di", "lagaya", "lagaye", "pilaya"]}
FUTURE = {fold(w) for w in ["अगली", "अगला", "अगले", "लगेगा", "लगेंगे", "लगेगी", "देना", "लगना", "बाकी", "next", "agla", "agli", "agle"]}
NEGATION = {fold(w) for w in ["नहीं", "नही", "ना", "न", "no", "not", "nahi", "nahin", "koi_nahi"]}
NEXT_CUES = {fold(w) for w in ["अगली", "अगला", "अगले", "दोबारा", "फिर", "next", "agla", "agli", "agle", "dobara", "phir", "again"]}
STOP_VERBS = {fold(w) for w in ["था", "थी", "थे", "है", "हैं", "हो", "चुका", "चुकी", "हुआ", "हुई", "गया", "गई", "was", "is", "had"]}
CONJ = {fold(w) for w in ["और", "लेकिन", "पर", "मगर", "aur", "lekin", "par", "but", "and"]}
REFERRAL_RX = _rx(r"रेफर|refer|भेजा|भेज दिया|भेजने|bheja", prefix=True)
FACILITY_RX = _rx(r"phc|पीएचसी|chc|सीएचसी|जिला अस्पताल|district hospital|sncu|एसएनसीयू|fru|"
                  r"एफआरयू|मेडिकल कॉलेज|medical college|उपकेंद्र|sub ?centre|पीएमएसएमए")
ANC_NO_RX = _rx(r"(पहली|पहला|दूसरी|दूसरा|तीसरी|तीसरा|चौथी|चौथा|first|second|third|fourth) "
                r"(anc|एएनसी|जांच|checkup|चेकअप)|(anc|एएनसी) ?[0-9]")
_BOUNDARY_RX = re.compile(r"[।॥?!\n;]|\.(?![0-9])")


class _Text:
    def __init__(self, text: str):
        self.text = text
        self.folded, self.idx = fold_with_map(text)

    def span(self, a: int, b: int) -> tuple[int, int]:
        return self.idx[a], self.idx[b - 1] + 1

    def find(self, rx: re.Pattern):
        for m in rx.finditer(self.folded):
            yield (*self.span(m.start(), m.end()), m)


def _window(text: str, start: int, end: int, max_tokens: int, comma: bool, conj: bool) -> tuple[int, int]:
    """Extend [start, end) to the enclosing clause: stop at sentence punctuation (and commas /
    conjunctions if asked) or after max_tokens tokens each side."""
    bound = re.compile(_BOUNDARY_RX.pattern + (r"|," if comma else ""))
    left = start
    seg = text[:start]
    cut = max((m.end() for m in bound.finditer(seg)), default=0)
    words = list(re.finditer(r"\S+", seg[cut:]))
    words = words[-max_tokens:] if max_tokens else words
    if conj:
        for k in range(len(words) - 1, -1, -1):
            if fold(words[k].group()) in CONJ:
                words = words[k + 1:]
                break
    left = cut + words[0].start() if words else start
    seg = text[end:]
    m = bound.search(seg)
    stop = m.start() if m else len(seg)
    words = list(re.finditer(r"\S+", seg[:stop]))[:max_tokens]
    if conj:
        for k, w in enumerate(words):
            if fold(w.group()) in CONJ:
                words = words[:k]
                break
    right = end + (words[-1].end() if words else 0)
    return left, right


def _clause_tokens(text: str, a: int, b: int) -> list[str]:
    return [fold(w) for w in re.findall(r"[A-Za-zऀ-ॣॱ-ॿ]+", text[a:b])]


def _quote(text: str, a: int, b: int) -> str:
    return text[a:b].strip(" ,;:-")


def extract(transcript: str, recorded_on: date, people: list[Person] | None = None) -> dict:
    """Return a raw record dict (LLM-shaped, with evidence) for validate_extraction()."""
    T = _Text(transcript)
    text = transcript
    raw: dict = {"schema_version": "0.1", "evidence": {}}
    ev = raw["evidence"]

    def put(path: str, value, a: int, b: int, conf: float = 0.7) -> None:
        q = _quote(text, a, b)
        if not q:
            return
        parts = path.split(".")
        cur = raw
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = value
        ev[path] = {"quote": q, "confidence": conf}

    # visit type
    vt = None
    for name, rx in VISIT_TYPES:
        hit = next(T.find(rx), None)
        if hit:
            vt = name
            put("visit_type", name, hit[0], hit[1])
            break

    # beneficiary mention (the id itself is set later by code, after validation)
    if people:
        nm = resolve_beneficiary(text, people, vt)
        if nm:
            put("beneficiary.mention", text[nm.start:nm.end], nm.start, nm.end, nm.confidence)

    _visit_index(T, vt, put)
    _vitals(T, put)
    _danger(T, vt, raw)
    _services(T, raw)
    _referral(T, put)
    _dates(T, recorded_on, raw, put, vt)
    return raw


def _visit_index(T: _Text, vt: str | None, put) -> None:
    text = T.text
    if vt == "HBNC":
        for a, b, _m in T.find(_rx(r"दिन|din|day")):
            # "day 7" / "दिन 7" after, or "तीसरे दिन" / "7वें दिन" / "7th day" before
            after = re.match(r"\s*([0-9]+)", text[b:])
            if after and fold(text[a:b]) in ("day", "दिन"):
                put("visit_index.hbnc_day", int(after.group(1)), a, b + after.end())
                return
            before = text[:a].rstrip()
            mw = re.search(r"([0-9]+)\s*(?:वें|वां|वीं|th|st|nd|rd)?$|(\S+)$", before)
            nxt = fold(text[b:].split()[0]) if text[b:].split() else ""
            if mw is None or nxt in {fold(w) for w in ["बाद", "पहले", "में", "से", "baad", "pehle", "mein", "se"]}:
                continue
            if mw.group(1):
                if re.search(r"(वें|वां|वीं|th|st|nd|rd)$", before):
                    put("visit_index.hbnc_day", int(mw.group(1)), mw.start() + 0, b)
                    return
                continue
            ov = _ordinal_value(fold(mw.group(2)))
            if ov is not None:
                put("visit_index.hbnc_day", ov, mw.start(2), b)
                return
    if vt == "HBYC":
        for a, b, _m in T.find(_rx(r"महीने|माह|month|months|mahine")):
            before = text[:a].rstrip()
            mw = re.search(r"([0-9]+)$|(\S+)$", before)
            if not mw:
                continue
            if mw.group(1):
                put("visit_index.hbyc_month", int(mw.group(1)), mw.start(1), b)
                return
            ov = _ordinal_value(fold(mw.group(2)))
            if ov is None:
                qs = extract_quantities(mw.group(2))
                ov = int(qs[0].value) if qs else None
            if ov is not None:
                put("visit_index.hbyc_month", ov, mw.start(2), b)
                return
    if vt == "ANC":
        hit = next(T.find(ANC_NO_RX), None)
        if hit:
            qs = extract_quantities(text[hit[0]:hit[1]])
            if qs:
                put("visit_index.anc_number", int(qs[0].value), hit[0], hit[1])


def _vitals(T: _Text, put) -> None:
    text = T.text
    for fld, rx in VITAL_CUES.items():
        for a, b, _ in T.find(rx):
            stop = _BOUNDARY_RX.search(text, b)
            window_end = min(stop.start() if stop else len(text), b + 45)
            seg = text[b:window_end]
            if fld == "bp":
                bps = find_bp(seg)
                if bps:
                    e = b + bps[0].end
                    put("vitals.bp_sys", bps[0].systolic, a, e)
                    put("vitals.bp_dia", bps[0].diastolic, a, e)
                    break
                continue
            qs = [q for q in extract_quantities(seg) if not q.ordinal]
            # the number must come before any other vital's keyword
            other = [m.start() for f2, r2 in VITAL_CUES.items() if f2 != fld
                     for m in r2.finditer(fold(seg))]
            if other:
                qs = [q for q in qs if q.start < min(other)]
            if not qs:
                continue
            q = qs[0]
            # weight: "2 किलो 800 ग्राम" was merged into one kg value by the normaliser
            val = weight_kg_candidates(seg[: q.end])[-1] if fld == "weight_kg" else q.value
            if fld in ("pulse", "resp_rate"):
                val = int(val)
            put(f"vitals.{fld}", val, a, b + q.end)
            break


def _danger(T: _Text, vt: str | None, raw: dict) -> None:
    group = _GROUP.get(vt or "")
    if not group:
        return
    text = T.text
    seen: set[str] = set()
    for codes, rx, negatable, fixed in DANGER_CUES:
        code = codes.get(group)
        if not code or code in seen:
            continue
        hit = next(T.find(rx), None)
        if not hit:
            continue
        a, b, _ = hit
        ca, cb = _window(text, a, b, 5, comma=True, conj=True)
        present = fixed if fixed is not None else not (
            negatable and set(_clause_tokens(text, ca, cb)) & NEGATION)
        i = len(raw.setdefault("danger_signs", []))
        raw["danger_signs"].append({"code": code, "present": present})
        raw["evidence"][f"danger_signs[{i}]"] = {"quote": _quote(text, ca, cb), "confidence": 0.7}
        seen.add(code)


def _services(T: _Text, raw: dict) -> None:
    text = T.text
    items: list[tuple[int, dict, tuple[int, int]]] = []

    def given(a: int, b: int) -> tuple[int, int] | None:
        """Scan right from the mention to its verb (Hindi is verb-final): a 'given' verb before
        any negation, future word, other verb/auxiliary or sentence end → given."""
        stop = _BOUNDARY_RX.search(text, b)
        end_limit = stop.start() if stop else len(text)
        for k, m in enumerate(re.finditer(r"\S+", text[b:end_limit])):
            if k >= 14:
                break
            w = fold(re.sub(r"[^\wऀ-ॿ]", "", m.group()))
            if w in GIVEN:
                return a, b + m.end()
            if w in NEGATION or w in FUTURE or w in STOP_VERBS:
                return None
        # Hinglish can put the verb first ("vaccine lagaya - Penta 2"): look a few words left
        sent_start = max((m.end() for m in _BOUNDARY_RX.finditer(text, 0, a)), default=0)
        lo = max(sent_start, a - 80)
        left = list(re.finditer(r"\S+", text[lo:a]))[-8:]
        for m in reversed(left):
            w = fold(re.sub(r"[^\wऀ-ॿ]", "", m.group()))
            if w in NEGATION or w in FUTURE or w in STOP_VERBS:
                return None
            if w in GIVEN:
                return lo + m.start(), b
        return None

    for name, rx in _VACCINE_RX:
        for a, b, _ in T.find(rx):
            span = given(a, b)
            if not span:
                continue
            items.append((a, {"type": "VACCINE", "detail": _dose_detail(name, text[b:b + 25])}, span))
            break
    for typ, rx, needs_given in SERVICE_CUES:
        for a, b, _ in T.find(rx):
            span = given(a, b) if needs_given else _window(text, a, b, 6, comma=False, conj=False)
            if span:
                items.append((a, {"type": typ, "detail": None}, span))
                break
    for detail, rx in OTHER_SERVICE_CUES:
        for a, b, _ in T.find(rx):
            span = given(a, b)
            if span:
                items.append((a, {"type": "OTHER", "detail": detail}, span))
                break
    items.sort(key=lambda x: x[0])
    for i, (_, item, (ca, cb)) in enumerate(items):
        raw.setdefault("services_given", []).append(item)
        raw["evidence"][f"services_given[{i}]"] = {"quote": _quote(text, ca, cb), "confidence": 0.7}


def _dose_detail(name: str, after: str) -> str:
    """'पेंटा 2' / 'पेंटा का दूसरा' / 'पोलियो दो' → 'Penta-2'; nothing number-like → 'Penta'."""
    m = re.match(r"\s*(?:(?:का|की|के|ka|ki|ke)\s+)?(\S+)", after)
    if not m:
        return name
    tok = re.sub(r"[^\wऀ-ॿ]", "", m.group(1))
    if not tok:
        return name
    if tok.isdigit():
        return f"{name}-{int(tok)}"
    n = fold(tok)
    v = _ordinal_value(n)
    if v is None:
        qs = extract_quantities(tok)
        v = int(qs[0].value) if qs and not qs[0].unit else None
    return f"{name}-{v}" if v is not None else name


def _referral(T: _Text, put) -> None:
    text = T.text
    hit = next(T.find(REFERRAL_RX), None)
    if not hit:
        return
    a, b, _ = hit
    ca, cb = _window(text, a, b, 6, comma=True, conj=True)
    needed = not (set(_clause_tokens(text, ca, cb)) & NEGATION)
    put("referral.needed", needed, ca, cb)
    if needed:
        fac = None
        for fa, fb, _ in _Text(text[ca:cb]).find(FACILITY_RX):
            fac = (ca + fa, ca + fb)
            break
        if fac:
            put("referral.facility", text[fac[0]:fac[1]], fac[0], fac[1])


def _dates(T: _Text, recorded_on: date, raw: dict, put, vt: str | None) -> None:
    text = T.text
    toks = [(m.start(), m.end(), fold(m.group())) for m in re.finditer(r"\S+", text)]

    def near_next_cue(a: int, b: int) -> bool:
        idx = [k for k, (s, e, _) in enumerate(toks) if s < b and e > a]
        if not idx:
            return False
        lo, hi = max(0, idx[0] - 5), min(len(toks), idx[-1] + 2)
        return any(re.sub(r"[^\wऀ-ॿ]", "", t[2]) in NEXT_CUES for t in toks[lo:hi])

    visit_done = False
    due_i = 0
    past = list(iter_date_phrases(text, recorded_on, "past"))
    future = {(a, b): d for d, a, b in iter_date_phrases(text, recorded_on, "future")}
    for d_past, a, b in past:
        if near_next_cue(a, b):
            d = future.get((a, b), d_past)
            raw.setdefault("next_due", []).append({"what": _due_what(text, vt), "date": d.isoformat()})
            raw["evidence"][f"next_due[{due_i}]"] = {"quote": _quote(text, a, b), "confidence": 0.7}
            due_i += 1
        elif not visit_done and d_past <= recorded_on:
            put("visit_date", d_past.isoformat(), a, b)
            visit_done = True


def _due_what(text: str, vt: str | None) -> str:
    if vt == "IMMUNIZATION":
        return "next vaccine"
    if vt:
        return f"next {vt} visit"
    return "next visit"
