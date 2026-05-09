from __future__ import annotations

import re
from dataclasses import dataclass, field

from epilepsy_extraction.document.sections import detect_sections
from epilepsy_extraction.schemas.contracts import FieldFamily


_SECTION_FAMILY_AFFINITY: dict[str, list[FieldFamily]] = {
    "seizure frequency": [FieldFamily.SEIZURE_FREQUENCY],
    "seizure history": [FieldFamily.SEIZURE_FREQUENCY, FieldFamily.SEIZURE_CLASSIFICATION],
    "current medications": [FieldFamily.CURRENT_MEDICATIONS],
    "medications": [FieldFamily.CURRENT_MEDICATIONS],
    "investigations": [FieldFamily.INVESTIGATIONS],
    "assessment": [FieldFamily.SEIZURE_CLASSIFICATION, FieldFamily.EPILEPSY_CLASSIFICATION],
    "background history": [FieldFamily.SEIZURE_CLASSIFICATION, FieldFamily.EPILEPSY_CLASSIFICATION],
    "background": [FieldFamily.SEIZURE_CLASSIFICATION, FieldFamily.EPILEPSY_CLASSIFICATION],
    "history": [FieldFamily.SEIZURE_CLASSIFICATION, FieldFamily.EPILEPSY_CLASSIFICATION],
    "preamble": [],
}

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass(frozen=True)
class TextChunk:
    text: str
    chunk_id: str
    source_section: str | None
    chunk_index: int
    char_start: int
    char_end: int

    @property
    def token_estimate(self) -> int:
        return max(1, len(self.text) // 4)


def chunk_letter(letter: str, max_chunk_chars: int = 800) -> list[TextChunk]:
    """Chunk a clinic letter by detected sections, splitting large sections by sentences."""
    sections = detect_sections(letter)
    chunks: list[TextChunk] = []
    for section in sections:
        if len(section.text) <= max_chunk_chars:
            chunks.append(
                TextChunk(
                    text=section.text,
                    chunk_id=f"{section.name}_0",
                    source_section=section.name,
                    chunk_index=0,
                    char_start=section.start,
                    char_end=section.end,
                )
            )
        else:
            sub = _split_by_sentences(section.text, section.name, section.start, max_chunk_chars)
            chunks.extend(sub)
    return chunks if chunks else [TextChunk(
        text=letter,
        chunk_id="body_0",
        source_section="body",
        chunk_index=0,
        char_start=0,
        char_end=len(letter),
    )]


def select_chunks_for_family(
    chunks: list[TextChunk],
    field_family: FieldFamily,
    max_chunks: int = 3,
) -> tuple[list[TextChunk], list[str]]:
    """Return (selected_chunks, warnings) for the given field family.

    Prefers section-affinity matches; falls back to keyword scoring.
    """
    affinity_chunks = [
        c for c in chunks
        if c.source_section and _section_has_affinity(c.source_section, field_family)
    ]
    if affinity_chunks:
        return affinity_chunks[:max_chunks], []

    from epilepsy_extraction.retrieval.candidates import FIELD_PATTERNS

    pattern = FIELD_PATTERNS.get(field_family)
    if pattern is None:
        return chunks[:max_chunks], ["no_pattern_for_family"]

    scored = sorted(chunks, key=lambda c: len(pattern.findall(c.text)), reverse=True)
    matched = [c for c in scored if pattern.search(c.text)]
    if not matched:
        return chunks[:max_chunks], ["chunk_selection_fallback_all"]
    return matched[:max_chunks], []


def _section_has_affinity(section_name: str, family: FieldFamily) -> bool:
    name = section_name.lower().strip()
    families = _SECTION_FAMILY_AFFINITY.get(name)
    if families is None:
        # Partial match
        for key, fams in _SECTION_FAMILY_AFFINITY.items():
            if key in name or name in key:
                if family in fams:
                    return True
        return False
    return family in families


def _split_by_sentences(
    text: str,
    section_name: str,
    offset: int,
    max_chunk_chars: int,
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    current_parts: list[str] = []
    current_len = 0
    chunk_idx = 0
    pos = 0
    sentences: list[str] = []
    sentence_starts: list[int] = []

    prev = 0
    for m in _SENTENCE_RE.finditer(text):
        sent = text[prev : m.start()].strip()
        if sent:
            sentences.append(sent)
            sentence_starts.append(offset + prev)
        prev = m.end()
    if prev < len(text):
        rem = text[prev:].strip()
        if rem:
            sentences.append(rem)
            sentence_starts.append(offset + prev)

    for i, sent in enumerate(sentences):
        if current_len + len(sent) > max_chunk_chars and current_parts:
            joined = " ".join(current_parts)
            chunks.append(TextChunk(
                text=joined,
                chunk_id=f"{section_name}_{chunk_idx}",
                source_section=section_name,
                chunk_index=chunk_idx,
                char_start=sentence_starts[pos],
                char_end=sentence_starts[pos] + len(joined),
            ))
            chunk_idx += 1
            current_parts = []
            current_len = 0
            pos = i
        current_parts.append(sent)
        current_len += len(sent) + 1

    if current_parts:
        joined = " ".join(current_parts)
        chunks.append(TextChunk(
            text=joined,
            chunk_id=f"{section_name}_{chunk_idx}",
            source_section=section_name,
            chunk_index=chunk_idx,
            char_start=sentence_starts[pos] if sentence_starts else offset,
            char_end=sentence_starts[pos] + len(joined) if sentence_starts else offset + len(joined),
        ))
    return chunks
