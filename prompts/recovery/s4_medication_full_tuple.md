# S4 Current ASM Full Tuple Extraction

Extract current anti-seizure medication tuples from the epilepsy clinic letter.

Return only one JSON object. Do not wrap the response in Markdown.

Output shape:

```json
{
  "task": "current_asm_full_tuple",
  "candidates": [
    {
      "name": "lamotrigine",
      "dose": "75",
      "dose_unit": "mg",
      "frequency": "twice a day",
      "evidence": {
        "quote": "Current antiepileptic medication: lamotrigine 75 mg twice a day",
        "sentence_id": null,
        "char_start": null,
        "char_end": null
      },
      "confidence": 0.0
    }
  ]
}
```

Rules:

- Include only current anti-seizure medications.
- Preserve the stated medication name, numeric dose, dose unit, and dosing
  frequency when present.
- Set any unstated tuple component to `null`; do not infer missing dose, unit,
  or frequency.
- Historical/stopped example trap: "previously tried levetiracetam" is not a
  current medication.
- Planned example trap: "we will start clobazam" is not current unless the
  letter also says the patient is already taking it.
- Declined example trap: "topiramate was offered but declined" is not current.
- Allergy/intolerance example trap: "allergic to carbamazepine" is not current
  medication use.
- Use exact contiguous evidence quotes copied from the source letter.
