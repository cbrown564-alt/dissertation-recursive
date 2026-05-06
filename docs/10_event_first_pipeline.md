# Event-First Pipeline

Milestone 4 adds an executable event-first path for the same development subset
used by the direct baselines.

## Pipelines

- `E1`: event extraction only. The model emits evidence-grounded events for
  medication, seizure frequency, seizure type, EEG/MRI investigation, and
  diagnosis claims.
- `E2`: deterministic aggregation. Valid E1 events are converted into
  canonical JSON fields using conservative rules from
  `docs/03_pipeline_design.md`.
- `E3`: constrained aggregation. A second model call receives only the event
  list and canonical schema, then emits canonical JSON. The stub provider
  falls back to E2 so the harness can be checked without an API key.

## Stub Exit Check

```bash
.venv/bin/python src/event_first.py run \
  --provider stub \
  --pipelines E1 E2 E3 \
  --limit 2 \
  --output-dir runs/milestone_4_stub
```

The stub provider emits a valid empty event list and valid canonical output.
It is not a clinical result; it checks event parsing, event evidence
validation, deterministic aggregation, constrained aggregation plumbing,
canonical validation, quote validity, and JSONL logging.

## Model Run

```bash
OPENAI_API_KEY=... .venv/bin/python src/event_first.py run \
  --provider openai \
  --model gpt-4.1-mini \
  --pipelines E1 E2 \
  --limit 2 \
  --output-dir runs/milestone_4_openai
```

Each run writes:

- E1 prompt text and raw event output,
- parsed event JSON,
- E2 and/or E3 canonical JSON when requested,
- aggregation decision logs,
- `event_first_runs.jsonl` with parse, schema, quote, aggregation, latency,
  provider, and model metadata.

## Aggregation Logging

The deterministic aggregator records selected event IDs, ignored event IDs,
conflict decisions, missingness decisions, final fields without event support,
non-current medication extension events, and non-result investigation status
events.
