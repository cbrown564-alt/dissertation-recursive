# Frequency Review Workbench Plan

**Date:** 2026-05-08  
**Seed artifact:** `runs/frequency_workstream/stage_f1/e3_validation_frequency_review.html`  
**Purpose:** Scale the one-off E3 seizure-frequency review page into a reusable visual
evaluation tool for comparing variants, harnesses, datasets, fields, and error modes.

---

## Product Idea

The Frequency Review Workbench should start as a researcher-facing inspection surface for
seizure-frequency extraction, then become a broader Key Metrics Review Workbench for the
main ExECTv2 dissertation fields. Its job is not to replace the command-line scorer. Its job is
to make the scorer's outputs inspectable enough that metric changes are explainable at the
field, document, and variant level.

The current E3 frequency review page already has the right ingredients for the first field
adapter:

- full letter text;
- gold frequency spans and normalized gold candidates;
- model prediction and parsed representation;
- evidence quotes and offsets;
- pass/miss badge;
- short diagnosis of what went wrong.

The workbench should generalize that page across:

- **datasets:** ExECTv2 and Gan 2026;
- **systems:** S2, E2, E3, S4/S5 recovery prompts, and future Gan-specific harnesses;
- **models:** GPT-4.1-mini, GPT-5.5, Claude Sonnet, local models;
- **harnesses:** canonical H0, Gan direct label, Gan evidence label, Gan two-pass, hard-case few-shot;
- **metrics:** ExECTv2 medication F1, seizure-type F1, diagnosis accuracy, EEG/MRI accuracy,
  seizure-frequency per-letter accuracy, seizure-frequency loose accuracy, Gan Pragmatic
  micro-F1, Gan Purist micro-F1, exact normalized-label match, evidence validity.

Frequency remains the first vertical slice because it is the hardest field to inspect and has
the richest normalization/error taxonomy. The durable target is not a frequency-only page; it
is a field-adapter architecture where frequency, medications, seizure type, diagnosis,
investigations, and Gan labels all render through one shared review shell.

---

## Core Questions

The tool should answer these questions quickly:

1. Which variant is winning, and is the difference visible in the actual letters?
2. Is a miss caused by evidence selection, normalization, temporality, gold-label mismatch, or task definition?
3. Does a model find the right text but produce the wrong label?
4. Does a Gan-optimized prompt transfer back to ExECTv2?
5. Which specific examples should be quoted in the dissertation as representative error modes?
6. Which field is responsible for a document-level regression or aggregate metric change?
7. Are improvements concentrated in one metric while another clinically important field degrades?
8. Do quote-validity or temporality failures explain otherwise surprising field scores?

---

## Users and Workflow

Primary user: dissertation author during model/prompt development.

Secondary users: supervisors/reviewers who need to audit whether reported frequency metrics are
credible.

Typical workflow:

1. Run a model/harness condition.
2. Score it with `src/evaluate.py` for ExECTv2 or `src/gan_frequency.py` for Gan.
3. Generate a workbench bundle.
4. Open the HTML/React view and filter to misses by field, document, evidence validity, or variant delta.
5. Tag failure modes and adjudication notes.
6. Export a comparison table and curated examples for writeup.

---

## MVP Scope

The MVP should remain lightweight: generate static HTML from run artifacts, similar to the
current E3 review page. A static artifact is easy to archive with a run and does not require
dashboard app state to be stable first.

### MVP Inputs

For ExECTv2:

- `runs/<condition>/document_scores.json`
- canonical outputs such as `canonical.json`, `e2_canonical.json`, `e3_canonical.json`
- source letters in `data/ExECT 2 (2025)/Gold1-200_corrected_spelling`
- gold annotations from the ExECTv2 markup CSVs, including prescriptions, seizure frequency,
  seizure type, diagnosis, and investigations
- optional E1 event logs and E3 aggregation logs

For Gan:

- `data/Gan (2026)/synthetic_data_subset_1500.json`
- `runs/gan_frequency/<condition>/predictions.json`
- `runs/gan_frequency/<condition>/gan_frequency_predictions_scored.csv`
- optional model response logs containing evidence quotes or analysis

### MVP Outputs

Each generated review should write:

- `review.html`: interactive static review page;
- `review_data.json`: normalized data backing the page;
- `error_tags.csv`: editable/exportable table of document-level error modes;
- `summary.json`: metric rollup, denominator notes, and artifact provenance.

### MVP Views

1. **Overview**
   - condition name, dataset, split, model, harness;
   - primary and secondary metrics;
   - field-level metric tiles for medication, seizure type, diagnosis, EEG, MRI, and frequency;
   - document count and availability;
   - class distribution for Gan or annotation-count distribution for ExECTv2.

2. **Case List**
   - sortable table of documents;
   - document-level status and per-field status chips;
   - gold label/category and predicted label/category for the selected field;
   - failure diagnosis for the selected field;
   - quick links to full case.

3. **Case Detail**
   - full letter text;
   - highlighted gold spans and prediction evidence spans for the active field;
   - field tabs for frequency, medications, seizure types, diagnosis, EEG, and MRI;
   - gold normalized candidates or label sets;
   - prediction, parsed prediction, category mappings, and set-level true/false positives;
   - model evidence quote and quote-validity status;
   - raw model output link/expandable JSON;
   - suggested failure mode.

4. **Error Mode Summary**
   - counts by failure mode;
   - counts by field and failure mode;
   - examples per mode;
   - exportable shortlist for dissertation writeup.

5. **Field Matrix**
   - one row per document;
   - one compact status cell per key field;
   - sort by number of failed fields, quote validity, temporal accuracy, or selected metric;
   - click any field cell to open that field's detail panel for the document.

6. **Evidence Audit**
   - quote presence and quote validity by field;
   - supported versus unsupported extraction counts;
   - cases where the label is correct but evidence is missing/invalid;
   - cases where evidence overlaps gold but normalization is wrong.

---

## Comparison Mode

The workbench becomes much more useful when it can compare two or more variants on the same
documents. In the all-key-metrics version, comparison happens at two levels:

- **document level:** did the overall document get better or worse?
- **field level:** which specific field fixed, regressed, or remained wrong?

### Variant Comparison Layout

For each document:

| Column | Content |
|---|---|
| Field | frequency, medication, seizure type, diagnosis, EEG, MRI, or Gan label |
| Gold | normalized label/category or gold label set, with evidence span |
| Variant A | prediction/category or predicted label set, evidence, pass/miss |
| Variant B | prediction/category or predicted label set, evidence, pass/miss |
| Delta | fixed / regressed / both miss / both correct / partial set change |

### Comparison Filters

- fixed by variant B;
- regressed by variant B;
- both miss with same predicted category;
- both miss with different predicted category;
- right evidence, wrong normalization;
- wrong evidence, plausible normalization;
- `UNK` versus `NS` confusion;
- frequent versus infrequent threshold confusion;
- cluster parsing errors;
- seizure-free interval errors.
- medication added by variant B;
- medication dropped by variant B;
- dose/frequency component fixed or regressed;
- seizure-type label fixed/regressed;
- diagnosis collapsed-label fixed/regressed;
- EEG/MRI status fixed/regressed;
- quote validity fixed/regressed.

### Outputs

- `variant_comparison.html`
- `variant_comparison.csv`
- `fixed_cases.csv`
- `regressions.csv`
- `field_delta_matrix.csv`
- `field_fixed_cases.csv`
- `field_regressions.csv`

---

## Field Adapter Architecture

To make the workbench genuinely useful beyond seizure frequency, the static generator should
be organized around field adapters rather than one-off render logic.

Each adapter should provide:

| Adapter method | Responsibility |
|---|---|
| `field_id` | stable identifier such as `current_seizure_frequency` or `medication_full` |
| `display_name` | human-readable label for UI and exports |
| `metric_kind` | scalar accuracy, set F1, category F1, evidence rate, or custom |
| `gold(case_context)` | normalized gold labels, categories, spans, and raw source values |
| `prediction(case_context, variant)` | normalized prediction labels, categories, spans, raw output path |
| `score(document_score)` | field-level score extracted from `document_scores.json` |
| `diagnose(gold, prediction, score)` | heuristic failure mode |
| `render_detail(...)` | compact detail panel tailored to the field |
| `comparison_delta(a, b)` | fixed/regressed/partial-change logic |

Recommended initial adapters:

| Adapter | Primary metric | Detail emphasis |
|---|---|---|
| `frequency_per_letter` | current seizure frequency per-letter accuracy | normalization, temporality, evidence span |
| `frequency_loose` | current seizure frequency loose accuracy | parser/normalization behavior |
| `medication_name` | medication-name micro-F1 | missing, extra, and matched medication names |
| `medication_full` | medication full tuple micro-F1 | name, dose, dose unit, frequency component errors |
| `medication_components` | dose/dose-unit/frequency F1 | component-specific regression analysis |
| `seizure_type` | seizure-type micro-F1 | set membership and collapsed benchmark labels |
| `epilepsy_diagnosis` | diagnosis accuracy and collapsed accuracy | exact versus collapsed mismatch |
| `investigations` | EEG/MRI accuracy | absent/present/status errors |
| `evidence_validity` | quote validity and field evidence support | label correct but unsupported; supported but wrong label |
| `gan_frequency` | Pragmatic/Purist micro-F1 | category thresholds, clusters, unknown/no-reference |

The shared review shell should not know how to parse medication tuples or frequency expressions.
It should only know how to display adapter-provided labels, spans, scores, badges, and exports.

---

## All-Key-Metrics Data Contract

The frequency-only `gold`/`predictions` shape should evolve into a document-level bundle with
field cards. This preserves the current contract while making cross-field review natural.

```json
{
  "meta": {
    "dataset": "exectv2",
    "condition": "E3_final_validation",
    "split": "validation",
    "model": "gpt_5_5",
    "harness": "E3",
    "generated_at": "2026-05-08T00:00:00Z",
    "source_artifacts": []
  },
  "metrics": {
    "primary_name": "field_macro_status",
    "primary_value": 0.0,
    "fields": {
      "medication_name": {"kind": "set_f1", "value": 0.0},
      "current_seizure_frequency": {"kind": "accuracy", "value": 0.0}
    }
  },
  "cases": [
    {
      "document_id": "EA0008",
      "source_text": "...",
      "document_status": {
        "failed_fields": ["current_seizure_frequency"],
        "quote_validity_rate": 1.0,
        "temporal_accuracy": 1.0
      },
      "fields": {
        "current_seizure_frequency": {
          "display_name": "Current seizure frequency",
          "metric_kind": "accuracy",
          "correct": false,
          "gold": {"labels": ["1 per 3 week"], "evidence": []},
          "predictions": [
            {
              "variant": "E3",
              "labels": ["every 3 weeks"],
              "parsed": {"count": "1", "period_count": "3", "period_unit": "week"},
              "correct": true,
              "evidence": [],
              "failure_mode": null
            }
          ]
        },
        "medication_full": {
          "display_name": "Medication full tuple",
          "metric_kind": "set_f1",
          "correct": false,
          "gold": {"labels": ["lamotrigine | 75 | mg | twice daily"], "evidence": []},
          "predictions": [
            {
              "variant": "E3",
              "labels": ["lamotrigine | 75 | mg | twice daily", "levetiracetam | 250 | mg | once daily"],
              "tp": ["lamotrigine | 75 | mg | twice daily"],
              "fp": ["levetiracetam | 250 | mg | once daily"],
              "fn": [],
              "failure_mode": "extra_medication"
            }
          ]
        }
      }
    }
  ]
}
```

The current frequency-only contract can be emitted as a compatibility projection of this
larger shape until the React dashboard consumes field cards directly.

---

## Failure Taxonomy

The tool should assign an initial heuristic failure mode, then allow manual override.

### ExECTv2 Frequency Failure Modes

- `no_gold_frequency`: model predicted a frequency but no ExECTv2 frequency annotation exists.
- `missing_prediction`: gold exists but model did not produce a present frequency.
- `unparsed_prediction`: model output cannot be parsed by `parse_frequency_expression()`.
- `wrong_span`: prediction evidence does not overlap a gold frequency span.
- `wrong_count`: count/range mismatch.
- `wrong_period`: period unit or period count mismatch.
- `wrong_temporality`: historical/family/planned frequency selected over current frequency.
- `gold_normalization_gap`: gold span exists but current parser cannot represent it.
- `task_definition_mismatch`: plausible model answer but not aligned with ExECTv2 annotation scope.

### ExECTv2 Medication Failure Modes

- `missing_medication`: gold medication is absent from the prediction.
- `extra_medication`: model predicts a current medication not in gold.
- `wrong_dose`: medication name matches but dose differs or is missing.
- `wrong_dose_unit`: medication name and dose match but unit differs.
- `wrong_medication_frequency`: medication name matches but dosing frequency differs.
- `wrong_temporality_or_status`: historical, stopped, or planned medication treated as current.
- `unsupported_medication_evidence`: medication label may be correct but evidence does not support it.
- `gold_alias_or_normalization_gap`: medication appears equivalent but canonicalization disagrees.

### ExECTv2 Seizure Type Failure Modes

- `missing_seizure_type`: gold seizure type absent from prediction.
- `extra_seizure_type`: predicted seizure type absent from gold.
- `collapsed_category_correct`: exact type differs but benchmark collapsed category matches.
- `wrong_seizure_type_category`: collapsed benchmark category differs.
- `historical_or_uncertain_type_selected`: model selects a non-current or uncertain type as current.
- `unsupported_seizure_type_evidence`: evidence does not support the predicted type.

### ExECTv2 Diagnosis/Investigation Failure Modes

- `missing_diagnosis`: affirmed epilepsy diagnosis not predicted.
- `wrong_diagnosis_subtype`: exact diagnosis differs.
- `collapsed_diagnosis_correct`: subtype differs but collapsed benchmark label matches.
- `negated_or_uncertain_diagnosis_selected`: negated or uncertain diagnosis treated as affirmed.
- `missing_investigation_status`: EEG/MRI status absent when gold status exists.
- `wrong_investigation_status`: normal/abnormal/completed status mismatch.
- `planned_or_historical_investigation_selected`: planned or historical result treated as current/completed.
- `unsupported_diagnosis_or_investigation_evidence`: label may be right but quote is invalid or unrelated.

### Cross-Field Failure Modes

- `quote_invalid`: extraction has a quote that is not found in the source text.
- `quote_missing`: present field lacks evidence.
- `evidence_right_label_wrong`: evidence overlaps gold but normalized label is wrong.
- `label_right_evidence_wrong`: normalized label is correct but evidence is missing or unsupported.
- `temporal_scope_error`: answer is semantically plausible but wrong for the required temporal scope.
- `schema_or_contract_error`: raw output violates schema/project constraints and downstream scoring is suspect.

### Gan Failure Modes

- `exact_label_mismatch_category_correct`: normalized string differs, but Purist/Pragmatic category matches.
- `purist_wrong_pragmatic_correct`: clinically coarse category is right; fine-grained category is wrong.
- `frequent_infrequent_boundary`: error around `1.1` seizures/month threshold.
- `unknown_vs_no_reference`: `unknown` confused with `no seizure frequency reference`.
- `unknown_vs_specific`: model gives a specific rate when gold is `unknown`, or vice versa.
- `ns_vs_short_seizure_free`: seizure-free interval handling error.
- `cluster_format_error`: cluster count or per-cluster count wrong.
- `range_format_error`: numeric range collapsed or widened incorrectly.
- `highest_frequency_error`: model chooses a lower-frequency seizure type when multiple types are present.
- `evidence_missing_or_invalid`: label may be right, but quote is absent or not in source.

---

## Data Contract

Create a shared intermediate JSON so both static HTML and the React dashboard can consume the
same review data later.

```json
{
  "meta": {
    "dataset": "gan_2026 | exectv2",
    "condition": "gpt_5_5__gan_two_pass",
    "split": "development",
    "model": "gpt_5_5",
    "harness": "Gan_two_pass",
    "generated_at": "2026-05-08T00:00:00Z",
    "source_artifacts": []
  },
  "metrics": {
    "primary_name": "pragmatic_micro_f1",
    "primary_value": 0.0,
    "secondary": {}
  },
  "cases": [
    {
      "document_id": "GAN11118",
      "source_text": "...",
      "gold": {
        "label": "2 cluster per month, 6 per cluster",
        "purist": "(1/W,1/D)",
        "pragmatic": "frequent",
        "evidence": []
      },
      "predictions": [
        {
          "variant": "gpt_5_5__gan_two_pass",
          "label": "2 cluster per month, 6 per cluster",
          "purist": "(1/W,1/D)",
          "pragmatic": "frequent",
          "correct": true,
          "evidence": [],
          "raw_output_path": null,
          "failure_mode": null
        }
      ]
    }
  ]
}
```

---

## Implementation Plan

### R1: Extract the Current E3 Review Generator

Move the ad hoc script used to create `e3_validation_frequency_review.html` into a reusable
module.

Suggested file:

- `src/frequency_review.py`

Commands:

```bash
.venv/bin/python src/frequency_review.py exectv2 \
  --scores runs/frequency_workstream/stage_f1/final_validation/document_scores.json \
  --system E3 \
  --event-run-dir runs/final_validation/event_first \
  --output-dir runs/frequency_workstream/stage_f1/e3_review
```

Deliverable:

- parity with the current E3 review page;
- reusable HTML renderer;
- `review_data.json`.

Status note: this is the frequency-first vertical slice. It should be kept, but the next
implementation pass should prevent frequency-specific assumptions from spreading through the
shared renderer.

### R2: Add Gan Review Support

Read Gan scored predictions and render the same case-detail experience.

Command:

```bash
.venv/bin/python src/frequency_review.py gan \
  --gan-path "data/Gan (2026)/synthetic_data_subset_1500.json" \
  --predictions runs/gan_frequency/stage_g2/gpt_5_5__gan_direct/predictions.json \
  --scored runs/gan_frequency/stage_g2/gpt_5_5__gan_direct/gan_frequency_predictions_scored.csv \
  --output-dir runs/gan_frequency/stage_g2/gpt_5_5__gan_direct/review
```

Deliverable:

- Gan case review page with full letters, gold labels, prediction labels, categories, evidence,
  and failure tags.

### R3: Add Variant Comparison

Allow multiple review bundles or prediction files to be merged into one comparison.

Command:

```bash
.venv/bin/python src/frequency_review.py compare \
  --bundle runs/gan_frequency/stage_g2/gpt_4_1_mini__gan_direct/review/review_data.json \
  --bundle runs/gan_frequency/stage_g2/gpt_5_5__gan_two_pass/review/review_data.json \
  --output-dir runs/gan_frequency/stage_g2/comparison_review
```

Deliverable:

- side-by-side variant comparison;
- fixed/regressed case exports.

### R4: Refactor Into Field Adapters

Split the generator into:

- shared bundle/provenance/export code;
- shared static HTML shell;
- ExECTv2 case context loader;
- Gan case context loader;
- field adapters.

Command shape:

```bash
.venv/bin/python src/review_workbench.py exectv2 \
  --scores runs/frequency_workstream/stage_f1/final_validation/document_scores.json \
  --system E3 \
  --fields current_seizure_frequency,medication_full,seizure_type,epilepsy_diagnosis,eeg,mri \
  --event-run-dir runs/final_validation/event_first \
  --output-dir runs/frequency_workstream/stage_f2/e3_key_metrics_review
```

Deliverable:

- current frequency review still works;
- `review_data.json` includes `cases[].fields`;
- renderer can switch active field without changing source text or case selection.

### R5: Add ExECTv2 Key-Metric Adapters

Implement adapters for:

- medication name/full/component scores;
- seizure type exact and collapsed labels;
- epilepsy diagnosis exact and collapsed labels;
- EEG and MRI status;
- evidence validity/support as an audit adapter.

Deliverable:

- all key ExECTv2 metrics visible in one workbench;
- field matrix view;
- field-level failure summaries;
- field-specific `error_tags.csv` export.

### R6: Add Cross-Field Comparison

Extend comparison mode so variant deltas are computed per field and per document.

Deliverable:

- `field_delta_matrix.csv`;
- `field_fixed_cases.csv`;
- `field_regressions.csv`;
- comparison HTML that can filter by field, fixed/regressed status, and failure mode;
- document-level summary that shows which fields drove an improvement or regression.

### R7: Manual Tagging and Writeup Export

Manual tags should move from document-only rows to field-scoped rows:

| Column | Meaning |
|---|---|
| `document_id` | source document |
| `field_id` | field adapter |
| `variant` | system/condition |
| `auto_failure_mode` | heuristic tag |
| `manual_failure_mode` | reviewer override |
| `adjudication_note` | concise note for audit/writeup |
| `include_in_writeup` | boolean shortlist flag |

Deliverable:

- editable field-level `error_tags.csv`;
- `curated_examples.md` export grouped by field and failure mode;
- copy-ready snippets with gold/prediction/evidence context.

### R8: Integrate With React Dashboard Later

Once the static generator is stable, expose review bundles to `dashboard/public/data/` or add a
dedicated Key Metrics page in the React dashboard.

This should happen after R1-R7, because static pages are faster to iterate, easier to archive
with each run, and force the JSON contract to stabilize before app state is introduced.

---

## UI Design Notes

The workbench should stay quiet and dense, closer to a clinical audit tool than a marketing
dashboard.

Required interactions:

- sticky metric/filter header;
- search by document ID or text;
- filters for pass/miss, class, failure mode, system, and variant delta;
- collapsible full letters;
- highlighted evidence spans with a legend;
- copyable normalized labels and quotes;
- links to source artifact paths;
- keyboard-friendly next/previous miss navigation.

Visual conventions:

- gold span: warm yellow;
- prediction evidence: green;
- overlap: purple;
- miss badge: red;
- match badge: green;
- regression: red outline;
- fixed case: green outline.

---

## Relationship To Existing Dashboard

The Reliability Dashboard remains the aggregate dissertation dashboard. The Frequency Review
Workbench evolves into the deep inspection tool for the main key fields.

In the long term:

- dashboard overview links to key-metric workbench bundles;
- key-metric workbench exports curated examples back to dissertation writeup support;
- both consume stable JSON contracts rather than scraping HTML.

---

## Milestones

| Milestone | Outcome | Priority |
|---|---|---|
| R1 | Reusable ExECTv2 static review generator | High |
| R2 | Gan static review generator | High |
| R3 | Variant comparison page | High |
| R4 | Field-adapter refactor and all-fields data contract | High |
| R5 | ExECTv2 key-metric adapters and field matrix | High |
| R6 | Cross-field variant comparison exports | High |
| R7 | Manual field-level tagging and writeup export | Medium |
| R8 | React dashboard Key Metrics page | Medium |
| R9 | Artifact provenance and shareable permalinks | Medium |

---

## Open Decisions

- Should the MVP remain pure static HTML, or should it use a small client-side JS bundle for filtering?
- Should manual error tags be stored as CSV next to the run, or as JSON patches over `review_data.json`?
- For Gan, should evidence quote validity be required for promotion, or only reported as a secondary audit metric?
- For ExECTv2, should letters with no frequency annotation count as negative cases, excluded cases, or explicit task-definition mismatches in visual summaries?
- Should the tool support adjudication notes that can be copied directly into dissertation prose?
- Should the all-fields workbench preserve the filename `frequency_review.py`, or should it graduate
  to `review_workbench.py` with frequency retained as one adapter?
- Which field should define document-level status: any failed key field, a weighted dissertation
  metric, or a user-selected primary field?
- Should set-valued fields use strict tuple matching in the UI, or expose component-level partial
  credit as the default visual summary?
- Should evidence validity be a standalone field, an overlay on every field, or both?
