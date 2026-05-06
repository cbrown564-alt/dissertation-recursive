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

## 2026-05-06: Milestone 3 Direct Baseline Harness

Decision: Milestone 3 is complete for the first executable harness when S1, S2, and S3 can run over a small development subset with prompt generation, raw response capture, parse/repair handling, canonical JSON output, JSON Schema validation, evidence-layer logging, and JSONL run metadata.

Rationale: This creates the direct-baseline comparison surface before event-first extraction is implemented. The stub provider verifies the pipeline mechanics without treating empty outputs as clinical extraction results.

Artifacts: `docs/09_direct_baselines.md`, `src/direct_baselines.py`, `prompts/direct_baselines/`, `requirements.txt`, and updates to `src/validate_extraction.py`.

Command: `.venv/bin/python src/direct_baselines.py run --provider stub --limit 2 --output-dir runs/milestone_3_stub_compact_log`

## 2026-05-06: JSON Schema As Structural Validator

Decision: `schemas/canonical_extraction.schema.json` is the authoritative structural contract. `src/validate_extraction.py` now uses `jsonschema` for schema validation and keeps custom Python checks for project-specific rules.

Rationale: JSON Schema prevents drift between the machine-readable contract and runtime validation, while custom checks remain necessary for duplicate event IDs, present-field evidence requirements, quote validity, and later semantic/temporal support scoring.

Implication: Runtime dependencies are declared in `requirements.txt`; validation commands should run inside a local `.venv`.

## 2026-05-06: Direct Baseline Formats And Repair Boundary

Decision: S1 emits direct canonical JSON without required evidence, S2 emits canonical JSON with evidence, and S3 emits YAML that is parsed into canonical JSON before scoring. JSON remains the only canonical scoring format.

Rationale: S1 tests the simplest structured extraction baseline, S2 is the primary direct evidence comparator, and S3 isolates model-facing format effects without changing downstream scoring.

Repair policy: allow one syntax-level repair attempt only. JSON repair may strip Markdown wrappers/preambles and trailing commas. YAML repair may strip Markdown wrappers and replace tabs with spaces. Repairs must not add clinical values or evidence.

## 2026-05-06: Local API Key Loading

Decision: `src/direct_baselines.py` loads a local `.env` file before OpenAI calls, but only fills environment variables that are not already exported.

Rationale: This keeps local model runs ergonomic while preserving shell-provided overrides and keeping secrets out of version control.

Implication: `.env`, `.venv/`, `runs/`, caches, and `.DS_Store` are ignored by the root `.gitignore`.

## 2026-05-06: Milestone 5 Evaluation Harness

Decision: Milestone 5 is complete for the first executable scorer when `src/evaluate.py` can score existing S2, E2, and E3 canonical outputs from a fixed split and write aggregate JSON, per-document JSON, and a CSV comparison table.

Rationale: Direct and event-first systems now share a canonical JSON contract, so evaluation can be separated from extraction. The first scorer keeps field correctness, quote presence, quote validity, evidence overlap, temporal support heuristics, and cost/latency metadata as separate layers instead of collapsing them into one opaque accuracy number.

Artifacts: `docs/11_evaluation_harness.md`, `src/evaluate.py`, and updates to `docs/05_implementation_roadmap.md`.

Command: `.venv/bin/python src/evaluate.py run --split development --limit 2 --systems E2 E3 --event-run-dir runs/milestone_4_stub_check_venv_2 --output-dir runs/milestone_5_stub_eval`

## 2026-05-06: Milestone 6 Robustness Harness

Decision: Milestone 6 is complete for the first executable robustness harness when perturbations can be generated as a runner-compatible corpus, marked by label effect, run through S2/E2/E3, and summarized as field-level degradation tables for label-preserving cases.

Rationale: Robustness needs to stay paired with the primary event-first comparison without treating deliberately label-changing challenge cases as ordinary ExECTv2 gold-label errors. Gan 2026 is kept as a seizure-frequency stress source rather than a replacement benchmark.

Artifacts: `docs/12_robustness_tests.md`, `src/robustness.py`, and updates to `docs/05_implementation_roadmap.md`.

Command: `.venv/bin/python src/robustness.py generate --split validation --limit 5 --include-gan --gan-limit 5 --output-dir runs/robustness && .venv/bin/python src/robustness.py run-systems --provider stub --output-dir runs/robustness && .venv/bin/python src/robustness.py evaluate --output-dir runs/robustness`

## 2026-05-06: Milestone 7 JSON Versus YAML-To-JSON Comparison

Decision: The controlled format comparison uses S2 direct JSON with evidence and S3 YAML-to-JSON with evidence over the same document IDs, then scores both through the canonical JSON evaluator. S3 is accepted by `src/evaluate.py` only as a direct-run system for this secondary analysis.

Rationale: JSON remains the canonical scoring format, so YAML is tested as a model-facing output condition rather than a separate downstream contract. Reusing the evaluator keeps schema validity, quote validity, evidence support, field accuracy, cost, and latency comparable with the primary pipeline results.

Artifacts: `docs/13_secondary_analyses.md`, `src/secondary_analyses.py`, updates to `src/evaluate.py`, `docs/11_evaluation_harness.md`, `README.md`, and `docs/05_implementation_roadmap.md`.

Command: `.venv/bin/python src/secondary_analyses.py json-yaml --split development --limit 2 --direct-run-dir runs/milestone_3_stub --output-dir runs/milestone_7_json_yaml_stub`

## 2026-05-06: Milestone 7 Bounded Model-Family Comparison

Decision: The open/local versus closed/frontier comparison is implemented as a secondary artifact scorer over named conditions in the form `LABEL:FAMILY:SYSTEM:RUN_DIR`, rather than as a model-calling runner or leaderboard. Supported scored systems are S2, S3, E2, and E3.

Rationale: The dissertation question is whether event-first, evidence-grounded extraction improves reliability. Model-family effects should therefore be measured on matched existing artifacts with the same documents, prompts, and pipeline outputs, while missing artifacts remain visible as unavailable.

Implication: Reports include parseability, schema validity, evidence layers, temporal support, field accuracy, latency, token counts, and estimated cost where metadata exists. Optional reference-condition deltas support compact open/local versus closed/frontier comparisons without displacing the primary S2 versus E2/E3 analysis.

Artifacts: `docs/13_secondary_analyses.md`, `src/secondary_analyses.py`, updates to `src/evaluate.py`, `README.md`, and `docs/05_implementation_roadmap.md`.

Command: `.venv/bin/python src/secondary_analyses.py model-compare --split development --limit 2 --condition local_stub:local:S2:runs/milestone_3_stub --condition frontier_stub:closed:S3:runs/milestone_3_stub --reference-condition local_stub --output-dir runs/milestone_7_model_compare_stub`

## 2026-05-06: Matched Final Artifact Orchestration

Decision: The final validation work should be launched through `src/final_runs.py`, which binds direct baselines, event-first extraction, primary evaluation, robustness, secondary analyses, write-up support, and dashboard export into one run-rooted artifact chain.

Rationale: The milestone scripts are useful independently, but dissertation claims need matched artifacts from the same split, provider, model, and run root. A single orchestration command reduces drift between primary tables, robustness outputs, secondary checks, and the dashboard.

Artifacts: `src/final_runs.py`, updates to `docs/05_implementation_roadmap.md`, and updates to `README.md`.

Command: `.venv/bin/python src/final_runs.py build --provider openai --model gpt-4.1-mini`
