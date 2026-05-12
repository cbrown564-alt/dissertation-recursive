#!/usr/bin/env python3
"""Multi-agent exploration pipeline (MA_v2).

Implements the experimental designs from docs/52_future_work_multi_agent_exploration.md:
  MA-A   - Verifier-only augmentation on best single harness
  SAS    - Matched-budget single-agent baselines (long-CoT, best-of-N)

Scoring includes the Efficiency-Adjusted BenchComp (EABC) metric:
  EABC = BenchComp / log(total_tokens + 1)

Usage:
    python src/multi_agent_exploration.py run-ma-a --base-harness H6full --model qwen_35b_local --split validation
    python src/multi_agent_exploration.py run-sas-long-cot --base-harness H6full --model gpt_5_4_mini --split validation
    python src/multi_agent_exploration.py run-sas-best-of-n --base-harness H6full --model gpt_5_4_mini --n 3 --split validation
    python src/multi_agent_exploration.py score --run-dir runs/multi_agent_exploration/...
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

from direct_baselines import (
    load_split_ids,
    normalize_contract_aliases,
    parse_json_response,
    validate_and_score,
    write_json,
    write_text,
)
from evaluate import DEFAULT_MARKUP_ROOT, flatten_summary, load_gold, score_document
from event_first import (
    E1_PIPELINE_ID,
    E3_PIPELINE_ID,
    aggregate_events,
    build_e1_prompt,
    build_e3_prompt,
    normalize_event_payload,
    validate_event_payload,
)
from intake import DEFAULT_EXECT_ROOT, DEFAULT_SPLITS, preprocess_document, read_text
from model_expansion import (
    BENCHMARK_EPILEPSY_LABELS,
    BENCHMARK_SEIZURE_LABELS,
    benchmark_label_block,
    build_h6fs_prompt,
    build_h6full_prompt,
    write_csv,
)
from model_providers import ModelRequest, TokenUsage, adapter_for, write_response_log
from model_registry import DEFAULT_REGISTRY, load_model_specs, write_registry_snapshot
from validate_extraction import DEFAULT_SCHEMA, ValidationError


PROMPT_DIR = Path("prompts/multi_agent_v2")
DEFAULT_OUTPUT_ROOT = Path("runs/multi_agent_exploration")

BENCHMARK_COMPOSITE_WEIGHTS = {
    "medication_name_f1": 0.30,
    "seizure_type_f1_collapsed": 0.25,
    "epilepsy_diagnosis_accuracy_collapsed_or_plain": 0.20,
    "eeg_accuracy": 0.125,
    "mri_accuracy": 0.125,
}

# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def _compute_benchcomp(row: dict[str, Any]) -> float | None:
    dx = row.get("epilepsy_diagnosis_accuracy_collapsed") or row.get("epilepsy_diagnosis_accuracy")
    values = {
        "medication_name_f1": row.get("medication_name_f1"),
        "seizure_type_f1_collapsed": row.get("seizure_type_f1_collapsed"),
        "epilepsy_diagnosis_accuracy_collapsed_or_plain": dx,
        "eeg_accuracy": row.get("eeg_accuracy"),
        "mri_accuracy": row.get("mri_accuracy"),
    }
    weighted_sum = 0.0
    total_weight = 0.0
    for key, weight in BENCHMARK_COMPOSITE_WEIGHTS.items():
        val = values.get(key)
        if val is not None:
            try:
                weighted_sum += float(val) * weight
                total_weight += weight
            except (TypeError, ValueError):
                pass
    return round(weighted_sum / total_weight, 3) if total_weight > 0 else None


def _compute_eabc(benchcomp: float | None, total_tokens: int) -> float | None:
    """Efficiency-Adjusted BenchComp = BenchComp / log(total_tokens + 1)."""
    if benchcomp is None or total_tokens <= 0:
        return None
    return round(benchcomp / math.log(total_tokens + 1), 4)


# ---------------------------------------------------------------------------
# Low-level model call helper
# ---------------------------------------------------------------------------


def _call_model(
    prompt: str,
    spec: Any,
    harness_id: str,
    stage_name: str,
    doc_id: str,
    run_root: Path,
    max_tokens: int = 512,
    stub: bool = False,
) -> tuple[Any, dict[str, Any] | None, int]:
    """Make one model call. Returns (response, parsed_dict, output_tokens)."""
    run_root.mkdir(parents=True, exist_ok=True)
    prompt_path = run_root / f"{stage_name}_prompt.txt"
    raw_path = run_root / f"{stage_name}_raw.txt"
    log_path = run_root / f"{stage_name}_response.json"
    write_text(prompt_path, prompt)

    request = ModelRequest(
        prompt=prompt,
        model=spec,
        harness_id=harness_id,
        temperature=0.0,
        max_output_tokens=max_tokens,
        metadata={"document_id": doc_id, "stage": stage_name},
    )
    adapter = adapter_for("stub" if stub else spec.provider)
    response = adapter.call(request)
    write_text(raw_path, response.text)
    response.raw_response_path = str(raw_path)
    write_response_log(response, log_path)

    parsed: dict[str, Any] | None = None
    if response.text:
        result = parse_json_response(response.text)
        if result.parse_success and isinstance(result.data, dict):
            parsed = result.data
            write_json(run_root / f"{stage_name}.json", parsed)

    out_tokens = response.token_usage.output_tokens or 0
    return response, parsed, out_tokens


# ---------------------------------------------------------------------------
# Canonical helpers
# ---------------------------------------------------------------------------


def _empty_scalar(missingness: str = "not_stated", temporality: str = "uncertain") -> dict[str, Any]:
    return {
        "value": None,
        "missingness": missingness,
        "temporality": temporality,
        "evidence": None,
        "evidence_event_ids": [],
        "confidence": None,
    }


def _empty_investigation() -> dict[str, Any]:
    return {
        "status": "not_stated",
        "result": "not_stated",
        "missingness": "not_stated",
        "temporality": "uncertain",
        "evidence": None,
        "evidence_event_ids": [],
        "confidence": None,
    }


def h6fs_to_canonical(document_id: str, payload: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    """Lightweight projection of H6fs benchmark JSON to canonical schema."""
    med_names = payload.get("medication_names") or []
    h6full_meds = payload.get("medications") or []
    seizure_types = payload.get("seizure_types") or []
    diagnosis = payload.get("epilepsy_diagnosis_type")
    frequency = payload.get("seizure_frequency") or payload.get("current_seizure_frequency")
    investigations = payload.get("investigations") or {}

    meds = []
    # H6full uses "medications" list of dicts
    for med in h6full_meds:
        if isinstance(med, dict) and med.get("name"):
            meds.append({
                "name": med.get("name"),
                "dose": med.get("dose") or None,
                "dose_unit": med.get("unit") or med.get("dose_unit") or None,
                "frequency": med.get("frequency") or None,
                "status": "current",
                "missingness": "present",
                "temporality": "current",
                "evidence": None,
                "evidence_event_ids": [],
                "confidence": None,
            })
    # H6fs uses "medication_names" list of strings
    for name in med_names:
        if isinstance(name, str):
            meds.append({
                "name": name,
                "dose": None,
                "dose_unit": None,
                "frequency": None,
                "status": "current",
                "missingness": "present",
                "temporality": "current",
                "evidence": None,
                "evidence_event_ids": [],
                "confidence": None,
            })

    sz_freq = _empty_scalar()
    sz_freq["temporal_scope"] = None
    sz_freq["seizure_type"] = None
    if frequency:
        sz_freq = {
            "value": frequency if isinstance(frequency, str) else None,
            "missingness": "present",
            "temporality": "current",
            "temporal_scope": "current",
            "seizure_type": None,
            "evidence": None,
            "evidence_event_ids": [],
            "confidence": None,
        }

    eeg_val = investigations.get("eeg") if isinstance(investigations, dict) else None
    mri_val = investigations.get("mri") if isinstance(investigations, dict) else None

    return {
        "document_id": document_id,
        "pipeline_id": metadata.get("pipeline_id", "H6fs_projection"),
        "fields": {
            "current_anti_seizure_medications": meds,
            "previous_anti_seizure_medications": [],
            "current_seizure_frequency": sz_freq,
            "seizure_types": [
                {
                    "value": st,
                    "missingness": "present",
                    "temporality": "current",
                    "evidence": None,
                    "evidence_event_ids": [],
                    "confidence": None,
                }
                for st in seizure_types
            ],
            "eeg": {
                "status": "completed" if eeg_val else "not_stated",
                "result": eeg_val if eeg_val in {"normal", "abnormal"} else "not_stated",
                "missingness": "not_stated" if not eeg_val else "present",
                "temporality": "completed" if eeg_val else "uncertain",
                "evidence": None,
                "evidence_event_ids": [],
                "confidence": None,
            },
            "mri": {
                "status": "completed" if mri_val else "not_stated",
                "result": mri_val if mri_val in {"normal", "abnormal"} else "not_stated",
                "missingness": "not_stated" if not mri_val else "present",
                "temporality": "completed" if mri_val else "uncertain",
                "evidence": None,
                "evidence_event_ids": [],
                "confidence": None,
            },
            "epilepsy_diagnosis": {
                "value": diagnosis,
                "missingness": "present" if diagnosis else "not_stated",
                "temporality": "current",
                "evidence": None,
                "evidence_event_ids": [],
                "confidence": None,
            },
        },
        "events": [],
        "metadata": metadata,
    }


# ---------------------------------------------------------------------------
# Base extraction runners
# ---------------------------------------------------------------------------


def run_base_h6fs(
    document: dict[str, Any],
    spec: Any,
    run_root: Path,
    long_cot: bool = False,
    stub: bool = False,
    use_h6full: bool = False,
) -> tuple[dict[str, Any] | None, list[Any], int]:
    """Run H6fs/H6full extraction and project to canonical.

    Returns (canonical_dict, responses, total_output_tokens).
    """
    if use_h6full:
        harness_id = "H6full_benchmark_coarse_json_long_cot" if long_cot else "H6full_benchmark_coarse_json"
        if long_cot:
            # Build long-CoT variant by prepending reasoning instructions to H6full prompt
            prompt = build_h6full_prompt(document, harness_id)
            prompt = (
                "Think step by step. First list all current medications with dose/unit/frequency. "
                "Then identify current seizure status and types. Then determine diagnosis and investigations. "
                "Verify each item against the source text before producing final JSON.\n\n" + prompt
            )
        else:
            prompt = build_h6full_prompt(document, harness_id)
    else:
        harness_id = "H6fs_benchmark_only_coarse_json_long_cot" if long_cot else "H6fs_benchmark_only_coarse_json"
        if long_cot:
            prompt = read_text(PROMPT_DIR / "long_cot_h6fs.md") + f"\n\n## Source Letter\n{document['text']}"
        else:
            prompt = build_h6fs_prompt(document, harness_id)

    response, parsed, out_tokens = _call_model(
        prompt, spec, harness_id, "base_extraction", document["document_id"], run_root, max_tokens=512, stub=stub,
    )
    responses = [response]
    total_tokens = (response.token_usage.input_tokens or 0) + (response.token_usage.output_tokens or 0)

    if parsed is None:
        return None, responses, total_tokens

    metadata = {
        "model": spec.provider_model_id,
        "model_label": spec.label,
        "provider": spec.provider,
        "harness_id": harness_id,
        "latency_ms": response.latency_ms,
        "input_tokens": response.token_usage.input_tokens or 0,
        "output_tokens": response.token_usage.output_tokens or 0,
        "repair_attempted": False,
        "repair_succeeded": False,
    }
    canonical = h6fs_to_canonical(document["document_id"], parsed, metadata)
    write_json(run_root / "base_canonical.json", canonical)
    return canonical, responses, total_tokens


def run_base_e3(
    document: dict[str, Any],
    spec: Any,
    run_root: Path,
    schema_path: Path,
    long_cot: bool = False,
    stub: bool = False,
) -> tuple[dict[str, Any] | None, list[Any], int]:
    """Run E1 -> E2 -> E3 pipeline and return canonical JSON.

    Returns (canonical_dict, responses, total_output_tokens).
    """
    responses: list[Any] = []
    total_tokens = 0
    doc_id = document["document_id"]

    # E1
    e1_prompt = build_e1_prompt(document)
    if long_cot:
        # For E1 long-CoT, prepend reasoning instructions
        e1_prompt = (
            "Think step by step. First identify all clinical events in the letter. "
            "For each event, note its category, temporality, and exact evidence quote. "
            "Then produce the final JSON.\n\n" + e1_prompt
        )
    resp1, e1_parsed, _ = _call_model(
        e1_prompt, spec, "E1_event_extraction", "e1_event_extraction", doc_id, run_root, max_tokens=1024, stub=stub,
    )
    responses.append(resp1)
    total_tokens += (resp1.token_usage.input_tokens or 0) + (resp1.token_usage.output_tokens or 0)

    if e1_parsed is None:
        return None, responses, total_tokens

    try:
        e1_payload = normalize_event_payload(e1_parsed, doc_id, spec.provider_model_id, resp1.latency_ms, parse_json_response(resp1.text))
    except ValidationError:
        return None, responses, total_tokens

    write_json(run_root / "e1_events.json", e1_payload)

    # E2 deterministic aggregation
    canonical_e2, agg_log = aggregate_events(doc_id, e1_payload.get("events", []), model_name="deterministic")
    write_json(run_root / "e2_canonical.json", canonical_e2)
    write_json(run_root / "e2_aggregation_log.json", agg_log)

    # E3 constrained aggregation
    e3_prompt = build_e3_prompt(doc_id, e1_payload.get("events", []), schema_path)
    if long_cot:
        e3_prompt = (
            "Think step by step. Review each event carefully. "
            "Apply the aggregation rules one at a time. "
            "Verify temporality before including any value. "
            "Then produce the final canonical JSON.\n\n" + e3_prompt
        )
    resp3, e3_parsed, _ = _call_model(
        e3_prompt, spec, "E3_constrained_event_aggregation", "e3_constrained_aggregation", doc_id, run_root, max_tokens=1024, stub=stub,
    )
    responses.append(resp3)
    total_tokens += (resp3.token_usage.input_tokens or 0) + (resp3.token_usage.output_tokens or 0)

    if e3_parsed is None:
        return None, responses, total_tokens

    e3_parsed = normalize_contract_aliases(e3_parsed, doc_id, E3_PIPELINE_ID)
    if isinstance(e3_parsed, dict):
        e3_parsed.setdefault("metadata", {})
        if isinstance(e3_parsed["metadata"], dict):
            e3_parsed["metadata"].update({
                "model": spec.provider_model_id,
                "model_label": spec.label,
                "provider": spec.provider,
                "harness_id": "E3_constrained_event_aggregation",
                "latency_ms": resp3.latency_ms,
                "input_tokens": resp3.token_usage.input_tokens or 0,
                "output_tokens": resp3.token_usage.output_tokens or 0,
            })
        write_json(run_root / "e3_canonical.json", e3_parsed)
        return e3_parsed, responses, total_tokens

    return None, responses, total_tokens


# ---------------------------------------------------------------------------
# Verifier / corrector prompts and runners
# ---------------------------------------------------------------------------


def build_verifier_prompt(document_text: str, canonical: dict[str, Any]) -> str:
    instructions = read_text(PROMPT_DIR / "verifier.md")
    return "\n\n".join([
        instructions,
        "## Extracted JSON",
        json.dumps(canonical, indent=2, ensure_ascii=False),
        "## Source Letter",
        document_text,
    ])


def build_corrector_prompt(document_text: str, canonical: dict[str, Any], flags: list[dict[str, Any]]) -> str:
    instructions = read_text(PROMPT_DIR / "corrector.md")
    return "\n\n".join([
        instructions,
        "## Verifier Flags",
        json.dumps({"flags": flags}, indent=2, ensure_ascii=False),
        "## Original Extraction",
        json.dumps(canonical, indent=2, ensure_ascii=False),
        "## Source Letter",
        document_text,
    ])


def run_verifier(
    document_text: str,
    canonical: dict[str, Any],
    spec: Any,
    run_root: Path,
    stub: bool = False,
) -> tuple[list[dict[str, Any]], Any, int]:
    """Run verifier agent. Returns (flags, response, total_tokens)."""
    prompt = build_verifier_prompt(document_text, canonical)
    response, parsed, _ = _call_model(
        prompt, spec, "MA_v2_verifier", "verifier", canonical.get("document_id", "unknown"), run_root, max_tokens=1024, stub=stub,
    )
    total_tokens = (response.token_usage.input_tokens or 0) + (response.token_usage.output_tokens or 0)
    if parsed is None:
        return [], response, total_tokens
    flags = parsed.get("flags") or []
    if not isinstance(flags, list):
        flags = []
    write_json(run_root / "verifier_flags.json", parsed)
    return flags, response, total_tokens


def run_corrector(
    document_text: str,
    canonical: dict[str, Any],
    flags: list[dict[str, Any]],
    spec: Any,
    run_root: Path,
    stub: bool = False,
) -> tuple[dict[str, Any] | None, Any, int]:
    """Run corrector agent. Returns (revised_canonical, response, total_tokens)."""
    prompt = build_corrector_prompt(document_text, canonical, flags)
    response, parsed, _ = _call_model(
        prompt, spec, "MA_v2_corrector", "corrector", canonical.get("document_id", "unknown"), run_root, max_tokens=1024, stub=stub,
    )
    total_tokens = (response.token_usage.input_tokens or 0) + (response.token_usage.output_tokens or 0)
    if parsed is None:
        return None, response, total_tokens
    # Ensure pipeline_id is updated
    if isinstance(parsed, dict):
        parsed["pipeline_id"] = canonical.get("pipeline_id", "unknown") + "_corrected"
        parsed["document_id"] = canonical.get("document_id", "unknown")
        if "metadata" not in parsed or not isinstance(parsed.get("metadata"), dict):
            parsed["metadata"] = {}
        parsed["metadata"]["corrector_latency_ms"] = response.latency_ms
        write_json(run_root / "corrected_canonical.json", parsed)
    return parsed, response, total_tokens


# ---------------------------------------------------------------------------
# High-level pipeline runners
# ---------------------------------------------------------------------------


def run_ma_a(
    document: dict[str, Any],
    spec: Any,
    run_root: Path,
    base_harness: str,
    schema_path: Path,
    stub: bool = False,
) -> dict[str, Any]:
    """Run MA-A: base extraction -> verifier -> optional corrector.

    Returns a result dict with canonical output and metrics.
    """
    doc_id = document["document_id"]
    text = document["text"]

    # Stage 1: Base extraction
    if base_harness.upper() == "E3":
        canonical, responses, base_tokens = run_base_e3(document, spec, run_root, schema_path, stub=stub)
    else:
        canonical, responses, base_tokens = run_base_h6fs(
            document, spec, run_root, stub=stub, use_h6full=(base_harness.upper() == "H6FULL")
        )

    if canonical is None:
        return {
            "document_id": doc_id,
            "status": "base_parse_failed",
            "canonical": None,
            "total_tokens": base_tokens,
            "flags_count": 0,
            "corrector_run": False,
        }

    # Stage 2: Verifier
    flags, v_resp, v_tokens = run_verifier(text, canonical, spec, run_root, stub=stub)
    total_tokens = base_tokens + v_tokens

    # Stage 3: Corrector (only if actionable flags exist)
    actionable_flags = [f for f in flags if f.get("issue") not in {"supported", "missing_evidence"}]
    final_canonical = canonical
    corrector_run = False
    if actionable_flags:
        corrected, c_resp, c_tokens = run_corrector(text, canonical, actionable_flags, spec, run_root, stub=stub)
        total_tokens += c_tokens
        corrector_run = True
        if corrected is not None:
            final_canonical = corrected

    # Write final canonical
    write_json(run_root / "canonical.json", final_canonical)

    # Compute verifier rates
    all_items = (
        len(final_canonical.get("fields", {}).get("current_anti_seizure_medications", [])) +
        len(final_canonical.get("fields", {}).get("seizure_types", [])) +
        (1 if final_canonical.get("fields", {}).get("epilepsy_diagnosis", {}).get("value") else 0)
    )
    drop_count = sum(1 for f in flags if "drop" in f.get("suggested_fix", "").lower())
    modify_count = sum(1 for f in flags if "replace" in f.get("suggested_fix", "").lower() or "fix" in f.get("suggested_fix", "").lower())
    drop_rate = drop_count / max(all_items, 1)
    modify_rate = modify_count / max(all_items, 1)

    return {
        "document_id": doc_id,
        "status": "success",
        "canonical": final_canonical,
        "total_tokens": total_tokens,
        "flags_count": len(flags),
        "corrector_run": corrector_run,
        "drop_rate": round(drop_rate, 3),
        "modify_rate": round(modify_rate, 3),
    }


def run_sas_long_cot(
    document: dict[str, Any],
    spec: Any,
    run_root: Path,
    base_harness: str,
    schema_path: Path,
    stub: bool = False,
) -> dict[str, Any]:
    """Run single-agent long-CoT baseline."""
    doc_id = document["document_id"]

    if base_harness.upper() == "E3":
        canonical, responses, total_tokens = run_base_e3(document, spec, run_root, schema_path, long_cot=True, stub=stub)
    else:
        canonical, responses, total_tokens = run_base_h6fs(
            document, spec, run_root, long_cot=True, stub=stub, use_h6full=(base_harness.upper() == "H6FULL")
        )

    if canonical is None:
        return {
            "document_id": doc_id,
            "status": "parse_failed",
            "canonical": None,
            "total_tokens": total_tokens,
        }

    write_json(run_root / "canonical.json", canonical)
    return {
        "document_id": doc_id,
        "status": "success",
        "canonical": canonical,
        "total_tokens": total_tokens,
    }


def _canonical_field_count(canonical: dict[str, Any]) -> int:
    """Heuristic: count populated fields for best-of-N selection."""
    if not isinstance(canonical, dict):
        return 0
    fields = canonical.get("fields", {})
    count = 0
    count += len(fields.get("current_anti_seizure_medications", []))
    count += len(fields.get("seizure_types", []))
    if fields.get("epilepsy_diagnosis", {}).get("value"):
        count += 1
    if fields.get("eeg", {}).get("result") in {"normal", "abnormal"}:
        count += 1
    if fields.get("mri", {}).get("result") in {"normal", "abnormal"}:
        count += 1
    if fields.get("current_seizure_frequency", {}).get("value"):
        count += 1
    return count


def run_sas_best_of_n(
    document: dict[str, Any],
    spec: Any,
    run_root: Path,
    base_harness: str,
    n: int,
    schema_path: Path,
    stub: bool = False,
) -> dict[str, Any]:
    """Run single-agent best-of-N baseline.

    Runs N independent extractions and selects the one with the highest
    heuristic score (schema-valid > parse-success > field count).
    """
    doc_id = document["document_id"]
    candidates: list[tuple[int, bool, dict[str, Any] | None, int, Path]] = []
    total_tokens_all = 0

    for i in range(n):
        trial_root = run_root / f"trial_{i}"
        if base_harness.upper() == "E3":
            canonical, responses, tokens = run_base_e3(document, spec, trial_root, schema_path, stub=stub)
        else:
            canonical, responses, tokens = run_base_h6fs(
                document, spec, trial_root, stub=stub, use_h6full=(base_harness.upper() == "H6FULL")
            )
        total_tokens_all += tokens

        # Score this trial
        schema_valid = False
        if canonical is not None:
            try:
                scores = validate_and_score(canonical, document["text"], schema_path, require_present_evidence=False)
                schema_valid = bool(scores.get("schema_valid"))
            except Exception:
                pass

        parse_ok = canonical is not None
        field_count = _canonical_field_count(canonical)
        # Ranking key: schema_valid > parse_ok > field_count
        rank = (1 if schema_valid else 0, 1 if parse_ok else 0, field_count)
        candidates.append((i, schema_valid, canonical, tokens, trial_root))

    # Select best
    best = max(candidates, key=lambda c: (1 if c[1] else 0, _canonical_field_count(c[2]), c[3]))
    best_index, _, best_canonical, best_tokens, best_trial_root = best

    if best_canonical is None:
        return {
            "document_id": doc_id,
            "status": "all_trials_failed",
            "canonical": None,
            "total_tokens": total_tokens_all,
            "best_trial": best_index,
        }

    # Copy best canonical to run root
    write_json(run_root / "canonical.json", best_canonical)
    # Save metadata about selection
    write_json(run_root / "best_of_n_meta.json", {
        "n": n,
        "best_trial": best_index,
        "trial_scores": [
            {"trial": i, "schema_valid": sv, "field_count": _canonical_field_count(c), "tokens": t}
            for i, sv, c, t, _ in candidates
        ],
    })

    return {
        "document_id": doc_id,
        "status": "success",
        "canonical": best_canonical,
        "total_tokens": total_tokens_all,
        "best_trial": best_index,
    }


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


def _load_document_ids(args: argparse.Namespace) -> list[str]:
    return load_split_ids(Path(args.splits), args.split, args.limit)


def _run_documents(args: argparse.Namespace, runner: Any, extra_kwargs: dict[str, Any]) -> list[dict[str, Any]]:
    specs = load_model_specs(Path(args.registry))
    spec = specs[args.model]
    document_ids = _load_document_ids(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Pass stub flag through to runners
    extra_kwargs["stub"] = getattr(args, "stub_calls", False)

    records: list[dict[str, Any]] = []
    for doc_id in document_ids:
        document = preprocess_document(doc_id, Path(args.exect_root))
        run_root = output_dir / args.model / args.design / doc_id
        result = runner(document, spec, run_root, **extra_kwargs)
        record = {
            "document_id": doc_id,
            "model_label": args.model,
            "design": args.design,
            "status": result["status"],
            "total_tokens": result.get("total_tokens", 0),
            "flags_count": result.get("flags_count", 0),
            "corrector_run": result.get("corrector_run", False),
            "drop_rate": result.get("drop_rate"),
            "modify_rate": result.get("modify_rate"),
            "best_trial": result.get("best_trial"),
            "canonical_path": str(run_root / "canonical.json"),
        }
        records.append(record)
        print(f"{record['status']}: {args.model} {args.design} {doc_id}", flush=True)
    return records


def command_run_ma_a(args: argparse.Namespace) -> int:
    records = _run_documents(args, run_ma_a, {
        "base_harness": args.base_harness,
        "schema_path": Path(args.schema),
    })
    write_csv(Path(args.output_dir) / args.design / "call_report.csv", records)
    manifest = {
        "design": args.design,
        "base_harness": args.base_harness,
        "model_label": args.model,
        "split": args.split,
        "document_ids": [r["document_id"] for r in records],
        "output_dir": args.output_dir,
    }
    write_json(Path(args.output_dir) / args.design / "manifest.json", manifest)
    return 0


def command_run_sas_long_cot(args: argparse.Namespace) -> int:
    records = _run_documents(args, run_sas_long_cot, {
        "base_harness": args.base_harness,
        "schema_path": Path(args.schema),
    })
    write_csv(Path(args.output_dir) / args.design / "call_report.csv", records)
    manifest = {
        "design": args.design,
        "base_harness": args.base_harness,
        "model_label": args.model,
        "split": args.split,
        "document_ids": [r["document_id"] for r in records],
        "output_dir": args.output_dir,
    }
    write_json(Path(args.output_dir) / args.design / "manifest.json", manifest)
    return 0


def command_run_sas_best_of_n(args: argparse.Namespace) -> int:
    records = _run_documents(args, run_sas_best_of_n, {
        "base_harness": args.base_harness,
        "n": args.n,
        "schema_path": Path(args.schema),
    })
    write_csv(Path(args.output_dir) / args.design / "call_report.csv", records)
    manifest = {
        "design": args.design,
        "base_harness": args.base_harness,
        "n": args.n,
        "model_label": args.model,
        "split": args.split,
        "document_ids": [r["document_id"] for r in records],
        "output_dir": args.output_dir,
    }
    write_json(Path(args.output_dir) / args.design / "manifest.json", manifest)
    return 0


def command_score(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    gold = load_gold(Path(args.markup_root), Path(args.exect_root))
    schema_path = Path(args.schema)

    # Discover model/design subdirectories
    all_scores: dict[str, list[dict[str, Any]]] = {}
    all_tokens: dict[str, list[int]] = {}

    for model_dir in run_dir.iterdir():
        if not model_dir.is_dir():
            continue
        for design_dir in model_dir.iterdir():
            if not design_dir.is_dir():
                continue
            condition_key = f"{model_dir.name}:{design_dir.name}"
            doc_scores = []
            tokens_list = []
            for doc_dir in design_dir.iterdir():
                if not doc_dir.is_dir():
                    continue
                canonical_path = doc_dir / "canonical.json"
                if not canonical_path.exists():
                    continue
                try:
                    data = json.loads(canonical_path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                doc_id = doc_dir.name
                doc_obj = preprocess_document(doc_id, Path(args.exect_root))
                score = score_document(data, doc_obj["text"], gold.get(doc_id), schema_path)
                score["document_id"] = doc_id
                doc_scores.append(score)

                # Load tokens from response logs if available (search recursively for trial subdirs)
                total = 0
                for resp_file in doc_dir.rglob("*_response.json"):
                    try:
                        resp_data = json.loads(resp_file.read_text(encoding="utf-8"))
                        total += resp_data.get("token_usage", {}).get("input_tokens", 0)
                        total += resp_data.get("token_usage", {}).get("output_tokens", 0)
                    except Exception:
                        pass
                tokens_list.append(total)

            if doc_scores:
                all_scores[condition_key] = doc_scores
                all_tokens[condition_key] = tokens_list

    summary_rows = []
    for condition_key, doc_scores in all_scores.items():
        flat = flatten_summary(condition_key, doc_scores)
        flat["condition"] = condition_key
        bc = _compute_benchcomp(flat)
        flat["benchcomp"] = bc
        mean_tokens = sum(all_tokens.get(condition_key, [0])) / max(len(all_tokens.get(condition_key, [])), 1)
        flat["mean_total_tokens"] = round(mean_tokens, 1)
        flat["eabc"] = _compute_eabc(bc, int(mean_tokens))
        summary_rows.append(flat)

    out_path = run_dir / "evaluation_summary.csv"
    write_csv(out_path, summary_rows)
    print(f"scored {sum(len(v) for v in all_scores.values())} documents, {len(summary_rows)} conditions")
    print(f"wrote: {out_path}")
    for row in summary_rows:
        med = row.get("medication_name_f1")
        sz = row.get("seizure_type_f1_collapsed")
        dx = row.get("epilepsy_diagnosis_accuracy") or row.get("epilepsy_diagnosis_accuracy_collapsed")
        eeg = row.get("eeg_accuracy")
        mri = row.get("mri_accuracy")
        bc = row.get("benchcomp")
        eabc = row.get("eabc")
        print(
            f"  {row['condition']}: med={_fmt(med)} sz={_fmt(sz)} dx={_fmt(dx)} "
            f"eeg={_fmt(eeg)} mri={_fmt(mri)} benchcomp={_fmt(bc)} eabc={_fmt(eabc)} "
            f"tokens={row.get('mean_total_tokens', 'n/a')}"
        )
    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return str(value)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Multi-agent exploration pipeline (MA_v2)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Common args
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--model", required=True, help="Model label from registry")
    common.add_argument("--base-harness", default="H6full", choices=["H6fs", "H6full", "E3"], help="Base single-agent harness")
    common.add_argument("--split", default="development", choices=["development", "validation", "test"])
    common.add_argument("--limit", type=int, help="Limit number of documents")
    common.add_argument("--stub-calls", action="store_true", help="Use stub provider (no real model calls)")
    common.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT))
    common.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    common.add_argument("--splits", default=str(DEFAULT_SPLITS))
    common.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    common.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    common.add_argument("--schema", default=str(DEFAULT_SCHEMA))

    # run-ma-a
    ma_a = sub.add_parser("run-ma-a", parents=[common], help="Run MA-A verifier-only augmentation")
    ma_a.add_argument("--design", default="MA_A", help="Design label for output directory")
    ma_a.set_defaults(func=command_run_ma_a)

    # run-sas-long-cot
    sas_cot = sub.add_parser("run-sas-long-cot", parents=[common], help="Run single-agent long-CoT baseline")
    sas_cot.add_argument("--design", default="SAS_long_CoT", help="Design label for output directory")
    sas_cot.set_defaults(func=command_run_sas_long_cot)

    # run-sas-best-of-n
    sas_bon = sub.add_parser("run-sas-best-of-n", parents=[common], help="Run single-agent best-of-N baseline")
    sas_bon.add_argument("--n", type=int, default=3, help="Number of independent samples")
    sas_bon.add_argument("--design", default="SAS_best_of_N", help="Design label for output directory")
    sas_bon.set_defaults(func=command_run_sas_best_of_n)

    # score
    score_p = sub.add_parser("score", help="Score existing run directory")
    score_p.add_argument("--run-dir", required=True, help="Run output directory containing canonical.json files")
    score_p.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    score_p.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    score_p.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    score_p.set_defaults(func=command_score)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
