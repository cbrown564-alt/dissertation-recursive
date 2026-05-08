#!/usr/bin/env python3
"""Generate static seizure-frequency review workbench bundles.

The workbench is intentionally archive-friendly: each command writes a
standalone HTML page plus the normalized JSON/CSV data needed to audit a run.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evaluate import (
    DEFAULT_DIRECT_RUN_DIR,
    DEFAULT_EVENT_RUN_DIR,
    DEFAULT_MARKUP_ROOT,
    DEFAULT_RECOVERY_RUN_DIR,
    evidence_overlaps_gold,
    extraction_path,
    flatten_summary,
    gold_frequency_part_candidates,
    load_gold,
    load_json,
)
from gan_frequency import (
    DEFAULT_GAN_PATH,
    classification_report,
    label_to_categories,
    load_gan_examples,
    normalize_label,
)
from intake import DEFAULT_EXECT_ROOT, DEFAULT_SPLITS, read_text
from normalization import parse_frequency_expression


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{ color-scheme: light; --ink:#17202a; --muted:#667085; --line:#d8dee8; --bg:#f6f7f9; --panel:#fff; --soft:#fcfcfd; --gold:#ffe58a; --pred:#9be7c4; --both:#b9a7ff; --fail:#b42318; --pass:#067647; --warn:#b54708; }}
body {{ margin:0; font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--ink); background:var(--bg); }}
header {{ position:sticky; top:0; z-index:5; background:#ffffffef; backdrop-filter:blur(8px); border-bottom:1px solid var(--line); padding:16px 24px; }}
h1 {{ margin:0 0 8px; font-size:22px; letter-spacing:0; }}
h2 {{ margin:0; font-size:18px; }} h3 {{ margin:0 0 10px; font-size:14px; }} p {{ margin:4px 0; }}
main {{ max-width:1320px; margin:0 auto; padding:20px; }}
.summary, .filters, .legend {{ display:flex; gap:10px; flex-wrap:wrap; align-items:center; }}
.summary span, .key {{ color:var(--muted); background:#fff; border:1px solid var(--line); border-radius:6px; padding:4px 8px; }}
.summary b {{ color:var(--ink); }}
.filters {{ margin-top:12px; }}
input, select, button {{ font:inherit; border:1px solid var(--line); border-radius:6px; background:#fff; color:var(--ink); padding:6px 8px; }}
button {{ cursor:pointer; }}
.layout {{ display:grid; grid-template-columns:360px minmax(0,1fr); gap:18px; align-items:start; }}
.case-list {{ position:sticky; top:120px; max-height:calc(100vh - 140px); overflow:auto; border:1px solid var(--line); background:#fff; border-radius:8px; }}
table {{ width:100%; border-collapse:collapse; }} th, td {{ border-bottom:1px solid var(--line); padding:8px; text-align:left; vertical-align:top; }} th {{ position:sticky; top:0; background:#fff; z-index:1; color:var(--muted); font-size:12px; }}
tr.case-row {{ cursor:pointer; }} tr.case-row:hover {{ background:#f2f4f7; }} tr.active {{ outline:2px solid #344054; outline-offset:-2px; }}
.case {{ display:none; background:var(--panel); border:1px solid var(--line); border-left-width:5px; border-radius:8px; margin:0 0 16px; overflow:hidden; }}
.case.visible {{ display:block; }} .case.fail {{ border-left-color:var(--fail); }} .case.pass {{ border-left-color:var(--pass); }} .case.warn {{ border-left-color:var(--warn); }}
.case.fixed {{ outline:2px solid var(--pass); }} .case.regressed {{ outline:2px solid var(--fail); }}
.case-head {{ display:flex; justify-content:space-between; gap:16px; padding:14px 16px; border-bottom:1px solid var(--line); }}
.badge {{ display:inline-block; font-weight:700; font-size:12px; padding:3px 7px; border-radius:5px; color:#fff; white-space:nowrap; }} .badge.fail {{ background:var(--fail); }} .badge.pass {{ background:var(--pass); }} .badge.warn {{ background:var(--warn); }}
.grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; padding:14px 16px; }}
.grid.three {{ grid-template-columns:repeat(3,minmax(0,1fr)); }}
.panel {{ border:1px solid var(--line); border-radius:8px; padding:12px; background:var(--soft); min-width:0; }}
dl {{ display:grid; grid-template-columns:120px minmax(0,1fr); gap:6px 10px; margin:0; }} dt {{ color:var(--muted); }} dd {{ margin:0; overflow-wrap:anywhere; }}
code {{ background:#eef1f5; padding:1px 4px; border-radius:4px; white-space:pre-wrap; overflow-wrap:anywhere; }}
.muted, .empty {{ color:var(--muted); }}
details {{ border-top:1px solid var(--line); }} summary {{ cursor:pointer; padding:12px 16px; font-weight:650; }}
.letter {{ white-space:pre-wrap; margin:0; padding:0 16px 16px; font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; overflow:auto; }}
mark {{ padding:1px 2px; border-radius:3px; }} mark.gold {{ background:var(--gold); }} mark.pred {{ background:var(--pred); }} mark.both {{ background:var(--both); }}
.examples {{ columns:2 280px; }}
.hidden {{ display:none !important; }}
@media (max-width: 980px) {{ header {{ position:static; }} .layout, .grid, .grid.three {{ grid-template-columns:1fr; }} .case-list {{ position:static; max-height:none; }} }}
</style>
</head>
<body>
<header>
  <h1>{heading}</h1>
  <div class="summary">{summary_badges}</div>
  <div class="filters">
    <input id="search" placeholder="Search document ID or text" aria-label="Search document ID or text">
    <select id="outcome"><option value="">all outcomes</option><option value="pass">pass</option><option value="fail">miss</option></select>
    <select id="failure"><option value="">all failure modes</option>{failure_options}</select>
    <select id="delta"><option value="">all deltas</option><option value="fixed">fixed</option><option value="regressed">regressed</option><option value="both_miss">both miss</option><option value="both_miss_same_prediction">both miss, same prediction</option><option value="both_correct">both correct</option></select>
    <button id="prevMiss" type="button">Prev miss</button><button id="nextMiss" type="button">Next miss</button>
  </div>
</header>
<main>
  <div class="legend"><span class="key"><mark class="gold">gold span</mark></span><span class="key"><mark class="pred">prediction evidence</mark></span><span class="key"><mark class="both">overlap</mark></span></div>
  <section class="panel">
    <h3>Error Mode Summary</h3>
    <div class="examples">{error_summary}</div>
  </section>
  <div style="height:16px"></div>
  <div class="layout">
    <aside class="case-list">{case_table}</aside>
    <section id="cases">{cases_html}</section>
  </div>
</main>
<script>
const search = document.getElementById('search');
const outcome = document.getElementById('outcome');
const failure = document.getElementById('failure');
const delta = document.getElementById('delta');
const cases = Array.from(document.querySelectorAll('.case'));
const rows = Array.from(document.querySelectorAll('.case-row'));
let activeIndex = 0;
function matchesFilters(card) {{
  const haystack = card.dataset.search || '';
  if (search.value && !haystack.includes(search.value.toLowerCase())) return false;
  if (outcome.value && card.dataset.outcome !== outcome.value) return false;
  if (failure.value && card.dataset.failure !== failure.value) return false;
  if (delta.value && card.dataset.delta !== delta.value) return false;
  return true;
}}
function showCase(index) {{
  const visible = cases.filter(matchesFilters);
  if (!visible.length) return;
  const card = visible[Math.max(0, Math.min(index, visible.length - 1))];
  activeIndex = visible.indexOf(card);
  cases.forEach(item => item.classList.toggle('visible', item === card));
  rows.forEach(row => row.classList.toggle('active', row.dataset.id === card.dataset.id));
  card.scrollIntoView({{ block:'nearest' }});
}}
function applyFilters() {{
  rows.forEach(row => {{
    const card = document.getElementById(row.dataset.id);
    row.classList.toggle('hidden', !matchesFilters(card));
  }});
  showCase(0);
}}
rows.forEach(row => row.addEventListener('click', () => showCase(cases.findIndex(card => card.dataset.id === row.dataset.id))));
[search, outcome, failure, delta].forEach(el => el.addEventListener('input', applyFilters));
function missStep(step) {{
  const visibleMisses = cases.filter(card => matchesFilters(card) && card.dataset.outcome === 'fail');
  if (!visibleMisses.length) return;
  const current = visibleMisses.findIndex(card => card.classList.contains('visible'));
  const next = current < 0 ? 0 : (current + step + visibleMisses.length) % visibleMisses.length;
  showCase(cases.indexOf(visibleMisses[next]));
}}
document.getElementById('prevMiss').addEventListener('click', () => missStep(-1));
document.getElementById('nextMiss').addEventListener('click', () => missStep(1));
document.addEventListener('keydown', event => {{ if (event.key === 'j') showCase(activeIndex + 1); if (event.key === 'k') showCase(activeIndex - 1); }});
applyFilters();
</script>
</body>
</html>
"""


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
            writer.writerows(rows)


def load_csv_dicts(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def condition_from_path(path: Path) -> str:
    parent = path.parent
    return parent.name if parent.name else path.stem


def score_bool(score: dict[str, Any], metric: str) -> bool:
    return bool(score.get("field_scores", {}).get(metric, {}).get("correct"))


def format_parts(parts: Any) -> str:
    if not isinstance(parts, dict):
        return str(parts or "")
    if parts.get("class") == "seizure_free":
        return "seizure_free"
    count = parts.get("count") or ""
    period_count = parts.get("period_count") or ""
    period_unit = parts.get("period_unit") or ""
    if count and period_unit:
        return f"{count} per {period_count or '1'} {period_unit}"
    return count or parts.get("class") or ""


def evidence_items(field_value: Any) -> list[dict[str, Any]]:
    if not isinstance(field_value, dict):
        return []
    raw = field_value.get("evidence") or []
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def span_from_quote(source_text: str, quote: str) -> tuple[int, int] | None:
    if not quote:
        return None
    start = source_text.find(quote)
    return (start, start + len(quote)) if start >= 0 else None


def normalized_span(span: dict[str, Any]) -> dict[str, Any]:
    return {
        "start": span.get("start"),
        "end": span.get("end"),
        "quote": span.get("quote") or span.get("text") or "",
        "label": span.get("label") or "",
    }


def spans_overlap(a: dict[str, Any], b: dict[str, Any]) -> bool:
    a_start, a_end, b_start, b_end = a.get("start"), a.get("end"), b.get("start"), b.get("end")
    return all(isinstance(x, int) for x in [a_start, a_end, b_start, b_end]) and min(a_end, b_end) > max(a_start, b_start)


def highlight_text(text: str, gold: list[dict[str, Any]], pred: list[dict[str, Any]]) -> str:
    points = {0, len(text)}
    gold_spans = [normalized_span(span) for span in gold]
    pred_spans = [normalized_span(span) for span in pred]
    for span in gold_spans + pred_spans:
        start, end = span.get("start"), span.get("end")
        if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(text):
            points.add(start)
            points.add(end)
    chunks: list[str] = []
    ordered = sorted(points)
    for start, end in zip(ordered, ordered[1:]):
        chunk = html.escape(text[start:end])
        if not chunk:
            continue
        segment = {"start": start, "end": end}
        in_gold = any(spans_overlap(segment, span) for span in gold_spans)
        in_pred = any(spans_overlap(segment, span) for span in pred_spans)
        if in_gold and in_pred:
            chunks.append(f'<mark class="both">{chunk}</mark>')
        elif in_gold:
            chunks.append(f'<mark class="gold">{chunk}</mark>')
        elif in_pred:
            chunks.append(f'<mark class="pred">{chunk}</mark>')
        else:
            chunks.append(chunk)
    return "".join(chunks)


def extract_frequency_field(raw_output: Any) -> dict[str, Any]:
    fields = raw_output.get("fields", {}) if isinstance(raw_output, dict) else {}
    value = fields.get("current_seizure_frequency", {})
    return value if isinstance(value, dict) else {}


def exect_failure_mode(score: dict[str, Any], raw_output: Any, gold_spans: list[Any]) -> str | None:
    if score_bool(score, "current_seizure_frequency_per_letter"):
        return None
    field = extract_frequency_field(raw_output)
    predicted = score.get("field_scores", {}).get("current_seizure_frequency", {}).get("predicted") or ""
    parsed = parse_frequency_expression(predicted)
    gold_count = int(score.get("field_scores", {}).get("current_seizure_frequency_per_letter", {}).get("gold_annotation_count", 0) or 0)
    evidence = evidence_items(field)
    if gold_count == 0 and predicted:
        return "no_gold_frequency"
    if gold_count > 0 and not predicted:
        return "missing_prediction"
    if predicted and parsed.get("class") in {"", "unparsed"}:
        return "unparsed_prediction"
    if evidence and not any(evidence_overlaps_gold(item, gold_spans) for item in evidence):
        return "wrong_span"
    if not score_bool(score, "seizure_frequency_temporal_scope"):
        return "wrong_temporality"
    if not score_bool(score, "seizure_frequency_period"):
        return "wrong_period"
    if not score_bool(score, "seizure_frequency_value"):
        return "wrong_count"
    if gold_count > 0 and not score.get("field_scores", {}).get("current_seizure_frequency_per_letter", {}).get("gold_values"):
        return "gold_normalization_gap"
    return "task_definition_mismatch"


def gan_failure_mode(gold_label: str, pred_label: str, evidence: list[dict[str, Any]]) -> str | None:
    gold = label_to_categories(gold_label)
    pred = label_to_categories(pred_label)
    if normalize_label(gold_label) == normalize_label(pred_label):
        return "evidence_missing_or_invalid" if not evidence else None
    if gold["pragmatic"] == pred["pragmatic"] and gold["purist"] != pred["purist"]:
        return "purist_wrong_pragmatic_correct"
    if gold["purist"] == pred["purist"] or gold["pragmatic"] == pred["pragmatic"]:
        return "exact_label_mismatch_category_correct"
    pair = {gold["pragmatic"], pred["pragmatic"]}
    if pair == {"UNK", "NS"}:
        return "unknown_vs_no_reference"
    if "UNK" in pair:
        return "unknown_vs_specific"
    if "NS" in pair:
        return "ns_vs_short_seizure_free"
    if any(abs(float(item.get("x_per_month", 1000.0)) - 1.1) <= 0.25 for item in [gold, pred]):
        return "frequent_infrequent_boundary"
    if "cluster" in normalize_label(gold_label) or "cluster" in normalize_label(pred_label):
        return "cluster_format_error"
    if " to " in normalize_label(gold_label) or " to " in normalize_label(pred_label):
        return "range_format_error"
    return "highest_frequency_error"


def build_exect_review(args: argparse.Namespace) -> dict[str, Any]:
    scores_path = Path(args.scores)
    all_scores = json.loads(read_text(scores_path))
    if args.system not in all_scores:
        raise ValueError(f"system {args.system!r} not found in {scores_path}; available: {', '.join(all_scores)}")
    scores = all_scores[args.system]
    exect_root = Path(args.exect_root)
    gold = load_gold(Path(args.markup_root), exect_root)
    raw_args = argparse.Namespace(
        direct_run_dir=str(Path(args.direct_run_dir)),
        event_run_dir=str(Path(args.event_run_dir)),
        recovery_run_dir=str(Path(args.recovery_run_dir)),
    )
    cases = []
    for score in scores:
        document_id = score["document_id"]
        source_text = read_text(exect_root / f"{document_id}.txt")
        document_gold = gold.get(document_id)
        gold_spans = document_gold.spans_by_group.get("seizure_frequency", []) if document_gold else []
        gold_span_dicts = [
            {"start": span.start, "end": span.end, "quote": source_text[span.start : span.end], "label": span.label}
            for span in gold_spans
        ]
        raw_path = extraction_path(args.system, document_id, raw_args)
        raw_output = load_json(raw_path)
        field = extract_frequency_field(raw_output)
        pred_spans = []
        for item in evidence_items(field):
            start, end = item.get("char_start"), item.get("char_end")
            if not (isinstance(start, int) and isinstance(end, int)):
                quote_span = span_from_quote(source_text, str(item.get("quote") or ""))
                if quote_span:
                    start, end = quote_span
            pred_spans.append({"start": start, "end": end, "quote": item.get("quote") or "", "label": "prediction"})
        exact = score.get("field_scores", {}).get("current_seizure_frequency", {})
        per_letter = score.get("field_scores", {}).get("current_seizure_frequency_per_letter", {})
        predicted_label = exact.get("predicted") or ""
        correct = bool(per_letter.get("correct"))
        failure = exect_failure_mode(score, raw_output, gold_spans)
        gold_candidates = gold_frequency_part_candidates(document_gold) if document_gold else []
        cases.append(
            {
                "document_id": document_id,
                "source_text": source_text,
                "gold": {
                    "label": "; ".join(format_parts(item) for item in gold_candidates),
                    "candidates": gold_candidates,
                    "annotation_count": len(document_gold.seizure_frequencies) if document_gold else 0,
                    "evidence": gold_span_dicts,
                },
                "predictions": [
                    {
                        "variant": args.condition or args.system,
                        "label": predicted_label,
                        "parsed": parse_frequency_expression(predicted_label),
                        "correct": correct,
                        "evidence": pred_spans,
                        "raw_output_path": str(raw_path) if raw_path.exists() else None,
                        "failure_mode": failure,
                        "evidence_gold_overlap": score.get("evidence_scores", {}).get("current_seizure_frequency", {}).get("gold_overlap"),
                    }
                ],
            }
        )
    summary = flatten_summary(args.system, scores)
    metrics = {
        "primary_name": "current_seizure_frequency_per_letter_accuracy",
        "primary_value": summary.get("current_seizure_frequency_per_letter_accuracy"),
        "secondary": summary,
    }
    return {
        "meta": {
            "dataset": "exectv2",
            "condition": args.condition or args.system,
            "split": args.split,
            "model": args.model,
            "harness": args.system,
            "generated_at": now_iso(),
            "source_artifacts": [str(scores_path)],
        },
        "metrics": metrics,
        "cases": cases,
    }


def load_gan_predictions(path: Path) -> dict[str, Any]:
    data = json.loads(read_text(path))
    if not isinstance(data, dict):
        raise ValueError(f"Gan predictions must be an object keyed by document_id: {path}")
    return data


def evidence_for_gan(source_text: str, row: dict[str, str], prediction_value: Any) -> list[dict[str, Any]]:
    evidence_texts: list[str] = []
    if row.get("evidence"):
        evidence_texts.append(row["evidence"])
    if isinstance(prediction_value, dict):
        for key in ["evidence", "quote", "evidence_quote"]:
            value = prediction_value.get(key)
            if isinstance(value, str):
                evidence_texts.append(value)
            elif isinstance(value, list):
                evidence_texts.extend(str(item) for item in value if item)
    spans = []
    seen = set()
    for quote in evidence_texts:
        if not quote or quote in seen:
            continue
        seen.add(quote)
        located = span_from_quote(source_text, quote)
        spans.append(
            {
                "start": located[0] if located else None,
                "end": located[1] if located else None,
                "quote": quote,
                "label": "prediction",
            }
        )
    return spans


def prediction_label(value: Any) -> str:
    if isinstance(value, dict):
        for key in ["label", "predicted_label", "seizure_frequency_number", "frequency"]:
            if value.get(key) is not None:
                return normalize_label(value.get(key))
        return normalize_label(json.dumps(value, ensure_ascii=False))
    return normalize_label(value)


def build_gan_review(args: argparse.Namespace) -> dict[str, Any]:
    examples = {example.document_id: example for example in load_gan_examples(Path(args.gan_path))}
    predictions = load_gan_predictions(Path(args.predictions))
    scored_rows = {row["document_id"]: row for row in load_csv_dicts(Path(args.scored))} if args.scored else {}
    cases = []
    gold_purist: list[str] = []
    pred_purist: list[str] = []
    gold_pragmatic: list[str] = []
    pred_pragmatic: list[str] = []
    for document_id, prediction in predictions.items():
        if document_id not in examples:
            continue
        example = examples[document_id]
        row = scored_rows.get(document_id, {})
        pred_label = normalize_label(row.get("predicted_label") or prediction_label(prediction))
        gold_label = example.gold_label
        gold_categories = label_to_categories(gold_label)
        pred_categories = label_to_categories(pred_label)
        gold_purist.append(gold_categories["purist"])
        pred_purist.append(pred_categories["purist"])
        gold_pragmatic.append(gold_categories["pragmatic"])
        pred_pragmatic.append(pred_categories["pragmatic"])
        gold_span = span_from_quote(example.text, example.evidence_reference)
        gold_evidence = [
            {
                "start": gold_span[0] if gold_span else None,
                "end": gold_span[1] if gold_span else None,
                "quote": example.evidence_reference,
                "label": "gold_reference",
            }
        ] if example.evidence_reference else []
        pred_evidence = evidence_for_gan(example.text, row, prediction)
        correct = gold_categories["pragmatic"] == pred_categories["pragmatic"]
        cases.append(
            {
                "document_id": document_id,
                "source_text": example.text,
                "gold": {
                    "label": gold_label,
                    "purist": gold_categories["purist"],
                    "pragmatic": gold_categories["pragmatic"],
                    "x_per_month": gold_categories["x_per_month"],
                    "evidence": gold_evidence,
                    "analysis": example.analysis,
                },
                "predictions": [
                    {
                        "variant": args.condition or condition_from_path(Path(args.predictions)),
                        "label": pred_label,
                        "purist": pred_categories["purist"],
                        "pragmatic": pred_categories["pragmatic"],
                        "x_per_month": pred_categories["x_per_month"],
                        "correct": correct,
                        "evidence": pred_evidence,
                        "raw_output_path": str(Path(args.predictions)),
                        "failure_mode": gan_failure_mode(gold_label, pred_label, pred_evidence),
                        "exact_label_match": normalize_label(gold_label) == normalize_label(pred_label),
                    }
                ],
            }
        )
    report = {
        "documents": len(cases),
        "purist": classification_report(gold_purist, pred_purist),
        "pragmatic": classification_report(gold_pragmatic, pred_pragmatic),
    }
    return {
        "meta": {
            "dataset": "gan_2026",
            "condition": args.condition or condition_from_path(Path(args.predictions)),
            "split": args.split,
            "model": args.model,
            "harness": args.harness,
            "generated_at": now_iso(),
            "source_artifacts": [
                artifact
                for artifact in [str(Path(args.gan_path)), str(Path(args.predictions)), str(Path(args.scored)) if args.scored else None]
                if artifact
            ],
        },
        "metrics": {
            "primary_name": "pragmatic_micro_f1",
            "primary_value": report["pragmatic"]["micro_f1"],
            "secondary": report,
        },
        "cases": cases,
    }


def prediction_outcome(prediction: dict[str, Any]) -> str:
    return "pass" if prediction.get("correct") else "fail"


def case_failure(case: dict[str, Any]) -> str:
    failures = [pred.get("failure_mode") for pred in case.get("predictions", []) if pred.get("failure_mode")]
    return str(failures[0]) if failures else ""


def sorted_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(cases, key=lambda case: (prediction_outcome(case["predictions"][0]) == "pass", case["document_id"]))


def metric_badges(bundle: dict[str, Any]) -> str:
    metrics = bundle.get("metrics", {})
    cases = bundle.get("cases", [])
    predictions = [case["predictions"][0] for case in cases if case.get("predictions")]
    passed = sum(1 for pred in predictions if pred.get("correct"))
    primary = metrics.get("primary_value")
    primary_text = f"{primary:.3f}" if isinstance(primary, (int, float)) else "n/a"
    values = [
        f"<span><b>{html.escape(str(metrics.get('primary_name', 'primary')))}</b> {primary_text}</span>",
        f"<span><b>{passed}/{len(predictions)}</b> primary matches</span>",
        f"<span><b>{len(cases)}</b> documents</span>",
    ]
    dataset = bundle.get("meta", {}).get("dataset")
    if dataset == "gan_2026":
        dist = Counter(case.get("gold", {}).get("pragmatic", "") for case in cases)
        values.append(f"<span>Gan pragmatic distribution: {html.escape(', '.join(f'{k}:{v}' for k, v in sorted(dist.items()) if k))}</span>")
    else:
        dist = Counter(str(case.get("gold", {}).get("annotation_count", 0)) for case in cases)
        values.append(f"<span>Gold annotation counts: {html.escape(', '.join(f'{k}:{v}' for k, v in sorted(dist.items())) )}</span>")
    return "".join(values)


def error_summary_html(cases: list[dict[str, Any]]) -> str:
    counts = Counter(case_failure(case) or "correct" for case in cases)
    if not counts:
        return '<p class="empty">No cases.</p>'
    parts = []
    for mode, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        examples = [case["document_id"] for case in cases if (case_failure(case) or "correct") == mode][:5]
        parts.append(f"<p><b>{html.escape(mode)}</b>: {count} <span class=\"muted\">{html.escape(', '.join(examples))}</span></p>")
    return "".join(parts)


def render_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return f"<code>{html.escape(json.dumps(value, ensure_ascii=False, indent=2))}</code>"
    return f"<code>{html.escape(str(value or ''))}</code>"


def render_prediction_panel(prediction: dict[str, Any], title: str) -> str:
    status = "pass" if prediction.get("correct") else "fail"
    rows = [
        ("Label", prediction.get("label")),
        ("Parsed", prediction.get("parsed")),
        ("Purist", prediction.get("purist")),
        ("Pragmatic", prediction.get("pragmatic")),
        ("Failure", prediction.get("failure_mode") or "none"),
        ("Evidence", " | ".join(item.get("quote", "") for item in prediction.get("evidence", []) if item.get("quote"))),
        ("Raw", prediction.get("raw_output_path")),
    ]
    body = "".join(f"<dt>{html.escape(label)}</dt><dd>{render_value(value)}</dd>" for label, value in rows if value not in [None, ""])
    return f'<div class="panel"><h3>{html.escape(title)} <span class="badge {status}">{status}</span></h3><dl>{body}</dl></div>'


def render_case(case: dict[str, Any], compare: bool = False) -> str:
    predictions = case.get("predictions", [])
    first = predictions[0] if predictions else {}
    outcome = prediction_outcome(first)
    failure = case_failure(case)
    delta = case.get("delta", "")
    classes = ["case", outcome]
    if delta in {"fixed", "regressed"}:
        classes.append(delta)
    search_text = " ".join(
        [
            case.get("document_id", ""),
            case.get("source_text", ""),
            str(case.get("gold", {}).get("label", "")),
            " ".join(str(pred.get("label", "")) for pred in predictions),
            failure,
            delta,
        ]
    ).lower()
    gold = case.get("gold", {})
    gold_rows = [
        ("Label", gold.get("label")),
        ("Candidates", gold.get("candidates")),
        ("Purist", gold.get("purist")),
        ("Pragmatic", gold.get("pragmatic")),
        ("Annotations", gold.get("annotation_count")),
        ("Gold Evidence", " | ".join(item.get("quote", "") for item in gold.get("evidence", []) if item.get("quote"))),
    ]
    gold_body = "".join(f"<dt>{html.escape(label)}</dt><dd>{render_value(value)}</dd>" for label, value in gold_rows if value not in [None, "", []])
    panels = [f'<div class="panel"><h3>Gold</h3><dl>{gold_body}</dl></div>']
    panels.extend(render_prediction_panel(pred, pred.get("variant", "Prediction")) for pred in predictions)
    grid_class = "grid three" if compare and len(panels) >= 3 else "grid"
    pred_spans: list[dict[str, Any]] = []
    for pred in predictions:
        pred_spans.extend(pred.get("evidence", []))
    letter = highlight_text(case.get("source_text", ""), gold.get("evidence", []), pred_spans)
    delta_badge = f' <span class="badge warn">{html.escape(delta)}</span>' if delta else ""
    return f"""
<article id="case-{html.escape(case['document_id'])}" class="{' '.join(classes)}" data-id="case-{html.escape(case['document_id'])}" data-outcome="{outcome}" data-failure="{html.escape(failure)}" data-delta="{html.escape(delta)}" data-search="{html.escape(search_text)}">
  <div class="case-head"><div><h2>{html.escape(case['document_id'])}</h2><p class="muted">{html.escape(failure or 'correct')}{delta_badge}</p></div><span class="badge {outcome}">{outcome}</span></div>
  <div class="{grid_class}">{''.join(panels)}</div>
  <details open><summary>Letter Text</summary><pre class="letter">{letter}</pre></details>
</article>"""


def render_case_table(cases: list[dict[str, Any]]) -> str:
    rows = []
    for case in cases:
        pred = case["predictions"][0]
        rows.append(
            f"<tr class=\"case-row\" data-id=\"case-{html.escape(case['document_id'])}\"><td>{html.escape(case['document_id'])}</td><td>{html.escape(prediction_outcome(pred))}</td><td>{html.escape(case_failure(case) or 'correct')}</td><td>{html.escape(str(case.get('gold', {}).get('label', ''))[:48])}</td><td>{html.escape(str(pred.get('label', ''))[:48])}</td></tr>"
        )
    return "<table><thead><tr><th>Doc</th><th>Result</th><th>Mode</th><th>Gold</th><th>Pred</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def render_review_html(bundle: dict[str, Any], compare: bool = False) -> str:
    cases = sorted_cases(bundle.get("cases", []))
    failures = sorted({case_failure(case) for case in cases if case_failure(case)})
    failure_options = "".join(f'<option value="{html.escape(mode)}">{html.escape(mode)}</option>' for mode in failures)
    heading = f"Frequency Review Workbench: {bundle.get('meta', {}).get('condition', 'review')}"
    return HTML_TEMPLATE.format(
        title=html.escape(heading),
        heading=html.escape(heading),
        summary_badges=metric_badges(bundle),
        failure_options=failure_options,
        error_summary=error_summary_html(cases),
        case_table=render_case_table(cases),
        cases_html="".join(render_case(case, compare=compare) for case in cases),
    )


def summary_rows(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for case in bundle.get("cases", []):
        pred = case["predictions"][0]
        rows.append(
            {
                "document_id": case["document_id"],
                "gold_label": case.get("gold", {}).get("label", ""),
                "predicted_label": pred.get("label", ""),
                "correct": pred.get("correct"),
                "failure_mode": pred.get("failure_mode") or "",
                "variant": pred.get("variant", ""),
            }
        )
    return rows


def write_review_bundle(bundle: dict[str, Any], output_dir: Path, html_name: str = "review.html", compare: bool = False) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "review_data.json", bundle)
    write_json(
        output_dir / "summary.json",
        {
            "meta": bundle.get("meta", {}),
            "metrics": bundle.get("metrics", {}),
            "case_count": len(bundle.get("cases", [])),
            "failure_modes": dict(Counter(case_failure(case) or "correct" for case in bundle.get("cases", []))),
        },
    )
    write_csv(output_dir / "error_tags.csv", summary_rows(bundle), ["document_id", "gold_label", "predicted_label", "correct", "failure_mode", "variant"])
    (output_dir / html_name).write_text(render_review_html(bundle, compare=compare), encoding="utf-8")


def compare_delta(predictions: list[dict[str, Any]]) -> str:
    if len(predictions) < 2:
        return ""
    before, after = bool(predictions[0].get("correct")), bool(predictions[-1].get("correct"))
    if not before and after:
        return "fixed"
    if before and not after:
        return "regressed"
    if before and after:
        return "both_correct"
    labels = {str(pred.get("label", "")) for pred in predictions}
    return "both_miss_same_prediction" if len(labels) == 1 else "both_miss"


def build_comparison(args: argparse.Namespace) -> dict[str, Any]:
    bundles = [json.loads(read_text(Path(path))) for path in args.bundle]
    by_doc: dict[str, dict[str, Any]] = {}
    for bundle in bundles:
        variant = bundle.get("meta", {}).get("condition", "variant")
        for case in bundle.get("cases", []):
            target = by_doc.setdefault(
                case["document_id"],
                {
                    "document_id": case["document_id"],
                    "source_text": case.get("source_text", ""),
                    "gold": case.get("gold", {}),
                    "predictions": [],
                },
            )
            for pred in case.get("predictions", []):
                merged = dict(pred)
                merged["variant"] = pred.get("variant") or variant
                target["predictions"].append(merged)
    cases = []
    for case in by_doc.values():
        case["delta"] = compare_delta(case["predictions"])
        cases.append(case)
    variant_names = [bundle.get("meta", {}).get("condition", f"variant_{i+1}") for i, bundle in enumerate(bundles)]
    return {
        "meta": {
            "dataset": bundles[0].get("meta", {}).get("dataset") if bundles else "unknown",
            "condition": " vs ".join(variant_names),
            "split": bundles[0].get("meta", {}).get("split") if bundles else None,
            "model": None,
            "harness": "comparison",
            "generated_at": now_iso(),
            "source_artifacts": [str(Path(path)) for path in args.bundle],
        },
        "metrics": {
            "primary_name": "comparison_documents",
            "primary_value": len(cases),
            "secondary": {"delta_distribution": dict(Counter(case.get("delta", "") for case in cases))},
        },
        "cases": cases,
    }


def write_comparison_outputs(bundle: dict[str, Any], output_dir: Path) -> None:
    write_review_bundle(bundle, output_dir, html_name="variant_comparison.html", compare=True)
    rows = []
    for case in bundle.get("cases", []):
        row = {
            "document_id": case["document_id"],
            "delta": case.get("delta", ""),
            "gold_label": case.get("gold", {}).get("label", ""),
        }
        for pred in case.get("predictions", []):
            variant = str(pred.get("variant", "variant")).replace(" ", "_")
            row[f"{variant}_label"] = pred.get("label", "")
            row[f"{variant}_correct"] = pred.get("correct")
            row[f"{variant}_failure_mode"] = pred.get("failure_mode") or ""
        rows.append(row)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    write_csv(output_dir / "variant_comparison.csv", rows, fieldnames)
    write_csv(output_dir / "fixed_cases.csv", [row for row in rows if row.get("delta") == "fixed"], fieldnames)
    write_csv(output_dir / "regressions.csv", [row for row in rows if row.get("delta") == "regressed"], fieldnames)


def command_exectv2(args: argparse.Namespace) -> int:
    bundle = build_exect_review(args)
    write_review_bundle(bundle, Path(args.output_dir))
    print(f"wrote {Path(args.output_dir) / 'review.html'}")
    return 0


def command_gan(args: argparse.Namespace) -> int:
    bundle = build_gan_review(args)
    write_review_bundle(bundle, Path(args.output_dir))
    print(f"wrote {Path(args.output_dir) / 'review.html'}")
    return 0


def command_compare(args: argparse.Namespace) -> int:
    bundle = build_comparison(args)
    write_comparison_outputs(bundle, Path(args.output_dir))
    print(f"wrote {Path(args.output_dir) / 'variant_comparison.html'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    exect = subparsers.add_parser("exectv2", help="Generate an ExECTv2 frequency review bundle.")
    exect.add_argument("--scores", required=True, help="document_scores.json from src/evaluate.py")
    exect.add_argument("--system", required=True, help="System key in document_scores.json, e.g. E3")
    exect.add_argument("--output-dir", required=True)
    exect.add_argument("--condition")
    exect.add_argument("--model")
    exect.add_argument("--split", default="unknown")
    exect.add_argument("--direct-run-dir", default=str(DEFAULT_DIRECT_RUN_DIR))
    exect.add_argument("--event-run-dir", default=str(DEFAULT_EVENT_RUN_DIR))
    exect.add_argument("--recovery-run-dir", default=str(DEFAULT_RECOVERY_RUN_DIR))
    exect.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    exect.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    exect.add_argument("--splits", default=str(DEFAULT_SPLITS))
    exect.set_defaults(func=command_exectv2)

    gan = subparsers.add_parser("gan", help="Generate a Gan 2026 frequency review bundle.")
    gan.add_argument("--gan-path", default=str(DEFAULT_GAN_PATH))
    gan.add_argument("--predictions", required=True)
    gan.add_argument("--scored")
    gan.add_argument("--output-dir", required=True)
    gan.add_argument("--condition")
    gan.add_argument("--model")
    gan.add_argument("--harness")
    gan.add_argument("--split", default="unknown")
    gan.set_defaults(func=command_gan)

    compare = subparsers.add_parser("compare", help="Compare two or more review_data.json bundles.")
    compare.add_argument("--bundle", action="append", required=True, help="Path to a review_data.json bundle. Repeat for each variant.")
    compare.add_argument("--output-dir", required=True)
    compare.set_defaults(func=command_compare)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
