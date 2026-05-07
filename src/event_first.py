#!/usr/bin/env python3
"""Run Milestone 4 event-first extraction and aggregation pipelines."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import time
from pathlib import Path
from typing import Any

from direct_baselines import (
    ParseResult,
    append_jsonl,
    call_openai,
    compact_schema_text,
    empty_investigation,
    empty_scalar,
    load_split_ids,
    normalize_contract_aliases,
    parse_json_response,
    sentence_table,
    validate_and_score,
    write_json,
    write_text,
)
from intake import DEFAULT_EXECT_ROOT, DEFAULT_SPLITS, preprocess_document, read_text
from normalization import (
    canonical_diagnosis,
    canonical_investigation_result,
    canonical_medication_name,
    canonical_seizure_type,
    normalize_value,
)
from validate_extraction import (
    DEFAULT_SCHEMA,
    EVENT_CATEGORY,
    EVENT_STATUS,
    TEMPORALITY,
    ValidationError,
    check_quote_validity,
    validate_event,
)


PROMPT_DIR = Path("prompts/event_first")
DEFAULT_OUTPUT_DIR = Path("runs/event_first")
DEFAULT_RECOVERY_ORACLE_DIR = Path("runs/recovery/aggregation_oracle")
DEFAULT_MARKUP_ROOT = Path("data/ExECT 2 (2025)/MarkupOutput_200_SyntheticEpilepsyLetters")

E1_PIPELINE_ID = "E1_event_extraction"
E2_PIPELINE_ID = "E2_deterministic_event_aggregation"
E3_PIPELINE_ID = "E3_constrained_event_aggregation"


def build_e1_prompt(document: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            read_text(PROMPT_DIR / "e1_event_extraction.md"),
            "## Event Schema Notes",
            event_schema_notes(),
            "## Sentence List",
            sentence_table(document["sentences"]),
            "## Source Letter",
            document["text"],
        ]
    )


def build_e3_prompt(document_id: str, events: list[dict[str, Any]], schema_path: Path) -> str:
    return "\n\n".join(
        [
            read_text(PROMPT_DIR / "e3_constrained_aggregation.md"),
            "## Canonical JSON Schema",
            compact_schema_text(schema_path),
            "## Document ID",
            document_id,
            "## Event List",
            json.dumps(events, indent=2, ensure_ascii=False),
        ]
    )


def event_schema_notes() -> str:
    statuses = sorted(item for item in EVENT_STATUS if item is not None) + [None]
    return json.dumps(
        {
            "category": sorted(EVENT_CATEGORY),
            "temporality": sorted(TEMPORALITY),
            "status": statuses,
            "investigation_type": ["EEG", "MRI", None],
            "investigation_result": ["normal", "abnormal", "not_stated", "uncertain", None],
        },
        indent=2,
        ensure_ascii=False,
    )


def stub_e1_response(document_id: str, latency_ms: float) -> str:
    return json.dumps(
        {
            "document_id": document_id,
            "pipeline_id": E1_PIPELINE_ID,
            "events": [],
            "metadata": {
                "model": "stub",
                "format": "json",
                "latency_ms": latency_ms,
                "input_tokens": 0,
                "output_tokens": 0,
                "repair_attempted": False,
                "repair_succeeded": False,
            },
        },
        indent=2,
        ensure_ascii=False,
    )


def get_model_response(args: argparse.Namespace, prompt: str, document_id: str) -> tuple[str, float, str]:
    started = time.perf_counter()
    if args.provider == "stub":
        latency_ms = (time.perf_counter() - started) * 1000
        return stub_e1_response(document_id, latency_ms), latency_ms, "stub"
    if args.provider == "openai":
        response = call_openai(prompt, args.model)
        latency_ms = (time.perf_counter() - started) * 1000
        return response, latency_ms, args.model
    raise ValueError(f"unsupported provider: {args.provider}")


def normalize_event_payload(data: Any, document_id: str, model_name: str, latency_ms: float, parse: ParseResult) -> dict[str, Any]:
    if isinstance(data, list):
        data = {"document_id": document_id, "pipeline_id": E1_PIPELINE_ID, "events": data, "metadata": {}}
    data = normalize_contract_aliases(data, document_id, E1_PIPELINE_ID)
    if not isinstance(data, dict):
        raise ValidationError("E1 output must be an object or event array")
    data.setdefault("document_id", document_id)
    data.setdefault("pipeline_id", E1_PIPELINE_ID)
    data.setdefault("events", [])
    data.setdefault("metadata", {})
    data["metadata"].update(
        {
            "model": model_name,
            "format": "json",
            "latency_ms": latency_ms,
            "repair_attempted": parse.repair_attempted,
            "repair_succeeded": parse.repair_succeeded,
        }
    )
    for token_key in ["input_tokens", "output_tokens"]:
        if data["metadata"].get(token_key) is None:
            data["metadata"][token_key] = 0
    return data


def validate_event_payload(data: dict[str, Any], source_text: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "event_constraints_valid": False,
        "quote_validity": None,
        "validation_errors": [],
    }
    try:
        if not isinstance(data.get("events"), list):
            raise ValidationError("$.events must be an array")
        event_ids = set()
        for index, event in enumerate(data["events"]):
            validate_event(event, f"$.events[{index}]")
            if event["id"] in event_ids:
                raise ValidationError(f"duplicate event id: {event['id']}")
            event_ids.add(event["id"])
        result["event_constraints_valid"] = True
    except ValidationError as exc:
        result["validation_errors"].append(str(exc))

    quote_total, quote_failures = check_quote_validity({"events": data.get("events", [])}, source_text)
    result["quote_validity"] = {
        "quote_count": quote_total,
        "valid_quote_count": quote_total - len(quote_failures),
        "invalid_quote_count": len(quote_failures),
        "invalid_quote_paths": quote_failures,
        "pass": len(quote_failures) == 0,
    }
    return result


def field_from_event(event: dict[str, Any], value: Any | None = None, temporality: str | None = None) -> dict[str, Any]:
    return {
        "value": value if value is not None else event.get("value"),
        "missingness": "present",
        "temporality": temporality or event.get("temporality", "uncertain"),
        "evidence": [event["evidence"]],
        "evidence_event_ids": [event["id"]],
        "confidence": None,
    }


def medication_from_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": event.get("medication_name") or event.get("value"),
        "dose": event.get("dose"),
        "dose_unit": event.get("dose_unit"),
        "frequency": event.get("frequency"),
        "status": event.get("status") or "current",
        "missingness": "present",
        "temporality": event.get("temporality", "current"),
        "reason_stopped": event.get("reason_stopped"),
        "evidence": [event["evidence"]],
        "evidence_event_ids": [event["id"]],
        "confidence": None,
    }


def investigation_from_event(event: dict[str, Any]) -> dict[str, Any]:
    result = canonical_investigation_result(event.get("result") or event.get("value")) or "not_stated"
    if result not in {"normal", "abnormal", "not_stated", "uncertain", None}:
        result = "uncertain"
    return {
        "status": event.get("status") or "completed",
        "result": result,
        "missingness": "present",
        "temporality": event.get("temporality", "completed"),
        "evidence": [event["evidence"]],
        "evidence_event_ids": [event["id"]],
        "confidence": None,
    }


def empty_seizure_frequency() -> dict[str, Any]:
    field = empty_scalar()
    field["temporal_scope"] = None
    field["seizure_type"] = None
    return field


def no_support(log: dict[str, Any], path: str, reason: str) -> None:
    log["missingness_decisions"].append({"field": path, "decision": "not_stated", "reason": reason})
    log["final_fields_without_event_support"].append(path)


def event_position(event: dict[str, Any], fallback: int) -> int:
    evidence = event.get("evidence") if isinstance(event.get("evidence"), dict) else {}
    start = evidence.get("char_start")
    return start if isinstance(start, int) else fallback


def candidate_snapshot(event: dict[str, Any], field: str, rank: tuple[Any, ...], reason: str | None = None) -> dict[str, Any]:
    snapshot = {
        "field": field,
        "event_id": event.get("id"),
        "category": event.get("category"),
        "temporality": event.get("temporality"),
        "status": event.get("status"),
        "value": event.get("value"),
        "rank": list(rank),
    }
    if reason:
        snapshot["reason"] = reason
    return snapshot


def discard_candidate(log: dict[str, Any], event: dict[str, Any], field: str, rank: tuple[Any, ...], reason: str) -> None:
    event_id = event.get("id")
    if event_id:
        log["ignored_event_ids"].append(event_id)
    log["discarded_candidates"].append(candidate_snapshot(event, field, rank, reason))


def select_candidate(
    log: dict[str, Any],
    field: str,
    candidates: list[tuple[dict[str, Any], tuple[Any, ...], str]],
    missing_reason: str,
) -> dict[str, Any] | None:
    for event, rank, note in sorted(candidates, key=lambda item: item[1], reverse=True):
        log["ranked_candidates"].append(candidate_snapshot(event, field, rank, note))
    selectable = [(event, rank, note) for event, rank, note in candidates if rank[0] > 0]
    if not selectable:
        no_support(log, field, missing_reason)
        for event, rank, note in candidates:
            discard_candidate(log, event, field, rank, note)
        return None
    selected, selected_rank, selected_note = max(selectable, key=lambda item: item[1])
    log["selected_event_ids"][field] = [selected["id"]]
    for event, rank, note in candidates:
        if event["id"] == selected["id"]:
            continue
        discard_candidate(log, event, field, rank, note)
        if rank[0] > 0:
            log["conflict_decisions"].append(
                {
                    "field": field,
                    "selected_event_id": selected["id"],
                    "discarded_event_id": event["id"],
                    "reason": f"ranked candidate selected over lower-ranked candidate: {note}",
                }
            )
    log["selection_decisions"].append(
        {
            "field": field,
            "selected_event_id": selected["id"],
            "rank": list(selected_rank),
            "reason": selected_note,
        }
    )
    return selected


def medication_rank(event: dict[str, Any], index: int) -> tuple[int, int, int, int]:
    temporality = event.get("temporality")
    status = event.get("status")
    current = temporality == "current" and status in {"current", "increased", "reduced"}
    has_components = int(bool(event.get("dose") or event.get("dose_unit") or event.get("frequency")))
    return (1 if current else 0, 1 if status == "current" else 0, has_components, event_position(event, index))


def medication_discard_reason(event: dict[str, Any]) -> str:
    temporality = event.get("temporality")
    status = event.get("status")
    if temporality == "historical" or status in {"previous", "stopped"}:
        return "non-current medication retained only in previous medication extension"
    if temporality == "planned" or status in {"planned", "declined"}:
        return "planned or declined medication is not a current ASM"
    if status != "current":
        return "medication status is not explicitly current"
    return "lower-ranked duplicate medication candidate"


def seizure_type_rank(event: dict[str, Any], index: int) -> tuple[int, int, int]:
    value = event.get("value")
    canonical = canonical_seizure_type(value)
    normalized = normalize_value(value)
    mapped = bool(canonical and canonical != normalized) or canonical in {
        "focal seizure",
        "focal aware seizure",
        "focal impaired awareness seizure",
        "focal to bilateral tonic clonic seizure",
        "generalized absence seizure",
        "generalized atonic seizure",
        "generalized myoclonic seizure",
        "generalized tonic clonic seizure",
        "unknown seizure type",
    }
    explicit = any(term in normalized for term in ["seizure", "absence", "tonic", "clonic", "focal", "partial", "myoclonic", "atonic", "gtc"])
    selectable = mapped or explicit
    return (1 if selectable else 0, 1 if mapped else 0, event_position(event, index))


def frequency_rank(event: dict[str, Any], index: int) -> tuple[int, int, int, int]:
    temporality = event.get("temporality")
    current = temporality == "current"
    non_historical = temporality not in {"historical", "family_history", "hypothetical", "planned"}
    has_linkage = int(bool(event.get("seizure_type")))
    return (1 if current or non_historical else 0, 1 if current else 0, has_linkage, event_position(event, index))


def investigation_rank(event: dict[str, Any], index: int) -> tuple[int, int, int, int]:
    status = event.get("status")
    result = canonical_investigation_result(event.get("result") or event.get("value"))
    completed_result = status == "completed" and result in {"normal", "abnormal", "uncertain"}
    definite_result = result in {"normal", "abnormal"}
    return (1 if completed_result else 0, 1 if definite_result else 0, 1 if status == "completed" else 0, event_position(event, index))


def diagnosis_rank(event: dict[str, Any], index: int) -> tuple[int, int, int]:
    temporality = event.get("temporality")
    value = canonical_diagnosis(event.get("value"))
    patient_level = temporality != "family_history"
    explicit = bool(value and "epilepsy" in value)
    return (1 if patient_level and explicit else 0, 1 if temporality == "current" else 0, event_position(event, index))


def aggregate_events(document_id: str, events: list[dict[str, Any]], model_name: str = "deterministic") -> tuple[dict[str, Any], dict[str, Any]]:
    log: dict[str, Any] = {
        "contract_version": "phase5_ranked_candidates_v1",
        "selected_event_ids": {},
        "ignored_event_ids": [],
        "ranked_candidates": [],
        "discarded_candidates": [],
        "selection_decisions": [],
        "conflict_decisions": [],
        "missingness_decisions": [],
        "final_fields_without_event_support": [],
        "extension_non_current_medications": [],
        "extension_investigation_statuses": [],
    }

    fields: dict[str, Any] = {
        "current_anti_seizure_medications": [],
        "previous_anti_seizure_medications": [],
        "current_seizure_frequency": empty_seizure_frequency(),
        "seizure_types": [],
        "eeg": empty_investigation(),
        "mri": empty_investigation(),
        "epilepsy_diagnosis": empty_scalar(),
    }

    medication_events = [event for event in events if event.get("category") == "medication"]
    medication_candidates_by_name: dict[str, list[tuple[dict[str, Any], tuple[Any, ...], str]]] = {}
    for index, event in enumerate(medication_events):
        rank = medication_rank(event, index)
        name = canonical_medication_name(event.get("medication_name") or event.get("value")) or f"__unnamed_{index}"
        reason = "current medication ranked above historical, planned, stopped, or declined medication"
        medication_candidates_by_name.setdefault(name, []).append((event, rank, reason))
        status = event.get("status")
        if status in {"previous", "stopped"} or event.get("temporality") == "historical":
            previous = medication_from_event(event)
            previous["status"] = status if status in {"previous", "stopped"} else "previous"
            previous["temporality"] = "historical"
            fields["previous_anti_seizure_medications"].append(previous)
            log["selected_event_ids"].setdefault("previous_anti_seizure_medications", []).append(event["id"])
            log["extension_non_current_medications"].append(event)

    selected_medication_ids: set[str] = set()
    for name, candidates in medication_candidates_by_name.items():
        selected = select_candidate(
            log,
            f"current_anti_seizure_medications[{name}]",
            [(event, rank, medication_discard_reason(event) if rank[0] == 0 else reason) for event, rank, reason in candidates],
            f"no current medication candidate for {name}",
        )
        if selected:
            fields["current_anti_seizure_medications"].append(medication_from_event(selected))
            log["selected_event_ids"].setdefault("current_anti_seizure_medications", []).append(selected["id"])
            selected_medication_ids.add(selected["id"])
    for event in medication_events:
        if event["id"] not in selected_medication_ids and event not in log["extension_non_current_medications"]:
            status = event.get("status")
            if status != "current" or event.get("temporality") != "current":
                log["extension_non_current_medications"].append(event)

    seizure_frequency_events = [event for event in events if event.get("category") == "seizure_frequency"]
    frequency_candidates = [
        (
            event,
            frequency_rank(event, index),
            "latest current seizure-frequency statement ranked above historical frequency",
        )
        for index, event in enumerate(seizure_frequency_events)
    ]
    selected_frequency = select_candidate(log, "current_seizure_frequency", frequency_candidates, "no current seizure-frequency event")
    if selected_frequency:
        frequency = field_from_event(selected_frequency, temporality=selected_frequency.get("temporality", "uncertain"))
        frequency["temporal_scope"] = selected_frequency.get("temporal_scope")
        frequency["seizure_type"] = selected_frequency.get("seizure_type")
        fields["current_seizure_frequency"] = frequency

    selected_seizure_type_values: set[str] = set()
    for index, event in enumerate(events):
        if event.get("category") == "seizure_type":
            rank = seizure_type_rank(event, index)
            canonical_value = canonical_seizure_type(event.get("value"))
            log["ranked_candidates"].append(
                candidate_snapshot(
                    event,
                    "seizure_types",
                    rank,
                    "explicit seizure-type label or mapped semiology preferred over unmapped descriptive semiology",
                )
            )
            if rank[0] <= 0:
                discard_candidate(log, event, "seizure_types", rank, "unmapped descriptive semiology is not promoted to seizure type")
                continue
            if canonical_value in selected_seizure_type_values:
                discard_candidate(log, event, "seizure_types", rank, "duplicate canonical seizure type")
                continue
            selected_seizure_type_values.add(canonical_value)
            selected = field_from_event(event)
            selected["value"] = canonical_value or event.get("value")
            fields["seizure_types"].append(selected)
            log["selected_event_ids"].setdefault("seizure_types", []).append(event["id"])

    investigation_events = [event for event in events if event.get("category") == "investigation"]
    for investigation_type, field_name in [("EEG", "eeg"), ("MRI", "mri")]:
        candidates = [event for event in investigation_events if event.get("investigation_type") == investigation_type]
        ranked = [
            (
                event,
                investigation_rank(event, index),
                f"completed {investigation_type} result ranked above requested or pending investigation",
            )
            for index, event in enumerate(candidates)
        ]
        selected = select_candidate(log, field_name, ranked, f"no completed {investigation_type} result event")
        if selected:
            fields[field_name] = investigation_from_event(selected)
        for event in candidates:
            if event.get("status") != "completed" or event.get("result") in {None, "not_stated"}:
                log["extension_investigation_statuses"].append(event)

    diagnosis_events = [event for event in events if event.get("category") == "diagnosis"]
    diagnosis_candidates = [
        (event, diagnosis_rank(event, index), "patient-level explicit diagnosis ranked by currentness and latest evidence")
        for index, event in enumerate(diagnosis_events)
    ]
    selected = select_candidate(log, "epilepsy_diagnosis", diagnosis_candidates, "no patient-level diagnosis event")
    if selected:
        fields["epilepsy_diagnosis"] = field_from_event(selected)

    log["ignored_event_ids"] = sorted(set(log["ignored_event_ids"]))

    canonical = {
        "document_id": document_id,
        "pipeline_id": E2_PIPELINE_ID,
        "fields": fields,
        "events": events,
        "metadata": {
            "model": model_name,
            "format": "json",
            "latency_ms": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "repair_attempted": False,
            "repair_succeeded": False,
            "aggregation": log,
        },
    }
    return canonical, log


def run_e1(args: argparse.Namespace, document: dict[str, Any], run_root: Path) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    prompt = build_e1_prompt(document)
    prompt_path = run_root / "e1_prompt.txt"
    raw_path = run_root / "e1_raw.json"
    events_path = run_root / "e1_events.json"
    write_text(prompt_path, prompt)

    if raw_path.exists() and not args.refresh:
        raw_response = read_text(raw_path)
        latency_ms = 0.0
        model_name = args.model if args.provider == "openai" else "stub"
    else:
        raw_response, latency_ms, model_name = get_model_response(args, prompt, document["document_id"])
        write_text(raw_path, raw_response)
    parse = parse_json_response(raw_response)

    payload = None
    scores = None
    if parse.data is not None:
        try:
            payload = normalize_event_payload(parse.data, document["document_id"], model_name, latency_ms, parse)
            write_json(events_path, payload)
            scores = validate_event_payload(payload, document["text"])
        except ValidationError as exc:
            scores = {"event_constraints_valid": False, "quote_validity": None, "validation_errors": [str(exc)]}

    record = {
        "document_id": document["document_id"],
        "pipeline": "E1",
        "pipeline_id": E1_PIPELINE_ID,
        "provider": args.provider,
        "model": model_name,
        "prompt_path": str(prompt_path),
        "raw_response_path": str(raw_path),
        "event_output_path": str(events_path) if payload is not None else None,
        "parse": {
            "parse_success": parse.parse_success,
            "repair_attempted": parse.repair_attempted,
            "repair_succeeded": parse.repair_succeeded,
            "error": parse.error,
        },
        "scores": scores,
    }
    return payload, record


def run_e2(args: argparse.Namespace, document: dict[str, Any], events: list[dict[str, Any]], run_root: Path) -> dict[str, Any]:
    canonical, log = aggregate_events(document["document_id"], events)
    canonical_path = run_root / "e2_canonical.json"
    log_path = run_root / "e2_aggregation_log.json"
    write_json(canonical_path, canonical)
    write_json(log_path, log)
    scores = validate_and_score(canonical, document["text"], Path(args.schema), require_present_evidence=True)
    return {
        "document_id": document["document_id"],
        "pipeline": "E2",
        "pipeline_id": E2_PIPELINE_ID,
        "provider": "deterministic",
        "model": "deterministic",
        "canonical_output_path": str(canonical_path),
        "aggregation_log_path": str(log_path),
        "scores": scores,
    }


def run_e3(args: argparse.Namespace, document: dict[str, Any], events: list[dict[str, Any]], run_root: Path) -> dict[str, Any]:
    prompt = build_e3_prompt(document["document_id"], events, Path(args.schema))
    prompt_path = run_root / "e3_prompt.txt"
    raw_path = run_root / "e3_raw.json"
    canonical_path = run_root / "e3_canonical.json"
    write_text(prompt_path, prompt)

    started = time.perf_counter()
    if raw_path.exists() and not args.refresh:
        raw_response = read_text(raw_path)
        latency_ms = 0.0
        model_name = args.model if args.provider == "openai" else "stub"
    elif args.provider == "stub":
        canonical, log = aggregate_events(document["document_id"], events, model_name="stub_constrained_fallback")
        canonical["pipeline_id"] = E3_PIPELINE_ID
        canonical["metadata"]["aggregation"] = log
        raw_response = json.dumps(canonical, indent=2, ensure_ascii=False)
        latency_ms = (time.perf_counter() - started) * 1000
        model_name = "stub"
    else:
        raw_response = call_openai(prompt, args.model)
        latency_ms = (time.perf_counter() - started) * 1000
        model_name = args.model
    write_text(raw_path, raw_response)

    parse = parse_json_response(raw_response)
    scores = None
    if parse.data is not None:
        parse.data = normalize_contract_aliases(parse.data, document["document_id"], E3_PIPELINE_ID)
        if isinstance(parse.data, dict):
            parse.data.setdefault("metadata", {})
            parse.data["metadata"].update(
                {
                    "model": model_name,
                    "format": "constrained_json",
                    "latency_ms": latency_ms,
                    "repair_attempted": parse.repair_attempted,
                    "repair_succeeded": parse.repair_succeeded,
                }
            )
            for token_key in ["input_tokens", "output_tokens"]:
                if parse.data["metadata"].get(token_key) is None:
                    parse.data["metadata"][token_key] = 0
        write_json(canonical_path, parse.data)
        scores = validate_and_score(parse.data, document["text"], Path(args.schema), require_present_evidence=True)

    return {
        "document_id": document["document_id"],
        "pipeline": "E3",
        "pipeline_id": E3_PIPELINE_ID,
        "provider": args.provider,
        "model": model_name,
        "prompt_path": str(prompt_path),
        "raw_response_path": str(raw_path),
        "canonical_output_path": str(canonical_path) if parse.data is not None else None,
        "parse": {
            "parse_success": parse.parse_success,
            "repair_attempted": parse.repair_attempted,
            "repair_succeeded": parse.repair_succeeded,
            "error": parse.error,
        },
        "scores": scores,
    }


def gold_evidence(span: Any, source_text: str) -> dict[str, Any]:
    quote = getattr(span, "value", "") or source_text[getattr(span, "start", 0) : getattr(span, "end", 0)]
    return {
        "quote": quote,
        "sentence_id": None,
        "char_start": getattr(span, "start", None),
        "char_end": getattr(span, "end", None),
    }


def first_span(spans: list[Any], index: int) -> Any | None:
    if not spans:
        return None
    return spans[index] if index < len(spans) else spans[-1]


def evidence_from_gold(document_gold: Any, group: str, index: int, source_text: str, fallback: str) -> dict[str, Any]:
    span = first_span(document_gold.spans_by_group.get(group, []), index)
    if span is not None:
        return gold_evidence(span, source_text)
    return {"quote": fallback, "sentence_id": None, "char_start": None, "char_end": None}


def gold_events_from_document(document_gold: Any, source_text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for index, medication in enumerate(document_gold.medications, start=1):
        name = medication.get("name")
        if not name:
            continue
        events.append(
            {
                "id": f"gold_med_{index}",
                "category": "medication",
                "temporality": "current",
                "status": "current",
                "value": name,
                "medication_name": name,
                "dose": medication.get("dose") or None,
                "dose_unit": medication.get("dose_unit") or None,
                "frequency": medication.get("frequency") or None,
                "reason_stopped": None,
                "evidence": evidence_from_gold(document_gold, "medications", index - 1, source_text, name),
            }
        )

    for index, frequency in enumerate(document_gold.seizure_frequencies, start=1):
        value = frequency.get("value")
        if not value:
            continue
        events.append(
            {
                "id": f"gold_freq_{index}",
                "category": "seizure_frequency",
                "temporality": "current",
                "status": None,
                "value": value,
                "temporal_scope": frequency.get("temporal_scope") or "current",
                "seizure_type": frequency.get("seizure_type") or None,
                "evidence": evidence_from_gold(document_gold, "seizure_frequency", index - 1, source_text, value),
            }
        )
        if frequency.get("seizure_type"):
            events.append(
                {
                    "id": f"gold_type_from_freq_{index}",
                    "category": "seizure_type",
                    "temporality": "current",
                    "status": None,
                    "value": frequency.get("seizure_type"),
                    "evidence": evidence_from_gold(document_gold, "seizure_frequency", index - 1, source_text, frequency.get("seizure_type") or ""),
                }
            )

    for index, diagnosis in enumerate(document_gold.diagnoses, start=1):
        events.append(
            {
                "id": f"gold_dx_{index}",
                "category": "diagnosis",
                "temporality": "current",
                "status": None,
                "value": diagnosis,
                "evidence": evidence_from_gold(document_gold, "diagnosis", index - 1, source_text, diagnosis),
            }
        )

    for field_name, investigation_type in [("eeg", "EEG"), ("mri", "MRI")]:
        result = document_gold.investigations.get(field_name)
        if not result:
            continue
        events.append(
            {
                "id": f"gold_{field_name}",
                "category": "investigation",
                "temporality": "completed",
                "status": "completed",
                "value": result,
                "investigation_type": investigation_type,
                "result": result,
                "evidence": evidence_from_gold(document_gold, field_name, 0, source_text, result),
            }
        )
    return events


def write_csv_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    preferred = ["field", "documents", "oracle_failures", "failure_rate"]
    extra = sorted({key for row in rows for key in row} - set(preferred))
    fieldnames = preferred + extra
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def oracle_error_budget(document_scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = [
        "medication_name",
        "medication_full",
        "seizure_type",
        "current_seizure_frequency",
        "seizure_frequency_type_linkage",
        "epilepsy_diagnosis",
    ]
    rows: list[dict[str, Any]] = []
    for field in fields:
        failures = 0
        available = 0
        for score in document_scores:
            field_scores = score.get("field_scores", {})
            field_correctness = score.get("field_correctness", {})
            value = field_scores.get(field) or field_correctness.get(field)
            if value is None:
                continue
            available += 1
            if isinstance(value, dict):
                ok = value.get("f1") == 1.0 if "f1" in value else bool(value.get("correct"))
            else:
                ok = bool(value)
            failures += 0 if ok else 1
        rows.append(
            {
                "field": field,
                "documents": available,
                "oracle_failures": failures,
                "failure_rate": failures / available if available else 0.0,
            }
        )
    return rows


def command_aggregation_oracle(args: argparse.Namespace) -> int:
    from evaluate import GoldDocument, load_gold, score_document

    ids = load_split_ids(Path(args.splits), args.split, args.limit)
    gold = load_gold(Path(args.markup_root), Path(args.exect_root))
    output_dir = Path(args.output_dir)
    document_scores = []
    log_path = output_dir / "event_first_runs.jsonl"
    if log_path.exists():
        log_path.unlink()

    for document_id in ids:
        source_text = read_text(Path(args.exect_root) / f"{document_id}.txt")
        document_gold = gold.get(document_id, GoldDocument(document_id=document_id))
        events = gold_events_from_document(document_gold, source_text)
        canonical, log = aggregate_events(document_id, events, model_name="gold_aggregation_oracle")
        run_root = output_dir / document_id
        write_json(run_root / "gold_events.json", {"document_id": document_id, "events": events})
        write_json(run_root / "e2_canonical.json", canonical)
        write_json(run_root / "e2_aggregation_log.json", log)
        score = score_document(canonical, source_text, document_gold, Path(args.schema))
        score["document_id"] = document_id
        document_scores.append(score)
        append_jsonl(
            log_path,
            {
                "document_id": document_id,
                "pipeline": "aggregation_oracle",
                "pipeline_id": E2_PIPELINE_ID,
                "canonical_output_path": str(run_root / "e2_canonical.json"),
                "aggregation_log_path": str(run_root / "e2_aggregation_log.json"),
                "gold_event_count": len(events),
                "scores": score,
            },
        )
        print(f"oracle: {document_id} events={len(events)}")

    write_json(output_dir / "oracle_document_scores.json", document_scores)
    budget = oracle_error_budget(document_scores)
    write_csv_rows(output_dir / "aggregation_error_budget.csv", budget)
    print(f"wrote {output_dir / 'aggregation_error_budget.csv'}")
    return 0


def command_run(args: argparse.Namespace) -> int:
    ids = load_split_ids(Path(args.splits), args.split, args.limit)
    failures = 0
    log_path = Path(args.output_dir) / "event_first_runs.jsonl"

    def run_document(document_id: str) -> tuple[list[dict[str, Any]], list[str], int]:
        document_failures = 0
        records: list[dict[str, Any]] = []
        messages: list[str] = []
        document = preprocess_document(document_id, Path(args.exect_root))
        run_root = Path(args.output_dir) / document_id
        payload, e1_record = run_e1(args, document, run_root)
        records.append(e1_record)
        e1_ok = bool(
            e1_record["parse"]["parse_success"]
            and e1_record["scores"]
            and e1_record["scores"].get("event_constraints_valid")
        )
        messages.append(f"{'pass' if e1_ok else 'fail'}: E1 {document_id}")
        if not e1_ok:
            return records, messages, 1

        events = payload["events"] if payload else []
        if "E2" in args.pipelines:
            e2_record = run_e2(args, document, events, run_root)
            records.append(e2_record)
            scores = e2_record["scores"]
            e2_ok = bool(scores.get("schema_valid") and scores.get("project_constraints_valid"))
            messages.append(f"{'pass' if e2_ok else 'fail'}: E2 {document_id}")
            if not e2_ok:
                document_failures += 1
        if "E3" in args.pipelines:
            e3_record = run_e3(args, document, events, run_root)
            records.append(e3_record)
            scores = e3_record["scores"] or {}
            e3_ok = bool(
                e3_record.get("parse", {}).get("parse_success")
                and scores.get("schema_valid")
                and scores.get("project_constraints_valid")
            )
            messages.append(f"{'pass' if e3_ok else 'fail'}: E3 {document_id}")
            if not e3_ok:
                document_failures += 1
        return records, messages, document_failures

    max_workers = max(1, args.max_workers)
    if max_workers == 1:
        results = [run_document(document_id) for document_id in ids]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(run_document, document_id) for document_id in ids]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

    for records, messages, document_failures in results:
        for record in records:
            append_jsonl(log_path, record)
        for message in messages:
            print(message)
        failures += document_failures
    return 1 if failures else 0


def command_prepare(args: argparse.Namespace) -> int:
    ids = load_split_ids(Path(args.splits), args.split, args.limit)
    for document_id in ids:
        document = preprocess_document(document_id, Path(args.exect_root))
        run_root = Path(args.output_dir) / document_id
        write_text(run_root / "e1_prompt.txt", build_e1_prompt(document))
        print(f"wrote {run_root / 'e1_prompt.txt'}")
        if "E3" in args.pipelines:
            write_text(run_root / "e3_prompt.empty_events.txt", build_e3_prompt(document_id, [], Path(args.schema)))
            print(f"wrote {run_root / 'e3_prompt.empty_events.txt'}")
    return 0


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    parser.add_argument("--splits", default=str(DEFAULT_SPLITS))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--split", default="development", choices=["development", "validation", "test"])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--refresh", action="store_true", help="Call the provider even when a raw response already exists.")
    parser.add_argument("--pipelines", nargs="+", default=["E1", "E2"], choices=["E1", "E2", "E3"])
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run event-first extraction and aggregation.")
    add_common_arguments(run)
    run.add_argument("--provider", default="stub", choices=["stub", "openai"])
    run.add_argument("--model", default="gpt-4.1-mini")
    run.set_defaults(func=command_run)

    prepare = subparsers.add_parser("prepare", help="Write event-first prompts without calling a provider.")
    add_common_arguments(prepare)
    prepare.set_defaults(func=command_prepare)

    oracle = subparsers.add_parser("aggregation-oracle", help="Feed gold-derived events through deterministic aggregation.")
    oracle.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    oracle.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    oracle.add_argument("--splits", default=str(DEFAULT_SPLITS))
    oracle.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    oracle.add_argument("--split", default="development", choices=["development", "validation", "test"])
    oracle.add_argument("--limit", type=int)
    oracle.add_argument("--output-dir", default=str(DEFAULT_RECOVERY_ORACLE_DIR))
    oracle.set_defaults(func=command_aggregation_oracle)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
