# Minimal Epilepsy Extraction Reproducibility Capsule

This is a trimmed reproduction repo for the two curated model-harness tracks
from the larger dissertation repository:

1. **Open/local:** Ollama `qwen3.5:4b` + guarded `h008_single_broad_field_llm`
2. **Closed/frontier:** OpenAI `gpt-5.5` + `h013_production_multi_agent_llm`

It intentionally excludes dashboards, historical negative experiments,
dissertation drafting files, and non-leading harnesses.

## Install

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
```

For the local run, install Ollama and pull the model:

```powershell
ollama pull qwen3.5:4b
```

For the frontier run, set `OPENAI_API_KEY`.

## Reproduce h008

```powershell
python scripts/run_h008_guarded.py --experiment-id repro_h008_qwen35_4b_n50
```

Expected headline from `expected_results/h008_qwen35_4b_guarded_n50_summary.json`:

- n=50, invalid-output rate `0.00`
- seizure-frequency pragmatic micro-F1 `0.32`
- current-medication support `1.00` across 73 extracted items
- investigation support `0.969` across 98 extracted items
- matched adjudication: current medications `42/44` value-correct; investigations `43/48` value-correct and `46/48` value-correct-or-partial

## Reproduce h013

```powershell
python scripts/run_h013_gpt55.py --experiment-id repro_h013_gpt55_n50
```

Expected headline from `expected_results/h013_gpt55_n50_summary.json`:

- n=50, invalid-output rate `0.00`
- seizure-frequency exact accuracy `0.34`
- monthly-rate tolerance accuracy `0.54`
- pragmatic micro-F1 `0.68`
- purist micro-F1 `0.64`
- proxy support checks: medications `1.00`, seizure types `1.00`, investigations `1.00`

Note: h013 GPT-5.5 is the strongest proxy-performing production-harness run in
this capsule, but its matched broader-field adjudication worksheet is included
as a handoff artifact and still needs scoring before it should be treated as a
fully adjudicated correctness result.

## Key Files

- `data/dataset_manifest.json`: dataset hash and canonical slice definition.
- `configs/*.yaml`: frozen model-harness settings.
- `prompts/`: human-readable prompt contracts; exact runtime prompts are in `src/`.
- `scripts/run_h008_guarded.py`: curated local h008 command.
- `scripts/run_h013_gpt55.py`: curated closed h013 command.
- `scripts/generate_adjudication_worksheet.py`: matched worksheet generator.
- `docs/adjudication/`: scoring/reference worksheets retained for reproducibility.
- `expected_results/`: frozen run records from the source repo.

## Smoke Tests

```powershell
python -m pytest -q
```
