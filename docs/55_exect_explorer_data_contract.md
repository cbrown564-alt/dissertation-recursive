# ExECT Explorer Data Contract

**Date:** 2026-05-12  
**Status:** Initial maintained contract  
**Purpose:** Define how canonical model artifacts enter ExECT Explorer without mixing them with browser-local annotation drafts.

---

## 1. Artifact Classes

ExECT Explorer now has two separate data classes:

1. **Gold letter manifests** under `exect-explorer/public/data/EA*.json`.
   These are generated from BRAT `.ann`, source `.txt`, and ExECT JSON exports.
2. **Model overlay bundles** under `exect-explorer/public/data/model_overlays/*.json`.
   These are generated from canonical model outputs, scored run reports, and the gold letter manifests.

Browser annotation drafts remain a third, deliberately non-canonical state:

- stored only in `localStorage` via the `exect_annotations_<letter_id>` key;
- not written into model overlay bundles;
- not treated as dissertation model artifacts.

---

## 2. Model Overlay Schema

The maintained schema is:

```text
schemas/exect_explorer_model_overlay.schema.json
```

Top-level fields:

- `schema_version`: contract version.
- `artifact_class`: always `model_overlay`.
- `source`: canonical model directory, Explorer gold data directory, scored comparison report, and optional run manifest.
- `model`: model, harness, and pipeline identifiers copied from canonical extraction metadata.
- `documents`: one entry per letter included in the bundle.

Each document contains:

- `document_id`
- `letter_path`
- `canonical_path`
- `gold_entity_count`
- `model_field_count`
- `model_fields`

Each `model_fields` item contains:

- a stable `field_path`;
- the model value plus missingness, temporality, and status;
- evidence spans resolved to source-letter character offsets when possible;
- overlapping gold candidates from the BRAT-derived Explorer manifest;
- an alignment status: `overlaps_gold`, `evidence_only`, `ungrounded`, or `not_present`.

---

## 3. Representative Export

Build a small H6fs + evidence-resolver sample bundle with:

```bash
python exect-explorer/scripts/build_model_overlay.py \
  --canonical-dir runs/evidence_resolver/scored_batch/resolved \
  --explorer-data-dir exect-explorer/public/data \
  --comparison-report runs/evidence_resolver/scored_batch/comparison_report.json \
  --run-manifest runs/evidence_resolver/scored_batch/run_manifest.json \
  --limit 3 \
  --output exect-explorer/public/data/model_overlays/h6fs_ev_validation_sample.json
```

This bundle is intentionally small: it is a UI and contract fixture, not a
replacement for the full scored run directory.
