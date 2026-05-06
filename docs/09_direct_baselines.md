# Direct Baselines

Milestone 3 adds an executable harness for the three direct extraction
baselines described in `docs/03_pipeline_design.md`.

## Baselines

- `S1`: direct canonical JSON extraction without evidence. Present fields may
  omit evidence; quote presence is scored separately.
- `S2`: direct canonical JSON extraction with evidence quotes and event IDs.
- `S3`: YAML model output parsed into canonical JSON for scoring. JSON remains
  the only canonical scoring format.

## Dependencies

Install the project runtime dependencies in a local virtual environment before
running validation:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

`jsonschema` validates the structural contract in
`schemas/canonical_extraction.schema.json`. Custom Python checks still handle
project-specific constraints such as duplicate event IDs, evidence quote
presence, and quote validity.

## Prepare Prompts

```bash
.venv/bin/python src/direct_baselines.py prepare --limit 2 --output-dir runs/milestone_3_prompts
```

This writes one prompt per baseline/document without calling a model.

## Stub Exit Check

```bash
.venv/bin/python src/direct_baselines.py run \
  --provider stub \
  --limit 2 \
  --output-dir runs/milestone_3_stub
```

The stub provider emits valid empty canonical outputs. It is not a clinical
baseline result; it exists to verify parse, YAML-to-JSON conversion,
validation, evidence-layer scoring, and JSONL logging on a small development
subset without requiring an API key.

## Model Run

```bash
OPENAI_API_KEY=... .venv/bin/python src/direct_baselines.py run \
  --provider openai \
  --model gpt-4.1-mini \
  --limit 2 \
  --output-dir runs/milestone_3_openai
```

Each run writes:

- prompt text,
- raw model output,
- parsed canonical JSON when parsing succeeds,
- `baseline_runs.jsonl` with parse, repair, schema, evidence, latency, and
  model metadata.

## Repair Policy

The harness allows one syntax-level repair attempt:

- JSON: remove Markdown wrappers/preambles and trailing commas.
- YAML: remove Markdown wrappers and replace tabs with spaces.

Repairs never add clinical values or evidence. Raw and parsed outputs remain
separate for traceability.
