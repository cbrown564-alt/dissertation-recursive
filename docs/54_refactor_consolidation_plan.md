# Refactor Consolidation Plan

**Date:** 2026-05-12  
**Status:** Initial consolidation plan  
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
- `core.io`: text, JSON, and CSV helpers.
- `core.datasets`: split loading and dataset identifiers.

Next modules:
- `core.scoring`: reusable scoring API extracted from `src/evaluate.py`.
- `core.projection`: H6/H6fs/H6full projection helpers extracted from `src/model_expansion.py`.
- `core.prompts`: named prompt-contract assembly.
- `core.manifests`: run metadata, freeze hashes, and condition identifiers.

### 4.2 Scoring Extraction

The corrected scorer is dissertation-critical and should become a stable API.

Target:
- Keep `src/evaluate.py` as a CLI wrapper.
- Move pure scoring logic to `core.scoring`.
- Add regression tests for:
  - gold-loader null-string fix
  - ASM synonym expansion
  - collapsed seizure labels
  - medication component scoring
  - frequency loose matching

### 4.3 Projection and Prompt Contracts

The most fragile failures came from prompt/projection drift, especially the H7/D3 medication tuple collapse. Projection and prompt contracts should therefore be explicit and tested.

Target:
- Extract H6/H6fs/H6full prompt builders from `src/model_expansion.py`.
- Treat allowed seizure and epilepsy labels as shared constants.
- Add contract-freeze tests for all promoted prompt families.
- Require structured medication objects where medication full-tuple scoring is expected.

### 4.4 Maintained Local Deployment Candidate

Make the promoted local path first-class.

Target:
- One clean CLI for `H6fs + evidence resolver`.
- One scored output directory shape.
- One manifest describing model, harness, resolver mode, prompt hashes, scorer version, and run inputs.
- Evidence resolver remains additive: it may only mutate evidence arrays.

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

Status: started.

- Add this consolidation plan.
- Add `src/core/` helpers.
- Replace duplicated IO/split helpers where safe.
- Refresh README current-state guidance.
- Run existing unit tests.

### Milestone B: Scorer Stabilization

- Extract scoring API.
- Keep `evaluate.py` CLI-compatible.
- Add scorer regression tests around known repaired failures.
- Document scorer version and required metrics.

### Milestone C: Local Candidate Pipeline

- Extract H6fs projection and prompt contract.
- Add a maintained local candidate runner.
- Integrate evidence resolver behind a stable option.
- Emit a standardized run manifest.

### Milestone D: Prompt Contract Freeze

- Add contract tests for H6/H6fs/H6full, evidence resolver fallback, and MA verifier/corrector prompts.
- Add token-budget exhaustion alarms for reasoning-model calls.
- Add medication tuple preservation tests.

### Milestone E: Explorer Data Contract

- Define the JSON shape for ExECT Explorer model overlays.
- Export one small, representative model-vs-gold bundle.
- Keep annotation-mode local-storage behavior separate from canonical model artifacts.

### Milestone F: Archive or Rename Legacy Entrypoints

- Mark frozen experiment scripts as archival.
- Update docs and README to point new work at maintained commands.
- Preserve historical run reproducibility.

---

## 6. Immediate Next Step

Complete Milestone A, then begin Milestone B by extracting scorer functions from `src/evaluate.py` without changing metric behavior.

