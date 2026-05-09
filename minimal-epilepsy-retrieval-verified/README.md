# Minimal Epilepsy Retrieval + Verification Capsule

This directory is a reproducibility capsule extracted from the larger dissertation repo.
It keeps only the model setup, prompts, harness code, dataset slice, adjudication inputs,
and evaluation scripts needed to recreate the leading results for:

- `retrieval_field_extractors` with `gpt-5.5-2026-04-23`
- `clines_epilepsy_verified` with `gpt-5.5-2026-04-23`

The larger repo's dashboards, letter explorer, broad model sweeps, anchor experiments,
and historical baselines are intentionally excluded.

## Contents

```text
config/
  harnesses/                  # frozen manifests for the retained harnesses
  model_registry.yaml          # frozen model entries used by the canonical runs
data/
  synthetic_data_subset_1500.json
  selected_rows_n25.json       # fixed row ids used by the canonical n=25 slice
prompts/
  retrieval/field_extractor_v1.md
  clines_inspired/field_extractor_v1.md
  clines_inspired/verification_v1.md
schemas/
  final_extraction_v1.json
src/epilepsy_extraction/
  data, document, retrieval, modules, providers, schemas, evaluation
  harnesses/retrieval_field_extractors.py
  harnesses/clines_epilepsy_modular.py
  harnesses/clines_epilepsy_verified.py
scripts/
  run_harness.py
  build_adjudication_sheet.py
  auto_adjudicate.py
  summarize_results.py
results/
  runs/                        # canonical leading run records
  replay/                      # provider response streams for deterministic replay
  adjudication/                # completed adjudication CSVs used for scoring
  tables/                      # compact canonical accuracy/cost tables
```

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,openai]'
```

The package has no required runtime dependency for replay mode. Live OpenAI mode
requires `OPENAI_API_KEY`.

## Replay the Canonical Harnesses

Replay mode uses saved provider responses, so it is deterministic and does not call
external APIs.

```bash
python3 scripts/run_harness.py data/synthetic_data_subset_1500.json \
  --harness retrieval_field_extractors \
  --provider replay \
  --replay results/replay/matrix_gpt-5_5-2026-04-23_retrieval_field_extractors.replay.json \
  --run-id replay_gpt55_retrieval \
  --output results/runs/replay_gpt55_retrieval.json \
  --code-version replay

python3 scripts/run_harness.py data/synthetic_data_subset_1500.json \
  --harness clines_epilepsy_verified \
  --provider replay \
  --replay results/replay/matrix_gpt-5_5-2026-04-23_clines_epilepsy_verified.replay.json \
  --run-id replay_gpt55_verified \
  --output results/runs/replay_gpt55_verified.json \
  --code-version replay
```

## Run Live

```bash
export OPENAI_API_KEY=...

python3 scripts/run_harness.py data/synthetic_data_subset_1500.json \
  --harness retrieval_field_extractors \
  --provider openai \
  --model gpt-5.5-2026-04-23 \
  --run-id live_gpt55_retrieval \
  --output results/runs/live_gpt55_retrieval.json
```

Use `--harness clines_epilepsy_verified` for the verification harness. By default,
the runner uses `data/selected_rows_n25.json`.

## Regenerate Tables

```bash
python3 scripts/summarize_results.py \
  results/runs/matrix_gpt-5_5-2026-04-23_retrieval_field_extractors.json \
  results/runs/matrix_gpt-5_5-2026-04-23_clines_epilepsy_verified.json \
  --tables-dir results/tables \
  --model-registry config/model_registry.yaml \
  --adjudication results/adjudication/architecture_ladder_n25_real_provider_2026_05_08_adjudicated.csv \
  --adjudication results/adjudication/gpt55_verified_n25_2026_05_09_adjudicated.csv
```

`results/tables/headline_comparison.csv` is the compact table for cross-repo comparison:
field-family accuracy plus calls, tokens, cost, and latency.

## Canonical Result Summary

| System | SF | Med | Inv | SC | EC | Cost / letter | Latency / letter |
|---|---:|---:|---:|---:|---:|---:|---:|
| GPT-5.5 retrieval | 68% | 100% | 98% | 99% | 67% | $0.061 | 38.4s |
| GPT-5.5 verified | 46% | 100% | 98% | 99% | 84% | $0.100 | 74.1s |

Interpretation: retrieval is the best value/performance system, especially for
seizure frequency. Verification is retained because it helps on harder supported
classification problems, especially epilepsy classification.
