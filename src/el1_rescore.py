#!/usr/bin/env python3
"""Reconstruct EL1 call rows from filesystem and run scoring for completed models."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from local_event_first import (
    EL_COMPACT, EL_E1E2, EL_MICRO,
    _summarize_condition, score_el_rows, write_csv,
)
from model_expansion import mean_present, to_float
from model_registry import DEFAULT_REGISTRY

CALLS_DIR = Path("runs/local_event_first/el1_dev_pilot/calls")
OUTPUT_DIR = Path("runs/local_event_first/el1_dev_pilot")
EXECT_ROOT = Path("data/ExECT 2 (2025)/Gold1-200_corrected_spelling")
MARKUP_ROOT = Path("data/ExECT 2 (2025)/MarkupOutput_200_SyntheticEpilepsyLetters")
SCHEMA = Path("schemas/canonical_extraction.schema.json")

SKIP_MODELS = {"qwen_4b_local", "qwen_27b_local"}

rows: list[dict] = []
for model_dir in sorted(CALLS_DIR.iterdir()):
    model = model_dir.name
    if model in SKIP_MODELS:
        continue
    for harness_dir in sorted(model_dir.iterdir()):
        harness = harness_dir.name
        for doc_dir in sorted(harness_dir.iterdir()):
            doc_id = doc_dir.name
            payload_path = doc_dir / "h6_payload.json"
            prov_path = doc_dir / "provider_response.json"
            if not prov_path.exists():
                prov_path = doc_dir / "e1_provider_response.json"
            latency_ms: float = 0.0
            if prov_path.exists():
                try:
                    pdata = json.loads(prov_path.read_text(encoding="utf-8"))
                    latency_ms = float(pdata.get("latency_ms") or 0)
                except Exception:
                    pass
            rows.append({
                "model_label": model,
                "harness_id": harness,
                "document_id": doc_id,
                "status": "success" if payload_path.exists() else "error",
                "parse_success": "True" if payload_path.exists() else "False",
                "latency_ms": latency_ms,
                "h6_payload_path": str(payload_path) if payload_path.exists() else None,
                "e1_event_count": None,
            })

print(f"Reconstructed {len(rows)} rows")
for model in sorted(set(r["model_label"] for r in rows)):
    for harness in sorted(set(r["harness_id"] for r in rows if r["model_label"] == model)):
        n = sum(1 for r in rows if r["model_label"] == model and r["harness_id"] == harness)
        ok = sum(1 for r in rows if r["model_label"] == model and r["harness_id"] == harness and r["parse_success"] == "True")
        print(f"  {model} / {harness}: {ok}/{n} parse ok")

write_csv(OUTPUT_DIR / "call_report.csv", rows)
print("call_report.csv written")

scores = score_el_rows(rows, OUTPUT_DIR, EXECT_ROOT, MARKUP_ROOT, SCHEMA, DEFAULT_REGISTRY)
print(f"Scored {len(scores)} conditions")

by_condition: dict = {}
for row in rows:
    key = (row["model_label"], row["harness_id"])
    by_condition.setdefault(key, []).append(row)

summaries = [
    _summarize_condition(model, harness, crows, scores.get((model, harness)))
    for (model, harness), crows in sorted(by_condition.items())
]
write_csv(OUTPUT_DIR / "comparison_table.csv", summaries)

H6_BASELINES = {
    "qwen_9b_local":  {"med": 0.839, "sz": 0.602, "dx": 0.825},
    "gemma_4b_local": {"med": 0.849, "sz": 0.593, "dx": 0.825},
    "qwen_35b_local": {"med": 0.852, "sz": 0.593, "dx": 0.800},
}

print("\n=== EL1 COMPARISON TABLE ===")
print(f"{'model':22s} {'harness':20s} {'parse':5s} {'med_f1':7s} {'sz_f1c':7s} {'dx_acc':7s} {'lat_s':6s} {'scoring'}")
print("-" * 95)
for s in summaries:
    med = s.get("medication_name_f1")
    sz = s.get("seizure_type_f1_collapsed")
    dx = s.get("epilepsy_diagnosis_accuracy")
    lat = (to_float(s.get("mean_latency_ms")) or 0) / 1000
    parse_r = to_float(s.get("parse_success_rate")) or 0
    scoring = s.get("scoring_status", "?")
    base = H6_BASELINES.get(s["model_label"], {})
    delta = ""
    if sz is not None and base.get("sz") is not None:
        diff = sz - base["sz"]
        delta = f"({diff:+.3f})" if abs(diff) >= 0.01 else ""
    print(
        f"{s['model_label']:22s} {s['harness_id']:20s} "
        f"{parse_r:.2f}  "
        f"{(med or 0):.3f}  {(sz or 0):.3f}{delta:10s}  "
        f"{(dx or 0):.3f}  {lat:5.1f}s  {scoring}"
    )

print("\n=== FLAGS: seizure_type_f1_collapsed >= +0.03 vs H6 baseline ===")
flagged = []
for s in summaries:
    sz = s.get("seizure_type_f1_collapsed")
    base = H6_BASELINES.get(s["model_label"], {}).get("sz")
    if sz is not None and base is not None and (sz - base) >= 0.03:
        flagged.append(s)
        print(f"  *** {s['model_label']} / {s['harness_id']}: sz_f1c={sz:.3f} vs baseline={base:.3f} (+{sz-base:.3f})")
if not flagged:
    print("  None met the +0.03 threshold on this 10-doc development subset.")

print(f"\ncomparison_table.csv written to {OUTPUT_DIR}")
