# Dissertation Recursive

Working materials for a dissertation on reliable, event-first information extraction from epilepsy clinic letters.

The current proposal is [proposal_tight.md](proposal_tight.md). It narrows the project to a training-free reliability evaluation: compare direct structured extraction with an event-first, evidence-grounded pipeline, then evaluate JSON/YAML and open/closed model differences as secondary factors.

## Documentation Map

- [Proposal review](docs/proposal_review.md) - strengths, risks, and immediate decisions from the tightened proposal.
- [Scope and research questions](docs/01_scope_and_research_questions.md) - locked project spine, hypotheses, and exclusions.
- [Canonical schema](docs/02_canonical_schema.md) - target fields, missingness, evidence, temporality, and event objects.
- [Pipeline design](docs/03_pipeline_design.md) - direct baselines, event-first stages, validation, and aggregation.
- [Evaluation protocol](docs/04_evaluation_protocol.md) - datasets, splits, metrics, perturbations, and comparisons.
- [Implementation roadmap](docs/05_implementation_roadmap.md) - practical build order and milestones.
- [Literature review matrix](docs/06_literature_review_matrix.md) - review strands and extraction decisions to support.
- [Canonical JSON Schema](schemas/canonical_extraction.schema.json) - initial machine-readable output contract.

## Current Priority

The next work should lock the canonical schema and scoring definitions before prompt or model iteration. That protects the primary comparison from accidental overfitting and keeps the event-first claim measurable.
