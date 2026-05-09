from .normalization import normalize_letter, normalize_whitespace
from .sections import LetterSection, detect_sections, letter_to_sections_dict

__all__ = [
    "LetterSection",
    "detect_sections",
    "letter_to_sections_dict",
    "normalize_letter",
    "normalize_whitespace",
]
from .interface import (
    ClinicalDocumentInterface,
    compare_evidence_to_claim,
    get_sections,
    get_span,
    quote_evidence,
    search_spans,
    validate_payload,
)

__all__ = [
    "ClinicalDocumentInterface",
    "compare_evidence_to_claim",
    "get_sections",
    "get_span",
    "quote_evidence",
    "search_spans",
    "validate_payload",
]
