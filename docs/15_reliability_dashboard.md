# Reliability Dashboard

The dashboard turns existing run outputs into an interactive React app for
exploring extraction reliability across direct JSON and event-first systems.
It is designed as a downstream consumer of reproducible artifacts rather than
as a scoring source.

## Export Data

Generate the dashboard bundle from existing smoke artifacts:

```bash
.venv/bin/python src/dashboard_export.py build \
  --evaluation-dir runs/milestone_5_stub_eval_final_2 \
  --robustness-dir runs/robustness_smoke_venv \
  --direct-run-dir runs/milestone_3_stub \
  --event-run-dir runs/milestone_4_stub_check_venv_2 \
  --secondary-dir runs/milestone_7_json_yaml_stub \
  --secondary-dir runs/milestone_7_model_compare_stub \
  --output dashboard/public/data/dashboard_data.json
```

For final dissertation runs, replace those smoke directories with final
validation artifact directories. Missing values are preserved as `null` and
rendered as `n/a` or an explicit empty state.

## Run The App

```bash
cd dashboard
npm install
npm run dev -- --port 5173
```

Open `http://127.0.0.1:5173/`.

Production build check:

```bash
cd dashboard
npm run build
```

## Dashboard Data Contract

The app consumes `dashboard/public/data/dashboard_data.json` with these
top-level sections:

- `meta`: source directories, split, and generation time.
- `systems`: S2/E2/E3 labels and colors.
- `kpis`: summary-card values by system.
- `field_accuracy`: field-level metric rows for grouped bars.
- `schema_breakdown`: valid/minor/major slices for the donut.
- `robustness`: perturbation rows for degradation charts.
- `format_comparison`: JSON versus YAML-to-JSON metrics.
- `model_family`: bounded model-family comparison rows.
- `documents`: per-document review rows.
- `evidence_examples`: extracted evidence quote snippets when available.

## Design Reference

The implemented dashboard was built from
`docs/assets/reliability-dashboard-concept.png`. It keeps the concept's
compact research-product shell, deep teal rail, white analytical panels, and
S2/E2/E3 color system while reflecting the real values available in current
run artifacts.
