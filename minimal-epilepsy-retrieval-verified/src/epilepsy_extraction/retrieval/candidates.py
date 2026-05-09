from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from epilepsy_extraction.schemas.contracts import FieldFamily


FIELD_PATTERNS: dict[FieldFamily, re.Pattern[str]] = {
    FieldFamily.SEIZURE_FREQUENCY: re.compile(
        r"\b(seizure|fit|episode|attack|ictus|per month|per week|per year|per day|"
        r"daily|weekly|monthly|annually|seizure.free|seizure free|last seizure|"
        r"frequency|cluster|breakthrough)\b",
        re.IGNORECASE,
    ),
    FieldFamily.CURRENT_MEDICATIONS: re.compile(
        r"\b(medication|medicine|drug|tablet|capsule|mg|dose|dosage|prescription|"
        r"lamotrigine|levetiracetam|valproate|carbamazepine|oxcarbazepine|topiramate|"
        r"clobazam|clonazepam|phenytoin|zonisamide|perampanel|lacosamide|brivaracetam|"
        r"eslicarbazepine|gabapentin|pregabalin|vigabatrin|ethosuximide|phenobarbital|"
        r"phenobarbitone|nitrazepam|rufinamide|stiripentol|cannabidiol|fenfluramine)\b",
        re.IGNORECASE,
    ),
    FieldFamily.INVESTIGATIONS: re.compile(
        r"\b(MRI|CT|EEG|ECG|telemetry|ambulatory|VEEG|genetics|karyotype|metabolic|"
        r"neuropsychology|neuropsychological|lactate|glucose|ammonia|blood|result|"
        r"investigation|scan|imaging|report|study|FISH|array|microarray|panel)\b",
        re.IGNORECASE,
    ),
    FieldFamily.SEIZURE_CLASSIFICATION: re.compile(
        r"\b(focal|generalised|generalized|tonic.clonic|tonic|clonic|atonic|"
        r"myoclonic|absence|infantile spasm|spasm|seizure type|semiology|"
        r"behaviour|posture|version|automatism|aura|awareness|consciousness|"
        r"bilateral|unilateral|motor|non.motor|hypermotor)\b",
        re.IGNORECASE,
    ),
    FieldFamily.EPILEPSY_CLASSIFICATION: re.compile(
        r"\b(epilepsy|syndrome|Dravet|Lennox.Gastaut|West syndrome|Doose|"
        r"Panayiotopoulos|JME|JAE|CAE|GTCS|temporal lobe|frontal lobe|occipital|"
        r"parietal|structural|genetic|unknown aetiology|cryptogenic|idiopathic|"
        r"BECTS|self.limited|developmental|epileptic encephalopathy)\b",
        re.IGNORECASE,
    ),
}


@dataclass(frozen=True)
class CandidateSpan:
    text: str
    field_family: str
    score: int
    span_start: int
    span_end: int
    warnings: list[str] = field(default_factory=list)


def retrieve_candidate_spans(
    letter: str,
    field_family: FieldFamily,
    max_spans: int = 5,
    context_chars: int = 150,
) -> list[CandidateSpan]:
    """Return scored candidate spans relevant to field_family, most relevant first."""
    pattern = FIELD_PATTERNS.get(field_family)
    if pattern is None:
        return []

    raw: list[CandidateSpan] = []
    for sent_start, sent_text in _split_sentences(letter):
        matches = list(pattern.finditer(sent_text))
        if not matches:
            continue
        ctx_start = max(0, sent_start - context_chars)
        ctx_end = min(len(letter), sent_start + len(sent_text) + context_chars)
        raw.append(
            CandidateSpan(
                text=letter[ctx_start:ctx_end].strip(),
                field_family=field_family.value,
                score=len(matches),
                span_start=ctx_start,
                span_end=ctx_end,
            )
        )

    return sorted(_deduplicate(raw), key=lambda s: s.score, reverse=True)[:max_spans]


def build_retrieval_context(
    letter: str,
    field_family: FieldFamily,
    max_spans: int = 3,
) -> tuple[str, list[dict[str, Any]], list[str]]:
    """Return (context_text, span_artifacts, warnings).

    Falls back to the full letter with a warning if no spans are found.
    """
    spans = retrieve_candidate_spans(letter, field_family, max_spans=max_spans)
    warnings: list[str] = []

    if not spans:
        warnings.append("retrieval_recall_loss_fallback_full")
        return letter, [], warnings

    seen: set[str] = set()
    context_parts: list[str] = []
    artifacts: list[dict[str, Any]] = []
    for span in spans:
        if span.text not in seen:
            seen.add(span.text)
            context_parts.append(span.text)
            artifacts.append(
                {
                    "text": span.text,
                    "field_family": span.field_family,
                    "score": span.score,
                    "span_start": span.span_start,
                    "span_end": span.span_end,
                }
            )

    context_text = "\n---\n".join(context_parts)
    if len(context_text) < len(letter) * 0.15 and len(letter) > 200:
        warnings.append("retrieval_context_sparse")

    return context_text, artifacts, warnings


def _split_sentences(text: str) -> list[tuple[int, str]]:
    pattern = re.compile(r"(?<=[.!?])\s+|\n+")
    results: list[tuple[int, str]] = []
    pos = 0
    for match in pattern.finditer(text):
        sent = text[pos : match.start()].strip()
        if sent:
            results.append((pos, sent))
        pos = match.end()
    if pos < len(text):
        remaining = text[pos:].strip()
        if remaining:
            results.append((pos, remaining))
    return results


def _deduplicate(spans: list[CandidateSpan]) -> list[CandidateSpan]:
    """Drop spans fully contained within a higher-scoring span."""
    by_score = sorted(spans, key=lambda s: s.score, reverse=True)
    kept: list[CandidateSpan] = []
    for span in by_score:
        if not any(
            k.span_start <= span.span_start and k.span_end >= span.span_end
            for k in kept
        ):
            kept.append(span)
    return kept
