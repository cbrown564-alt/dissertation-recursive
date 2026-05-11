#!/usr/bin/env python3
"""Multi-agent extraction pipeline (MA_v1).

Implements the four-role architecture from docs/36_multi_agent_pipeline_plan.md:
  Stage 1  - Section/Timeline Agent         (1 call)
  Stage 2  - Parallel Field Extractor Agents (2a medications, 2b seizure/freq,
                                              2c investigations, 2d diagnosis)
  Stage 3  - Verification Agent             (1 call)
  Stage 4  - Aggregator Agent               (1 call)

Usage:
    python src/multi_agent.py run --stage ma0 --stub-calls
    python src/multi_agent.py run --stage ma1 --models gpt_5_4_mini --docs 10
    python src/multi_agent.py run --stage ma1 --models gpt_5_4_mini qwen_35b_local --docs 10
    python src/multi_agent.py run --stage ma2 --models gpt_5_4_mini qwen_35b_local
    python src/multi_agent.py run --stage ma3 --models gpt_5_5
    python src/multi_agent.py score --run-dir runs/multi_agent/stage_ma1_dev_pilot
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from direct_baselines import load_split_ids, parse_json_response, write_json, write_text
from evaluate import DEFAULT_MARKUP_ROOT, flatten_summary, load_gold, score_document
from intake import DEFAULT_EXECT_ROOT, DEFAULT_SPLITS, preprocess_document
from model_expansion import (
    BENCHMARK_EPILEPSY_LABELS,
    BENCHMARK_SEIZURE_LABELS,
    benchmark_label_block,
    combined_cost,
    combined_usage,
    projected_canonical,
    write_csv,
)
from model_providers import ModelRequest, adapter_for, write_response_log
from model_registry import DEFAULT_REGISTRY, load_model_specs, write_registry_snapshot
from validate_extraction import DEFAULT_SCHEMA


DEFAULT_OUTPUT_ROOT = Path("runs/multi_agent")

STAGE_OUTPUT_DIR = {
    "ma0": "stage_ma0_stub",
    "ma1": "stage_ma1_dev_pilot",
    "ma2": "stage_ma2_validation",
    "ma3": "stage_ma3_gpt55",
}

STAGE_SPLITS = {
    "ma0": "development",
    "ma1": "development",
    "ma2": "validation",
    "ma3": "validation",
}

STAGE_DEFAULT_DOCS = {
    "ma0": 2,
    "ma1": 10,
    "ma2": None,  # full split
    "ma3": None,
}

# Benchmark composite weights — identical to final_full_field.py BenchComp.
BENCHMARK_COMPOSITE_WEIGHTS = {
    "medication_name_f1": 0.30,
    "seizure_type_f1_collapsed": 0.25,
    "epilepsy_diagnosis_accuracy_collapsed_or_plain": 0.20,
    "eeg_accuracy": 0.125,
    "mri_accuracy": 0.125,
}

# Promotion thresholds from plan doc (MA2 → MA3).
PROMOTION_GATES = {
    "benchcomp_gt": 0.810,          # beats frontier E3
    "seizure_f1_collapsed_ge": 0.660,
}


# ---------------------------------------------------------------------------
# Stage prompt builders
# ---------------------------------------------------------------------------

def build_stage1_prompt(text: str) -> str:
    return "\n\n".join([
        "You are a clinical document segmenter. Read the epilepsy clinic letter below.",
        (
            "Identify the main clinical sections and classify each as current-patient or "
            "historical/family context. Then extract exact verbatim quotes that describe "
            "the patient's CURRENT seizure status, any HISTORICAL seizure mentions (no "
            "longer current), and any seizure mentions about FAMILY MEMBERS (not the patient)."
        ),
        "Return JSON only with this shape:",
        json.dumps({
            "sections": [
                {"label": "Presenting Complaint", "is_current": True,
                 "is_family": False, "key_phrases": ["..."]}
            ],
            "current_seizure_quotes": ["exact verbatim quote"],
            "historical_seizure_quotes": ["exact verbatim quote"],
            "family_seizure_quotes": ["exact verbatim quote"],
        }, indent=2),
        (
            "Section labels to use (use as many as apply): "
            "Presenting Complaint, Seizure History, Past Medical History, Family History, "
            "Current Medications, Investigations, Assessment and Plan."
        ),
        "If a section is absent in this letter, omit it. Use [] for empty quote lists.",
        "## Source Letter",
        text,
    ])


def build_stage2a_prompt(text: str, seg: dict[str, Any] | None) -> str:
    ctx_parts = []
    if seg and seg.get("sections"):
        med_sections = [s for s in seg["sections"] if "medication" in s.get("label", "").lower()]
        if med_sections:
            phrases = []
            for s in med_sections:
                phrases.extend(s.get("key_phrases", []))
            if phrases:
                ctx_parts.append("Medication section key phrases: " + "; ".join(p for p in phrases if p != "..."))
    context_block = ("\n\n## Segmentation Context\n" + "\n".join(ctx_parts)) if ctx_parts else ""

    return "\n\n".join(filter(None, [
        "Extract CURRENT anti-seizure medications from this epilepsy clinic letter.",
        "Return JSON only with this shape:",
        '{"medications": [{"name": "...", "dose": "...", "unit": "...", "frequency": "..."}]}',
        (
            "Include only currently prescribed medications; exclude discontinued or historical ones. "
            "Use generic drug names where possible (e.g. levetiracetam not Keppra). "
            "Include dose (number only), unit (mg/mcg/g/ml), and frequency "
            "(once daily / twice daily / three times daily / nocte / as required) "
            "if stated; use null for any component not mentioned."
        ),
        context_block if context_block else None,
        "## Source Letter",
        text,
    ]))


def build_stage2b_prompt(text: str, seg: dict[str, Any] | None) -> str:
    current_quotes = (seg or {}).get("current_seizure_quotes") or []
    family_quotes = (seg or {}).get("family_seizure_quotes") or []
    historical_quotes = (seg or {}).get("historical_seizure_quotes") or []

    quotes_block_lines = []
    if current_quotes:
        quotes_block_lines.append(
            "CURRENT seizure quotes (use ONLY these for seizure_types):\n"
            + "\n".join(f"  - {q}" for q in current_quotes if q and q != "...")
        )
    if family_quotes:
        quotes_block_lines.append(
            "FAMILY HISTORY quotes (DO NOT use these — they describe relatives, not the patient):\n"
            + "\n".join(f"  - {q}" for q in family_quotes if q and q != "...")
        )
    if historical_quotes:
        quotes_block_lines.append(
            "HISTORICAL quotes (DO NOT use — these describe past events no longer current):\n"
            + "\n".join(f"  - {q}" for q in historical_quotes if q and q != "...")
        )

    quotes_block = ("\n\n## Segmentation Output\n" + "\n\n".join(quotes_block_lines)) if quotes_block_lines else ""

    return "\n\n".join(filter(None, [
        "Extract CURRENT seizure types and current seizure frequency from this epilepsy clinic letter.",
        "Return JSON only with this shape:",
        '{"seizure_types": [], "current_seizure_frequency": null}',
        (
            "IMPORTANT: Include ONLY the patient's CURRENT seizure types as documented. "
            "Do NOT include seizure types from family history or historical sections. "
            "If the patient has seizures but the specific type is not described or is unclear, "
            "use 'unknown seizure type'. "
            "If the patient is currently seizure-free, use 'seizure free'. "
            "Do not include aura, warning, symptom, medication side effect, or investigation "
            "finding labels as seizure types."
        ),
        (
            "current_seizure_frequency: copy the frequency expression from the letter as a short "
            "string (e.g. '2 per month', 'daily', 'every 6 weeks') or null if not stated "
            "or patient is seizure-free."
        ),
        benchmark_label_block(),
        quotes_block if quotes_block else None,
        "## Source Letter",
        text,
    ]))


def build_stage2c_prompt(text: str, seg: dict[str, Any] | None) -> str:
    ctx_parts = []
    if seg and seg.get("sections"):
        inv_sections = [s for s in seg["sections"] if "investigation" in s.get("label", "").lower()]
        if inv_sections:
            phrases = []
            for s in inv_sections:
                phrases.extend(s.get("key_phrases", []))
            if phrases:
                ctx_parts.append("Investigations section key phrases: " + "; ".join(p for p in phrases if p != "..."))
    context_block = ("\n\n## Segmentation Context\n" + "\n".join(ctx_parts)) if ctx_parts else ""

    return "\n\n".join(filter(None, [
        "Extract EEG and MRI investigation results from this epilepsy clinic letter.",
        "Return JSON only with this shape:",
        '{"eeg": null, "mri": null}',
        (
            'Use "normal" or "abnormal" only — do not copy raw descriptions. '
            "Classify as abnormal if the result mentions: spike, wave, discharge, "
            "epileptiform, slowing, polyspike, or photosensitivity. "
            "Use null if the investigation was not mentioned or not performed."
        ),
        context_block if context_block else None,
        "## Source Letter",
        text,
    ]))


def build_stage2d_prompt(text: str) -> str:
    return "\n\n".join([
        "Extract the epilepsy diagnosis or type from this epilepsy clinic letter.",
        "Return JSON only with this shape:",
        '{"epilepsy_diagnosis_type": null}',
        (
            "Use one of the allowed labels or null. "
            "Do not invent a diagnosis if the letter does not clearly support one."
        ),
        "Allowed epilepsy_diagnosis_type labels:\n" + "\n".join(f"- {lbl}" for lbl in BENCHMARK_EPILEPSY_LABELS),
        "## Source Letter",
        text,
    ])


def build_stage3_prompt(text: str, stage2: dict[str, dict[str, Any] | None]) -> str:
    meds = (stage2.get("stage2a_medications") or {}).get("medications") or []
    sz_types = (stage2.get("stage2b_seizure") or {}).get("seizure_types") or []
    sz_freq = (stage2.get("stage2b_seizure") or {}).get("current_seizure_frequency")
    eeg = (stage2.get("stage2c_investigations") or {}).get("eeg")
    mri = (stage2.get("stage2c_investigations") or {}).get("mri")
    dx = (stage2.get("stage2d_diagnosis") or {}).get("epilepsy_diagnosis_type")

    extracted_summary = json.dumps({
        "medications": meds,
        "seizure_types": sz_types,
        "current_seizure_frequency": sz_freq,
        "investigations": {"eeg": eeg, "mri": mri},
        "epilepsy_diagnosis_type": dx,
    }, indent=2)

    schema = json.dumps({
        "medications": [{"name": "...", "dose": "...", "unit": "...", "frequency": "...",
                         "action": "keep|drop|modify", "evidence_quote": "...", "reason": "..."}],
        "seizure_types": [{"label": "...", "action": "keep|drop|modify",
                           "evidence_quote": "...", "reason": "..."}],
        "seizure_frequency": {"value": "...", "action": "keep|drop", "evidence_quote": "..."},
        "investigations": {
            "eeg": {"value": "...", "action": "keep|drop", "evidence_quote": "..."},
            "mri": {"value": "...", "action": "keep|drop", "evidence_quote": "..."},
        },
        "epilepsy_diagnosis": {"value": "...", "action": "keep|drop|modify",
                                "evidence_quote": "...", "reason": "..."},
        "consistency_flags": [],
    }, indent=2)

    return "\n\n".join([
        "You are a clinical verification agent. Review the extracted fields against the source letter.",
        f"Return JSON only with this shape:\n{schema}",
        (
            "Verification rules:\n"
            "1. DROP any medication that is clearly historical or discontinued (not current).\n"
            "2. DROP any seizure type that comes from family history or describes a historical event "
            "no longer occurring in the patient.\n"
            "3. DROP any investigation result that has no supporting text in the letter.\n"
            "4. DROP any epilepsy diagnosis that is speculative or unsupported.\n"
            "5. MODIFY any field where the letter states a different value.\n"
            "6. For every kept or modified item, provide a short exact verbatim quote from the letter.\n"
            "7. Record any cross-field inconsistencies in consistency_flags.\n"
            "Set action='keep' when the item is correct and supported."
        ),
        "## Extracted Fields\n" + extracted_summary,
        "## Source Letter",
        text,
    ])


def build_stage4_prompt(verified: dict[str, Any] | None, stage2_fallback: dict[str, dict[str, Any] | None] | None = None) -> str:
    if verified:
        kept_meds = [
            {"name": m["name"], "dose": m.get("dose"), "unit": m.get("unit"), "frequency": m.get("frequency")}
            for m in (verified.get("medications") or [])
            if m.get("action") in {"keep", "modify"} and m.get("name")
        ]
        kept_sz = [
            s["label"] for s in (verified.get("seizure_types") or [])
            if s.get("action") in {"keep", "modify"} and s.get("label")
        ]
        freq_obj = verified.get("seizure_frequency") or {}
        kept_freq = freq_obj.get("value") if freq_obj.get("action") in {"keep", "modify"} else None
        inv = verified.get("investigations") or {}
        kept_eeg = inv.get("eeg", {}).get("value") if (inv.get("eeg") or {}).get("action") in {"keep", "modify"} else None
        kept_mri = inv.get("mri", {}).get("value") if (inv.get("mri") or {}).get("action") in {"keep", "modify"} else None
        dx_obj = verified.get("epilepsy_diagnosis") or {}
        kept_dx = dx_obj.get("value") if dx_obj.get("action") in {"keep", "modify"} else None
        verified_summary = json.dumps({
            "medications": kept_meds,
            "seizure_types": kept_sz,
            "current_seizure_frequency": kept_freq,
            "investigations": {"eeg": kept_eeg, "mri": kept_mri},
            "epilepsy_diagnosis_type": kept_dx,
        }, indent=2)
    elif stage2_fallback:
        # Stage 3 failed — aggregate Stage 2 outputs directly
        meds = (stage2_fallback.get("stage2a_medications") or {}).get("medications") or []
        sz = (stage2_fallback.get("stage2b_seizure") or {}).get("seizure_types") or []
        freq = (stage2_fallback.get("stage2b_seizure") or {}).get("current_seizure_frequency")
        eeg = (stage2_fallback.get("stage2c_investigations") or {}).get("eeg")
        mri = (stage2_fallback.get("stage2c_investigations") or {}).get("mri")
        dx = (stage2_fallback.get("stage2d_diagnosis") or {}).get("epilepsy_diagnosis_type")
        verified_summary = json.dumps({
            "medications": meds,
            "seizure_types": sz,
            "current_seizure_frequency": freq,
            "investigations": {"eeg": eeg, "mri": mri},
            "epilepsy_diagnosis_type": dx,
        }, indent=2)
    else:
        verified_summary = "{}"

    schema = (
        '{"medications":[{"name":"...","dose":"...","unit":"...","frequency":"..."}],'
        '"seizure_types":[],"epilepsy_diagnosis_type":null,'
        '"current_seizure_frequency":null,'
        '"investigations":{"eeg":null,"mri":null}}'
    )

    return "\n\n".join([
        "Produce the final clinical extraction JSON for this epilepsy clinic letter.",
        f"Return JSON only with this shape:\n{schema}",
        (
            "Include only the verified/kept fields from the input. "
            "Set fields to [] or null when empty. "
            "Medications must be a list of objects with name/dose/unit/frequency."
        ),
        "## Verified Fields\n" + verified_summary,
    ])


# ---------------------------------------------------------------------------
# Core call helper
# ---------------------------------------------------------------------------

def _call_stage(
    prompt: str,
    spec: Any,
    adapter: Any,
    stage_name: str,
    doc_id: str,
    run_root: Path,
    max_tokens: int,
) -> tuple[Any, dict[str, Any] | None]:
    """Make one model call for a pipeline stage. Returns (response, parsed_dict or None)."""
    run_root.mkdir(parents=True, exist_ok=True)
    prompt_path = run_root / f"{stage_name}_prompt.txt"
    raw_path = run_root / f"{stage_name}_raw.txt"
    log_path = run_root / f"{stage_name}_response.json"
    write_text(prompt_path, prompt)

    request = ModelRequest(
        prompt=prompt,
        model=spec,
        harness_id="MA_v1",
        temperature=0.0,
        max_output_tokens=max_tokens,
        metadata={"document_id": doc_id, "stage": stage_name},
    )
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

    return response, parsed


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------

def run_pipeline(
    document: dict[str, Any],
    spec: Any,
    adapter: Any,
    run_root: Path,
    max_tokens_stage3: int = 1024,
    max_tokens_stage4: int = 512,
) -> tuple[list[Any], dict[str, dict[str, Any] | None], dict[str, Any] | None]:
    """Run the full 4-stage MA_v1 pipeline for one document.

    Returns:
        all_responses   — list of ModelResponse objects (one per call)
        stage_outputs   — dict mapping stage name → parsed dict (or None on parse failure)
        final_payload   — Stage 4 output dict for passing to projected_canonical
    """
    text = document["text"]
    doc_id = document["document_id"]
    all_responses: list[Any] = []
    stage_outputs: dict[str, dict[str, Any] | None] = {}

    # Stage 1: Segmentation
    resp1, seg = _call_stage(
        build_stage1_prompt(text), spec, adapter, "stage1_segmentation",
        doc_id, run_root, max_tokens=256,
    )
    all_responses.append(resp1)
    stage_outputs["stage1_segmentation"] = seg

    # Stage 2: Field extraction — parallel for API, sequential for Ollama
    stage2_defs = [
        ("stage2a_medications",    build_stage2a_prompt(text, seg),  512),
        ("stage2b_seizure",        build_stage2b_prompt(text, seg),  256),
        ("stage2c_investigations", build_stage2c_prompt(text, seg),  128),
        ("stage2d_diagnosis",      build_stage2d_prompt(text),       128),
    ]

    if spec.provider == "ollama":
        for name, prompt, max_tok in stage2_defs:
            resp, parsed = _call_stage(prompt, spec, adapter, name, doc_id, run_root, max_tok)
            all_responses.append(resp)
            stage_outputs[name] = parsed
    else:
        # Thread-pool parallel for API models
        futures: dict[str, Any] = {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            for name, prompt, max_tok in stage2_defs:
                futures[name] = pool.submit(
                    _call_stage, prompt, spec, adapter, name, doc_id, run_root, max_tok
                )
        # Collect in definition order so all_responses is deterministic
        for name, _, _ in stage2_defs:
            resp, parsed = futures[name].result()
            all_responses.append(resp)
            stage_outputs[name] = parsed

    # Stage 3: Verification
    resp3, verified = _call_stage(
        build_stage3_prompt(text, stage_outputs),
        spec, adapter, "stage3_verification",
        doc_id, run_root, max_tokens=max_tokens_stage3,
    )
    all_responses.append(resp3)
    stage_outputs["stage3_verification"] = verified

    # Stage 4: Aggregation (falls back to raw Stage 2 if Stage 3 failed)
    resp4, final = _call_stage(
        build_stage4_prompt(verified, stage_outputs if verified is None else None),
        spec, adapter, "stage4_aggregation",
        doc_id, run_root, max_tokens=max_tokens_stage4,
    )
    all_responses.append(resp4)
    stage_outputs["stage4_aggregation"] = final

    return all_responses, stage_outputs, final


# ---------------------------------------------------------------------------
# MA-specific metrics extracted from stage outputs
# ---------------------------------------------------------------------------

def ma_metrics(stage_outputs: dict[str, dict[str, Any] | None]) -> dict[str, Any]:
    seg = stage_outputs.get("stage1_segmentation") or {}
    verified = stage_outputs.get("stage3_verification") or {}

    section_count = len(seg.get("sections") or [])
    current_sz_count = len([q for q in (seg.get("current_seizure_quotes") or []) if q and q != "..."])

    all_stage2_names = ["stage2a_medications", "stage2b_seizure", "stage2c_investigations", "stage2d_diagnosis"]
    stage_parse = {
        "stage1_segmentation": stage_outputs.get("stage1_segmentation") is not None,
        "stage3_verification": stage_outputs.get("stage3_verification") is not None,
        "stage4_aggregation": stage_outputs.get("stage4_aggregation") is not None,
    }
    for name in all_stage2_names:
        stage_parse[name] = stage_outputs.get(name) is not None
    all_stages_ok = all(stage_parse.values())

    meds_v = verified.get("medications") or []
    sz_v = verified.get("seizure_types") or []
    all_verified_items = meds_v + sz_v
    drop_count = sum(1 for item in all_verified_items if item.get("action") == "drop")
    modify_count = sum(1 for item in all_verified_items if item.get("action") == "modify")
    total_verified = len(all_verified_items)

    return {
        "stage1_section_count": section_count,
        "stage1_current_seizure_count": current_sz_count,
        "stage3_drop_rate": round(drop_count / total_verified, 3) if total_verified else None,
        "stage3_modify_rate": round(modify_count / total_verified, 3) if total_verified else None,
        "all_stages_parse_ok": all_stages_ok,
        **{f"parse_{k}": v for k, v in stage_parse.items()},
    }


# ---------------------------------------------------------------------------
# Run command
# ---------------------------------------------------------------------------

def command_run(args: argparse.Namespace) -> int:
    stage = args.stage.lower()
    if stage not in STAGE_OUTPUT_DIR:
        print(f"unknown stage: {stage}. Expected one of {list(STAGE_OUTPUT_DIR)}", file=sys.stderr)
        return 1

    output_dir = Path(args.output_root) / STAGE_OUTPUT_DIR[stage]
    split = args.split or STAGE_SPLITS[stage]
    doc_limit = args.docs or STAGE_DEFAULT_DOCS[stage]

    specs = load_model_specs(Path(args.registry))
    write_registry_snapshot(output_dir / "registry_snapshot.json", Path(args.registry))

    model_labels = args.models or (["gpt_5_4_mini"] if stage in {"ma1", "ma2"} else ["gpt_5_5"])
    for label in model_labels:
        if label not in specs:
            print(f"unknown model label: {label}", file=sys.stderr)
            return 1

    document_ids = load_split_ids(Path(args.splits), split, doc_limit)
    gold = load_gold(Path(args.markup_root), Path(args.exect_root))

    all_call_rows: list[dict[str, Any]] = []
    all_scores: dict[str, list[dict[str, Any]]] = {}

    max_tokens_s3 = args.max_output_tokens_stage3 or 1024
    max_tokens_s4 = args.max_output_tokens_stage4 or 512

    for model_label in model_labels:
        spec = specs[model_label]
        provider = "stub" if args.stub_calls else spec.provider
        adapter = adapter_for(provider)
        condition_key = f"{model_label}:MA_v1"

        for doc_id in document_ids:
            document = preprocess_document(doc_id, Path(args.exect_root))
            run_root = output_dir / model_label / "MA_v1" / doc_id

            print(f"  [{model_label}] {doc_id} ...", flush=True, end=" ")
            responses, stage_outputs, final_payload = run_pipeline(
                document, spec, adapter, run_root,
                max_tokens_stage3=max_tokens_s3,
                max_tokens_stage4=max_tokens_s4,
            )

            # Build canonical output for scoring
            canonical: dict[str, Any] | None = None
            parse_ok = final_payload is not None
            if parse_ok:
                try:
                    meta_row: dict[str, str] = {
                        "latency_ms": str(sum(r.latency_ms for r in responses)),
                        "input_tokens": str(combined_usage(responses).input_tokens or 0),
                        "output_tokens": str(combined_usage(responses).output_tokens or 0),
                        "estimated_cost": str(combined_cost(responses) or 0.0),
                    }
                    canonical = projected_canonical(
                        document_id=doc_id,
                        harness_id="MA_v1",
                        model_label=model_label,
                        payload=final_payload,
                        row=meta_row,
                        document=document,
                    )
                    write_json(run_root / "canonical.json", canonical)
                except Exception as exc:
                    canonical = None
                    print(f"[projection error: {exc}]", end=" ")

            # Score the canonical output
            score = score_document(
                canonical,
                document["text"],
                gold.get(doc_id, type("G", (), {"document_id": doc_id})()),
                Path(args.schema),
            )
            score["document_id"] = doc_id
            score["system"] = condition_key
            all_scores.setdefault(condition_key, []).append(score)

            # Build the MA-specific extras
            ma_extra = ma_metrics(stage_outputs)
            total_latency = round(sum(r.latency_ms for r in responses), 3)
            usage = combined_usage(responses)
            cost = combined_cost(responses)
            errors = [r.error for r in responses if r.error]

            call_row: dict[str, Any] = {
                "model_label": model_label,
                "provider": spec.provider,
                "called_provider": adapter.provider,
                "provider_model_id": spec.provider_model_id,
                "harness_id": "MA_v1",
                "document_id": doc_id,
                "status": "success" if not errors else "unavailable",
                "error": "; ".join(errors),
                "total_calls": len(responses),
                "parse_success": str(parse_ok),
                "canonical_written": str(canonical is not None),
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "latency_ms": total_latency,
                "estimated_cost": cost,
                **ma_extra,
            }
            all_call_rows.append(call_row)
            status_str = "ok" if parse_ok else "parse_fail"
            print(f"{status_str} | {total_latency:.0f}ms", flush=True)

    write_csv(output_dir / "call_report.csv", all_call_rows)

    # Score summaries
    summary_rows: list[dict[str, Any]] = []
    for condition_key, doc_scores in all_scores.items():
        flat = flatten_summary(condition_key, doc_scores)
        flat["condition"] = condition_key
        summary_rows.append(flat)

    write_csv(output_dir / "evaluation_summary.csv", summary_rows)

    # Print quick comparison table
    print("\n--- MA_v1 results ---")
    for row in summary_rows:
        med = row.get("medication_name_f1")
        sz = row.get("seizure_type_f1_collapsed")
        dx = row.get("epilepsy_diagnosis_accuracy") or row.get("epilepsy_diagnosis_accuracy_collapsed")
        eeg = row.get("eeg_accuracy")
        mri = row.get("mri_accuracy")
        benchcomp = _compute_benchcomp(row)
        print(
            f"  {row['condition']}: "
            f"med={_fmt(med)} sz={_fmt(sz)} dx={_fmt(dx)} "
            f"eeg={_fmt(eeg)} mri={_fmt(mri)} benchcomp={_fmt(benchcomp)}"
        )

    if stage == "ma2":
        _print_promotion_decision(summary_rows)

    write_json(output_dir / "manifest.json", {
        "stage": stage,
        "split": split,
        "models": model_labels,
        "document_ids": document_ids,
        "stub_calls": args.stub_calls,
        "call_report": str(output_dir / "call_report.csv"),
        "evaluation_summary": str(output_dir / "evaluation_summary.csv"),
    })

    return 0


# ---------------------------------------------------------------------------
# Score command (re-score existing artifacts)
# ---------------------------------------------------------------------------

def command_score(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        print(f"run directory not found: {run_dir}", file=sys.stderr)
        return 1

    gold = load_gold(Path(args.markup_root), Path(args.exect_root))
    all_scores: dict[str, list[dict[str, Any]]] = {}

    for canonical_path in sorted(run_dir.rglob("canonical.json")):
        parts = canonical_path.parts
        # Expected layout: run_dir / model_label / MA_v1 / doc_id / canonical.json
        try:
            model_label = parts[-4]
            doc_id = parts[-2]
        except IndexError:
            continue

        condition_key = f"{model_label}:MA_v1"
        try:
            data = json.loads(canonical_path.read_text(encoding="utf-8"))
        except Exception:
            data = None

        doc_obj = preprocess_document(doc_id, Path(args.exect_root))
        score = score_document(
            data,
            doc_obj["text"],
            gold.get(doc_id, type("G", (), {"document_id": doc_id})()),
            Path(args.schema),
        )
        score["document_id"] = doc_id
        score["system"] = condition_key
        all_scores.setdefault(condition_key, []).append(score)

    summary_rows = []
    for condition_key, doc_scores in all_scores.items():
        flat = flatten_summary(condition_key, doc_scores)
        flat["condition"] = condition_key
        flat["benchcomp"] = _compute_benchcomp(flat)
        summary_rows.append(flat)

    out_path = run_dir / "evaluation_summary_rescored.csv"
    write_csv(out_path, summary_rows)
    print(f"rescored {sum(len(v) for v in all_scores.values())} documents, {len(summary_rows)} conditions")
    print(f"wrote: {out_path}")
    for row in summary_rows:
        med = row.get("medication_name_f1")
        sz = row.get("seizure_type_f1_collapsed")
        dx = row.get("epilepsy_diagnosis_accuracy") or row.get("epilepsy_diagnosis_accuracy_collapsed")
        eeg = row.get("eeg_accuracy")
        mri = row.get("mri_accuracy")
        print(
            f"  {row['condition']}: med={_fmt(med)} sz={_fmt(sz)} dx={_fmt(dx)} "
            f"eeg={_fmt(eeg)} mri={_fmt(mri)} benchcomp={_fmt(row.get('benchcomp'))}"
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


def _print_promotion_decision(summary_rows: list[dict[str, Any]]) -> None:
    print("\n--- MA2 Promotion decision ---")
    for row in summary_rows:
        bc = _compute_benchcomp(row)
        sz = row.get("seizure_type_f1_collapsed")
        gates_met = []
        if bc is not None and bc > PROMOTION_GATES["benchcomp_gt"]:
            gates_met.append(f"BenchComp {bc:.3f} > {PROMOTION_GATES['benchcomp_gt']}")
        if sz is not None and sz >= PROMOTION_GATES["seizure_f1_collapsed_ge"]:
            gates_met.append(f"SeizureF1 {sz:.3f} >= {PROMOTION_GATES['seizure_f1_collapsed_ge']}")
        if gates_met:
            print(f"  PROMOTE {row['condition']}: {'; '.join(gates_met)}")
        else:
            print(f"  NO PROMOTION {row['condition']}: benchcomp={_fmt(bc)}, sz_f1c={_fmt(sz)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="MA_v1 multi-agent extraction pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- run ---
    run_p = sub.add_parser("run", help="Run the MA_v1 pipeline on a split")
    run_p.add_argument("--stage", default="ma1",
                       choices=list(STAGE_OUTPUT_DIR),
                       help="Pipeline stage (determines split, doc count, output dir)")
    run_p.add_argument("--models", nargs="+", default=None,
                       help="Model labels from registry (overrides stage default)")
    run_p.add_argument("--docs", type=int, default=None,
                       help="Limit number of documents (overrides stage default)")
    run_p.add_argument("--split", default=None,
                       help="Split override (development|validation|test)")
    run_p.add_argument("--stub-calls", action="store_true",
                       help="Use stub provider (no real model calls)")
    run_p.add_argument("--max-output-tokens-stage3", type=int, default=1024)
    run_p.add_argument("--max-output-tokens-stage4", type=int, default=512)
    run_p.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    run_p.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    run_p.add_argument("--splits", default=str(DEFAULT_SPLITS))
    run_p.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    run_p.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    run_p.add_argument("--schema", default=str(DEFAULT_SCHEMA))

    # --- score ---
    score_p = sub.add_parser("score", help="Re-score existing canonical artifacts")
    score_p.add_argument("--run-dir", required=True,
                         help="Run output directory containing canonical.json files")
    score_p.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    score_p.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    score_p.add_argument("--schema", default=str(DEFAULT_SCHEMA))

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "run":
        return command_run(args)
    if args.command == "score":
        return command_score(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
