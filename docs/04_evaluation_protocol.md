# Evaluation Protocol

## Primary Comparison

The primary comparison is:

- S2: direct extraction with evidence
- E2/E3: event-first extraction with evidence and aggregation

Both conditions require evidence. The main difference is whether the model extracts final fields directly or first extracts temporally qualified events.

## Dataset Plan

Initial benchmark:

- Public synthetic annotated epilepsy clinic-letter corpus.

Optional external validation:

- De-identified real clinic letters, only if available through appropriate governance.

## Splits

Before prompt optimization:

- Lock development, validation, and final test splits.
- Use development data for prompt iteration.
- Use validation data for choosing pipeline variants.
- Use the final test set once for the main reported comparison.

## Field Metrics

- Medication name precision, recall, and F1.
- Medication status accuracy across current, previous, stopped, declined, planned, increased, and reduced.
- Dose exact match and relaxed match.
- Current seizure-frequency normalized-value accuracy.
- Seizure-frequency temporal accuracy.
- Seizure-frequency temporal-scope accuracy.
- Seizure-frequency seizure-type linkage accuracy where stated.
- Seizure type F1.
- EEG status F1 and EEG result F1, reported separately.
- MRI status F1 and MRI result F1, reported separately.
- Diagnosis/type exact or partial match.
- Missingness accuracy.

Investigation status labels should include requested, pending, completed, unavailable, not stated, and uncertain. Investigation result labels should include normal, abnormal, not stated, and uncertain.

## Evidence Metrics

- Evidence quote present rate.
- Quote validity: quote appears in source text.
- Semantic support: quote supports the extracted value.
- Temporal support: quote supports the extracted temporality or status.
- Evidence overlap with annotated span where available.
- Field correctness: extracted normalized value matches the gold field.
- Unsupported extraction rate.

Quote validity, semantic support, temporal support, and field correctness should be reported separately. Exact quote matching is necessary for quote validity, but not sufficient for evidence support.

## Format Metrics

- Parse success rate.
- Repair rate.
- Repair success rate.
- Schema validity.
- Type correctness.
- Output token count.

JSON is the canonical scoring format. YAML-to-JSON should be treated as a secondary model-facing comparison, with parseability, repair, and schema-validity metrics reported separately from clinical accuracy.

## Reliability Metrics

- Abstention quality for absent fields.
- Robustness under perturbation.
- Stability across repeated runs where budget allows.
- Cost per correctly supported field.
- Latency per letter.

## Robustness Perturbations

Perturbations should be documented as label-preserving or label-changing.

Initial perturbation set:

- Reordered sections.
- Removed headings.
- Bullet lists converted to prose.
- Added historical medication mentions.
- Added planned medication changes.
- Added family-history traps.
- Added negation.
- Temporal contrast, such as "previously weekly, now seizure-free".
- Investigation ambiguity, such as "MRI requested" versus "MRI normal".

## Statistical Analysis

Use paired comparisons because systems run on the same letters. Report field-specific results rather than only an aggregate score.

Model comparisons should be small and controlled. They should emphasize whether event-first extraction changes reliability under the same conditions rather than ranking a broad set of models.

Primary fields for event-first benefit:

- seizure frequency,
- medication status,
- EEG/MRI status,
- seizure type,
- diagnosis/type.

## Reporting Rule

Every result table should make clear whether a value is:

- correct,
- evidence-supported,
- temporally correct,
- parseable,
- and costed.
