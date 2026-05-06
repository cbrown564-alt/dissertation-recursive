# Pipeline Design

## Shared Preprocessing

All systems should use the same preprocessed input:

- Normalize whitespace.
- Preserve original source text.
- Split into sentence-like spans.
- Assign stable sentence IDs.
- Record character offsets when feasible.

The preprocessor should not remove clinically meaningful formatting such as headings, bullet lists, medication lists, or investigation sections.

## Direct Baselines

### S1: Direct JSON Extraction

The model reads the whole letter and emits canonical JSON directly.

Purpose: establish a simple structured baseline.

### S2: Direct JSON Extraction With Evidence

The model emits final fields plus exact evidence quotes.

Purpose: primary direct comparator for event-first extraction.

### S3: Direct YAML-To-JSON Extraction With Evidence

The model emits YAML, which is parsed and converted into canonical JSON.

Purpose: test whether model-facing YAML changes parseability or extraction quality.

## Event-First Pipeline

### E1: Event Extraction Only

The model extracts all relevant clinical events with temporality and evidence. No final patient-level fields are scored from this condition unless separately aggregated.

Purpose: measure event quality and support debugging.

### E2: Event Extraction Plus Deterministic Aggregation

Rules derive final fields from event objects.

Example aggregation rules:

- Select current medications from current medication events.
- Select previous medications from historical stopped medication events.
- Select current seizure frequency from current or most recent seizure-frequency events.
- Do not treat requested EEG/MRI as a completed result.
- Do not treat family-history events as patient-level facts.

Purpose: test whether event-first decomposition helps without adding another model call.

### E3: Event Extraction Plus Constrained Aggregation

A constrained model call derives final fields from the event list rather than from the full source letter.

Purpose: handle cases where deterministic rules are too brittle while keeping the aggregation evidence-bounded.

## Validation Layer

Every output should pass through the same validation stages:

1. Parse output.
2. Convert to canonical JSON if needed.
3. Validate against schema.
4. Check that evidence quotes appear in source text.
5. Normalize field values.
6. Score against gold labels.
7. Log repairs, cost, latency, token use, and model parameters.

## Repair Policy

Repairs should be limited and logged.

- Allow one parse repair attempt per output.
- Never repair by adding unsupported clinical values.
- Score both raw parse success and post-repair success.
- Keep repaired outputs traceable to the original model response.

## Aggregation Logging

Aggregators should log:

- selected event IDs,
- ignored event IDs,
- conflict decisions,
- missingness decisions,
- and any final field without event support.

This prevents the event-first pipeline from becoming opaque.
