# Frequency Review Workbench Plan

**Date:** 2026-05-08  
**Seed artifact:** `runs/frequency_workstream/stage_f1/e3_validation_frequency_review.html`  
**Purpose:** Scale the one-off E3 seizure-frequency review page into a reusable visual
evaluation tool for comparing variants, harnesses, datasets, and error modes.

---

## Product Idea

The Frequency Review Workbench should be a researcher-facing inspection surface for
seizure-frequency extraction. Its job is not to replace the command-line scorer. Its job is
to make the scorer's outputs inspectable enough that metric changes are explainable.

The current E3 review page already has the right ingredients:

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
- **metrics:** ExECTv2 per-letter accuracy, ExECTv2 loose accuracy, Gan Pragmatic micro-F1,
  Gan Purist micro-F1, exact normalized-label match, evidence validity.

---

## Core Questions

The tool should answer these questions quickly:

1. Which variant is winning, and is the difference visible in the actual letters?
2. Is a miss caused by evidence selection, normalization, temporality, gold-label mismatch, or task definition?
3. Does a model find the right text but produce the wrong label?
4. Does a Gan-optimized prompt transfer back to ExECTv2?
5. Which specific examples should be quoted in the dissertation as representative error modes?

---

## Users and Workflow

Primary user: dissertation author during model/prompt development.

Secondary users: supervisors/reviewers who need to audit whether reported frequency metrics are
credible.

Typical workflow:

1. Run a model/harness condition.
2. Score it with `src/evaluate.py` for ExECTv2 or `src/gan_frequency.py` for Gan.
3. Generate a workbench bundle.
4. Open the HTML/React view and filter to misses.
5. Tag failure modes.
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
- gold annotations from `MarkupSeizureFrequency.csv`
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
   - document count and availability;
   - class distribution for Gan or annotation-count distribution for ExECTv2.

2. **Case List**
   - sortable table of documents;
   - pass/miss;
   - gold label/category;
   - predicted label/category;
   - failure diagnosis;
   - quick links to full case.

3. **Case Detail**
   - full letter text;
   - highlighted gold spans;
   - highlighted prediction evidence spans;
   - gold normalized candidates;
   - prediction, parsed prediction, category mappings;
   - model evidence quote;
   - raw model output link/expandable JSON;
   - suggested failure mode.

4. **Error Mode Summary**
   - counts by failure mode;
   - examples per mode;
   - exportable shortlist for dissertation writeup.

---

## Comparison Mode

The workbench becomes much more useful when it can compare two or more variants on the same
documents.

### Variant Comparison Layout

For each document:

| Column | Content |
|---|---|
| Gold | normalized label, category, evidence span |
| Variant A | prediction, category, evidence, pass/miss |
| Variant B | prediction, category, evidence, pass/miss |
| Delta | fixed / regressed / both miss / both correct |

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

### Outputs

- `variant_comparison.html`
- `variant_comparison.csv`
- `fixed_cases.csv`
- `regressions.csv`

---

## Failure Taxonomy

The tool should assign an initial heuristic failure mode, then allow manual override.

### ExECTv2 Failure Modes

- `no_gold_frequency`: model predicted a frequency but no ExECTv2 frequency annotation exists.
- `missing_prediction`: gold exists but model did not produce a present frequency.
- `unparsed_prediction`: model output cannot be parsed by `parse_frequency_expression()`.
- `wrong_span`: prediction evidence does not overlap a gold frequency span.
- `wrong_count`: count/range mismatch.
- `wrong_period`: period unit or period count mismatch.
- `wrong_temporality`: historical/family/planned frequency selected over current frequency.
- `gold_normalization_gap`: gold span exists but current parser cannot represent it.
- `task_definition_mismatch`: plausible model answer but not aligned with ExECTv2 annotation scope.

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

### R4: Integrate With React Dashboard Later

Once the static generator is stable, expose review bundles to `dashboard/public/data/` or add a
dedicated Frequency page in the React dashboard.

This should happen after R1-R3, because static pages are faster to iterate and easier to archive
with each run.

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
Workbench is the deep inspection tool for one hard field.

In the long term:

- dashboard overview links to frequency workbench bundles;
- frequency workbench exports curated examples back to dissertation writeup support;
- both consume stable JSON contracts rather than scraping HTML.

---

## Milestones

| Milestone | Outcome | Priority |
|---|---|---|
| R1 | Reusable ExECTv2 static review generator | High |
| R2 | Gan static review generator | High |
| R3 | Variant comparison page | High |
| R4 | Manual failure-mode tagging/export | Medium |
| R5 | React dashboard Frequency page | Medium |
| R6 | Artifact provenance and shareable permalinks | Medium |

---

## Open Decisions

- Should the MVP remain pure static HTML, or should it use a small client-side JS bundle for filtering?
- Should manual error tags be stored as CSV next to the run, or as JSON patches over `review_data.json`?
- For Gan, should evidence quote validity be required for promotion, or only reported as a secondary audit metric?
- For ExECTv2, should letters with no frequency annotation count as negative cases, excluded cases, or explicit task-definition mismatches in visual summaries?
- Should the tool support adjudication notes that can be copied directly into dissertation prose?

