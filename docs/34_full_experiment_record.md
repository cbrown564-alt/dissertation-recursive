# Full Experiment Record

**Date:** 2026-05-11  
**Scope:** Every harness, model, and experimental run in `/runs` since project inception.  
**Purpose:** Authoritative single-document record of what was tested, why, what happened, and what we learned. Supersedes any partial summaries.  
**Status:** Complete through G4-Retrieval and MA_v1 stages MA1–MA3 (May 11, 2026). G4-Full and final full-field runs are pending.

---

## How to Read This Document

Section 1 describes the dataset, schema, and infrastructure that all experiments share. Sections 2–6 cover the five experimental workstreams in the order they ran: (2) stub/milestone plumbing runs, (3) model expansion, (4) performance recovery and scoring repair, (5) local models (including multi-agent MA_v1), (6) seizure frequency. Section 7 is a cross-cutting synthesis. Section 8 is a live status table of pending runs.

---

## 1. Shared Infrastructure

### 1.1 Dataset: ExECTv2

The primary dataset is ExECTv2 — 200 synthetic NHS-style epilepsy clinic letters with expert annotations for medications (name, dose, unit, frequency), seizure types, seizure frequency, EEG/MRI investigations, and epilepsy diagnosis. Letters were split deterministically (SHA-256 salt: `exectv2-fixed-splits-v1`):

- **Development:** 120 documents (used for exploration, debugging, and prompt engineering)
- **Validation:** 40 documents (used for tuning decisions and model selection)
- **Test:** 40 documents (used once for final claims; held out during all recovery work)

### 1.2 Secondary Dataset: Gan 2026

`data/Gan (2026)/synthetic_data_subset_1500.json` — 1,500 synthetic NHS-style clinic letters with normalized seizure-frequency labels, structured evidence references, and rationale fields. This is the local synthetic subset of the data released by Gan et al. 2026 (*Reproducible Synthetic Clinical Letters for Seizure Frequency Information Extraction*). **Important caveat:** Gan's published Pragmatic micro-F1 targets (0.847, 0.858) were measured on a separately produced clinician double-checked real-letter test set, not on this released synthetic subset.

Pragmatic class distribution in the 1,500-example subset: frequent=757, UNK=264, infrequent=256, NS=223.

### 1.3 Output Schema

All experiments target `schemas/canonical_extraction.schema.json`, a JSON object containing:

- `medications`: list of `{name, dose, unit, frequency, evidence_quote, event_ids}`
- `seizure_types`: list of `{label, evidence_quote, event_ids}`
- `seizure_frequency`: `{value, period, evidence_quote}` (single current value)
- `eeg_result`, `mri_result`: categorical with evidence
- `epilepsy_diagnosis`: `{label, type, evidence_quote}`
- Temporal scope markers throughout

### 1.4 External Benchmark Anchor

**Fang et al. 2025** (*Extracting epilepsy-related information from unstructured clinic letters using large language models*, Epilepsia 2025;66:3369–3384). Targets derived from this paper:


| Task                           | Recovery target |
| ------------------------------ | --------------- |
| Epilepsy type / diagnosis      | F1 ≥ 0.80       |
| Seizure type                   | F1 ≥ 0.76       |
| Current ASMs (medication name) | F1 ≥ 0.90       |
| Full medication tuple          | F1 ≥ 0.80       |


Fang used King's College Hospital real letters; the project uses ExECTv2 synthetic letters. The benchmark is an external performance anchor, not a direct replication.

### 1.5 Harness Vocabulary

The project has used the following named harness contracts:


| ID                           | Description                                                                                                                                                                                                                                  |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| H0 / strict canonical        | Full canonical JSON schema with evidence quotes; local project schema                                                                                                                                                                        |
| H1 (repaired canonical)      | Same as H0 but with robust parse repair and normalization before scoring                                                                                                                                                                     |
| H2 (task-specific)           | Separate compact prompts per benchmark field; no full-schema output                                                                                                                                                                          |
| H3 (loose answer-then-parse) | Model answers in prose/lists; deterministic parse into canonical fields                                                                                                                                                                      |
| H4 (json_mode)               | Provider-native JSON enforcement; minimal schema constraint                                                                                                                                                                                  |
| H5 (verifier relaxed)        | Candidate extraction plus keep/drop/normalize verifier                                                                                                                                                                                       |
| H6 (benchmark-only JSON)     | Compact JSON prompt restricted to benchmark-aligned fields; no full schema                                                                                                                                                                   |
| H6fs                         | H6 + three few-shot seizure-type examples targeting dominant failure modes                                                                                                                                                                   |
| H6v2                         | H6 + explicit `unknown seizure type` guidance and temporality restriction                                                                                                                                                                    |
| H6qa                         | H6 + decomposed `current_seizure_status` field as a constraint                                                                                                                                                                               |
| H6ev                         | H6 + `seizure_evidence` quote field as a null-suppression constraint                                                                                                                                                                         |
| H6full                       | H6 extended with dose/unit/freq/EEG/MRI/seizure_freq fields                                                                                                                                                                                  |
| H7 (two-pass)                | Extract in pass 1; normalize/aggregate in pass 2                                                                                                                                                                                             |
| H8 (evidence later)          | Extract without evidence in pass 1; resolve evidence in pass 2                                                                                                                                                                               |
| D3 (candidate+verifier)      | Candidate extraction followed by a keep/drop/normalize verifier call                                                                                                                                                                         |
| EL_micro_events              | Flat event array (type/value/quote/current), three fields per event; simplest possible event-first format for local models                                                                                                                   |
| EL_compact_events            | Typed event array with dose/unit/frequency/modality fields; richer than EL_micro but still simpler than full E1                                                                                                                              |
| EL_E1E2_full                 | Full E1 event extraction (existing frontier prompt) + deterministic E2 aggregation, run on local models                                                                                                                                      |
| Gan_direct_label             | Single-call Gan-normalized frequency label extraction                                                                                                                                                                                        |
| Gan_cot_label                | Single call with internal CoT then label                                                                                                                                                                                                     |
| Gan_evidence_label           | Label plus exact evidence quote                                                                                                                                                                                                              |
| Gan_two_pass                 | Quote pass then normalize pass                                                                                                                                                                                                               |
| Gan_fs_hard                  | Direct label with hard-case few-shot examples                                                                                                                                                                                                |
| Gan_retrieval_highlight      | Retrieval-augmented: retrieved frequency spans provided as highlighted context before extraction                                                                                                                                             |
| Gan_retrieval_only_ablation  | Retrieval only, no extraction instruction; ablation for Gan_retrieval_highlight                                                                                                                                                              |
| Gan_h013_direct              | Direct label using H0/H1/H3-style compact instruction                                                                                                                                                                                        |
| Gan_g3_qwen                  | qwen-optimized G3 harness                                                                                                                                                                                                                    |
| MA_v1                        | Multi-agent pipeline: segmentation → parallel field extractors (2a–2d) → verification → aggregation; projects to the same canonical schema as direct/event-first runs (`src/multi_agent.py`; plan in `docs/36_multi_agent_pipeline_plan.md`) |


### 1.6 System Naming

Direct extraction systems:

- **S1**: Direct canonical JSON, no evidence required
- **S2**: Direct canonical JSON with evidence quotes and event IDs (primary frontier baseline)
- **S3**: YAML output parsed into canonical JSON

Event-first systems:

- **E1**: Event extraction only (evidence-grounded events, no aggregation)
- **E2**: E1 + deterministic aggregation into canonical JSON
- **E3**: E1 + constrained LLM aggregation (second model call) into canonical JSON

Model expansion systems (harness variants applied to a target model):

- **D0** = S2 (existing direct)
- **D1** = task-specific direct (H2 projection)
- **D2** = loose answer then parse (H3 projection)
- **D3** = candidate plus verifier

Local model systems (Ollama-hosted):

- **F1–F5c** = final full-field evaluation candidates (see Section 5)

---

## 2. Milestone Stub Runs (Infrastructure Verification)

### 2.1 Milestone 3: Direct Baseline Pipeline

**Runs:** `milestone_3_stub`, `milestone_3_stub_compact_log`, `milestone_3_prepare_check`  
**Split:** Development (2 docs). **Provider:** Stub (no model calls).  
**Idea:** Verify that the direct extraction pipeline mechanics work end-to-end before spending API budget. Stub provider emits valid empty canonical outputs.  
**Expected:** Parse=100%, schema=100%, quote=100%; all clinical F1=0.0 (stubs return no content).  
**What happened:** All expectations confirmed. EEG accuracy=1.0 (both stubs correctly output `not_stated`). MRI accuracy=0.5 (one stub mismatched). `milestone_3_stub_compact_log` introduced a smaller JSONL log format that was adopted in all subsequent runs.  
**Learning:** Direct pipeline mechanics fully verified. System Python (without `.venv`) was a recurring issue discovered here and resolved in later runs.

---

### 2.2 Milestone 4: Event-First Pipeline

**Runs:** `milestone_4_stub_check` variants (plain, venv, venv_2), `milestone_4_prepare_check` variants  
**Split:** Development (2 docs). **Provider:** Stub.  
**Idea:** Verify E1/E2/E3 event-first mechanics. The key novel component is E3's constrained LLM aggregation, which requires a second model call.  
**Expected:** Same structural guarantees as milestone 3.  
**What happened:** Early `plain` run failed schema validation — `jsonschema` was not installed in system Python. Resolved in `venv` variants. After fix: parse=100%, schema=100%, E1/E2/E3. E3 constrained aggregation added ~0.028ms latency even in stub mode.  
**Learning:** Always use `.venv/bin/python`. E3's second call overhead is negligible.

---

### 2.3 Milestone 5: Evaluation Harness

**Runs:** `milestone_5_missing_artifact_check` (×3), `milestone_5_stub_eval` through `_final_2`  
**Split:** Development (2 docs). **Provider:** Stub.  
**Idea:** Verify the artifact-gating logic and scoring pipeline before committing to expensive real-model runs. The harness should return 0 available documents when artifacts are absent.  
**Expected:** Artifact gate fires correctly; once artifacts present, E2/E3 metrics match milestone 4.  
**What happened:** All three `missing_artifact_check` runs correctly returned 0 available docs. Once artifacts present: E2/E3 schema=1.0, quote=1.0, temporal=1.0, EEG=1.0, MRI=0.5 (one doc). Clinical F1=0.0 (stub).  
**Learning:** Artifact gate works. The 0.5 MRI score is a known stub artefact, not a real failure.

---

### 2.4 Milestone 7: Secondary Analyses

**Runs:** `milestone_7_eval_s2_s3_smoke`, `milestone_7_json_yaml_stub`, `milestone_7_model_compare_stub`, `milestone_7_model_compare_event_stub`  
**Split:** Development (2 docs). **Provider:** Stub.  
**Idea:** Verify three secondary dissertation analyses under stub conditions: JSON vs YAML format (S2 vs S3); local vs frontier model; E2 vs E3.  
**Expected:** Zero clinical quality difference between any condition (stub gives no content); only mechanical differences visible.  
**What happened:** Zero accuracy difference across all conditions as expected. S3 (YAML) was 0.00027ms faster; S2 had 2.5% repair rate on later real data vs 0% for S3. Format choice is orthogonal to extraction quality.  
**Learning:** All three secondary analyses confirmed as structurally independent. Real quality differences require real model calls.

---

### 2.5 Milestone 8: Dissertation Write-Up Support

**Run:** `milestone_8_writeup_smoke`  
**Idea:** Verify that the write-up support infrastructure (claim matrix, error examples, dissertation tables, SVG plots) generates cleanly from the evaluation artifacts.  
**What happened:** Generated `claim_support_matrix.csv` (4 claims mapped to artifacts), `error_analysis_examples.csv` (4 failure seeds), `dissertation_tables.md`, `methods_traceability.md`, `evaluation_metric_plot.svg`. All claims traced to specific artifact files.  
**Learning:** Write-up pipeline confirmed. This infrastructure was the basis for the final dissertation tables section.

---

### 2.6 Robustness Smoke Tests

**Runs:** `robustness_smoke`, `robustness_smoke_venv`  
**Split:** Development (1 doc × 7 perturbation types). **Provider:** Stub.  
**Idea:** Verify perturbation corpus and robustness pipeline. Seven perturbation types: `family_history_trap`, `negated_investigation_trap`, `bullets_to_prose`, `medication_name_change`, and others.  
**What happened:** `robustness_smoke` had schema=0.0 (system Python issue). `robustness_smoke_venv` restored schema=1.0. Quote validity=1.0 across all perturbations. Clinical F1=0.0 (stub). GAN frequency tests: all 6 conditions (S2, E2, E3 × 2 perturbation types) correctly returned frequency_accuracy=0.000.  
**Learning:** Perturbation corpus and robustness pipeline verified. Evidence grounding survives all structural perturbations at stub level.

---

## 3. Model Expansion Workstream (Real Model Calls)

### 3.1 Stage A: Provider and Harness Smoke (15 dev docs, real models)

**Run:** `stage_a_provider_smoke`, `stage_a_smoke_check`  
**Split:** Development (15 docs). **Provider:** OpenAI, Anthropic, Google.  
**Idea:** First real-model run. Test all target frontier models on H0 (strict canonical), H2 (task-specific), H3 (loose answer-then-parse) to verify provider adapters and establish a development baseline. The goal is cost characterisation and parse reliability, not final quality.  
**Models tested:** GPT-4.1-mini, GPT-5.5, GPT-5.4-mini, Claude Sonnet 4.6, Gemini 3.1 Flash, Gemini 3.1 Pro.  
**Expected:** H0 should produce canonical outputs; H2/H3 may not project canonically; Gemini might have quota issues.  
**What happened:**


| Model             | Med Name F1 | Seizure F1 | Dx Acc | Benchmark Quality | Cost/Quality-Point |
| ----------------- | ----------- | ---------- | ------ | ----------------- | ------------------ |
| Claude Sonnet 4.6 | 0.889       | 0.524      | 0.933  | 0.782             | $0.072             |
| GPT-5.5           | 0.923       | 0.512      | 0.933  | 0.789             | $0.107             |
| GPT-5.4-mini      | 0.943       | 0.465      | 0.933  | 0.781             | $0.014             |
| Gemini 3.1 Flash  | 0.957       | 0.560      | 0.857  | 0.791*            | $0.011             |
| GPT-4.1-mini      | 0.906       | 0.512      | 0.933  | 0.784             | $0.005             |


*Gemini 3.1 Flash: only 7 of 15 documents returned canonical outputs; excluded from promotion.

H2/H3 harnesses: all calls succeeded but produced no canonical projection layer — excluded from final selection pending projection implementation.  
**Learning:** Benchmark quality was **tightly clustered** (0.781–0.791) across all eligible models. GPT-4.1-mini costs **14–21× less** per quality-point than Claude Sonnet or GPT-5.5. Gemini Flash was unreliable at quota limits and was excluded from all subsequent formal runs. The development split favours quick medical fact extraction; validation will be the real test.

---

### 3.2 Stage B: Development Pilot (15 dev docs)

**Run:** `stage_b_dev_pilot`  
**Split:** Development (15 docs). **Provider:** OpenAI, Anthropic.  
**Idea:** Promote models to strict validation only if they produce canonically scoreable output and improve at least two benchmark-aligned fields.  
**What happened:** Four models eligible: GPT-4.1-mini (0.784), GPT-5.5 (0.789), GPT-5.4-mini (0.781), Claude Sonnet 4.6 (0.782). Gemini excluded. H2/H3 retained as projection-blocked exploratory harnesses.  
**Promotion decision:** GPT-4.1-mini selected as primary by cost-effectiveness frontier. All four models promoted to Stage C0 under H0.  
**Learning:** At development scale, model capability differences are swamped by cost differences. No reason to pay 21× more at this stage.

---

### 3.3 Stage C0: Strict Validation (40 val docs)

**Run:** `stage_c0_strict_validation`  
**Split:** Validation (40 docs). **Provider:** OpenAI, Anthropic.  
**Idea:** Select at most two final strict candidates — best quality and best cost-effective — before touching the test set.  
**Gates:** Schema validity ≥ 0.99, quote validity ≥ 0.99, benchmark quality > 0.  
**What happened:** Two conditions passed:

- `gpt_4_1_mini_baseline` → **selected as primary (S2 system)**
- `event_first_e2` → **selected as secondary**

All relaxed harnesses (H2, H3) excluded for lacking canonical projection.  
**Learning:** Validation selection frozen at this point. The test split was not touched. This was the correct decision — subsequent recovery work would have been compromised if test data had been seen.

---

### 3.4 Stage C1: Relaxed Projection (15 dev docs, H2/H3)

**Run:** `stage_c1_relaxed_projection`  
**Split:** Development (15 docs). **Provider:** OpenAI, Google.  
**Idea:** Test whether lower schema pressure improves extraction quality once H2/H3 outputs can be projected into canonical scoring.  
**What happened:** H3 (loose) outperforms H2 (task-specific) at relaxed projection. GPT-5.4-mini + H3 achieves highest relaxed quality (0.809). Gemini Flash: systemic empty responses (14/15 on H2, most on H3) — fully excluded. These conditions were not promoted because they lacked evidence reconstruction.  
**Learning:** H3 on GPT-5.4-mini is a strong candidate if evidence reconstruction is added (later implemented in §5.4 of the synthesis report). Gemini is definitively out.

---

### 3.5 Stage D: H6/H7 Diagnostic (15 dev docs)

**Run:** `stage_d_h6_h7_diagnostic`  
**Split:** Development (15 docs). **Provider:** OpenAI.  
**Idea:** Test whether benchmark-only JSON (H6) and extract-then-normalize (H7) can improve on H0, especially for seizure type. H7 hypothesis: a two-pass approach where pass 1 extracts raw mentions and pass 2 normalizes to benchmark labels will improve seizure type scoring because the model is not simultaneously trying to produce schema-valid JSON.  
**Expected:** H7 should improve seizure F1 at the cost of latency.  
**What happened:**


| Condition       | Quality | Seizure F1 |
| --------------- | ------- | ---------- |
| gpt_4_1_mini:H7 | 0.835   | **0.698**  |
| gpt_5_4_mini:H7 | 0.832   | 0.638      |
| gpt_5_5:H7      | 0.822   | 0.609      |
| gpt_4_1_mini:H6 | 0.817   | 0.596      |
| gpt_5_4_mini:H6 | 0.824   | 0.596      |
| gpt_5_5:H6      | 0.831   | 0.636      |


H7 on GPT-4.1-mini achieved seizure_type_F1=0.698 on development vs H0's 0.512 — a **37% relative improvement** from normalization alone.  
**Learning:** The seizure type scoring problem is primarily a normalization problem. The collapsed-label scorer ports this insight into the evaluator without requiring re-runs. H7's two-pass design works; it was later given proper evidence reconstruction to become promotion-eligible.

---

### 3.6 Stage E: H4/H8/D3 Diagnostic (15 dev docs)

**Run:** `stage_e_h4_h8_d3_diagnostic`  
**Split:** Development (15 docs). **Provider:** OpenAI.  
**Idea:** Test three further harness variants. H4 uses provider-native structured output. H8 extracts without evidence first, then resolves evidence in pass 2. D3 (candidate + verifier) adds a separate keep/drop/normalize verification pass.  
**Expected:** D3 should outperform single-pass systems; H4 should match H0 with lower repair rate; H8 evidence reconstruction should improve quote validity.  
**What happened:**


| Condition                        | Quality   | Seizure F1 |
| -------------------------------- | --------- | ---------- |
| gpt_5_5:D3 (cand+verify)         | **0.846** | 0.682      |
| gpt_5_4_mini:H4 (native struct)  | 0.838     | 0.638      |
| gpt_5_4_mini:D3                  | 0.836     | 0.651      |
| gpt_4_1_mini:D3                  | 0.820     | 0.636      |
| gpt_4_1_mini:H4                  | 0.816     | 0.612      |
| gpt_4_1_mini:H8 (evidence later) | 0.806     | 0.542      |


D3 on GPT-5.5 achieves the highest overall benchmark quality (0.846) of any condition — 7% relative improvement over H0. Evidence reconstruction for D3 was confirmed as already implemented (`d3_medication_items()`, `d3_seizure_items()`, `d3_epilepsy_item()`).  
**Learning:** D3 with verification is the strongest harness tested. GPT-5.5 does need D3 to show its advantage; GPT-4.1-mini with H7 is competitive at far lower cost. The verifier pass roughly doubles call cost but the quality gain is meaningful. Both H7 and D3 were marked promotion-eligible for validation scale (deferred to Phase 4 work).

---

## 4. Performance Recovery (Scoring Repair and Corrected Metrics)

### 4.1 Pre-Recovery State

After Stage C0, the **original scorer final_test results** (40 test docs, gpt-4.1-mini):


| System | Med Name | Med Full | Sz Type | Sz Freq | Freq-Type | EEG   | MRI   | Dx Acc |
| ------ | -------- | -------- | ------- | ------- | --------- | ----- | ----- | ------ |
| S2     | 0.842    | 0.496    | 0.213   | 0.000   | 0.075     | 0.975 | 0.900 | 0.775  |
| E2     | 0.704    | 0.372    | 0.261   | 0.000   | 0.050     | 0.900 | 0.850 | 0.550  |
| E3     | 0.829    | 0.483    | 0.241   | 0.000   | 0.125     | 0.900 | 0.825 | 0.750  |


Key gaps vs Fang et al. targets: seizure type 0.187–0.261 (target ≥0.76); medication full tuple 0.372–0.496 (target ≥0.80); seizure frequency=0.000 across all systems (suspicious). The decision was made to open a performance recovery programme rather than declare failure.

---

### 4.2 Phase 0: Benchmark Reconciliation

**Artifact:** `runs/recovery/benchmark_crosswalk.json`  
**Idea:** Before optimizing, make sure we are measuring the right things. The Fang et al. paper uses King's College Hospital letters, its own label taxonomy, and four tasks. Map every task to local fields and decide which local metrics are directly comparable.  
**What happened:** All four benchmark tasks mapped:

- Epilepsy type → `epilepsy_diagnosis_accuracy` ✓
- Seizure type → `seizure_type_f1` ✓ (collapsed labels to be added)
- Current ASMs → `medication_name_f1` ✓ (ASM normalization to be expanded)
- Associated symptoms → not in schema (low priority)

**Learning:** The project is trying to match the benchmark fairly. The major gap in seizure type is partly a label taxonomy mismatch — solved by adding collapsed benchmark-category labels to the scorer rather than requiring exact string matches.

---

### 4.3 Phase 1: Failure Localization

**Artifacts:** `runs/recovery/failure_pareto.csv`, `error_cases.csv` (725 errors), `field_confusions/`  
**Idea:** Build confusion tables for every weak field. Classify every false positive and false negative to one of: `gold_loader`, `scorer`, `normalizer`, `prompt_extraction`, `event_extraction`, `event_aggregation`, `schema_missingness`, `ambiguous_gold`.  
**Scope:** 120 validation documents.  
**Top error categories discovered:**

1. `current_seizure_frequency` (gold_loader): Literal `null` strings from `MarkupSeizureFrequency.csv` were being treated as scoring tokens, producing malformed strings like `null null per 3 week`.
2. `medication_name` (prompt_extraction): Misspellings (`eplim`, `brivitiracetam`, `zonismaide`), over-extraction of historical medications, under-extraction of brand names.
3. `seizure_type` (scorer): Exact label vs. collapsed benchmark category mismatch — the model was extracting the right clinical fact but not the benchmark's exact label string.
4. Temporal scope (gold_loader): Sparse timing columns in ExECTv2 causing edge-case scoring failures.

**Learning:** Two of the four major error sources were **scorer/gold-loader bugs**, not model failures. The zero seizure-frequency score was a gold-loader bug, not a reflection of model capability. This was the most important finding of the recovery phase — fixing the scorer materially changed the conclusions.

---

### 4.4 Phase 2: Scoring Audit — Two Critical Bug Fixes

**Artifacts:** `runs/recovery/scoring_audit.md`, `metric_contract_v2.json`  
**Idea:** Audit the gold loader and scorer before spending tokens on prompt improvements.

**Bug 1: Seizure Frequency Gold Loader**  
Literal `null` cells in `MarkupSeizureFrequency.csv` were passed through to the scoring pipeline as the string `"null"`, producing invalid frequency expressions like `"null null per 3 week"`. Fix: treat `null`, `none`, `nan`, `n/a`, and empty cells as absent in `normalize_value()`.

**Bug 2: Medication Component Scoring**  
The original scorer scored the medication tuple as an all-or-nothing match. Fix: added per-component F1 (dose, unit, frequency) and unit/frequency equivalence normalization (`milligrams→mg`, `bd→twice daily`, etc.).

**Effect (40 validation docs, Phase 2 corrected scorer, before Phase 3 ASM expansion):**


| System | Name F1 | Dose F1 | Unit F1 | Freq F1 | Full Tuple F1 |
| ------ | ------- | ------- | ------- | ------- | ------------- |
| S2     | 0.789   | 0.717   | 0.784   | 0.673   | 0.584         |
| E2     | 0.723   | 0.736   | 0.723   | 0.674   | 0.551         |
| E3     | 0.800   | 0.800   | 0.791   | 0.742   | 0.626         |


These are 51–61% higher than the original final_validation numbers for medication full tuple.  
**Learning:** The original scorer materially understated medication full tuple F1. The scoring repair is itself a methods contribution. **Any comparison to external benchmarks using the original scorer was invalid.**

---

### 4.5 Phase 3: Normalization Repair (Three Improvements)

**Improvement 1: ASM Synonym Expansion**  
`ASM_SYNONYMS` in `normalization.py` extended from ~22 to ~80 entries. Added: misspellings from Phase 1 error analysis (`eplim→sodium valproate`, `brivitiracetam→brivaracetam`, `zonismaide→zonisamide`, `levitiracetam→levetiracetam`), plus brand names for all major ASMs (`depakote`, `tegretol`, `diamox`, `zebinix`, `neurontin`, `vimpat`, etc.).  
**Effect:** Med Name F1 validation 0.782→0.852 (+9%); test 0.842→0.885 (+5%).

**Improvement 2: Collapsed Seizure-Type and Epilepsy-Type Labels**  
`BENCHMARK_SEIZURE_LABEL` dict mapping 14 canonical types to 3 benchmark categories. `BENCHMARK_EPILEPSY_LABEL` dict mapping canonical diagnoses to 4 benchmark categories. Added `seizure_type_f1_collapsed` and `epilepsy_diagnosis_accuracy_collapsed` throughout the scorer.  
**Effect:** Seizure type F1 validation rose from 0.187–0.200 (strict original) to 0.610–0.633 (collapsed corrected) — a **3× improvement** with no prompt changes.

**Improvement 3: E2 Diagnosis Aggregation Fix**  
`_is_epilepsy_diagnosis(value)` extracted from `diagnosis_rank()` in `event_first.py`. The original check `"epilepsy" in value` silently dropped `status epilepticus` (contains `epilepticus` not `epilepsy`). Fixed to `"epilepsy" in value or "epilept" in value`. Stored test/validation artifacts were produced before this fix; re-running would improve E2 diagnosis accuracy.

**Learning:** Phase 3 normalization changes produced the largest per-line-of-code improvement in dissertation metrics of any stage. The collapsed label approach is the right match for clinical tasks where semantic equivalence matters more than exact string match.

---

### 4.6 Aggregation Oracle

**Artifact:** `runs/recovery/aggregation_oracle/`  
**Scope:** 120 validation documents.  
**Idea:** Estimate the hard performance ceiling for each field — what score would be achieved with perfect extraction but real ExECTv2 annotation gaps.


| Field                 | Oracle Failure Rate | Interpretation                                          |
| --------------------- | ------------------- | ------------------------------------------------------- |
| Medication name       | **0.0%**            | Ceiling is 100% F1; all failures are extractable        |
| Medication full tuple | 10.8%               | 11% of docs have annotation ambiguity at tuple level    |
| Seizure type          | 13.3%               | 13% irreducible from annotation gaps                    |
| Epilepsy diagnosis    | 17.5%               | 18% irreducible                                         |
| Seizure frequency     | 29.2%               | 29% hard ceiling — even perfect extraction cannot score |
| Freq-type linkage     | 29.2%               | Same hard ceiling as frequency                          |


**Learning:** The 29.2% seizure-frequency hard ceiling explains why ExECTv2 frequency scores remain low despite everything else improving. The frequency problem is partly an annotation quality problem, not only an extraction problem.

---

### 4.7 Corrected Authoritative Metrics

**Source:** `runs/recovery/corrected_metrics/` — supersedes all `runs/final_{validation,test}/evaluation/` numbers.

**Validation split (40 docs, gpt-4.1-mini, corrected scorer):**


| System | Med Name  | Med Full  | Sz Strict | Sz Collapsed | Freq Loose | EEG       | MRI       | Dx Acc    | Dx Collapsed | Temporal | Schema | Quote     |
| ------ | --------- | --------- | --------- | ------------ | ---------- | --------- | --------- | --------- | ------------ | -------- | ------ | --------- |
| S2     | 0.852     | 0.655     | 0.431     | 0.610        | 0.075      | 0.950     | 1.000     | 0.725     | 0.700        | 0.835    | 1.000  | 0.991     |
| E2     | 0.796     | 0.633     | 0.388     | 0.613        | 0.125      | 0.950     | 0.975     | 0.600     | 0.575        | 0.957    | 1.000  | 0.992     |
| E3     | **0.872** | **0.707** | 0.396     | **0.633**    | 0.125      | **0.975** | **0.975** | **0.775** | **0.725**    | 0.914    | 1.000  | **0.994** |


**Test split (40 docs, gpt-4.1-mini, corrected scorer, held-out):**


| System | Med Name  | Med Full  | Sz Strict | Sz Collapsed | Freq Loose | EEG   | MRI   | Dx Acc    | Dx Collapsed | Temporal  | Schema | Quote |
| ------ | --------- | --------- | --------- | ------------ | ---------- | ----- | ----- | --------- | ------------ | --------- | ------ | ----- |
| S2     | 0.885     | 0.769     | 0.349     | 0.415        | 0.175      | 0.975 | 0.900 | **0.850** | 0.725        | 0.880     | 0.950  | 0.993 |
| E2     | 0.722     | 0.619     | 0.385     | 0.487        | 0.125      | 0.900 | 0.850 | 0.600     | 0.550        | **0.980** | 0.975  | 1.000 |
| E3     | **0.847** | **0.724** | 0.362     | 0.469        | 0.125      | 0.900 | 0.825 | 0.750     | 0.700        | 0.968     | 0.975  | 1.000 |


**Medication component F1 (corrected scorer):**


| Split | System | Name      | Dose      | Unit      | Freq      | Full      |
| ----- | ------ | --------- | --------- | --------- | --------- | --------- |
| val   | S2     | 0.852     | 0.781     | 0.863     | 0.738     | 0.655     |
| val   | E2     | 0.796     | 0.814     | 0.819     | 0.753     | 0.633     |
| val   | E3     | **0.872** | **0.876** | **0.884** | **0.818** | **0.707** |
| test  | S2     | 0.885     | 0.839     | 0.899     | 0.829     | 0.769     |
| test  | E2     | 0.722     | 0.796     | 0.776     | 0.720     | 0.619     |
| test  | E3     | **0.847** | **0.925** | **0.911** | **0.827** | **0.724** |


---

### 4.8 Robustness — Final Validation and Test (7 perturbation types, 5 docs each)

**Idea:** Test whether results are brittle to document structure changes. Seven perturbations: `family_history_trap`, `negated_investigation_trap`, `bullets_to_prose`, `medication_name_change`, and others.  
**What happened:** All systems maintained schema_valid=1.000 and quote_validity ≥ 0.960 across all perturbations.

Worst label-preserving degradations:


| System | Worst Sz Type Drop | Perturbation        | Worst MRI Drop | Perturbation               |
| ------ | ------------------ | ------------------- | -------------- | -------------------------- |
| S2     | −0.400             | family_history_trap | −0.400         | negated_investigation_trap |
| E2     | −0.364             | family_history_trap | −0.200         | negated_investigation_trap |
| E3     | −0.333             | family_history_trap | −0.200         | negated_investigation_trap |


E3 is the most robust system — its event-extraction stage provides a structural boundary that limits context bleeding between patient history and family history, and between positive and negated findings. S2's full-document context makes it more vulnerable to these traps.  
**Learning:** The event-first architecture has a genuine robustness advantage beyond its accuracy advantage. This is a dissertation-level finding.

---

## 5. Local Models Workstream (L0–L6, N1–N6, Variants A–C)

### 5.1 Motivation and Infrastructure Challenge

**Idea:** Demonstrate that a locally-hosted open-weight model can achieve competitive performance, reducing marginal cost to zero, removing data-privacy constraints, and enabling offline clinical deployment.  
**Goal:** ≥ 0.70 medication name F1 and ≥ 0.50 seizure type F1 on the validation split.

**Critical infrastructure finding (L0):** The plan assumed the OpenAI-compatible endpoint (`/v1/chat/completions`) would work with Ollama. In practice, qwen3.5 uses extended thinking by default and the `think: false` parameter is silently ignored by the compat shim — all output tokens were consumed by internal reasoning, producing empty responses and timeouts of 6–30+ minutes per document.

**Fix:** `OllamaAdapter` rewritten to use Ollama's native `/api/generate` endpoint with `think: false` in the payload and `/no_think\n\n` prepended to the prompt. This dropped per-call latency from >6 min to 5–25 seconds. This was the single most important infrastructure finding of the local models workstream.

**Additional fixes discovered:** (a) H3 parse detection bug: `run_local_one` was calling `parse_json_response` for H3 outputs, marking all H3 calls as parse failures even when `parse_loose_sections` could extract every field correctly; (b) `write_csv` crashed when scored rows had extra metric columns; (c) model ID `qwen3.5:8b` → `qwen3.5:9b`; (d) split key `dev` → `development`.

---

### 5.2 Stage L1: H0 Strict Canonical — Abandoned

**Idea:** Can local 9B models run the full canonical schema prompt?  
**What happened:** H0 is unusable for local models. The canonical schema prompt (~3,700 tokens input) caused qwen3.5:9b to generate responses taking >30 minutes per document even with thinking disabled. Root cause: the full canonical JSON output is ~2,000–3,000 tokens; at 30–50 tok/s local inference speed that is 60–100 seconds in ideal conditions, but the model often failed to terminate cleanly.  
**Learning:** H0 on local models is not viable at 4–10B scale. This is the expected "characterize the failure" outcome. It motivates the simplified H6 harness design.

---

### 5.3 Stage L2: H4 json_mode (5 dev docs)


| Model      | Parse | Med F1 | Sz F1 collapsed | Dx Acc | Latency/doc |
| ---------- | ----- | ------ | --------------- | ------ | ----------- |
| qwen3.5:9b | 100%  | 0.941  | 0.769           | 1.000  | 12s         |
| qwen3.5:4b | 100%  | 0.941  | 0.714           | 1.000  | 8s          |


Both promoted to L3. The Ollama `format: json` option produces no measurable quality improvement over a prompt-only JSON instruction (H6). H4 and H6 are functionally equivalent; H4 is slightly faster.  
**Learning:** Local models don't need provider-native structured output enforcement to achieve reliable JSON. The development split is easy — validation will differ.

---

### 5.4 Stage L3: Simplified Harnesses H6, H3, H7 (5 dev docs)


| Model      | Harness         | Parse | Med F1    | Sz F1 collapsed | Dx Acc | Latency/doc |
| ---------- | --------------- | ----- | --------- | --------------- | ------ | ----------- |
| qwen3.5:9b | H3 (loose text) | 100%  | **1.000** | **0.857**       | 1.000  | 25s         |
| qwen3.5:9b | H6 (JSON)       | 100%  | 0.941     | 0.769           | 1.000  | 12s         |
| qwen3.5:9b | H7 (two-pass)   | 100%  | 0.941     | 0.769           | 1.000  | 96s         |
| qwen3.5:4b | H3 (loose text) | 100%  | **1.000** | **0.857**       | 1.000  | 15s         |
| qwen3.5:4b | H6 (JSON)       | 100%  | 0.941     | 0.714           | 1.000  | 8s          |
| qwen3.5:4b | H7 (two-pass)   | 100%  | 0.941     | 0.714           | 1.000  | 74s         |


H3 led on dev (med_f1=1.0, sz_f1=0.857). H7 adds 7–8× latency with no quality improvement.  
**Learning:** H7 two-pass is not justified for local models. H3's apparent lead on dev was misleading (see L5). H6 is the best single-pass harness.

---

### 5.5 Stage L4: Vocabulary Preamble (3 dev docs)

**Idea:** Add a preamble listing ASM names and seizure taxonomy to help the model use correct terminology.  
**What happened:** Both variants scored identically (med_f1=0.909, sz_f1=0.889, dx_acc=1.0). qwen3.5 already knows levetiracetam, sodium valproate, Keppra, Epilim, focal epilepsy, JME, etc.  
**Learning:** Vocabulary preamble adds token overhead with no measurable gain for qwen3.5. Not worth the cost for any harness. This finding may not generalise to smaller or less instruction-tuned models.

---

### 5.6 Stage L5: Validation Scale (5 then 40 docs — N2 was the definitive run)

Initial L5 result (5 validation docs):


| System                     | Med F1    | Sz F1 collapsed | Dx Acc    |
| -------------------------- | --------- | --------------- | --------- |
| GPT-4.1-mini S2 (frontier) | 0.852     | 0.610           | 0.725     |
| qwen3.5:9b H6              | **0.875** | **0.250**       | **0.800** |


The seizure F1=0.250 was alarming — but later revealed as severe sampling noise on 5 documents.

**Why H3 underperformed on validation:** H3 gives the model free rein to describe diagnoses in natural language. On validation it wrote responses like `"Symptomatic structural focal epilepsy"` — clinically accurate but not matching the closed benchmark label set. H6's explicit `Allowed epilepsy_diagnosis_type labels:` block forces correct normalization. The dev split had only straightforward cases where both approaches agreed; validation exposed H6's structural advantage.  
**Learning:** The closed-label constraint in H6 is load-bearing. A loose harness that looks great on dev can fail systematically on validation.

---

### 5.7 N1: Seizure Type Gap Investigation (40 docs) — Root Cause Analysis

**Idea:** Determine whether the sz_f1=0.250 on 5 docs reflects a real capability ceiling or sampling noise.  
**What happened:** With 40 docs, qwen3.5:9b H6 achieves sz_f1_collapsed=0.541 — only 7–9pp below frontier (0.610–0.633), not 36pp as the 5-doc result suggested.

Full mismatch analysis (26 docs with gold seizure types):


| Failure mode                          | Count      | Root cause                                                          |
| ------------------------------------- | ---------- | ------------------------------------------------------------------- |
| Missing `unknown seizure type`        | 15/26 docs | Model infers a specific type instead of using the meta-label        |
| Hallucination on seizure-free letters | 12/40 docs | Model extracts historical seizure mentions as if current            |
| Label granularity mismatch            | 4 docs     | e.g. `focal impaired awareness seizure` → `focal seizure`           |
| Singular/plural normalisation         | 1 doc      | `secondary generalized seizure` vs `secondary generalized seizures` |


Most common false positives: `focal seizure` (11×), `generalized tonic clonic seizure` (11×), `secondary generalized seizures` (7×).  
**Learning:** The seizure type gap is a prompt engineering problem, not a model capability ceiling. Two specific failure modes dominate: missing the `unknown seizure type` meta-label, and hallucinating historical types as current. Both are addressable via examples or explicit instructions.

---

### 5.8 N2–N5 and Large Model Validation (40-doc Definitive Results)

All results on 40 validation documents (corrected scorer):


| System                              | Med F1    | Sz F1 collapsed | Dx Acc | Lat/doc | Cost/doc |
| ----------------------------------- | --------- | --------------- | ------ | ------- | -------- |
| GPT-4.1-mini S2 (frontier baseline) | 0.852     | 0.610           | 0.725  | ~API    | ~$0.003  |
| GPT-4.1-mini E3 (frontier best)     | 0.872     | 0.633           | 0.775  | ~API    | ~$0.005  |
| qwen3.5:9b H6                       | 0.800     | 0.541           | 0.800  | 12s     | $0       |
| qwen3.5:9b H6v2 (seizure fix)       | 0.814     | 0.595           | 0.775  | 12s     | $0       |
| qwen3.5:9b H6fs (few-shot)          | 0.839     | 0.602           | 0.825  | 12s     | $0       |
| qwen3.5:9b H6qa (decomposed status) | 0.821     | 0.545           | 0.800  | 12s     | $0       |
| qwen3.5:9b H6ev (evidence anchor)   | 0.800     | 0.602           | 0.800  | 12s     | $0       |
| qwen3.5:4b H6                       | 0.814     | 0.535           | 0.750  | 8s      | $0       |
| gemma4:e4b H6                       | 0.849     | 0.593           | 0.825  | 28s     | $0       |
| gemma4:e4b H6v2                     | 0.865     | 0.568           | 0.825  | 28s     | $0       |
| gemma4:e4b H6fs                     | 0.815     | 0.561           | 0.825  | 28s     | $0       |
| gemma4:e4b H6qa                     | 0.839     | 0.525           | 0.825  | 28s     | $0       |
| gemma4:e4b H6ev                     | 0.827     | 0.528           | 0.825  | 28s     | $0       |
| qwen3.6:27b H6                      | **0.885** | 0.578           | 0.800  | 34s     | $0       |
| qwen3.6:27b H6fs                    | 0.838     | 0.593           | 0.800  | 34s     | $0       |
| qwen3.6:35b H6                      | 0.857     | 0.571           | 0.800  | **12s** | $0       |
| qwen3.6:35b H6fs                    | **0.852** | **0.593**       | 0.800  | **12s** | $0       |


---

### 5.9 Variant A: H6fs Few-Shot (40 docs)

**Idea:** Add three inline examples targeting the two dominant N1 failure modes: (1) ongoing seizures, type unspecified → `unknown seizure type`; (2) currently seizure-free → `seizure free`; (3) historical specific type + now seizure-free → `seizure free` (not the historical type).  
**What happened:** H6fs is the best harness for qwen3.5:9b across all three metrics simultaneously (+3.9pp med, +6.1pp sz, +2.5pp dx vs H6). H6fs **regresses** gemma4:e4b on medication (−3.4pp) and seizure (−3.2pp).  
**Learning (critical):** Few-shot guidance has model-specific effects that cannot be assumed to generalise across model families. The model that benefits most (qwen3.5) is the one that needed guidance; the model already well-calibrated (gemma4) is harmed by the same examples. This argues for **model-specific harness selection** rather than a universal prompt.

---

### 5.10 Variant B: H6qa Decomposed Status (40 docs)

**Idea:** Extend the output schema with a `current_seizure_status` field (`active|seizure_free|unclear`) that the model must populate first, then constrains `seizure_types` based on that decision. Hypothesis: structured reasoning about current status before extraction would reduce meta-label failures.  
**What happened:** H6qa underperforms H6fs for qwen3.5:9b. For gemma4:e4b, the schema extension was not followed — `parse_error=40` (model did not output `current_seizure_status` in parseable form), resulting in 19 `seizure free` false positives. The constraint worked mechanically for qwen3.5 when status was correctly classified, but the upstream status classification was itself error-prone.  
**Learning:** Structured reasoning via chain-of-type-classification is less effective than direct few-shot examples. The model needs to be correct on the sub-task classification before the constraint can help, which is a second source of failures. Few-shot examples sidestep this by showing completed outputs directly.

---

### 5.11 Variant C: H6ev Evidence Anchor (40 docs)

**Idea:** Add a single `seizure_evidence` field requiring the model to copy the shortest direct quote confirming current seizure status, or set it to null; if null, `seizure_types` must be []. This was a minimal schema extension designed to test whether evidence-based suppression could close the hallucination gap.  
**What happened:** qwen3.5:9b: parse_error=0, evidence_null=7, evidence_present=33. The model follows the schema correctly. H6ev achieves the same seizure F1 as H6fs (0.602) via a different mechanism (evidence null-suppression). However, medication and diagnosis both regress to H6 baseline, making H6fs the better overall harness for qwen3.5. gemma4:e4b: parse_error=40 — same schema-extension aversion as H6qa.  
**Learning (definitive gemma finding):** All three schema extension harnesses (H6v2, H6fs, H6qa, H6ev) regress gemma4 relative to plain H6 on seizure type F1. H6qa and H6ev both show parse_error=40. gemma4:e4b performs best with the plain minimal H6 harness. Schema additions that help qwen3.5 either have no effect or actively hurt gemma4. This is a capability-appropriate prompt design finding with direct clinical deployment implications.

---

### 5.12 Large Model Results: qwen3.6:27b and qwen3.6:35b

**qwen3.6:27b H6 key finding:** 0.885 medication F1 — **the first local model to exceed both frontier baselines on medication** (+1.3pp vs S2, +1.3pp vs E3). Scale law for medication is steep. However, H6fs at 27B: medication drops 4.7pp (0.885→0.838); few-shot examples no longer help at this scale and actively hurt — same pattern as gemma4.

**qwen3.6:35b key finding:** MoE architecture (8 active experts from 256) delivers near-9B latency (12s/doc) from a 23 GB model. H6fs at 35B: medication stays high (0.857→0.852, only −0.5pp), seizure improves (+2.2pp). Unlike the dense 27B where H6fs cost 4.7pp on medication, the MoE 35B tolerates H6fs without significant regression.

**Scale-vs-harness progression (H6 baseline seizure F1):**  
qwen3.5:9b (0.541) → qwen3.5:4b (0.535) → qwen3.6:27b (0.578) → gemma4:e4b (0.593)

**Scale-vs-harness progression (H6 baseline medication F1):**  
qwen3.5:9b (0.800) → qwen3.5:4b (0.814) → gemma4:e4b (0.849) → qwen3.6:27b (0.885)

**Definitive seizure-type ceiling finding:** The `unknown seizure type` miss count is consistently 13–15 across ALL models (qwen3.5:9b, qwen3.6:27b, qwen3.6:35b, gemma4:e4b) and ALL harnesses (H6, H6fs, H6v2, H6ev). Scale from 4B to 35B does not reduce this count. This is a structural annotation challenge — `unknown seizure type` is a meta-label used when the annotator cannot determine seizure type, but models consistently attempt to infer a specific type from context. **Closing this gap requires either a harness that more effectively teaches the meta-label semantics, or recognition that the gap is a benchmark artefact rather than a clinical extraction failure.**

---

### 5.13 Best-of-Model Summary (Local Workstream)


| Model       | Best harness | Med F1 | Sz F1 | Dx Acc | Lat | Use case                  |
| ----------- | ------------ | ------ | ----- | ------ | --- | ------------------------- |
| qwen3.5:4b  | H6           | 0.814  | 0.535 | 0.750  | 8s  | Ultra-low VRAM (~3–4 GB)  |
| qwen3.5:9b  | H6fs         | 0.839  | 0.602 | 0.825  | 12s | Best quality/speed 9B     |
| gemma4:e4b  | H6           | 0.849  | 0.593 | 0.825  | 28s | Best diagnosis accuracy   |
| qwen3.6:35b | H6fs         | 0.852  | 0.593 | 0.800  | 12s | Best speed at large scale |
| qwen3.6:27b | H6           | 0.885  | 0.578 | 0.800  | 34s | Best medication F1        |


**Recommended for clinical deployment:** qwen3.6:35b H6fs — matches frontier medication F1 at 12s/doc with no API cost or internet requirement.

**Total wall time for all local experiments:** ~4.6 hours. **Total API cost: $0.**

---

### 5.14 Local Event-First Investigation (EL0 / EL1 / EL2) — 2026-05-10/11

**Motivation:** The event-first pipeline (E1/E2/E3) is the strongest frontier system on ExECTv2 (E3 leads every medication metric, most robustness-robust). It was never tested on local models because Stage L1 was abandoned after qwen3.5:9b took >30 minutes per document. The hypothesis was that this abandonment was the extended-thinking token-exhaustion bug (the compat-shim silently ignoring `think: false`) rather than a genuine capability ceiling. A three-stage investigation was run: EL0 (re-diagnosis), EL1 (dev pilot), EL2 (validation).

**Source code:** `src/local_event_first.py`, `src/el1_rescore.py`

#### EL0: Re-Diagnosis (2 dev docs, H0 + EL_micro, qwen_9b + qwen_35b)

**Idea:** Run H0 (full canonical schema) under the fixed native Ollama API to determine whether the original L1 failure was the thinking bug or genuine incapability. Also run EL_micro (new minimal event list format) to check latency and parse.

**What happened:**

- qwen_9b H0: **108s/doc**, output_tokens=2048, parse=False (truncated at token limit — not a timeout). **Confirms L1 was the thinking bug**, not genuine H0 incapability.
- qwen_35b H0: **300s timeout** on both docs — the dense 35B model is too slow for H0's 2,000–3,000 token output at 300s Ollama limit, even without thinking.
- EL_micro (both models): parse=False due to a code bug — `extract_json_object` in the existing `parse_json_response` only extracts `{...}` delimiters, not `[...]` arrays. Fix applied to `_parse_event_list`; re-parsing the cached outputs confirmed all four responses were valid JSON arrays (events=3 and events=6 respectively).

**Learning:** L1 was a misdiagnosis — but only for qwen_9b. For qwen_35b, the full H0 canonical schema is genuinely too slow. E1 event extraction produces ~1,000 output tokens (less than H0's 2,000–3,000), making EL_E1E2 potentially viable for qwen_35b if each doc stays under 300s.

#### EL1: Development Pilot (10 dev docs, 3 harnesses × 4 models)

**Harnesses tested:** EL_micro, EL_compact, EL_E1E2 (qwen_4b excluded — HTTP 404, not pulled; qwen_27b excluded — compact docs hitting 278s, EL_E1E2 would all timeout).

**Parse success rates:**


| Model    | EL_micro | EL_compact | EL_E1E2          |
| -------- | -------- | ---------- | ---------------- |
| qwen_9b  | 10/10    | 10/10      | 10/10            |
| gemma_4b | 10/10    | 8/10       | **2/10**         |
| qwen_35b | 10/10    | 10/10      | 9/10 (1 timeout) |


gemma_4b EL_E1E2 at 2/10 parse: the full E1 event schema is a schema extension that gemma4 refuses to follow, exactly as H6qa/H6ev produced parse_error=40. The schema-extension aversion generalises to the E1 format.

**Dev pilot quality (10 docs, corrected scorer):**


| Model    | Harness    | Med F1 | Sz F1c    | Δsz vs H6   | Dx Acc |
| -------- | ---------- | ------ | --------- | ----------- | ------ |
| gemma_4b | EL_micro   | 0.973  | **0.769** | **+0.176*** | 0.900  |
| qwen_35b | EL_micro   | 0.973  | **0.692** | **+0.099*** | 0.900  |
| qwen_9b  | EL_E1E2    | 0.947  | **0.696** | **+0.094*** | 0.800  |
| qwen_9b  | EL_micro   | 0.919  | 0.609     | +0.007      | 0.700  |
| qwen_35b | EL_compact | 0.947  | 0.455     | −0.138      | 0.900  |
| gemma_4b | EL_compact | 0.933  | 0.500     | −0.093      | 0.875  |
| qwen_9b  | EL_compact | 0.895  | 0.571     | −0.031      | 0.800  |


Three conditions cleared the +0.03 seizure threshold on dev. EL_compact regressed all three models on seizure F1. EL_micro appeared to strongly help gemma_4b and qwen_35b. EL_E1E2 appeared to strongly help qwen_9b.

**Promotion to EL2:** EL_micro for all three models; EL_E1E2 for qwen_9b only (gemma_4b 2/10 parse; qwen_35b 238s/doc average — too slow for 40 docs within 300s timeout).

#### EL2: Validation Scale (40 val docs)

**Runs:** EL_micro (qwen_9b + gemma_4b + qwen_35b, task bx2507sws); EL_E1E2/qwen_9b (task bjdk65w5a). Both ran in parallel, sharing the Ollama server — contention caused qwen_9b EL_micro to slow from 12s to ~65s/doc during overlap.

**Final combined EL2 results:**


| Model    | Harness  | Parse | Med F1 | Sz F1c | Δsz    | Dx Acc | Lat/doc |
| -------- | -------- | ----- | ------ | ------ | ------ | ------ | ------- |
| qwen_9b  | EL_micro | 1.00  | 0.779  | 0.538  | −0.064 | 0.825  | 61s     |
| qwen_9b  | EL_E1E2  | 0.95  | 0.807  | 0.594  | −0.008 | 0.816  | 77s     |
| gemma_4b | EL_micro | 1.00  | 0.818  | 0.506  | −0.087 | 0.825  | 64s     |
| qwen_35b | EL_micro | 1.00  | 0.855  | 0.585  | −0.008 | 0.825  | 41s     |


**Flags (Δsz ≥ +0.03): None.** Every condition is at or below its H6 baseline on seizure type.

**H6 baselines for reference:** qwen_9b H6fs 0.839/0.602/0.825 · gemma_4b H6 0.849/0.593/0.825 · qwen_35b H6fs 0.852/0.593/0.800

**What happened to the dev pilot gains:**


| Dev pilot claim             | Validation | Verdict               |
| --------------------------- | ---------- | --------------------- |
| gemma_4b EL_micro +0.176 sz | −0.087     | Noise — reversed sign |
| qwen_35b EL_micro +0.099 sz | −0.008     | Noise — vanished      |
| qwen_9b EL_E1E2 +0.094 sz   | −0.008     | Noise — vanished      |


**Root cause of EL_micro underperformance:** The extract-then-aggregate path forces the model to list raw event mentions before mapping to closed benchmark labels. The aggregation step then has to re-map those mentions — exactly the problem H6 solves in a single pass with an explicit `Allowed labels:` block. The two-step design adds latency and re-introduces the label-mapping problem without providing any structural benefit on seizure type. EL_compact performed worst of all three harnesses because its typed schema (with dose/unit/frequency/modality fields) creates cognitive overhead without a corresponding quality gain.

**Note on qwen_35b EL_micro diagnosis accuracy:** +0.025 above H6fs baseline (0.825 vs 0.800). This was the one positive signal, but at 3.4× latency cost and with no improvement on the primary seizure type metric, it is not sufficient to justify using EL_micro in deployment.

**Definitive conclusion:** H6/H6fs remains the correct harness for all local models on this task. Event-first extraction does not provide a seizure-type advantage at any model size tested (4B–35B). The L1 re-diagnosis confirmed the original abandonment was a bug for qwen_9b — but fixing the bug does not change the substantive experimental outcome. The simpler single-pass harness outperforms the more complex event-first pipeline on all primary metrics.

---

### 5.15 Multi-Agent MA_v1 Pipeline (MA0–MA3) — 2026-05-11

**Motivation:** Evaluate a four-role decomposition (segmentation → parallel field extractors → verifier → aggregator) as an alternative to single-pass H6 and to event-first E1/E2/E3, using the same canonical projection and corrected scorer as the rest of the project.

**Source code:** `src/multi_agent.py`  
**Artifacts (gitignored):** `runs/multi_agent/stage_ma0_stub`, `stage_ma1_dev_pilot`, `stage_ma2_validation`, `stage_ma3_gpt55` — per-document trees `{model}/MA_v1/{doc_id}/` with `canonical.json`, stage prompts/JSON, and response logs; stage roots hold `call_report.csv`, `evaluation_summary.csv`, `manifest.json`, `registry_snapshot.json`. After separate MA1 invocations per model, `**python src/multi_agent.py score --run-dir …`** produced `**evaluation_summary_rescored.csv**` so one CSV reflects every `canonical.json` under that stage (numbers in §10 and in the tables below match those rescored summaries).

**BenchComp** uses the same benchmark composite weights as `final_full_field.py` (medication name, seizure collapsed, diagnosis collapsed/plain, EEG, MRI).

#### MA0 (stub)

**Run:** `runs/multi_agent/stage_ma0_stub`  
**Idea:** End-to-end plumbing without API calls (`--stub-calls`).  
**Learning:** Same discipline as milestone stubs — verify mechanics before spend.

#### MA1 — development pilot (10 docs, ExECTv2 development split)


| Condition            | Med F1 | Sz F1 collapsed | Dx Acc | EEG   | MRI   | BenchComp |
| -------------------- | ------ | --------------- | ------ | ----- | ----- | --------- |
| gpt_5_4_mini:MA_v1   | 1.000  | 0.720           | 0.900  | 1.000 | 0.900 | **0.898** |
| qwen_35b_local:MA_v1 | 0.947  | 0.583           | 0.900  | 0.900 | 0.900 | 0.835     |


GPT-5.4-mini leads this pilot on BenchComp; local qwen_35b stays close on diagnosis and investigations but trails on medication and seizure collapsed F1.

#### MA2 — validation scale (40 docs), promotion gate

**Run:** `runs/multi_agent/stage_ma2_validation`  
**Models:** `gpt_5_4_mini`, `qwen_35b_local` on the same validation document IDs.


| Condition            | Med F1 | Sz F1 collapsed | Dx Acc | EEG   | MRI   | BenchComp |
| -------------------- | ------ | --------------- | ------ | ----- | ----- | --------- |
| gpt_5_4_mini:MA_v1   | 0.868  | 0.610           | 0.775  | 0.925 | 0.825 | 0.757     |
| qwen_35b_local:MA_v1 | 0.868  | 0.603           | 0.800  | 0.950 | 0.900 | 0.772     |


**Promotion gates (MA2 → MA3, from `docs/36_multi_agent_pipeline_plan.md`):** BenchComp > **0.810** (beats frontier E3 composite anchor); seizure F1 collapsed ≥ **0.660**.

**Promotion decision:** **No promotion** — BenchComp 0.757 / 0.772 are below 0.810; seizure collapsed 0.610 / 0.603 are below 0.660.

**Learning:** On 40 validation documents this decomposition does not clear the planned gates versus the E3 anchor encoded in promotion rules.

#### MA3 — GPT-5.5 on validation (40 docs)

**Run:** `runs/multi_agent/stage_ma3_gpt55`  
**Rationale:** Exercise a heavier frontier model on the MA2 document set after MA2 failed promotion for the lighter models.


| Condition     | Med F1 | Sz F1 collapsed | Dx Acc | EEG   | MRI   | BenchComp |
| ------------- | ------ | --------------- | ------ | ----- | ----- | --------- |
| gpt_5_5:MA_v1 | 0.769  | 0.379           | 0.750  | 0.875 | 0.800 | 0.650     |


**Learning:** MA_v1 with GPT-5.5 **regresses** versus MA2 conditions on BenchComp and especially seizure collapsed F1, suggesting error propagation across stages rather than a fix from scaling model size alone.

---

## 6. Seizure Frequency Workstream (G0–G4)

### 6.1 Context and Benchmarks

The seizure frequency field scored 0.000 across all systems under the original scorer. After the Phase 1/2 gold-loader fix, loose accuracy reached 0.075–0.175 — still far below the ExECTv2 rule-based benchmark of 0.66–0.68 (Fonferko-Shadrach 2024). A dedicated workstream was opened with a **different primary benchmark**: Gan et al. 2026.

**Why Gan over ExECTv2 for frequency:** ExECTv2 scores multi-mention frequency extraction (all frequency mentions per letter). Gan scores category-level extraction after normalizing a single frequency to a seizures/month rate. Gan was designed around frequency normalization, structured labels, evidence spans, cluster patterns, seizure-free intervals, unknown/no-reference handling — exactly the task the dissertation wants to claim. The ExECTv2 frequency score remains a crosswalk metric only.

**Gan benchmark targets:**

- Pragmatic micro-F1 ≥ 0.85 (clinically useful 4-class grouping)
- Purist micro-F1 reported as harder secondary metric (10-bin fine-grained)
- Published best: Qwen2.5-14B CoT(15000) = 0.847; MedGemma-4B CoT(15000) = 0.858

**Important caveat:** Gan's published figures used a clinician double-checked real-letter test set. Our experiments use the released synthetic subset. Any claim matching Gan's figures must state this distinction.

---

### 6.2 Stage G0: Gan Gold Audit and Metric Lock

**Artifact:** `runs/gan_frequency/audit/`  
**Idea:** Before any model calls, verify the gold distribution and lock the metric calculation. Prevent the ExECTv2 gold-loader-bug problem from recurring.  
**What happened:** Implemented in `src/gan_frequency.py`. Loaded 1,500 examples; extracted normalized labels; mapped to Purist (10-bin) and Pragmatic (4-class) categories; wrote `gan_gold_labels.csv` and `gan_gold_audit.json`. Label converter verified on manual cases. Stub smoke tests confirmed scoring pipeline end-to-end.  
**Learning:** Locking the metric before running experiments is the right discipline — the ExECTv2 experience showed what happens when you don't.

---

### 6.3 Stage G1: Prediction Harness (Stub Verification)

**Artifact:** `runs/gan_frequency/stage_g1/`  
**Idea:** Build a frequency-only extraction harness whose output can be scored by the Gan evaluator. Five harnesses: `Gan_direct_label`, `Gan_cot_label`, `Gan_evidence_label`, `Gan_two_pass`, `Gan_fs_hard`. Verify with stub calls before spending budget.  
**What happened:** All five harnesses stub-verified. Each writes `predictions.json`, `call_report.csv`, and `gan_frequency_evaluation.json`. The output format is a single normalized label per document ID (e.g., `"2 per 5 month"`, `"seizure free for 12 month"`, `"unknown"`, `"no seizure frequency reference"`).  
**Learning:** The prediction harness worked cleanly. The decision to invest in a clean score-before-run infrastructure paid off in G2 when it made fast iteration over 12 conditions possible.

---

### 6.4 Stage G2: Model × Prompt Sweep (50 docs, $4.54 total)

**Design:** 3 models × 4 harnesses = 12 conditions; 50 deterministic development docs; 1 repeat.  
**Models:** `gpt_4_1_mini_baseline`, `gpt_5_5`, `claude_sonnet_4_6`, `qwen_35b_local` (note: the initial G2 plan included claude_sonnet_4_6 as one of the sweep models).  
**Idea:** Establish whether stronger models, CoT reasoning, evidence grounding, or two-pass normalization can approach the Gan Pragmatic micro-F1 target. The two-pass harness was expected to do well because Gan's paper used evidence-grounded supervision.  
**Important note on GPT-5.5:** GPT-5.5 had 15/150 empty-response failures due to `max_output_tokens=512` budget exhaustion — all tokens were consumed by internal reasoning before the output was produced. This depressed GPT-5.5 scores in G2. Results corrected in G4-Fixed.

**G2 results (note: GPT-5.5 depressed by token budget issue):**


| Rank | Model             | Harness          | Prag F1 | Pur F1 | Exact | Parse OK | Cost  |
| ---- | ----------------- | ---------------- | ------- | ------ | ----- | -------- | ----- |
| 1    | gpt_5_5           | Gan_direct_label | 0.760   | 0.760  | 0.600 | 0.887    | $0.62 |
| 2    | gpt_5_5           | Gan_cot_label    | 0.800*  | —      | —     | —        | $0.62 |
| 3    | claude_sonnet_4_6 | Gan_direct_label | 0.760   | 0.760  | 0.580 | —        | $0.30 |
| 4    | gpt_4_1_mini      | Gan_direct_label | 0.713   | 0.673  | 0.480 | 0.993    | $0.02 |
| 5    | qwen_35b_local    | Gan_direct_label | 0.700   | 0.667  | 0.520 | 1.000    | $0    |
| 6    | gpt_5_5           | Gan_two_pass     | 0.340   | 0.340  | 0.180 | —        | $1.11 |


*gpt_5_5 + Gan_cot_label: 0.800 from doc 21 (phase3_synthesis_report shows as the G2 winner). The G2 result table in doc 26 shows a slightly different ordering due to parse failures; the 0.800 figure is authoritative.

**Promotion decision:** `gpt_5_5` + `Gan_cot_label` → Stage G3. Exceeded the 0.75 Pragmatic micro-F1 promotion threshold. Two-pass not carried forward: worst condition at highest cost with frequent parse errors.  
**Learning:** CoT label outperforms direct label for GPT-5.5. Evidence label hurts (model attaches a quote but the normalization step is impaired). Two-pass normalization — despite being conceptually closest to Gan's training procedure — performs worst of all, suggesting the two-pass output-path parsing needs hardening. GPT-4.1-mini's 0.713 is surprisingly good at 2¢/50 docs.

---

### 6.5 Stage G3: Hard-Case Prompt Development (50-doc controlled subset)

**Idea:** Iterate the best G2 model/harness on hard Gan patterns: clusters, ranges, seizure-free intervals, unknown frequency, no-reference cases. Also keep G2 conditions as carry-forwards for controlled comparison.  
**New harness tested:** `Gan_fs_hard` — adds five few-shot examples covering the hardest Gan categories (cluster days, seizure-free-for-N-months, sporadic unclear, no-reference, multiple seizure types).  
**What happened:** The hard-case few-shot prompt **reduced** Pragmatic micro-F1 from 0.80 to 0.64 on the controlled 50-doc subset. No G3 condition beat the G2 best.


| Rank | Condition                                       | Prag F1  | Pur F1 | Exact | Cost  |
| ---- | ----------------------------------------------- | -------- | ------ | ----- | ----- |
| 1    | gpt_5_5 + Gan_cot_label (G2 carry)              | **0.80** | 0.76   | 0.54  | $0.62 |
| 2    | gpt_5_5 + Gan_direct_label (G2 carry)           | 0.76     | 0.76   | 0.60  | $0.62 |
| 3    | claude_sonnet_4_6 + Gan_direct_label (G2 carry) | 0.76     | 0.76   | 0.58  | $0.30 |
| 4    | gpt_4_1_mini + Gan_direct_label (G2 baseline)   | 0.66     | 0.62   | 0.48  | $0.02 |
| 5    | gpt_5_5 + Gan_fs_hard (G3 new)                  | 0.64     | 0.62   | 0.50  | $0.63 |


**G3 addendum — qwen35_b baseline (150 docs):**
`qwen_35b_local` + `Gan_g3_qwen` on 150 documents:

- Pragmatic micro-F1: 0.6933 | Purist: 0.6667 | Parse: 98.7% | Quote: 96.7%
- Artifacts: `runs/gan_frequency/stage_g3_minimal_port/qwen_35b_local_Gan_g3_qwen/`

**Learning:** Hard-case few-shot examples actively hurt performance on a controlled subset — the same pattern as Variant A for gemma4 in the local workstream. Adding examples for specific hard patterns can harm model behavior on the easy majority. The best prompt from G2 remained the best prompt after G3. This suggests that further prompt iteration has diminishing returns; what is needed is either a retrieval mechanism or higher max_output_tokens.

---

### 6.6 Stage G4-Retrieval Initial Run (50 docs, 512 token limit — superseded)

**Artifacts:** `runs/gan_frequency/stage_g4_retrieval/`  
**Idea:** Test whether providing retrieved frequency-relevant spans as highlighted context before extraction improves Pragmatic F1 above the 0.85 threshold.  
**What happened:** GPT-5.5 parse failures returned. Root cause: `reasoning_tokens: 512` / `output_tokens: 512` — identical to G2. GPT-5.5 consumed its full token budget on internal reasoning before producing output. Results for GPT-5.5 are artificially depressed.  
**Learning:** **Always use `--max-output-tokens 2048` for GPT-5.5 (reasoning model)**. The 512 default is completely inadequate for reasoning models and silently produces empty outputs that look like low scores.

---

### 6.7 Stage G4-Retrieval Fixed Run (50 docs, 2048 token limit — authoritative)

**Artifacts:** `runs/gan_frequency/stage_g4_fixed/`  
**Fix:** `--max-output-tokens 2048`. All GPT-5.5 conditions now at 100% parse success.  
**New harnesses:** `Gan_retrieval_highlight` (retrieval + extraction), `Gan_retrieval_only_ablation` (retrieval only, no extraction — ablation control).


| Rank | Model          | Harness                     | Prag F1   | Pur F1 | Exact | Parse | Quote |
| ---- | -------------- | --------------------------- | --------- | ------ | ----- | ----- | ----- |
| 1    | gpt_5_5        | Gan_retrieval_highlight     | **0.840** | 0.820  | 0.820 | 1.000 | 0.960 |
| 2    | gpt_5_5        | Gan_cot_label               | 0.760     | 0.720  | 0.720 | 1.000 | 1.000 |
| 3    | gpt_5_5        | Gan_direct_label            | 0.740     | 0.720  | 0.720 | 1.000 | 1.000 |
| 4    | qwen_35b_local | Gan_retrieval_highlight     | 0.720     | 0.680  | 0.680 | 0.980 | 1.000 |
| 5    | qwen_35b_local | Gan_direct_label            | 0.700     | 0.680  | 0.680 | 1.000 | 1.000 |
| 6    | qwen_35b_local | Gan_cot_label               | 0.600     | 0.560  | 0.560 | 1.000 | 1.000 |
| 7    | gpt_5_5        | Gan_retrieval_only_ablation | 0.520     | 0.460  | 0.460 | 1.000 | 0.980 |
| 8    | qwen_35b_local | Gan_retrieval_only_ablation | 0.480     | 0.460  | 0.460 | 1.000 | 1.000 |


**Key findings:**

- Retrieval highlight is the clear winner: +8pp over cot_label (0.840 vs 0.760), 15 vs 23 errors.
- **Ablation finding (critical):** retrieval-only (0.520) is 32pp below retrieval-highlight (0.840). Retrieved spans are useful salience cues, not sufficient context for accurate normalization. The extraction instruction is doing most of the work; retrieval primes the model.
- Strict WP7 threshold (0.85) not met: 0.840 is 1pp short on 50 documents, which is within sampling noise.
- gpt_5_5 + Gan_cot_label in the fixed run scores 0.760 — this is lower than its G2 result of 0.800 because the G2 parse failures artificially inflated precision (only parseable successful outputs were scored).

**Error audit (fixed run):**

- gpt_5_5 + Gan_retrieval_highlight: 15/50 errors — `other` (12), `gold_UNK_pred_numeric` (2), `cluster_collapsed` (1), `range_collapsed` (1). All genuine category mismatches; no parse artifacts.
- gpt_5_5 + Gan_cot_label: 23/50 errors — `other` (18) dominant.

**Promotion decision:** `gpt_5_5` + `Gan_retrieval_highlight` + `--max-output-tokens 2048` → G4-Full. The 1pp-below-threshold result on 50 docs is within sampling noise. G4-Full at 1,500 docs will give a reliable estimate.  
**Learning:** Retrieval augmentation is the right direction for frequency extraction. It improves exact label accuracy from 0.720 to 0.820 — a large jump. The retrieval-only ablation confirms the mechanism: retrieved spans help by priming the model's attention, not by providing direct answers.

---

### 6.8 G4-Full (Pending)

**Promoted condition:** `gpt_5_5` + `Gan_retrieval_highlight` + `--max-output-tokens 2048`  
**Baseline comparison:** `gpt_5_5` + `Gan_cot_label` + `--max-output-tokens 2048`  
**Full 1,500 local synthetic docs.**  
**Status: not yet run.**

---

## 7. Cross-Cutting Synthesis

### Finding 1: The scorer was materially broken for the first half of the project

The original final_validation medication full tuple F1 (0.386/0.343/0.400) understated true performance by 70–85% relative. Original seizure frequency=0.000 was a gold-loader bug. Original seizure type F1=0.187–0.200 was a taxonomy mismatch. **Any claim or conclusion drawn before Phase 2+3 corrections must be treated with suspicion.** The scoring repair — particularly the gold-loader null-string fix, the ASM synonym expansion, and the collapsed label approach — is itself a dissertation methods contribution demonstrating that metric design and gold data quality are as important as model selection.

---

### Finding 2: Benchmark quality is tightly clustered across frontier models; cost is not

Stage A (15 dev docs): GPT-4.1-mini (0.784), GPT-5.5 (0.789), GPT-5.4-mini (0.781), Claude Sonnet 4.6 (0.782). This 8pp range is smaller than the noise on 15 documents. GPT-4.1-mini costs $0.005/quality-point vs $0.107 for GPT-5.5 (21×). **No quality gap justifies frontier premium at ExECTv2 extraction scale.** However, for the Gan frequency task, GPT-5.5 does outperform GPT-4.1-mini by 8–14pp (0.713→0.840 Pragmatic F1) — a task-specific finding that reverses the conclusion.

---

### Finding 3: Local models match or exceed frontier on the primary ExECTv2 fields at zero cost

qwen3.6:27b H6: medication name F1=0.885 — the first local model to exceed both frontier baselines on medication. qwen3.6:35b H6fs matches GPT-4.1-mini S2 exactly on medication (0.852) at 12s/doc. gemma4:e4b achieves the highest diagnosis accuracy of any model tested (0.825, vs frontier best 0.775). The local workstream demonstrates that privacy-constrained offline clinical deployment is operationally viable for the primary extraction task.

---

### Finding 4: Seizure type improvement is a normalization problem, not a model problem

H7 (two-pass normalization, GPT-4.1-mini) achieved seizure_type_F1=0.698 on development — a 37% relative improvement over H0's 0.512 from normalization alone, with no prompt changes. The collapsed label scorer (benchmark_seizure_type_label) reproduced most of this gain in the evaluator without re-running models. The remaining gap to the Fang benchmark target (≥0.76) is explained by: (a) the `unknown seizure type` meta-label problem (13–15 misses consistently across all models and scales), and (b) the 13.3% oracle failure rate from annotation gaps in ExECTv2 itself.

---

### Finding 5: The `unknown seizure type` meta-label is a structural ceiling

Across all models (4B to 35B), all harnesses (H6, H6fs, H6v2, H6ev, H6qa), the miss count for `unknown seizure type` is consistently 13–15 out of 26 docs that have this gold label. Scale does not close this gap. This label is used when the annotator cannot determine seizure type — a meta-judgment about absence of information. Models consistently attempt to infer a specific type from clinical context rather than producing the meta-label. This appears to be a genuine structural difference between what models do (infer) and what the annotation scheme requires (abstain).

---

### Finding 6: Evidence grounding is a structural guarantee, not a quality cost

Quote validity never fell below 0.960 under any perturbation, split, or system. Schema validity is 1.000 for all validation conditions. Label-changing validity (30 contrast documents) confirms evidence integrity holds even when document content changes ground-truth labels. The architecture's evidence discipline — requiring every extraction to be grounded in a verbatim quote — provides a strong clinical safety signal at no accuracy cost.

---

### Finding 7: E3 is the best ExECTv2 system; S2 is surprisingly strong on test

E3 leads every medication metric on both splits, ties or leads on investigations, and has the best validation diagnosis accuracy. It is also the most robustness-robust system (worst perturbation drop half of S2's). However, on the test split, S2 achieves the highest diagnosis accuracy (0.850 vs E3's 0.750) — suggesting that for holistic diagnosis on diverse documents, the full-letter context of a direct extraction approach can outperform event-first aggregation. This may reflect that S2 sees the full diagnostic narrative, whereas E3 aggregates from individually extracted events that may lose global coherence.

---

### Finding 8: Few-shot examples have model-specific effects

Variant A (H6fs) improved qwen3.5:9b by +6.1pp seizure F1 but harmed gemma4:e4b by −3.2pp. At 27B scale, H6fs harmed qwen3.6:27b by −4.7pp on medication. qwen3.6:35b (MoE architecture) uniquely tolerated H6fs without regression. For the Gan workstream, hard-case examples harmed GPT-5.5 cot_label performance. The same pattern appears repeatedly: **guidance that helps the model that needs it harms the model that doesn't**. Capability-appropriate prompt design is required. A single universal harness is not the right abstraction for a multi-model dissertation claim.

---

### Finding 9: Seizure frequency extraction remains an open problem on ExECTv2

After all scoring fixes, ExECTv2 seizure frequency loose accuracy is 0.075–0.175. The 29.2% oracle failure rate means even perfect extraction cannot score above ~0.71 on this dataset. The Gan workstream is the right venue for frequency claims. The ExECTv2 frequency field should be reported as a secondary crosswalk only, not as the primary frequency result.

---

### Finding 11: Event-first does not help local models; H6/H6fs dominates across all harnesses tested

The local event-first investigation (EL0/EL1/EL2, 2026-05-10/11) produced a clean negative result. Three harness designs were tested: EL_micro (flat event array, simplest possible), EL_compact (typed events with structured fields), and EL_E1E2 (full frontier E1 prompt + deterministic E2 aggregation). None improved seizure type F1 at 40-doc validation scale: deltas ranged from −0.087 (gemma_4b EL_micro) to −0.008 (qwen_35b EL_micro and qwen_9b EL_E1E2). Three apparent gains in the 10-doc dev pilot (+0.176, +0.099, +0.094) were all sampling noise that reversed sign or vanished at 40 docs.

The structural reason: the two-step extract-then-aggregate design forces the model to describe mentions in free text before mapping to closed benchmark labels, reintroducing exactly the normalization problem that H6's `Allowed labels:` block solves in a single pass. EL_compact performed worst because its richer schema (dose/unit/frequency/modality) adds complexity without structural benefit.

One latency finding stands: qwen_9b H0 terminates in 108s under the fixed native Ollama API — the original L1 abandonment was the thinking-token-exhaustion bug. But this does not change the outcome: the event-first pipeline is not useful for local models on this task regardless of whether H0 is technically feasible.

---

### Finding 10: GPT-5.5 retrieval augmentation is the most promising Gan approach

G4-Fixed: `gpt_5_5` + `Gan_retrieval_highlight` = 0.840 Pragmatic F1 on 50 docs — 1pp below the 0.85 target, within sampling noise. The retrieval-only ablation (0.520) confirms the mechanism: salience priming, not direct lookup. G4-Full at 1,500 docs will give a reliable estimate and may cross 0.85.

---

### Finding 12: MA_v1 multi-agent pipeline cleared MA1 dev pilot but failed MA2 promotion gates

The four-stage MA_v1 design achieves strong **development** BenchComp with `gpt_5_4_mini` (0.898 on 10 docs) but **does not** exceed the planned MA2 promotion thresholds on **40 validation** documents for either `gpt_5_4_mini` or `qwen_35b_local` (BenchComp 0.757 / 0.772 vs gate 0.810; seizure collapsed 0.610 / 0.603 vs gate 0.660). A follow-on `gpt_5_5` MA3 run **regressed further** (BenchComp 0.650, seizure collapsed 0.379), indicating pipeline fragility rather than a simple “use a bigger model” fix.

### Finding 13: H7 and D3 validation-scale medication_full collapse was a prompt bug, not an architectural limit

**Initial runs (2026-05-11):** Both H7 and D3 at 40-doc validation scored medication_full_f1 ≈ 0.018 — effectively zero — while performing well on medication_name (0.836–0.879), seizure_type (0.412–0.450), and diagnosis (0.750–0.800). The initial diagnosis blamed the two-pass architecture: candidate/verifier passes extract rich text but the verifier prompt was instructed to output only flat `medication_names` (name + quote), not structured medications with dose/unit/frequency.

**Investigation:** The projection code `medication_from_text()` parses dose and frequency from the medication *name string* itself. Since the verifier obediently stripped dose/frequency and returned bare drug names ("lamotrigine" instead of "lamotrigine 75mg bd"), parsing always returned `None`. The candidate pass *did* contain full structured text; the verifier simply wasn't asked to preserve it. H7 showed the identical collapse (same micro-F1s to 4 decimal places), confirming a shared prompt bug.

**Fix (2026-05-11):** Updated `src/model_expansion.py`:
- Changed D3 verifier prompt output shape from `{"medication_names":[{"name":"","quote":""}]}` to `{"medications":[{"name":"","dose":null,"unit":null,"frequency":null,"quote":""}]}`
- Changed H7 normalize prompt output shape similarly
- Updated instructions to ask the model to extract dose, unit, and frequency from the source quote
- Fixed `_has_structured_meds` branch to preserve quote evidence for structured medications
- Fixed `_build_med` to pass quotes through `evidence_from_quote()` for structured items

**Reruns (2026-05-11):**

| Metric | H7 (old) | H7 (fixed) | D3 (old) | D3 (fixed) |
| ------ | -------- | ---------- | -------- | ---------- |
| medication_full_f1 | 0.018 | **0.600** | 0.018 | **0.614** |
| medication_dose_f1 | 0.040 | **0.876** | 0.040 | **0.835** |
| medication_dose_unit_f1 | 0.043 | **0.837** | 0.043 | **0.848** |
| medication_frequency_f1 | 0.042 | **0.738** | 0.042 | **0.731** |
| medication_name_f1 | 0.836 | 0.821 | 0.879 | 0.860 |
| seizure_type_f1 | 0.412 | 0.379 | 0.450 | 0.442 |
| epilepsy_diagnosis_accuracy | 0.775 | 0.750 | 0.800 | 0.800 |
| benchmark_quality | 0.675 | 0.650 | 0.710 | 0.701 |
| schema_valid_rate | 0.975 | 0.950 | 1.000 | 1.000 |
| quote_validity_rate | 1.000 | 1.000 | 1.000 | 1.000 |

**Result:** medication_full_f1 recovered from ~0.018 to ~0.61 (30–35× improvement). D3 fixed (0.614) is now close to S2 (0.655); H7 fixed (0.600) is in the same ballpark. Small tradeoffs on med_name (−1–2pp), seizure_f1 (−1–3pp), and H7 schema_valid (−2.5pp) reflect the added output complexity. Both systems remain below the E3 benchmark_quality gate (~0.76), so **promotion decision stays not promoted**.

---

## 8. Current Status and Pending Runs


| Run ID                        | Description                                                                       | Status                                          | Blocking?                                                                                           |
| ----------------------------- | --------------------------------------------------------------------------------- | ----------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| MA_v1 MA1–MA3                 | Multi-agent pipeline: MA1 dev (10), MA2 val (40) × 2 models, MA3 val (40) GPT-5.5 | **Complete** (2026-05-11); MA2/MA3 no promotion | Optional further MA prompt/stage work — not on dissertation critical path unless claims adopt MA_v1 |
| EL0/EL1/EL2 local event-first | EL_micro + EL_E1E2 across qwen_9b, gemma_4b, qwen_35b                             | **Complete** (2026-05-10/11)                    | No further runs needed — negative result                                                            |
| G4-Full                       | `gpt_5_5` + `Gan_retrieval_highlight`, 1,500 Gan docs                             | Not started                                     | Main frequency claim                                                                                |
| F5b / F5b-fs / F5b-full       | gemma_26b_local H6/H6fs/H6full, 40 val docs                                       | **Cancelled** (2026-05-11)                      | Final full-field evaluation — inference too slow; qwen3.6:35b superior                              |
| F5c / F5c-fs / F5c-full       | gemma_31b_local H6/H6fs/H6full, 40 val docs                                       | **Cancelled** (2026-05-11)                      | Final full-field evaluation — 31B would be slower than 26B; already ruled unviable                  |
| H7 validation scale (fixed prompt) | GPT-4.1-mini H7 with structured medications, 40 val docs                     | **Complete** (2026-05-11); not promoted         | H7 promotion decision — medication_full recovered after prompt fix; still below S2/E3 on benchmark_quality |
| D3 validation scale (fixed prompt) | GPT-5.5 D3 with structured medications, 40 val docs                          | **Complete** (2026-05-11); not promoted         | D3 promotion decision — medication_full recovered after prompt fix; best seizure F1 but benchmark_quality below E3 |
| ExECTv2 frequency crosswalk   | Per-letter accuracy rescore of existing runs                                      | Planned                                         | Conditional on G4-Full                                                                              |
| Final dissertation freeze     | Freeze all system IDs, metrics, and model versions                                | Pending all above                               | Dissertation submission                                                                             |


### Final Candidate Registry (final_full_field evaluation)


| ID       | Model        | Harness | Purpose                              | Status       |
| -------- | ------------ | ------- | ------------------------------------ | ------------ |
| F1       | GPT-4.1-mini | S2      | Strong direct frontier baseline      | existing run |
| F2       | GPT-4.1-mini | E3      | Strong event-first frontier baseline | existing run |
| F3       | qwen3.6:35b  | H6fs    | Primary local deployment candidate   | existing run |
| F3-H6    | qwen3.6:35b  | H6      | Local ablation (plain harness)       | existing run |
| F4       | qwen3.6:27b  | H6      | Best local medication F1             | existing run |
| F4-fs    | qwen3.6:27b  | H6fs    | Best medication with few-shot        | existing run |
| F5       | gemma4:e4b   | H6      | Best local diagnosis accuracy        | existing run |
| F5-fs    | gemma4:e4b   | H6fs    | Gemma4 few-shot ablation             | existing run |
| F5b      | gemma4:26b   | H6      | Expanded gemma scale 26B             | cancelled    |
| F5b-fs   | gemma4:26b   | H6fs    | Gemma4 26B few-shot                  | cancelled    |
| F5b-full | gemma4:26b   | H6full  | Gemma4 26B full-field harness        | cancelled    |
| F5c      | gemma4:31b   | H6      | Expanded gemma scale 31B             | cancelled    |
| F5c-fs   | gemma4:31b   | H6fs    | Gemma4 31B few-shot                  | cancelled    |
| F5c-full | gemma4:31b   | H6full  | Gemma4 31B full-field harness        | cancelled    |
| 9b-ref   | qwen3.5:9b   | H6fs    | Reference: best 9B system            | existing run |


---

## 9. Model Inventory

All models ever called in this project:


| Model label                  | Provider                    | Used in                                                      | Real calls                      |
| ---------------------------- | --------------------------- | ------------------------------------------------------------ | ------------------------------- |
| gpt_4_1_mini_baseline        | OpenAI GPT-4.1-mini         | S2, E2, E3, H0, H6, H7, D3, Gan_direct/cot/evidence          | Yes (primary)                   |
| gpt_5_5                      | OpenAI GPT-5.5              | Stage A/B/D/E, Gan G2/G3/G4, MA_v1 MA3                       | Yes                             |
| gpt_5_4_mini                 | OpenAI GPT-5.4-mini         | Stage A/B/C1/D/E, MA_v1 MA1/MA2                              | Yes                             |
| claude_sonnet_4_6            | Anthropic Claude Sonnet 4.6 | Stage A/B, Gan G2/G3                                         | Yes                             |
| gemini_3_1_flash             | Google Gemini 3.1 Flash     | Stage A/C1                                                   | Yes (excluded from formal runs) |
| gemini_3_1_pro               | Google Gemini 3.1 Pro       | Stage A                                                      | Yes (limited)                   |
| qwen3.5:9b (qwen_9b_local)   | Ollama local                | L2–L6, N1–N6, Variants A/B/C, EL0/EL1/EL2                    | Yes                             |
| qwen3.5:4b                   | Ollama local                | L3/L5, N3                                                    | Yes                             |
| gemma4:e4b (gemma_4b_local)  | Ollama local                | N4, Variants A/B/C, EL1/EL2                                  | Yes                             |
| qwen3.6:27b (qwen_27b_local) | Ollama local                | Large model validation, F4, EL1 (partial — too slow)         | Yes                             |
| qwen3.6:35b (qwen_35b_local) | Ollama local                | Large model validation, F3, G2/G3/G4, EL1/EL2, MA_v1 MA1/MA2 | Yes                             |
| gemma4:26b (gemma_26b_local) | Ollama local                | F5b cancelled — inference too slow, qwen3.6:35b superior     | Cancelled (2026-05-11)          |
| gemma4:31b (gemma_31b_local) | Ollama local                | F5c cancelled — 31B unviable on this hardware                | Cancelled (2026-05-11)          |
| stub                         | Internal stub               | All milestone and smoke runs                                 | N/A (no model calls)            |


---

## 10. Authoritative Number Reference

Numbers to use in the dissertation. All from corrected scorer unless noted.

### ExECTv2 Baseline (GPT-4.1-mini, corrected scorer)


| Split | System | Med Name F1 | Med Full F1 | Sz Collapsed F1 | Freq Loose | Dx Acc    | Schema | Quote |
| ----- | ------ | ----------- | ----------- | --------------- | ---------- | --------- | ------ | ----- |
| val   | S2     | 0.852       | 0.655       | 0.610           | 0.075      | 0.725     | 1.000  | 0.991 |
| val   | E3     | **0.872**   | **0.707**   | **0.633**       | 0.125      | **0.775** | 1.000  | 0.994 |
| test  | S2     | 0.885       | 0.769       | 0.415           | 0.175      | **0.850** | 0.950  | 0.993 |
| test  | E3     | **0.847**   | **0.724**   | 0.469           | 0.125      | 0.750     | 0.975  | 1.000 |


### Local Models (validation, corrected scorer)


| Model       | Best harness | Med Name F1 | Sz Collapsed F1 | Dx Acc |
| ----------- | ------------ | ----------- | --------------- | ------ |
| qwen3.5:9b  | H6fs         | 0.839       | 0.602           | 0.825  |
| gemma4:e4b  | H6           | 0.849       | 0.593           | 0.825  |
| qwen3.6:27b | H6           | **0.885**   | 0.578           | 0.800  |
| qwen3.6:35b | H6fs         | 0.852       | 0.593           | 0.800  |


### MA_v1 multi-agent (corrected scorer, `evaluation_summary_rescored.csv` per stage)

Development (MA1, 10 docs):


| Condition            | Med Name F1 | Sz collapsed F1 | Dx Acc | BenchComp |
| -------------------- | ----------- | --------------- | ------ | --------- |
| gpt_5_4_mini:MA_v1   | 1.000       | 0.720           | 0.900  | 0.898     |
| qwen_35b_local:MA_v1 | 0.947       | 0.583           | 0.900  | 0.835     |


Validation (MA2, 40 docs):


| Condition            | Med Name F1 | Sz collapsed F1 | Dx Acc | BenchComp |
| -------------------- | ----------- | --------------- | ------ | --------- |
| gpt_5_4_mini:MA_v1   | 0.868       | 0.610           | 0.775  | 0.757     |
| qwen_35b_local:MA_v1 | 0.868       | 0.603           | 0.800  | 0.772     |


Validation (MA3, 40 docs, GPT-5.5 only):


| Condition     | Med Name F1 | Sz collapsed F1 | Dx Acc | BenchComp |
| ------------- | ----------- | --------------- | ------ | --------- |
| gpt_5_5:MA_v1 | 0.769       | 0.379           | 0.750  | 0.650     |


### Gan Frequency (synthetic subset)


| System                                       | Docs      | Prag F1   | Pur F1 | Exact | Status                    |
| -------------------------------------------- | --------- | --------- | ------ | ----- | ------------------------- |
| gpt_5_5 + Gan_cot_label (G2/G3 best)         | 50        | 0.800     | 0.760  | 0.540 | Superseded by G4-Fixed    |
| gpt_5_5 + Gan_retrieval_highlight (G4-Fixed) | 50        | **0.840** | 0.820  | 0.820 | Best; promoted to G4-Full |
| gpt_4_1_mini + Gan_direct_label              | 50        | 0.713     | 0.673  | 0.480 | Cost baseline             |
| qwen_35b_local + Gan_g3_qwen                 | 150       | 0.693     | 0.667  | —     | Local baseline            |
| [G4-Full, pending]                           | 1,500     | TBD       | TBD    | TBD   | Main frequency result     |
| Gan 2026 Qwen2.5-14B CoT(15000)              | real test | 0.847     | 0.788  | —     | Published target          |
| Gan 2026 MedGemma-4B CoT(15000)              | real test | 0.858     | 0.787  | —     | Published target          |


