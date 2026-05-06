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
- Medication status accuracy.
- Dose exact match and relaxed match.
- Current seizure-frequency normalized-value accuracy.
- Seizure-frequency temporal accuracy.
- Seizure type F1.
- EEG status/result F1.
- MRI status/result F1.
- Diagnosis/type exact or partial match.
- Missingness accuracy.

## Evidence Metrics

- Evidence quote present rate.
- Quote validity: quote appears in source text.
- Evidence support: quote supports the extracted value and temporality.
- Evidence overlap with annotated span where available.
- Unsupported extraction rate.

Quote validity and evidence support should be reported separately.

## Format Metrics

- Parse success rate.
- Repair rate.
- Repair success rate.
- Schema validity.
- Type correctness.
- Output token count.

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
