"""Prompt contracts for maintained benchmark extraction harnesses."""

from __future__ import annotations

from typing import Any

from .labels import benchmark_label_block

INTERNAL_PROMPT_STYLE = "internal"
SANITIZED_PROMPT_STYLE = "clinician"
PROMPT_STYLES = {INTERNAL_PROMPT_STYLE, SANITIZED_PROMPT_STYLE}


def _validate_prompt_style(prompt_style: str) -> None:
    if prompt_style not in PROMPT_STYLES:
        styles = ", ".join(sorted(PROMPT_STYLES))
        raise ValueError(f"unknown prompt_style={prompt_style!r}; expected one of: {styles}")


def _harness_section(harness_id: str, prompt_style: str) -> list[str]:
    if prompt_style == INTERNAL_PROMPT_STYLE:
        return [f"## Harness\n{harness_id}"]
    return []


def _field_intro(prompt_style: str, *, rich: bool = False) -> str:
    if prompt_style == INTERNAL_PROMPT_STYLE:
        return (
            "Extract clinical fields from this epilepsy clinic letter."
            if rich
            else "Extract only benchmark fields from this epilepsy clinic letter."
        )
    return (
        "Extract the requested current clinical fields from this epilepsy clinic letter."
        if rich
        else "Extract the requested current epilepsy fields from this clinic letter."
    )


def h6_few_shot_examples() -> str:
    """Synthetic few-shot examples for current seizure-status edge cases."""
    return "\n".join(
        [
            "## Examples",
            "",
            "Example 1 -- patient has ongoing seizures but type is not specified in the letter:",
            'Letter excerpt: "She continues to have approximately two episodes per month. We plan to review her medication at the next visit."',
            'Output: {"medication_names":["lamotrigine"],"seizure_types":["unknown seizure type"],"epilepsy_diagnosis_type":"epilepsy"}',
            "",
            "Example 2 -- patient is currently seizure-free:",
            'Letter excerpt: "He has been completely seizure-free for the past ten months since starting levetiracetam."',
            'Output: {"medication_names":["levetiracetam"],"seizure_types":["seizure free"],"epilepsy_diagnosis_type":"juvenile myoclonic epilepsy"}',
            "",
            "Example 3 -- letter mentions past seizure type but patient is now seizure-free:",
            'Letter excerpt: "Previously had tonic clonic seizures, but has had no further events since sodium valproate was introduced two years ago."',
            'Output: {"medication_names":["sodium valproate"],"seizure_types":["seizure free"],"epilepsy_diagnosis_type":"generalized epilepsy"}',
        ]
    )


def h6full_examples() -> str:
    """Few-shot examples using structured medications and investigation fields."""
    return "\n".join(
        [
            "## Examples",
            "",
            "Example 1 -- named current seizure type, frequency stated, EEG done:",
            'Letter excerpt: "She continues to have focal impaired awareness seizures approximately twice a month. '
            'EEG showed left temporal spikes. Lamotrigine 100mg twice daily."',
            '{"medications":[{"name":"lamotrigine","dose":"100","unit":"mg","frequency":"twice daily"}],'
            '"seizure_types":["focal seizure"],"epilepsy_diagnosis_type":"focal epilepsy",'
            '"current_seizure_frequency":"2 per month","investigations":{"eeg":"abnormal","mri":null}}',
            "",
            "Example 2 -- seizures ongoing but type not specified in letter:",
            'Letter excerpt: "She continues to have approximately two episodes per month. EEG showed generalised discharges. Lamotrigine 100mg twice daily."',
            '{"medications":[{"name":"lamotrigine","dose":"100","unit":"mg","frequency":"twice daily"}],'
            '"seizure_types":["unknown seizure type"],"epilepsy_diagnosis_type":"epilepsy",'
            '"current_seizure_frequency":"2 per month","investigations":{"eeg":"abnormal","mri":null}}',
            "",
            "Example 3 -- currently seizure-free, no investigations mentioned:",
            'Letter excerpt: "He has been completely seizure-free for the past ten months since starting levetiracetam 1000mg twice daily."',
            '{"medications":[{"name":"levetiracetam","dose":"1000","unit":"mg","frequency":"twice daily"}],'
            '"seizure_types":["seizure free"],"epilepsy_diagnosis_type":"juvenile myoclonic epilepsy",'
            '"current_seizure_frequency":null,"investigations":{"eeg":null,"mri":null}}',
            "",
            "Example 4 -- letter mentions past seizure type but patient is now seizure-free:",
            'Letter excerpt: "Previously had tonic clonic seizures, but has had no further events since sodium valproate was introduced two years ago. MRI was normal."',
            '{"medications":[{"name":"sodium valproate","dose":null,"unit":null,"frequency":null}],'
            '"seizure_types":["seizure free"],"epilepsy_diagnosis_type":"generalized epilepsy",'
            '"current_seizure_frequency":null,"investigations":{"eeg":null,"mri":"normal"}}',
        ]
    )


def build_h6_prompt(document: dict[str, Any], harness_id: str, prompt_style: str = INTERNAL_PROMPT_STYLE) -> str:
    _validate_prompt_style(prompt_style)
    return "\n\n".join(
        [
            _field_intro(prompt_style),
            "Return JSON only with this shape:",
            '{"medication_names":[],"seizure_types":[],"epilepsy_diagnosis_type":null}',
            "Medication names should include current anti-seizure medications only. Use generic drug names where possible.",
            "Seizure types must use only the allowed labels. Do not include aura, warning, symptom, medication side effect, investigation finding, or differential diagnosis labels as seizure types.",
            "Epilepsy diagnosis/type must use one allowed label or null. Do not invent a diagnosis if the letter does not support one.",
            benchmark_label_block(),
            *_harness_section(harness_id, prompt_style),
            "## Source Letter",
            document["text"],
        ]
    )


def build_h6fs_prompt(document: dict[str, Any], harness_id: str, prompt_style: str = INTERNAL_PROMPT_STYLE) -> str:
    _validate_prompt_style(prompt_style)
    return "\n\n".join(
        [
            _field_intro(prompt_style),
            "Return JSON only with this shape:",
            '{"medication_names":[],"seizure_types":[],"epilepsy_diagnosis_type":null}',
            "Medication names should include current anti-seizure medications only. Use generic drug names where possible.",
            "Seizure types must use only the allowed labels. Do not include aura, warning, symptom, medication side effect, investigation finding, or differential diagnosis labels as seizure types.",
            "Epilepsy diagnosis/type must use one allowed label or null. Do not invent a diagnosis if the letter does not support one.",
            benchmark_label_block(),
            h6_few_shot_examples(),
            *_harness_section(harness_id, prompt_style),
            "## Source Letter",
            document["text"],
        ]
    )


def build_h6full_prompt(document: dict[str, Any], harness_id: str, prompt_style: str = INTERNAL_PROMPT_STYLE) -> str:
    _validate_prompt_style(prompt_style)
    schema = (
        '{"medications":[{"name":"...","dose":"...","unit":"...","frequency":"..."}],'
        '"seizure_types":[],"epilepsy_diagnosis_type":null,'
        '"current_seizure_frequency":null,'
        '"investigations":{"eeg":null,"mri":null}}'
    )
    return "\n\n".join(
        [
            _field_intro(prompt_style, rich=True),
            f"Return JSON only with this shape:\n{schema}",
            (
                "medications: list current anti-seizure medications only. "
                "Each entry must have a name. Include dose (number only), unit (mg/mcg/g/ml), "
                "and frequency (once daily / twice daily / three times daily / nocte / as required) "
                "if stated; use null for any component not mentioned. "
                "Use generic drug names where possible."
            ),
            (
                "Seizure types must use only the allowed labels. "
                "Include only the patient's CURRENT seizure types as documented in this letter - "
                "do not include historical seizure types that are no longer occurring. "
                "If the patient has seizures but the specific type is not described or is unclear in the letter, "
                "use 'unknown seizure type'. "
                "Do not include aura, warning, symptom, medication side effect, "
                "investigation finding, or differential diagnosis labels as seizure types."
            ),
            "Epilepsy diagnosis/type must use one allowed label or null. Do not invent a diagnosis if the letter does not support one.",
            (
                'current_seizure_frequency: copy the frequency expression from the letter as a short string '
                '(e.g. "2 per month", "daily", "every 6 weeks") or null if not stated or patient is seizure-free.'
            ),
            (
                'investigations.eeg: normalized result - use "normal", "abnormal", or null. '
                "Do not copy the raw EEG description; classify it as normal or abnormal. "
                "Same for investigations.mri."
            ),
            benchmark_label_block(),
            h6full_examples(),
            *_harness_section(harness_id, prompt_style),
            "## Source Letter",
            document["text"],
        ]
    )


def prompt_artifact_report(prompt: str, harness_id: str | None = None) -> dict[str, Any]:
    """Return prompt artefacts that can bias an extraction run toward internals."""
    lower_prompt = prompt.lower()
    artefacts = {
        "mentions_harness": "## harness" in lower_prompt or (harness_id is not None and harness_id.lower() in lower_prompt),
        "mentions_benchmark": "benchmark" in lower_prompt,
        "mentions_pass": "pass 1 of 2" in lower_prompt or "pass 2 of 2" in lower_prompt,
        "mentions_nearest_allowed_benchmark_label": "nearest allowed benchmark label" in lower_prompt,
        "mentions_pipeline_id": "pipeline_id" in lower_prompt,
    }
    return {
        "harness_id": harness_id,
        "artefacts": artefacts,
        "artefact_count": sum(1 for found in artefacts.values() if found),
    }
