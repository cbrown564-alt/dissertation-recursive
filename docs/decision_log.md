# Decision Log

This log records project decisions that affect scope, evaluation, or interpretation. Keep entries short and traceable.

## 2026-05-06: Primary Evaluation Limited To ExECTv2-Native Fields

Decision: Primary quantitative evaluation will use fields natively captured by ExECTv2: current ASM name/dose/unit/frequency, seizure frequency with temporal scope, seizure type, EEG/MRI result where stated, and diagnosis/type.

Rationale: ExECTv2 provides public, reproducible, span-level gold labels for these fields. Using only native labels keeps the main event-first versus direct extraction comparison defensible.

Implication: Previous/stopped/planned medication status and requested/pending/unavailable investigation status move to extension or robustness analyses unless manually adjudicated.

Affected docs: `docs/01_scope_and_research_questions.md`, `docs/02_canonical_schema.md`, `docs/03_pipeline_design.md`, `docs/04_evaluation_protocol.md`, `docs/05_implementation_roadmap.md`, `docs/07_dataset_rationale.md`.
