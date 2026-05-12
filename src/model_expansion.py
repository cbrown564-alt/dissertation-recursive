#!/usr/bin/env python3
"""Stage A smoke runner for the powerful-model expansion study."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import yaml

from core.labels import BENCHMARK_EPILEPSY_LABELS, BENCHMARK_SEIZURE_LABELS, benchmark_label_block
from core.projection import projected_canonical as _core_projected_canonical
from core.prompts import (
    build_h6_prompt as _core_build_h6_prompt,
    build_h6fs_prompt as _core_build_h6fs_prompt,
    build_h6full_prompt as _core_build_h6full_prompt,
    h6_few_shot_examples as _core_h6_few_shot_examples,
    h6full_examples as _core_h6full_examples,
)
from direct_baselines import (
    build_prompt as build_direct_prompt,
    load_split_ids,
    normalize_contract_aliases,
    parse_json_response,
    validate_and_score,
    write_json,
    write_text,
)
from evaluate import DEFAULT_MARKUP_ROOT, GoldDocument, build_field_prf_table, flatten_summary, load_gold, score_document
from intake import DEFAULT_EXECT_ROOT, DEFAULT_SPLITS, preprocess_document
from model_providers import ModelRequest, TokenUsage, adapter_for, estimate_cost, write_response_log
from model_registry import DEFAULT_REGISTRY, load_model_specs, write_registry_snapshot
from normalization import canonical_investigation_result as _canonical_inv
from validate_extraction import DEFAULT_SCHEMA, normalize_text
from validate_extraction import validate_extraction


DEFAULT_HARNESS_MATRIX = Path("configs/harness_matrix.yaml")
DEFAULT_OUTPUT_DIR = Path("runs/model_expansion/stage_a_smoke")
DEFAULT_STAGE_B_OUTPUT_DIR = Path("runs/model_expansion/stage_b_dev_pilot")
DEFAULT_STAGE_C_OUTPUT_DIR = Path("runs/model_expansion/stage_c0_strict_validation")
DEFAULT_STAGE_C1_OUTPUT_DIR = Path("runs/model_expansion/stage_c1_relaxed_projection")
DEFAULT_H6_H7_OUTPUT_DIR = Path("runs/model_expansion/stage_d_h6_h7_diagnostic")
BENCHMARK_METRICS = ["medication_name_f1", "seizure_type_f1", "epilepsy_diagnosis_accuracy"]
RELAXED_PROJECTION_VERSION = "relaxed_v2_benchmark_seizure_labels_no_evidence"


def load_harnesses(path: Path) -> dict[str, dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    harnesses = data.get("harnesses")
    if not isinstance(harnesses, dict):
        raise ValueError(f"harness matrix must contain a harnesses object: {path}")
    return harnesses


def sentence_table(document: dict[str, Any]) -> str:
    return "\n".join(
        f"{sentence['sentence_id']} [{sentence['char_start']}, {sentence['char_end']}]: {sentence['text']}"
        for sentence in document["sentences"]
    )


def build_task_specific_prompt(document: dict[str, Any], harness_id: str) -> str:
    return "\n\n".join(
        [
            "Extract only these benchmark-oriented fields from the epilepsy clinic letter.",
            "Return compact JSON with keys: medication_names, seizure_types, epilepsy_types, seizure_frequency, investigations.",
            "Use null or [] when absent. Do not invent unsupported values.",
            f"## Harness\n{harness_id}",
            "## Sentence List",
            sentence_table(document),
            "## Source Letter",
            document["text"],
        ]
    )


def build_loose_prompt(document: dict[str, Any], harness_id: str) -> str:
    return "\n\n".join(
        [
            "Answer concisely from the epilepsy clinic letter.",
            "List current anti-seizure medications, seizure types, epilepsy diagnosis/type, current seizure frequency, EEG result, and MRI result.",
            "Use brief bullets or simple JSON. Say not stated when the letter does not support a field.",
            f"## Harness\n{harness_id}",
            "## Source Letter",
            document["text"],
        ]
    )


def build_h6_prompt(document: dict[str, Any], harness_id: str) -> str:
    return _core_build_h6_prompt(document, harness_id)


def build_h6v2_prompt(document: dict[str, Any], harness_id: str) -> str:
    """H6 with two seizure-type prompt fixes identified via N1 gap analysis:
    - Explicit 'unknown seizure type' guidance for unspecified-type cases.
    - Temporality restriction to current (not historical) seizure types.
    """
    return "\n\n".join(
        [
            "Extract only benchmark fields from this epilepsy clinic letter.",
            "Return JSON only with this shape:",
            '{"medication_names":[],"seizure_types":[],"epilepsy_diagnosis_type":null}',
            "Medication names should include current anti-seizure medications only. Use generic drug names where possible.",
            (
                "Seizure types must use only the allowed labels. "
                "Include only the patient's CURRENT seizure types as documented in this letter -- do not include historical seizure types that are no longer occurring. "
                "If the patient has seizures but the specific type is not described or is unclear in the letter, use 'unknown seizure type'. "
                "Do not include aura, warning, symptom, medication side effect, investigation finding, or differential diagnosis labels as seizure types."
            ),
            "Epilepsy diagnosis/type must use one allowed label or null. Do not invent a diagnosis if the letter does not support one.",
            benchmark_label_block(),
            f"## Harness\n{harness_id}",
            "## Source Letter",
            document["text"],
        ]
    )


def _h6fs_examples() -> str:
    """Two-shot examples targeting the two dominant N1 seizure-type failure modes:
    (1) 'unknown seizure type' meta-label miss when type is unspecified.
    (2) 'seizure free' when patient is currently seizure-free.
    Examples are synthetic and do not appear in the ExECT dataset.
    """
    return _core_h6_few_shot_examples()


def build_h6fs_prompt(document: dict[str, Any], harness_id: str) -> str:
    """H6 with few-shot examples (Variant A).
    Three inline examples demonstrate: unknown seizure type when unspecified,
    seizure free when currently seizure-free, and seizure free (not historical
    type) when past seizures are mentioned but currently resolved.
    Targets the two dominant N1 failure modes without changing the label set or
    schema shape.
    """
    return _core_build_h6fs_prompt(document, harness_id)


def build_h6qa_prompt(document: dict[str, Any], harness_id: str) -> str:
    """H6 with decomposed current-status reasoning (Variant B).
    Extends the output schema with a required current_seizure_status field.
    The model must classify seizure status before populating seizure_types,
    anchoring temporality and constraining the label choices:
    - active     -> list specific current types (or 'unknown seizure type' if unspecified)
    - seizure_free -> seizure_types must be ['seizure free']
    - unclear    -> seizure_types must be ['unknown seizure type']
    Addresses both N1 failure modes: hallucination on seizure-free letters and
    the 'unknown seizure type' meta-label miss.
    """
    return "\n\n".join(
        [
            "Extract only benchmark fields from this epilepsy clinic letter.",
            "Return JSON only with this shape:",
            '{"current_seizure_status":"active|seizure_free|unclear","medication_names":[],"seizure_types":[],"epilepsy_diagnosis_type":null}',
            (
                "Set current_seizure_status first, then populate seizure_types accordingly:\n"
                "- \"active\": patient is currently experiencing seizures. "
                "List their specific current seizure types using only the allowed labels. "
                "If seizures are occurring but the type is not described, use \"unknown seizure type\".\n"
                "- \"seizure_free\": patient has had no recent seizures (explicitly stated or strongly implied). "
                "Set seizure_types to [\"seizure free\"].\n"
                "- \"unclear\": seizure status is ambiguous or not clearly stated. "
                "Set seizure_types to [\"unknown seizure type\"].\n"
                "Do not include historical seizure types that are no longer occurring. "
                "Do not include aura, warning, symptom, or side effect labels as seizure types."
            ),
            "Medication names should include current anti-seizure medications only. Use generic drug names where possible.",
            "Epilepsy diagnosis/type must use one allowed label or null. Do not invent a diagnosis if the letter does not support one.",
            benchmark_label_block(),
            f"## Harness\n{harness_id}",
            "## Source Letter",
            document["text"],
        ]
    )


def build_h6ev_prompt(document: dict[str, Any], harness_id: str) -> str:
    """H6 with evidence-anchored seizure type extraction (Variant C).
    Adds a single seizure_evidence field: a direct quote from the letter
    confirming the patient's CURRENT seizure status. The constraint is:
    if no current-seizure quote can be found, seizure_types must be [].
    This grounds extraction in the source text and naturally filters
    hallucinations from historical or implicit mentions, since historical
    passages are harder to present as current-status evidence.
    Literature basis: lit review sec. 6 (evidence spans in two layers),
    Abeysinghe et al. 2025 (phrase extraction before attribute extraction).
    """
    return "\n\n".join(
        [
            "Extract only benchmark fields from this epilepsy clinic letter.",
            "Return JSON only with this shape:",
            '{"medication_names":[],"seizure_types":[],"seizure_evidence":null,"epilepsy_diagnosis_type":null}',
            (
                "In seizure_evidence, copy the shortest exact phrase from the letter that "
                "most directly states the patient's CURRENT seizure status -- for example "
                "\"seizure-free since starting lamotrigine\" or \"continuing to have focal seizures\". "
                "Use null if the letter contains no phrase that directly states current seizure status.\n"
                "Then populate seizure_types:\n"
                "- If seizure_evidence is null, set seizure_types to [].\n"
                "- If the evidence states the patient is seizure-free, set seizure_types to [\"seizure free\"].\n"
                "- If the evidence states seizures are ongoing but does not name the type, use [\"unknown seizure type\"].\n"
                "- Otherwise list the specific current seizure types using only the allowed labels."
            ),
            "Medication names should include current anti-seizure medications only. Use generic drug names where possible.",
            "Epilepsy diagnosis/type must use one allowed label or null. Do not invent a diagnosis if the letter does not support one.",
            benchmark_label_block(),
            f"## Harness\n{harness_id}",
            "## Source Letter",
            document["text"],
        ]
    )


def _h6full_examples() -> str:
    """Few-shot examples using the H6full schema (structured medications + investigations)."""
    return _core_h6full_examples()


def build_h6full_prompt(document: dict[str, Any], harness_id: str) -> str:
    """H6full: extends H6 with structured medication dose/unit/frequency,
    explicit EEG/MRI investigations, and current seizure frequency.
    Includes full-schema few-shot examples for calibration.
    Tests whether larger models can follow a richer schema than H6/H6fs.
    """
    return _core_build_h6full_prompt(document, harness_id)


def benchmark_output_schema() -> dict[str, Any]:
    return {
        "name": "benchmark_fields",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "medication_names": {"type": "array", "items": {"type": "string"}},
                "seizure_types": {
                    "type": "array",
                    "items": {"type": "string", "enum": BENCHMARK_SEIZURE_LABELS},
                },
                "epilepsy_diagnosis_type": {
                    "anyOf": [{"type": "string", "enum": BENCHMARK_EPILEPSY_LABELS}, {"type": "null"}]
                },
            },
            "required": ["medication_names", "seizure_types", "epilepsy_diagnosis_type"],
        },
    }


def build_h7_extract_prompt(document: dict[str, Any], harness_id: str) -> str:
    return "\n\n".join(
        [
            "Pass 1 of 2: extract rich clinical facts from this epilepsy clinic letter.",
            "Return JSON only with this shape:",
            '{"rich_facts":[{"category":"medication|seizure_type|epilepsy_diagnosis","text":"","quote":"<exact verbatim span copied from the letter>","current_patient_fact":true}]}',
            "Include current anti-seizure medication names, clinically described seizure/semiology facts, and epilepsy diagnosis/type facts.",
            "The quote field must be an exact contiguous span copied from the source letter. Do not paraphrase. If no single span supports the fact, use the most representative short span.",
            "Mark non-current, family-history, unsupported, or non-patient facts with current_patient_fact=false.",
            f"## Harness\n{harness_id}",
            "## Source Letter",
            document["text"],
        ]
    )


def build_h8_evidence_prompt(document: dict[str, Any], harness_id: str, candidates_text: str) -> str:
    return "\n\n".join(
        [
            "Pass 2 of 2: provide evidence quotes only for the selected benchmark candidate fields.",
            "Return JSON only with this shape:",
            '{"field_evidence":[{"field":"medication_names|seizure_types|epilepsy_diagnosis_type","value":"","quote":""}]}',
            "Quotes must be exact short spans copied from the source letter. If no exact supporting quote exists, omit that evidence item.",
            f"## Harness\n{harness_id}",
            "## Candidate Fields",
            candidates_text,
            "## Source Letter",
            document["text"],
        ]
    )


def build_d3_candidate_prompt(document: dict[str, Any], harness_id: str) -> str:
    return "\n\n".join(
        [
            "Pass 1 of 2: extract permissive candidate benchmark facts from this epilepsy clinic letter.",
            "Return JSON only with this shape:",
            '{"candidates":[{"category":"medication|seizure_type|epilepsy_diagnosis","text":"","support":""}]}',
            "Include possible current anti-seizure medications, seizure labels/semiology, and epilepsy diagnosis/type facts. Preserve specific wording.",
            f"## Harness\n{harness_id}",
            "## Source Letter",
            document["text"],
        ]
    )


def build_d3_verifier_prompt(document: dict[str, Any], harness_id: str, candidates_text: str) -> str:
    return "\n\n".join(
        [
            "Pass 2 of 2: verify candidate facts and drop unsupported or non-benchmark labels.",
            "Return JSON only with this shape:",
            '{"medications":[{"name":"","dose":null,"unit":null,"frequency":null,"quote":""}],"verified_seizure_type_mappings":[{"candidate":"","benchmark_label":null,"keep":true,"reason":"supported|unsupported|not_benchmark_relevant|too_specific","quote":""}],"seizure_types":[{"label":"","quote":""}],"epilepsy_diagnosis_type":{"label":null,"quote":""}}',
            "Keep only current patient anti-seizure medications. Extract name, dose, unit, and frequency from the source letter quote.",
            "For seizure types, keep only supported benchmark labels. Drop aura-only symptoms, non-patient history, investigation-only findings, and unsupported differentials. Map too-specific supported labels to the nearest allowed benchmark label.",
            "Every kept medication, seizure type, and epilepsy diagnosis/type must include an exact contiguous quote copied from the source letter.",
            "If no exact source quote supports a candidate, drop it rather than returning an unsupported field.",
            benchmark_label_block(),
            f"## Harness\n{harness_id}",
            "## Candidate Facts",
            candidates_text,
            "## Source Letter",
            document["text"],
        ]
    )


def build_h7_normalize_prompt(document: dict[str, Any], harness_id: str, rich_fact_text: str) -> str:
    return "\n\n".join(
        [
            "Pass 2 of 2: map extracted clinical facts to benchmark labels and preserve evidence quotes.",
            "Use only the extracted facts and source letter. Return JSON only with this shape:",
            '{"medications":[{"name":"","dose":null,"unit":null,"frequency":null,"quote":""}],"seizure_type_mappings":[{"fact":"","benchmark_label":null,"decision":"supported|unsupported|too_specific|not_benchmark_relevant","quote":""}],"seizure_types":[{"label":"","quote":""}],"epilepsy_diagnosis_type":{"label":null,"quote":""},"epilepsy_diagnosis_decision":"supported|unsupported|too_specific|not_benchmark_relevant"}',
            "Keep medications as current anti-seizure medications. Extract name, dose, unit, and frequency from Pass 1 rich_facts or the source letter.",
            "For seizure_types, include only supported benchmark labels from mappings. Drop aura-only symptoms, non-patient facts, investigation-only findings, and unsupported differentials.",
            "Every kept medication_name, seizure_type, and epilepsy_diagnosis_type must include the exact quote from Pass 1 (or from the source letter if Pass 1 omitted it).",
            "If a fact is clinically specific, map it to the nearest allowed benchmark label and set decision=too_specific.",
            benchmark_label_block(),
            f"## Harness\n{harness_id}",
            "## Pass 1 Rich Facts",
            rich_fact_text,
            "## Source Letter",
            document["text"],
        ]
    )


def build_vocab_preamble() -> str:
    return "\n".join(
        [
            "## Anti-seizure medication names",
            "Common ASMs include: levetiracetam (Keppra), sodium valproate (Epilim, Eplim),",
            "lamotrigine (Lamictal), carbamazepine (Tegretol), phenytoin, topiramate, zonisamide,",
            "brivaracetam, lacosamide, oxcarbazepine, perampanel, clobazam, clonazepam.",
            "Normalize brand names to generic names in your output.",
            "",
            "## Epilepsy and seizure terminology",
            "Focal seizures: focal aware, focal impaired awareness, focal to bilateral tonic-clonic.",
            "Generalized seizures: generalized tonic-clonic (GTCS), absence, myoclonic, atonic.",
            "Epilepsy syndromes: JME (juvenile myoclonic epilepsy), childhood absence epilepsy (CAE),",
            "Lennox-Gastaut syndrome (LGS), DRAVET syndrome.",
        ]
    )


def build_harness_prompt(harness_id: str, document: dict[str, Any], schema_path: Path, vocab_preamble: bool = False) -> str:
    if harness_id == "H0_strict_canonical":
        return build_direct_prompt("S2", document, schema_path)
    if harness_id == "H2_task_specific":
        return build_task_specific_prompt(document, harness_id)
    if harness_id == "H3_loose_answer_then_parse":
        prompt = build_loose_prompt(document, harness_id)
    elif harness_id == "H6_benchmark_only_coarse_json":
        prompt = build_h6_prompt(document, harness_id)
    elif harness_id == "H4_provider_native_structured_output":
        prompt = build_h6_prompt(document, harness_id)
    else:
        raise ValueError(f"unsupported Stage A harness: {harness_id}")
    if vocab_preamble:
        return build_vocab_preamble() + "\n\n" + prompt
    return prompt


def provider_for_args(model_provider: str, stub_calls: bool) -> str:
    return "stub" if stub_calls else model_provider


def run_one(args: argparse.Namespace, model_label: str, harness_id: str, document_id: str) -> dict[str, Any]:
    specs = load_model_specs(Path(args.registry))
    spec = specs[model_label]
    document = preprocess_document(document_id, Path(args.exect_root))
    prompt = build_harness_prompt(harness_id, document, Path(args.schema))

    run_root = Path(args.output_dir) / model_label / harness_id / document_id
    prompt_path = run_root / "prompt.txt"
    raw_path = run_root / "raw_response.txt"
    response_log_path = run_root / "provider_response.json"
    write_text(prompt_path, prompt)

    request = ModelRequest(
        prompt=prompt,
        model=spec,
        harness_id=harness_id,
        temperature=args.temperature if args.temperature is not None else spec.temperature,
        max_output_tokens=args.max_output_tokens or spec.max_output_tokens,
        schema_mode=None,
        reasoning_effort=args.reasoning_effort,
        google_thinking_budget=args.google_thinking_budget,
        metadata={"document_id": document_id, "stage": "stage_a_smoke"},
    )
    adapter = adapter_for(provider_for_args(spec.provider, args.stub_calls))
    response = adapter.call(request)
    write_text(raw_path, response.text)
    response.raw_response_path = str(raw_path)
    write_response_log(response, response_log_path)

    parse = parse_json_response(response.text)
    scores = None
    if harness_id == "H0_strict_canonical" and parse.data is not None:
        parse.data = normalize_contract_aliases(parse.data, document_id, f"D0_{harness_id}")
        metadata = parse.data.setdefault("metadata", {}) if isinstance(parse.data, dict) else {}
        if isinstance(metadata, dict):
            metadata.update(
                {
                    "model": spec.provider_model_id,
                    "model_label": model_label,
                    "provider": spec.provider,
                    "harness_id": harness_id,
                    "latency_ms": response.latency_ms,
                    "input_tokens": response.token_usage.input_tokens,
                    "output_tokens": response.token_usage.output_tokens,
                    "cache_read_tokens": response.token_usage.cache_read_tokens,
                    "cache_write_tokens": response.token_usage.cache_write_tokens,
                    "estimated_cost_usd": response.estimated_cost.get("total"),
                    "pricing_snapshot_date": response.estimated_cost.get("pricing_snapshot_date"),
                    "repair_attempted": parse.repair_attempted,
                    "repair_succeeded": parse.repair_succeeded,
                }
            )
        scores = validate_and_score(parse.data, document["text"], Path(args.schema), require_present_evidence=True)
        write_json(run_root / "canonical.json", parse.data)

    record = {
        "model_label": model_label,
        "provider": spec.provider,
        "called_provider": adapter.provider,
        "provider_model_id": spec.provider_model_id,
        "harness_id": harness_id,
        "document_id": document_id,
        "status": "success" if not response.error else "unavailable",
        "error": response.error,
        "stop_reason": response.stop_reason,
        "prompt_path": str(prompt_path),
        "raw_response_path": str(raw_path),
        "provider_response_path": str(response_log_path),
        "canonical_output_path": str(run_root / "canonical.json") if scores is not None else None,
        "parse_success": parse.parse_success,
        "repair_attempted": parse.repair_attempted,
        "repair_succeeded": parse.repair_succeeded,
        "schema_valid": (scores or {}).get("schema_valid"),
        "project_constraints_valid": (scores or {}).get("project_constraints_valid"),
        "input_tokens": response.token_usage.input_tokens,
        "output_tokens": response.token_usage.output_tokens,
        "cache_read_tokens": response.token_usage.cache_read_tokens,
        "cache_write_tokens": response.token_usage.cache_write_tokens,
        "latency_ms": round(response.latency_ms, 3),
        "retries": response.retries,
        "estimated_cost": response.estimated_cost.get("total"),
        "cost_status": response.estimated_cost.get("status"),
        "pricing_snapshot_date": response.estimated_cost.get("pricing_snapshot_date"),
        "parse_error": parse.error,
    }
    return record


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    # Collect all unique fieldnames across all rows to handle heterogeneous summary rows
    seen: dict[str, None] = {}
    for row in rows:
        seen.update(dict.fromkeys(row.keys()))
    fieldnames = list(seen)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", restval="")
        writer.writeheader()
        writer.writerows(rows)


def command_stage_a(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    snapshot = write_registry_snapshot(output_dir / "model_registry_snapshot.json", Path(args.registry))
    specs = load_model_specs(Path(args.registry))
    harnesses = load_harnesses(Path(args.harness_matrix))
    document_ids = load_split_ids(Path(args.splits), args.split, args.limit)
    model_labels = args.models or list(specs)
    harness_ids = args.harnesses or ["H0_strict_canonical", "H2_task_specific", "H3_loose_answer_then_parse"]

    rows = []
    for model_label in model_labels:
        if model_label not in specs:
            raise ValueError(f"unknown model label: {model_label}")
        for harness_id in harness_ids:
            if harness_id not in harnesses:
                raise ValueError(f"unknown harness id: {harness_id}")
            for document_id in document_ids:
                row = run_one(args, model_label, harness_id, document_id)
                rows.append(row)
                print(f"{row['status']}: {model_label} {harness_id} {document_id}", flush=True)

    write_csv(output_dir / "provider_call_report.csv", rows)
    manifest = {
        "stage": "stage_a_smoke",
        "registry_version": snapshot.get("version"),
        "harness_matrix": args.harness_matrix,
        "split": args.split,
        "document_ids": document_ids,
        "model_labels": model_labels,
        "harness_ids": harness_ids,
        "max_output_tokens": args.max_output_tokens,
        "reasoning_effort": args.reasoning_effort,
        "google_thinking_budget": args.google_thinking_budget,
        "stub_calls": args.stub_calls,
        "report": str(output_dir / "provider_call_report.csv"),
    }
    write_json(output_dir / "stage_a_manifest.json", manifest)
    failures = [row for row in rows if row["status"] != "success"]
    return 1 if failures and not args.allow_unavailable else 0


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def to_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def mean_present(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return sum(present) / len(present) if present else None


def system_for_harness(harness_id: str) -> str:
    return {
        "H0_strict_canonical": "D0",
        "H2_task_specific": "D1",
        "H3_loose_answer_then_parse": "D2",
        "H4_provider_native_structured_output": "D4",
        "H6_benchmark_only_coarse_json": "D6",
        "H7_extract_then_normalize": "D7",
        "H8_evidence_later": "D8",
        "D3_candidate_plus_verifier": "D3",
    }.get(harness_id, harness_id)


def truthy_csv(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def resolve_report_path(stage_a_dir: Path, row: dict[str, str], field: str) -> Path | None:
    value = (row.get(field) or "").strip()
    if not value:
        return None
    path = Path(value)
    candidates = [path] if path.is_absolute() else [path, stage_a_dir / path]
    source_dir = (row.get("source_dir") or "").strip()
    if source_dir and not path.is_absolute():
        candidates.append(Path(source_dir) / path)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0] if candidates else None


def canonical_path_for_report_row(stage_a_dir: Path, row: dict[str, str]) -> Path:
    explicit = resolve_report_path(stage_a_dir, row, "canonical_output_path")
    if explicit and explicit.exists():
        return explicit
    raw_path = resolve_report_path(stage_a_dir, row, "raw_response_path")
    if raw_path:
        sibling = raw_path.with_name("canonical.json")
        if sibling.exists():
            return sibling
    return stage_a_dir / row["model_label"] / row["harness_id"] / row["document_id"] / "canonical.json"


def parse_success_for_row(stage_a_dir: Path, row: dict[str, str]) -> bool:
    if "parse_success" in row and (row.get("parse_success") or "") != "":
        parsed = truthy_csv(row.get("parse_success"))
        if row.get("harness_id") == "H0_strict_canonical":
            return parsed and canonical_path_for_report_row(stage_a_dir, row).exists()
        return parsed
    return row.get("harness_id") == "H0_strict_canonical" and canonical_path_for_report_row(stage_a_dir, row).exists()


def repair_attempted_for_row(row: dict[str, str]) -> bool:
    return truthy_csv(row.get("repair_attempted"))


def repair_succeeded_for_row(row: dict[str, str]) -> bool:
    return truthy_csv(row.get("repair_succeeded"))


def availability_note(pair_rows: list[dict[str, str]]) -> str:
    errors = " ".join(row.get("error") or "" for row in pair_rows)
    successes = sum(1 for row in pair_rows if row.get("status") == "success")
    failures = len(pair_rows) - successes
    if failures and successes == 0 and ("RESOURCE_EXHAUSTED" in errors or "quota" in errors.lower() or "429" in errors):
        return "unavailable_due_to_quota"
    if failures and successes and ("503" in errors or "UNAVAILABLE" in errors):
        return "mostly_available_with_transient_503"
    if failures:
        return "partially_available_with_failures"
    return "available"


def score_stage_b_canonical(
    stage_a_dir: Path,
    rows: list[dict[str, str]],
    exect_root: Path,
    markup_root: Path,
    schema_path: Path,
) -> dict[tuple[str, str], dict[str, Any]]:
    gold = load_gold(markup_root, exect_root)
    by_pair: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("harness_id") != "H0_strict_canonical":
            continue
        document_id = row["document_id"]
        canonical_path = canonical_path_for_report_row(stage_a_dir, row)
        data = json.loads(canonical_path.read_text(encoding="utf-8")) if canonical_path.exists() else None
        source_text = preprocess_document(document_id, exect_root)["text"]
        by_pair.setdefault((row["model_label"], row["harness_id"]), []).append(
            score_document(data, source_text, gold[document_id], schema_path)
        )
    return {pair: flatten_summary(f"{pair[0]}:{pair[1]}", scores) for pair, scores in by_pair.items()}


def summarize_stage_b_rows(
    stage_a_dir: Path,
    rows: list[dict[str, str]],
    canonical_scores: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault((row["model_label"], row["harness_id"]), []).append(row)

    summaries = []
    for (model_label, harness_id), pair_rows in sorted(grouped.items()):
        status_success = sum(1 for row in pair_rows if row.get("status") == "success")
        parse_success = sum(1 for row in pair_rows if parse_success_for_row(stage_a_dir, row))
        repair_attempted = sum(1 for row in pair_rows if repair_attempted_for_row(row))
        repair_succeeded = sum(1 for row in pair_rows if repair_succeeded_for_row(row))
        scored = canonical_scores.get((model_label, harness_id), {})
        canonical_documents_available = int(scored.get("documents_available") or 0)
        benchmark_values = [to_float(scored.get(metric)) for metric in BENCHMARK_METRICS]
        benchmark_quality = mean_present(benchmark_values)
        mean_cost = mean_present([to_float(row.get("estimated_cost")) for row in pair_rows])
        note = availability_note(pair_rows)
        scoring_status = "canonical_scored" if canonical_documents_available else "parser_only_until_canonical_projection"
        summary = {
            "model_label": model_label,
            "provider": pair_rows[0].get("provider"),
            "provider_model_id": pair_rows[0].get("provider_model_id"),
            "system": system_for_harness(harness_id),
            "harness_id": harness_id,
            "documents": len(pair_rows),
            "canonical_documents_available": canonical_documents_available,
            "successful_calls": status_success,
            "call_success_rate": status_success / len(pair_rows) if pair_rows else 0.0,
            "availability_note": note,
            "parse_success_rate": parse_success / len(pair_rows) if pair_rows else 0.0,
            "repair_attempt_rate": repair_attempted / len(pair_rows) if pair_rows else 0.0,
            "repair_success_rate": repair_succeeded / repair_attempted if repair_attempted else 1.0,
            "schema_valid_rate": scored.get("schema_valid_rate"),
            "quote_presence_rate": scored.get("quote_presence_rate"),
            "quote_validity_rate": scored.get("quote_validity_rate"),
            "temporal_accuracy": scored.get("temporal_accuracy"),
            "medication_name_f1": scored.get("medication_name_f1"),
            "seizure_type_f1": scored.get("seizure_type_f1"),
            "epilepsy_diagnosis_accuracy": scored.get("epilepsy_diagnosis_accuracy"),
            "benchmark_quality": benchmark_quality,
            "mean_latency_ms": mean_present([to_float(row.get("latency_ms")) for row in pair_rows]),
            "latency_p50_ms": percentile([value for value in [to_float(row.get("latency_ms")) for row in pair_rows] if value is not None], 0.50),
            "latency_p95_ms": percentile([value for value in [to_float(row.get("latency_ms")) for row in pair_rows] if value is not None], 0.95),
            "mean_input_tokens": mean_present([to_float(row.get("input_tokens")) for row in pair_rows]),
            "mean_output_tokens": mean_present([to_float(row.get("output_tokens")) for row in pair_rows]),
            "mean_estimated_cost_usd": mean_cost,
            "cost_per_benchmark_quality_point": (mean_cost / benchmark_quality) if mean_cost is not None and benchmark_quality else None,
            "scoring_status": scoring_status,
            "promotion_eligibility": "eligible" if scoring_status == "canonical_scored" and note == "available" else f"excluded_or_marked:{note}",
        }
        summaries.append(summary)
    return summaries


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    position = (len(ordered) - 1) * pct
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def cost_frontier(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [
        row
        for row in rows
        if isinstance(row.get("benchmark_quality"), (int, float))
        and isinstance(row.get("mean_estimated_cost_usd"), (int, float))
        and row.get("scoring_status") == "canonical_scored"
        and row.get("availability_note") == "available"
        and (to_float(row.get("call_success_rate")) or 0.0) >= 0.9
        and (to_float(row.get("parse_success_rate")) or 0.0) >= 0.9
        and (to_float(row.get("schema_valid_rate")) or 0.0) >= 0.9
    ]
    frontier = []
    for row in candidates:
        dominated = any(
            other is not row
            and other["benchmark_quality"] >= row["benchmark_quality"]
            and other["mean_estimated_cost_usd"] <= row["mean_estimated_cost_usd"]
            and (
                other["benchmark_quality"] > row["benchmark_quality"]
                or other["mean_estimated_cost_usd"] < row["mean_estimated_cost_usd"]
            )
            for other in candidates
        )
        if not dominated:
            frontier.append({**row, "frontier_reason": "not_dominated_on_quality_and_cost"})
    return sorted(frontier, key=lambda row: (row["mean_estimated_cost_usd"], -row["benchmark_quality"]))


def promotion_decision(rows: list[dict[str, Any]], frontier_rows: list[dict[str, Any]], split: str) -> str:
    scored_rows = [row for row in rows if row["scoring_status"] == "canonical_scored"]
    baseline = next((row for row in scored_rows if row["model_label"] == "gpt_4_1_mini_baseline"), None)
    baseline_quality = to_float((baseline or {}).get("benchmark_quality")) or 0.0
    promoted = [
        row
        for row in frontier_rows
        if (to_float(row.get("benchmark_quality")) or 0.0) >= baseline_quality
        and row.get("availability_note") == "available"
        and (to_float(row.get("call_success_rate")) or 0.0) >= 0.9
        and (to_float(row.get("parse_success_rate")) or 0.0) >= 0.9
        and (to_float(row.get("schema_valid_rate")) or 0.0) >= 0.9
    ]
    cheapest = min(scored_rows, key=lambda row: to_float(row.get("mean_estimated_cost_usd")) or float("inf"), default=None)
    retained_baseline = baseline or cheapest

    lines = [
        "# Stage B Development Pilot Promotion Decision",
        "",
        f"Split: `{split}`",
        "",
        "## Summary",
        "",
        f"- Scored canonical pairs: {len(scored_rows)}",
        f"- Cost-effectiveness frontier pairs: {len(frontier_rows)}",
        f"- Baseline benchmark quality: {baseline_quality:.4f}",
        f"- Retained cheap baseline: `{retained_baseline['model_label']}` / `{retained_baseline['harness_id']}`"
        if retained_baseline
        else "- Retained cheap baseline: none",
        "",
        "## Promoted Pairs",
        "",
    ]
    if promoted:
        for row in promoted:
            lines.append(
                "- "
                + f"`{row['model_label']}` / `{row['harness_id']}` "
                + f"(quality={to_float(row.get('benchmark_quality')) or 0.0:.4f}, "
                + f"mean_cost_usd={to_float(row.get('mean_estimated_cost_usd')) or 0.0:.8f})"
            )
    else:
        lines.append("- None; no scored pair passed the promotion gate.")
    lines.extend(["", "## Gate Notes", ""])
    if any(row["model_label"] == "gemini_3_1_pro" and row.get("availability_note") == "unavailable_due_to_quota" for row in rows):
        lines.append("- `gemini_3_1_pro` is marked unavailable where Stage A returned quota/resource-exhausted errors.")
    if any(row["model_label"] == "gemini_3_1_flash" and row.get("availability_note") == "mostly_available_with_transient_503" for row in rows):
        lines.append("- `gemini_3_1_flash` is marked mostly available where Stage A mixed successful calls with a transient 503.")
    lines.extend(
        [
            "- `H2_task_specific` and `H3_loose_answer_then_parse` are tracked for call and parse stability, but remain parser-only until a deterministic canonical projection is added.",
            "- Promotion requires call/parse stability, canonical schema validity, and non-dominance on cost versus benchmark-quality when cost is available.",
        ]
    )
    return "\n".join(lines) + "\n"


def command_stage_b(args: argparse.Namespace) -> int:
    stage_a_dir = Path(args.stage_a_dir)
    report_path = stage_a_dir / "provider_call_report.csv"
    if not report_path.exists():
        raise FileNotFoundError(f"Stage A provider report not found: {report_path}")
    rows = read_csv(report_path)
    canonical_scores = score_stage_b_canonical(
        stage_a_dir,
        rows,
        Path(args.exect_root),
        Path(args.markup_root),
        Path(args.schema),
    )
    summaries = summarize_stage_b_rows(stage_a_dir, rows, canonical_scores)
    frontier = cost_frontier(summaries)
    output_dir = Path(args.output_dir)
    write_csv(output_dir / "comparison_table.csv", summaries)
    write_csv(output_dir / "cost_effectiveness_frontier.csv", frontier)
    (output_dir / "promotion_decision.md").parent.mkdir(parents=True, exist_ok=True)
    (output_dir / "promotion_decision.md").write_text(
        promotion_decision(summaries, frontier, args.split),
        encoding="utf-8",
    )
    manifest = {
        "stage": "stage_b_dev_pilot",
        "source_stage_a_dir": str(stage_a_dir),
        "split": args.split,
        "artifact_path_policy": "canonical_output_path/raw_response_path from provider report are honored before falling back under source_stage_a_dir",
        "comparison_table": str(output_dir / "comparison_table.csv"),
        "cost_effectiveness_frontier": str(output_dir / "cost_effectiveness_frontier.csv"),
        "promotion_decision": str(output_dir / "promotion_decision.md"),
    }
    write_json(output_dir / "stage_b_manifest.json", manifest)
    print(f"wrote Stage B comparison for {len(summaries)} model/harness pairs")
    return 0


def condition_label(model_label: str, harness_id: str, system: str) -> str:
    return f"{model_label}:{system}:{harness_id}"


def score_stage_a_outputs(
    stage_a_dir: Path,
    exect_root: Path,
    markup_root: Path,
    schema_path: Path,
    harness_ids: set[str] | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    report_path = stage_a_dir / "provider_call_report.csv"
    if not report_path.exists():
        raise FileNotFoundError(f"Stage A provider report not found: {report_path}")
    rows = read_csv(report_path)
    gold = load_gold(markup_root, exect_root)
    all_scores: dict[str, list[dict[str, Any]]] = {}
    metadata: dict[str, dict[str, Any]] = {}

    for row in rows:
        harness_id = row.get("harness_id", "")
        if harness_ids and harness_id not in harness_ids:
            continue
        system = system_for_harness(harness_id)
        label = condition_label(row["model_label"], harness_id, system)
        metadata.setdefault(
            label,
            {
                "model_label": row["model_label"],
                "registry_model_label": row["model_label"],
                "provider": row.get("provider"),
                "provider_model_id": row.get("provider_model_id"),
                "system": system,
                "harness_id": harness_id,
                "source": "stage_a_outputs",
                "source_dir": str(stage_a_dir),
                "call_rows": [],
            },
        )
        metadata[label]["call_rows"].append(row)
        if harness_id != "H0_strict_canonical":
            continue

        document_id = row["document_id"]
        canonical_path = canonical_path_for_report_row(stage_a_dir, row)
        data = json.loads(canonical_path.read_text(encoding="utf-8")) if canonical_path.exists() else None
        source_text = preprocess_document(document_id, exect_root)["text"]
        score = score_document(data, source_text, gold.get(document_id, GoldDocument(document_id=document_id)), schema_path)
        score["document_id"] = document_id
        score["system"] = label
        all_scores.setdefault(label, []).append(score)
    return all_scores, metadata


def load_evaluation_condition(value: str) -> tuple[str, str, str, Path]:
    parts = value.split(":", 3)
    if len(parts) != 4:
        raise ValueError(
            "--evaluation-condition must be LABEL:SYSTEM:HARNESS_ID:EVALUATION_DIR, "
            f"got: {value}"
        )
    label, system, harness_id, evaluation_dir = parts
    return label, system, harness_id, Path(evaluation_dir)


def parse_condition_model(values: list[str] | None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError(f"--condition-model must be CONDITION=REGISTRY_MODEL_LABEL, got: {value}")
        condition, model_label = value.split("=", 1)
        mapping[condition] = model_label
    return mapping


def load_existing_evaluation_conditions(
    conditions: list[str] | None,
    condition_models: dict[str, str] | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    all_scores: dict[str, list[dict[str, Any]]] = {}
    metadata: dict[str, dict[str, Any]] = {}
    for condition in conditions or []:
        label, system, harness_id, evaluation_dir = load_evaluation_condition(condition)
        document_scores_path = evaluation_dir / "document_scores.json"
        if not document_scores_path.exists():
            raise FileNotFoundError(f"missing document scores for condition {condition}: {document_scores_path}")
        document_scores = json.loads(document_scores_path.read_text(encoding="utf-8"))
        system_scores = document_scores.get(system)
        if not isinstance(system_scores, list):
            raise ValueError(f"system {system} not found in {document_scores_path}")
        all_scores[label] = [{**score, "system": label} for score in system_scores]
        metadata[label] = {
            "model_label": label,
            "registry_model_label": (condition_models or {}).get(label, label),
            "provider": None,
            "provider_model_id": None,
            "system": system,
            "harness_id": harness_id,
            "source": "evaluation_dir",
            "source_dir": str(evaluation_dir),
            "call_rows": [],
        }
    return all_scores, metadata


def document_metric_value(score: dict[str, Any], metric: str) -> float:
    field_scores = score.get("field_scores", {})
    item = field_scores.get(metric, {})
    if metric in {"medication_name", "seizure_type"} and isinstance(item, dict):
        return float(item.get("f1", 0.0))
    if isinstance(item, dict):
        return 1.0 if item.get("correct") else 0.0
    return 0.0


def summarize_condition(label: str, scores: list[dict[str, Any]], meta: dict[str, Any]) -> dict[str, Any]:
    summary = flatten_summary(label, scores)
    call_rows = meta.get("call_rows") or []
    parse_success = sum(1 for row in call_rows if row.get("parse_success") == "True")
    repair_attempted = sum(1 for row in call_rows if row.get("repair_attempted") == "True")
    repair_succeeded = sum(1 for row in call_rows if row.get("repair_succeeded") == "True")
    benchmark_quality = mean_present([to_float(summary.get(metric)) for metric in BENCHMARK_METRICS])
    mean_input_tokens = summary.get("mean_input_tokens")
    mean_output_tokens = summary.get("mean_output_tokens")
    mean_estimated_cost = summary.get("mean_estimated_cost_usd")
    if mean_estimated_cost is None:
        mean_estimated_cost = estimate_mean_cost_from_registry(
            meta.get("registry_model_label"),
            mean_input_tokens,
            mean_output_tokens,
            meta.get("model_specs", {}),
        )

    return {
        "condition": label,
        "model_label": meta.get("model_label"),
        "provider": meta.get("provider"),
        "provider_model_id": meta.get("provider_model_id"),
        "system": meta.get("system"),
        "harness_id": meta.get("harness_id"),
        "source": meta.get("source"),
        "documents_expected": summary.get("documents_expected"),
        "documents_available": summary.get("documents_available"),
        "call_success_rate": (sum(1 for row in call_rows if row.get("status") == "success") / len(call_rows))
        if call_rows
        else None,
        "parse_success_rate": parse_success / len(call_rows) if call_rows else None,
        "repair_attempt_rate": repair_attempted / len(call_rows) if call_rows else None,
        "repair_success_rate": repair_succeeded / repair_attempted if repair_attempted else None,
        "schema_valid_rate": summary.get("schema_valid_rate"),
        "quote_presence_rate": summary.get("quote_presence_rate"),
        "quote_validity_rate": summary.get("quote_validity_rate"),
        "temporal_accuracy": summary.get("temporal_accuracy"),
        "medication_name_f1": summary.get("medication_name_f1"),
        "seizure_type_f1": summary.get("seizure_type_f1"),
        "epilepsy_diagnosis_accuracy": summary.get("epilepsy_diagnosis_accuracy"),
        "medication_full_f1": summary.get("medication_full_f1"),
        "current_seizure_frequency_accuracy": summary.get("current_seizure_frequency_accuracy"),
        "seizure_frequency_type_linkage_accuracy": summary.get("seizure_frequency_type_linkage_accuracy"),
        "benchmark_quality": benchmark_quality,
        "mean_latency_ms": summary.get("mean_latency_ms"),
        "mean_input_tokens": mean_input_tokens,
        "mean_output_tokens": mean_output_tokens,
        "mean_estimated_cost_usd": mean_estimated_cost,
        "cost_estimation_status": cost_estimation_status(
            mean_estimated_cost,
            meta.get("registry_model_label"),
            mean_input_tokens,
            mean_output_tokens,
        ),
    }


def estimate_mean_cost_from_registry(
    registry_model_label: str | None,
    mean_input_tokens: Any,
    mean_output_tokens: Any,
    specs: dict[str, Any],
) -> float | None:
    input_tokens = to_float(mean_input_tokens)
    output_tokens = to_float(mean_output_tokens)
    if not registry_model_label or registry_model_label not in specs:
        return None
    if input_tokens is None or output_tokens is None:
        return None
    if input_tokens <= 0 and output_tokens <= 0:
        return None
    cost = estimate_cost(
        specs[registry_model_label],
        TokenUsage(input_tokens=int(round(input_tokens)), output_tokens=int(round(output_tokens))),
    )
    return cost.get("total") if cost.get("status") == "complete" else None


def cost_estimation_status(
    mean_estimated_cost: Any,
    registry_model_label: str | None,
    mean_input_tokens: Any,
    mean_output_tokens: Any,
) -> str:
    if isinstance(mean_estimated_cost, (int, float)):
        return "estimated_or_recorded"
    if not registry_model_label:
        return "missing_registry_model_label"
    input_tokens = to_float(mean_input_tokens)
    output_tokens = to_float(mean_output_tokens)
    if input_tokens is None or output_tokens is None:
        return "missing_token_usage"
    if input_tokens <= 0 and output_tokens <= 0:
        return "legacy_zero_token_usage"
    return "missing_registry_price"


def bootstrap_stage_c(
    all_scores: dict[str, list[dict[str, Any]]],
    summaries: dict[str, dict[str, Any]],
    iterations: int,
    seed: int,
) -> dict[str, Any]:
    import random

    rng = random.Random(seed)
    intervals: dict[str, dict[str, Any]] = {}
    for label, scores in all_scores.items():
        intervals[label] = {}
        if not scores:
            continue
        for metric in ["medication_name", "seizure_type", "epilepsy_diagnosis"]:
            samples = []
            for _ in range(iterations):
                sampled_scores = [scores[rng.randrange(len(scores))] for _ in scores]
                samples.append(sum(document_metric_value(score, metric) for score in sampled_scores) / len(sampled_scores))
            intervals[label][metric] = {
                "observed": summaries[label].get(f"{metric}_f1")
                if metric != "epilepsy_diagnosis"
                else summaries[label].get("epilepsy_diagnosis_accuracy"),
                "ci95_low": percentile(samples, 0.025),
                "ci95_high": percentile(samples, 0.975),
                "bootstrap_iterations": iterations,
            }
    return intervals


def correctly_extracted_benchmark_units(scores: list[dict[str, Any]]) -> float:
    total = 0.0
    for score in scores:
        total += document_metric_value(score, "medication_name")
        total += document_metric_value(score, "seizure_type")
        total += document_metric_value(score, "epilepsy_diagnosis")
    return total


def build_cost_latency_table(summaries: list[dict[str, Any]], all_scores: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows = []
    for summary in summaries:
        label = summary["condition"]
        scores = all_scores.get(label, [])
        cost = to_float(summary.get("mean_estimated_cost_usd"))
        correct_units = correctly_extracted_benchmark_units(scores)
        rows.append(
            {
                "condition": label,
                "model_label": summary.get("model_label"),
                "system": summary.get("system"),
                "harness_id": summary.get("harness_id"),
                "documents_available": summary.get("documents_available"),
                "mean_latency_ms": summary.get("mean_latency_ms"),
                "latency_p50_ms": percentile(
                    [
                        score.get("cost_latency", {}).get("latency_ms")
                        for score in scores
                        if isinstance(score.get("cost_latency", {}).get("latency_ms"), (int, float))
                    ],
                    0.50,
                ),
                "latency_p95_ms": percentile(
                    [
                        score.get("cost_latency", {}).get("latency_ms")
                        for score in scores
                        if isinstance(score.get("cost_latency", {}).get("latency_ms"), (int, float))
                    ],
                    0.95,
                ),
                "mean_input_tokens": summary.get("mean_input_tokens"),
                "mean_output_tokens": summary.get("mean_output_tokens"),
                "mean_estimated_cost_usd": cost,
                "cost_estimation_status": summary.get("cost_estimation_status"),
                "cost_per_correct_benchmark_unit": cost / correct_units if cost is not None and correct_units else None,
                "correct_benchmark_units": correct_units,
            }
        )
    return rows


def validation_decision(summaries: list[dict[str, Any]], split: str) -> dict[str, Any]:
    eligible = [
        row
        for row in summaries
        if (to_float(row.get("benchmark_quality")) or 0.0) > 0.0
        and (to_float(row.get("schema_valid_rate")) or 0.0) >= 0.9
        and (to_float(row.get("quote_validity_rate")) or 0.0) >= 0.9
    ]
    quality_ranked = sorted(eligible, key=lambda row: to_float(row.get("benchmark_quality")) or 0.0, reverse=True)
    cost_ranked = sorted(
        [row for row in eligible if isinstance(row.get("mean_estimated_cost_usd"), (int, float))],
        key=lambda row: (
            -(to_float(row.get("benchmark_quality")) or 0.0),
            to_float(row.get("mean_estimated_cost_usd")) or float("inf"),
        ),
    )
    best_quality = quality_ranked[0] if quality_ranked else None
    best_cost_effective = cost_ranked[0] if cost_ranked else None
    selected = []
    for row in [best_quality, best_cost_effective]:
        if row and row["condition"] not in selected:
            selected.append(row["condition"])
    return {
        "split": split,
        "held_out_test_used": split == "test",
        "eligible_conditions": [row["condition"] for row in eligible],
        "quality_rank_order": [row["condition"] for row in quality_ranked],
        "selected_final_candidates": selected[:2],
        "best_quality_candidate": best_quality["condition"] if best_quality else None,
        "best_cost_effective_candidate": best_cost_effective["condition"] if best_cost_effective else None,
        "decision": "select_final_candidates" if selected else "no_candidate_selected",
        "notes": [
            "Candidates require positive benchmark quality plus schema and quote validity gates.",
            "Relaxed harnesses without canonical projection are excluded from final-candidate selection.",
        ],
    }


def command_stage_c(args: argparse.Namespace) -> int:
    all_scores: dict[str, list[dict[str, Any]]] = {}
    metadata: dict[str, dict[str, Any]] = {}
    model_specs = load_model_specs(Path(args.registry))
    if args.stage_a_dir:
        stage_scores, stage_metadata = score_stage_a_outputs(
            Path(args.stage_a_dir),
            Path(args.exect_root),
            Path(args.markup_root),
            Path(args.schema),
            set(args.harnesses) if args.harnesses else None,
        )
        all_scores.update(stage_scores)
        metadata.update(stage_metadata)

    eval_scores, eval_metadata = load_existing_evaluation_conditions(
        args.evaluation_condition,
        parse_condition_model(args.condition_model),
    )
    all_scores.update(eval_scores)
    metadata.update(eval_metadata)
    for meta in metadata.values():
        meta["model_specs"] = model_specs

    summaries_by_label = {
        label: summarize_condition(label, scores, metadata[label])
        for label, scores in all_scores.items()
        if scores
    }
    summaries = list(summaries_by_label.values())
    output_dir = Path(args.output_dir)
    write_csv(output_dir / "model_harness_table.csv", summaries)
    write_csv(output_dir / "field_prf_table.csv", build_field_prf_table(all_scores))
    write_json(
        output_dir / "bootstrap_intervals.json",
        bootstrap_stage_c(all_scores, summaries_by_label, args.bootstrap_iterations, args.seed),
    )
    write_csv(output_dir / "cost_latency_table.csv", build_cost_latency_table(summaries, all_scores))
    decision = validation_decision(summaries, args.split)
    write_json(output_dir / "validation_decision.json", decision)
    write_json(output_dir / "strict_validation_decision.json", decision)
    write_json(
        output_dir / "stage_c_manifest.json",
        {
            "stage": "stage_c0_strict_validation",
            "split": args.split,
            "stage_a_dir": args.stage_a_dir,
            "evaluation_conditions": args.evaluation_condition or [],
            "conditions": sorted(all_scores),
            "outputs": {
                "model_harness_table": str(output_dir / "model_harness_table.csv"),
                "field_prf_table": str(output_dir / "field_prf_table.csv"),
                "bootstrap_intervals": str(output_dir / "bootstrap_intervals.json"),
                "cost_latency_table": str(output_dir / "cost_latency_table.csv"),
                "validation_decision": str(output_dir / "validation_decision.json"),
                "strict_validation_decision": str(output_dir / "strict_validation_decision.json"),
            },
        },
    )
    print(f"wrote Stage C0 strict validation matrix for {len(summaries)} scored conditions")
    return 0


def first_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        for item in value:
            result = first_value(item)
            if result:
                return result
        return None
    if isinstance(value, dict):
        for key in ["value", "name", "result", "text"]:
            result = first_value(value.get(key))
            if result:
                return result
        return None
    text = str(value).strip()
    if not text or text.lower() in {"not stated", "none", "null", "[]"}:
        return None
    return text


def value_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            if isinstance(item, str):
                items.extend(split_compact_list(item))
            else:
                nested = first_value(item)
                if nested:
                    items.append(nested)
        return [item for item in items if item and item.lower() not in {"not stated", "none", "null"}]
    if isinstance(value, dict):
        nested = first_value(value)
        return [nested] if nested else []
    return split_compact_list(str(value))


def split_compact_list(text: str) -> list[str]:
    cleaned = text.strip().strip("[]")
    if not cleaned or cleaned.lower() in {"not stated", "none", "null"}:
        return []
    parts = [cleaned]
    if ";" in cleaned:
        parts = cleaned.split(";")
    return [part.strip(" -\t\n\r,") for part in parts if part.strip(" -\t\n\r,")]


def benchmark_seizure_type(value: str | None) -> str | None:
    """Collapse relaxed seizure descriptions to the ExECT benchmark label space."""
    if not value:
        return None
    text = value.lower().replace("generalised", "generalized")
    text = text.replace("-", " ")
    text = re_sub(r"[^a-z0-9/ ]+", " ", text)
    text = re_sub(r"\s+", " ", text).strip()
    if not text or text in {"not stated", "none", "null"}:
        return None

    symptom_terms = [
        "aura",
        "warning",
        "unusual smell",
        "strange smell",
        "strange taste",
        "abdominal sensation",
        "epigastric",
    ]
    seizure_terms = ["seizure", "seizures", "fit", "fits", "convulsive", "convulsion"]
    if any(term in text for term in symptom_terms) and not any(term in text for term in seizure_terms):
        return None

    if any(term in text for term in ["dissociative", "nonepileptic", "non epileptic", "dizzy spell"]):
        return "unknown seizure type"
    if "secondary" in text and any(term in text for term in ["generalized", "convulsive", "tonic clonic"]):
        return "secondary generalized seizures"
    if "focal to bilateral" in text and "tonic clonic" in text:
        return "secondary generalized seizures"
    if "focal" in text or "partial" in text or "temporal" in text:
        return "focal seizure"
    if "complex partial" in text:
        return "focal seizure"
    if "tonic clonic" in text or "gtc" in text:
        return "generalized tonic clonic seizure"
    if "absence" in text:
        return "generalized absence seizure"
    if "myoclonic" in text:
        return "generalized myoclonic seizure"
    if "generalized seizure" in text or "generalized seizures" in text:
        return "generalized seizures"
    if text in {"seizure", "seizures", "fits"}:
        return "unknown seizure type"
    return value.strip()


def re_sub(pattern: str, replacement: str, text: str) -> str:
    import re

    return re.sub(pattern, replacement, text, flags=re.IGNORECASE)


def benchmark_seizure_types(values: list[str]) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for value in values:
        label = benchmark_seizure_type(value)
        if label and label not in seen:
            labels.append(label)
            seen.add(label)
    return labels


_NULL_VALUES = frozenset(["none", "nil", "n/a", "not stated", "not mentioned", "not reported", "unknown", "not applicable"])


def _split_list_value(value: str) -> list[str] | str:
    """Split comma/semicolon-separated values into a list; return as string if it's a single item."""
    if not value or value.lower() in _NULL_VALUES:
        return []
    parts = [v.strip() for v in value.replace(";", ",").split(",") if v.strip()]
    parts = [p for p in parts if p.lower() not in _NULL_VALUES]
    return parts if len(parts) > 1 else (parts[0] if parts else value)


_CANONICAL_KEY_ALIASES: dict[str, str] = {
    "medications": "medication_names",
    "medication": "medication_names",
    "medication names": "medication_names",
    "current medications": "medication_names",
    "current anti seizure medications": "medication_names",
    "anti seizure medications": "medication_names",
    "asms": "medication_names",
    "seizure types": "seizure_types",
    "seizure type": "seizure_types",
    "seizure semiology": "seizure_types",
    "seizures": "seizure_types",
    "epilepsy types": "epilepsy_types",
    "epilepsy type": "epilepsy_types",
    "epilepsy diagnosis": "epilepsy_types",
    "epilepsy diagnosis type": "epilepsy_types",
    "epilepsy_diagnosis_type": "epilepsy_types",
    "diagnosis": "epilepsy_types",
    "frequency": "seizure_frequency",
    "seizure frequency": "seizure_frequency",
    "current seizure frequency": "seizure_frequency",
}


_LIST_FIELDS = frozenset(["medication_names", "seizure_types"])


def _normalize_parsed_keys(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize non-canonical JSON keys to canonical field names and split list fields."""
    normalized: dict[str, Any] = {}
    for key, value in data.items():
        # Strip parenthetical qualifiers: "Medications (current)" → "medications"
        clean_key = key.lower().replace("_", " ").replace("-", " ").split("(")[0].strip()
        canon = _CANONICAL_KEY_ALIASES.get(clean_key, key)
        # Split comma-separated strings for list fields
        if canon in _LIST_FIELDS and isinstance(value, str):
            value = _split_list_value(value)
        normalized[canon] = value
    return normalized


def parse_loose_sections(text: str) -> dict[str, Any]:
    parsed = parse_json_response(text)
    if isinstance(parsed.data, dict):
        return _normalize_parsed_keys(parsed.data)
    sections: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = line.lstrip("-*•·0123456789. ").strip()
        line = line.replace("**", "").replace("__", "")
        if not line:
            continue
        if ":" not in line:
            if current_key:
                item = line.strip()
                if item and item.lower() not in _NULL_VALUES:
                    sections.setdefault(current_key, [])
                    if isinstance(sections[current_key], list):
                        sections[current_key].append(item)
            continue
        label, value = line.split(":", 1)
        # Strip parenthetical qualifiers from label: "Medications (current)" -> "medications"
        label_key = label.strip().lower().replace("-", " ").split("(")[0].strip()
        value = value.strip()
        target_key = None
        if "medication" in label_key or "anti seizure" in label_key or "anti-seizure" in label_key or "asm" in label_key:
            target_key = "medication_names"
        elif "seizure type" in label_key or "seizure semiology" in label_key:
            target_key = "seizure_types"
        elif "seizure" in label_key and "frequency" not in label_key and "type" not in label_key:
            target_key = "seizure_types"
        elif "epilepsy" in label_key or "diagnosis" in label_key or "syndrome" in label_key:
            target_key = "epilepsy_types"
        elif "frequency" in label_key or "seizure control" in label_key:
            target_key = "seizure_frequency"
        elif "eeg" in label_key or "electroencephalogram" in label_key:
            target_key = "eeg"
        elif "mri" in label_key or "magnetic resonance" in label_key:
            target_key = "mri"
        if not target_key:
            current_key = None
            continue
        current_key = target_key
        if value and value.lower() not in _NULL_VALUES:
            if target_key in {"medication_names", "seizure_types"}:
                sections[target_key] = _split_list_value(value)
            else:
                sections[target_key] = value
        else:
            sections.setdefault(target_key, [])
    return sections


def normalize_relaxed_payload(harness_id: str, text: str) -> tuple[dict[str, Any] | None, str | None]:
    parsed = parse_json_response(text)
    if harness_id == "H2_task_specific":
        if not isinstance(parsed.data, dict):
            return None, parsed.error or "H2 output did not parse as an object"
        return parsed.data, None
    if harness_id == "H3_loose_answer_then_parse":
        sections = parse_loose_sections(text)
        if not sections:
            return None, parsed.error or "H3 output did not contain parseable sections"
        return sections, None
    return None, f"unsupported relaxed harness: {harness_id}"


def medication_from_text(text: str) -> dict[str, Any]:
    dose_match = re_search(r"\b(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml)\b", text)
    frequency_match = re_search(r"\b(once daily|twice daily|three times daily|four times daily|bd|od|tds|qds|daily|nocte)\b", text)
    name = text
    if dose_match:
        name = text[: dose_match.start()].strip(" ,-")
    name = name.split("(")[0].strip(" ,-")
    return {
        "name": name or text,
        "dose": dose_match.group(1) if dose_match else None,
        "dose_unit": dose_match.group(2) if dose_match else None,
        "frequency": frequency_match.group(1) if frequency_match else None,
        "status": "current",
        "missingness": "present",
        "temporality": "current",
        "evidence": [],
        "evidence_event_ids": [],
    }


def re_search(pattern: str, text: str):
    import re

    return re.search(pattern, text, flags=re.IGNORECASE)


def scalar_field(value: str | None, temporality: str = "current") -> dict[str, Any]:
    return {
        "value": value,
        "missingness": "present" if value else "not_stated",
        "temporality": temporality if value else "uncertain",
        "evidence": [] if value else None,
        "evidence_event_ids": [],
    }


def investigation_field(value: str | None) -> dict[str, Any]:
    normalized = _canonical_inv(value)
    result = normalized if normalized in {"normal", "abnormal", "uncertain"} else "not_stated"
    status = "completed" if result in {"normal", "abnormal"} else "not_stated"
    return {
        "status": status,
        "result": result,
        "missingness": "present" if status == "completed" else "not_stated",
        "temporality": "completed" if status == "completed" else "uncertain",
        "evidence": [] if status == "completed" else None,
        "evidence_event_ids": [],
    }


def quote_value(item: Any) -> str | None:
    if isinstance(item, dict):
        for key in ["quote", "support", "evidence", "source_quote"]:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def named_items(value: Any, value_keys: list[str]) -> list[dict[str, str | None]]:
    if value is None:
        return []
    if isinstance(value, list):
        items: list[dict[str, str | None]] = []
        for item in value:
            items.extend(named_items(item, value_keys))
        return items
    if isinstance(value, dict):
        text = None
        for key in value_keys:
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                text = candidate.strip()
                break
        if text is None:
            text = first_value(value)
        return [{"value": text, "quote": quote_value(value)}] if text else []
    text = first_value(value)
    return [{"value": text, "quote": None}] if text else []


def d3_medication_items(payload: dict[str, Any]) -> list[dict[str, str | None]]:
    return named_items(
        payload.get("medication_names")
        or payload.get("current_anti_seizure_medications")
        or payload.get("current anti-seizure medications"),
        ["name", "value", "text", "medication"],
    )


def d3_seizure_items(payload: dict[str, Any]) -> list[dict[str, str | None]]:
    items = named_items(payload.get("seizure_types") or payload.get("seizure_type"), ["label", "benchmark_label", "value", "text"])
    for mapping in payload.get("verified_seizure_type_mappings") or []:
        if not isinstance(mapping, dict) or mapping.get("keep") is False:
            continue
        label = mapping.get("benchmark_label") or mapping.get("label")
        if isinstance(label, str) and label.strip():
            items.append({"value": label.strip(), "quote": quote_value(mapping)})
    deduped: list[dict[str, str | None]] = []
    seen: set[tuple[str | None, str | None]] = set()
    for item in items:
        key = (item.get("value"), item.get("quote"))
        if item.get("value") and key not in seen:
            deduped.append(item)
            seen.add(key)
    return deduped


def d3_epilepsy_item(payload: dict[str, Any]) -> dict[str, str | None]:
    raw = (
        payload.get("epilepsy_types")
        or payload.get("epilepsy_diagnosis")
        or payload.get("epilepsy_diagnosis_type")
        or payload.get("epilepsy diagnosis/type")
    )
    items = named_items(raw, ["label", "value", "text", "diagnosis"])
    return items[0] if items else {"value": None, "quote": None}


def evidence_from_quote(document: dict[str, Any] | None, quote: str | None) -> list[dict[str, Any]]:
    if not quote or not document:
        return []
    if normalize_text(quote) not in normalize_text(document["text"]):
        return []
    char_start = document["text"].find(quote)
    char_end = char_start + len(quote) if char_start >= 0 else None
    sentence_id = None
    if char_start >= 0 and char_end is not None:
        for sentence in document.get("sentences", []):
            if sentence["char_start"] <= char_start and char_end <= sentence["char_end"]:
                sentence_id = sentence["sentence_id"]
                break
    return [
        {
            "quote": quote,
            "sentence_id": sentence_id,
            "char_start": char_start if char_start >= 0 else None,
            "char_end": char_end,
        }
    ]


def medication_from_item(item: dict[str, str | None], document: dict[str, Any] | None) -> dict[str, Any]:
    field = medication_from_text(str(item["value"]))
    field["evidence"] = evidence_from_quote(document, item.get("quote"))
    return field


def scalar_field_with_evidence(value: str | None, quote: str | None, document: dict[str, Any] | None, temporality: str = "current") -> dict[str, Any]:
    field = scalar_field(value, temporality)
    if value:
        field["evidence"] = evidence_from_quote(document, quote)
    return field


def projected_canonical(
    document_id: str,
    harness_id: str,
    model_label: str,
    payload: dict[str, Any],
    row: dict[str, str],
    document: dict[str, Any] | None = None,
    require_present_evidence: bool = False,
) -> dict[str, Any]:
    return _core_projected_canonical(
        document_id,
        harness_id,
        model_label,
        payload,
        row,
        document,
        require_present_evidence,
    )
    use_evidence_items = harness_id in {"D3_candidate_plus_verifier", "H7_extract_then_normalize"}
    # H6full outputs structured medication objects; all other harnesses use name strings.
    _raw_meds = payload.get("medications")
    _has_structured_meds = (
        isinstance(_raw_meds, list)
        and any(isinstance(m, dict) and m.get("name") for m in _raw_meds)
    )
    if _has_structured_meds:
        medication_items = [
            {"value": m["name"], "_structured": m, "quote": m.get("quote")}
            for m in _raw_meds
            if isinstance(m, dict) and m.get("name")
        ]
    elif use_evidence_items:
        medication_items = d3_medication_items(payload)
    else:
        medication_items = [
            {"value": item, "quote": None}
            for item in value_list(
                payload.get("medication_names")
                or payload.get("current_anti_seizure_medications")
                or payload.get("current anti-seizure medications")
            )
        ]
    raw_seizure_items = d3_seizure_items(payload) if use_evidence_items else [
        {"value": item, "quote": None}
        for item in value_list(payload.get("seizure_types") or payload.get("seizure_type"))
    ]
    seizure_items: list[dict[str, str | None]] = []
    seen_seizure_labels: set[str] = set()
    for item in raw_seizure_items:
        label = benchmark_seizure_type(item.get("value"))
        if label and label not in seen_seizure_labels:
            seizure_items.append({"value": label, "quote": item.get("quote")})
            seen_seizure_labels.add(label)
    epilepsy_item = d3_epilepsy_item(payload) if use_evidence_items else {
        "value": first_value(
            payload.get("epilepsy_types")
            or payload.get("epilepsy_diagnosis")
            or payload.get("epilepsy_diagnosis_type")
            or payload.get("epilepsy diagnosis/type")
        ),
        "quote": None,
    }
    seizure_types = [str(item["value"]) for item in seizure_items if item.get("value")]
    epilepsy = epilepsy_item.get("value")
    if use_evidence_items and require_present_evidence:
        medication_items = [
            item for item in medication_items if item.get("value") and evidence_from_quote(document, item.get("quote"))
        ]
        seizure_items = [
            item for item in seizure_items if item.get("value") and evidence_from_quote(document, item.get("quote"))
        ]
        seizure_types = [str(item["value"]) for item in seizure_items if item.get("value")]
        if epilepsy and not evidence_from_quote(document, epilepsy_item.get("quote")):
            epilepsy = None
            epilepsy_item = {"value": None, "quote": None}
    frequency = first_value(payload.get("seizure_frequency") or payload.get("current_seizure_frequency"))
    # H6full outputs investigations as a dict {"eeg": ..., "mri": ...}; other harnesses use a list.
    _inv_payload = payload.get("investigations")
    if isinstance(_inv_payload, dict):
        eeg = first_value(_inv_payload.get("eeg") or payload.get("eeg") or payload.get("EEG_result"))
        mri = first_value(_inv_payload.get("mri") or payload.get("mri") or payload.get("MRI_result"))
    else:
        investigations = value_list(_inv_payload)
        eeg = first_value(payload.get("eeg") or payload.get("EEG_result"))
        mri = first_value(payload.get("mri") or payload.get("MRI_result"))
        for item in investigations:
            lowered = item.lower()
            if "eeg" in lowered and not eeg:
                eeg = item
            if ("mri" in lowered or "magnetic resonance" in lowered) and not mri:
                mri = item

    def _build_med(item: dict[str, Any]) -> dict[str, Any]:
        if "_structured" in item:
            m = item["_structured"]
            result = {
                "name": m.get("name") or "",
                "dose": str(m["dose"]) if m.get("dose") is not None else None,
                "dose_unit": str(m.get("unit") or m.get("dose_unit") or "") or None,
                "frequency": str(m["frequency"]) if m.get("frequency") else None,
                "status": "current",
                "missingness": "present",
                "temporality": "current",
                "evidence": [],
                "evidence_event_ids": [],
            }
            quote = item.get("quote") or m.get("quote")
            if quote:
                result["evidence"] = evidence_from_quote(document, quote)
            return result
        return medication_from_item(item, document)

    return {
        "document_id": document_id,
        "pipeline_id": f"{system_for_harness(harness_id)}_{'evidence_projection' if use_evidence_items else 'relaxed_projection'}",
        "fields": {
            "current_anti_seizure_medications": [
                _build_med(item) for item in medication_items if item.get("value")
            ],
            "previous_anti_seizure_medications": [],
            "current_seizure_frequency": {
                **scalar_field(frequency),
                "temporal_scope": "current" if frequency else None,
                "seizure_type": seizure_types[0] if seizure_types else None,
            },
            "seizure_types": [
                scalar_field_with_evidence(str(item["value"]), item.get("quote"), document)
                for item in seizure_items
                if item.get("value")
            ],
            "eeg": investigation_field(eeg),
            "mri": investigation_field(mri),
            "epilepsy_diagnosis": scalar_field_with_evidence(
                str(epilepsy) if epilepsy else None,
                epilepsy_item.get("quote"),
                document,
            ),
        },
        "events": [],
        "metadata": {
            "model": row.get("provider_model_id") or model_label,
            "model_label": model_label,
            "harness_id": harness_id,
            "format": "unknown",
            "projection": RELAXED_PROJECTION_VERSION,
            "latency_ms": to_float(row.get("latency_ms")),
            "input_tokens": int(to_float(row.get("input_tokens")) or 0),
            "output_tokens": int(to_float(row.get("output_tokens")) or 0),
            "estimated_cost_usd": to_float(row.get("estimated_cost")),
        },
    }


def relaxed_projection_report(summaries: list[dict[str, Any]], projection_rows: list[dict[str, Any]], split: str) -> str:
    projected = sum(1 for row in projection_rows if row["projection_success"])
    total = len(projection_rows)
    lines = [
        "# Stage C1 Relaxed-Projection Report",
        "",
        f"Split: `{split}`",
        "",
        "## Projection Status",
        "",
        f"- Projected documents: {projected}/{total}",
        f"- Projection version: `{RELAXED_PROJECTION_VERSION}`",
        "- Seizure-type projection collapses focal semiology to `focal seizure`, maps secondary generalized convulsive wording to `secondary generalized seizures`, and drops aura-only symptom phrases.",
        "- Evidence quotes are not reconstructed; benchmark field scores are comparable, but strict evidence metrics are intentionally degraded.",
        "",
        "## Scored Conditions",
        "",
    ]
    for row in summaries:
        lines.append(
            "- "
            + f"`{row['condition']}`: quality={to_float(row.get('benchmark_quality')) or 0.0:.4f}, "
            + f"projection_schema_valid={to_float(row.get('projection_schema_valid_rate')) or 0.0:.2f}, "
            + f"docs={row.get('documents_available')}"
        )
    failures = [row for row in projection_rows if not row["projection_success"]]
    if failures:
        lines.extend(["", "## Failures", ""])
        for row in failures[:20]:
            lines.append(f"- `{row['model_label']}` / `{row['harness_id']}` / `{row['document_id']}`: {row['projection_error']}")
    return "\n".join(lines) + "\n"


def command_stage_c1(args: argparse.Namespace) -> int:
    stage_a_dir = Path(args.stage_a_dir)
    rows = read_csv(stage_a_dir / "provider_call_report.csv")
    selected_harnesses = set(args.harnesses or ["H2_task_specific", "H3_loose_answer_then_parse"])
    selected_models = set(args.models or [])
    gold = load_gold(Path(args.markup_root), Path(args.exect_root))
    output_dir = Path(args.output_dir)
    all_scores: dict[str, list[dict[str, Any]]] = {}
    metadata: dict[str, dict[str, Any]] = {}
    projection_rows: list[dict[str, Any]] = []

    for row in rows:
        harness_id = row.get("harness_id", "")
        model_label = row.get("model_label", "")
        if harness_id not in selected_harnesses:
            continue
        if selected_models and model_label not in selected_models:
            continue
        document_id = row["document_id"]
        label = condition_label(model_label, harness_id, system_for_harness(harness_id))
        metadata.setdefault(
            label,
            {
                "model_label": model_label,
                "provider": row.get("provider"),
                "provider_model_id": row.get("provider_model_id"),
                "system": system_for_harness(harness_id),
                "harness_id": harness_id,
                "source": "relaxed_projection",
                "call_rows": [],
                "projection_schema_valid": 0,
                "projection_count": 0,
            },
        )
        metadata[label]["call_rows"].append(row)
        raw_path = resolve_report_path(stage_a_dir, row, "raw_response_path")
        text = raw_path.read_text(encoding="utf-8") if raw_path and raw_path.exists() else ""
        payload, error = normalize_relaxed_payload(harness_id, text)
        projection_success = payload is not None and row.get("status") == "success"
        projection_path = output_dir / "projections" / model_label / harness_id / document_id / "canonical_projection.json"
        projected = projected_canonical(document_id, harness_id, model_label, payload or {}, row) if projection_success else None
        projection_schema_valid = False
        if projected is not None:
            try:
                validate_extraction(projected, Path(args.schema), require_present_evidence=False)
                projection_schema_valid = True
            except Exception as exc:
                error = str(exc)
            write_json(projection_path, projected)
            source_text = preprocess_document(document_id, Path(args.exect_root))["text"]
            score = score_document(projected, source_text, gold.get(document_id, GoldDocument(document_id=document_id)), Path(args.schema))
            score["document_id"] = document_id
            score["system"] = label
            all_scores.setdefault(label, []).append(score)
        metadata[label]["projection_count"] += 1
        metadata[label]["projection_schema_valid"] += 1 if projection_schema_valid else 0
        projection_rows.append(
            {
                "model_label": model_label,
                "provider": row.get("provider"),
                "provider_model_id": row.get("provider_model_id"),
                "harness_id": harness_id,
                "document_id": document_id,
                "call_status": row.get("status"),
                "projection_success": projection_success,
                "projection_schema_valid": projection_schema_valid,
                "projection_error": error,
                "projection_path": str(projection_path) if projected is not None else None,
            }
        )

    summaries = []
    for label, scores in sorted(all_scores.items()):
        summary = summarize_condition(label, scores, metadata[label])
        projection_count = metadata[label]["projection_count"]
        summary["projection_success_rate"] = len(scores) / projection_count if projection_count else 0.0
        summary["projection_schema_valid_rate"] = metadata[label]["projection_schema_valid"] / projection_count if projection_count else 0.0
        summaries.append(summary)

    write_csv(output_dir / "model_harness_table.csv", summaries)
    write_csv(output_dir / "projection_rows.csv", projection_rows)
    write_csv(output_dir / "field_prf_table.csv", build_field_prf_table(all_scores))
    write_csv(output_dir / "cost_latency_table.csv", build_cost_latency_table(summaries, all_scores))
    (output_dir / "projection_report.md").parent.mkdir(parents=True, exist_ok=True)
    (output_dir / "projection_report.md").write_text(
        relaxed_projection_report(summaries, projection_rows, args.split),
        encoding="utf-8",
    )
    write_json(
        output_dir / "relaxed_validation_decision.json",
        {
            "split": args.split,
            "decision": "projection_ready_for_review" if summaries else "no_relaxed_projection_outputs",
            "conditions": [row["condition"] for row in summaries],
            "notes": [
                "Projected relaxed outputs are benchmark-scoreable but do not reconstruct evidence quotes.",
                "Use Stage C0 strict validation for final candidate selection until evidence audit policy is chosen.",
            ],
        },
    )
    write_json(
        output_dir / "stage_c1_manifest.json",
        {
            "stage": "stage_c1_relaxed_projection",
            "split": args.split,
            "stage_a_dir": str(stage_a_dir),
            "harnesses": sorted(selected_harnesses),
            "models": sorted(selected_models) if selected_models else "all",
            "outputs": {
                "projection_report": str(output_dir / "projection_report.md"),
                "model_harness_table": str(output_dir / "model_harness_table.csv"),
                "projection_rows": str(output_dir / "projection_rows.csv"),
                "field_prf_table": str(output_dir / "field_prf_table.csv"),
                "cost_latency_table": str(output_dir / "cost_latency_table.csv"),
                "relaxed_validation_decision": str(output_dir / "relaxed_validation_decision.json"),
            },
        },
    )
    print(f"wrote Stage C1 relaxed projection for {len(summaries)} scored conditions")
    return 0


def diagnostic_report(summaries: list[dict[str, Any]], projection_rows: list[dict[str, Any]], split: str) -> str:
    harnesses = {row.get("harness_id") for row in summaries}
    lines = [
        "# Harness Diagnostic Report",
        "",
        f"Split: `{split}`",
        "",
        "## Purpose",
        "",
    ]
    if "H4_provider_native_structured_output" in harnesses:
        lines.append("- H4 tests provider-native structured output for benchmark-only fields.")
    if "H6_benchmark_only_coarse_json" in harnesses:
        lines.append("- H6 tests direct benchmark-only JSON extraction with coarse allowed labels.")
    if "H7_extract_then_normalize" in harnesses:
        lines.append("- H7 tests rich extraction followed by model-based benchmark normalization.")
    if "H8_evidence_later" in harnesses:
        lines.append("- H8 tests quote-free field extraction first, with evidence requested only after candidate fields are selected.")
    if "D3_candidate_plus_verifier" in harnesses:
        lines.append("- D3 tests permissive candidate extraction followed by verifier pruning of unsupported or non-benchmark labels.")
    lines.append("- Benchmark scores are computed from projected field values; H8 evidence-pass outputs are retained in call logs for audit.")
    lines.extend(["", "## Scored Conditions", ""])
    for row in summaries:
        lines.append(
            "- "
            + f"`{row['condition']}`: quality={to_float(row.get('benchmark_quality')) or 0.0:.4f}, "
            + f"med_f1={to_float(row.get('medication_name_f1')) or 0.0:.4f}, "
            + f"seizure_f1={to_float(row.get('seizure_type_f1')) or 0.0:.4f}, "
            + f"diagnosis_acc={to_float(row.get('epilepsy_diagnosis_accuracy')) or 0.0:.4f}, "
            + f"docs={row.get('documents_available')}"
        )
    failures = [row for row in projection_rows if not row["projection_success"]]
    if failures:
        lines.extend(["", "## Failures", ""])
        for row in failures[:30]:
            lines.append(f"- `{row['model_label']}` / `{row['harness_id']}` / `{row['document_id']}`: {row['projection_error']}")
    return "\n".join(lines) + "\n"


def combined_usage(responses: list[Any]) -> TokenUsage:
    return TokenUsage(
        input_tokens=sum(int(response.token_usage.input_tokens or 0) for response in responses),
        output_tokens=sum(int(response.token_usage.output_tokens or 0) for response in responses),
        cache_read_tokens=sum(int(response.token_usage.cache_read_tokens or 0) for response in responses),
        cache_write_tokens=sum(int(response.token_usage.cache_write_tokens or 0) for response in responses),
    )


def combined_cost(responses: list[Any]) -> float | None:
    values = [response.estimated_cost.get("total") for response in responses]
    numeric = [value for value in values if isinstance(value, (int, float))]
    return sum(numeric) if numeric else None


def diagnostic_row(
    spec: Any,
    adapter: Any,
    harness_id: str,
    document_id: str,
    responses: list[Any],
    parse_success: bool,
    parse_error: str | None,
    output_path: Path | None,
) -> dict[str, Any]:
    first = responses[0]
    usage = combined_usage(responses)
    errors = [response.error for response in responses if response.error]
    return {
        "model_label": spec.label,
        "provider": spec.provider,
        "called_provider": adapter.provider,
        "provider_model_id": spec.provider_model_id,
        "harness_id": harness_id,
        "document_id": document_id,
        "status": "success" if not errors else "unavailable",
        "error": "; ".join(errors),
        "stop_reason": responses[-1].stop_reason,
        "raw_response_path": str(output_path) if output_path else None,
        "parse_success": str(parse_success),
        "repair_attempted": "False",
        "repair_succeeded": "False",
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_read_tokens": usage.cache_read_tokens,
        "cache_write_tokens": usage.cache_write_tokens,
        "latency_ms": round(sum(response.latency_ms for response in responses), 3),
        "retries": sum(response.retries for response in responses),
        "estimated_cost": combined_cost(responses),
        "cost_status": "complete" if combined_cost(responses) is not None else first.estimated_cost.get("status"),
        "pricing_snapshot_date": first.estimated_cost.get("pricing_snapshot_date"),
        "parse_error": parse_error,
    }


def metadata_row_for_projection(row: dict[str, Any]) -> dict[str, str]:
    return {key: "" if value is None else str(value) for key, value in row.items()}


def run_h6_h7_one(
    args: argparse.Namespace,
    spec: Any,
    adapter: Any,
    harness_id: str,
    document_id: str,
    document: dict[str, Any],
    output_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any] | None, str | None]:
    google_thinking_budget = getattr(args, "google_thinking_budget", None)
    run_root = output_dir / "calls" / spec.label / harness_id / document_id
    run_root.mkdir(parents=True, exist_ok=True)
    if harness_id in {"H6_benchmark_only_coarse_json", "H4_provider_native_structured_output"}:
        prompt = build_h6_prompt(document, harness_id)
        write_text(run_root / "prompt.txt", prompt)
        request = ModelRequest(
            prompt=prompt,
            model=spec,
            harness_id=harness_id,
            temperature=args.temperature if args.temperature is not None else spec.temperature,
            max_output_tokens=args.max_output_tokens or min(spec.max_output_tokens or 4096, 4096),
            schema_mode="json_schema" if harness_id == "H4_provider_native_structured_output" else None,
            response_json_schema=benchmark_output_schema()
            if harness_id == "H4_provider_native_structured_output"
            else None,
            reasoning_effort=args.reasoning_effort,
            google_thinking_budget=google_thinking_budget,
            metadata={"document_id": document_id, "stage": "h6_h7_clean_diagnostic"},
        )
        response = adapter.call(request)
        write_text(run_root / "raw_response.txt", response.text)
        response.raw_response_path = str(run_root / "raw_response.txt")
        write_response_log(response, run_root / "provider_response.json")
        parsed = parse_json_response(response.text)
        payload = parsed.data if isinstance(parsed.data, dict) and not response.error else None
        row = diagnostic_row(spec, adapter, harness_id, document_id, [response], payload is not None, parsed.error, run_root / "raw_response.txt")
        return row, payload, parsed.error

    if harness_id == "H8_evidence_later":
        extract_prompt = build_h6_prompt(document, harness_id)
        write_text(run_root / "extract_prompt.txt", extract_prompt)
        extract_request = ModelRequest(
            prompt=extract_prompt,
            model=spec,
            harness_id=f"{harness_id}:extract",
            temperature=args.temperature if args.temperature is not None else spec.temperature,
            max_output_tokens=args.max_output_tokens or min(spec.max_output_tokens or 4096, 4096),
            reasoning_effort=args.reasoning_effort,
            google_thinking_budget=google_thinking_budget,
            metadata={"document_id": document_id, "stage": "h4_h8_d3_clean_diagnostic", "pass": "extract"},
        )
        extract_response = adapter.call(extract_request)
        write_text(run_root / "extract_raw_response.txt", extract_response.text)
        write_response_log(extract_response, run_root / "extract_provider_response.json")
        parsed_extract = parse_json_response(extract_response.text)
        candidate_text = json.dumps(parsed_extract.data, indent=2) if isinstance(parsed_extract.data, dict) else extract_response.text
        evidence_prompt = build_h8_evidence_prompt(document, harness_id, candidate_text)
        write_text(run_root / "evidence_prompt.txt", evidence_prompt)
        evidence_request = ModelRequest(
            prompt=evidence_prompt,
            model=spec,
            harness_id=f"{harness_id}:evidence",
            temperature=args.temperature if args.temperature is not None else spec.temperature,
            max_output_tokens=args.max_output_tokens or min(spec.max_output_tokens or 4096, 4096),
            reasoning_effort=args.reasoning_effort,
            google_thinking_budget=google_thinking_budget,
            metadata={"document_id": document_id, "stage": "h4_h8_d3_clean_diagnostic", "pass": "evidence"},
        )
        evidence_response = adapter.call(evidence_request)
        write_text(run_root / "raw_response.txt", evidence_response.text)
        write_response_log(evidence_response, run_root / "evidence_provider_response.json")
        payload = parsed_extract.data if isinstance(parsed_extract.data, dict) and not extract_response.error and not evidence_response.error else None
        row = diagnostic_row(
            spec,
            adapter,
            harness_id,
            document_id,
            [extract_response, evidence_response],
            payload is not None,
            parsed_extract.error,
            run_root / "raw_response.txt",
        )
        return row, payload, parsed_extract.error

    if harness_id == "D3_candidate_plus_verifier":
        candidate_prompt = build_d3_candidate_prompt(document, harness_id)
        write_text(run_root / "candidate_prompt.txt", candidate_prompt)
        candidate_request = ModelRequest(
            prompt=candidate_prompt,
            model=spec,
            harness_id=f"{harness_id}:candidate",
            temperature=args.temperature if args.temperature is not None else spec.temperature,
            max_output_tokens=args.max_output_tokens or min(spec.max_output_tokens or 4096, 4096),
            reasoning_effort=args.reasoning_effort,
            google_thinking_budget=google_thinking_budget,
            metadata={"document_id": document_id, "stage": "h4_h8_d3_clean_diagnostic", "pass": "candidate"},
        )
        candidate_response = adapter.call(candidate_request)
        write_text(run_root / "candidate_raw_response.txt", candidate_response.text)
        write_response_log(candidate_response, run_root / "candidate_provider_response.json")
        verifier_prompt = build_d3_verifier_prompt(document, harness_id, candidate_response.text)
        write_text(run_root / "verifier_prompt.txt", verifier_prompt)
        verifier_request = ModelRequest(
            prompt=verifier_prompt,
            model=spec,
            harness_id=f"{harness_id}:verifier",
            temperature=args.temperature if args.temperature is not None else spec.temperature,
            max_output_tokens=args.max_output_tokens or min(spec.max_output_tokens or 4096, 4096),
            reasoning_effort=args.reasoning_effort,
            google_thinking_budget=google_thinking_budget,
            metadata={"document_id": document_id, "stage": "h4_h8_d3_clean_diagnostic", "pass": "verifier"},
        )
        verifier_response = adapter.call(verifier_request)
        write_text(run_root / "raw_response.txt", verifier_response.text)
        write_response_log(verifier_response, run_root / "verifier_provider_response.json")
        parsed = parse_json_response(verifier_response.text)
        payload = parsed.data if isinstance(parsed.data, dict) and not candidate_response.error and not verifier_response.error else None
        row = diagnostic_row(
            spec,
            adapter,
            harness_id,
            document_id,
            [candidate_response, verifier_response],
            payload is not None,
            parsed.error,
            run_root / "raw_response.txt",
        )
        return row, payload, parsed.error

    if harness_id == "H7_extract_then_normalize":
        extract_prompt = build_h7_extract_prompt(document, harness_id)
        write_text(run_root / "extract_prompt.txt", extract_prompt)
        extract_request = ModelRequest(
            prompt=extract_prompt,
            model=spec,
            harness_id=f"{harness_id}:extract",
            temperature=args.temperature if args.temperature is not None else spec.temperature,
            max_output_tokens=args.max_output_tokens or min(spec.max_output_tokens or 4096, 4096),
            reasoning_effort=args.reasoning_effort,
            google_thinking_budget=google_thinking_budget,
            metadata={"document_id": document_id, "stage": "h6_h7_clean_diagnostic", "pass": "extract"},
        )
        extract_response = adapter.call(extract_request)
        write_text(run_root / "extract_raw_response.txt", extract_response.text)
        extract_response.raw_response_path = str(run_root / "extract_raw_response.txt")
        write_response_log(extract_response, run_root / "extract_provider_response.json")

        normalize_prompt = build_h7_normalize_prompt(document, harness_id, extract_response.text)
        write_text(run_root / "normalize_prompt.txt", normalize_prompt)
        normalize_request = ModelRequest(
            prompt=normalize_prompt,
            model=spec,
            harness_id=f"{harness_id}:normalize",
            temperature=args.temperature if args.temperature is not None else spec.temperature,
            max_output_tokens=args.max_output_tokens or min(spec.max_output_tokens or 4096, 4096),
            reasoning_effort=args.reasoning_effort,
            google_thinking_budget=google_thinking_budget,
            metadata={"document_id": document_id, "stage": "h6_h7_clean_diagnostic", "pass": "normalize"},
        )
        normalize_response = adapter.call(normalize_request)
        write_text(run_root / "raw_response.txt", normalize_response.text)
        normalize_response.raw_response_path = str(run_root / "raw_response.txt")
        write_response_log(normalize_response, run_root / "normalize_provider_response.json")
        parsed = parse_json_response(normalize_response.text)
        payload = parsed.data if isinstance(parsed.data, dict) and not extract_response.error and not normalize_response.error else None
        row = diagnostic_row(
            spec,
            adapter,
            harness_id,
            document_id,
            [extract_response, normalize_response],
            payload is not None,
            parsed.error,
            run_root / "raw_response.txt",
        )
        return row, payload, parsed.error

    raise ValueError(f"unsupported diagnostic harness: {harness_id}")


def command_h6_h7_diagnostic(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    specs = load_model_specs(Path(args.registry))
    model_labels = args.models or ["gpt_4_1_mini_baseline", "gpt_5_4_mini", "gpt_5_5"]
    harness_ids = args.harnesses or ["H6_benchmark_only_coarse_json", "H7_extract_then_normalize"]
    document_ids = load_split_ids(Path(args.splits), args.split, args.limit)
    gold = load_gold(Path(args.markup_root), Path(args.exect_root))
    all_scores: dict[str, list[dict[str, Any]]] = {}
    metadata: dict[str, dict[str, Any]] = {}
    call_rows: list[dict[str, Any]] = []
    projection_rows: list[dict[str, Any]] = []

    for model_label in model_labels:
        if model_label not in specs:
            raise ValueError(f"unknown model label: {model_label}")
        spec = specs[model_label]
        adapter = adapter_for(provider_for_args(spec.provider, args.stub_calls))
        for harness_id in harness_ids:
            for document_id in document_ids:
                document = preprocess_document(document_id, Path(args.exect_root))
                row, payload, error = run_h6_h7_one(args, spec, adapter, harness_id, document_id, document, output_dir)
                call_rows.append(row)
                projection_success = payload is not None and row["status"] == "success"
                label = condition_label(model_label, harness_id, system_for_harness(harness_id))
                metadata.setdefault(
                    label,
                    {
                        "model_label": model_label,
                        "provider": spec.provider,
                        "provider_model_id": spec.provider_model_id,
                        "system": system_for_harness(harness_id),
                        "harness_id": harness_id,
                        "source": "h6_h7_clean_diagnostic",
                        "call_rows": [],
                        "projection_schema_valid": 0,
                        "projection_count": 0,
                    },
                )
                metadata[label]["call_rows"].append(metadata_row_for_projection(row))
                metadata[label]["projection_count"] += 1
                projection_path = output_dir / "projections" / model_label / harness_id / document_id / "canonical_projection.json"
                projected = (
                    projected_canonical(
                        document_id,
                        harness_id,
                        model_label,
                        payload or {},
                        metadata_row_for_projection(row),
                        document,
                        require_present_evidence=args.require_present_evidence_for_projection,
                    )
                    if projection_success
                    else None
                )
                projection_schema_valid = False
                projection_error = error
                if projected is not None:
                    try:
                        validate_extraction(
                            projected,
                            Path(args.schema),
                            require_present_evidence=args.require_present_evidence_for_projection,
                        )
                        projection_schema_valid = True
                    except Exception as exc:
                        projection_error = str(exc)
                    write_json(projection_path, projected)
                    score = score_document(projected, document["text"], gold.get(document_id, GoldDocument(document_id=document_id)), Path(args.schema))
                    score["document_id"] = document_id
                    score["system"] = label
                    all_scores.setdefault(label, []).append(score)
                metadata[label]["projection_schema_valid"] += 1 if projection_schema_valid else 0
                projection_rows.append(
                    {
                        "model_label": model_label,
                        "provider": spec.provider,
                        "provider_model_id": spec.provider_model_id,
                        "harness_id": harness_id,
                        "document_id": document_id,
                        "call_status": row["status"],
                        "projection_success": projection_success,
                        "projection_schema_valid": projection_schema_valid,
                        "projection_error": projection_error,
                        "projection_path": str(projection_path) if projected is not None else None,
                    }
                )
                print(f"{row['status']}: {model_label} {harness_id} {document_id}", flush=True)

    summaries = []
    for label, scores in sorted(all_scores.items()):
        summary = summarize_condition(label, scores, metadata[label])
        projection_count = metadata[label]["projection_count"]
        summary["projection_success_rate"] = len(scores) / projection_count if projection_count else 0.0
        summary["projection_schema_valid_rate"] = metadata[label]["projection_schema_valid"] / projection_count if projection_count else 0.0
        summaries.append(summary)

    write_csv(output_dir / "provider_call_report.csv", call_rows)
    write_csv(output_dir / "projection_rows.csv", projection_rows)
    write_csv(output_dir / "model_harness_table.csv", summaries)
    write_csv(output_dir / "field_prf_table.csv", build_field_prf_table(all_scores))
    write_csv(output_dir / "cost_latency_table.csv", build_cost_latency_table(summaries, all_scores))
    (output_dir / "diagnostic_report.md").parent.mkdir(parents=True, exist_ok=True)
    (output_dir / "diagnostic_report.md").write_text(diagnostic_report(summaries, projection_rows, args.split), encoding="utf-8")
    write_json(
        output_dir / "stage_d_manifest.json",
        {
            "stage": "h6_h7_clean_diagnostic",
            "split": args.split,
            "document_ids": document_ids,
            "models": model_labels,
            "harnesses": harness_ids,
            "outputs": {
                "diagnostic_report": str(output_dir / "diagnostic_report.md"),
                "model_harness_table": str(output_dir / "model_harness_table.csv"),
                "field_prf_table": str(output_dir / "field_prf_table.csv"),
                "projection_rows": str(output_dir / "projection_rows.csv"),
                "provider_call_report": str(output_dir / "provider_call_report.csv"),
            },
        },
    )
    print(f"wrote H6/H7 clean diagnostic for {len(summaries)} scored conditions")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    stage_a = subparsers.add_parser("stage-a-smoke", help="Run the Stage A provider and harness smoke matrix.")
    stage_a.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    stage_a.add_argument("--harness-matrix", default=str(DEFAULT_HARNESS_MATRIX))
    stage_a.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    stage_a.add_argument("--splits", default=str(DEFAULT_SPLITS))
    stage_a.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    stage_a.add_argument("--split", default="development", choices=["development", "validation", "test"])
    stage_a.add_argument("--limit", type=int, default=2)
    stage_a.add_argument("--models", nargs="+")
    stage_a.add_argument("--harnesses", nargs="+")
    stage_a.add_argument("--temperature", type=float)
    stage_a.add_argument("--max-output-tokens", type=int)
    stage_a.add_argument(
        "--reasoning-effort",
        choices=["minimal", "low", "medium", "high"],
        help="OpenAI reasoning effort for reasoning models; use low/minimal for extraction smoke runs.",
    )
    stage_a.add_argument(
        "--google-thinking-budget",
        type=int,
        help="Google thinking token budget. Use 0 or a small value for extraction smoke runs.",
    )
    stage_a.add_argument("--stub-calls", action="store_true", help="Exercise logging without paid provider calls.")
    stage_a.add_argument("--allow-unavailable", action="store_true", help="Exit zero even if providers are unavailable.")
    stage_a.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    stage_a.set_defaults(func=command_stage_a)

    stage_b = subparsers.add_parser(
        "stage-b-dev-pilot",
        help="Summarize a Stage A/dev-pilot run into comparison, frontier, and promotion artifacts.",
    )
    stage_b.add_argument("--stage-a-dir", default=str(DEFAULT_OUTPUT_DIR))
    stage_b.add_argument("--output-dir", default=str(DEFAULT_STAGE_B_OUTPUT_DIR))
    stage_b.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    stage_b.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    stage_b.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    stage_b.add_argument("--split", default="development", choices=["development", "validation", "test"])
    stage_b.set_defaults(func=command_stage_b)

    stage_c = subparsers.add_parser(
        "stage-c-validation",
        aliases=["stage-c0-strict-validation"],
        help="Build Stage C0 strict validation tables and candidate decision from scored validation artifacts.",
    )
    stage_c.add_argument("--stage-a-dir", help="Stage A-style validation run directory to score canonical H0 outputs.")
    stage_c.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    stage_c.add_argument(
        "--evaluation-condition",
        action="append",
        help="Existing evaluation condition as LABEL:SYSTEM:HARNESS_ID:EVALUATION_DIR.",
    )
    stage_c.add_argument(
        "--condition-model",
        action="append",
        help="Map an evaluation condition to a registry model label, as CONDITION=REGISTRY_MODEL_LABEL.",
    )
    stage_c.add_argument("--harnesses", nargs="+")
    stage_c.add_argument("--output-dir", default=str(DEFAULT_STAGE_C_OUTPUT_DIR))
    stage_c.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    stage_c.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    stage_c.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    stage_c.add_argument("--split", default="validation", choices=["development", "validation", "test"])
    stage_c.add_argument("--bootstrap-iterations", type=int, default=1000)
    stage_c.add_argument("--seed", type=int, default=1729)
    stage_c.set_defaults(func=command_stage_c)

    stage_c1 = subparsers.add_parser(
        "stage-c1-relaxed-projection",
        help="Project H2/H3 relaxed outputs into canonical fields and score benchmark metrics.",
    )
    stage_c1.add_argument("--stage-a-dir", required=True, help="Stage A-style run directory containing H2/H3 outputs.")
    stage_c1.add_argument("--harnesses", nargs="+", default=["H2_task_specific", "H3_loose_answer_then_parse"])
    stage_c1.add_argument("--models", nargs="+")
    stage_c1.add_argument("--output-dir", default=str(DEFAULT_STAGE_C1_OUTPUT_DIR))
    stage_c1.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    stage_c1.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    stage_c1.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    stage_c1.add_argument("--split", default="development", choices=["development", "validation", "test"])
    stage_c1.set_defaults(func=command_stage_c1)

    h6_h7 = subparsers.add_parser(
        "h6-h7-clean-diagnostic",
        help="Run H6 benchmark-only JSON and H7 extract-then-normalize on the development diagnostic slice.",
    )
    h6_h7.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    h6_h7.add_argument("--splits", default=str(DEFAULT_SPLITS))
    h6_h7.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    h6_h7.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    h6_h7.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    h6_h7.add_argument("--split", default="development", choices=["development", "validation", "test"])
    h6_h7.add_argument("--limit", type=int, default=15)
    h6_h7.add_argument("--models", nargs="+", default=["gpt_4_1_mini_baseline", "gpt_5_4_mini", "gpt_5_5"])
    h6_h7.add_argument("--harnesses", nargs="+", default=["H6_benchmark_only_coarse_json", "H7_extract_then_normalize"])
    h6_h7.add_argument("--temperature", type=float)
    h6_h7.add_argument("--max-output-tokens", type=int)
    h6_h7.add_argument("--reasoning-effort", choices=["minimal", "low", "medium", "high"])
    h6_h7.add_argument("--stub-calls", action="store_true", help="Exercise logging without paid provider calls.")
    h6_h7.add_argument(
        "--require-present-evidence-for-projection",
        action="store_true",
        help="Validate projected canonical outputs as strict evidence-bearing extractions.",
    )
    h6_h7.add_argument("--google-thinking-budget", type=int, help="Google thinking token budget. Use 0 or a small value for extraction smoke runs.")
    h6_h7.add_argument("--output-dir", default=str(DEFAULT_H6_H7_OUTPUT_DIR))
    h6_h7.set_defaults(func=command_h6_h7_diagnostic)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
