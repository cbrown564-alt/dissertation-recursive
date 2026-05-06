# Implementation Roadmap

## Milestone 0: Repository Setup

- Add project documentation.
- Add initial JSON Schema.
- Decide directory structure for source code, prompts, data manifests, and reports.

## Milestone 1: Schema And Scoring Lock

Status: complete for the first executable contract. See `docs/scoring/milestone_1_scoring_spec.md`, `examples/sample_canonical_extraction.json`, `examples/sample_scoring_expectations.json`, and `src/validate_extraction.py`.

- Finalize primary canonical field schema around ExECTv2-native fields: current medication name/dose/unit/frequency, current seizure frequency, seizure type, EEG/MRI result, and diagnosis/type.
- Finalize event schema requiring medication, seizure-frequency, seizure-type, investigation, and diagnosis events for the event-first pipeline.
- Define seizure-frequency normalization rules that retain temporal scope and seizure-type linkage where stated.
- Define extension medication status labels: current, previous, stopped, declined, planned, increased, and reduced.
- Define extension investigation status/result labels, separating requested/pending/completed/unavailable status from normal/abnormal/not-stated results.
- Keep primary quantitative scoring limited to labels supported by ExECTv2 unless an extension set is manually adjudicated.
- Define missingness labels separately from temporality.
- Define temporal labels: current, historical, planned, requested, completed, family_history, hypothetical, and uncertain.
- Implement schema validation.
- Write a small scoring specification with examples for quote presence, quote validity, semantic support, temporal support, and field correctness.

Exit criterion: a manually written sample output can be validated and scored.

## Milestone 2: Data Intake

Status: complete for the first executable intake contract. See `docs/08_data_intake.md`, `data/manifests/dataset_manifest.json`, `data/splits/exectv2_splits.json`, and `src/intake.py`.

- Add dataset manifest.
- Add dataset rationale documentation.
- Build preprocessing for letters.
- Assign sentence IDs and offsets.
- Create fixed splits.
- Add a gold-label loader.
- Add quote-normalization rules for ExECTv2 span text, including hyphen/whitespace normalization and mismatch logging.

Exit criterion: one letter can be loaded, preprocessed, and paired with gold labels.

## Milestone 3: Direct Baselines

Status: complete for the first executable harness. See `docs/09_direct_baselines.md`, `src/direct_baselines.py`, and `prompts/direct_baselines/`.

- Implement S1 direct JSON extraction.
- Implement S2 direct JSON extraction with evidence.
- Implement S3 YAML-to-JSON extraction with evidence.
- Add parse, repair, validation, evidence-layer scoring, and logging.
- Keep JSON as the canonical scoring format; treat YAML-to-JSON as a secondary model-facing format comparison.

Exit criterion: direct baselines can run on a small development subset.

## Milestone 4: Event-First Pipeline

- Implement E1 event extraction.
- Implement evidence validation for events.
- Implement E2 deterministic aggregation.
- Add aggregation logging.
- Implement E3 constrained aggregation if deterministic rules are insufficient.
- Ensure aggregation preserves event IDs, temporal scope, seizure-type linkage, current medication dose/frequency, and EEG/MRI result.
- Log non-current medication statuses and non-result investigation statuses as extension outputs.

Exit criterion: event-first extraction can produce canonical JSON for the same subset as direct baselines.

## Milestone 5: Evaluation Harness

- Implement field scoring.
- Implement evidence scoring at quote-presence, quote-validity, semantic-support, temporal-support, and field-correctness levels.
- Implement temporal scoring.
- Implement cost and latency reporting.
- Produce first comparison table for S2 versus E2/E3.

Exit criterion: validation-set results can be reproduced from a single command.

## Milestone 6: Robustness Tests

- Implement perturbation generators.
- Mark perturbations as label-preserving or label-changing.
- Run direct and event-first systems on perturbed letters.
- Compare degradation by field and perturbation type.
- Use Gan 2026 primarily for seizure-frequency stress tests and EXeCTv2-derived/manual cases for broader field perturbations.

Exit criterion: robustness tables identify where event-first extraction helps or fails.

## Milestone 7: Secondary Analyses

- Run controlled JSON versus YAML-to-JSON comparison.
- Run small open/local versus closed/frontier model comparison.
- Report parseability, schema validity, cost, latency, and accuracy.
- Keep model comparisons bounded to the event-first reliability question rather than a broad leaderboard.

Exit criterion: secondary results are bounded and do not displace the primary event-first analysis.

## Milestone 8: Dissertation Write-Up Support

- Convert methods into chapter-ready prose.
- Build reproducible tables and plots.
- Write error analysis examples.
- Document limitations, especially synthetic-data validity and clinical deployment boundaries.

Exit criterion: results and methods can be traced from proposal to code to dissertation tables.
