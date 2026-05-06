# Proposal Review

Reviewed file: `proposal_tight.md`

## Overall Assessment

The tightened proposal is substantially stronger than the broader draft. Its main contribution is now clear: evaluate whether evidence-grounded, event-first extraction improves reliability for epilepsy clinic-letter information extraction compared with direct structured extraction.

The strongest move is the scope reduction. Multi-agent verification, self-consistency, autoresearch loops, and broad model leaderboards are no longer load-bearing. That makes the dissertation more defensible and easier to complete.

## What Is Working

- The research problem is framed as reliability, not generic extraction performance.
- The primary comparison is clear: direct evidence-based extraction versus event-first evidence-based extraction.
- The field list is clinically meaningful and narrow enough to evaluate.
- Temporality is treated as a first-class error source rather than an afterthought.
- JSON/YAML and open/closed model comparisons are appropriately secondary.
- Robustness tests are aligned with likely clinical failure modes.

## Main Risks

1. **Schema drift**

   The proposal mentions values, statuses, temporality, missingness, quotes, sentence IDs, offsets, and confidence. These need one canonical representation before experiments begin.

2. **Ambiguous gold definitions**

   Some fields need explicit scoring rules. For example, seizure frequency may be "monthly", "two in the last year", "seizure-free for six months", or "previously weekly, now controlled". Medication status also needs rules for current, previous, planned, stopped, and family-history mentions.

3. **Evidence validity can be too weak**

   Checking that a quote appears in the source text is necessary but not sufficient. The evaluation should distinguish quote validity from quote support. A copied quote can still support the wrong temporal interpretation.

4. **Aggregation may hide extraction errors**

   Deterministic aggregation is attractive, but it should log which events were selected, ignored, or conflicted. Otherwise the event-first system may be difficult to debug.

5. **Perturbation labels need governance**

   Perturbations should preserve gold labels only when the transformation is label-preserving. Some perturbations, especially planned medication changes or investigation ambiguity, may intentionally change labels.

6. **Model comparison can expand again**

   The proposal correctly avoids a leaderboard. The implementation docs should keep the model set small and force every added model to answer a specific methodological question.

## Immediate Decisions To Lock

- Canonical output schema and event schema.
- Missingness labels and abstention semantics.
- Temporal labels for events and fields.
- Gold-label normalization rules for medication names, dose, seizure frequency, and investigation status.
- Dataset splits and prompt-development rules.
- Primary comparison: S2 direct evidence extraction versus E2/E3 event-first extraction.

## Suggested Dissertation Spine

The dissertation should keep returning to this claim:

> Event-first extraction is useful if it improves field accuracy, temporal correctness, evidence support, or robustness enough to justify its extra cost and latency.

That formulation is empirical, bounded, and defensible even if the results are mixed.
