# Refactor Consolidation Plan

**Date:** 2026-05-12  
**Status:** Milestones A-F completed; maintained evidence-freeze work now follows  
**Purpose:** Convert the exploratory codebase into a maintainable dissertation and deployment codebase without losing the experimental record.

---

## 1. Why Refactor Now

The project has completed its main exploratory arc. The latest synthesis documents show that the core dissertation findings are now stable enough to support consolidation:

1. Corrected scoring and normalization are central methodological contributions.
2. Local direct extraction is viable for primary ExECTv2 fields.
3. `qwen3.6:35b` with `H6fs` plus the evidence resolver is the strongest local deployment candidate.
4. E3 and S2 remain the key frontier baselines.
5. Gan retrieval-highlight is the most promising seizure-frequency route.
6. Multi-agent designs are research leads, not yet a default maintained pipeline.
7. ExECT Explorer is becoming the practical audit surface for gold-standard and model disagreement review.

The codebase reflects the exploratory process: large phase scripts contain prompt design, provider calls, projection, scoring, reporting, and CLI orchestration in one place. That was appropriate during discovery, but it now makes future experiments harder to run safely and makes dissertation methods harder to audit.

---

## 2. Consolidation Principle

Preserve the experiment history; extract the reusable spine.

The refactor should not rewrite the research record or invalidate existing run artifacts. Instead, it should draw a clear boundary between:

- **Maintained pipeline code:** reusable, tested infrastructure for datasets, prompts, providers, projection, scoring, evidence resolution, run manifests, and selected active experiments.
- **Archived experiment code:** phase-specific scripts retained so historical results remain reproducible, but no longer treated as the place for new abstractions.

---

## 3. Canonical Pipeline Spine

Future maintained code should converge on this shape:

```text
dataset -> prompt contract -> model call -> parse/project -> corrected scoring
        -> evidence resolving -> manifest/report -> explorer/dashboard surface
```

The current highest-priority maintained path is:

```text
ExECTv2 letter
  -> H6fs local extraction
  -> canonical projection
  -> Option-C evidence resolver
  -> corrected ExECTv2 scorer
  -> auditable output for ExECT Explorer
```

This path is narrow enough to stabilize first and important enough to anchor the broader refactor.

---

## 4. Workstreams

### 4.1 Shared Core Layer

Create a small shared layer under `src/core/` for low-risk utilities and stable contracts.

Initial modules:
- `core.io`: text, JSON, and CSV helpers. **Completed.**
- `core.datasets`: split loading and dataset identifiers. **Completed.**

Next modules:
- `core.scoring`: reusable scoring API extracted from `src/evaluate.py`. **Completed.**
- `core.projection`: H6/H6fs/H6full projection helpers extracted from `src/model_expansion.py`. **Completed for promoted relaxed/canonical projection path.**
- `core.prompts`: named prompt-contract assembly. **Completed for H6/H6fs/H6full.**
- `core.manifests`: run metadata, freeze hashes, and condition identifiers. **Initial helper layer completed.**

### 4.2 Scoring Extraction

The corrected scorer is dissertation-critical and should become a stable API.

Target:
- Keep `src/evaluate.py` as a CLI wrapper. **Completed.**
- Move pure scoring logic to `core.scoring`. **Completed.**
- Add regression tests for:
  - gold-loader null-string fix. **Completed.**
  - ASM synonym expansion. **Completed.**
  - collapsed seizure labels. **Completed.**
  - medication component scoring. **Completed.**
  - frequency loose matching. **Completed.**

### 4.3 Projection and Prompt Contracts

The most fragile failures came from prompt/projection drift, especially the H7/D3 medication tuple collapse. Projection and prompt contracts should therefore be explicit and tested.

Target:
- Extract H6/H6fs/H6full prompt builders from `src/model_expansion.py`. **Completed.**
- Treat allowed seizure and epilepsy labels as shared constants. **Completed via `core.labels`.**
- Add contract-freeze tests for all promoted prompt families. **Completed for H6/H6fs/H6full; MA verifier/corrector prompt freeze remains.**
- Require structured medication objects where medication full-tuple scoring is expected. **Partially completed via projection tests for H6full medication tuple preservation.**

### 4.4 Maintained Local Deployment Candidate

Make the promoted local path first-class.

Target:
- One clean CLI for `H6fs + evidence resolver`. **Partially completed by standardizing `scripts/run_evidence_resolver_scored_batch.py` as the maintained scored runner.**
- One scored output directory shape. **Partially completed: scored runner writes `comparison_report.json`, `run_manifest.json`, and `resolved/*.json`.**
- One manifest describing model, harness, resolver mode, prompt hashes, scorer version, and run inputs. **Completed for the scored evidence-resolver runner.**
- Evidence resolver remains additive: it may only mutate evidence arrays. **Completed: recorded in the run manifest and covered by a direct mutation-policy regression test.**

### 4.5 Experiment Archive Boundary

After the maintained spine exists, move or mark old phase scripts as archival.

Candidates to preserve as phase artifacts:
- `src/model_expansion.py`
- `src/local_event_first.py`
- `src/multi_agent.py`
- `src/multi_agent_exploration.py`
- `src/recovery_experiments.py`
- older dashboard/export scripts

This should happen only after imports and tests prove current commands still run.

### 4.6 Explorer and Dashboard Decision

Clarify whether `dashboard/` and `exect-explorer/` are separate products or whether ExECT Explorer supersedes the earlier dashboard.

Likely direction:
- Keep `dashboard/` as the original aggregate-results prototype.
- Treat `exect-explorer/` as the active gold/model audit workbench.
- Add a documented data contract for model overlays and evidence-resolver outputs.

---

## 5. Proposed Milestones

### Milestone A: Orientation and Low-Risk Core

Status: completed.

- Add this consolidation plan. **Completed.**
- Add `src/core/` helpers. **Completed for IO, datasets, labels, scoring, prompts, projection, and manifests.**
- Replace duplicated IO/split helpers where safe. **Partially completed in `src/evaluate.py`; broader replacement remains intentionally incremental.**
- Refresh README current-state guidance. **Completed.**
- Run existing unit tests. **Completed: `python -m pytest -q tests`, 54 passed.**

### Milestone B: Scorer Stabilization

Status: completed.

- Extract scoring API. **Completed in `src/core/scoring.py`.**
- Keep `evaluate.py` CLI-compatible. **Completed; legacy imports are preserved.**
- Add scorer regression tests around known repaired failures. **Completed in `tests/test_core_scoring.py`.**
- Document scorer version and required metrics. **Partially completed via `SCORER_VERSION`; metric documentation still belongs in methods docs.**

### Milestone C: Local Candidate Pipeline

Status: partially completed.

- Extract H6fs projection and prompt contract. **Completed via `core.prompts` and `core.projection`.**
- Add a maintained local candidate runner. **Partially completed by standardizing the existing scored batch runner.**
- Integrate evidence resolver behind a stable option. **Completed in existing runner with deterministic-only default and optional fallback.**
- Emit a standardized run manifest. **Completed in `scripts/run_evidence_resolver_scored_batch.py`.**

### Milestone D: Prompt Contract Freeze

Status: partially completed.

- Add contract tests for H6/H6fs/H6full, evidence resolver fallback, and MA verifier/corrector prompts. **Completed.**
- Add token-budget exhaustion alarms for reasoning-model calls. **Completed in provider response metadata.**
- Add medication tuple preservation tests. **Completed for H6full projection.**

### Milestone E: Explorer Data Contract

Status: completed.

- Define the JSON shape for ExECT Explorer model overlays. **Completed via `schemas/exect_explorer_model_overlay.schema.json`.**
- Export one small, representative model-vs-gold bundle. **Completed at `exect-explorer/public/data/model_overlays/h6fs_ev_validation_sample.json`.**
- Keep annotation-mode local-storage behavior separate from canonical model artifacts. **Completed in `docs/55_exect_explorer_data_contract.md` and regression tests.**

### Milestone F: Archive or Rename Legacy Entrypoints

Status: completed.

- Mark frozen experiment scripts as archival. **Completed with in-place archival markers.**
- Update docs and README to point new work at maintained commands. **Completed via `docs/56_archival_entrypoints.md` and README routing.**
- Preserve historical run reproducibility. **Completed by leaving historical files and commands in place.**

---

## 6. Immediate Next Step

Milestones A through F are now complete for the maintained local candidate and Explorer data-contract path. New implementation work should add shared behavior under `src/core/`, run H6fs + evidence-resolver experiments through `scripts/run_evidence_resolver_scored_batch.py`, and use ExECT Explorer model overlays for audit-facing artifacts.

---

## 7. Completed Implementation Log

Completed on 2026-05-12:

- Added the maintained shared modules:
  - `src/core/scoring.py`
  - `src/core/prompts.py`
  - `src/core/projection.py`
  - `src/core/manifests.py`
- Kept compatibility wrappers/import surfaces:
  - `src/evaluate.py` now delegates scoring logic to `core.scoring`.
  - `src/model_expansion.py` delegates promoted H6/H6fs/H6full prompts and canonical projection to `core.prompts` / `core.projection`.
- Added standardized manifest emission to `scripts/run_evidence_resolver_scored_batch.py`.
- Updated `README.md` to identify `src/core/` as the maintained shared layer.
- Added regression tests:
  - `tests/test_core_scoring.py`
  - `tests/test_core_prompts_projection.py`
  - expanded `tests/test_core_helpers.py`
- Verification completed:
  - `python -m pytest -q tests` -> 54 passed.
  - `python -m compileall -q src scripts` -> passed.
  - `python scripts/run_evidence_resolver_scored_batch.py --help` -> passed.

Completed on 2026-05-12:

- Made the maintained H6fs evidence-resolver runner first-class:
  - documented the canonical invocation and output contract in `README.md`;
  - added `validate_scored_output_shape()` to `scripts/run_evidence_resolver_scored_batch.py`;
  - added a representative scored-runner output-shape regression test.
- Added direct resolver mutation-policy coverage proving non-evidence content is unchanged.
- Added prompt-contract coverage for:
  - `prompts/recovery/evidence_resolver_fallback.md`;
  - `prompts/multi_agent_v2/verifier.md`;
  - `prompts/multi_agent_v2/corrector.md`.
- Added provider-level token-budget exhaustion alarms in `src/model_providers.py`.
- Verification completed:
  - `python -m pytest -q tests` -> 60 passed.
  - `python -m compileall -q src scripts` -> passed.
  - `python scripts/run_evidence_resolver_scored_batch.py --help` -> passed.

Completed on 2026-05-12:

- Added the ExECT Explorer model-overlay data contract:
  - `schemas/exect_explorer_model_overlay.schema.json`
  - `docs/55_exect_explorer_data_contract.md`
- Added `exect-explorer/scripts/build_model_overlay.py` to export canonical model outputs into Explorer-ready overlay bundles.
- Exported a representative H6fs + evidence-resolver sample:
  - `exect-explorer/public/data/model_overlays/h6fs_ev_validation_sample.json`
- Added regression tests:
  - `tests/test_exect_explorer_model_overlay.py`
- Verification completed:
  - `python -m pytest -q tests` -> 62 passed.
  - `python -m compileall -q src scripts exect-explorer/scripts` -> passed.
  - `python exect-explorer/scripts/build_model_overlay.py --help` -> passed.

Completed on 2026-05-12:

- Completed Milestone F by marking frozen exploratory entrypoints as archival without moving or deleting them:
  - `src/model_expansion.py`
  - `src/local_event_first.py`
  - `src/multi_agent.py`
  - `src/multi_agent_exploration.py`
  - `src/recovery_experiments.py`
  - `src/dashboard_export.py`
  - evidence-resolver pilot scripts under `scripts/`
- Added the maintained routing guide:
  - `docs/56_archival_entrypoints.md`
- Updated `README.md` to point new work at maintained commands and distinguish archived historical commands from active surfaces.
