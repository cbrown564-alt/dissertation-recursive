# S4 Current ASM Name Extraction

Extract only current anti-seizure medication names from the epilepsy clinic
letter.

Return only one JSON object. Do not wrap the response in Markdown.

Output shape:

```json
{
  "task": "current_asm_names",
  "candidates": [
    {
      "name": "lamotrigine",
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

- Extract medication names only; do not include dose, unit, or dosing
  frequency in `name`.
- Include only medications the letter states are current anti-seizure
  medications.
- Drop medications that are previous, stopped, declined, planned, trialled in
  the past, allergies, or family history.
- If a medication is being increased or reduced and the patient is currently
  taking it, keep it as current.
- Use exact contiguous evidence quotes copied from the source letter.
- Do not infer a medication from a dose or diagnosis.
- If no current anti-seizure medication is stated, return an empty
  `candidates` array.
