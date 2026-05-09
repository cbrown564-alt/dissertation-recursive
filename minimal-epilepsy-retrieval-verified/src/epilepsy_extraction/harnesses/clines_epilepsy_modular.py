from __future__ import annotations

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
    ProviderResponse,
    budget_from_provider_responses,
)
from epilepsy_extraction.schemas import (
    CORE_FIELD_FAMILIES,
    DatasetSlice,
    ExtractionPayload,
    GoldRecord,
    RunRecord,
    event_dicts,
    failed_component_coverage,
    field_coverage,
    harness_event,
    summarize_harness_events,
)
from epilepsy_extraction.schemas.contracts import ArchitectureFamily, FieldFamily


def run_clines_epilepsy_modular(
    records: Iterable[GoldRecord],
    dataset: DatasetSlice,
    run_id: str,
    code_version: str,
    provider: ChatProvider,
    *,
    model: str = "mock-model",
    temperature: float = 0.0,
) -> RunRecord:
    """CLINES-inspired modular extraction pipeline.

    Per row:
      1. Normalise letter text.
      2. Chunk by sections.
      3. For each field family: select relevant chunks, extract, annotate
         status/temporality, normalise values, verify evidence (deterministic).
      4. Aggregate across families into FinalExtraction.

    Makes len(CORE_FIELD_FAMILIES) provider calls per row.
    Architecture family: clines_inspired_modular.
    """
    prompt = load_prompt("clines_field_extractor")
    schema = load_schema("final_extraction")
    record_list = list(records)
    rows: list[dict[str, Any]] = []
    all_responses: list[ProviderResponse] = []
    parse_results: list[tuple[str, bool]] = []
    run_coverage = field_coverage(implemented=CORE_FIELD_FAMILIES)
    events = []
    workflow_units = modular_workflow_units(provider_verifier=False)

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
                summary="Letter normalized and chunked for modular extraction",
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
                provider, prompt.content, schema.content, family, context, model, temperature
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

            # Deterministic post-processing (stored in artifacts, not final payload)
            _, status_ann = annotate_status(result.data, context)
            verification_artifact, _ = verify_field_extraction(result.data, context)
            row_events.append(
                harness_event(
                    "verification_completed",
                    record.row_id,
                    sequence,
                    component=family.value,
                    summary="Deterministic evidence verification completed",
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
                "verification": verification_artifact,
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
                    summary="Modular field-family extraction and enrichment completed",
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
                summary="Verified field-family outputs aggregated into final payload",
                metrics={"valid": not agg.any_invalid, "conflicts": len(agg.conflicts)},
                warnings=agg.warnings,
            )
        )
        if agg.warnings:
            row_events.append(
                harness_event(
                    "warning_emitted",
                    record.row_id,
                    sequence + 1,
                    component="aggregation",
                    summary="Modular aggregation emitted warnings",
                    warnings=agg.warnings,
                )
            )
        events.extend(row_events)

        payload = ExtractionPayload(
            pipeline_id="clines_epilepsy_modular",
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
        harness="clines_epilepsy_modular",
        schema_version=schema.version,
        dataset=dataset,
        model=model,
        provider=provider.provider_name,
        temperature=temperature,
        prompt_version=prompt.version,
        code_version=code_version,
        budget=budget_from_provider_responses(all_responses, rows=len(record_list)),
        field_coverage=run_coverage,
        rows=rows,
        parse_validity=parse_validity_summary(parse_results),
        artifact_paths={"prompt": prompt.path, "schema": schema.path},
        architecture_family=ArchitectureFamily.CLINES_INSPIRED_MODULAR.value,
        complexity={
            "modules": [
                "chunking",
                "field_extractors",
                "status_temporality",
                "normalization",
                "verification_deterministic",
                "aggregation",
            ],
            "workflow_units": [unit.unit_id for unit in workflow_units],
        },
        harness_events=event_dicts(events),
        event_summary=summarize_harness_events(events),
    )
