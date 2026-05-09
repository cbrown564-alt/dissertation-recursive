from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from epilepsy_extraction.document.normalization import normalize_letter
from epilepsy_extraction.document.sections import LetterSection, detect_sections
from epilepsy_extraction.modules.verification import verify_evidence_deterministic
from epilepsy_extraction.retrieval.candidates import retrieve_candidate_spans
from epilepsy_extraction.schemas import ExtractionPayload, validate_final_payload_keys
from epilepsy_extraction.schemas.contracts import FieldFamily


@dataclass(frozen=True)
class SpanLocator:
    start: int
    end: int
    text_hash: str

    @property
    def locator(self) -> str:
        return f"char:{self.start}-{self.end}:{self.text_hash}"


class ClinicalDocumentInterface:
    """Bounded document tools for clinical extraction harnesses.

    The interface exposes deterministic document operations analogous to an
    agent-computer interface. It never exposes gold labels and does not make
    clinical claims; it only returns sections, spans, quotes, schema validation,
    and evidence-support comparisons.
    """

    def __init__(self, letter: str):
        self.letter = normalize_letter(letter)
        self._sections = detect_sections(self.letter)

    def get_sections(self) -> list[dict[str, Any]]:
        return [asdict(section) for section in self._sections]

    def search_spans(
        self,
        field_family: FieldFamily | str,
        *,
        max_spans: int = 5,
        context_chars: int = 150,
    ) -> list[dict[str, Any]]:
        family = field_family if isinstance(field_family, FieldFamily) else FieldFamily(str(field_family))
        spans = retrieve_candidate_spans(
            self.letter,
            family,
            max_spans=max_spans,
            context_chars=context_chars,
        )
        return [
            {
                "text": span.text,
                "field_family": span.field_family,
                "score": span.score,
                "span_start": span.span_start,
                "span_end": span.span_end,
                "locator": _locator(self.letter, span.span_start, span.span_end).locator,
                "warnings": list(span.warnings),
            }
            for span in spans
        ]

    def get_span(self, locator: str) -> dict[str, Any]:
        start, end = _parse_locator(locator)
        if start < 0 or end < start or end > len(self.letter):
            raise ValueError(f"Span locator out of bounds: {locator}")
        expected_hash = locator.rsplit(":", 1)[-1]
        span_hash = _text_hash(self.letter[start:end])
        if expected_hash != span_hash:
            raise ValueError("Span locator hash does not match document text")
        return {
            "text": self.letter[start:end],
            "span_start": start,
            "span_end": end,
            "locator": locator,
        }

    def quote_evidence(self, quote: str) -> dict[str, Any]:
        start = self.letter.find(quote)
        if start < 0:
            return {"quote": quote, "supported": False, "locator": "", "span_start": None, "span_end": None}
        end = start + len(quote)
        return {
            "quote": quote,
            "supported": True,
            "locator": _locator(self.letter, start, end).locator,
            "span_start": start,
            "span_end": end,
        }

    def validate_payload(self, payload: ExtractionPayload | dict[str, Any]) -> dict[str, Any]:
        final = payload.final.to_dict() if isinstance(payload, ExtractionPayload) else payload.get("final", payload)
        try:
            validate_final_payload_keys(final)
        except (TypeError, ValueError) as exc:
            return {"valid": False, "error": str(exc)}
        return {"valid": True, "error": ""}

    def compare_evidence_to_claim(self, claim: str, quote: str | None) -> dict[str, Any]:
        assessment = verify_evidence_deterministic(claim, quote, self.letter)
        evidence = self.quote_evidence(quote) if quote else {}
        full_credit = assessment.grade.value in {"exact_span", "overlapping_span"}
        return {
            "grade": assessment.grade.value,
            "full_credit": full_credit,
            "warnings": list(assessment.notes),
            "locator": evidence.get("locator", ""),
        }

    def section_for_locator(self, locator: str) -> dict[str, Any] | None:
        start, end = _parse_locator(locator)
        for section in self._sections:
            if section.start <= start and end <= section.end:
                return asdict(section)
        return None


def get_sections(letter: str) -> list[dict[str, Any]]:
    return ClinicalDocumentInterface(letter).get_sections()


def search_spans(letter: str, field_family: FieldFamily | str, **kwargs: Any) -> list[dict[str, Any]]:
    return ClinicalDocumentInterface(letter).search_spans(field_family, **kwargs)


def get_span(letter: str, locator: str) -> dict[str, Any]:
    return ClinicalDocumentInterface(letter).get_span(locator)


def quote_evidence(letter: str, quote: str) -> dict[str, Any]:
    return ClinicalDocumentInterface(letter).quote_evidence(quote)


def validate_payload(letter: str, payload: ExtractionPayload | dict[str, Any]) -> dict[str, Any]:
    return ClinicalDocumentInterface(letter).validate_payload(payload)


def compare_evidence_to_claim(letter: str, claim: str, quote: str | None) -> dict[str, Any]:
    return ClinicalDocumentInterface(letter).compare_evidence_to_claim(claim, quote)


def _locator(text: str, start: int, end: int) -> SpanLocator:
    return SpanLocator(start=start, end=end, text_hash=_text_hash(text[start:end]))


def _parse_locator(locator: str) -> tuple[int, int]:
    try:
        kind, rest, _ = locator.split(":", 2)
        if kind != "char":
            raise ValueError
        start_s, end_s = rest.split("-", 1)
        return int(start_s), int(end_s)
    except ValueError as exc:
        raise ValueError(f"Invalid span locator: {locator}") from exc


def _text_hash(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
