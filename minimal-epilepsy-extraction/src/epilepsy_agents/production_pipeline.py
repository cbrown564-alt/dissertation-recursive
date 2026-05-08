"""Faithful production multi-agent extraction pipeline.

The experimental harnesses in :mod:`epilepsy_agents.llm_pipeline` remain useful
for controlled comparisons. This module is the product-shaped implementation of
the original design: explicit section/timeline, field extractor, verification,
and aggregation roles with inspectable intermediate artifacts.
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, replace
from typing import Any, Callable

from .agents import MultiAgentPipeline, SectionTimelineAgent
from .broader_field_schema import (
    TIER1A_BROADER_ONLY_JSON_SCHEMA,
    broader_coverage_user_prompt,
    parse_broader_only_response,
    tier1a_system_prompt,
)
from .broader_verification import verify_broader_field_support
from .labels import parse_label
from .llm_pipeline import SinglePromptLLMPipeline, _usage_metadata
from .production_schema import (
    EPILEPSY_CLASSIFICATION_JSON_SCHEMA,
    classification_system_prompt,
    classification_user_prompt,
    parse_classification_response,
)
from .providers import ChatMessage, LLMProvider


class ProductionSectionTimelineAgent:
    """Segment the source letter and expose timeline-like context."""

    _DATE_PATTERN = re.compile(
        r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
        r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{4}|"
        r"\d{4})\b",
        re.IGNORECASE,
    )
    _EVENT_TERMS = re.compile(
        r"\b(seizure|seizures|event|events|episode|episodes|asm|medication|"
        r"lamotrigine|levetiracetam|valproate|eeg|mri|ct|telemetry|genetic|"
        r"diagnosis|syndrome|epilepsy)\b",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        self._baseline = SectionTimelineAgent()

    def run(self, letter: str) -> dict[str, Any]:
        timeline = self._baseline.run(letter)
        sentences = _sentence_spans(letter)
        events = []
        for sentence in sentences:
            if self._EVENT_TERMS.search(sentence["text"]):
                events.append(
                    {
                        "text": sentence["text"],
                        "start": sentence["start"],
                        "end": sentence["end"],
                        "dates": self._DATE_PATTERN.findall(sentence["text"]),
                    }
                )
        return {
            "sections": timeline.sections,
            "candidate_spans": [asdict(span) for span in timeline.candidates[:20]],
            "timeline_events": events[:40],
        }


class ProductionFieldExtractorAgent:
    """Run field-group-specific extractors under explicit call budgets."""

    def __init__(self, provider: LLMProvider, max_retries: int = 1) -> None:
        self.provider = provider
        self.max_retries = max_retries
        self._sf_pipeline = SinglePromptLLMPipeline(provider=provider, max_retries=max_retries)
        self._sf_fallback = MultiAgentPipeline()

    def run(self, letter: str) -> dict[str, Any]:
        sf_prediction = self._sf_pipeline.predict(letter)
        if (sf_prediction.metadata or {}).get("invalid_output"):
            failed_metadata = sf_prediction.metadata or {}
            failed_warnings = list(sf_prediction.warnings)
            fallback_prediction = self._sf_fallback.predict(letter)
            sf_prediction = replace(
                fallback_prediction,
                warnings=failed_warnings
                + list(fallback_prediction.warnings)
                + ["sf_deterministic_fallback"],
                metadata={
                    "provider": getattr(self.provider, "provider_name", "unknown"),
                    "model": getattr(self.provider, "model", "unknown"),
                    "invalid_output": False,
                    "fallback_used": True,
                    "fallback_reason": "llm_json_failure",
                    "failed_call": failed_metadata,
                },
            )
        broader = self._call_broader_fields(letter)
        classification = self._call_classification(letter)
        core_invalid_output = bool(
            (sf_prediction.metadata or {}).get("invalid_output")
            or broader.get("invalid_output")
        )
        classification_invalid_output = bool(classification.get("invalid_output"))
        full_contract_invalid_output = core_invalid_output or classification_invalid_output
        return {
            "seizure_frequency": {
                "label": sf_prediction.label,
                "evidence": [asdict(span) for span in sf_prediction.evidence],
                "confidence": sf_prediction.confidence,
                "parsed_monthly_rate": sf_prediction.parsed_monthly_rate,
                "pragmatic_class": sf_prediction.pragmatic_class,
                "purist_class": sf_prediction.purist_class,
                "warnings": sf_prediction.warnings,
                "metadata": sf_prediction.metadata,
            },
            "current_medications": broader.get("current_medications", []),
            "seizure_types": broader.get("seizure_types", []),
            "investigations": broader.get("investigations", []),
            "epilepsy_type": classification.get("epilepsy_type", {}),
            "epilepsy_syndrome": classification.get("epilepsy_syndrome", {}),
            "invalid_output": full_contract_invalid_output,
            "warnings": list(sf_prediction.warnings)
            + broader.get("warnings", [])
            + classification.get("warnings", []),
            "metadata": {
                "core_invalid_output": core_invalid_output,
                "classification_invalid_output": classification_invalid_output,
                "optional_invalid_output": classification_invalid_output,
                "full_contract_invalid_output": full_contract_invalid_output,
                "sf_call": sf_prediction.metadata or {},
                "broader_call": broader.get("metadata", {}),
                "classification_call": classification.get("metadata", {}),
            },
        }

    def _call_broader_fields(self, letter: str) -> dict[str, Any]:
        result = self._call_json_role(
            letter=letter,
            schema=TIER1A_BROADER_ONLY_JSON_SCHEMA,
            messages_fn=lambda source: [
                ChatMessage(role="system", content=tier1a_system_prompt()),
                ChatMessage(role="user", content=broader_coverage_user_prompt(source)),
            ],
            parser=parse_broader_only_response,
            role_name="broader",
            fallback={
                "current_medications": [],
                "seizure_types": [],
                "investigations": [],
                "invalid_output": True,
            },
        )
        if not result.get("invalid_output"):
            return result
        fallback = _deterministic_broader_fallback(letter)
        return {
            **fallback,
            "invalid_output": False,
            "warnings": result.get("warnings", []) + fallback.get("warnings", []),
            "metadata": {
                **result.get("metadata", {}),
                "invalid_output": False,
                "fallback_used": True,
                "fallback_reason": "broader_json_failure",
                "failed_call": result.get("metadata", {}),
            },
        }

    def _call_classification(self, letter: str) -> dict[str, Any]:
        return self._call_json_role(
            letter=letter,
            schema=EPILEPSY_CLASSIFICATION_JSON_SCHEMA,
            messages_fn=lambda source: [
                ChatMessage(role="system", content=classification_system_prompt()),
                ChatMessage(role="user", content=classification_user_prompt(source)),
            ],
            parser=parse_classification_response,
            role_name="classification",
            fallback={
                "epilepsy_type": {"value": "unknown", "evidence": "", "confidence": 0.0},
                "epilepsy_syndrome": {"value": "unknown", "evidence": "", "confidence": 0.0},
                "invalid_output": True,
            },
        )

    def _call_json_role(
        self,
        letter: str,
        schema: dict[str, object],
        messages_fn: Callable[[str], list[ChatMessage]],
        parser: Callable[[str], dict[str, Any]],
        role_name: str,
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        warnings: list[str] = []
        last_error: str | None = None
        for attempt in range(1, self.max_retries + 2):
            started = time.perf_counter()
            try:
                result = self.provider.chat_json(messages_fn(letter), schema)
                latency_ms = round((time.perf_counter() - started) * 1000, 1)
                parsed = parser(result.content)
                if parsed.get("invalid_output"):
                    raise ValueError(f"invalid_{role_name}_output")
                return {
                    **parsed,
                    "warnings": warnings,
                    "metadata": {
                        "provider": result.provider,
                        "model": result.model,
                        "latency_ms": latency_ms,
                        "attempt": attempt,
                        **_usage_metadata(result.raw),
                    },
                }
            except Exception as exc:
                last_error = type(exc).__name__
                warnings.append(f"{role_name}_attempt_{attempt}_{type(exc).__name__.lower()}")
        return {
            **fallback,
            "warnings": warnings + [f"{role_name}_pipeline_failure"],
            "metadata": {
                "provider": getattr(self.provider, "provider_name", "unknown"),
                "model": getattr(self.provider, "model", "unknown"),
                "latency_ms": None,
                "attempt": self.max_retries + 1,
                "error_type": last_error,
            },
        }


class ProductionVerificationAgent:
    """Check evidence support, contradictions, and missingness signals."""

    def run(self, letter: str, extractions: dict[str, Any]) -> dict[str, Any]:
        verified_broader = verify_broader_field_support(
            letter,
            {
                "current_medications": extractions.get("current_medications", []),
                "investigations": extractions.get("investigations", []),
            },
        )
        seizure_frequency = self._verify_sf(letter, extractions.get("seizure_frequency", {}))
        seizure_types = [
            self._verify_generic_item(letter, item, "evidence") for item in extractions.get("seizure_types", [])
        ]
        epilepsy_type = self._verify_generic_field(letter, extractions.get("epilepsy_type", {}))
        epilepsy_syndrome = self._verify_generic_field(
            letter, extractions.get("epilepsy_syndrome", {})
        )
        warnings = []
        warnings.extend(seizure_frequency["support"]["warnings"])
        warnings.extend(_collect_support_warnings(verified_broader.get("current_medications", [])))
        warnings.extend(_collect_support_warnings(verified_broader.get("investigations", [])))
        warnings.extend(_collect_support_warnings(seizure_types))
        warnings.extend(epilepsy_type["support"]["warnings"])
        warnings.extend(epilepsy_syndrome["support"]["warnings"])
        return {
            "seizure_frequency": seizure_frequency,
            "current_medications": verified_broader.get("current_medications", []),
            "seizure_types": seizure_types,
            "investigations": verified_broader.get("investigations", []),
            "epilepsy_type": epilepsy_type,
            "epilepsy_syndrome": epilepsy_syndrome,
            "warnings": warnings,
        }

    def _verify_sf(self, letter: str, field: dict[str, Any]) -> dict[str, Any]:
        evidence_items = field.get("evidence", [])
        evidence_text = ""
        if evidence_items and isinstance(evidence_items[0], dict):
            evidence_text = str(evidence_items[0].get("text", ""))
        support = _support_for_evidence(letter, evidence_text)
        if str(field.get("label", "")).lower() in {"unknown", "no seizure frequency reference"}:
            support["supported"] = True
        return {**field, "support": support}

    def _verify_generic_field(self, letter: str, field: dict[str, Any]) -> dict[str, Any]:
        evidence = str(field.get("evidence", ""))
        support = _support_for_evidence(letter, evidence)
        if str(field.get("value", "")).lower() == "unknown" and not evidence:
            support["supported"] = True
            support["warnings"] = []
        return {**field, "support": support}

    def _verify_generic_item(self, letter: str, item: dict[str, Any], evidence_key: str) -> dict[str, Any]:
        return {**item, "support": _support_for_evidence(letter, str(item.get(evidence_key, "")))}


class ProductionAggregatorAgent:
    """Produce final JSON, confidence, citations, and warnings from verified fields."""

    def run(
        self,
        section_timeline: dict[str, Any],
        extractions: dict[str, Any],
        verification: dict[str, Any],
    ) -> dict[str, Any]:
        warnings = list(dict.fromkeys(extractions.get("warnings", []) + verification.get("warnings", [])))
        final = {
            "patient_summary": {},
            "timeline": section_timeline.get("timeline_events", []),
            "seizure_frequency": self._aggregate_sf(verification.get("seizure_frequency", {})),
            "current_medications": self._aggregate_items(
                verification.get("current_medications", []), "medication"
            ),
            "seizure_types": self._aggregate_items(
                verification.get("seizure_types", []), "seizure_type"
            ),
            "investigations": self._aggregate_items(
                verification.get("investigations", []), "investigation"
            ),
            "epilepsy_type": self._aggregate_classification(
                verification.get("epilepsy_type", {})
            ),
            "epilepsy_syndrome": self._aggregate_classification(
                verification.get("epilepsy_syndrome", {})
            ),
            "warnings": warnings,
            "confidence": {},
            "citations": [],
        }
        final["citations"] = _collect_citations(final)
        final["confidence"] = _field_confidence(final)
        return {
            "final": final,
            "aggregation": {
                "policy": "unsupported items retained with support metadata and confidence downgrade",
                "warning_count": len(warnings),
            },
        }

    def _aggregate_sf(self, field: dict[str, Any]) -> dict[str, Any]:
        confidence = _downgrade_confidence(field.get("confidence", 0.0), field.get("support", {}))
        parsed = parse_label(str(field.get("label", "unknown")))
        return {
            "label": field.get("label", "unknown"),
            "evidence": field.get("evidence", []),
            "confidence": confidence,
            "parsed_monthly_rate": parsed.monthly_rate,
            "pragmatic_class": parsed.pragmatic_class,
            "purist_class": parsed.purist_class,
            "support": field.get("support", {}),
        }

    def _aggregate_items(self, items: list[dict[str, Any]], field_name: str) -> list[dict[str, Any]]:
        aggregated = []
        for item in items:
            aggregated.append(
                {
                    **item,
                    "field": field_name,
                    "confidence": _downgrade_confidence(
                        item.get("confidence", 0.0), item.get("support", {})
                    ),
                }
            )
        return aggregated

    def _aggregate_classification(self, field: dict[str, Any]) -> dict[str, Any]:
        return {
            **field,
            "confidence": _downgrade_confidence(field.get("confidence", 0.0), field.get("support", {})),
        }


class ProductionMultiAgentPipeline:
    """End-to-end production pipeline with explicit role artifacts."""

    pipeline_id = "production_multi_agent_v1"

    def __init__(self, provider: LLMProvider, max_retries: int = 1) -> None:
        self.section_timeline_agent = ProductionSectionTimelineAgent()
        self.field_extractor_agent = ProductionFieldExtractorAgent(
            provider=provider,
            max_retries=max_retries,
        )
        self.verification_agent = ProductionVerificationAgent()
        self.aggregator_agent = ProductionAggregatorAgent()

    def predict(self, letter: str) -> dict[str, Any]:
        section_timeline = self.section_timeline_agent.run(letter)
        field_extractions = self.field_extractor_agent.run(letter)
        verification = self.verification_agent.run(letter, field_extractions)
        aggregated = self.aggregator_agent.run(section_timeline, field_extractions, verification)
        return {
            "pipeline_id": self.pipeline_id,
            "final": aggregated["final"],
            "artifacts": {
                "section_timeline": section_timeline,
                "field_extractions": field_extractions,
                "verification": verification,
                "aggregation": aggregated["aggregation"],
            },
            "invalid_output": bool(field_extractions.get("invalid_output")),
            "warnings": aggregated["final"]["warnings"],
            "metadata": {
                "call_budget": {
                    "llm_calls": 3,
                    "roles": ["seizure_frequency", "broader_fields", "epilepsy_classification"],
                },
                "calls": field_extractions.get("metadata", {}),
            },
        }


def _sentence_spans(letter: str) -> list[dict[str, Any]]:
    spans = []
    for match in re.finditer(r"[^.!?\n]+(?:[.!?]|\n|$)", letter):
        text = " ".join(match.group(0).strip().split())
        if text:
            spans.append({"text": text, "start": match.start(), "end": match.end()})
    return spans


_FALLBACK_ASMS = (
    "brivaracetam",
    "buccal midazolam",
    "carbamazepine",
    "cenobamate",
    "clobazam",
    "clonazepam",
    "diazepam",
    "eslicarbazepine",
    "ethosuximide",
    "gabapentin",
    "lacosamide",
    "lamotrigine",
    "levetiracetam",
    "midazolam",
    "oxcarbazepine",
    "perampanel",
    "phenobarbital",
    "phenobarbitone",
    "phenytoin",
    "pregabalin",
    "primidone",
    "rufinamide",
    "sodium valproate",
    "stiripentol",
    "tiagabine",
    "topiramate",
    "valproate",
    "vigabatrin",
    "zonisamide",
)


def _deterministic_broader_fallback(letter: str) -> dict[str, Any]:
    """Best-effort valid core fallback used only after broader-field JSON failure."""
    sentences = _sentence_spans(letter)
    return {
        "current_medications": _fallback_medications(sentences),
        "seizure_types": _fallback_seizure_types(sentences),
        "investigations": _fallback_investigations(sentences),
        "warnings": ["broader_deterministic_fallback"],
    }


def _fallback_medications(sentences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for sentence in sentences:
        text = sentence["text"]
        norm_text = _norm(text)
        for drug in _FALLBACK_ASMS:
            if f" {_norm(drug)} " not in f" {norm_text} " or drug in seen:
                continue
            status = "previous" if _contains_word(norm_text, ("stopped", "previous", "prior", "past")) else "current"
            if status != "current":
                continue
            seen.add(drug)
            items.append(
                {
                    "drug_name": drug,
                    "dose_text": _fallback_dose_text(text, drug),
                    "status": status,
                    "evidence": text,
                    "confidence": 0.35,
                }
            )
    return items


def _fallback_dose_text(text: str, drug: str) -> str:
    pattern = re.compile(
        rf"{re.escape(drug)}[^.;,\n]{{0,80}}?(?:\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml)[^.;,\n]{{0,40}})?",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return ""
    dose = match.group(0).strip()
    return dose if re.search(r"\d", dose) else ""


def _fallback_seizure_types(sentences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    patterns = (
        ("focal impaired awareness seizures", "focal"),
        ("focal aware seizures", "focal"),
        ("focal seizures", "focal"),
        ("tonic-clonic seizures", "generalized"),
        ("tonic clonic seizures", "generalized"),
        ("generalized seizures", "generalized"),
        ("absence seizures", "generalized"),
        ("myoclonic jerks", "generalized"),
        ("drop attacks", "unknown"),
    )
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for sentence in sentences:
        norm_text = _norm(sentence["text"])
        for description, onset in patterns:
            if description in seen or f" {_norm(description)} " not in f" {norm_text} ":
                continue
            seen.add(description)
            items.append(
                {
                    "description": description,
                    "onset": onset,
                    "evidence": sentence["text"],
                    "confidence": 0.32,
                }
            )
    return items


def _fallback_investigations(sentences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for sentence in sentences:
        text = sentence["text"]
        norm_text = _norm(text)
        investigation_type = _fallback_investigation_type(norm_text)
        if not investigation_type or _negated_investigation(norm_text):
            continue
        key = (investigation_type, norm_text)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "investigation_type": investigation_type,
                "result": _fallback_investigation_result(norm_text),
                "status": _fallback_investigation_status(norm_text),
                "evidence": text,
                "confidence": 0.34,
            }
        )
    return items


def _fallback_investigation_type(norm_text: str) -> str | None:
    if _contains_word(norm_text, ("video eeg", "telemetry", "video telemetry")):
        return "video_EEG"
    if _contains_word(norm_text, ("eeg", "electroencephalogram")):
        return "EEG"
    if _contains_word(norm_text, ("mri", "magnetic resonance")):
        return "MRI"
    if _contains_word(norm_text, ("ct", "computed tomography")):
        return "CT"
    if _contains_word(norm_text, ("genetic", "gene panel", "genomic")):
        return "genetic_test"
    if _contains_word(norm_text, ("blood", "serum", "ecg", "ekg", "thyroid", "drug level")):
        return "other"
    return None


def _fallback_investigation_result(norm_text: str) -> str:
    if _contains_word(norm_text, ("normal", "unremarkable")):
        return "normal"
    if _contains_word(norm_text, ("abnormal", "sharp", "spike", "slowing", "lesion")):
        return "abnormal"
    if _contains_word(norm_text, ("non diagnostic", "nondiagnostic", "indeterminate")):
        return "non_diagnostic"
    if _contains_word(norm_text, ("pending", "awaited", "awaiting")):
        return "pending"
    return "not_stated"


def _fallback_investigation_status(norm_text: str) -> str:
    if _contains_word(norm_text, ("planned", "arranged", "ordered", "request", "requested")):
        return "planned"
    if _contains_word(norm_text, ("pending", "awaited", "awaiting", "sent")):
        return "pending"
    if _contains_word(norm_text, ("previous", "prior", "historical", "past")):
        return "historical"
    if _contains_word(norm_text, ("consider", "if needed", "if worsens")):
        return "conditional"
    return "completed"


def _negated_investigation(norm_text: str) -> bool:
    return bool(
        re.search(
            r"\b(no|without|denies)\s+(?:prior\s+|previous\s+|available\s+|planned\s+)?"
            r"(eeg|mri|ct|investigation|investigations|genetic|telemetry)\b",
            norm_text,
        )
    )


def _contains_word(norm_text: str, phrases: tuple[str, ...]) -> bool:
    padded = f" {norm_text} "
    return any(f" {_norm(phrase)} " in padded for phrase in phrases)


def _support_for_evidence(letter: str, evidence: str) -> dict[str, Any]:
    grade = _evidence_grade(letter, evidence)
    warnings = []
    if grade == "missing_evidence":
        warnings.append("missing_evidence")
    elif grade == "unsupported":
        warnings.append("unsupported_evidence")
    return {
        "evidence_grade": grade,
        "supported": grade in {"exact_span", "overlapping_span"},
        "warnings": warnings,
    }


def _evidence_grade(letter: str, evidence: str) -> str:
    evidence = evidence.strip()
    if not evidence:
        return "missing_evidence"
    if _norm(evidence) in _norm(letter):
        return "exact_span"
    if _has_contiguous_overlap(letter, evidence):
        return "overlapping_span"
    return "unsupported"


def _has_contiguous_overlap(letter: str, evidence: str, min_tokens: int = 4) -> bool:
    letter_tokens = _tokens(letter)
    evidence_tokens = _tokens(evidence)
    if len(evidence_tokens) < min_tokens:
        return False
    ngrams = {
        tuple(letter_tokens[index : index + min_tokens])
        for index in range(0, len(letter_tokens) - min_tokens + 1)
    }
    return any(
        tuple(evidence_tokens[index : index + min_tokens]) in ngrams
        for index in range(0, len(evidence_tokens) - min_tokens + 1)
    )


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _norm(text: str) -> str:
    return " ".join(_tokens(text))


def _collect_support_warnings(items: list[dict[str, Any]]) -> list[str]:
    warnings = []
    for item in items:
        support = item.get("support", {})
        warnings.extend(str(warning) for warning in support.get("warnings", []))
    return warnings


def _downgrade_confidence(confidence: object, support: dict[str, Any]) -> float:
    try:
        value = float(confidence)
    except (TypeError, ValueError):
        value = 0.0
    if support and not support.get("supported", False):
        value *= 0.35
    return round(max(0.0, min(value, 1.0)), 3)


def _collect_citations(final: dict[str, Any]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    sf_evidence = final.get("seizure_frequency", {}).get("evidence", [])
    for span in sf_evidence:
        if isinstance(span, dict) and span.get("text"):
            citations.append({"field": "seizure_frequency", "text": span["text"]})
    for field in ("current_medications", "seizure_types", "investigations"):
        for item in final.get(field, []):
            evidence = item.get("evidence")
            if evidence:
                citations.append({"field": field, "text": evidence})
    for field in ("epilepsy_type", "epilepsy_syndrome"):
        evidence = final.get(field, {}).get("evidence")
        if evidence:
            citations.append({"field": field, "text": evidence})
    return citations


def _field_confidence(final: dict[str, Any]) -> dict[str, float]:
    return {
        "seizure_frequency": float(final.get("seizure_frequency", {}).get("confidence", 0.0)),
        "current_medications": _mean_confidence(final.get("current_medications", [])),
        "seizure_types": _mean_confidence(final.get("seizure_types", [])),
        "investigations": _mean_confidence(final.get("investigations", [])),
        "epilepsy_type": float(final.get("epilepsy_type", {}).get("confidence", 0.0)),
        "epilepsy_syndrome": float(final.get("epilepsy_syndrome", {}).get("confidence", 0.0)),
    }


def _mean_confidence(items: list[dict[str, Any]]) -> float:
    if not items:
        return 0.0
    return round(sum(float(item.get("confidence", 0.0)) for item in items) / len(items), 3)
