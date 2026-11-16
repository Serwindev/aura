"""Eval harness (T-025). Transcripts → extractor → validator → names, scored against ground truth.

Text mode (default) scores the written transcripts. Audio mode (--audio-dir + --stt) first runs
speech-to-text on <audio-dir>/<note id>.wav and also reports word error rate (WER) against the
written transcript. Test audio so far is AI-voiced (eval/make_tts_audio.py), not field speech.

Usage:  uv run --project server python eval/harness.py [--out eval/results/<date>]
        uv run --project server python eval/harness.py --notes eval/data/notes_holdout.yaml \
            --audio-dir eval/data/audio/notes_holdout --stt sarvam --out eval/results/<date>/audio-sarvam
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from app.core.config import load_yaml  # noqa: E402
from app.extraction.normalize import fold, normalize_for_match  # noqa: E402
from app.pipeline import load_people, process_text  # noqa: E402

_PUNCT = str.maketrans({c: " " for c in ".,;:!?\u0964\u0965\"'()-\u2013\u2014/"})


def _words(text: str) -> list[str]:
    return fold(text.translate(_PUNCT)).split()


def word_errors(ref: str, hyp: str) -> tuple[int, int]:
    """(edit distance in words, reference length). Raw: '2.8' vs 'two point eight' counts as errors."""
    r, h = _words(ref), _words(hyp)
    prev = list(range(len(h) + 1))
    for i, rw in enumerate(r, 1):
        cur = [i] + [0] * len(h)
        for j, hw in enumerate(h, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rw != hw))
        prev = cur
    return prev[-1], len(r)


def _lang(text: str) -> str:
    return "hi" if any("\u0900" <= ch <= "\u097f" for ch in text) else "en"

SCALARS = ["visit_type", "visit_date", "beneficiary_id", "hbnc_day", "hbyc_month", "anc_number",
           "weight_kg", "temp_c", "bp_sys", "bp_dia", "hb_g_dl", "pulse", "resp_rate",
           "referral_needed", "referral_facility"]
SETS = ["danger_signs", "services", "next_due"]
CRITICAL = ["visit_type", "visit_date", "beneficiary_id", "hbnc_day", "hbyc_month", "anc_number",
            "weight_kg", "temp_c", "bp_sys", "bp_dia", "hb_g_dl"]


def gold_view(g: dict) -> dict:
    v = g.get("vitals") or {}
    r = g.get("referral") or {}
    out = {
        "visit_type": g.get("visit_type"), "visit_date": g.get("visit_date"),
        "beneficiary_id": g.get("beneficiary_id"),
        "hbnc_day": g.get("hbnc_day"), "hbyc_month": g.get("hbyc_month"), "anc_number": g.get("anc_number"),
        **{k: v.get(k) for k in ("weight_kg", "temp_c", "bp_sys", "bp_dia", "hb_g_dl", "pulse", "resp_rate")},
        "referral_needed": r.get("needed"), "referral_facility": r.get("facility"),
        "danger_signs": {f"{c}:{p}" for c, p in (g.get("danger_signs") or {}).items()},
        "services": {s if ":" in s else f"{s}:" for s in (g.get("services") or [])},
        "next_due": {str(d) for d in (g.get("next_due") or [])},
    }
    return _canon(out)


def pred_view(rec) -> dict:
    out = {
        "visit_type": rec.visit_type, "visit_date": rec.visit_date,
        "beneficiary_id": rec.beneficiary.matched_id,
        "hbnc_day": rec.visit_index.hbnc_day, "hbyc_month": rec.visit_index.hbyc_month,
        "anc_number": rec.visit_index.anc_number,
        **{k: getattr(rec.vitals, k) for k in ("weight_kg", "temp_c", "bp_sys", "bp_dia", "hb_g_dl", "pulse", "resp_rate")},
        "referral_needed": rec.referral.needed, "referral_facility": rec.referral.facility,
        "danger_signs": {f"{d.code}:{d.present}" for d in rec.danger_signs},
        "services": {f"{s.type}:{s.detail or ''}" for s in rec.services_given},
        "next_due": {str(n.date) for n in rec.next_due if n.date},
    }
    return _canon(out)


def _canon(v: dict) -> dict:
    for k in ("weight_kg", "temp_c", "hb_g_dl"):
        if v[k] is not None:
            v[k] = round(float(v[k]), 2)
    if v["visit_date"] is not None:
        v["visit_date"] = str(v["visit_date"])
    if v["referral_facility"]:
        v["referral_facility"] = normalize_for_match(v["referral_facility"])
    v["services"] = {fold(s) for s in v["services"]}
    return v


def score(gold: dict, pred: dict, counts: dict, unsupported: list) -> dict:
    per_note = {}
    for f in SCALARS:
        g, p = gold[f], pred[f]
        c = counts[f]
        if p is not None and g is not None and p == g:
            c["tp"] += 1
            per_note[f] = True
        else:
            if p is not None:
                c["fp"] += 1
                if g is None:
                    unsupported.append(f)
            if g is not None:
                c["fn"] += 1
            per_note[f] = g == p
    for f in SETS:
        g, p = gold[f], pred[f]
        c = counts[f]
        c["tp"] += len(g & p)
        c["fp"] += len(p - g)
        c["fn"] += len(g - p)
        per_note[f] = g == p
    return per_note


def prf(c: dict) -> tuple[float, float, float]:
    p = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else float("nan")
    r = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else float("nan")
    f = 2 * p * r / (p + r) if p == p and r == r and p + r else float("nan")
    return p, r, f


def pct(x: float) -> str:
    return "n/a" if x != x else f"{x:.2f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "eval" / "results" / date.today().isoformat()))
    ap.add_argument("--notes", default=str(ROOT / "eval" / "data" / "notes.yaml"))
    ap.add_argument("--audio-dir", default=None, help="score speech: <dir>/<note id>.wav")
    ap.add_argument("--stt", default=None, help="sarvam | vosk (with --audio-dir)")
    ap.add_argument("--llm", default=None,
                    help="free LLM provider: ollama | groq | gemini | openai_compat (model etc. from server/.env)")
    args = ap.parse_args()
    llm = None
    if args.llm:
        from app.core.settings import load_dotenv
        from app.extraction.llm import from_env as llm_from_env

        load_dotenv()
        os.environ["LLM_PROVIDER"] = args.llm
        llm = llm_from_env()
        if llm is None:
            raise SystemExit(f"--llm {args.llm}: set LLM_MODEL (and LLM_BASE_URL/LLM_API_KEY if needed) in server/.env")
    stt = None
    if args.audio_dir:
        from app.core.settings import load_dotenv
        from app.stt.providers import get_stt

        load_dotenv()
        stt = get_stt(args.stt)
        if hasattr(stt, "fallback"):
            stt.fallback = None  # measure the provider itself, never a silent fallback
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    people = load_people()
    notes = load_yaml(Path(args.notes))["notes"]
    set_name = Path(args.notes).stem
    counts = {f: defaultdict(int) for f in SCALARS + SETS}
    by_style = defaultdict(lambda: {f: defaultdict(int) for f in SCALARS + SETS})
    unsupported: list[str] = []
    rows, latencies, crit_ok, flags_err = [], [], [], []
    stt_ms, wer_err, wer_len, heard = [], 0, 0, {}
    stt_name = "none (text transcripts)"
    fallbacks = 0
    for n in notes:
        text = n["transcript"]
        if stt is not None:
            wav = (Path(args.audio_dir) / f"{n['id']}.wav").read_bytes()
            lang = _lang(text)
            hints = sorted({nm for p in people for nm in p.names if nm.isascii() == (lang == "en")})
            t = time.perf_counter()
            tr = stt.transcribe(wav, lang, hints=hints)
            stt_ms.append((time.perf_counter() - t) * 1000)
            stt_name = tr.provider
            e, length = word_errors(n["transcript"], tr.text)
            wer_err, wer_len = wer_err + e, wer_len + length
            text = heard[n["id"]] = tr.text
        t = time.perf_counter()
        res = process_text(text, n["recorded_on"], people, llm=llm)
        latencies.append((time.perf_counter() - t) * 1000)
        if llm is not None and "fallback" in res.extractor:
            fallbacks += 1  # scored as-is (rule-based result), but counted so the report says so
        gold, pred = gold_view(n["gold"]), pred_view(res.validation.record)
        per = score(gold, pred, counts, unsupported)
        score(gold, pred, by_style[n["style"]], [])
        ok = all(per[f] for f in CRITICAL)
        crit_ok.append(ok)
        n_err = sum(1 for f in res.validation.flags if f.severity == "error")
        flags_err.append(n_err)
        wrong = sorted(f for f, good in per.items() if not good)
        rows.append({"id": n["id"], "style": n["style"], "tags": n.get("tags", []),
                     "critical_ok": ok, "wrong_fields": wrong, "error_flags": n_err,
                     **({"heard": heard[n["id"]], "said": n["transcript"]} if n["id"] in heard else {}),
                     "pred": {k: sorted(v) if isinstance(v, set) else v for k, v in pred.items()},
                     "gold": {k: sorted(v) if isinstance(v, set) else v for k, v in gold.items()}})

    total = {k: sum(counts[f][k] for f in counts) for k in ("tp", "fp", "fn")}
    P, R, F = prf(total)
    n_pred = total["tp"] + total["fp"]
    lat = sorted(latencies)
    p95 = lat[max(0, int(round(0.95 * len(lat))) - 1)]
    summary = {
        "date": date.today().isoformat(), "set": set_name, "notes": len(notes),
        "extractor": llm.name if llm else "rule-based-v0", "stt": stt_name,
        "llm": ({"provider": llm.provider, "model": llm.model, "cloud": llm.cloud, "calls": len(llm.usage),
                 "fallbacks": fallbacks,
                 "tokens": {k: sum(u[k] for u in llm.usage) for k in ("input", "output")},
                 "call_seconds_p50": statistics.median([u["seconds"] for u in llm.usage]) if llm.usage else None}
                if llm else None),
        "audio": ({"source": "AI voice (Sarvam bulbul:v3 TTS), not field speech",
                   "wer_raw": wer_err / wer_len if wer_len else None,
                   "stt_ms": {"p50": statistics.median(stt_ms), "max": max(stt_ms)}} if stt_ms else None),
        "field_micro": {"precision": P, "recall": R, "f1": F, **total},
        "critical_exact_match_rate": sum(crit_ok) / len(crit_ok),
        "unsupported_value_rate": len(unsupported) / n_pred if n_pred else 0.0,
        "unsupported_fields": sorted(set(unsupported)),
        "latency_ms_text_pipeline": {"p50": statistics.median(lat), "p95": p95},
        "mean_error_flags_per_note": statistics.mean(flags_err),
        "per_field": {f: dict(zip(("precision", "recall", "f1"), prf(counts[f]), strict=True)) | dict(counts[f])
                      for f in counts},
        "by_style": {s: dict(zip(("precision", "recall", "f1"), prf(
            {k: sum(c[f][k] for f in c) for k in ("tp", "fp", "fn")}), strict=True)) for s, c in by_style.items()},
        "machine": f"{platform.system()} {platform.release()}, Python {platform.python_version()}",
    }
    (out / "results.json").write_text(json.dumps({"summary": summary, "notes": rows}, ensure_ascii=False,
                                                 indent=1, default=str), encoding="utf-8")
    (out / "report.md").write_text(render(summary, rows), encoding="utf-8")
    print(f"notes={len(notes)} P={pct(P)} R={pct(R)} F1={pct(F)} "
          f"critical={summary['critical_exact_match_rate']:.2f} "
          f"unsupported={summary['unsupported_value_rate']:.3f} p50={lat[len(lat)//2]:.1f}ms"
          + (f" WER={summary['audio']['wer_raw']:.3f} stt_p50={summary['audio']['stt_ms']['p50']:.0f}ms"
             if summary["audio"] else "")
          + (f" llm={llm.provider}/{llm.model} fallbacks={fallbacks}" if llm else "")
          + f" -> {out}")


def render(s: dict, rows: list[dict]) -> str:
    fm = s["field_micro"]
    a = s.get("audio")
    if a:
        intro = [
            "> **Read this first.** Synthetic notes written by the same developer (Claude) who wrote the",
            f"> rule-based extractor, **spoken by an AI voice** ({a['source']}), then transcribed by `{s['stt']}`.",
            "> AI voices are clean: this tests the audio path end to end, **not field accuracy**. Do not",
            "> put these numbers on a slide without this caveat.",
        ]
        speech_row = ("| STT word error rate (raw: no number/spelling normalisation) / STT time p50, max | "
                      f"{a['wer_raw']:.3f} / {a['stt_ms']['p50'] / 1000:.1f} s, {a['stt_ms']['max'] / 1000:.1f} s |")
    else:
        intro = [
            "> **Read this first.** *Synthetic, text-only* notes written by the same developer (Claude) who",
            "> wrote the rule-based extractor. This is a **smoke test of the pipeline**, not evidence of",
            "> real-world accuracy. Speech-to-text is not part of this run (see the audio reports).",
            "> Do not put these numbers on a slide without this caveat.",
        ]
        speech_row = "| STT WER | not part of this run (text transcripts) |"
    lines = [
        f"# Eval report — {s['set']} — {s['date']}",
        "",
        *intro,
        "",
        f"- Extractor: `{s['extractor']}` "
        + ("(LLM proposal → same code validator)" if s.get("llm") else "(deterministic, offline)")
        + f" · STT: {s['stt']}",
        f"- Machine: {s['machine']}",
        "",
        "## Headline",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Field precision / recall / F1 (micro, {fm['tp']} TP · {fm['fp']} FP · {fm['fn']} FN) | "
        f"{pct(fm['precision'])} / {pct(fm['recall'])} / {pct(fm['f1'])} |",
        f"| Notes with every critical field right | {s['critical_exact_match_rate']:.2f} ({round(s['critical_exact_match_rate'] * s['notes'])}/{s['notes']}) |",
        f"| Unsupported values (filled where gold says nothing was said) | {s['unsupported_value_rate']:.3f} |",
        f"| Text pipeline latency p50 / p95 (extract + validate + names) | {s['latency_ms_text_pipeline']['p50']:.1f} / {s['latency_ms_text_pipeline']['p95']:.1f} ms |",
        f"| Mean error flags per note (shown to the ASHA for review) | {s['mean_error_flags_per_note']:.2f} |",
        speech_row,
        (f"| LLM `{s['llm']['provider']}/{s['llm']['model']}`: tokens in/out · call time p50 · "
         f"fallbacks to rule-based | {s['llm']['tokens']['input']}/{s['llm']['tokens']['output']} · "
         f"{(s['llm']['call_seconds_p50'] or 0):.1f} s · {s['llm']['fallbacks']}/{s['notes']} |"
         if s.get("llm") else "| LLM extractor | not part of this run (rule-based) |"),
        "",
        "## By transcript style",
        "",
        "| Style | P | R | F1 |",
        "|---|---|---|---|",
        *[f"| {k} | {pct(v['precision'])} | {pct(v['recall'])} | {pct(v['f1'])} |" for k, v in s["by_style"].items()],
        "",
        "## Per field",
        "",
        "| Field | TP | FP | FN | P | R | F1 |",
        "|---|---|---|---|---|---|---|",
    ]
    for f, v in s["per_field"].items():
        if v.get("tp", 0) + v.get("fp", 0) + v.get("fn", 0) == 0:
            continue
        lines.append(f"| {f} | {v.get('tp', 0)} | {v.get('fp', 0)} | {v.get('fn', 0)} | "
                     f"{pct(v['precision'])} | {pct(v['recall'])} | {pct(v['f1'])} |")
    lines += ["", "## Notes with errors", "", "| Note | Style | Tags | Wrong fields |", "|---|---|---|---|"]
    for r in rows:
        if r["wrong_fields"]:
            lines.append(f"| {r['id']} | {r['style']} | {', '.join(r['tags'])} | {', '.join(r['wrong_fields'])} |")
    if a:
        lines += ["", "## What was said vs heard", "", "| Note | Said | Heard |", "|---|---|---|"]
        for r in rows:
            lines.append(f"| {r['id']} | {r['said']} | {r['heard']} |")
    lines += ["", "Raw per-note predictions vs gold: `results.json`.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
