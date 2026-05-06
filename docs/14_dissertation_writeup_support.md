# Dissertation Write-Up Support

Milestone 8 adds a reproducible bridge from run artifacts to chapter-ready
tables, traceability notes, and error-analysis seeds. The support command does
not call models and does not change scores; it formats existing evaluation,
robustness, and secondary-analysis outputs into dissertation-facing artifacts.

## Command

```bash
.venv/bin/python src/writeup_support.py build \
  --evaluation-dir runs/evaluation \
  --robustness-dir runs/robustness \
  --secondary-dir runs/secondary_analyses \
  --secondary-dir runs/secondary_analyses_model_compare \
  --output-dir runs/writeup_support
```

For a mechanical smoke check against existing stub outputs:

```bash
.venv/bin/python src/writeup_support.py build \
  --evaluation-dir runs/milestone_5_stub_eval_final_2 \
  --robustness-dir runs/robustness_smoke_venv \
  --secondary-dir runs/milestone_7_json_yaml_stub \
  --secondary-dir runs/milestone_7_model_compare_stub \
  --output-dir runs/milestone_8_writeup_smoke
```

## Outputs

- `writeup_manifest.json`: input run directories, artifact availability, and
  row counts.
- `dissertation_tables.md`: primary evaluation, robustness, and secondary
  analysis tables in Markdown.
- `evaluation_metric_plot.svg`: dependency-free visual summary of primary
  evaluation metrics.
- `methods_traceability.md`: artifact inventory, claim-support matrix,
  method-note checklist, and error-analysis seeds.
- `claim_support_matrix.csv`: compact mapping from bounded claims to the
  artifacts that support them.
- `error_analysis_examples.csv`: candidate document/system rows for qualitative
  error analysis.

## Interpretation Boundary

The generated Markdown is a reporting aid, not a new source of empirical
truth. Final dissertation values should be regenerated from final validation
artifacts, and smoke-test outputs should be treated only as mechanical checks.
