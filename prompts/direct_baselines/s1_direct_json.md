# S1 Direct JSON Extraction

You are extracting structured information from an epilepsy clinic letter.

Return only one JSON object matching the canonical extraction schema. Do not
wrap the response in Markdown. Use `pipeline_id: "S1_direct_json"`.

S1 is the no-evidence direct baseline. Include all required `evidence` keys
from the schema, but set field evidence to `null` or `[]` if you extract a
present clinical value. Do not invent unsupported values. Use `not_stated`
when the letter does not state the field.

Required final fields:

- current anti-seizure medications: name, dose, dose_unit, frequency, status
- previous anti-seizure medications
- current seizure frequency, preserving temporal scope and seizure type
- seizure types
- EEG result/status
- MRI result/status
- epilepsy diagnosis/type

Use empty `events: []` for this baseline.
