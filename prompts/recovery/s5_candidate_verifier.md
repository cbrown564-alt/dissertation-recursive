# S5 Candidate Verifier

Verify extracted candidates against the source epilepsy clinic letter.

Return only one JSON object. Do not wrap the response in Markdown.

Input includes source text plus task-specific candidates from S4. For each
candidate, decide whether to keep it, drop it, or keep it with normalized
values.

Output shape:

```json
{
  "decisions": [
    {
      "task": "current_asm_full_tuple",
      "candidate_index": 0,
      "decision": "keep",
      "normalized": {
        "name": "lamotrigine",
        "dose": "75",
        "dose_unit": "mg",
        "frequency": "twice a day"
      },
      "reason": "The quoted text states current lamotrigine use.",
      "evidence": {
        "quote": "Current antiepileptic medication: lamotrigine 75 mg twice a day",
        "sentence_id": null,
        "char_start": null,
        "char_end": null
      }
    }
  ]
}
```

Rules:

- Keep a candidate only when its evidence quote directly supports it.
- Drop current medication candidates that are historical, stopped, planned,
  declined, allergies, family history, or general counselling.
- Drop diagnosis and seizure-type candidates that are inferred rather than
  explicitly stated.
- Drop seizure-frequency candidates that are clearly historical when a current
  frequency or seizure-free statement exists.
- Normalize only spelling, abbreviations, brands, and simple dose/frequency
  wording; do not add unstated clinical facts.
- Evidence quotes must be exact contiguous text copied from the source letter.
