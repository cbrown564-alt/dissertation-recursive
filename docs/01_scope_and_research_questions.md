# Scope and Research Questions

## Core Aim

Determine whether event-first, evidence-grounded extraction improves the reliability of structured information extraction from epilepsy clinic letters compared with direct structured extraction.

## Primary Research Question

Does extracting temporally qualified clinical events before deriving final fields improve field-level accuracy, temporal correctness, and evidence support compared with extracting final structured fields directly?

## Secondary Research Questions

1. Does requiring exact evidence spans reduce unsupported extractions, and how does it affect precision, recall, and abstention?
2. Does event-first extraction improve robustness under realistic letter perturbations?
3. Does model-facing output format, especially JSON versus YAML-to-JSON, affect parseability, schema validity, repair rate, or accuracy?
4. How do a small number of open/local and closed/frontier models compare under the same extraction conditions?

## Main Hypothesis

Event-first, evidence-grounded extraction will improve reliability for temporally complex epilepsy fields compared with direct structured extraction. The primary expected benefit should be clearest for seizure frequency, where ExECTv2 provides native gold annotations for temporal scope, seizure counts, ranges, and seizure-free statements.

## Target Fields

Primary scored field definitions should follow the ExECT/ExECTv2 target categories and should be limited to fields natively captured by the public ExECTv2 annotations:

- Current anti-seizure medications.
- Medication dose, dose unit, and dosing frequency where stated or defined by the ExECTv2 annotation guidance.
- Current seizure frequency and temporal scope.
- Seizure type.
- EEG result where stated.
- MRI result where stated.
- Epilepsy diagnosis or epilepsy type where stated.

Event-first extraction should require intermediate events for medication, seizure frequency, seizure type, investigation, and diagnosis claims before deriving these final fields.

Extension fields may be explored through manual challenge sets or perturbations, but should not carry the primary quantitative claim unless separately adjudicated:

- Previous, stopped, declined, planned, increased, or reduced medication status.
- Requested, pending, unavailable, or planned EEG/MRI status.
- Other non-ExECTv2 investigation-state distinctions.

## Implementation Decisions

- Temporality labels should include `current`, `historical`, `planned`, `requested`, `completed`, `family_history`, `hypothetical`, and `uncertain`.
- Missingness labels should stay separate from temporality. `not_stated`, `uncertain`, `conflicting`, and `not_applicable` answer different scoring questions.
- Evidence support should be evaluated in layers: quote presence, quote validity, semantic support, temporal support, and field correctness.
- Exact quote matching is necessary for mechanical evidence validation, but not sufficient for semantic evidence support.
- Seizure frequency normalization should retain temporal scope and seizure type linkage where stated.
- Primary medication scoring should use ExECTv2-native current ASM annotations: drug name, dose, dose unit, and frequency.
- Primary investigation scoring should use ExECTv2-native completed investigation results: EEG/MRI normal, abnormal, or unknown where annotated.
- Broader medication-status and investigation-status labels may remain in the event schema for exploratory analysis, but should be reported separately from primary EXeCTv2-native accuracy.
- JSON should be the canonical scoring format. YAML-to-JSON is a secondary model-facing comparison only.
- Model comparisons should be small and controlled, emphasizing whether event-first extraction changes reliability rather than ranking models.

## In Scope

- Training-free or minimal-training LLM extraction.
- Direct extraction baselines.
- Event-first extraction with evidence spans.
- Deterministic or constrained aggregation from events to final fields.
- Schema validation, parseability, evidence checking, and repair logging.
- Robustness tests for temporal ambiguity, negation, family history, planned changes, and investigation ambiguity, reported as extension analyses when they involve non-ExECTv2-native labels.
- Small, controlled model-family and output-format comparisons.

## Out of Scope

- Fine-tuning.
- Broad multi-agent architectures.
- Unbounded self-consistency.
- Autoresearch loops.
- Live clinical deployment.
- Claims of clinical safety without external validation.
- Broad model leaderboards.

## Success Criteria

The project succeeds if it can provide a reproducible answer to whether event-first extraction improves reliability enough to justify its added complexity, cost, and latency.
