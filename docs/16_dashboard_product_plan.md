# Reliability Dashboard Product Plan

This document describes the intended full dashboard product, the current
prototype stage, and the work required to turn it into a genuinely useful
analysis surface for dissertation results.

## Product Idea

The Reliability Dashboard should be the interactive companion to the
dissertation evaluation pipeline. Its job is not to rescore outputs or replace
the reproducible command-line artifacts. Its job is to make the artifacts easy
to inspect, compare, explain, and trust.

The dashboard should answer four researcher questions quickly:

1. Which extraction path is more reliable: direct JSON, deterministic
   event-first aggregation, or constrained event-first aggregation?
2. Where does reliability improve or fail by clinical field, evidence support,
   temporality, schema validity, parseability, and robustness perturbation?
3. Which documents and evidence spans explain the aggregate numbers?
4. Which claims are supported by final validation artifacts versus smoke-test,
   missing, or incomplete artifacts?

The intended audience is primarily the dissertation author and reviewers of the
methods/results pipeline. A secondary audience is anyone reproducing the
evaluation later and needing a faster way to audit run outputs.

## Current Stage

Current stage: **prototype / proof of dashboard contract**.

Implemented pieces:

- `src/dashboard_export.py` converts existing run artifacts into a single
  dashboard bundle at `dashboard/public/data/dashboard_data.json`.
- `dashboard/` contains a React/Vite app that reads the bundle and renders a
  first-pass reliability dashboard.
- The current screen includes KPI cards, field accuracy bars, an evidence
  panel, schema donut, robustness panel, JSON-vs-YAML comparison, model-family
  matrix, and document review table.
- S2/E2/E3 selected-system state works for visible dashboard panels such as
  the schema donut and latency cue.
- The app uses the real smoke-run data currently available. Missing values are
  rendered as `n/a` or explicit empty states rather than invented numbers.

Prototype limitations:

- The sidebar is mostly visual shell. Buttons do not yet route to real
  sections, pages, filtered views, or persistent tabs.
- Top controls are not fully functional. Search, current run, and letter
  filters are visual affordances rather than working data filters.
- Charts are code-native SVG sketches, but they lack rich context: tooltips,
  denominators, confidence intervals, linked document counts, and explanatory
  metric definitions.
- The evidence panel is shallow because current smoke artifacts do not contain
  enough evidence quotes. It needs final artifacts and better quote ranking.
- Robustness degradation cannot show meaningful deltas when clean matched
  baselines are missing. The current empty state is honest but not yet useful.
- The document table is a starter audit surface, not a full error-analysis
  workflow.
- The dashboard data bundle is now versioned against
  `schemas/dashboard_data.schema.json`, includes exporter metadata, artifact
  metadata, and missingness reasons, and can be validated with
  `src/dashboard_export.py validate`.
- The visual design is cleaner than a raw table, but still needs polish around
  density, chart readability, responsive behavior, and interaction feedback.

## Intended Information Architecture

The full dashboard should become a small analysis app with these areas.

### Overview

Purpose: fast summary of the final matched evaluation.

Expected panels:

- KPI cards for field accuracy, temporal correctness, evidence validity,
  schema validity, parse/repair, latency/cost, and robustness degradation.
- System comparison for S2, E2, and E3.
- Clear split/run metadata, including artifact directory, generation time,
  model/provider, document count, and whether the run is smoke or final.
- Warnings when data is incomplete, missing, smoke-only, or not matched across
  systems.

### Fields

Purpose: understand which clinical fields drive success or failure.

Expected panels:

- Field-level comparison across medication, seizure type, seizure frequency,
  EEG, MRI, and diagnosis.
- Precision/recall/F1 where set matching is used.
- Accuracy where exact current-field correctness is used.
- Per-field denominators and missingness counts.
- Drill-down from a field to the documents behind false positives, false
  negatives, and unsupported predictions.

### Evidence

Purpose: audit whether extracted claims are actually grounded in source text.

Expected panels:

- Ranked evidence quotes by system, field, document, and support status.
- Quote-validity, semantic-support, temporal-support, and field-correctness
  layers shown separately.
- Source quote, predicted field value, gold span overlap, and character offsets.
- Filters for unsupported evidence, missing evidence, invalid quote, and
  temporal mismatch.
- Link from aggregate evidence metrics to concrete examples.

### Robustness

Purpose: inspect performance under label-preserving and label-changing
perturbations.

Expected panels:

- Degradation by perturbation type and system.
- Clean versus perturbed metric values side by side.
- Separate view for label-changing validity checks.
- Perturbation manifest with descriptions and source document IDs.
- Gan 2026 seizure-frequency stress-test results separated from ExECTv2-derived
  perturbations.

### Documents

Purpose: document-level audit and error analysis.

Expected panels:

- Searchable document list by split, system, availability, schema validity, and
  error type.
- Side-by-side S2/E2/E3 canonical outputs for a selected document.
- Gold labels and evidence spans where available.
- Event-first trace: E1 events, E2 aggregation log, E3 constrained output, and
  links back to evidence event IDs.
- Error tags suitable for dissertation qualitative analysis.

### Artifacts

Purpose: trace dashboard values back to reproducible files.

Expected panels:

- Artifact manifest with paths, existence, size, row counts, split, systems,
  and generation times.
- Links to evaluation summary, document scores, robustness summary, secondary
  analysis summaries, canonical outputs, event logs, and prompts.
- Claim-support matrix showing which dashboard claims are supported by which
  artifacts.

### Settings / Data

Purpose: make the dashboard reusable across final runs.

Expected controls:

- Select run bundle.
- Select split.
- Select systems.
- Toggle smoke/final artifacts.
- Export current filtered table as CSV/JSON.
- Show dashboard data schema version.

## Required Development Work

### 1. Stabilize The Dashboard Data Contract

Priority: high.

Status: complete for the first stable dashboard contract.

Work:

- Define a JSON Schema for `dashboard_data.json`. Completed in
  `schemas/dashboard_data.schema.json`.
- Add a validation command for generated dashboard bundles. Completed via
  `src/dashboard_export.py validate`.
- Convert current ad hoc fields into stable typed sections. Completed for the
  current dashboard sections while preserving backwards-compatible frontend
  fields.
- Preserve `null` for missing values, but attach explicit missingness reasons:
  missing artifact, unavailable metric, smoke artifact, no clean baseline,
  unsupported analysis, or not applicable. Completed for KPI, field,
  robustness, artifact, and unsupported-analysis gaps.
- Add a schema version and exporter version to `meta`. Completed.
- Add tests that run the exporter against smoke artifacts. Covered by the
  final-run smoke orchestration and explicit schema validation command; a
  dedicated unit test can still be added if the repo grows a test suite.

Why it matters:

The dashboard should remain a downstream consumer. A stable contract prevents
the frontend from becoming coupled to incidental run-folder shapes.

### 2. Make Navigation Real

Priority: high.

Work:

- Replace decorative sidebar buttons with real route or section state.
- Add views for Overview, Fields, Evidence, Robustness, Documents, Artifacts,
  and Settings/Data.
- Make the active sidebar state reflect the current view.
- Add URL hash or client routing so specific views can be shared.

Why it matters:

The current sidebar implies a product that does not exist yet. Real navigation
will make the app feel honest and useful.

### 3. Make Header Controls Functional

Priority: high.

Work:

- Make document search filter evidence rows and document tables.
- Add split/run selectors based on available dashboard bundle metadata.
- Make "All letters" filter by availability, schema validity, error status, or
  field.
- Add a visible reset-control state.
- Show result counts after filters are applied.

Why it matters:

The dashboard needs to support exploration, not just display static charts.

### 4. Improve Chart Semantics

Priority: high.

Work:

- Add tooltips or detail panels for every chart mark.
- Show denominator counts beside percentages.
- Separate precision, recall, and F1 where appropriate.
- Use clearer metric names for fields whose scoring type differs.
- Add uncertainty or bootstrap confidence intervals if the evaluation protocol
  later supports them.
- Add axis labels and legends that explain what is being plotted.
- Make empty states actionable: name the missing artifact or command needed.

Why it matters:

The current visualizations are readable but thin. Dissertation reviewers will
need to understand what each number means and why it is legitimate.

### 5. Build Evidence Drill-Down

Priority: high.

Work:

- Export evidence examples from canonical outputs and document scores with
  support status, field, quote, offsets, prediction, gold span, and metric
  layer.
- Rank examples by usefulness: invalid quote, unsupported quote, temporal
  mismatch, field incorrect, then representative correct examples.
- Add a source-text viewer with highlighted quote and gold span.
- Support filtering by field, system, support status, and document.

Why it matters:

Evidence grounding is central to the dissertation. The dashboard should make
the evidence thread inspectable, not just summarize quote validity.

### 6. Build Document-Level Audit Workflow

Priority: medium-high.

Work:

- Create a document detail view.
- Show S2, E2, and E3 predictions side by side.
- Show gold labels and field-level scoring results.
- Show E1 events and E2/E3 aggregation trace for event-first outputs.
- Add error categorization fields that can feed dissertation error analysis.
- Add copy/export affordances for selected examples.

Why it matters:

Aggregate metrics explain the headline; document-level audit explains the
mechanism.

### 7. Make Robustness Useful

Priority: medium-high.

Work:

- Ensure final robustness outputs include matched clean baselines for every
  perturbation row.
- Export clean score, perturbed score, delta, perturbation label effect, source
  dataset, and description.
- Separate label-preserving degradation from label-changing validity.
- Add field-specific robustness views, not only composite views.
- Add perturbation examples showing the changed text.

Why it matters:

The robustness panel is one of the strongest dissertation-facing ideas, but it
needs complete matched artifacts to avoid becoming a decorative line chart.

### 8. Polish Visual Design

Priority: medium.

Work:

- Reduce cramped KPI behavior on medium desktop widths.
- Improve chart label legibility and truncation.
- Add hover/focus states consistently.
- Add professional empty states and loading states for each panel.
- Improve mobile and tablet behavior.
- Avoid panels that visually promise unavailable details.
- Add subtle view transitions only where they clarify state changes.

Why it matters:

The current screen is a good first pass, but a dashboard earns trust through
small interaction and typography decisions.

### 9. Add Export And Reproducibility Features

Priority: medium.

Work:

- Export current filtered table to CSV.
- Export selected evidence examples to Markdown.
- Export dashboard snapshot metadata for dissertation appendices.
- Add a "copy command used to generate this bundle" affordance.
- Add artifact links where local paths are meaningful.

Why it matters:

The dashboard should accelerate writing and auditing, not trap insight inside
the UI.

### 10. Add Test Coverage

Priority: medium.

Work:

- Add exporter unit tests over smoke fixture artifacts.
- Add frontend component tests for formatting and missing values.
- Add Playwright or browser smoke tests for initial render, navigation, filters,
  and selected-system behavior.
- Add visual regression screenshots once the design stabilizes.

Why it matters:

The dashboard is a reporting surface. Regressions can mislead analysis even
when the backend scorer is correct.

## Optional Enhancements

These are not required for dissertation viability but would make the dashboard
feel much richer.

- Run comparison mode: compare two generated dashboard bundles, such as smoke
  versus final or model A versus model B.
- Claim builder: select a metric and generate a draft dissertation sentence
  with the exact artifact provenance attached.
- Field lineage graph: show source letter -> E1 events -> E2/E3 aggregation ->
  canonical field -> score layer.
- Review annotations: locally tag examples as "good limitation", "chapter
  example", "needs manual adjudication", or "ignore".
- Static export mode: build a read-only HTML report from a dashboard bundle for
  sharing without a dev server.
- Confidence/uncertainty layer: add bootstrap intervals once there are enough
  final validation documents.

## Suggested Implementation Order

1. Stabilize and validate `dashboard_data.json`.
2. Replace sidebar shell with real views.
3. Make search and filters functional.
4. Build the evidence drill-down.
5. Build the document detail view.
6. Complete robustness delta support from final matched artifacts.
7. Polish chart semantics, empty states, and responsive layout.
8. Add export features.
9. Add tests and visual regression checks.

## Near-Term Acceptance Criteria

The dashboard should not be considered beyond prototype until all of these are
true:

- Sidebar navigation changes the visible view.
- Header controls filter real data.
- Every chart has denominators and metric definitions.
- Evidence examples link to source quote, field, document, and support status.
- Robustness degradation uses matched clean and perturbed scores.
- Missing data states explain exactly which artifact or command is needed.
- A final validation bundle can be exported and loaded without code changes.

## Current Product Summary

The dashboard is currently a promising shell over a real export contract. Its
best contribution so far is proving that the existing run outputs can be
converted into a downstream-consumable bundle and rendered as a coherent
S2/E2/E3 reliability view. The next stage is to turn the shell into an
analysis workflow: navigable, filterable, evidence-linked, and explicit about
what each number can and cannot support.
