# Secondary Analyses

Milestone 7 keeps secondary results bounded around the primary event-first
reliability question. The first executable comparison is a controlled direct
format analysis: `S2` direct JSON with evidence versus `S3` YAML model output
converted into canonical JSON for the same documents.

## JSON Versus YAML-To-JSON

This analysis assumes direct-baseline artifacts already exist for both `S2`
and `S3` under the same run directory. It does not call a model; it scores the
matched canonical outputs and reads `baseline_runs.jsonl` for parse and repair
metadata.

```bash
.venv/bin/python src/secondary_analyses.py json-yaml \
  --split validation \
  --systems S2 S3 \
  --direct-run-dir runs/direct_baselines \
  --output-dir runs/secondary_analyses
```

For a mechanical smoke check against the Milestone 3 stub outputs:

```bash
.venv/bin/python src/secondary_analyses.py json-yaml \
  --split development \
  --limit 2 \
  --direct-run-dir runs/milestone_3_stub \
  --output-dir runs/milestone_7_json_yaml_stub
```

## Outputs

- `json_yaml_summary.json`: parseability, validation, scoring, and S3-minus-S2
  deltas.
- `json_yaml_document_scores.json`: per-document score layers for S2 and S3.
- `json_yaml_comparison_table.csv`: compact reporting table with parseability,
  schema validity, evidence, field accuracy, cost, and latency columns.

## Interpretation Boundary

The comparison treats JSON and YAML-to-JSON as prompt/output-format conditions
inside the direct baseline, not as a replacement for the primary S2 versus
E2/E3 event-first analysis. Missing artifacts are counted as unavailable so
format comparisons cannot silently drop difficult documents.
