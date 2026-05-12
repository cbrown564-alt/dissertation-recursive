#!/usr/bin/env python3
"""Run E1/E2/E3 event-first pipeline with Gemini Flash via model_providers adapter."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from direct_baselines import (
    normalize_contract_aliases,
    parse_json_response,
    validate_and_score,
    write_json,
    write_text,
)
from evaluate import DEFAULT_MARKUP_ROOT, flatten_summary, load_gold, score_document
from event_first import (
    E1_PIPELINE_ID,
    E2_PIPELINE_ID,
    E3_PIPELINE_ID,
    aggregate_events,
    build_e1_prompt,
    build_e3_prompt,
    normalize_event_payload,
    validate_event_payload,
)
from direct_baselines import load_split_ids
from intake import DEFAULT_EXECT_ROOT, DEFAULT_SPLITS, preprocess_document
from model_providers import GoogleAdapter, ModelRequest, TokenUsage, write_response_log
from model_registry import DEFAULT_REGISTRY, load_model_specs
from validate_extraction import DEFAULT_SCHEMA


def call_gemini_flash(prompt: str, harness_id: str, thinking_budget: int = 0) -> tuple[str, float, dict[str, Any]]:
    """Call Gemini Flash with thinking budget control. Returns (text, latency_ms, metadata)."""
    specs = load_model_specs(Path(DEFAULT_REGISTRY))
    spec = specs["gemini_3_1_flash"]
    adapter = GoogleAdapter()
    request = ModelRequest(
        prompt=prompt,
        model=spec,
        harness_id=harness_id,
        temperature=spec.temperature,
        max_output_tokens=spec.max_output_tokens,
        google_thinking_budget=thinking_budget,
        metadata={"model_label": "gemini_3_1_flash"},
    )
    started = time.perf_counter()
    response = adapter.call(request)
    latency_ms = (time.perf_counter() - started) * 1000
    return response.text or "", latency_ms, {
        "input_tokens": response.token_usage.input_tokens,
        "output_tokens": response.token_usage.output_tokens,
        "estimated_cost": response.estimated_cost,
        "error": response.error,
    }


def run_e1_gemini(document: dict[str, Any], run_root: Path, thinking_budget: int = 0) -> tuple[list[dict[str, Any]] | None, dict[str, Any]]:
    prompt = build_e1_prompt(document)
    prompt_path = run_root / "e1_prompt.txt"
    raw_path = run_root / "e1_raw.json"
    events_path = run_root / "e1_events.json"
    write_text(prompt_path, prompt)

    raw_response, latency_ms, metadata = call_gemini_flash(prompt, "E1_event_extraction", thinking_budget)
    write_text(raw_path, raw_response)

    parse = parse_json_response(raw_response)
    payload = None
    scores = None
    if parse.data is not None:
        try:
            payload = normalize_event_payload(parse.data, document["document_id"], "gemini-3-flash-preview", latency_ms, parse)
            write_json(events_path, payload)
            scores = validate_event_payload(payload, document["text"])
        except Exception as exc:
            scores = {"event_constraints_valid": False, "quote_validity": None, "validation_errors": [str(exc)]}

    record = {
        "document_id": document["document_id"],
        "pipeline": "E1",
        "provider": "google",
        "model": "gemini-3-flash-preview",
        "prompt_path": str(prompt_path),
        "raw_response_path": str(raw_path),
        "event_output_path": str(events_path) if payload is not None else None,
        "parse": {"parse_success": parse.parse_success, "repair_attempted": parse.repair_attempted, "repair_succeeded": parse.repair_succeeded, "error": parse.error},
        "scores": scores,
        "metadata": metadata,
    }
    return payload, record


def run_e3_gemini(document: dict[str, Any], events: list[dict[str, Any]], run_root: Path, thinking_budget: int = 0) -> dict[str, Any]:
    prompt = build_e3_prompt(document["document_id"], events, Path(DEFAULT_SCHEMA))
    prompt_path = run_root / "e3_prompt.txt"
    raw_path = run_root / "e3_raw.json"
    canonical_path = run_root / "e3_canonical.json"
    write_text(prompt_path, prompt)

    raw_response, latency_ms, metadata = call_gemini_flash(prompt, "E3_constrained_aggregation", thinking_budget)
    write_text(raw_path, raw_response)

    parse = parse_json_response(raw_response)
    scores = None
    if parse.data is not None:
        parse.data = normalize_contract_aliases(parse.data, document["document_id"], E3_PIPELINE_ID)
        if isinstance(parse.data, dict):
            parse.data.setdefault("metadata", {})
            parse.data["metadata"].update({
                "model": "gemini-3-flash-preview",
                "format": "constrained_json",
                "latency_ms": latency_ms,
                "repair_attempted": parse.repair_attempted,
                "repair_succeeded": parse.repair_succeeded,
            })
            for token_key in ["input_tokens", "output_tokens"]:
                if parse.data["metadata"].get(token_key) is None:
                    parse.data["metadata"][token_key] = 0
        write_json(canonical_path, parse.data)
        scores = validate_and_score(parse.data, document["text"], Path(DEFAULT_SCHEMA), require_present_evidence=True)

    return {
        "document_id": document["document_id"],
        "pipeline": "E3",
        "provider": "google",
        "model": "gemini-3-flash-preview",
        "prompt_path": str(prompt_path),
        "raw_response_path": str(raw_path),
        "canonical_output_path": str(canonical_path) if parse.data is not None else None,
        "parse": {"parse_success": parse.parse_success, "repair_attempted": parse.repair_attempted, "repair_succeeded": parse.repair_succeeded, "error": parse.error},
        "scores": scores,
        "metadata": metadata,
    }


def main() -> int:
    output_dir = Path("runs/model_expansion/gemini_flash_e3_validation")
    output_dir.mkdir(parents=True, exist_ok=True)

    document_ids = load_split_ids(Path(DEFAULT_SPLITS), "validation", 40)
    gold = load_gold(Path(DEFAULT_MARKUP_ROOT), Path(DEFAULT_EXECT_ROOT))
    exect_root = Path(DEFAULT_EXECT_ROOT)
    schema_path = Path(DEFAULT_SCHEMA)

    e3_scores = []
    e2_scores = []

    for document_id in document_ids:
        document = preprocess_document(document_id, exect_root)
        run_root = output_dir / document_id
        run_root.mkdir(parents=True, exist_ok=True)

        # E1
        payload, e1_record = run_e1_gemini(document, run_root, thinking_budget=0)
        e1_ok = bool(
            e1_record["parse"]["parse_success"]
            and e1_record["scores"]
            and e1_record["scores"].get("event_constraints_valid")
        )
        print(f"{'pass' if e1_ok else 'FAIL'}: E1 {document_id}", flush=True)
        if not e1_ok:
            continue

        events = payload["events"] if payload else []

        # E2 (deterministic fallback)
        e2_canonical, e2_log = aggregate_events(document_id, events, model_name="gemini_flash_deterministic")
        e2_canonical["pipeline_id"] = E2_PIPELINE_ID
        e2_canonical["metadata"]["aggregation"] = e2_log
        write_json(run_root / "e2_canonical.json", e2_canonical)
        e2_score = score_document(e2_canonical, document["text"], gold.get(document_id), schema_path)
        e2_score["document_id"] = document_id
        e2_scores.append(e2_score)

        # E3 (constrained LLM aggregation)
        e3_record = run_e3_gemini(document, events, run_root, thinking_budget=0)
        e3_ok = bool(e3_record["parse"]["parse_success"] and e3_record["scores"])
        print(f"{'pass' if e3_ok else 'FAIL'}: E3 {document_id}", flush=True)
        if e3_ok:
            e3_record["scores"]["document_id"] = document_id
            e3_scores.append(e3_record["scores"])

    # Summarize
    summaries = {}
    if e2_scores:
        summaries["E2_deterministic"] = flatten_summary("gemini_flash:E2", e2_scores)
    if e3_scores:
        summaries["E3_constrained"] = flatten_summary("gemini_flash:E3", e3_scores)

    out_path = output_dir / "summary.json"
    out_path.write_text(json.dumps(summaries, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote summary to {out_path}")

    # Print table
    fields = [
        "medication_name_f1", "medication_full_f1", "seizure_type_f1",
        "seizure_type_f1_collapsed", "epilepsy_diagnosis_accuracy",
        "epilepsy_diagnosis_accuracy_collapsed", "eeg_accuracy", "mri_accuracy",
        "temporal_accuracy", "schema_valid_rate", "quote_validity_rate",
        "documents_available",
    ]
    print(f"\n{'System':<30}", end="")
    for f in fields:
        print(f"{f:<25}", end="")
    print()
    print("=" * (30 + 25 * len(fields)))
    for system, summary in summaries.items():
        print(f"{system:<30}", end="")
        for f in fields:
            val = summary.get(f)
            s = f"{val:.3f}" if isinstance(val, float) else (str(val) if val is not None else "N/A")
            print(f"{s:<25}", end="")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
