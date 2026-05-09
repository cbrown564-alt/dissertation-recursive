from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Iterable

from epilepsy_extraction.assets import load_prompt, load_schema
from epilepsy_extraction.document import ClinicalDocumentInterface
from epilepsy_extraction.evaluation import parse_validity_summary
from epilepsy_extraction.modules.aggregation import aggregate_field_results
from epilepsy_extraction.modules.chunking import chunk_letter, select_chunks_for_family
from epilepsy_extraction.modules.field_extractors import extract_field_family
from epilepsy_extraction.modules.normalization import enrich_seizure_frequency
from epilepsy_extraction.modules.status_temporality import annotate_status
from epilepsy_extraction.modules.verification import verify_field_extraction
from epilepsy_extraction.modules.workflows import (
    field_extractor_unit,
    modular_workflow_units,
    normalizer_unit,
    verifier_unit,
    workflow_unit_dicts,
)
from epilepsy_extraction.providers import (
    ChatProvider,
    ProviderMessage,
    ProviderRequest,
    ProviderResponse,
    budget_from_provider_responses,
)
from epilepsy_extraction.schemas import (
    CORE_FIELD_FAMILIES,
    DatasetSlice,
    ExtractionPayload,
    FinalExtraction,
    GoldRecord,
    RunRecord,
    event_dicts,
    failed_component_coverage,
    field_coverage,
    harness_event,
    summarize_harness_events,
)
from epilepsy_extraction.schemas.contracts import ArchitectureFamily, FieldFamily


def run_clines_epilepsy_verified(
    records: Iterable[GoldRecord],
    dataset: DatasetSlice,
    run_id: str,
    code_version: str,
    provider: ChatProvider,
    *,
    model: str = "mock-model",
    temperature: float = 0.0,
) -> RunRecord:
    """CLINES-inspired modular pipeline with provider-backed evidence verification.

    Extends clines_epilepsy_modular by adding one additional provider call per
    row that reviews the aggregated extraction against the original letter and
    returns evidence grades beyond simple quote presence.

    Makes len(CORE_FIELD_FAMILIES) + 1 provider calls per row.
    Architecture family: clines_inspired_modular.
    """
    extraction_prompt = load_prompt("clines_field_extractor")
    verification_prompt = load_prompt("clines_verifier")
    schema = load_schema("final_extraction")
    record_list = list(records)
    rows: list[dict[str, Any]] = []
    all_responses: list[ProviderResponse] = []
    parse_results: list[tuple[str, bool]] = []
    run_coverage = field_coverage(implemented=CORE_FIELD_FAMILIES)
    events = []
    workflow_units = modular_workflow_units(provider_verifier=True)

    for record in record_list:
        document = ClinicalDocumentInterface(record.letter)
        letter_norm = document.letter
        chunks = chunk_letter(letter_norm)
        row_events = [
            harness_event(
                "context_built",
                record.row_id,
                1,
                component="chunking",
                summary="Letter normalized and chunked for verified modular extraction",
                metrics={"chunks": len(chunks)},
            )
        ]
        sequence = 2

        row_responses: list[ProviderResponse] = []
        field_data: dict[FieldFamily, dict[str, Any]] = {}
        row_artifacts: dict[str, Any] = {
            "document_interface": {
                "used": True,
                "tools": ["get_sections", "search_spans", "quote_evidence", "validate_payload"],
                "sections": document.get_sections(),
            },
            "workflow_units": workflow_unit_dicts(workflow_units),
            "chunks": [
                {
                    "chunk_id": c.chunk_id,
                    "source_section": c.source_section,
                    "token_estimate": c.token_estimate,
                }
                for c in chunks
            ]
        }

        for family in CORE_FIELD_FAMILIES:
            selected, selection_warnings = select_chunks_for_family(chunks, family)
            context = "\n---\n".join(c.text for c in selected)
            row_events.append(
                harness_event(
                    "candidate_spans_selected",
                    record.row_id,
                    sequence,
                    component=family.value,
                    summary="Chunks selected for field-family extraction",
                    metrics={"selected_chunks": len(selected), "context_chars": len(context)},
                    warnings=selection_warnings,
                )
            )
            sequence += 1
            row_events.append(
                harness_event(
                    "provider_call_started",
                    record.row_id,
                    sequence,
                    component=family.value,
                    summary="Provider call requested modular field extraction",
                )
            )
            sequence += 1

            result = extract_field_family(
                provider, extraction_prompt.content, schema.content, family, context, model, temperature
            )
            if result.response:
                row_responses.append(result.response)
                row_events.append(
                    harness_event(
                        "provider_call_finished",
                        record.row_id,
                        sequence,
                        component=family.value,
                        summary="Provider call completed",
                        metrics={
                            "ok": result.response.ok,
                            "input_tokens": result.response.usage.input_tokens,
                            "output_tokens": result.response.usage.output_tokens,
                            "latency_ms": result.response.latency_ms,
                        },
                        error=result.response.error.type if result.response.error else "",
                    )
                )
                sequence += 1
            parse_results.append((family.value, result.valid))
            row_events.append(
                harness_event(
                    "parse_attempted",
                    record.row_id,
                    sequence,
                    component=family.value,
                    summary="Provider JSON parsed into modular field result",
                    metrics={"valid": result.valid},
                    warnings=result.warnings,
                )
            )
            sequence += 1

            _, status_ann = annotate_status(result.data, context)
            det_verification, _ = verify_field_extraction(result.data, context)
            row_events.append(
                harness_event(
                    "verification_completed",
                    record.row_id,
                    sequence,
                    component=family.value,
                    summary="Deterministic field verification completed",
                    metrics={"parse_valid": result.valid},
                    warnings=result.warnings,
                )
            )
            sequence += 1

            freq_norm = {}
            if family == FieldFamily.SEIZURE_FREQUENCY and result.data:
                freq_norm = enrich_seizure_frequency(
                    result.data.get("seizure_frequency", {})
                )

            row_artifacts[family.value] = {
                "selected_chunk_ids": [c.chunk_id for c in selected],
                "selection_warnings": selection_warnings,
                "status_annotation": {
                    "status": status_ann.status,
                    "confidence": status_ann.confidence,
                    "evidence_phrase": status_ann.evidence_phrase,
                },
                "verification_deterministic": det_verification,
                "frequency_normalization": freq_norm,
                "parse_valid": result.valid,
                "warnings": result.warnings,
                "workflow_units": workflow_unit_dicts(
                    [
                        field_extractor_unit(family),
                        normalizer_unit(),
                        verifier_unit(provider_backed=False),
                    ]
                ),
            }
            field_data[family] = result.data
            row_events.append(
                harness_event(
                    "field_extraction_completed",
                    record.row_id,
                    sequence,
                    component=family.value,
                    summary="Verified modular field-family extraction and enrichment completed",
                    metrics={"valid": result.valid},
                    warnings=selection_warnings + result.warnings,
                )
            )
            sequence += 1

        agg = aggregate_field_results(field_data)
        if agg.any_invalid:
            run_coverage = failed_component_coverage(CORE_FIELD_FAMILIES)
        row_events.append(
            harness_event(
                "aggregation_completed",
                record.row_id,
                sequence,
                component="aggregation",
                summary="Field-family outputs aggregated before provider verification",
                metrics={"valid": not agg.any_invalid, "conflicts": len(agg.conflicts)},
                warnings=agg.warnings,
            )
        )
        sequence += 1

        # Provider-backed verification pass
        row_events.append(
            harness_event(
                "provider_call_started",
                record.row_id,
                sequence,
                component="provider_verification",
                summary="Provider call requested evidence verification",
            )
        )
        sequence += 1
        verification_response, verification_artifact = _run_verification(
            provider,
            verification_prompt.content,
            agg.final,
            letter_norm,
            model,
            temperature,
        )
        if verification_response:
            row_responses.append(verification_response)
            row_events.append(
                harness_event(
                    "provider_call_finished",
                    record.row_id,
                    sequence,
                    component="provider_verification",
                    summary="Provider verification call completed",
                    metrics={
                        "ok": verification_response.ok,
                        "input_tokens": verification_response.usage.input_tokens,
                        "output_tokens": verification_response.usage.output_tokens,
                        "latency_ms": verification_response.latency_ms,
                    },
                    error=verification_response.error.type if verification_response.error else "",
                )
            )
            sequence += 1
        row_artifacts["provider_verification"] = verification_artifact
        row_artifacts["provider_verification"]["workflow_unit"] = verifier_unit(provider_backed=True).to_dict()
        parse_results.append(("verification", verification_artifact.get("parse_valid", False)))
        row_events.append(
            harness_event(
                "verification_completed",
                record.row_id,
                sequence,
                component="provider_verification",
                summary="Provider-backed evidence verification completed",
                metrics={
                    "parse_valid": verification_artifact.get("parse_valid", False),
                    "overall_confidence": verification_artifact.get("overall_confidence"),
                },
                warnings=[str(warning) for warning in verification_artifact.get("warnings", [])],
                error=str(verification_artifact.get("error", "")),
            )
        )
        if agg.warnings or verification_artifact.get("warnings"):
            row_events.append(
                harness_event(
                    "warning_emitted",
                    record.row_id,
                    sequence + 1,
                    component="clines_epilepsy_verified",
                    summary="Verified modular run emitted warnings",
                    warnings=agg.warnings + [str(warning) for warning in verification_artifact.get("warnings", [])],
                )
            )
        events.extend(row_events)

        payload = ExtractionPayload(
            pipeline_id="clines_epilepsy_verified",
            final=agg.final,
            field_coverage=(
                field_coverage(implemented=CORE_FIELD_FAMILIES)
                if not agg.any_invalid
                else failed_component_coverage(CORE_FIELD_FAMILIES)
            ),
            artifacts=row_artifacts,
            invalid_output=agg.any_invalid,
            warnings=agg.warnings,
            metadata={
                "source_row_index": record.source_row_index,
                "aggregation_conflicts": agg.conflicts,
                "verification_overall_confidence": verification_artifact.get("overall_confidence"),
                "workflow_units": [unit.unit_id for unit in workflow_units],
            },
        )

        all_responses.extend(row_responses)
        rows.append(
            {
                "row_id": record.row_id,
                "source_row_index": record.source_row_index,
                "payload": payload.to_dict(),
                "modular_artifacts": row_artifacts,
                "provider_responses": [asdict(r) for r in row_responses],
                "harness_events": event_dicts(row_events),
            }
        )

    return RunRecord(
        run_id=run_id,
        harness="clines_epilepsy_verified",
        schema_version=schema.version,
        dataset=dataset,
        model=model,
        provider=provider.provider_name,
        temperature=temperature,
        prompt_version=extraction_prompt.version,
        code_version=code_version,
        budget=budget_from_provider_responses(all_responses, rows=len(record_list)),
        field_coverage=run_coverage,
        rows=rows,
        parse_validity=parse_validity_summary(parse_results),
        artifact_paths={
            "extraction_prompt": extraction_prompt.path,
            "verification_prompt": verification_prompt.path,
            "schema": schema.path,
        },
        architecture_family=ArchitectureFamily.CLINES_INSPIRED_MODULAR.value,
        complexity={
            "modules": [
                "chunking",
                "field_extractors",
                "status_temporality",
                "normalization",
                "verification_deterministic",
                "verification_provider",
                "aggregation",
            ],
            "workflow_units": [unit.unit_id for unit in workflow_units],
        },
        harness_events=event_dicts(events),
        event_summary=summarize_harness_events(events),
    )


def _run_verification(
    provider: ChatProvider,
    prompt_text: str,
    final: FinalExtraction,
    letter: str,
    model: str,
    temperature: float,
) -> tuple[ProviderResponse | None, dict[str, Any]]:
    """Call provider to verify evidence support for the aggregated extraction."""
    extraction_summary = json.dumps(final.to_dict(), indent=2, sort_keys=True)
    content = (
        f"{prompt_text}\n\n"
        f"Extracted output:\n{extraction_summary}\n\n"
        f"Original clinic letter:\n{letter}"
    )
    response = provider.complete(
        ProviderRequest(
            messages=[ProviderMessage(role="user", content=content)],
            model=model,
            temperature=temperature,
            response_format="json",
            metadata={"prompt_id": "clines_verifier"},
        )
    )
    if not response.ok:
        return response, {"parse_valid": False, "error": "provider_error"}
    try:
        data = json.loads(response.content)
    except json.JSONDecodeError:
        return response, {"parse_valid": False, "error": "json_parse_error"}
    return response, {
        "parse_valid": True,
        "verifications": data.get("verifications", {}),
        "overall_confidence": data.get("overall_confidence"),
        "warnings": data.get("warnings", []),
    }
