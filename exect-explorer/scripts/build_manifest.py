#!/usr/bin/env python3
"""
Build a unified manifest for all ExECT v2 letters by parsing BRAT .ann files,
raw .txt files, and structured .json files.
"""

import json
import os
import re
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path("data/ExECT 2 (2025)")
TXT_DIR = BASE_DIR / "Gold1-200_corrected_spelling"
ANN_DIR = BASE_DIR / "Gold1-200_corrected_spelling"
JSON_DIR = BASE_DIR / "Json"
OUT_DIR = Path("exect-explorer/public/data")

# Known flawed documents from Phase 6 gold standard analysis
KNOWN_FLAWS = {
    "EA0001": {
        "category": "medication_tuple_ambiguity",
        "description": "Split-dose ambiguity: '500mg morning and 500mg evening' encoded as single frequency value. Gold is structurally simplified.",
        "oracle_impact": "medication_full_tuple"
    },
    "EA0012": {
        "category": "seizure_free_hallucination_vs_gold_ambiguity",
        "description": "Letter mentions both 'seizure free' AND historical focal seizures. Model may attend to wrong sentence.",
        "oracle_impact": "seizure_type"
    },
    "EA0034": {
        "category": "unknown_seizure_type_meta_label",
        "description": "Annotator used 'unknown seizure type' meta-label; models consistently infer specific type from clinical context. Structural benchmark-model mismatch.",
        "oracle_impact": "seizure_type"
    },
    "EA0056": {
        "category": "frequency_contradiction",
        "description": "Two frequency mentions in same letter: '1 per month' vs 'cluster of 4 over 3 days'. ExECTv2 wants all mentions; Gan wants single normalized judgment.",
        "oracle_impact": "seizure_frequency"
    },
    "EA0006": {
        "category": "temporal_sparsity",
        "description": "Previous medication 'carbamazepine' lacks temporal anchoring in gold. Annotator labels as current when temporal column is empty; model may correctly infer 'previous'.",
        "oracle_impact": "medication_temporality"
    }
}

# Oracle failure rates per field
ORACLE_RATES = {
    "medication_name": 0.0,
    "medication_full_tuple": 0.108,
    "seizure_type": 0.133,
    "epilepsy_diagnosis": 0.175,
    "seizure_frequency": 0.292,
    "freq_type_linkage": 0.292,
}

# Entity type colours for the UI
ENTITY_COLOURS = {
    "Diagnosis": "#c45c3e",
    "Prescription": "#2d8a5e",
    "SeizureFrequency": "#b85cb8",
    "PatientHistory": "#5c7db8",
    "Investigations": "#b88a5c",
    "BirthHistory": "#5cb8a5",
    "Onset": "#8a5cb8",
    "EpilepsyCause": "#5c8ab8",
    "WhenDiagnosed": "#b85c7d",
}


def parse_ann_file(ann_path: Path):
    """Parse a BRAT .ann file into structured entities and attributes."""
    entities = {}
    attributes = defaultdict(dict)
    relations = []
    notes = []

    with open(ann_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n\r")
            if not line:
                continue
            if line.startswith("T"):
                # Entity: T1\tDiagnosis 21 73\ttext...
                match = re.match(r"^(T\d+)\t(\S+)\s+(\d+)\s+(\d+)\t(.*)$", line)
                if match:
                    eid, etype, start, end, text = match.groups()
                    entities[eid] = {
                        "id": eid,
                        "type": etype,
                        "start": int(start),
                        "end": int(end),
                        "text": text,
                        "attributes": {},
                    }
            elif line.startswith("A"):
                # Attribute: A12\tDiagCategory T1 Epilepsy
                # Format: A<id>\t<name> <target> <value...>
                match = re.match(r"^(A\d+)\t(\S+)\s+(T\d+)\s+(.*)$", line)
                if match:
                    _, attr_name, target_id, value = match.groups()
                    if target_id in entities:
                        entities[target_id]["attributes"][attr_name] = value
            elif line.startswith("R"):
                relations.append(line)
            elif line.startswith("N"):
                notes.append(line)

    return list(entities.values()), relations, notes


def parse_json_file(json_path: Path):
    """Parse the structured JSON export."""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_txt(txt_path: Path):
    with open(txt_path, "r", encoding="utf-8") as f:
        return f.read()


def detect_overlapping_entities(entities):
    """Find entities that share the same text span."""
    span_map = defaultdict(list)
    for e in entities:
        span_map[(e["start"], e["end"])].append(e)
    overlaps = []
    for span, ents in span_map.items():
        if len(ents) > 1:
            overlaps.append({
                "start": span[0],
                "end": span[1],
                "text": ents[0]["text"],
                "entity_types": [e["type"] for e in ents],
                "entity_ids": [e["id"] for e in ents],
            })
    return overlaps


def detect_temporal_sparsity(entities):
    """Find entities that probably need temporal anchoring but lack it."""
    sparse = []
    for e in entities:
        if e["type"] in ("Prescription", "SeizureFrequency", "PatientHistory"):
            has_temporal = any(k in e["attributes"] for k in [
                "YearDate", "TimePeriod", "NumberOfTimePeriods",
                "TimeSince_or_TimeOfEvent", "PointInTime"
            ])
            if not has_temporal:
                sparse.append({
                    "id": e["id"],
                    "type": e["type"],
                    "text": e["text"],
                    "reason": "No temporal attribute"
                })
    return sparse


def detect_incomplete_medication_tuples(entities):
    """Find Prescription entities with missing tuple fields."""
    incomplete = []
    for e in entities:
        if e["type"] == "Prescription":
            attrs = e["attributes"]
            missing = []
            for field in ["DrugName", "DrugDose", "DoseUnit", "Frequency"]:
                if field not in attrs or attrs[field] in ("", None):
                    missing.append(field)
            if missing:
                incomplete.append({
                    "id": e["id"],
                    "text": e["text"],
                    "missing_fields": missing,
                })
    return incomplete


def extract_temporal_events(entities):
    """Extract events with temporal information for the timeline view."""
    events = []
    for e in entities:
        attrs = e["attributes"]
        year = attrs.get("YearDate")
        period = attrs.get("TimePeriod")
        num_periods = attrs.get("NumberOfTimePeriods")
        time_since = attrs.get("TimeSince_or_TimeOfEvent")
        point_in_time = attrs.get("PointInTime")
        lower = attrs.get("LowerNumberOfSeizures")
        upper = attrs.get("UpperNumberOfSeizures")
        num_seizures = attrs.get("NumberOfSeizures")
        
        # Only include entities with some temporal signal
        if year or period or time_since or point_in_time:
            events.append({
                "id": e["id"],
                "type": e["type"],
                "text": e["text"],
                "start": e["start"],
                "end": e["end"],
                "year": year,
                "period": period,
                "num_periods": num_periods,
                "time_since": time_since,
                "point_in_time": point_in_time,
                "lower_seizures": lower,
                "upper_seizures": upper,
                "num_seizures": num_seizures,
            })
    return events


def build_letter_manifest(letter_id: str):
    txt_path = TXT_DIR / f"{letter_id}.txt"
    ann_path = ANN_DIR / f"{letter_id}.ann"
    json_path = JSON_DIR / f"{letter_id}.json"

    text = read_txt(txt_path)
    entities, relations, notes = parse_ann_file(ann_path)
    json_data = parse_json_file(json_path) if json_path.exists() else []

    # Sort entities by start position
    entities.sort(key=lambda e: (e["start"], e["end"]))

    overlaps = detect_overlapping_entities(entities)
    temporal_sparse = detect_temporal_sparsity(entities)
    incomplete_meds = detect_incomplete_medication_tuples(entities)
    timeline_events = extract_temporal_events(entities)

    # Count entities by type
    type_counts = defaultdict(int)
    for e in entities:
        type_counts[e["type"]] += 1

    # Detect unknown seizure type
    unknown_seizure = any(
        e["type"] == "Diagnosis" and "unknown" in e["attributes"].get("CUIPhrase", "").lower()
        for e in entities
    )

    # Detect negated entities
    negated = [e for e in entities if e["attributes"].get("Negation", "").lower() == "negated"]

    # Detect low-certainty entities
    low_certainty = []
    for e in entities:
        cert = e["attributes"].get("Certainty")
        if cert and int(cert) < 5:
            low_certainty.append({
                "id": e["id"],
                "type": e["type"],
                "text": e["text"],
                "certainty": int(cert)
            })

    # Build flaws list
    flaws = []
    if letter_id in KNOWN_FLAWS:
        flaws.append(KNOWN_FLAWS[letter_id])
    if overlaps:
        flaws.append({
            "category": "overlapping_entities",
            "description": f"{len(overlaps)} text span(s) carry multiple entity types.",
            "details": overlaps,
            "oracle_impact": "scoring_ambiguity"
        })
    if temporal_sparse:
        flaws.append({
            "category": "temporal_sparsity",
            "description": f"{len(temporal_sparse)} entity/ies lack explicit temporal anchoring.",
            "details": temporal_sparse,
            "oracle_impact": "seizure_frequency"
        })
    if incomplete_meds:
        flaws.append({
            "category": "incomplete_medication_tuple",
            "description": f"{len(incomplete_meds)} prescription(s) have incomplete tuple fields.",
            "details": incomplete_meds,
            "oracle_impact": "medication_full_tuple"
        })
    if unknown_seizure:
        flaws.append({
            "category": "unknown_seizure_type_meta_label",
            "description": "This letter contains the 'unknown seizure type' meta-label — a structural ceiling for all models.",
            "oracle_impact": "seizure_type"
        })
    if negated:
        flaws.append({
            "category": "negated_entities",
            "description": f"{len(negated)} entity/ies are explicitly negated in the text.",
            "details": [{"id": e["id"], "type": e["type"], "text": e["text"]} for e in negated],
            "oracle_impact": "clinical_precision"
        })

    return {
        "id": letter_id,
        "text": text,
        "entities": entities,
        "json_export": json_data,
        "overlaps": overlaps,
        "temporal_sparse": temporal_sparse,
        "incomplete_meds": incomplete_meds,
        "timeline_events": timeline_events,
        "type_counts": dict(type_counts),
        "flaws": flaws,
        "negated_entities": [{"id": e["id"], "type": e["type"], "text": e["text"]} for e in negated],
        "low_certainty": low_certainty,
        "has_unknown_seizure": unknown_seizure,
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Find all letter IDs
    txt_files = sorted(TXT_DIR.glob("EA*.txt"))
    letter_ids = [f.stem for f in txt_files]

    print(f"Found {len(letter_ids)} letters")

    manifest = []
    for lid in letter_ids:
        try:
            m = build_letter_manifest(lid)
            manifest.append(m)
        except Exception as e:
            print(f"Error processing {lid}: {e}")

    # Write individual letter files
    for m in manifest:
        out_path = OUT_DIR / f"{m['id']}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=2)

    # Write index
    index = {
        "letters": [{"id": m["id"], "type_counts": m["type_counts"], "flaw_count": len(m["flaws"])} for m in manifest],
        "entity_colours": ENTITY_COLOURS,
        "oracle_rates": ORACLE_RATES,
        "total_letters": len(manifest),
    }
    with open(OUT_DIR / "index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(manifest)} letter manifests to {OUT_DIR}")

    # Stats
    flaw_counts = defaultdict(int)
    for m in manifest:
        for f in m["flaws"]:
            flaw_counts[f["category"]] += 1
    print("Flaw distribution:")
    for cat, count in sorted(flaw_counts.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
