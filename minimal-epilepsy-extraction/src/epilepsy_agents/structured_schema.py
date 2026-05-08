from __future__ import annotations


def extract_json_object(content: str) -> str:
    """Recover a JSON object from common local-model wrappers without storing raw output."""
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    start = stripped.find("{")
    if start == -1:
        return stripped

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(stripped)):
        char = stripped[index]
        if escape:
            escape = False
            continue
        if char == "\\" and in_string:
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return stripped[start : index + 1]
    return stripped


EXTRACTION_JSON_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "label": {
            "type": "string",
            "description": "Structured seizure-frequency label from the project label scheme.",
        },
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "text": {"type": "string"},
                    "start": {"type": ["integer", "null"]},
                    "end": {"type": ["integer", "null"]},
                    "source": {"type": "string"},
                },
                "required": ["text", "start", "end", "source"],
            },
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "analysis": {
            "type": "string",
            "description": "Brief audit rationale. Do not include hidden chain-of-thought.",
        },
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["label", "evidence", "confidence", "analysis", "warnings"],
}


OPENAI_RESPONSE_FORMAT: dict[str, object] = {
    "type": "json_schema",
    "json_schema": {
        "name": "seizure_frequency_extraction",
        "strict": True,
        "schema": EXTRACTION_JSON_SCHEMA,
    },
}


def system_prompt() -> str:
    return (
        "/no_think\n"
        "You extract seizure-frequency information from epilepsy clinic letters. "
        "Do not include deliberation, hidden reasoning, markdown, or explanatory prose. "
        "Return only JSON conforming to the supplied schema. Use the structured "
        "label scheme: explicit rates such as '2 per week', windows such as "
        "'6 per 7 month', seizure-free durations, cluster labels such as "
        "'2 cluster per month, 6 per cluster', 'unknown', or "
        "'no seizure frequency reference'. Every non-unknown answer must be "
        "supported by quoted evidence from the letter."
    )
