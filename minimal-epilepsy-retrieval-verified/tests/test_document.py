from epilepsy_extraction.document.normalization import normalize_letter, normalize_whitespace
from epilepsy_extraction.document.sections import detect_sections, letter_to_sections_dict


def test_normalize_whitespace_collapses_spaces() -> None:
    assert normalize_whitespace("hello   world") == "hello world"


def test_normalize_whitespace_collapses_blank_lines() -> None:
    result = normalize_whitespace("line1\n\n\n\nline2")
    assert "\n\n\n" not in result
    assert "line1" in result
    assert "line2" in result


def test_normalize_letter_trims_whitespace() -> None:
    assert normalize_letter("  hello  ") == "hello"


def test_detect_sections_returns_body_when_no_headers() -> None:
    letter = "Patient has two seizures per month."
    sections = detect_sections(letter)

    assert len(sections) == 1
    assert sections[0].name == "body"
    assert "two seizures" in sections[0].text


def test_detect_sections_finds_known_header() -> None:
    letter = "Preamble text.\n\nCurrent Medications:\nLamotrigine 100 mg bd\n"
    sections = detect_sections(letter)

    names = [s.name for s in sections]
    assert any("medication" in n for n in names)


def test_detect_sections_includes_preamble_before_first_header() -> None:
    letter = "Some intro text.\n\nAssessment:\nStable.\n"
    sections = detect_sections(letter)

    assert sections[0].name == "preamble"
    assert "intro" in sections[0].text


def test_letter_to_sections_dict_returns_dict() -> None:
    letter = "No headers present in this text."
    result = letter_to_sections_dict(letter)

    assert isinstance(result, dict)
    assert "body" in result
