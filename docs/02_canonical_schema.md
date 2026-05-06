# Canonical Schema

This document defines the first-pass output contract for extraction and scoring. The machine-readable version starts in `schemas/canonical_extraction.schema.json`.

## Design Principles

- Use one canonical JSON representation for scoring, regardless of whether the model emits JSON or YAML.
- Require every asserted value to carry missingness and evidence information.
- Represent temporality explicitly for events and derived fields.
- Keep missingness separate from temporality.
- Separate evidence validity from field correctness.
- Preserve source traceability through exact quotes and optional sentence IDs or character offsets.
- Treat exact quote matching as necessary but not sufficient for evidence support.

## Top-Level Object

The canonical extraction output contains:

- `document_id`
- `pipeline_id`
- `fields`
- `events`
- `metadata`

## Missingness

Every final field should use one of these missingness labels:

- `present` - the value is explicitly stated or directly supported.
- `not_stated` - the letter does not state the value.
- `uncertain` - the letter contains relevant text but the value cannot be confidently resolved.
- `conflicting` - the letter contains incompatible statements that cannot be resolved.
- `not_applicable` - the field does not apply to the patient or letter context.

Models should abstain with `not_stated` or `uncertain` rather than infer unsupported values.

Missingness should not be used as a proxy for temporality. For example, a planned medication increase is `present` as an event with `temporality: planned`, not `uncertain`; an absent MRI result is `not_stated` even if an MRI request is present.

## Temporality

Event temporality should use:

- `current`
- `historical`
- `planned`
- `requested`
- `completed`
- `family_history`
- `hypothetical`
- `uncertain`

Final field temporality should usually be `current`, `historical`, or `uncertain`, depending on the field.

## Evidence Object

Each extracted event and each present final field should include evidence:

```json
{
  "quote": "She remains on lamotrigine 100 mg twice daily.",
  "sentence_id": "s12",
  "char_start": 482,
  "char_end": 533
}
```

Required for first implementation:

- `quote`

Optional but preferred:

- `sentence_id`
- `char_start`
- `char_end`

## Event Object

Events are intermediate evidence-grounded claims. They should not directly replace final fields.

Event categories:

- `medication`
- `seizure_frequency`
- `seizure_type`
- `investigation`
- `diagnosis`

The event-first pipeline should require event objects for all medication, seizure-frequency, seizure-type, investigation, and diagnosis claims. Final fields should be derived from these events and should reference the supporting event IDs.

Common event properties:

- `id`
- `category`
- `temporality`
- `status`
- `value`
- `evidence`

Medication-specific properties:

- `medication_name`
- `dose`
- `route`
- `frequency`
- `status`: `current`, `previous`, `stopped`, `declined`, `planned`, `increased`, `reduced`, `uncertain`, or `not_stated`
- `reason_stopped`

Investigation-specific properties:

- `investigation_type`: `EEG` or `MRI`
- `status`: `requested`, `pending`, `completed`, `unavailable`, `not_stated`, or `uncertain`
- `result`: `normal`, `abnormal`, `not_stated`, or `uncertain`

Seizure-frequency-specific properties:

- `value`
- `temporal_scope`
- `seizure_type`

Seizure frequency normalization should preserve temporal scope and seizure-type linkage where stated. "Previously monthly but now seizure-free" should create separate historical and current seizure-frequency events.

## Final Field Rules

Current medications should be derived from medication events with `temporality: current`. Previous medications should be derived from medication events with `temporality: historical` or a status indicating stopped, discontinued, or previously tried.

Current seizure frequency should prefer explicitly current or most recent statements. Historical frequencies should not override a current seizure-free statement.

EEG and MRI fields should distinguish request/completion status from results. "MRI requested" is not equivalent to "MRI normal"; "MRI unavailable" should not be scored as a normal result.

Diagnosis/type should be conservative. If the letter discusses possible epilepsy without a stated diagnosis, use `uncertain` rather than inventing an epilepsy type.

## Evidence Support

Evidence should be scored in layers:

- quote presence,
- quote validity,
- semantic support,
- temporal support,
- field correctness.

Quote validity means the evidence quote appears in the source text after agreed normalization. Semantic support means the quote supports the extracted value. Temporal support means the quote also supports the extracted temporality or status.
