"""Eval harness (T-025). Text-only for now: transcripts → extractor → validator → names,
scored against ground truth. WER/CER need recordings (T-022) and are reported as NOT MEASURED.

Usage:  uv run --project server python eval/harness.py [--out eval/results/<date>]
"""

from __future__ import annotations

import argparse
import json
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
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    people = load_people()
    notes = load_yaml(Path(args.notes))["notes"]
    set_name = Path(args.notes).stem
    counts = {f: defaultdict(int) for f in SCALARS + SETS}
    by_style = defaultdict(lambda: {f: defaultdict(int) for f in SCALARS + SETS})
    unsupported: list[str] = []
    rows, latencies, crit_ok, flags_err = [], [], [], []
    for n in notes:
        t = time.perf_counter()
        res = process_text(n["transcript"], n["recorded_on"], people)
        latencies.append((time.perf_counter() - t) * 1000)
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
                     "pred": {k: sorted(v) if isinstance(v, set) else v for k, v in pred.items()},
                     "gold": {k: sorted(v) if isinstance(v, set) else v for k, v in gold.items()}})

    total = {k: sum(counts[f][k] for f in counts) for k in ("tp", "fp", "fn")}
    P, R, F = prf(total)
    n_pred = total["tp"] + total["fp"]
    lat = sorted(latencies)
    p95 = lat[max(0, int(round(0.95 * len(lat))) - 1)]
    summary = {
        "date": date.today().isoformat(), "set": set_name, "notes": len(notes),
        "extractor": "rule-based-v0", "stt": "none (text transcripts)",
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
          f"unsupported={summary['unsupported_value_rate']:.3f} p50={lat[len(lat)//2]:.1f}ms → {out}")


def render(s: dict, rows: list[dict]) -> str:
    fm = s["field_micro"]
    lines = [
        f"# Eval report — {s['set']} — {s['date']}",
        "",
        "> **Read this first.** 40 *synthetic, text-only* notes written by the same developer (Claude) who",
        "> wrote the rule-based extractor. This is a **smoke test of the pipeline**, not evidence of",
        "> real-world accuracy. No audio was recorded, so speech-to-text error (WER/CER) is **not measured**.",
        "> Do not put these numbers on a slide without this caveat.",
        "",
        f"- Extractor: `{s['extractor']}` (deterministic, offline) · STT: {s['stt']}",
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
        "| STT WER / CER | **not measured** (no recordings) |",
        "| LLM extractor | **not measured** (no API key) |",
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
    lines += ["", "Raw per-note predictions vs gold: `results.json`.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
