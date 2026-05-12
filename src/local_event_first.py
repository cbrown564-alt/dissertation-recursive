#!/usr/bin/env python3
"""Archived local event-first extraction investigation (EL0 / EL1 / EL2).

This file is retained for historical run reproduction. New maintained local
candidate work should use the H6fs evidence-resolver path documented in
``docs/56_archival_entrypoints.md``.

EL0 -- Re-diagnosis latency check: run H0 (full canonical) and EL_micro on 2 dev docs to
       determine whether the original L1 abandonment was the extended-thinking bug or a
       genuine incapability.
EL1 -- Development pilot: 4 harnesses x N models x 10 dev docs with scoring.
EL2 -- Validation scale: promoted conditions x 40 val docs with full corrected scorer.

Harness IDs defined here:
  EL_micro_events   -- flat event list (type/value/quote/current), simplest possible
  EL_compact_events -- typed events with dose/unit/frequency/modality fields
  EL_E1E2_full      -- full E1 event extraction + deterministic E2 aggregation (two passes)
  EL_E1E3_full      -- full E1 + E3 constrained LLM aggregation (three passes, expensive)
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from direct_baselines import load_split_ids, parse_json_response, write_json, write_text
from evaluate import flatten_summary, load_gold, score_document
from event_first import aggregate_events, build_e1_prompt
from intake import DEFAULT_EXECT_ROOT, DEFAULT_SPLITS, preprocess_document
from model_expansion import (
    BENCHMARK_EPILEPSY_LABELS,
    BENCHMARK_SEIZURE_LABELS,
    mean_present,
    projected_canonical,
    to_float,
    write_csv,
)
from model_providers import ModelRequest, adapter_for, write_response_log
from model_registry import DEFAULT_REGISTRY, load_model_specs
from normalization import canonical_medication_name, canonical_seizure_type
from validate_extraction import DEFAULT_SCHEMA

DEFAULT_MARKUP_ROOT = Path("data/ExECT 2 (2025)/MarkupOutput_200_SyntheticEpilepsyLetters")
ARCHIVAL_STATUS = "archived_phase_runner"
MAINTAINED_ENTRYPOINT = "scripts/run_evidence_resolver_scored_batch.py"
DEFAULT_EL_OUTPUT_ROOT = Path("runs/local_event_first")

EL_MICRO = "EL_micro_events"
EL_COMPACT = "EL_compact_events"
EL_E1E2 = "EL_E1E2_full"
EL_E1E3 = "EL_E1E3_full"

EL0_HARNESSES = ["H0_strict_canonical", EL_MICRO]
EL1_HARNESSES = [EL_MICRO, EL_COMPACT, EL_E1E2]
EL2_HARNESSES = EL1_HARNESSES  # updated after EL1 promotion decision

EL0_MODELS = ["qwen_9b_local", "qwen_35b_local"]
EL1_MODELS = ["qwen_4b_local", "qwen_9b_local", "gemma_4b_local", "qwen_35b_local", "qwen_27b_local"]


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _benchmark_label_block() -> str:
    return "\n".join([
        "Allowed seizure_type values (use exactly as written):",
        *[f"- {lbl}" for lbl in BENCHMARK_SEIZURE_LABELS],
        "",
        "Allowed diagnosis values (use exactly as written):",
        *[f"- {lbl}" for lbl in BENCHMARK_EPILEPSY_LABELS],
    ])


def build_el_micro_prompt(document: dict[str, Any]) -> str:
    return "\n\n".join([
        "Extract clinical events from this epilepsy clinic letter.",
        (
            "Return a JSON array only. Each element must have exactly these fields:\n"
            '{"type":"medication|seizure_type|diagnosis","value":"...","quote":"exact phrase from letter","current":true}'
        ),
        (
            "Include:\n"
            "- type \"medication\": current anti-seizure medication names. Use generic drug names.\n"
            "  Set current=true if the patient is currently taking the medication.\n"
            "- type \"seizure_type\": current seizure types using only the allowed labels.\n"
            "  Set current=true for seizure types the patient currently has.\n"
            "  Set current=false for historical seizure types that are no longer occurring.\n"
            "- type \"diagnosis\": the epilepsy diagnosis/type using only the allowed labels."
        ),
        _benchmark_label_block(),
        (
            "Important:\n"
            "- Use \"unknown seizure type\" when seizures are occurring but the specific type is "
            "not described or unclear.\n"
            "- Add one event {\"type\":\"seizure_type\",\"value\":\"seizure free\",\"quote\":\"...\","
            "\"current\":true} when the patient is currently seizure-free.\n"
            "- Copy quotes exactly from the source letter. Do not paraphrase.\n"
            "- If a quote contains double-quote characters, replace them with single quotes to keep the JSON valid.\n"
            "- Return a JSON array directly. Do not wrap in an object or add keys."
        ),
        "## Source Letter",
        document["text"],
    ])


def build_el_compact_prompt(document: dict[str, Any]) -> str:
    med_fmt = (
        '{"type":"medication","name":"generic name","dose":null,"unit":null,'
        '"frequency":null,"quote":"exact phrase","current":true}'
    )
    sz_fmt = '{"type":"seizure_type","value":"allowed label","quote":"exact phrase","current":true}'
    freq_fmt = '{"type":"seizure_frequency","value":"N per period or seizure free for N month","quote":"exact phrase"}'
    inv_fmt = '{"type":"investigation","modality":"EEG","result":"normal","quote":"exact phrase"}'
    dx_fmt = '{"type":"diagnosis","value":"allowed label","quote":"exact phrase"}'

    return "\n\n".join([
        "Extract clinical events from this epilepsy clinic letter as a JSON array.",
        "Each event uses a type-specific format. Include a quote for every event.",
        "\n".join([
            "Medication event:    " + med_fmt,
            "Seizure type event:  " + sz_fmt,
            "Frequency event:     " + freq_fmt,
            "Investigation event: " + inv_fmt,
            "Diagnosis event:     " + dx_fmt,
        ]),
        _benchmark_label_block(),
        (
            "Rules:\n"
            "- medication: current=true for active ASMs; current=false for stopped/historical.\n"
            "  dose is a number only (e.g. \"500\", not \"500mg\"); unit is \"mg\", \"mcg\", \"g\", \"ml\", or null;\n"
            "  frequency is \"once daily\", \"twice daily\", \"three times daily\", \"nocte\", \"as required\", or null.\n"
            "- seizure_type: current=true for current types only. Use \"unknown seizure type\" if type unclear;\n"
            "  use \"seizure free\" if currently seizure-free. current=false for historical types.\n"
            "- investigation: result must be \"normal\" or \"abnormal\" only -- do not copy the raw EEG/MRI description.\n"
            "- Return a JSON array directly. Do not wrap in an object."
        ),
        "## Source Letter",
        document["text"],
    ])


# ---------------------------------------------------------------------------
# Aggregators: event list -> H6-style payload dict for projected_canonical
# ---------------------------------------------------------------------------

def aggregate_micro_events(events: list[Any]) -> dict[str, Any]:
    """Aggregate EL_micro event array into an H6-style payload dict."""
    if not isinstance(events, list):
        return {"medication_names": [], "seizure_types": [], "epilepsy_diagnosis_type": None}

    medication_names: list[str] = []
    seen_meds: set[str] = set()
    seizure_types: list[str] = []
    seen_sz: set[str] = set()
    epilepsy_diagnosis_type: str | None = None

    for ev in events:
        if not isinstance(ev, dict):
            continue
        t = str(ev.get("type") or "")
        value = str(ev.get("value") or "").strip()
        current = ev.get("current", True)

        if t == "medication" and current and value:
            norm = canonical_medication_name(value) or value
            if norm not in seen_meds:
                medication_names.append(norm)
                seen_meds.add(norm)

        elif t == "seizure_type" and current and value:
            mapped = canonical_seizure_type(value) or value
            if mapped not in seen_sz:
                seizure_types.append(mapped)
                seen_sz.add(mapped)

        elif t == "diagnosis" and value and epilepsy_diagnosis_type is None:
            epilepsy_diagnosis_type = value

    return {
        "medication_names": medication_names,
        "seizure_types": seizure_types,
        "epilepsy_diagnosis_type": epilepsy_diagnosis_type,
    }


def aggregate_compact_events(events: list[Any]) -> dict[str, Any]:
    """Aggregate EL_compact event array into a payload dict for projected_canonical.

    Passes structured medication objects (name/dose/unit/frequency) so that
    projected_canonical can score full medication tuple F1 as well as name-only.
    """
    if not isinstance(events, list):
        return {"medications": [], "seizure_types": [], "epilepsy_diagnosis_type": None}

    medications: list[dict[str, Any]] = []
    seen_meds: set[str] = set()
    seizure_types: list[str] = []
    seen_sz: set[str] = set()
    seizure_frequency: str | None = None
    epilepsy_diagnosis_type: str | None = None
    eeg: str | None = None
    mri: str | None = None

    for ev in events:
        if not isinstance(ev, dict):
            continue
        t = str(ev.get("type") or "")

        if t == "medication" and ev.get("current", True):
            name_raw = str(ev.get("name") or "").strip()
            if name_raw:
                norm_name = canonical_medication_name(name_raw) or name_raw
                if norm_name not in seen_meds:
                    medications.append({
                        "name": norm_name,
                        "dose": str(ev["dose"]) if ev.get("dose") is not None else None,
                        "unit": str(ev.get("unit") or "") or None,
                        "frequency": str(ev.get("frequency") or "") or None,
                    })
                    seen_meds.add(norm_name)

        elif t == "seizure_type" and ev.get("current", True):
            val = str(ev.get("value") or "").strip()
            if val:
                mapped = canonical_seizure_type(val) or val
                if mapped not in seen_sz:
                    seizure_types.append(mapped)
                    seen_sz.add(mapped)

        elif t == "seizure_frequency" and not seizure_frequency:
            seizure_frequency = str(ev.get("value") or "").strip() or None

        elif t == "investigation":
            modality = str(ev.get("modality") or "").upper()
            result = str(ev.get("result") or "").lower()
            if modality == "EEG" and eeg is None:
                eeg = result
            elif modality == "MRI" and mri is None:
                mri = result

        elif t == "diagnosis" and epilepsy_diagnosis_type is None:
            val = str(ev.get("value") or "").strip()
            if val:
                epilepsy_diagnosis_type = val

    return {
        "medications": medications,
        "medication_names": [m["name"] for m in medications],
        "seizure_types": seizure_types,
        "seizure_frequency": seizure_frequency,
        "epilepsy_diagnosis_type": epilepsy_diagnosis_type,
        "eeg": eeg,
        "mri": mri,
        "investigations": {"eeg": eeg, "mri": mri},
    }


def e2_fields_to_h6(fields: dict[str, Any]) -> dict[str, Any]:
    """Convert aggregate_events() fields dict to H6-style payload for projected_canonical."""
    med_names = [
        m.get("name") for m in fields.get("current_anti_seizure_medications", [])
        if isinstance(m, dict) and m.get("name")
    ]
    sz_types = [
        s.get("value") for s in fields.get("seizure_types", [])
        if isinstance(s, dict) and s.get("value")
    ]
    dx_field = fields.get("epilepsy_diagnosis") or {}
    dx = dx_field.get("value") if isinstance(dx_field, dict) else None
    freq_field = fields.get("current_seizure_frequency") or {}
    freq = freq_field.get("value") if isinstance(freq_field, dict) else None
    eeg_field = fields.get("eeg") or {}
    mri_field = fields.get("mri") or {}
    eeg = eeg_field.get("result") if isinstance(eeg_field, dict) else None
    mri = mri_field.get("result") if isinstance(mri_field, dict) else None
    return {
        "medication_names": [n for n in med_names if n],
        "seizure_types": [s for s in sz_types if s],
        "epilepsy_diagnosis_type": dx,
        "current_seizure_frequency": freq,
        "eeg": eeg,
        "mri": mri,
        "investigations": {"eeg": eeg, "mri": mri},
    }


# ---------------------------------------------------------------------------
# Run functions
# ---------------------------------------------------------------------------

def _make_request(
    prompt: str,
    spec: Any,
    harness_id: str,
    document_id: str,
    temperature: float,
    max_output_tokens: int,
    pass_tag: str | None = None,
) -> ModelRequest:
    meta: dict[str, Any] = {"document_id": document_id, "stage": "local_event_first"}
    if pass_tag:
        meta["pass"] = pass_tag
    return ModelRequest(
        prompt=prompt,
        model=spec,
        harness_id=harness_id,
        temperature=temperature,
        max_output_tokens=max_output_tokens or spec.max_output_tokens,
        metadata=meta,
    )


def _diagnostic_row(
    spec: Any,
    harness_id: str,
    document_id: str,
    responses: list[Any],
    parse_ok: bool,
    parse_error: str | None,
    e1_event_count: int | None,
) -> dict[str, Any]:
    total_latency = sum(r.latency_ms for r in responses)
    total_input = sum(r.token_usage.input_tokens or 0 for r in responses)
    total_output = sum(r.token_usage.output_tokens or 0 for r in responses)
    error = next((r.error for r in responses if r.error), None)
    return {
        "model_label": spec.label,
        "provider_model_id": spec.provider_model_id,
        "harness_id": harness_id,
        "document_id": document_id,
        "status": "error" if error else "success",
        "error": error,
        "parse_success": parse_ok,
        "parse_error": parse_error,
        "e1_event_count": e1_event_count,
        "num_calls": len(responses),
        "latency_ms": round(total_latency, 1),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "estimated_cost": 0.0,
    }


def _parse_event_list(text: str) -> tuple[list[Any] | None, str | None]:
    """Parse a JSON array from model output. Returns (events, error).

    parse_json_response uses extract_json_object which only looks for {} delimiters
    and cannot handle top-level arrays. This function extracts [...] directly.
    """
    import re as _re

    if not text or not text.strip():
        return None, "empty response"

    # Strip code fences
    stripped = text.strip()
    m = _re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=_re.DOTALL | _re.IGNORECASE)
    if m:
        stripped = m.group(1).strip()

    # Primary path: extract [...] array
    arr_start = stripped.find("[")
    arr_end = stripped.rfind("]")
    if arr_start != -1 and arr_end > arr_start:
        candidate = stripped[arr_start : arr_end + 1]
        try:
            data = json.loads(candidate, strict=False)
            if isinstance(data, list):
                return data, None
        except json.JSONDecodeError:
            pass
        # YAML fallback (more lenient about some characters)
        try:
            import yaml as _yaml
            data = _yaml.safe_load(candidate)
            if isinstance(data, list):
                return data, None
        except Exception:
            pass

    # Fallback: try full text as an object that wraps the list
    try:
        data = json.loads(stripped, strict=False)
        if isinstance(data, list):
            return data, None
        if isinstance(data, dict):
            for key in ("events", "event_list", "items", "results"):
                if isinstance(data.get(key), list):
                    return data[key], None
    except json.JSONDecodeError:
        pass

    return None, "no valid JSON array found in response"


def run_el_single(
    model_label: str,
    harness_id: str,
    document_id: str,
    output_dir: Path,
    registry: Path,
    exect_root: Path,
    temperature: float,
    max_output_tokens: int,
    ollama_base_url: str,
) -> dict[str, Any]:
    """Run one condition for EL_micro or EL_compact (single-pass)."""
    os.environ.setdefault("OLLAMA_BASE_URL", ollama_base_url)
    specs = load_model_specs(registry)
    spec = specs[model_label]
    document = preprocess_document(document_id, exect_root)
    adapter = adapter_for("ollama")

    run_root = output_dir / "calls" / model_label / harness_id / document_id
    run_root.mkdir(parents=True, exist_ok=True)

    if harness_id == EL_MICRO:
        prompt = build_el_micro_prompt(document)
    elif harness_id == EL_COMPACT:
        prompt = build_el_compact_prompt(document)
    else:
        raise ValueError(f"unsupported single-pass harness: {harness_id}")

    write_text(run_root / "prompt.txt", prompt)
    request = _make_request(prompt, spec, harness_id, document_id, temperature, max_output_tokens)
    response = adapter.call(request)
    write_text(run_root / "raw_response.txt", response.text)
    write_response_log(response, run_root / "provider_response.json")

    events, parse_error = _parse_event_list(response.text)
    parse_ok = events is not None and not response.error

    if events is not None:
        if harness_id == EL_MICRO:
            payload = aggregate_micro_events(events)
        else:
            payload = aggregate_compact_events(events)
        write_json(run_root / "events.json", events)
        write_json(run_root / "h6_payload.json", payload)
    else:
        payload = None

    row = _diagnostic_row(spec, harness_id, document_id, [response], parse_ok, parse_error, len(events) if events else None)
    row["h6_payload_path"] = str(run_root / "h6_payload.json") if payload else None
    return row


def run_el_e1e2(
    model_label: str,
    document_id: str,
    output_dir: Path,
    registry: Path,
    exect_root: Path,
    temperature: float,
    max_output_tokens: int,
    ollama_base_url: str,
) -> dict[str, Any]:
    """Run EL_E1E2: E1 event extraction (local model) + deterministic E2 aggregation."""
    os.environ.setdefault("OLLAMA_BASE_URL", ollama_base_url)
    specs = load_model_specs(registry)
    spec = specs[model_label]
    document = preprocess_document(document_id, exect_root)
    adapter = adapter_for("ollama")

    run_root = output_dir / "calls" / model_label / EL_E1E2 / document_id
    run_root.mkdir(parents=True, exist_ok=True)

    # Pass 1: E1 event extraction
    e1_prompt = build_e1_prompt(document)
    write_text(run_root / "e1_prompt.txt", e1_prompt)
    e1_request = _make_request(e1_prompt, spec, EL_E1E2, document_id, temperature, max_output_tokens, pass_tag="e1")
    e1_response = adapter.call(e1_request)
    write_text(run_root / "e1_raw_response.txt", e1_response.text)
    write_response_log(e1_response, run_root / "e1_provider_response.json")

    e1_parse = parse_json_response(e1_response.text)
    e1_data = e1_parse.data
    events: list[dict[str, Any]] = []
    parse_ok = False
    parse_error = e1_parse.error

    if isinstance(e1_data, dict) and isinstance(e1_data.get("events"), list):
        events = e1_data["events"]
        parse_ok = not e1_response.error
    elif isinstance(e1_data, list):
        events = e1_data
        parse_ok = not e1_response.error
    else:
        parse_error = parse_error or "e1_output_not_object_with_events_array"

    e1_event_count = len(events)
    if events:
        write_json(run_root / "e1_events.json", {"document_id": document_id, "events": events})

    # Pass 2: deterministic E2 aggregation
    e2_canonical: dict[str, Any] | None = None
    h6_payload: dict[str, Any] | None = None
    if events:
        try:
            e2_canonical, agg_log = aggregate_events(document_id, events)
            write_json(run_root / "e2_canonical.json", e2_canonical)
            write_json(run_root / "e2_aggregation_log.json", agg_log)
            h6_payload = e2_fields_to_h6(e2_canonical.get("fields", {}))
            write_json(run_root / "h6_payload.json", h6_payload)
        except Exception as exc:
            parse_error = (parse_error or "") + f"; e2_aggregation_error: {exc}"

    row = _diagnostic_row(spec, EL_E1E2, document_id, [e1_response], parse_ok, parse_error, e1_event_count)
    row["h6_payload_path"] = str(run_root / "h6_payload.json") if h6_payload else None
    row["e2_canonical_path"] = str(run_root / "e2_canonical.json") if e2_canonical else None
    return row


def run_el_one(
    model_label: str,
    harness_id: str,
    document_id: str,
    output_dir: Path,
    registry: Path,
    exect_root: Path,
    temperature: float,
    max_output_tokens: int,
    ollama_base_url: str,
) -> dict[str, Any]:
    """Dispatch to the correct run function for the harness."""
    if harness_id in (EL_MICRO, EL_COMPACT):
        return run_el_single(
            model_label, harness_id, document_id, output_dir, registry,
            exect_root, temperature, max_output_tokens, ollama_base_url,
        )
    if harness_id == EL_E1E2:
        return run_el_e1e2(
            model_label, document_id, output_dir, registry,
            exect_root, temperature, max_output_tokens, ollama_base_url,
        )
    raise ValueError(f"unsupported event-first harness: {harness_id}")


# ---------------------------------------------------------------------------
# H0 re-diagnosis run (EL0 only)
# ---------------------------------------------------------------------------

def run_h0_rediagnosis(
    model_label: str,
    document_id: str,
    output_dir: Path,
    registry: Path,
    exect_root: Path,
    temperature: float,
    max_output_tokens: int,
    ollama_base_url: str,
    schema_path: Path,
) -> dict[str, Any]:
    """Run H0 (full canonical schema) purely as a latency/termination check."""
    from direct_baselines import build_prompt as build_direct_prompt
    os.environ.setdefault("OLLAMA_BASE_URL", ollama_base_url)
    specs = load_model_specs(registry)
    spec = specs[model_label]
    document = preprocess_document(document_id, exect_root)
    adapter = adapter_for("ollama")

    run_root = output_dir / "calls" / model_label / "H0_strict_canonical" / document_id
    run_root.mkdir(parents=True, exist_ok=True)

    prompt = build_direct_prompt("S2", document, schema_path)
    write_text(run_root / "prompt.txt", prompt)
    request = _make_request(prompt, spec, "H0_strict_canonical", document_id, temperature, max_output_tokens)

    started = time.perf_counter()
    response = adapter.call(request)
    elapsed_s = time.perf_counter() - started

    write_text(run_root / "raw_response.txt", response.text)
    write_response_log(response, run_root / "provider_response.json")

    parsed = parse_json_response(response.text)
    return {
        "model_label": model_label,
        "harness_id": "H0_strict_canonical",
        "document_id": document_id,
        "status": "error" if response.error else "success",
        "error": response.error,
        "parse_success": parsed.parse_success,
        "latency_ms": round(response.latency_ms, 1),
        "latency_s": round(elapsed_s, 1),
        "total_output_tokens": response.token_usage.output_tokens or 0,
        "total_input_tokens": response.token_usage.input_tokens or 0,
        "prompt_len_chars": len(prompt),
        "output_len_chars": len(response.text),
        "terminated_cleanly": not response.error and len(response.text) > 10,
        "note": "EL0_rediagnosis",
    }


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_el_rows(
    rows: list[dict[str, Any]],
    output_dir: Path,
    exect_root: Path,
    markup_root: Path,
    schema_path: Path,
    registry: Path,
) -> dict[tuple[str, str], dict[str, Any]]:
    """Score event-first rows by loading h6_payload and running projected_canonical -> score_document."""
    gold = load_gold(markup_root, exect_root)
    specs = load_model_specs(registry)

    by_condition: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (row["model_label"], row["harness_id"])
        by_condition.setdefault(key, []).append(row)

    scores: dict[tuple[str, str], dict[str, Any]] = {}
    for (model_label, harness_id), condition_rows in by_condition.items():
        doc_scores: list[dict[str, Any]] = []
        for row in condition_rows:
            document_id = row["document_id"]
            if document_id not in gold:
                continue
            payload_path = row.get("h6_payload_path")
            if not payload_path or not Path(payload_path).exists():
                continue
            try:
                payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue

            document = preprocess_document(document_id, exect_root)
            row_str = {k: "" if v is None else str(v) for k, v in row.items()}
            projected = projected_canonical(
                document_id, harness_id, model_label, payload, row_str, document,
                require_present_evidence=False,
            )
            proj_path = (output_dir / "calls" / model_label / harness_id / document_id / "canonical_projection.json")
            write_json(proj_path, projected)
            doc_score = score_document(projected, document["text"], gold[document_id], schema_path)
            doc_scores.append(doc_score)

        if doc_scores:
            label = f"{model_label}:{harness_id}"
            scores[(model_label, harness_id)] = flatten_summary(label, doc_scores)

    return scores


def _summarize_condition(
    model_label: str,
    harness_id: str,
    rows: list[dict[str, Any]],
    scored: dict[str, Any] | None,
) -> dict[str, Any]:
    total = len(rows)
    success = sum(1 for r in rows if r.get("status") == "success")
    parse_ok = sum(1 for r in rows if str(r.get("parse_success", "")).lower() in {"true", "1", "yes"})
    latencies = [to_float(r.get("latency_ms")) for r in rows]
    evt_counts = [to_float(r.get("e1_event_count")) for r in rows if r.get("e1_event_count") is not None]

    summary: dict[str, Any] = {
        "model_label": model_label,
        "harness_id": harness_id,
        "documents": total,
        "call_success_rate": success / total if total else 0.0,
        "parse_success_rate": parse_ok / total if total else 0.0,
        "mean_latency_ms": mean_present(latencies),
        "mean_latency_s": round((mean_present(latencies) or 0) / 1000, 1),
        "mean_event_count": mean_present(evt_counts),
    }

    if scored:
        summary.update({
            "medication_name_f1": scored.get("medication_name_f1"),
            "seizure_type_f1_collapsed": scored.get("seizure_type_f1_collapsed"),
            "epilepsy_diagnosis_accuracy": scored.get("epilepsy_diagnosis_accuracy"),
            "medication_full_f1": scored.get("medication_full_f1"),
            "seizure_type_f1": scored.get("seizure_type_f1"),
            "quote_presence_rate": scored.get("quote_presence_rate"),
            "scoring_status": "scored",
        })
    else:
        summary["scoring_status"] = "parse_only"

    return summary


# ---------------------------------------------------------------------------
# Stage commands
# ---------------------------------------------------------------------------

def command_el0(args: argparse.Namespace) -> int:
    """EL0: latency re-diagnosis check on 2 dev docs — H0 and EL_micro."""
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    document_ids = load_split_ids(Path(args.splits), "development", args.limit)
    models = args.models or EL0_MODELS
    specs = load_model_specs(Path(args.registry))
    missing = [m for m in models if m not in specs]
    if missing:
        print(f"ERROR: unknown model labels: {missing}")
        return 1

    rows: list[dict[str, Any]] = []

    for model_label in models:
        for document_id in document_ids:
            print(f"EL0 H0_rediagnosis: {model_label} {document_id}", flush=True)
            row = run_h0_rediagnosis(
                model_label, document_id, output_dir, Path(args.registry),
                Path(args.exect_root), args.temperature, args.max_output_tokens,
                args.ollama_base_url, Path(args.schema),
            )
            rows.append(row)
            print(f"  -> {row['status']} latency={row['latency_s']}s output_tokens={row['total_output_tokens']} parse={row['parse_success']}", flush=True)

        for document_id in document_ids:
            print(f"EL0 EL_micro: {model_label} {document_id}", flush=True)
            row = run_el_single(
                model_label, EL_MICRO, document_id, output_dir, Path(args.registry),
                Path(args.exect_root), args.temperature, args.max_output_tokens,
                args.ollama_base_url,
            )
            rows.append(row)
            print(f"  -> {row['status']} latency_ms={row['latency_ms']} parse={row['parse_success']} events={row.get('e1_event_count')}", flush=True)

    write_csv(output_dir / "el0_latency_report.csv", rows)

    # Print summary
    print("\n=== EL0 SUMMARY ===")
    for row in rows:
        status_str = "OK" if row.get("terminated_cleanly", row.get("parse_success")) else "FAIL"
        print(
            f"{status_str:4s}  {row['model_label']:20s}  {row['harness_id']:30s}  "
            f"latency={row.get('latency_s', round((row.get('latency_ms') or 0) / 1000, 1))}s  "
            f"out_tokens={row.get('total_output_tokens', '?')}"
        )

    print(f"\nReport written to {output_dir / 'el0_latency_report.csv'}")

    # Decision note
    h0_rows = [r for r in rows if r["harness_id"] == "H0_strict_canonical"]
    timeouts = [r for r in h0_rows if not r.get("terminated_cleanly") or (r.get("latency_ms") or 0) > 300_000]
    if timeouts:
        print(f"\nDECISION: {len(timeouts)} H0 condition(s) timed out or failed to terminate. "
              "L1 abandonment may still be partially valid for those models at H0 scale. "
              "Proceed with EL_micro/EL_compact harnesses for affected models.")
    else:
        max_h0_latency = max((r.get("latency_ms") or 0) for r in h0_rows) / 1000
        print(f"\nDECISION: H0 terminated cleanly on all models (max latency {max_h0_latency:.1f}s). "
              "L1 abandonment was likely the extended-thinking bug. Proceed to EL1.")
    return 0


def _run_el_stage(
    stage_name: str,
    models: list[str],
    harnesses: list[str],
    document_ids: list[str],
    output_dir: Path,
    registry: Path,
    exect_root: Path,
    markup_root: Path,
    schema_path: Path,
    temperature: float,
    max_output_tokens: int,
    ollama_base_url: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    call_rows: list[dict[str, Any]] = []

    for model_label in models:
        for harness_id in harnesses:
            for document_id in document_ids:
                print(f"{stage_name}: {model_label} {harness_id} {document_id}", flush=True)
                row = run_el_one(
                    model_label, harness_id, document_id, output_dir,
                    registry, exect_root, temperature, max_output_tokens, ollama_base_url,
                )
                call_rows.append(row)
                print(f"  -> {row['status']} latency_ms={row['latency_ms']} parse={row['parse_success']}", flush=True)

    write_csv(output_dir / "call_report.csv", call_rows)

    scores = score_el_rows(call_rows, output_dir, exect_root, markup_root, schema_path, registry)

    by_condition: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in call_rows:
        by_condition.setdefault((row["model_label"], row["harness_id"]), []).append(row)

    summaries = [
        _summarize_condition(model_label, harness_id, rows, scores.get((model_label, harness_id)))
        for (model_label, harness_id), rows in sorted(by_condition.items())
    ]
    write_csv(output_dir / "comparison_table.csv", summaries)
    return call_rows, summaries


def command_el1(args: argparse.Namespace) -> int:
    """EL1: development pilot — all models x all harnesses x 10 dev docs."""
    output_dir = Path(args.output_dir)
    specs = load_model_specs(Path(args.registry))
    models = args.models or EL1_MODELS
    missing = [m for m in models if m not in specs]
    if missing:
        print(f"ERROR: unknown model labels: {missing}")
        return 1

    harnesses = args.harnesses or EL1_HARNESSES
    document_ids = load_split_ids(Path(args.splits), "development", args.limit)

    _, summaries = _run_el_stage(
        "EL1", models, harnesses, document_ids, output_dir,
        Path(args.registry), Path(args.exect_root), Path(args.markup_root),
        Path(args.schema), args.temperature, args.max_output_tokens, args.ollama_base_url,
    )

    print("\n=== EL1 COMPARISON TABLE ===")
    print(f"{'model':22s} {'harness':20s} {'parse':6s} {'med_f1':7s} {'sz_f1c':7s} {'dx_acc':7s} {'lat_s':6s}")
    print("-" * 80)
    baselines = {"qwen_9b_local": 0.839, "gemma_4b_local": 0.849, "qwen_35b_local": 0.852, "qwen_27b_local": 0.885, "qwen_4b_local": 0.814}
    for row in summaries:
        med = row.get("medication_name_f1")
        sz = row.get("seizure_type_f1_collapsed")
        dx = row.get("epilepsy_diagnosis_accuracy")
        lat = row.get("mean_latency_s") or 0
        parse_r = row.get("parse_success_rate") or 0
        h6_med = baselines.get(row["model_label"])
        delta = f"(+{med - h6_med:.3f})" if med and h6_med else ""
        print(
            f"{row['model_label']:22s} {row['harness_id']:20s} "
            f"{parse_r:.2f}  "
            f"{med or 0:.3f}{delta:10s}  "
            f"{sz or 0:.3f}  {dx or 0:.3f}  {lat:.1f}s"
        )

    print(f"\nComparison table: {output_dir / 'comparison_table.csv'}")
    return 0


def command_el2(args: argparse.Namespace) -> int:
    """EL2: validation scale — promoted conditions x 40 val docs."""
    output_dir = Path(args.output_dir)
    specs = load_model_specs(Path(args.registry))
    models = args.models
    if not models:
        print("ERROR: --models required for EL2 (specify promoted models from EL1 decision)")
        return 1
    missing = [m for m in models if m not in specs]
    if missing:
        print(f"ERROR: unknown model labels: {missing}")
        return 1

    harnesses = args.harnesses or EL1_HARNESSES
    document_ids = load_split_ids(Path(args.splits), "validation", args.limit)

    _, summaries = _run_el_stage(
        "EL2", models, harnesses, document_ids, output_dir,
        Path(args.registry), Path(args.exect_root), Path(args.markup_root),
        Path(args.schema), args.temperature, args.max_output_tokens, args.ollama_base_url,
    )

    print("\n=== EL2 VALIDATION SUMMARY ===")
    h6_baselines = {
        "qwen_9b_local": {"med": 0.839, "sz": 0.602, "dx": 0.825},
        "gemma_4b_local": {"med": 0.849, "sz": 0.593, "dx": 0.825},
        "qwen_35b_local": {"med": 0.852, "sz": 0.593, "dx": 0.800},
        "qwen_27b_local": {"med": 0.885, "sz": 0.578, "dx": 0.800},
    }
    print(f"{'model':22s} {'harness':20s} {'med_f1':7s} {'sz_f1c':7s} {'dx_acc':7s} {'lat_s':6s} vs H6-best")
    print("-" * 90)
    for row in summaries:
        med = row.get("medication_name_f1") or 0
        sz = row.get("seizure_type_f1_collapsed") or 0
        dx = row.get("epilepsy_diagnosis_accuracy") or 0
        lat = row.get("mean_latency_s") or 0
        base = h6_baselines.get(row["model_label"], {})
        delta_med = f"{med - base.get('med', 0):+.3f}" if base else "n/a"
        delta_sz = f"{sz - base.get('sz', 0):+.3f}" if base else "n/a"
        print(
            f"{row['model_label']:22s} {row['harness_id']:20s} "
            f"{med:.3f}  {sz:.3f}  {dx:.3f}  {lat:.1f}s  "
            f"dMed={delta_med} dSz={delta_sz}"
        )

    print(f"\nFull table: {output_dir / 'comparison_table.csv'}")
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--splits", default=str(DEFAULT_SPLITS))
    parser.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    parser.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-output-tokens", type=int, default=2048)
    parser.add_argument("--ollama-base-url", default=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"))
    parser.add_argument("--models", nargs="+", default=None)
    parser.add_argument("--harnesses", nargs="+", default=None)
    parser.add_argument("--limit", type=int, default=None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    el0 = sub.add_parser("el0", help="EL0: latency re-diagnosis (2 dev docs)")
    _add_common_args(el0)
    el0.add_argument("--output-dir", default=str(DEFAULT_EL_OUTPUT_ROOT / "el0_rediagnosis"))
    el0.set_defaults(func=command_el0, limit=2)

    el1 = sub.add_parser("el1", help="EL1: development pilot (10 dev docs)")
    _add_common_args(el1)
    el1.add_argument("--output-dir", default=str(DEFAULT_EL_OUTPUT_ROOT / "el1_dev_pilot"))
    el1.set_defaults(func=command_el1, limit=10)

    el2 = sub.add_parser("el2", help="EL2: validation scale (40 val docs)")
    _add_common_args(el2)
    el2.add_argument("--output-dir", default=str(DEFAULT_EL_OUTPUT_ROOT / "el2_validation"))
    el2.set_defaults(func=command_el2, limit=None)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
