# S4 Current Seizure Frequency Extraction

Extract the current seizure frequency from the epilepsy clinic letter.

Return only one JSON object. Do not wrap the response in Markdown.

Output shape:

```json
{
  "task": "current_seizure_frequency",
  "candidate": {
    "value": "2 to 3 per month",
    "temporal_scope": "current",
    "seizure_type": "focal impaired awareness seizures",
    "evidence": {
      "quote": "focal impaired awareness seizures approximately 2 to 3 per month",
      "sentence_id": null,
      "char_start": null,
      "char_end": null
    },
    "confidence": 0.0
  }
}
```

Rules:

- Extract only the current or most recent active seizure frequency.
- Prefer explicit current status such as "currently", "now", "at present",
  "ongoing", or the assessment/plan summary.
- Do not let historical frequencies override current seizure-free statements.
- Treat "seizure-free since March 2024" or "no seizures since..." as a current
  frequency statement.
- Preserve the linked seizure type when it is stated in the same phrase or
  nearby sentence.
- If no current frequency is stated, use `"candidate": null`.
- Use exact contiguous evidence quotes copied from the source letter.
