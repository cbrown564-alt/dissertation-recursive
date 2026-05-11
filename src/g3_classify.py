#!/usr/bin/env python3
"""Classify all 132 G3 seizure-free precision cases into categories based on deep manual reading."""
import csv, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

classifications = {
    "GAN8488": ("C", "~5-6m borderline, analysis says approximately 6m"),
    "GAN7708": ("D", "several months, no specific number"),
    "GAN8188": ("A", "no date of last assessment, 6m is threshold text"),
    "GAN13485": ("D", "over several years, no specific count"),
    "GAN4967": ("A", "many months, since early this year, 6m threshold"),
    "GAN5082": ("B", "letter explicitly says past six months"),
    "GAN5136": ("P", "3 months since last clinic - below threshold"),
    "GAN9202": ("A", "since last appointment, no date"),
    "GAN13889": ("A", "non-epileptic events, 6m threshold"),
    "GAN9601": ("A", "no specific date, 6m threshold"),
    "GAN13591": ("A", "multiple year label correct - years"),
    "GAN5088": ("A", "recent months, no specific number"),
    "GAN9163": ("P", "only 2 months stated in analysis"),
    "GAN8286": ("P", "3 months explicitly stated"),
    "GAN5345": ("A", "several months, no exact number"),
    "GAN8813": ("P", "3 months / 90 days explicit"),
    "GAN7721": ("B", "5 months computed May-Oct"),
    "GAN5141": ("P", "2 months from early August to Oct"),
    "GAN8160": ("P", "3 months, with brief moments of lost thread"),
    "GAN8721": ("A", "no date of last review, 6m threshold"),
    "GAN7892": ("P", "4 months explicit - previous appointment 4 months ago"),
    "GAN8235": ("A", "follow-up period unspecified, 6m threshold"),
    "GAN7911": ("A", "no exact time interval, 6m threshold"),
    "GAN4951": ("B", "Feb 2025 to Oct 2025 = 8 months explicitly computed"),
    "GAN9147": ("D", "no epilepsy, non-epileptic attribution"),
    "GAN8144": ("A", "since last review, no date"),
    "GAN13590": ("A", "multiple year label correct - years"),
    "GAN8169": ("P", "4 to 4.5 months, late May to October"),
    "GAN7834": ("A", "no date of last appointment, 6m threshold"),
    "GAN13574": ("A", "multiple year label correct - years"),
    "GAN8790": ("P", "8 weeks / 2 months explicit wearable data"),
    "GAN3131": ("A", "no date, 6m threshold"),
    "GAN8354": ("P", "3 months since last review explicit"),
    "GAN8185": ("A", "no date, 6m threshold"),
    "GAN7905": ("A", "no date, 6m threshold"),
    "GAN8695": ("A", "multiple year label correct - 2+ years, 6m threshold"),
    "GAN8791": ("P", "6 weeks - clear improvement since mid-August"),
    "GAN8512": ("P", "3 months explicit diary"),
    "GAN5379": ("B", "last epileptic event approximately 6 months ago"),
    "GAN8674": ("A", "several months, no specific number"),
    "GAN13608": ("A", "multiple year label correct - years"),
    "GAN8540": ("P", "3 months explicit in letter"),
    "GAN13349": ("B", "12 months explicitly stated for no events"),
    "GAN13584": ("D", "since mid-adolescence, no count"),
    "GAN8979": ("A", "multiple year correct - post-lobectomy 2021-2025, 6m threshold"),
    "GAN8928": ("A", "no precise start date, 6m threshold"),
    "GAN8355": ("C", "16 months = just over 1 year, label is multiple year - borderline"),
    "GAN13416": ("A", "multiple year label correct, recent years"),
    "GAN5430": ("A", "non-epileptic events only, 6m threshold"),
    "GAN7958": ("A", "multiple year correct - over 3 years"),
    "GAN5210": ("B", "past year mentioned - could be seizure free for 1 year"),
    "GAN8736": ("B", "explicitly over 18 months - label says multiple month, should be multiple year"),
    "GAN9238": ("D", "no specific duration, period unspecified"),
    "GAN8180": ("B", "April to October 2025 = approximately 6 months computed"),
    "GAN5110": ("P", "3 months explicit diary July-September"),
    "GAN8724": ("P", "3 months since dose commenced"),
    "GAN9251": ("A", "no epilepsy confirmed, 12m is future follow-up not SF period"),
    "GAN7816": ("P", "since start of last month - only approximately 1 month"),
    "GAN3118": ("A", "no date of prior visit, 6m threshold"),
    "GAN8135": ("P", "June dose increase to Oct = 3-4 months"),
    "GAN9189": ("A", "extended interval, no numeric, 6m threshold"),
    "GAN5221": ("B", "since early 2024 to Oct 2025 = 18+ months, label says multiple month"),
    "GAN8581": ("P", "June to Oct 2025 = 4 months"),
    "GAN8222": ("B", "seizure about 9 months ago = 9 months seizure-free"),
    "GAN8568": ("A", "9-12m is future follow-up date, 6m threshold"),
    "GAN7783": ("P", "3 months explicit"),
    "GAN8474": ("A", "no explicit numeric duration, 6m threshold"),
    "GAN5200": ("A", "multiple year correct - late 2023 to Oct 2025, 6m threshold"),
    "GAN8476": ("A", "no duration, 6m threshold"),
    "GAN8346": ("B", "late Feb to Oct 2025 = approximately 7-8 months computed"),
    "GAN7884": ("A", "no date of prior review, 6m threshold"),
    "GAN9215": ("P", "early summer to Oct approximately 4 months"),
    "GAN5092": ("A", "no specific timeframe, 6m threshold"),
    "GAN5406": ("A", "non-epileptic events only, 2m is non-epileptic"),
    "GAN8858": ("B", "July 2024 to Oct 2025 = 15 months, label says multiple month"),
    "GAN13843": ("A", "non-epileptic events, 6m threshold"),
    "GAN13600": ("A", "multiple year label correct - years"),
    "GAN4842": ("A", "no date of last appointment, 6m threshold"),
    "GAN7863": ("P", "since early August to Oct = approximately 2 months"),
    "GAN13595": ("A", "multiple year label correct - years"),
    "GAN7719": ("P", "diet started 4 months ago"),
    "GAN4839": ("P", "18 May to Oct 2025 = approximately 4-5 months"),
    "GAN7935": ("A", "brief warnings without full seizures, ambiguous, 6m threshold"),
    "GAN8398": ("A", "multiple year correct - since April 2021"),
    "GAN7961": ("A", "multiple year correct - 2+ years"),
    "GAN7894": ("D", "seizure free in adult life, no count"),
    "GAN8203": ("A", "since last review, no date, 6m threshold"),
    "GAN8924": ("P", "3 months since dose escalation"),
    "GAN8400": ("A", "several months with occasional auras, ambiguous, 6m threshold"),
    "GAN8723": ("P", "several weeks only"),
    "GAN13823": ("A", "non-epileptic events, 6m threshold"),
    "GAN8244": ("A", "since last review, no date, 6m threshold"),
    "GAN8805": ("B", "past six months device analytics - explicit letter text"),
    "GAN8922": ("P", "3 months since titration"),
    "GAN5174": ("A", "since last appointment, no date, 6m threshold"),
    "GAN8423": ("P", "over 10 weeks approximately 2.5 months"),
    "GAN13587": ("A", "multiple year label correct - years"),
    "GAN7872": ("A", "complete control since last review, no date, 6m threshold"),
    "GAN5197": ("A", "since last consultation, no date, 6m threshold"),
    "GAN8577": ("B", "09 March to Sept 2025 = approximately 6 months"),
    "GAN9190": ("B", "late Feb to Oct 2025 = approximately 7-8 months"),
    "GAN9179": ("P", "mid-August to Oct = approximately 6 weeks"),
    "GAN4831": ("B", "early April to Oct 2025 = approximately 6 months"),
    "GAN8473": ("P", "late summer to Oct = only weeks to 2 months"),
    "GAN9618": ("P", "May to Oct 2025 = approximately 5 months"),
    "GAN8854": ("B", "8-month seizure calendar explicit in letter"),
    "GAN8221": ("P", "last three months explicit"),
    "GAN13822": ("A", "non-epileptic events, 6m threshold"),
    "GAN8208": ("A", "since last review, no dates, 6m threshold"),
    "GAN7738": ("B", "letter explicitly says last appointment six months ago"),
    "GAN5213": ("A", "since last review, no date, 6m threshold"),
    "GAN10371": ("A", "multiple year correct - Aug 2023 to Oct 2025 = 2+ years"),
    "GAN5140": ("P", "diary shows no events since May, clinic Sept = approximately 4-5 months"),
    "GAN5121": ("A", "since last review, no date, 6m threshold"),
    "GAN8631": ("A", "in the interim, no date, 6m threshold"),
    "GAN13598": ("A", "multiple year label correct - years"),
    "GAN9654": ("P", "2 months explicit"),
    "GAN8893": ("P", "four months gradual increase then cessation"),
    "GAN9250": ("B", "since January 2025 to Oct = approximately 9 months"),
    "GAN8006": ("B", "past six months explicit in letter text"),
    "GAN13327": ("A", "multiple year label correct - several years"),
    "GAN13858": ("A", "non-epileptic events, 6m threshold"),
    "GAN7987": ("A", "since last review, no date, 6m threshold"),
    "GAN3137": ("A", "since last appointment, no date, 6m threshold"),
    "GAN5248": ("A", "multiple year correct - March 2023 to Oct 2025 = 31 months"),
    "GAN9588": ("B", "Feb 2025 to Oct 2025 = approximately 7 months"),
    "GAN8645": ("A", "since last review, no date, 6m threshold"),
    "GAN8494": ("A", "since last review, no date, 6m threshold"),
    "GAN5034": ("P", "mid-May to Oct = approximately 5 months"),
    "GAN8224": ("P", "3 months explicit - last appointment three months ago"),
    "GAN13487": ("A", "multiple year label correct - over several years"),
    "GAN8969": ("A", "postoperative, no specific duration, 6m threshold"),
}

g3 = list(csv.DictReader(open("audit/gan/G3_seizure_free_precision.csv", encoding="utf-8")))
counts = {"A": 0, "B": 0, "P": 0, "D": 0, "C": 0}
b_cases = []
p_cases = []

for row in g3:
    doc_id = row["document_id"]
    cls, note = classifications.get(doc_id, ("?", "unclassified"))
    counts[cls] = counts.get(cls, 0) + 1
    if cls == "B":
        b_cases.append((doc_id, row["gold_label"], row["specific_duration_found"], note))
    if cls == "P":
        p_cases.append((doc_id, row["gold_label"], row["specific_duration_found"], note))

total = sum(counts.values())
print("=== G3 DEEP CLASSIFICATION RESULTS ===")
print(f"Total cases: {total}")
print()
print(f"A  Threshold-only / label correct:        {counts['A']:3d}  ({100*counts['A']/total:.1f}%)")
print(f"B  Genuine precision opportunity:         {counts['B']:3d}  ({100*counts['B']/total:.1f}%)")
print(f"P  Sub-threshold: <6m but SF label:       {counts['P']:3d}  ({100*counts['P']/total:.1f}%)")
print(f"D  No duration / genuinely vague:         {counts['D']:3d}  ({100*counts['D']/total:.1f}%)")
print(f"C  Ambiguous / borderline:                {counts['C']:3d}  ({100*counts['C']/total:.1f}%)")
print(f"?  Unclassified:                          {counts.get('?', 0):3d}")
print()

print(f"=== B CASES ({len(b_cases)} genuine precision opportunities) ===")
for d, lbl, dur, note in b_cases:
    print(f"  {d} | dur_found={dur!r:20s} | {note}")

print()
print(f"=== P CASES ({len(p_cases)} sub-threshold labelling) ===")
for d, lbl, dur, note in p_cases:
    print(f"  {d} | dur_found={dur!r:20s} | {note}")
