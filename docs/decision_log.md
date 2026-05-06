# Decision Log

This log records project decisions that affect scope, evaluation, or interpretation. Keep entries short and traceable.

## 2026-05-06: Milestone 1 Executable Contract

Decision: Milestone 1 is complete when the hand-authored EA0001 canonical extraction validates structurally, all evidence quotes appear in the source letter after conservative normalization, and all manual field expectations pass.

Rationale: This gives the schema and scoring lock an executable exit criterion before model prompts, data splits, or gold-loader code are introduced.

Artifacts: `docs/scoring/milestone_1_scoring_spec.md`, `examples/sample_canonical_extraction.json`, `examples/sample_scoring_expectations.json`, and `src/validate_extraction.py`.

Command: `python3 src/validate_extraction.py examples/sample_canonical_extraction.json --source "data/ExECT 2 (2025)/Gold1-200_corrected_spelling/EA0001.txt" --expectations examples/sample_scoring_expectations.json`

## 2026-05-06: Milestone 2 Intake Contract

Decision: ExECTv2 intake uses a deterministic SHA-256 split with salt `exectv2-fixed-splits-v1`, a 120/40/40 development/validation/test partition, and a BRAT loader that logs quote-normalization mismatches without modifying gold annotations.

Rationale: Fixed splits prevent prompt iteration from leaking into validation or test data, and explicit mismatch logging keeps ExECTv2 offset and annotation-text quirks visible to later evidence scoring.

Artifacts: `docs/08_data_intake.md`, `data/manifests/dataset_manifest.json`, `data/splits/exectv2_splits.json`, and `src/intake.py`.

Command: `python3 src/intake.py check-one EA0001 --max-mismatches 10`

## 2026-05-06: Primary Evaluation Limited To ExECTv2-Native Fields

Decision: Primary quantitative evaluation will use fields natively captured by ExECTv2: current ASM name/dose/unit/frequency, seizure frequency with temporal scope, seizure type, EEG/MRI result where stated, and diagnosis/type.

Rationale: ExECTv2 provides public, reproducible, span-level gold labels for these fields. Using only native labels keeps the main event-first versus direct extraction comparison defensible.

Implication: Previous/stopped/planned medication status and requested/pending/unavailable investigation status move to extension or robustness analyses unless manually adjudicated.

Affected docs: `docs/01_scope_and_research_questions.md`, `docs/02_canonical_schema.md`, `docs/03_pipeline_design.md`, `docs/04_evaluation_protocol.md`, `docs/05_implementation_roadmap.md`, `docs/07_dataset_rationale.md`.
