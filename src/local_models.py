#!/usr/bin/env python3
"""Stage-gated runner for local models (Ollama) workstream.

Stages L0–L5 follow the plan in docs/22_local_models_workstream.md.
Each stage gates on results from the previous stage.

Usage:
    python -m local_models stage-l0 [options]
    python -m local_models stage-l1 [options]
    python -m local_models stage-l2 [options]
    python -m local_models stage-l3 [options]
    python -m local_models stage-l4 [options]
    python -m local_models stage-l5 [options]
"""

from __future__ import annotations

import argparse
import json
import logging
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

from direct_baselines import (
    build_prompt as build_direct_prompt,
    load_split_ids,
    parse_json_response,
    write_json,
    write_text,
)
from evaluate import DEFAULT_MARKUP_ROOT, flatten_summary, load_gold, score_document
from intake import DEFAULT_EXECT_ROOT, DEFAULT_SPLITS, preprocess_document
from model_expansion import (
    BENCHMARK_EPILEPSY_LABELS,
    BENCHMARK_SEIZURE_LABELS,
    build_h6_prompt,
    build_h7_extract_prompt,
    build_h7_normalize_prompt,
    build_loose_prompt,
    build_vocab_preamble,
    combined_cost,
    combined_usage,
    diagnostic_row,
    projected_canonical,
    system_for_harness,
    write_csv,
)
from model_providers import ModelRequest, adapter_for, truncate_to_context, write_response_log
from model_registry import DEFAULT_REGISTRY, load_model_specs, write_registry_snapshot
from validate_extraction import DEFAULT_SCHEMA

LOCAL_MODEL_LABELS = ["qwen_9b_local", "qwen_4b_local", "gemma_4b_local"]
LOCAL_HARNESSES_L1 = ["H0_strict_canonical"]
LOCAL_HARNESSES_L2 = ["H4_provider_native_structured_output"]
LOCAL_HARNESSES_L3 = ["H6_benchmark_only_coarse_json", "H3_loose_answer_then_parse", "H7_extract_then_normalize"]

DEFAULT_LOCAL_OUTPUT_ROOT = Path("runs/local_models")


def _ollama_tags_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        base = base[: -len("/v1")]
    return f"{base}/api/tags"


def check_ollama_connectivity(base_url: str) -> dict[str, Any]:
    tags_url = _ollama_tags_url(base_url)
    try:
        with urllib.request.urlopen(tags_url, timeout=5) as resp:
            body = json.loads(resp.read().decode())
        return {"status": "ok", "url": tags_url, "models": [m.get("name") for m in body.get("models", [])]}
    except urllib.error.URLError as exc:
        return {"status": "error", "url": tags_url, "error": str(exc)}
    except Exception as exc:
        return {"status": "error", "url": tags_url, "error": str(exc)}


def _build_local_prompt(
    harness_id: str,
    document: dict[str, Any],
    schema_path: Path,
    vocab_preamble: bool = False,
) -> str:
    if harness_id == "H0_strict_canonical":
        return build_direct_prompt("S2", document, schema_path)
    if harness_id in {"H4_provider_native_structured_output", "H6_benchmark_only_coarse_json"}:
        prompt = build_h6_prompt(document, harness_id)
    elif harness_id == "H3_loose_answer_then_parse":
        prompt = build_loose_prompt(document, harness_id)
    elif harness_id == "H7_extract_then_normalize":
        prompt = build_h7_extract_prompt(document, harness_id)
    else:
        raise ValueError(f"unsupported local harness: {harness_id}")
    if vocab_preamble:
        return build_vocab_preamble() + "\n\n" + prompt
    return prompt


def _schema_mode_for_harness(harness_id: str) -> str | None:
    return "json_mode" if harness_id == "H4_provider_native_structured_output" else None


def run_local_one(
    model_label: str,
    harness_id: str,
    document_id: str,
    output_dir: Path,
    registry: Path,
    exect_root: Path,
    schema_path: Path,
    temperature: float,
    max_output_tokens: int,
    ollama_base_url: str,
    vocab_preamble: bool = False,
    stage_tag: str = "local",
) -> dict[str, Any]:
    """Execute one model × harness × document combination for a local (Ollama) model.

    For H7 (two-pass), both extract and normalize calls are made. For all other
    harnesses a single call is made. Returns a result row compatible with write_csv.
    """
    import os
    os.environ.setdefault("OLLAMA_BASE_URL", ollama_base_url)

    specs = load_model_specs(registry)
    spec = specs[model_label]
    document = preprocess_document(document_id, exect_root)
    adapter = adapter_for("ollama")

    run_root = output_dir / "calls" / model_label / harness_id / document_id
    run_root.mkdir(parents=True, exist_ok=True)

    def make_request(prompt: str, harness_sub_id: str, pass_tag: str | None = None) -> ModelRequest:
        meta: dict[str, Any] = {"document_id": document_id, "stage": stage_tag}
        if pass_tag:
            meta["pass"] = pass_tag
        if vocab_preamble:
            meta["vocab_preamble"] = True
        return ModelRequest(
            prompt=truncate_to_context(prompt, spec),
            model=spec,
            harness_id=harness_sub_id,
            temperature=temperature,
            max_output_tokens=max_output_tokens or spec.max_output_tokens,
            schema_mode=_schema_mode_for_harness(harness_id),
            metadata=meta,
        )

    if harness_id == "H7_extract_then_normalize":
        extract_prompt = _build_local_prompt("H7_extract_then_normalize", document, schema_path, vocab_preamble)
        write_text(run_root / "extract_prompt.txt", extract_prompt)
        extract_response = adapter.call(make_request(extract_prompt, f"{harness_id}:extract", "extract"))
        write_text(run_root / "extract_raw_response.txt", extract_response.text)
        write_response_log(extract_response, run_root / "extract_provider_response.json")

        normalize_prompt = build_h7_normalize_prompt(document, harness_id, extract_response.text)
        if vocab_preamble:
            normalize_prompt = build_vocab_preamble() + "\n\n" + normalize_prompt
        write_text(run_root / "normalize_prompt.txt", normalize_prompt)
        normalize_response = adapter.call(make_request(normalize_prompt, f"{harness_id}:normalize", "normalize"))
        write_text(run_root / "raw_response.txt", normalize_response.text)
        write_response_log(normalize_response, run_root / "normalize_provider_response.json")

        parsed = parse_json_response(normalize_response.text)
        payload = (
            parsed.data
            if isinstance(parsed.data, dict) and not extract_response.error and not normalize_response.error
            else None
        )
        row = diagnostic_row(
            spec, adapter, harness_id, document_id,
            [extract_response, normalize_response],
            payload is not None, parsed.error,
            run_root / "raw_response.txt",
        )
        row["vocab_preamble"] = vocab_preamble
        return row

    # Single-pass harnesses
    prompt = _build_local_prompt(harness_id, document, schema_path, vocab_preamble)
    write_text(run_root / "prompt.txt", prompt)
    response = adapter.call(make_request(prompt, harness_id))
    write_text(run_root / "raw_response.txt", response.text)
    write_response_log(response, run_root / "provider_response.json")

    parsed = parse_json_response(response.text)
    payload = parsed.data if isinstance(parsed.data, dict) and not response.error else None
    row = diagnostic_row(
        spec, adapter, harness_id, document_id,
        [response], payload is not None, parsed.error,
        run_root / "raw_response.txt",
    )
    row["vocab_preamble"] = vocab_preamble
    return row


def score_local_rows(
    rows: list[dict[str, Any]],
    output_dir: Path,
    exect_root: Path,
    markup_root: Path,
    schema_path: Path,
    registry: Path,
    require_present_evidence: bool = False,
) -> dict[tuple[str, str, bool], dict[str, Any]]:
    """Project payloads to canonical form and score benchmark metrics for local model rows."""
    gold = load_gold(markup_root, exect_root)
    specs = load_model_specs(registry)
    by_condition: dict[tuple[str, str, bool], list[dict[str, Any]]] = {}
    for row in rows:
        key = (row["model_label"], row["harness_id"], row.get("vocab_preamble", False))
        by_condition.setdefault(key, []).append(row)

    scores: dict[tuple[str, str, bool], dict[str, Any]] = {}
    for key, condition_rows in by_condition.items():
        model_label, harness_id, vocab_flag = key
        doc_scores: list[dict[str, Any]] = []
        for row in condition_rows:
            document_id = row["document_id"]
            if document_id not in gold:
                continue
            run_root = output_dir / "calls" / model_label / harness_id / document_id
            raw_path = run_root / "raw_response.txt"
            if not raw_path.exists():
                continue
            text = raw_path.read_text(encoding="utf-8")
            parsed = parse_json_response(text)
            payload = parsed.data if isinstance(parsed.data, dict) else None
            if payload is None:
                continue
            document = preprocess_document(document_id, exect_root)
            projection_row = {k: "" if v is None else str(v) for k, v in row.items()}
            projected = projected_canonical(
                document_id, harness_id, model_label, payload, projection_row, document,
                require_present_evidence=require_present_evidence,
            )
            proj_path = run_root / "canonical_projection.json"
            write_json(proj_path, projected)
            doc_score = score_document(projected, document["text"], gold[document_id], schema_path)
            doc_scores.append(doc_score)
        if doc_scores:
            label = f"{model_label}:{harness_id}:{'vocab' if vocab_flag else 'no_vocab'}"
            scores[key] = flatten_summary(label, doc_scores)
    return scores


def _summarize_condition(
    model_label: str,
    harness_id: str,
    vocab_preamble: bool,
    rows: list[dict[str, Any]],
    scored: dict[str, Any] | None,
) -> dict[str, Any]:
    from model_expansion import to_float, mean_present
    total = len(rows)
    success = sum(1 for r in rows if r.get("status") == "success")
    parse_ok = sum(1 for r in rows if str(r.get("parse_success", "")).lower() in {"true", "1", "yes"})
    latencies = [to_float(r.get("latency_ms")) for r in rows]
    costs = [to_float(r.get("estimated_cost")) for r in rows]
    context_truncated = sum(
        1 for r in rows
        if str(r.get("context_truncated", "false")).lower() in {"true", "1", "yes"}
    )
    summary: dict[str, Any] = {
        "model_label": model_label,
        "harness_id": harness_id,
        "vocab_preamble": vocab_preamble,
        "documents": total,
        "call_success_rate": success / total if total else 0.0,
        "parse_success_rate": parse_ok / total if total else 0.0,
        "context_truncation_rate": context_truncated / total if total else 0.0,
        "mean_latency_ms": mean_present(latencies),
        "mean_estimated_cost": mean_present(costs),
    }
    if scored:
        summary.update(
            {
                "medication_name_f1": scored.get("medication_name_f1"),
                "seizure_type_f1": scored.get("seizure_type_f1"),
                "seizure_type_f1_collapsed": scored.get("seizure_type_f1_collapsed"),
                "epilepsy_diagnosis_accuracy": scored.get("epilepsy_diagnosis_accuracy"),
                "schema_valid_rate": scored.get("schema_valid_rate"),
                "quote_presence_rate": scored.get("quote_presence_rate"),
                "scoring_status": "scored",
            }
        )
    else:
        summary["scoring_status"] = "parse_only"
    return summary


def _passes_l3_gate(summary: dict[str, Any]) -> bool:
    parse_ok = (summary.get("parse_success_rate") or 0.0) >= 0.80
    med_f1 = (summary.get("medication_name_f1") or 0.0) >= 0.50
    sz_f1 = (summary.get("seizure_type_f1_collapsed") or 0.0) >= 0.30
    dx_acc = (summary.get("epilepsy_diagnosis_accuracy") or 0.0) >= 0.50
    return parse_ok and med_f1 and (sz_f1 or dx_acc)


def _run_stage(
    stage_name: str,
    model_labels: list[str],
    harness_ids: list[str],
    document_ids: list[str],
    output_dir: Path,
    registry: Path,
    exect_root: Path,
    markup_root: Path,
    schema_path: Path,
    temperature: float,
    max_output_tokens: int,
    ollama_base_url: str,
    vocab_preamble: bool = False,
    require_present_evidence: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Run all model × harness × document combinations and return (call_rows, summaries)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    call_rows: list[dict[str, Any]] = []
    for model_label in model_labels:
        for harness_id in harness_ids:
            for document_id in document_ids:
                row = run_local_one(
                    model_label, harness_id, document_id, output_dir,
                    registry, exect_root, schema_path, temperature, max_output_tokens,
                    ollama_base_url, vocab_preamble, stage_tag=stage_name,
                )
                call_rows.append(row)
                print(f"{row['status']}: {model_label} {harness_id} {document_id}", flush=True)

    write_csv(output_dir / "call_report.csv", call_rows)

    scores = score_local_rows(
        call_rows, output_dir, exect_root, markup_root, schema_path, registry, require_present_evidence,
    )

    by_condition: dict[tuple[str, str, bool], list[dict[str, Any]]] = {}
    for row in call_rows:
        key = (row["model_label"], row["harness_id"], row.get("vocab_preamble", False))
        by_condition.setdefault(key, []).append(row)

    summaries = [
        _summarize_condition(model_label, harness_id, bool(vocab_flag), rows, scores.get((model_label, harness_id, bool(vocab_flag))))
        for (model_label, harness_id, vocab_flag), rows in sorted(by_condition.items())
    ]
    write_csv(output_dir / "comparison_table.csv", summaries)
    return call_rows, summaries


def command_l0(args: argparse.Namespace) -> int:
    """Stage L0: verify Ollama connectivity, record model metadata, run stub test."""
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    connectivity = check_ollama_connectivity(args.ollama_base_url)
    print(f"Ollama connectivity: {connectivity['status']}")
    if connectivity["status"] != "ok":
        print(f"ERROR: Cannot reach Ollama at {connectivity['url']}: {connectivity.get('error')}")
        return 1

    available_models = connectivity.get("models", [])
    specs = load_model_specs(Path(args.registry))
    target_labels = args.models or ["qwen_9b_local", "gemma_4b_local"]
    target_model_ids = [specs[label].provider_model_id for label in target_labels if label in specs]

    missing = [mid for mid in target_model_ids if not any(mid in m for m in available_models)]

    report_lines = [
        "# Stage L0 Connectivity Report",
        "",
        f"Ollama base URL: {args.ollama_base_url}",
        f"Status: {connectivity['status']}",
        f"Available models: {available_models}",
        "",
        "## Target Model Status",
    ]
    for label in target_labels:
        if label not in specs:
            report_lines.append(f"- {label}: NOT IN REGISTRY")
            continue
        mid = specs[label].provider_model_id
        pulled = any(mid in m for m in available_models)
        report_lines.append(f"- {label} ({mid}): {'PULLED' if pulled else 'NOT PULLED — run: ollama pull ' + mid}")

    if missing:
        report_lines.extend(["", "## Action Required", f"Pull missing models: {missing}"])

    # Prompt length check for dev docs
    report_lines.extend(["", "## Prompt Length vs Context Window"])
    import os
    os.environ.setdefault("OLLAMA_BASE_URL", args.ollama_base_url)
    doc_ids = load_split_ids(Path(args.splits), "dev", args.limit or 15)
    for label in target_labels:
        if label not in specs:
            continue
        spec = specs[label]
        context_tokens = spec.context_window_tokens or 32768
        max_out = spec.max_output_tokens or 4096
        budget = context_tokens - max_out
        for doc_id in doc_ids[:3]:
            try:
                document = preprocess_document(doc_id, Path(args.exect_root))
                prompt = build_h6_prompt(document, "H6_benchmark_only_coarse_json")
                estimated_tokens = len(prompt) / 4
                headroom = budget - estimated_tokens
                status = "OK" if headroom > 0 else "TRUNCATION NEEDED"
                report_lines.append(f"- {label} / {doc_id}: ~{int(estimated_tokens)} tokens (budget {budget}): {status}")
            except Exception as exc:
                report_lines.append(f"- {label} / {doc_id}: ERROR: {exc}")

    report_text = "\n".join(report_lines) + "\n"
    (output_dir / "connectivity_report.md").write_text(report_text, encoding="utf-8")

    meta = {
        "stage": "l0_connectivity",
        "ollama_base_url": args.ollama_base_url,
        "connectivity": connectivity,
        "target_labels": target_labels,
        "missing_models": missing,
    }
    write_json(output_dir / "model_metadata.json", meta)
    print(report_text)
    return 1 if missing else 0


def command_l1(args: argparse.Namespace) -> int:
    """Stage L1: H0 strict canonical baseline on development docs. Characterizes failure modes."""
    output_dir = Path(args.output_dir)
    write_registry_snapshot(output_dir / "model_registry_snapshot.json", Path(args.registry))
    specs = load_model_specs(Path(args.registry))
    model_labels = args.models or ["qwen_9b_local", "gemma_4b_local"]
    document_ids = load_split_ids(Path(args.splits), args.split, args.limit)
    call_rows, summaries = _run_stage(
        "stage_l1_h0_baseline", model_labels, LOCAL_HARNESSES_L1, document_ids,
        output_dir, Path(args.registry), Path(args.exect_root), Path(args.markup_root),
        Path(args.schema), args.temperature, args.max_output_tokens, args.ollama_base_url,
    )
    failures = [r for r in call_rows if r.get("status") != "success"]
    _write_failure_analysis(output_dir / "failure_analysis.md", call_rows, "L1 H0 Baseline")
    print(f"\nL1 complete: {len(call_rows)} calls, {len(failures)} failures")
    for s in summaries:
        print(f"  {s['model_label']} {s['harness_id']}: parse={s['parse_success_rate']:.2f} "
              f"med_f1={s.get('medication_name_f1', 'n/a')}")
    return 0


def command_l2(args: argparse.Namespace) -> int:
    """Stage L2: H4 (json_mode) test — does enforcing JSON output improve parse success?"""
    output_dir = Path(args.output_dir)
    write_registry_snapshot(output_dir / "model_registry_snapshot.json", Path(args.registry))
    model_labels = args.models or ["qwen_9b_local", "gemma_4b_local"]
    document_ids = load_split_ids(Path(args.splits), args.split, args.limit)
    call_rows, summaries = _run_stage(
        "stage_l2_h4_json_mode", model_labels, LOCAL_HARNESSES_L2, document_ids,
        output_dir, Path(args.registry), Path(args.exect_root), Path(args.markup_root),
        Path(args.schema), args.temperature, args.max_output_tokens, args.ollama_base_url,
    )
    print(f"\nL2 complete: {len(call_rows)} calls")
    for s in summaries:
        print(f"  {s['model_label']} {s['harness_id']}: parse={s['parse_success_rate']:.2f} "
              f"med_f1={s.get('medication_name_f1', 'n/a')}")
    return 0


def command_l3(args: argparse.Namespace) -> int:
    """Stage L3: H6, H3, H7 harnesses — test simpler tasks for local models."""
    output_dir = Path(args.output_dir)
    write_registry_snapshot(output_dir / "model_registry_snapshot.json", Path(args.registry))
    model_labels = args.models or ["qwen_9b_local", "gemma_4b_local"]
    harness_ids = args.harnesses or LOCAL_HARNESSES_L3
    document_ids = load_split_ids(Path(args.splits), args.split, args.limit)
    call_rows, summaries = _run_stage(
        "stage_l3_simplified_harnesses", model_labels, harness_ids, document_ids,
        output_dir, Path(args.registry), Path(args.exect_root), Path(args.markup_root),
        Path(args.schema), args.temperature, args.max_output_tokens, args.ollama_base_url,
    )
    promoted = [s for s in summaries if _passes_l3_gate(s)]
    decision_lines = [
        "# Stage L3 Harness Selection Decision",
        "",
        "## Gate criteria",
        "- parse_success_rate >= 0.80",
        "- medication_name_f1 >= 0.50",
        "- seizure_type_f1_collapsed >= 0.30 OR epilepsy_diagnosis_accuracy >= 0.50",
        "",
        "## Results",
    ]
    for s in summaries:
        gate = _passes_l3_gate(s)
        decision_lines.append(
            f"- {s['model_label']} / {s['harness_id']}: "
            f"parse={s['parse_success_rate']:.2f} "
            f"med_f1={s.get('medication_name_f1', 'n/a')} "
            f"{'PROMOTED' if gate else 'not promoted'}"
        )
    decision_lines.extend(["", "## Promoted to L4", ""])
    for s in promoted:
        decision_lines.append(f"- {s['model_label']} / {s['harness_id']}")
    if not promoted:
        decision_lines.append("- None: no harness met L3 thresholds. Document failure modes and stop.")
    (output_dir / "harness_selection_decision.md").write_text("\n".join(decision_lines) + "\n", encoding="utf-8")
    print("\n".join(decision_lines))
    return 0 if promoted else 1


def command_l4(args: argparse.Namespace) -> int:
    """Stage L4: prompt engineering variants — vocabulary preamble, minimal prompt."""
    output_dir = Path(args.output_dir)
    write_registry_snapshot(output_dir / "model_registry_snapshot.json", Path(args.registry))
    model_labels = args.models or ["qwen_9b_local", "gemma_4b_local"]
    harness_ids = args.harnesses or ["H6_benchmark_only_coarse_json", "H7_extract_then_normalize"]
    document_ids = load_split_ids(Path(args.splits), args.split, args.limit)

    all_rows: list[dict[str, Any]] = []
    all_summaries: list[dict[str, Any]] = []

    # L4-A: vocabulary preamble
    vocab_dir = output_dir / "l4a_vocab_preamble"
    rows_a, summaries_a = _run_stage(
        "stage_l4a_vocab", model_labels, harness_ids, document_ids,
        vocab_dir, Path(args.registry), Path(args.exect_root), Path(args.markup_root),
        Path(args.schema), args.temperature, args.max_output_tokens, args.ollama_base_url,
        vocab_preamble=True,
    )
    for s in summaries_a:
        s["l4_variant"] = "vocab_preamble"
    all_rows.extend(rows_a)
    all_summaries.extend(summaries_a)

    # L4-B: no preamble (baseline for comparison)
    base_dir = output_dir / "l4b_no_preamble"
    rows_b, summaries_b = _run_stage(
        "stage_l4b_baseline", model_labels, harness_ids, document_ids,
        base_dir, Path(args.registry), Path(args.exect_root), Path(args.markup_root),
        Path(args.schema), args.temperature, args.max_output_tokens, args.ollama_base_url,
        vocab_preamble=False,
    )
    for s in summaries_b:
        s["l4_variant"] = "no_preamble"
    all_rows.extend(rows_b)
    all_summaries.extend(summaries_b)

    write_csv(output_dir / "comparison_table.csv", all_summaries)

    best_by_model: dict[str, dict[str, Any]] = {}
    for s in all_summaries:
        ml = s["model_label"]
        med_f1 = s.get("medication_name_f1") or 0.0
        if ml not in best_by_model or med_f1 > (best_by_model[ml].get("medication_name_f1") or 0.0):
            best_by_model[ml] = s

    decision_lines = ["# Stage L4 Promotion Decision", ""]
    for ml, s in best_by_model.items():
        decision_lines.append(f"- {ml}: best variant={s.get('l4_variant')} harness={s['harness_id']} med_f1={s.get('medication_name_f1', 'n/a')}")
    (output_dir / "promotion_decision.md").write_text("\n".join(decision_lines) + "\n", encoding="utf-8")
    print("\n".join(decision_lines))
    return 0


def command_l5(args: argparse.Namespace) -> int:
    """Stage L5: validation-scale run. Produces dissertation-quality numbers."""
    output_dir = Path(args.output_dir)
    write_registry_snapshot(output_dir / "model_registry_snapshot.json", Path(args.registry))
    model_labels = args.models or ["qwen_9b_local"]
    harness_ids = args.harnesses or ["H7_extract_then_normalize"]
    document_ids = load_split_ids(Path(args.splits), args.split or "validation", args.limit)
    call_rows, summaries = _run_stage(
        "stage_l5_validation", model_labels, harness_ids, document_ids,
        output_dir, Path(args.registry), Path(args.exect_root), Path(args.markup_root),
        Path(args.schema), args.temperature, args.max_output_tokens, args.ollama_base_url,
        vocab_preamble=args.vocab_preamble,
        require_present_evidence=args.require_present_evidence,
    )
    # Comparison vs frontier baseline numbers from the workstream plan
    frontier_baselines = [
        {"system": "S2 H0 GPT-4.1-mini (baseline)", "medication_name_f1": 0.852, "seizure_type_f1_collapsed": 0.610,
         "epilepsy_diagnosis_accuracy": 0.725, "cost_per_doc_usd": 0.003},
        {"system": "E3 H0 GPT-4.1-mini (baseline)", "medication_name_f1": 0.872, "seizure_type_f1_collapsed": 0.633,
         "epilepsy_diagnosis_accuracy": 0.775, "cost_per_doc_usd": 0.005},
    ]
    comparison_rows = list(frontier_baselines)
    for s in summaries:
        comparison_rows.append({
            "system": f"{s['model_label']} / {s['harness_id']}",
            "medication_name_f1": s.get("medication_name_f1"),
            "seizure_type_f1_collapsed": s.get("seizure_type_f1_collapsed"),
            "epilepsy_diagnosis_accuracy": s.get("epilepsy_diagnosis_accuracy"),
            "cost_per_doc_usd": 0.0,
        })
    write_csv(output_dir / "comparison_vs_frontier.csv", comparison_rows)

    # Claim package summary
    claim_lines = [
        "# Stage L5 Local Model Claim Package",
        "",
        "## Results vs Frontier Baselines",
        "",
    ]
    for s in summaries:
        med_f1 = s.get("medication_name_f1") or 0.0
        if med_f1 >= 0.70:
            tier = "SUCCESS (≥ 0.70 med name F1)"
        elif med_f1 >= 0.50:
            tier = "PARTIAL SUCCESS (0.50–0.70 med name F1)"
        else:
            tier = "FAILURE (< 0.50 med name F1)"
        claim_lines.extend([
            f"### {s['model_label']} / {s['harness_id']}",
            f"- Tier: {tier}",
            f"- medication_name_f1: {s.get('medication_name_f1', 'n/a')}",
            f"- seizure_type_f1_collapsed: {s.get('seizure_type_f1_collapsed', 'n/a')}",
            f"- epilepsy_diagnosis_accuracy: {s.get('epilepsy_diagnosis_accuracy', 'n/a')}",
            f"- Cost per doc: $0 marginal",
            "",
        ])
    (output_dir / "claim_package.md").write_text("\n".join(claim_lines), encoding="utf-8")
    eval_summary = {
        "stage": "l5_validation",
        "document_count": len(set(r["document_id"] for r in call_rows)),
        "model_labels": model_labels,
        "harness_ids": harness_ids,
        "summaries": summaries,
    }
    write_json(output_dir / "evaluation_summary.json", eval_summary)
    print("\n".join(claim_lines))
    return 0


def _write_failure_analysis(path: Path, rows: list[dict[str, Any]], stage_label: str) -> None:
    from collections import Counter
    parse_failures = [r for r in rows if str(r.get("parse_success", "")).lower() not in {"true", "1", "yes"}]
    call_failures = [r for r in rows if r.get("status") != "success"]
    error_counts: Counter = Counter(r.get("parse_error", "unknown") for r in parse_failures)
    lines = [
        f"# Failure Analysis: {stage_label}",
        "",
        f"Total calls: {len(rows)}",
        f"Call failures (API error): {len(call_failures)}",
        f"Parse failures: {len(parse_failures)}",
        "",
        "## Parse Error Distribution",
    ]
    for error, count in error_counts.most_common(10):
        lines.append(f"- {error!r}: {count}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    parser.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--splits", default=str(DEFAULT_SPLITS))
    parser.add_argument("--split", default="dev")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--models", nargs="+", default=None)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-output-tokens", type=int, default=4096)
    parser.add_argument("--ollama-base-url", default="http://localhost:11434/v1")


def main() -> int:
    parser = argparse.ArgumentParser(description="Local models (Ollama) stage-gated runner.")
    subparsers = parser.add_subparsers(dest="command")

    # L0: connectivity
    l0 = subparsers.add_parser("stage-l0", help="Verify Ollama connectivity and record model metadata.")
    _add_common_args(l0)
    l0.add_argument("--output-dir", default=str(DEFAULT_LOCAL_OUTPUT_ROOT / "stage_l0"))

    # L1: H0 baseline
    l1 = subparsers.add_parser("stage-l1", help="H0 strict canonical baseline to characterize failure modes.")
    _add_common_args(l1)
    l1.add_argument("--output-dir", default=str(DEFAULT_LOCAL_OUTPUT_ROOT / "stage_l1"))

    # L2: H4 json mode
    l2 = subparsers.add_parser("stage-l2", help="H4 (json_mode) — does enforcing JSON output improve parse success?")
    _add_common_args(l2)
    l2.add_argument("--output-dir", default=str(DEFAULT_LOCAL_OUTPUT_ROOT / "stage_l2"))

    # L3: simplified harnesses
    l3 = subparsers.add_parser("stage-l3", help="H6/H3/H7 simplified harnesses for local models.")
    _add_common_args(l3)
    l3.add_argument("--harnesses", nargs="+", default=None)
    l3.add_argument("--output-dir", default=str(DEFAULT_LOCAL_OUTPUT_ROOT / "stage_l3"))

    # L4: prompt engineering
    l4 = subparsers.add_parser("stage-l4", help="Prompt engineering variants (vocabulary preamble).")
    _add_common_args(l4)
    l4.add_argument("--harnesses", nargs="+", default=None)
    l4.add_argument("--output-dir", default=str(DEFAULT_LOCAL_OUTPUT_ROOT / "stage_l4"))

    # L5: validation scale
    l5 = subparsers.add_parser("stage-l5", help="Validation-scale run producing dissertation numbers.")
    _add_common_args(l5)
    l5.add_argument("--harnesses", nargs="+", default=None)
    l5.add_argument("--output-dir", default=str(DEFAULT_LOCAL_OUTPUT_ROOT / "stage_l5"))
    l5.add_argument("--vocab-preamble", action="store_true", default=False)
    l5.add_argument("--require-present-evidence", action="store_true", default=False)

    args = parser.parse_args()
    if args.command == "stage-l0":
        return command_l0(args)
    if args.command == "stage-l1":
        return command_l1(args)
    if args.command == "stage-l2":
        return command_l2(args)
    if args.command == "stage-l3":
        return command_l3(args)
    if args.command == "stage-l4":
        return command_l4(args)
    if args.command == "stage-l5":
        return command_l5(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
