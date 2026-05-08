# Adjudication Reference — 20260430T141604Z_h008_single_broad_field_llm_n50

First 25 rows from the h008 run. Use this alongside the scoring CSV.

## Scoring guide

- **value_correct**: Y / N / P — Is the extracted value clinically correct?
- **status_correct**: Y / N / P — Is the temporal/medication status correct (current / historical / planned)?
- **normalization_correct**: Y / N / NA — Is the normalized label or drug name appropriate?
- **evidence_grade**: exact_span / overlapping_span / section_level / wrong_temporal_status / unsupported / missing_evidence
  - *exact_span*: cited evidence directly supports the value and status.
  - *overlapping_span*: overlaps the right text but includes extra or incomplete wording.
  - *section_level*: points to right section but not the decisive phrase.
  - *wrong_temporal_status*: evidence supports the entity but not the claimed status.
  - *unsupported*: cited evidence does not support the value.
  - *missing_evidence*: value non-empty but no usable evidence supplied.

---

## Letter 01 — source_row_index=11118

### Extractions

**SF** gold=`2 cluster per month, 6 per cluster` | pred=`2 per week` | exact=✗ monthly=✗
  **med** `sodium valproate 500 mg bd` status=current | ev: _"Sodium valproate 500 mg bd"_
  **med** `clobazam 10 mg nocte` status=current | ev: _"Clobazam 10 mg nocte"_
  **sz_type** `generalised convulsions` onset=generalized | ev: _"These events are brief generalised convulsions"_

### Letter text

```
Department of Neurology 

Clinic Date: 02 October 2025 

Dr Eleanor Matthews  
St Bartholomew's Hospital  
Department of Neurology, West Smithfield, London EC1A 7BE  

Dear Dr Eleanor Matthews,  

Michael Turner, DOB: 14-03-1989, Hospital No: H392745 NHS No. 9034512786  
Flat 3, Willow Supported Living, 22 Brook Lane, London, SE15 4JG 

Diagnoses:  

Generalised epilepsy with documented generalised spike-and-wave activity on prior EEG (2017) 

Current Medication:  

Sodium valproate 500 mg bd  
Clobazam 10 mg nocte (as rescue on cluster days) 

Plan:  

- Continue sodium valproate 500 mg twice daily  
- Maintain clobazam 10 mg at night for up to 3 nights during cluster periods, as per existing
protocol
- Continue seizure charting by supported accommodation staff and share monthly summaries  
- Consider ambulatory EEG if frequency or pattern worsens  
- Safety advice reinforced; SUDEP risk discussed; emphasis on sleep regularity and alcohol avoidance

I reviewed Michael Turner in my clinic today. He lives in supported accommodation where rotating
staff maintain daily seizure charts; these charts, which I reviewed, are used as our primary source
of frequency data. Over the last four weeks, the records note: "Cluster days twice this month;
typically six seizures in 24 h." These events are brief generalised convulsions with rapid recovery,
no new focal features, and no injuries reported. Staff have been consistent in logging times,
witnessed features, and rescue medication use.

He describes a prodrome of diffuse head pressure and photophobia on days preceding clusters,
occasionally with poor sleep the night before. There is no clear relation to intercurrent illness,
but stress and missed meals were mentioned as possible triggers. He reports good adherence to sodium
valproate, and staff confirm administration records align. Where rescue has been needed, clobazam 10
mg nocte has been used for up to three consecutive nights with good effect and without excessive
daytime sedation.

Neurologically he is unchanged on examination. Weight stable, no tremor, and no rash. Liver function
tests in August were within normal limits; we will repeat monitoring at the usual interval. He
remains seizure‑free between clusters for prolonged stretches, and there have been no emergency
department attendances this year.

We discussed options. Given the current balance of efficacy and tolerability, I recommend continuing
sodium valproate at the present dose, with staff continuing meticulous charting. If clusters
increase in frequency or if daytime sedation from clobazam becomes problematic, we can consider
either a small valproate titration or introducing lamotrigine as adjunct. For now, no immediate
changes are required.

I have provided updated written guidance for staff regarding when to initiate clobazam on cluster
days, thresholds for calling 999, and parameters for documenting duration and post‑ictal recovery
(Ã‚Â· please file in the medication folder). Standard safety advice was reiterated, including
supervision when bathing, avoiding heights, and maintaining sleep hygiene. We also reviewed SUDEP
information briefly and gave a leaflet for the team and key worker.

Follow‑up: I will review him in six months, sooner if the pattern shifts (e.g. more than two cluster
days per month or any prolonged seizure >5 minutes). The team will continue to email monthly seizure
chart summaries to our clinic address.

With best wishes,  

Yours sincerely
```

---

## Letter 02 — source_row_index=16750

### Extractions

**SF** gold=`6 per 7 month` | pred=`unknown` | exact=✗ monthly=✗
  **med** `Lamotrigine 150 mg b.d.` status=current | ev: _Current treatment consists of Lamotrigine 150 mg b.d._
  **med** `Levetiracetam 1 g b.d.` status=current | ev: _and Levetiracetam 1 g b.d._
  **sz_type** `focal seizure` onset=focal | ev: _In February she experienced a prolonged focal seizure lasting 8 minutes_
  **sz_type** `absence` onset=generalized | ev: _In May there were four further brief absences_
  **sz_type** `generalised tonic-clonic seizure` onset=generalized | ev: _in August a single generalised tonic-clonic seizure was reported_
  **inv** `other` result=pending | ev: _Bloods today for routine monitoring (FBC, U&Es, LFTs)_

### Letter text

```
KINGS NEUROSCIENCES CENTRE


Clinic Date: 8 September 2010 

Dr Patel
Elmwood Medical Centre

72 Elmwood Road, London, SE5 3HT
Dear Dr Patel
Jane Smith, DOB: 21-11-1982, Hospital No: H738291 NHS No. 0093384721
Flat 4, 21 Brook Lane, London, SE5 1AB 

Thank you for asking me to review the above patient in the Neurology Clinic today. She is known to
our service with focal epilepsy and, encouragingly, reports a steady improvement over recent months,
which she attributes to better adherence following use of a consistent seizure diary and reminders
on her phone.

Current treatment consists of Lamotrigine 150 mg b.d. and Levetiracetam 1 g b.d., both well
tolerated without dose-limiting adverse effects. She reports improved energy levels compared to
earlier in the year and no new intercurrent illnesses. There is no current concern regarding mood or
sleep beyond occasional pre-examination anxiety, which she manages with standard breathing
techniques taught by our epilepsy nurse specialist.

Regarding recent events: In February she experienced a prolonged focal seizure lasting 8 minutes,
resolving without intervention. In May there were four further brief absences, and in August a
single generalised tonic-clonic seizure was reported at school (not witnessed by family). These
episodes have been clearly recorded in her diary, with triggers likely related to missed meals and
sleep deprivation around coursework deadlines. Since adopting structured reminders in late August,
she has had no further events and has taken all doses on time.

Neurological examination today is unremarkable. There are no drug-related rashes, no tremor, and no
cognitive concerns on bedside screening. We discussed safety and rescue planning; no rescue
medication has been required. She prefers to avoid changes while her control is improving, and I
agree that stability is prudent given the recent positive trajectory.

Plan:
- Continue Lamotrigine 150 mg b.d. and Levetiracetam 1 g b.d. unchanged.
- Maintain seizure diary and phone reminders; continue avoidance of sleep deprivation and missed
meals.
- Bloods today for routine monitoring (FBC, U&Es, LFTs) – to be copied to you.
- Review in clinic in 4 months, sooner if breakthrough seizures recur or if tolerability issues
arise.

Overall, her focal epilepsy appears better controlled with improved adherence, and she is optimistic
about maintaining this trajectory.

Yours sincerely
```

---

## Letter 03 — source_row_index=14706

### Extractions

**SF** gold=`2 per 5 month` | pred=`2 per 5 months` | exact=✗ monthly=✓
  **med** `sodium valproate 500 mg twice daily` status=current | ev: _1. Sodium valproate 500 mg twice daily_
  **med** `clobazam 10 mg at night as needed` status=current | ev: _2. Clobazam 10 mg at night as needed for jet-lag periods_
  **sz_type** `generalised` onset=generalized | ev: _Patient has generalised epilepsy._
  **sz_type** `rhythmic twitching of the right arm and a sense of déjà vu` onset=focal | ev: _He woke with rhythmic twitching of the right arm and a sense of déjà vu._
  **sz_type** `similar pattern of symptoms` onset=focal | ev: _The second event was in October 2019 in Scotland, also during sleep, lasting five minutes with a similar pattern of symp_
  **inv** `EEG` result=pending | ev: _Arrange routine EEG at next in-person visit when in London_

### Letter text

```
Epilepsy Centre

Neurosciences Division


From: Dr Thomas Reid (KING'S COLLEGE HOSPITAL NHS FOUNDATION TRUST)
Sent: 14 October 2019 10:15
To: neuro.epilepsy@nhs.net
Cc: Dr Meera Shah (KING'S COLLEGE HOSPITAL NHS FOUNDATION TRUST); Dr Patrick O’Neill (KING'S COLLEGE
HOSPITAL NHS FOUNDATION TRUST)
Subject: Telephone review and travel-related considerations

Dear Thomas

Epilepsy Diagnosis:

Patient has generalised epilepsy.

Present Medication:

1. Sodium valproate 500 mg twice daily
2. Clobazam 10 mg at night as needed for jet-lag periods (patient-reported intermittent use)

Present Seizure Frequency:

Two events over the last five months.

History and Context:

This is a follow-up conducted by telephone as he is a frequent business traveller with irregular
sleep and time zones. He reports adherence to valproate on most days but occasionally misses doses
during long-haul flights. His first seizure occurred in May 2019 in Ireland, at night while asleep.
He woke with rhythmic twitching of the right arm and a sense of déjà vu. The second event was in
October 2019 in Scotland, also during sleep, lasting five minutes with a similar pattern of
symptoms. He denies daytime collapses, injuries, or prolonged postictal confusion. No alcohol excess
reported; significant sleep disruption around both events.

Plan of Action:

- Reinforced general measures for generalised epilepsy with emphasis on strict medication adherence
when crossing time zones; advised use of alarms and written dosing plans for flights.
- Continue sodium valproate 500 mg twice daily. He prefers no change at present given infrequency of
events and travel schedule.
- May use clobazam 10 mg at night for up to three nights around major time-zone shifts if sleep
disruption is expected, as previously advised.
- Arrange routine EEG at next in-person visit when in London; if logistics difficult, consider
ambulatory EEG coordinated around his travel.
- Safety counselling provided (no driving until compliant with DVLA guidance; avoid sleep
deprivation, swimming alone, or climbing heights).
- Next review by telephone in three months or sooner if further seizures occur.

With best wishes,
```

---

## Letter 04 — source_row_index=12383

### Extractions

**SF** gold=`4 per day` | pred=`focal onset seizures four times per day, tonic-clonic seizures 2 times per month` | exact=✗ monthly=✗
  **sz_type** `focal onset seizures` onset=focal | ev: _focal onset seizures four times per day_
  **sz_type** `drop attacks` onset=focal | ev: _drop attacks occurring in batches_
  **sz_type** `tonic-clonic seizures` onset=generalized | ev: _tonic-clonic seizures 2 times per month_

### Letter text

```
King's College Hospital 

Department of Neurosciences 

Clinic Date: 15 September 2023 

Dr A. Patel
Consultant Neurologist  
King's College Hospital  
Department of Neurosciences, Denmark Hill, London SE5 9RS  

Dear Dr A. Patel
Consultant Neurologist,  

James Carter, DOB: 14-03-1986, Hospital No: KCH472918 NHS No. 9473165820  
Flat 12, 8 Millwright Lane, London, SE15 3AB

Thank you for your referral. I reviewed the patient in clinic following concerns about ongoing
seizures in the context of his work with metal fabrication and intermittent arc-light exposure. He
reports strict adherence to workplace safety practices, including a full protective welding visor
and gloves, and says he does not remove the visor during active welding. He is otherwise in good
general health. There is no recent history of head injury, meningitis, or alcohol misuse. Sleep has
been variable due to shift changes at the workshop.

Regarding current events, he still has focal onset seizures four times per day, drop attacks
occurring in batches, and tonic-clonic seizures 2 times per month, this long-standing pattern has
persisted without major change. He and his partner describe the focal episodes as brief lapses with
a rising internal sensation and impaired awareness lasting under a minute, often clustering late
morning. The drop attacks tend to occur in short runs over two to three days, typically in the early
evening after work, with quick recovery but occasional bruising. The tonic-clonic events are usually
nocturnal or in the early hours; he is sore and fatigued for the following day. He denies clear
photic triggers, and states the seizure frequency does not vary with welding versus non-welding
days. He continues his regular medication regimen as previously prescribed and has not missed doses.

He does not drive and remains in manual employment with modified duties when fatigued. His employer
is aware of his condition and has implemented buddy supervision during hot-work tasks. There have
been no burns or occupational incidents attributable to events on the shop floor. He reports that
hydration, regular breaks, and consistent sleep help him feel steadier, though not changing the
overall frequency. No new neurological symptoms were volunteered. Examination in clinic today was
unremarkable with normal speech, cranial nerves, tone, and coordination; gait steady.

I have advised ongoing documentation of events with dates, times, and context (workday versus rest
day, sleep duration, and recent stressors), and asked him to bring his workplace risk assessment to
the next appointment so that we can ensure appropriate safety planning remains in place. We also
discussed continuing to avoid working at heights or near unguarded machinery during periods of
increased events. He is agreeable to sharing seizure logs with your practice.

I will arrange routine follow-up and will update you if any new information emerges from collateral
reports or monitoring. Please let me know if there are any concerns in the interim.

Yours sincerely
```

---

## Letter 05 — source_row_index=5555

### Extractions

**SF** gold=`multiple per week` | pred=`several episodes per week` | exact=✗ monthly=✗
  **med** `sodium valproate 500 mg twice daily` status=current | ev: _Continue sodium valproate 500 mg twice daily for now_
  **sz_type** `generalised absence-type seizures` onset=generalized | ev: _brief generalised absence-type seizures_
  **sz_type** `myoclonic jerks` onset=focal | ev: _occasional morning myoclonic jerks on awakening_
  **inv** `MRI` result=normal | ev: _MRI brain (2023) was normal_
  **inv** `EEG` result=abnormal | ev: _EEG (2024) showed generalised 3 Hz spike-and-wave discharges_
  **inv** `other` result=normal | ev: _Routine bloods last month were normal including FBC and LFTs_

### Letter text

```
University College Hospital

National Hospital for Neurology and Neurosurgery

Clinic Date: 02 October 2025

Dr Amelia Rhodes
Riverside Medical Practice
14 Brook Street, London W1A 3QL

Dear Dr Amelia Rhodes,

Alex Morgan, DOB: 22-08-1991, Hospital No: U918273 NHS No. 3021187745
Flat 3, 7 Harrow Lane, London NW1 5TS

Summary/Diagnoses: Generalised epilepsy with photosensitivity and startle-triggered events; early-
years childcare worker in a high-noise, multitasking environment; sleep fragmentation due to
interrupted midday rest breaks; history of mild anxiety symptoms related to workplace interruptions.

Medication: Sodium valproate 500 mg twice daily.

I reviewed the patient in clinic today. They attended alone. They report ongoing challenges at work
in a nursery setting where the ambient noise is high, tasks require frequent rapid switching of
attention, and planned midday rest breaks are often interrupted by staffing needs. Over the past
three months they describe several episodes per week of brief generalised events, typically
characterised by abrupt behavioural arrest with eyelid fluttering and loss of awareness lasting
10–20 seconds, occasionally clustering in the early afternoon when rest has been curtailed.
Colleagues have noted brief pauses and dropped tasks without warning, followed by rapid recovery.
There have been two morning episodes with sudden generalised jerks on awakening, leading to the
patient dropping lightweight items but without injury.

The patient has no focal aura or lateralising features. No tongue biting or sustained postictal
confusion has been reported after the brief absence-type events. Sleep is curtailed by early starts
and the unreliable rest period at midday. Alcohol is minimal, and there is no recreational drug use.
They deny missed doses; a weekly pill organiser is used. There have been no recent infections or
intercurrent illnesses.

Examination today was unremarkable with normal cardiovascular and neurological findings. Weight and
blood pressure are within target range. Review of prior investigations: MRI brain (2023) was normal.
EEG (2024) showed generalised 3 Hz spike-and-wave discharges provoked by hyperventilation and
intermittent photic stimulation, consistent with generalised epilepsy. Routine bloods last month
were normal including FBC and LFTs.

Seizures: Patient currently experiences several episodes per week of brief generalised absence-type
seizures, with occasional morning myoclonic jerks on awakening. These episodes are more frequent on
days when the midday rest break is interrupted.

Plan:
- Diagnosis reaffirmed as generalised epilepsy. Continue sodium valproate 500 mg twice daily for
now; adherence is good and no adverse effects reported.
- Provide seizure diary template to document timing relative to rest break interruptions and high-
noise periods at work.
- Workplace liaison letter (with patient consent) offering neutral information about generalised
epilepsy and recommending predictable, uninterrupted short rest period where feasible, and avoidance
of strobe-like lighting in play areas.
- Safety advice reiterated for childcare duties: ensure another adult supervises during water play
or ladder use; avoid carrying hot liquids during early morning periods when myoclonic jerks have
occurred.
- Consider dose optimisation or alternative broad-spectrum therapy if diary confirms persistent
several episodes per week despite stable routine; review in 3 months with diary and, if needed,
repeat EEG with sleep deprivation.

Yours sincerely,
```

---

## Letter 06 — source_row_index=6216

### Extractions

**SF** gold=`4 per 6 week` | pred=`4 brief focal-aware episodes and 1 focal-impaired awareness spell over 6 weeks` | exact=✗ monthly=✗
  **med** `Lamotrigine 150 mg twice daily` status=current | ev: _Continue lamotrigine 150 mg twice daily unchanged for now_
  **med** `Clobazam 10 mg at night as needed` status=current | ev: _Clobazam 10 mg at night as needed (intermittent use per patient)_
  **med** `Lacosamide 50 mg at night for 1 week, then 50 mg twice daily for 1 week, then increase to 100 mg in the morning and 50 mg at night for 1 week, and thereafter 100 mg twice daily` status=planned | ev: _Initiate lacosamide as follows: 50 mg at night for 1 week, then 50 mg twice daily for 1 week, then increase to 100 mg in_
  **sz_type** `Focal-aware episodes` onset=focal | ev: _four brief focal-aware episodes_
  **sz_type** `Focal-impaired awareness spell` onset=focal | ev: _one focal-impaired awareness spell_
  **inv** `other` result=pending | ev: _Please arrange basic metabolic panel and ECG locally before uptitration to 100 mg twice daily_

### Letter text

```
Epilepsy Centre

Neurosciences Division

From: Dr Priya Shah (KING'S COLLEGE HOSPITAL NHS FOUNDATION TRUST)
Sent: 17 June 2020 10:12
To: kch.epilepsyclinic@nhs.net
Cc: Dr Michael Turner (KING'S COLLEGE HOSPITAL NHS FOUNDATION TRUST); Dr Emily Chen (KING'S COLLEGE
HOSPITAL NHS FOUNDATION TRUST)
Subject: Review and medication adjustment

Dear Dr Shah,

Epilepsy diagnosis:

Focal epilepsy, likely temporal lobe onset, based on semiology and diary-linked patterns.

Present medication:

1. Lamotrigine 150 mg twice daily
2. Clobazam 10 mg at night as needed (intermittent use per patient)

Present seizure frequency:

According to the patient’s seizure diary app, events have clustered around sudden noises; over the
past six weeks there were four brief focal-aware episodes and one focal-impaired awareness spell,
typically occurring when exposed to abrupt auditory shocks (e.g., dropped crockery or unexpected
alarms). The diary time-stamps correlate with environments of heightened noise and suggest a pattern
consistent with startle-triggered focal events rather than spontaneous occurrences.

Plan of action:

- We discussed optimising treatment for focal seizures with sensory triggers. The patient reports
good adherence and stable lamotrigine serum levels previously. Given the diary-documented noise-
precipitated events and occasional breakthrough focal-impaired awareness, I recommend adding
lacosamide as adjunctive therapy while maintaining lamotrigine.

- Initiate lacosamide as follows: 50 mg at night for 1 week, then 50 mg twice daily for 1 week, then
increase to 100 mg in the morning and 50 mg at night for 1 week, and thereafter 100 mg twice daily
if tolerated. Continue this dose until review.

- Continue lamotrigine 150 mg twice daily unchanged for now. Clobazam may remain as intermittent
rescue for anticipated high-risk noise exposures, but we advised minimising routine use to avoid
sedation.

- The patient will continue to use the seizure diary app to log events, noting context (sound level,
location, preceding stress, sleep quality) and any medication side effects. We asked them to enable
the app’s noise-trigger tagging feature to refine correlation analysis.

- Safety: advised on avoiding hazardous activities when episodes are more likely (e.g., handling hot
liquids during known noisy times). No driving until seizure-free in accordance with DVLA guidance;
we have reiterated current restrictions and the need to report any loss of awareness events.

Follow-up:

- Please arrange basic metabolic panel and ECG locally before uptitration to 100 mg twice daily to
screen for any conduction concerns.
- I have scheduled a review in 4 months. If well-tolerated with improved control, we will consider
cautious clobazam de-escalation. If breakthrough events persist despite lacosamide, we will discuss
alternative adjuncts or video-EEG monitoring.

With best wishes,
```

---

## Letter 07 — source_row_index=10703

### Extractions

**SF** gold=`unknown, 2 to 3 per cluster` | pred=`2 per week` | exact=✗ monthly=✗
  **med** `Lamotrigine 200 mg twice daily` status=current | ev: _Current anti-seizure medication: Lamotrigine 200 mg twice daily_
  **med** `Levetiracetam 1,000 mg twice daily` status=current | ev: _Levetiracetam 1,000 mg twice daily_
  **sz_type** `focal epilepsy` onset=focal | ev: _He describes focal epilepsy_
  **sz_type** `focal impaired-awareness seizure` onset=focal | ev: _one focal impaired-awareness seizure_
  **sz_type** `possible secondary generalisation` onset=generalized | ev: _possible secondary generalisation overnight_
  **inv** `MRI` result=abnormal | ev: _MRI (2021) demonstrated right mesial temporal T2/FLAIR signal change_
  **inv** `EEG` result=abnormal | ev: _EEG (2022) showed right temporal interictal sharp waves_
  **inv** `MRI` result=pending | ev: _I have requested an urgent repeat MRI brain with epilepsy protocol_
  **inv** `EEG` result=pending | ev: _ambulatory EEG (72 hours)_

### Letter text

```
King's College Hospital 

Department of Neurosciences 

Clinic Date: 02 October 2025 

Dr A. Sharma
Consultant Neurologist  
King's College Hospital  
Department of Neurosciences, King's College Hospital, London SE5 9RS  

Dear Dr A. Sharma
Consultant Neurologist,  

Daniel Carter, DOB: 14-03-1986, Hospital No: K912345 NHS No. 9076543211  
12 Brookfield Road, London, SE15 3QT

Thank you for your referral. I reviewed Daniel Carter in clinic today with his partner present.
Unfortunately, there has been a clear deterioration over recent months, marked by an increase in
seizure-related incidents and several episodes resulting in falls and minor injuries (forearm
bruising and a superficial eyebrow laceration managed with steri-strips at a walk-in centre). He
describes focal epilepsy with impaired awareness; events begin with a rising epigastric sensation
and left arm tingling, followed by behavioural arrest, lip-smacking, and unresponsiveness for 60–90
seconds. Post-event confusion lasts around 20–30 minutes, often with headache and fatigue.

Frequency has escalated. He and his partner report that what were previously sporadic episodes have
evolved into short bursts of activity linked to warm environments and sustained physical
activity—particularly on school field afternoons and community fun-run days—after which he may have
two to three events over a 24–48 hour period. Outside these activity-linked bursts, he is now
averaging one focal impaired-awareness seizure every 7–10 days. No clear nocturnal convulsive events
have been witnessed, though he wakes on some mornings with tongue bite indentations and myalgia
suggestive of possible secondary generalisation overnight on two occasions in the last six weeks.

He has focal epilepsy. Onset was in 2019 following a mild traumatic head injury. MRI (2021)
demonstrated right mesial temporal T2/FLAIR signal change without clear volume loss; EEG (2022)
showed right temporal interictal sharp waves. Current anti-seizure medication: Lamotrigine 200 mg
twice daily and Levetiracetam 1,000 mg twice daily, both reportedly taken reliably. He notes mood
lability on Levetiracetam but prefers not to alter this while seizures are active. There is no
recent alcohol excess; sleep has been fragmented due to childcare demands. No intercurrent infection
reported.

Given the recent falls and injury risk, coupled with the apparent cluster pattern associated with
warm, exertional community events, I am concerned about a worsening of seizure control. I have
requested an urgent repeat MRI brain with epilepsy protocol and ambulatory EEG (72 hours) to capture
both habitual focal events and any sleep-related activity. I have also issued a safety plan,
including advice on hydration, gradual warm-up/cool-down for physical activity, and supervision
during higher-risk periods, as discussed. He has agreed to track events using a diary and smartphone
seizure app, including antecedents, duration, and recovery features.

I will review him in four weeks or sooner if further injuries occur. Depending on results, we may
consider transitioning from Levetiracetam to Brivaracetam or adding Lacosamide, but I will defer a
firm decision until investigations are complete. I have given interim written guidance to his
workplace regarding temporary duty modification to reduce risk from ladders and hot environments.
DVLA advice has been reiterated in line with current seizure activity.

Please let me know if there are any additional concerns or if further information emerges from
primary care.

Yours sincerely
```

---

## Letter 08 — source_row_index=10594

### Extractions

**SF** gold=`unknown, 2 per cluster` | pred=`unknown` | exact=✗ monthly=✓
  **med** `Levetiracetam 1000 mg twice daily` status=current | ev: _Levetiracetam 1000 mg twice daily_
  **sz_type** `focal impaired-awareness seizures` onset=focal | ev: _Clusters characterized by two focal impaired-awareness seizures_
  **inv** `EEG` result=pending | ev: _Arrange routine EEG_
  **inv** `other` result=pending | ev: _updated serum biochemistry including U&E, LFT, and levetiracetam level_

### Letter text

```
St Mary's Hospital 

Institute of Neurology 

Clinic Date: 02 October 2025 

Dr Ahmed  
St Mary's Hospital  
Institute of Neurology, St Mary's Hospital, London W2 1NY  

Dear Dr Ahmed,  

Sophie Daniels, DOB: 12-05-1991, Hospital No: H948320 NHS No. 8934751206  
14 Brookside Close, London, W10 6JP 

Medication: 

Levetiracetam 1000 mg twice daily. Patient reports tolerating this without clear adverse effects
apart from occasional fatigue. No recent dose changes.

History since last review: 

She describes intermittent nocturnal episodes over the past three months with post-event confusion
on waking and occasional tongue-biting reported by her partner. She remains currently not driving by
self-report. Clusters characterized by two focal impaired-awareness seizures; frequency unclear. She
is keeping a basic diary but cannot specify how often these occur, as some events may be
unwitnessed.

She notes increased stress at work and irregular sleep. No intercurrent illness, head injury, or new
medications. Caffeine intake modest; no alcohol excess. Menses regular; no clear cyclical pattern
noted by her. Family is supportive and monitoring overnight. No emergency department attendances.

Examination today was unremarkable with normal speech, gait, and cranial nerve examination. Blood
pressure 118/72 mmHg, pulse 72 bpm regular.

Plan: 

- Continue levetiracetam 1000 mg twice daily for now. 
- Implement structured seizure and trigger diary with partner corroboration to help clarify timing
and frequency of clusters and any precipitants (stress, sleep loss).
- Safety counselling reiterated, including bathing precautions and avoidance of heights or open
water when alone. She remains off driving and understands to inform DVLA as appropriate per current
guidance.
- Arrange routine EEG and updated serum biochemistry including U&E, LFT, and levetiracetam level
(for reference only).
- Provide information on sleep hygiene and stress management resources; patient agreeable. 
- We will review in clinic in 4 months or sooner if events escalate, any injury occurs, or if there
is a change in pattern.

Yours sincerely
```

---

## Letter 09 — source_row_index=14036

### Extractions

**SF** gold=`unknown` | pred=`4 per month` | exact=✗ monthly=✗
  **med** `sodium valproate 300 mg twice daily` status=current | ev: _1. Sodium valproate 300 mg twice daily_
  **med** `clobazam 5 mg at night` status=current | ev: _2. Clobazam 5 mg at night_
  **sz_type** `drop attacks` onset=unknown | ev: _4 drop attacks_
  **inv** `EEG` result=pending | ev: _Arrange ambulatory EEG within the next 6–8 weeks_

### Letter text

```
Epilepsy Centre

Neurosciences Division


From: Dr Emily Fraser (KING'S COLLEGE HOSPITAL NHS FOUNDATION TRUST)
Sent: 20 April 2023 10:15
To: epilepsy.centre@nhs.net
Cc: Dr Nikhil Shah (KING'S COLLEGE HOSPITAL NHS FOUNDATION TRUST); Dr Laura Bennett (KING'S COLLEGE
HOSPITAL NHS FOUNDATION TRUST)
Subject: Review and medication adjustment

Hi Emily

Epilepsy Diagnosis:

Diagnosis remains under review with ongoing characterisation. No definitive electroclinical
classification assigned at present.

Present Medication:

1. Sodium valproate 300 mg twice daily
2. Clobazam 5 mg at night

Present Seizure Frequency:

The parents state that since starting ketogenic diet he has had 4 drop attacks, the latest one on 17
Dec. They report no clear precipitating triggers; sleep is variable due to the family currently
awaiting relocation from temporary accommodation, with crowded living conditions noted and frequent
nocturnal disturbances.

Plan of Action:

- Continue ketogenic diet with dietician oversight; parents to maintain seizure and dietary logs and
report any concerns regarding hydration or tolerance.
- Increase clobazam to 5 mg in the morning and 5 mg at night for two weeks, then 10 mg at night
thereafter if daytime sedation occurs; maintain sodium valproate at current dose pending review of
response and tolerability.
- Arrange ambulatory EEG within the next 6–8 weeks to assist with classification and to capture
typical events if possible.
- Refer to hospital family liaison for support regarding housing-related stressors that may be
impacting sleep and seizure threshold.
- Safety advice reiterated regarding drop attacks: use of protective headgear during high‑risk
activities and avoidance of unsupervised bathing.
- Follow‑up in three months or sooner if attacks cluster or there is any injury.

With best wishes
```

---

## Letter 10 — source_row_index=4562

### Extractions

**SF** gold=`1 per 6 week` | pred=`approximately every 6 weeks` | exact=✗ monthly=✗
  **sz_type** `focal aware episodes` onset=focal | ev: _stereotyped focal aware episodes_
  **sz_type** `impaired awareness with automatisms` onset=focal | ev: _occasionally progressing to impaired awareness with automatisms_

### Letter text

```
Epilepsy Centre 

Neurosciences Division 

Clinic Date: 12 October 2019 

Dr Patel  
St Cuthbert’s NHS Trust  
Neurology Department, 12 Waverley Road, Bristol BS1 4QF  

Dear Dr Patel,  

Jordan Ellis, DOB: 14-11-1988, Hospital No: H392174 NHS No. 9081764521  
Flat 3, 29 Brookfield Terrace, Bristol BS7 1NL  

Diagnoses: 

Focal epilepsy, likely temporal lobe onset. 

I reviewed Jordan Ellis in the epilepsy clinic today. They remain on long-term antiseizure therapy,
with bone-health monitoring recorded elsewhere. They report stereotyped focal aware episodes
characterised by a brief rising epigastric sensation and déjà vu, occasionally progressing to
impaired awareness with automatisms lasting 1–2 minutes, followed by mild post-ictal fatigue. There
have been no generalised tonic–clonic seizures reported. Seizure clustering is not described.

Since the last review, there has been no intercurrent illness, sleep pattern is stable, and there is
no clear relation to menses or alcohol. Work attendance is good and no injuries have occurred.
Importantly, the median inter-seizure interval ≈ six weeks, with the patient noting that stress and
missed meals can shorten this interval, while regular routines appear protective.

Neurological examination today was non-focal. No new adverse effects from medication were reported.
Driving status and SUDEP risk were discussed; no red-flag features such as prolonged impaired
awareness, cyanosis, or trauma were reported. Emergency care plans remain unchanged as seizures
self-terminate within minutes and there has been no requirement for rescue medication.

We agreed to continue current management and to keep a detailed seizure diary capturing potential
precipitants, duration, and level of awareness during events. Investigations and bone-health reviews
are being coordinated through existing pathways and are documented elsewhere. We will plan routine
follow-up in six months, or earlier should there be a change in frequency, semiology, or recovery
profile.

Yours sincerely
```

---

## Letter 11 — source_row_index=14369

### Extractions

**SF** gold=`2 per 3 month` | pred=`2 per week` | exact=✗ monthly=✗
  **med** `Thiamine 100 mg daily` status=current | ev: _Thiamine 100 mg daily (self-initiated)_
  **med** `Omeprazole 20 mg once daily` status=current | ev: _Omeprazole 20 mg once daily for dyspepsia_
  **inv** `EEG` result=non_diagnostic | ev: _prior routine EEG reported as non-diagnostic_
  **inv** `MRI` result=normal | ev: _past MRI (2012) described as structurally unremarkable without focal lesion_
  **inv** `other` result=pending | ev: _Routine bloods today (FBC, U&E, LFT, B12, folate, TFTs) requested_

### Letter text

```
KINGS NEUROSCIENCES CENTRE


Clinic Date: 15 April 2015

Dr James Rowe
Stour Vale Medical Centre

14 Millstream Way
Stourbridge
West Midlands DY8 1QG
Dear Dr James Rowe
Mr Daniel Kerr, DOB: 03-02-1986, Hospital No: H728915 NHS No. 7410592264
42 Forge Mews, Unit 6, West Bromwich, B70 8QR 

Diagnoses/summary: Recurrent seizures of unclear classification; prior routine EEG reported as non-
diagnostic; past MRI (2012) described as structurally unremarkable without focal lesion. Driving
suspended and remains under DVLA self-report guidance. Occupational exposure: metalwork/welding with
intermittent arc-light exposure; uses protective visor per workplace routine.

Previous medication: Levetiracetam (behavioural irritability), Sodium Valproate (weight gain,
tremor), Carbamazepine (dizziness), Lamotrigine (ineffective at therapeutic dose), Clobazam (recent
withdrawal). Rescue: Buccal midazolam supplied previously, unused in the past year.

Not taken: Topiramate, Zonisamide, Lacosamide, Perampanel, Pregabalin, Tiagabine, Rufinamide. 

I reviewed him in clinic today, attended alone. He works full-time as a welder/fabricator and
reports good adherence to workplace safety, including visor and appropriate filters; no sustained
photic provocation at work. He notes regular sleep and reduced caffeine. He withdrew from Clobazam
on 12/Jan. At that time, he had 2 seizures, one precipitated by illness. He has remained stable
without seizures since. He reports occasional brief light-headedness under stress but no witnessed
events, no tongue-biting, no incontinence, and no post-ictal confusion since January. No new
injuries.

Current medication:
- None for seizure prophylaxis at present
- Thiamine 100 mg daily (self-initiated)
- Omeprazole 20 mg once daily for dyspepsia 

Work/occupational context: Continues welding duties; avoids lone working for heavy lifts; colleagues
aware of emergency plan. Reports no issues with arc flash given visor use; no sustained photic
discomfort. He drives neither privately nor professionally.

Examination: BP 124/76, pulse 72 regular. Neurological examination normal; no focal deficit.
Fundoscopy normal (no papilloedema). Gait normal.

Investigations: Prior EEG (2014) non-specific. MRI brain (2012) structurally normal. Routine bloods
today (FBC, U&E, LFT, B12, folate, TFTs) requested.

Discussion and plan:
- Given his current stability off Clobazam since January with no further seizures, we agreed to
continue observation without initiating a new anti-seizure medication at this point. We discussed
red flags and early contact plan.
- I advised continued adherence to workplace safety standards; he already uses appropriate
visor/filters; no change required.
- To maintain a seizure diary (including intercurrent illness, sleep disruption, and any welding
shift variations).
- If breakthrough events occur, we discussed possible future options (e.g. Lacosamide or Zonisamide)
and the need to consider side-effect profiles relevant to concentration and visual focus at work.
- DVLA guidance reiterated; he confirms ongoing compliance. 
- Follow-up in 4–6 months, earlier if any recurrence. Telephone review acceptable. 

Yours sincerely
```

---

## Letter 12 — source_row_index=9786

### Extractions

**SF** gold=`unknown` | pred=`worsening over 2 months` | exact=✗ monthly=✗
  **med** `Carbamazepine 400 mg twice daily` status=current | ev: _Carbamazepine modified‑release 400 mg twice daily_
  **med** `Levetiracetam 750 mg twice daily` status=current | ev: _Levetiracetam 750 mg twice daily_
  **sz_type** `focal epileptic spasms` onset=focal | ev: _Skipping meals triggers focal epileptic spasms_

### Letter text

```
Epilepsy Centre

Neurosciences Division

From: Dr Priya Shah (KING'S COLLEGE HOSPITAL NHS FOUNDATION TRUST)
Sent: 18 February 2018 10:15
To: kch.neuroclinic@nhs.net
Cc: Dr Michael O’Connor (KING'S COLLEGE HOSPITAL NHS FOUNDATION TRUST); Dr Helen Davies (KING'S
COLLEGE HOSPITAL NHS FOUNDATION TRUST)
Subject: Worsening seizure control and access barriers at work

Dear Priya,

Diagnosis:

Seizure disorder of uncertain classification.

Current Medicines:

1. Carbamazepine modified‑release 400 mg twice daily
2. Levetiracetam 750 mg twice daily

Seizure Course and Triggers:

The patient reports a clear deterioration over the past two months. Skipping meals triggers focal
epileptic spasms, and this has become more frequent due to their shift pattern and restricted access
to personal items at a cleanroom/data‑hall workplace. They describe brief clusters of spasms lasting
seconds, sometimes progressing to confusion if a full dose has been missed. Workplace controls have
delayed retrieval of rescue medication and refills on several occasions, leading to missed doses and
a noticeable worsening of seizure control compared with earlier this year.

Context and Contributing Factors:

- The patient must request escorted access to lockers and pharmacy deliveries, often resulting in
delays beyond dosing times.
- Meal breaks are occasionally curtailed or rescheduled at short notice during maintenance windows,
coinciding with increased spasms on fasted days.
- No alcohol or recreational drug use reported; sleep is fragmented on night shifts.

Plan:

- Provide the patient with a written dosing schedule and a work letter requesting reasonable
adjustments: guaranteed meal breaks aligned with dosing, timely escorted access to personal
medication, and permission to carry a limited supply of non‑contaminating, sealed medication within
permitted zones.
- Issue a duplicate supply card for community pharmacy to reduce refill delays and encourage use of
a monitored dosage system to mitigate missed doses.
- Maintain current doses for now while the above adjustments are implemented; we will reassess
frequency and severity at review in 8–10 weeks.
- If access and adherence improve but spasms persist, we will discuss alternative therapies at next
clinic visit.

I have arranged follow‑up in the next available clinic. Please advise if workplace liaison
documentation requires specific wording.

With best wishes,
```

---

## Letter 13 — source_row_index=9879

### Extractions

**SF** gold=`unknown` | pred=`occasional` | exact=✗ monthly=✗
  **med** `Lamotrigine 200 mg twice daily` status=current | ev: _Lamotrigine modified-release 200 mg twice daily_
  **med** `Buccal midazolam 10 mg PRN` status=current | ev: _Rescue: buccal midazolam 10 mg PRN prolonged events_
  **sz_type** `Focal tonic` onset=focal | ev: _Overall seizure pattern is best characterised as focal tonic_
  **sz_type** `Jaw clamping and right arm stiffening` onset=focal | ev: _jaw tightness then body goes stiff on the right_
  **inv** `MRI` result=normal | ev: _Prior MRI (2016) reported no definite epileptogenic lesion_
  **inv** `EEG` result=abnormal | ev: _Routine EEG in 2019 showed intermittent left temporal slowing without epileptiform discharges_
  **inv** `other` result=pending | ev: _Bloods requested: FBC, U&Es, LFTs, lamotrigine trough level in 1–2 weeks_

### Letter text

```
KINGS NEUROSCIENCES CENTRE

Clinic Date: 02 October 2025

Dr Kate
Health Centre

Keele University, Keele, Newcastle

 Staffordshire ST5 5BG

Dear Dr Kate

Wendy Brown, DOB: 21-11-1982, Hospital No: K482715 NHS No. 6592841037
Flat 7 Brookside Avenue, Newcastle-under-Lyme, ST5 2QD

Diagnoses/summary: Focal epilepsy, likely temporal lobe onset. Patient has practiced aura
recognition strategies and is able to describe prodromal warning features in her own words.

Current concerns: She reports that over the past three months she has had brief clusters of events
described as “jaw tightness then body goes stiff on the right, and I can’t get words out”, typically
lasting under a minute with rapid recovery. She links these to missed doses of anti-seizure
medication and has kept a diary demonstrating a temporal association. Overall seizure pattern is
best characterised as focal tonic with missed ASM doses.

Aura/ictal description (patient-reported): “A rising wave in my stomach, a metallic taste, and
sounds feel far away for a few seconds. If I catch it early and sit down, it sometimes fades; if
I’ve missed tablets, it goes into the jaw clamping and right arm stiffening.” No clear
generalisation reported. Postictal phase minimal; feels briefly foggy.

Relevant history: No new neurological deficits. No recent head injury. Sleep fragmented due to work
shifts. Alcohol minimal. No pregnancy plans. Family history negative for epilepsy.

Investigations: Prior MRI (2016) reported no definite epileptogenic lesion. Routine EEG in 2019
showed intermittent left temporal slowing without epileptiform discharges. No recent bloods on file.

Medication: Lamotrigine modified-release 200 mg twice daily. Rescue: buccal midazolam 10 mg PRN
prolonged events (not used in past year). Reports occasional missed evening doses during late
shifts. No known drug allergies.

Self-management: She has actively used aura recognition strategies learned at previous epilepsy
nurse sessions and keeps a structured seizure and dosing diary on her phone. She has set phone
alarms but reports these are sometimes ignored during busy shifts.

Examination (today): Alert, oriented, fluent speech. Cranial nerves intact. Motor and coordination
normal. No focal deficits. BP 118/72, pulse 72 regular.

Plan:
- Reinforce adherence: patient to switch to a single daily dosing schedule if suitable after serum
level review; she agrees to pharmacy blister packs and watch-based reminders to reduce missed doses.
- Bloods requested: FBC, U&Es, LFTs, lamotrigine trough level in 1–2 weeks.
- Safety: reiterated individual seizure triggers (sleep loss, missed doses) and advised continued
use of aura recognition strategies, sitting/lying down when warnings occur, and maintaining diary
entries.
- Work: letter offered to occupational health to consider minor shift adjustments to support
adherence.
- Follow-up: nurse telephone review in 6 weeks to review levels, adherence tools, and seizure diary;
clinic review in 4 months or earlier if events increase or generalise.

Thank you for your continued care of Wendy Brown. Please contact me if there are any concerns or if
adherence remains problematic despite the above measures.

Yours sincerely
```

---

## Letter 14 — source_row_index=8488

### Extractions

**SF** gold=`seizure free for multiple month` | pred=`unknown` | exact=✗ monthly=✗
  **med** `Levetiracetam 1,000 mg twice daily` status=current | ev: _Levetiracetam 1,000 mg twice daily_
  **med** `Clobazam 10 mg at night as needed` status=current | ev: _Clobazam 10 mg at night as needed for clusters_
  **sz_type** `Focal epilepsy with impaired awareness` onset=focal | ev: _Focal epilepsy with impaired awareness_
  **sz_type** `Focal to bilateral tonic–clonic evolution` onset=focal | ev: _prior nocturnal and daytime focal to bilateral tonic–clonic evolution_

### Letter text

```
Department of Neurology 

Clinic Date: 02 October 2025 

Dr Aisha Rahman  
South Thames Neurology Centre  
Neurology Outpatients, 12 Kingfisher Way, London SE10 3AB  

Dear Dr Aisha Rahman,  

Michael Turner, DOB: 23-02-1991, Hospital No: H392715 NHS No. 9182736450  
Flat 7, 28 Willow Street, London EC2A 4BH 

Diagnoses:  

Focal epilepsy with impaired awareness; prior nocturnal and daytime focal to bilateral tonic–clonic
evolution reported in March

Current Medication: 

Levetiracetam 1,000 mg twice daily  
Clobazam 10 mg at night as needed for clusters (not recently required) 

Plan: 

- Continue levetiracetam at current dose  
- Maintain adherence supports (pillbox and phone reminders)  
- Safety advice reinforced; no driving until formally cleared per DVLA guidance  
- Routine follow-up in 6 months, sooner if any breakthrough events 

I reviewed Michael Turner in clinic today. He reports a sustained improvement in seizure control
since adopting adherence supports (pillbox and smartphone reminders), which have markedly reduced
missed doses and improved day-to-day stability. For context, before this improvement: in March he
had 5 seizures during sleep and 5 while awake; in April he had none in sleep and one while awake.
Since then, there have been no events suggestive of seizures, and he has not experienced aura-like
symptoms, automatisms, or post-event confusion. He has also not required rescue clobazam.

He describes satisfactory sleep, reduced stress at work, and consistent medication timing aided by
the pillbox and reminders. Neurological examination today is unremarkable, and there are no adverse
effects from levetiracetam. Based on the current trajectory and the absence of events, I have
advised continuation of the present regimen and adherence measures. We discussed seizure first-aid
and lifestyle precautions. He understands to contact us promptly if there is any recurrence or
change in semiology.

With best wishes,  
```

---

## Letter 15 — source_row_index=13079

### Extractions

**SF** gold=`2 per 8 month` | pred=`2 per week` | exact=✗ monthly=✗
  **med** `Levetiracetam 500 mg twice daily` status=current | ev: _He began Levetiracetam 500 mg twice daily via primary care_
  **med** `Vitamin D 1,000 IU daily` status=current | ev: _Vitamin D 1,000 IU daily (self-purchased)_
  **sz_type** `generalised tonic-clonic seizure` onset=generalized | ev: _experiencing a generalised tonic-clonic seizure_
  **sz_type** `absence seizures` onset=focal | ev: _cluster of absences_
  **inv** `MRI` result=normal | ev: _prior normal MRI_
  **inv** `EEG` result=not_stated | ev: _No prior EEGs available in our system_
  **inv** `other` result=normal | ev: _Routine bloods earlier this year were reportedly normal via GP_
  **inv** `EEG` result=pending | ev: _Arrange: routine EEG_
  **inv** `MRI` result=pending | ev: _repeat MRI brain (epilepsy protocol)_
  **inv** `other` result=pending | ev: _Blood tests via GP: FBC, U&E, LFT, bone profile, vitamin D, and Levetiracetam trough level_

### Letter text

```
KINGS NEUROSCIENCES CENTRE

Clinic Date: 02 October 2025

Dr Simon Patel
Maple Grove Health Centre

12 Maple Grove, Southwark, London SE1 4AB

Dear Dr Simon Patel

Daniel Harris, DOB: 14-05-1990, Hospital No: K918372 NHS No. 7482106395
Flat 3, 22 Larch Court, Peckham, London SE15 2NL

Summary: Ongoing seizures of uncertain classification; prior normal MRI; high caffeine intake
acknowledged.

Thank you for asking me to review Daniel Harris in clinic today. He attended alone and brought a
seizure diary. He reports historically infrequent events since last year, with improved routine and
sleep hygiene. He began Levetiracetam 500 mg twice daily via primary care after a telephone
consultation in December. He remained seizure-free for 8 months after starting Levetiracetam 500 mg
twice daily, before experiencing a generalised tonic-clonic seizure three Tuesdays ago, preceded by
a cluster of absences. He describes the absences as brief episodes of lost time with staring and no
awareness, occurring over the preceding weekend. The generalised event occurred mid-morning at work;
there was a tongue bite and post-ictal confusion for approximately 30 minutes. No injury was
sustained.

He drinks high-caffeine energy drinks (3–4 cans most weekdays) and several strong coffees daily,
particularly when working late. He acknowledges poor hydration and intermittent missed breakfasts.
Sleep is reported as 5–6 hours on weeknights with weekend catch-up. No recent intercurrent illness.
No new medications. He denies alcohol misuse or recreational drugs. There is no clear trigger other
than increased workload and caffeine. Family history unremarkable for seizures.

Investigations: He recalls an MRI head from 2019 reported as normal (no report available today). No
prior EEGs available in our system. Routine bloods earlier this year were reportedly normal via GP.

Current medication: Levetiracetam 500 mg twice daily; Vitamin D 1,000 IU daily (self-purchased). No
known drug allergies.

Adverse effects: Mild irritability in the first fortnight of Levetiracetam, settled without
intervention. No rash, diplopia, ataxia or weight change reported.

Driving and safety: We discussed DVLA requirements around seizures and the need to cease driving and
inform DVLA following the recent event; he states he has already stopped driving and will notify
DVLA. We also reviewed general safety measures at work and at home (showers rather than baths,
supervised swimming, and awareness for colleagues).

Plan:
- Continue Levetiracetam at current dose for now; adherence reinforced. We will review the seizure
diary over the next 6–8 weeks.
- Lifestyle measures: he agreed to reduce caffeine substantially, improve hydration, and regularise
sleep and meals; these were framed as patient-led goals.
- Arrange: routine EEG and repeat MRI brain (epilepsy protocol) to update baseline investigations.
- Blood tests via GP: FBC, U&E, LFT, bone profile, vitamin D, and Levetiracetam trough level for
reference.
- Nurse specialist telephone review in 4–6 weeks to assess seizure control, side effects, and
progress with caffeine reduction and sleep routine.
- Follow-up in clinic in 3 months, sooner if further events occur.

Thank you for your ongoing care of Daniel Harris. Please let me know if there are any concerns in
the interim.

Yours sincerely
```

---

## Letter 16 — source_row_index=16158

### Extractions

**SF** gold=`13 per 4 month` | pred=`2 per week` | exact=✗ monthly=✗
  **med** `Levetiracetam 500 mg twice daily` status=current | ev: _Levetiracetam 500 mg twice daily_
  **med** `Clonazepam 0.5 mg nocte` status=current | ev: _Clonazepam 0.5 mg nocte as rescue for clusters_
  **sz_type** `brief episodes of behavioural arrest with loss of awareness` onset=focal | ev: _brief episodes of behavioural arrest with loss of awareness_
  **sz_type** `bilateral stiffening and jerking` onset=focal | ev: _occasionally progressing to bilateral stiffening and jerking_
  **inv** `EEG` result=pending | ev: _Arrange urgent EEG_
  **inv** `MRI` result=pending | ev: _MRI brain with epilepsy protocol_
  **inv** `other` result=pending | ev: _Bloods today: U&E, LFT, FBC, vitamin D; Levetiracetam level if clinically indicated_

### Letter text

```
Department of Neurology 

Clinic Date: 27 September 2012 

Dr Amelia Rhodes  
South Thames Neurology Centre  
Neurology Outpatients, 14 Kingfisher Way, London SE10 3LX  

Dear Dr Amelia Rhodes,  

Emily Carter, DOB: 23-02-1986, Hospital No: H392847 NHS No. 9045127783  
Flat 5, 27 Brookfield Terrace, London, N4 2JP 

Diagnoses: 

Recurrent seizures of uncertain classification with increasing frequency and situational
sensitivity.

Current Medication: 

Levetiracetam 500 mg twice daily  
Clonazepam 0.5 mg nocte as rescue for clusters (patient-reported, used sparingly)

Plan: 

- Increase Levetiracetam to 750 mg twice daily and monitor tolerability and mood  
- Provide written seizure first-aid advice and workplace adjustments letter (to address lighting
triggers)
- Arrange urgent EEG and MRI brain with epilepsy protocol  
- Bloods today: U&E, LFT, FBC, vitamin D; Levetiracetam level if clinically indicated  
- Safety counselling: driving, machinery, heights, water, and sleep hygiene  
- Follow-up in 6 weeks or earlier if further deterioration 

I reviewed Emily Carter in clinic today following a clear deterioration in her seizure control over
recent months. She has started a new role in an open-plan office where strong and intermittently
flickering lighting is present, and she has noticed more events in that environment. As of this
month she reports 2 seizure events; two in August, 7 in July and 2 in June during both sleep and
wakefulness. Events are described as brief episodes of behavioural arrest with loss of awareness,
sometimes preceded by a rising internal sensation and flashing lights in her vision, occasionally
progressing to bilateral stiffening and jerking lasting under two minutes, with post-event confusion
and headache. There is no tongue biting or urinary incontinence reported in the majority of
episodes. Her partner has witnessed two daytime collapses at work, both temporally associated with
exposure to overhead flicker. Sleep deprivation and stress appear to exacerbate frequency.

There is no history of recent head injury, fever, or new systemic illness. She does not consume
alcohol to excess and denies recreational drug use. Adherence to current medication is good by pill
count and patient report. Neurological examination today is non-focal.

Given the pattern of escalation and the environmental trigger at the new workplace, I have
recommended an increase in Levetiracetam to 750 mg twice daily, provision of an employer letter
requesting adjustments (reduced flicker/strong light exposure, screen filters, breaks, and option to
work in a lower-stimulus area), and urgent neurophysiological and imaging reassessment. We discussed
risks related to driving and safety-critical tasks; she is aware of the current guidance and will
refrain accordingly. Written seizure first-aid information has been supplied.

I will review her in six weeks, sooner if there are further clusters, injuries, or any emergence of
mood or behavioural adverse effects. Please do not hesitate to contact me if there are concerns in
the interim.

With best wishes, 
```

---

## Letter 17 — source_row_index=9278

### Extractions

**SF** gold=`3 per week` | pred=`≤ three simple partial seizures per week` | exact=✗ monthly=✗
  **med** `Levetiracetam 500 mg bd` status=current | ev: _Levetiracetam 500 mg bd_
  **sz_type** `simple partial seizures` onset=focal | ev: _brief events characterised by a rising epigastric sensation, momentary déjà vu, and preserved awareness, occasionally fo_
  **inv** `MRI` result=normal | ev: _Normal brain MRI (January 2024)_
  **inv** `EEG` result=non_diagnostic | ev: _A routine EEG (February 2024) was non-diagnostic_

### Letter text

```
Department of Neurology

Clinic Date: 02 October 2025

Dr Hannah Keane
St Bartholomew’s Hospital
Department of Neurology, West Smithfield, London EC1A 7BE

Dear Dr Hannah Keane,

Liam Turner, DOB: 14-03-2003, Hospital No: H932774 NHS No. 4098573216
12 Alder Court, Mile End, London E3 4HT

Diagnoses:

Recurrent seizure episodes of uncertain classification (onset 2023)
Normal brain MRI (January 2024)

Current Medication:

Levetiracetam 500 mg bd

Plan:

Optimise sleep hygiene and reduce prolonged continuous screen exposure
Continue Levetiracetam 500 mg twice daily and review in 6 months
Provide seizure safety advice and sports participation guidance

I reviewed Liam Turner in clinic today. He is a university esports club lead and reports prolonged
screen time due to training, competition schedules, and event administration. He describes brief
events characterised by a rising epigastric sensation, momentary déjà vu, and preserved awareness,
occasionally followed by mild right-hand tingling without spread. He reports a frequency of ≤ three
simple partial seizures per week, usually clustering during weeks with late-night tournaments and
irregular sleep. There are no witnessed convulsions, tongue biting, or incontinence. Post-event
fatigue is mild and short-lived.

Since starting Levetiracetam 500 mg twice daily in May 2024, he notes a reduction in intensity and
duration of episodes, though frequency remains tied to sleep disruption and extended sessions at
dual monitors with high visual load. He denies mood change or irritability on current dose. No
alcohol misuse or recreational drugs. He maintains academic attendance and coaching
responsibilities.

Neurological examination today is normal. Prior MRI brain (January 2024) was reported as normal. A
routine EEG (February 2024) was non-diagnostic. We discussed the pattern of triggers, particularly
irregular sleep and prolonged continuous screen time with limited breaks. He will implement
protected sleep windows, scheduled screen breaks (every 45–60 minutes), blue-light reduction
settings in the evenings, and avoidance of overnight events where possible. He will track events
alongside sleep duration and training intensity to help correlate triggers.

I have advised continuation of Levetiracetam 500 mg twice daily. We agreed to reassess in 6 months,
earlier if there is any evolution in semiology, loss of awareness, injury, or generalisation. He has
been provided with seizure first-aid information for teammates and guidance on safe participation in
esports tournaments and travel planning. DVLA guidance was discussed with respect to awareness-
preserving events; he currently reports preserved awareness and no events at the wheel, and he does
not drive.

I would be grateful if you could continue prescribing Levetiracetam 500 mg bd. Please let me know if
there are any concerns regarding mood or adherence. I remain happy to review sooner should the
pattern change or if he wishes to consider ambulatory EEG during tournament periods.

With best wishes,
```

---

## Letter 18 — source_row_index=16356

### Extractions

**SF** gold=`1 per 4 day` | pred=`every 4 days` | exact=✗ monthly=✗
  **med** `Valproate 500 mg in the morning and 1000 mg at night` status=current | ev: _Valproate (modified-release) 500 mg in the morning and 1000 mg at night_
  **med** `Clobazam 10 mg at night as needed` status=current | ev: _Clobazam 10 mg at night as needed for clusters_
  **med** `Vitamin D3 1000 IU once daily` status=current | ev: _Vitamin D3 1000 IU once daily_
  **sz_type** `generalised epilepsy` onset=generalized | ev: _Primary generalised epilepsy_

### Letter text

```
Epilepsy Centre

Neurosciences Division


From: Dr Hannah Reid (KING'S COLLEGE HOSPITAL NHS FOUNDATION TRUST)
Sent: 02 October 2025 10:15
To: kch.neuroepilepsy@nhs.net
Cc: Dr Naveen Shah (KING'S COLLEGE HOSPITAL NHS FOUNDATION TRUST); Dr Emily Grant (KING'S COLLEGE
HOSPITAL NHS FOUNDATION TRUST)
Subject: Interval review and VNS usage update

Hi Hannah

Epilepsy Diagnosis:

Primary generalised epilepsy


Present Medication:

1. Valproate (modified-release) 500 mg in the morning and 1000 mg at night
2. Clobazam 10 mg at night as needed for clusters (per personalised plan)
3. Vitamin D3 1000 IU once daily


Present Seizure Frequency:

Seizures remain relatively stable, typically occurring in clusters every 4 days. Rescue medication
was required once in June and twice in August. The patient has increased VNS swiping, but there has
been no overall rise in seizure frequency since the last review.


Context and Patient-Reported Features:

- The patient has generalised epilepsy with occasional cluster patterns linked to sleep loss,
particularly after late shifts or long-haul travel.
- A personalised plan for cluster management is documented elsewhere and remains unchanged; the
patient is familiar with when to initiate the rescue protocol and when to present to emergency
services.
- Vagus nerve stimulator in situ since 2023; the patient reports more frequent magnet swiping at
aura onset and during early cluster periods. No adverse effects beyond transient voice change.
Battery status checked at last device clinic: satisfactory.
- No recent hospital admissions. Headaches post-cluster respond to simple analgesia and hydration.
- The patient is exploring sleep hygiene strategies (fixed bedtime, reduction of caffeine after
midday) and has begun using a sleep diary to identify triggers.


Plan of Action:

- Continue current anti-seizure regimen without dose changes at this time, given stable overall
frequency and effective use of the personalised rescue plan.
- Reinforce sleep optimisation and adherence to the personalised plan. Patient to maintain seizure
and sleep diary to better delineate the relationship with sleep loss and cluster timing.
- No change to VNS parameters today; continue magnet use at aura onset and during clusters as per
training. Next VNS device check at routine device clinic in 3 months or sooner if concerns.
- Safety advice reiterated regarding water precautions, heights, and operating machinery. The
patient confirms understanding and has support at home.
- Follow-up in 4 months, or earlier if there is any increase in seizure severity, prolonged
clusters, adverse effects, or concerns about VNS function.

With best wishes
```

---

## Letter 19 — source_row_index=16036

### Extractions

**SF** gold=`13 per 2 month` | pred=`increasing` | exact=✗ monthly=✗
  **med** `Carbamazepine 400 mg twice daily` status=current | ev: _Carbamazepine modified‑release 400 mg twice daily_
  **med** `Levetiracetam 750 mg twice daily` status=current | ev: _Levetiracetam 750 mg twice daily_
  **med** `Lacosamide 50 mg at night` status=planned | ev: _Begin lacosamide 50 mg at night for one week_
  **sz_type** `seizures during sleep` onset=unknown | ev: _In Feb he had four seizures during sleep_
  **sz_type** `seizures while awake` onset=unknown | ev: _3 while awake_

### Letter text

```
Epilepsy Centre

Neurosciences Division

From: Dr Emily Carter (KING'S COLLEGE HOSPITAL NHS FOUNDATION TRUST)
Sent: 14 April 2015 10:22
To: epilepsy.clinic@nhs.net
Cc: Dr Ravi Shah (KING'S COLLEGE HOSPITAL NHS FOUNDATION TRUST); Dr Helen Brooks (KING'S COLLEGE
HOSPITAL NHS FOUNDATION TRUST)
Subject: Worsening seizures, medication review and safety advice

Dear Emily,

Summary and current concerns:
I reviewed Sam in clinic today. Over the last two months his seizure control has clearly
deteriorated. He reports increasing social pressures at work and more frequent evenings out, with
higher alcohol exposure than previously, which he recognises often precedes poor sleep and clusters
of events.

Seizure history and current frequency:
He keeps a diary. In Feb he had four seizures during sleep and 3 while awake. In Mar he had 4 in
sleep and 2 while awake. Prior to this, he had gone several months with only occasional brief
episodes, typically after late nights.

Current medicines:
- Carbamazepine modified‑release 400 mg twice daily
- Levetiracetam 750 mg twice daily

Previous medicines (patient‑reported):
- Lamotrigine up to 100 mg twice daily (stopped in 2014 due to rash)
- Sodium valproate 500 mg twice daily (self‑discontinued in 2013 because of weight gain and tremor)

Examination and collateral:
Neurological examination today was unremarkable. Mood is strained; he reports sleep restriction,
variable adherence when out socially, and alcohol intake most weekends. No new focal neurological
symptoms between events.

Assessment:
Sam’s seizure burden has increased in the context of heightened social stressors, reduced sleep,
variable adherence, and increased alcohol exposure. He feels the recent uptitration of levetiracetam
may have coincided with more frequent events and irritability, though this is confounded by
lifestyle factors. There is no single reliable non‑medication trigger identified beyond alcohol and
sleep loss.

Plan:
- Medication: Maintain carbamazepine MR 400 mg twice daily for now. Reduce levetiracetam to 500 mg
twice daily over one week to assess for behavioural side effects while monitoring seizure frequency.
Begin lacosamide 50 mg at night for one week, then 50 mg twice daily ongoing. If tolerated and
seizures remain frequent, we will consider further titration at the next review.
- Safety and lifestyle: Strongly advised strict alcohol moderation/avoidance, consistent sleep
schedule, and adherence with dosing alarms. Discussed interim driving and safety precautions given
recent events, including avoiding swimming alone, working at heights, and operating machinery.
- Monitoring: Sam will continue his seizure diary, noting alcohol, sleep duration, and doses taken.
We will check U&E/LFTs in four weeks and review in clinic in eight weeks, sooner if events escalate.

I will update you after the medication adjustment period. Please contact me if there are concerns
before then.

With best wishes,
```

---

## Letter 20 — source_row_index=665

### Extractions

**SF** gold=`2 per 2 week` | pred=`twice every two weeks` | exact=✗ monthly=✗
  **med** `Levetiracetam 750 mg twice daily` status=current | ev: _Medication: Levetiracetam 750 mg twice daily._
  **med** `Lamotrigine 100 mg twice daily` status=current | ev: _Medication: Lamotrigine 100 mg twice daily._
  **med** `Sumatriptan 50 mg as required` status=current | ev: _Sumatriptan 50 mg as required for migraine_
  **med** `Sertraline 50 mg once daily` status=current | ev: _Sertraline 50 mg once daily._
  **sz_type** `brief events with preserved awareness` onset=focal | ev: _Episodes are described as brief events with preserved awareness followed by fatigue and mild headache_
  **inv** `other` result=normal | ev: _Routine bloods (FBC, U&E, LFTs) from August 2025 were within normal limits._
  **inv** `other` result=not_stated | ev: _Lamotrigine and levetiracetam levels not checked recently._
  **inv** `MRI` result=normal | ev: _MRI brain (2023) unchanged from prior imaging; no acute pathology._
  **inv** `EEG` result=non_diagnostic | ev: _EEG (2022) was non-specific; no clear epileptiform discharges captured._

### Letter text

```
University College Hospital 

National Hospital for Neurology and Neurosurgery 

Clinic Date: 02 October 2025 

Dr Alicia Morton  
Riverside Medical Practice  
12 Wharf Street, London SE8 3DR  

Dear Dr Alicia Morton,  

Jordan Ellis, DOB: 22-07-1989, Hospital No: U918273 NHS No. 3049185562  
Flat 5, 28 Fairview Road, London N7 8HP 

Summary/ Diagnoses: Epilepsy with ongoing seizures; history of migraine; mild anxiety symptoms; no
known drug allergies; lives with partner; non-smoker; minimal alcohol intake.

Medication: Levetiracetam 750 mg twice daily.  
Lamotrigine 100 mg twice daily.  
Sumatriptan 50 mg as required for migraine (max 2 doses in 24 hours).  
Sertraline 50 mg once daily. 

I reviewed Jordan Ellis in clinic today. They attended alone and provided data from a seizure diary
app, which they have been using consistently for the past four months. The app includes timestamped
entries, short free-text descriptions, and prompts for potential triggers. The patient reports good
adherence to medication with no recent missed doses. Sleep remains irregular due to shift work, and
they are working with their employer to stabilise schedules. No recent head injuries, intercurrent
illness, or new medications. Appetite is normal, and weight is stable.

Seizures: The app logs indicate a regular pattern of seizures twice every two weeks, typically
clustering on days following consecutive late shifts. Episodes are described as brief events with
preserved awareness followed by fatigue and mild headache; there have been no injuries, tongue
biting, or incontinence reported. Partners’ observations, entered into the app on shared entries,
corroborate the timing and brief duration. No rescue medication has been required. The patient’s
last emergency department attendance for a seizure-related event was over a year ago.

Examination: Alert and oriented. Speech fluent. Cranial nerves intact. No focal neurological
deficits. Gait normal. Cardiovascular and respiratory examinations unremarkable.

Investigations: 
- Routine bloods (FBC, U&E, LFTs) from August 2025 were within normal limits.  
- Lamotrigine and levetiracetam levels not checked recently.  
- MRI brain (2023) unchanged from prior imaging; no acute pathology.  
- EEG (2022) was non-specific; no clear epileptiform discharges captured. 

Plan: 
- Continue current anti-seizure medications unchanged for now.  
- Request trough levels for lamotrigine and levetiracetam at the GP practice to assess for
subtherapeutic range in the context of ongoing events.
- Encourage ongoing seizure diary app use; patient to enable automatic export so we can review
monthly trends.
- Provide fit note advice as needed; patient to avoid working consecutive late shifts if possible
and to discuss reasonable adjustments with occupational health.
- Standard safety counselling reinforced (showers rather than baths, avoid heights, cook with
caution).
- Follow-up in clinic in 4 months, or sooner if there is an increase beyond the current pattern of
seizures twice every two weeks or any event associated with injury or loss of awareness.

Yours sincerely
```

---

## Letter 21 — source_row_index=1165

### Extractions

**SF** gold=`5 to 7 per 3 week` | pred=`unknown` | exact=✗ monthly=✗

### Letter text

```
University College Hospital

National Hospital for Neurology and Neurosurgery

Clinic Date: 20 November 2021

Dr Susan
University College Hospital
National Hospital for Neurology and Neurosurgery, London WC1N 3BG

Dear Dr Susan,

William Harris, DOB: 15-02-1965, Hospital No: H563829 NHS No. 9273645810
10 Meadow Park, London, EC1V 9BT

Summary/Diagnoses: Focal epilepsy with impaired awareness; history of traumatic brain injury;
travel-related anxiety; osteoporosis; former alcohol dependence (in sustained remission);
hypertension; hyperlipidaemia. Currently residing in supported accommodation. Smoker.

Medication: Levetiracetam 1000 mg twice daily; Carbamazepine (Tegretol Retard) 400 mg twice daily;
Topiramate 75 mg morning and 100 mg evening; Atorvastatin 20 mg once daily; Lansoprazole 30 mg once
daily; Bisoprolol 5 mg once daily; Ramipril 5 mg once daily; Thiamine 100 mg once daily; Vitamin B
compound strong one tablet daily; Calcium/Vitamin D supplements; Carbocisteine 750 mg twice daily;
Emollients as required.

I reviewed Bill in clinic today, accompanied by his key worker from the residence. He remains
engaged with routines and reports improved appetite. He uses a single-point stick outdoors and is
independent indoors. No recent falls. Sleep has improved since a change to a quieter room. He
continues to abstain from alcohol and attends weekly wellbeing sessions.

Focal epilepsy: Bill describes stereotyped focal impaired-awareness episodes featuring a rising
epigastric sensation, brief arrest of speech, right facial pulling, and post-event confusion for
several minutes. Importantly, he and staff document 5 or 7 focal onset seizures in three weeks
during a recent period that included an episode while travelling by air. He links this cluster to
marked anticipatory and in-flight anxiety, sleep disruption the night before travel, and missed
hydration. Outside that three‑week window, there have been no further episodes for the last six
weeks. There has been no secondary generalisation, tongue biting, or injuries. No clear intercurrent
infection. Medication adherence is generally good; one evening dose of levetiracetam may have been
late on the day of outbound travel.

Travel context: Bill acknowledges travel anxiety, particularly around security checks and take-off.
He is open to structured preparation and timing medication around flight schedules. No panic attacks
outside travel.

Examination: Afebrile, BP 132/78 mmHg, pulse 66 bpm regular. Neurological exam unchanged: mild
increased tone right upper limb, subtle right pronator drift, gait slightly wide-based but safe with
stick. No focal tenderness; feet intact, no callosities today. Cognition stable to brief screening;
orientation preserved.

Plan:
- Diagnosis reaffirmed as focal epilepsy. Maintain current anti-seizure regimen without dose change,
given six seizure-free weeks following the travel-related cluster.
- Provide a written travel plan: ensure adherence with doses timed to flight schedule, maintain
sleep the night before, regular hydration, and avoidance of excess caffeine. Airport letter supplied
to carry medicines in hand luggage.
- Offer brief anxiety management strategies and signpost to primary care for short-term
psychological support focused on travel anxiety.
- Safety advice reinforced: no swimming unsupervised, avoid heights, and comply with DVLA
guidance—he is not driving.
- Bloods: request U&E, LFT, FBC, vitamin D, and carbamazepine level via practice in the next two
weeks.
- Bone health: continue calcium/vitamin D; DEXA recheck due next year.
- Follow-up: neurology clinic in 6 months, sooner if further clusters or any generalised tonic-
clonic seizure.

Yours sincerely,
```

---

## Letter 22 — source_row_index=10967

### Extractions

**SF** gold=`3 cluster per month, 4 to 5 per cluster` | pred=`3 per month` | exact=✗ monthly=✗
  **med** `Levetiracetam 1,000 mg twice daily` status=current | ev: _Continue current anti-seizure medicines: Levetiracetam 1,000 mg twice daily_
  **med** `Lacosamide 100 mg twice daily` status=current | ev: _and Lacosamide 100 mg twice daily_
  **sz_type** `nocturnal clusters` onset=focal | ev: _three nocturnal clusters this month; each ~ 4 - 5 events. These are brief, stereotyped episodes occurring typically betw_
  **inv** `MRI` result=normal | ev: _Prior MRI brain (2024) unremarkable_
  **inv** `EEG` result=non_diagnostic | ev: _Routine EEG (2024) non-diagnostic_
  **inv** `other` result=normal | ev: _Baseline bloods (June 2025) normal apart from mild iron deficiency now treated_
  **inv** `EEG` result=pending | ev: _Ambulatory home EEG has been requested to better capture nocturnal events and correlate with the diary; awaiting schedul_

### Letter text

```
Centre for Epilepsy

Neurosciences Division 

Clinic Date: 02 October 2025 

Dr Sarah Coleman 
Consultant Neurologist  
Centre for Epilepsy  
King’s College Hospital, Denmark Hill, London SE5 9RS  

Dear Dr Sarah Coleman, 

Alex Turner, DOB: 22-08-1992, Hospital No: K847392 NHS No. 1039485726  
Flat 12, 4 Brookfield Road, London, N16 7HF  

Diagnosis: 

Recurrent unprovoked seizures; phenotype under ongoing evaluation

Aetiology: 

No clear structural, metabolic, or genetic cause identified to date

Other Medical Problems: 

Generalised anxiety symptoms under community psychological support; mild iron-deficiency anaemia
treated with oral ferrous fumarate

Management Plan: 

Continue current anti-seizure medicines: Levetiracetam 1,000 mg twice daily and Lacosamide 100 mg
twice daily. Maintain single-brand supply for both. Arrange serum levels and U&Es/LFTs prior to next
review. Safety advice reinforced around nocturnal events and supervision overnight when feasible.
Sleep hygiene and regular routines encouraged. Continue seizure and mood diary. Review in three
months, sooner if escalation occurs.

History and Progress: 

Since the last appointment, the patient reports three nocturnal clusters this month; each ~4 - 5
events. These are brief, stereotyped episodes occurring typically between 02:00 and 04:00, with
rapid post-event reorientation. No clear daytime events were reported. The patient notes prodromal
mood change and irritability for 12–24 hours prior to some clusters and has been tracking this in a
diary, which shows a temporal association with sleep deprivation and increased work-related stress.
No new head injuries, intercurrent infections, or alcohol binges reported.

Medication Tolerability and Past Treatments: 

Previously trialled Carbamazepine (dizziness and diplopia at therapeutic doses) and Topiramate
(word-finding difficulties and paraesthesia), both discontinued. Currently tolerating Levetiracetam
and Lacosamide with manageable irritability that appears to fluctuate with sleep and stress rather
than dose changes. No rash, hyponatraemia symptoms, or weight loss reported. Adherence reported as
good; pharmacy records corroborate on monthly collection.

Investigations: 

Prior MRI brain (2024) unremarkable. Routine EEG (2024) non-diagnostic. Ambulatory home EEG has been
requested to better capture nocturnal events and correlate with the diary; awaiting scheduling.
Baseline bloods (June 2025) normal apart from mild iron deficiency now treated.

Lifestyle and Safety: 

We discussed SUDEP and general safety; the patient uses a phone-based seizure alert app at night and
has arranged for a family member to check in when clusters occur. Driving remains not applicable as
the patient does not hold a licence. Work arrangements have been modified to avoid night shifts and
mitigate sleep loss.

Plan Summary: 

- Continue Levetiracetam 1,000 mg BD and Lacosamide 100 mg BD (single-brand).  
- Pre-clinic bloods: FBC, U&Es, LFTs, Levetiracetam and Lacosamide levels.  
- Proceed with ambulatory EEG to characterise nocturnal clusters.  
- Maintain detailed seizure and mood/sleep diary; bring to next review.  
- Review in three months in clinic; earlier contact if frequency increases or injuries occur. 

Yours sincerely
```

---

## Letter 23 — source_row_index=280

### Extractions

**SF** gold=`multiple per day` | pred=`multiple seizures in past day` | exact=✗ monthly=✗
  **med** `Levetiracetam 1 g b.d.` status=current | ev: _He is currently taking Levetiracetam 1 g b.d._
  **med** `Clobazam 10 mg nocte` status=current | ev: _and Clobazam 10 mg nocte_
  **sz_type** `brief episodes of loss of awareness with post-event confusion and marked fatigue` onset=focal | ev: _described by him and his partner as brief episodes of loss of awareness with post-event confusion and marked fatigue_
  **sz_type** `near-miss episodes` onset=focal | ev: _several near-miss episodes over the preceding week, including sudden staring and unresponsiveness lasting under a minute_
  **inv** `EEG` result=pending | ev: _I have arranged urgent ambulatory EEG within the next 1–2 weeks_
  **inv** `other` result=pending | ev: _will request updated serum drug levels and routine bloods (U&E, LFT, FBC)_

### Letter text

```
KINGS NEUROSCIENCES CENTRE


Clinic Date: 11 December 2015 

Dr Anita Shah
Riverside Medical Practice

12 Riverside Way, London, SE1 9ZZ
Dear Dr Anita Shah
Michael Carter, DOB: 21-11-1982, Hospital No: M827461 NHS No. 8845123367
Flat 4, 29 Millstream Court, London, SE16 3LP 

I reviewed the above patient in the Neurology Clinic today. Since his last appointment there has
been a notable deterioration in his condition. He reports recent job loss from his banking role,
with associated stress and disrupted sleep patterns over several weeks. In the 24 hours prior to
clinic he experienced multiple seizures in past day, described by him and his partner as brief
episodes of loss of awareness with post-event confusion and marked fatigue. He also reports several
near-miss episodes over the preceding week, including sudden staring and unresponsiveness lasting
under a minute, followed by headaches and irritability.

He is currently taking Levetiracetam 1 g b.d. and Clobazam 10 mg nocte, both of which he states he
has taken regularly. He denies missed doses but admits that sleep fragmentation and early waking
have worsened his daytime somnolence and concentration. He also notes increased anxiety since
becoming unemployed, with occasional palpitations and a sense of impending events before the
episodes. There have been no clear triggers such as intercurrent infection or alcohol excess, though
caffeine intake has risen. No injuries were reported, but there is concern from family regarding
safety at home given the recent escalation.

On examination today he was alert and oriented with normal speech and cranial nerves. Motor and
coordination were intact; no focal neurological deficits were identified. Cardiovascular and
respiratory examinations were unremarkable. BP in clinic was mildly elevated, likely stress-related.

Given the clinical picture and the clear pattern of worsening events temporally associated with
stress and sleep disruption, I have advised close observation and prompt contact if events cluster
or if any convulsive episodes occur. I have arranged urgent ambulatory EEG within the next 1–2 weeks
and will request updated serum drug levels and routine bloods (U&E, LFT, FBC). He has been provided
seizure first-aid guidance for his partner and we discussed practical risk mitigation at home. He is
aware of the DVLA guidance and understands he should not drive. I will review him in an expedited
follow-up once the ambulatory EEG is completed.

Yours sincerely
```

---

## Letter 24 — source_row_index=7708

### Extractions

**SF** gold=`seizure free for multiple month` | pred=`unknown` | exact=✗ monthly=✗
  **sz_type** `focal epilepsy` onset=focal | ev: _history consistent with focal epilepsy_
  **sz_type** `brief episodes of behavioural arrest with automatisms and post‑event confusion lasting a few minutes` onset=focal | ev: _characterised previously by brief episodes of behavioural arrest with automatisms and post‑event confusion lasting a few_
  **inv** `MRI` result=normal | ev: _prior MRI unremarkable_
  **inv** `EEG` result=normal | ev: _interictal EEG previously normal_
  **inv** `EEG` result=pending | ev: _Should any breakthrough focal events occur, we would reconsider pharmacological options and repeat EEG. Routine bloods (_

### Letter text

```
Department of Neurology

Clinic Date: 15 January 2019

Dr Eleanor Hughes
St Cuthbert Neurology Centre
Neurology Outpatients, 12 Morley Lane, Leeds LS2 8AB

Dear Dr Eleanor Hughes,

Michael Turner, DOB: 03-02-1991, Hospital No: L937520 NHS No. 9054312768
22 Brookside Close, Leeds, LS7 3HT

Diagnoses:

Focal epilepsy with impaired awareness seizures; prior MRI unremarkable; interictal EEG previously
normal.

Current Management:

Ketogenic/modified diet (supervised by an external specialist dietetic team); diet details recorded
in notes. No regular anti-seizure medicines at present.

Plan:

Continue current dietary therapy with ongoing external dietetic supervision and ensure copies of
dietary reviews are shared with our service. Safety advice reinforced. Routine bloods (lipid
profile, liver function, bicarbonate) via GP every 6 months while on diet. Review in neurology
clinic in 12 months, or sooner if events recur or dietary intolerance emerges.

I reviewed Michael Turner in clinic today. He reports a history consistent with focal epilepsy,
characterised previously by brief episodes of behavioural arrest with automatisms and post‑event
confusion lasting a few minutes. He has been following a clinician‑supervised ketogenic/modified
diet for several months; the dietary protocol and ratios have been documented in the medical record.
Since adopting the diet, he describes that seizure occurrences have not been happening, and there
have been no witnessed episodes by family or colleagues. He denies new neurological symptoms. Sleep
and hydration are reported as stable. He is not currently taking lamotrigine or other anti‑seizure
medicines.

On examination today he was well, with normal neurological findings. We discussed ongoing safety
measures, driving regulations where applicable, and the importance of maintaining meticulous dietary
adherence and regular monitoring while on this therapy. I have asked that the external dietetic team
continue to supervise macronutrient ratios and provide periodic summaries for our records. Should
any breakthrough focal events occur, we would reconsider pharmacological options and repeat EEG.

I have arranged follow‑up in 12 months. He may contact the clinic earlier if there is any change in
seizure pattern, adverse effects from the diet, or other concerns.

With best wishes,
```

---

## Letter 25 — source_row_index=4003

### Extractions

**SF** gold=`1 per month` | pred=`abs monthly` | exact=✗ monthly=✗
  **med** `ramipril` status=current | ev: _medications include ramipril_
  **med** `vitamin D` status=current | ev: _medications include ... vitamin D_
  **sz_type** `episodes characterised by a brief prodrome of tightness across the chest, a rising internal "surge", and an abrupt loss of awareness` onset=unknown | ev: _episodes characterised by a brief prodrome of tightness across the chest, a rising internal "surge", and an abrupt loss _
  **sz_type** `bilateral hand fumbling and a brief vocalisation` onset=unknown | ev: _bilateral hand fumbling and a brief vocalisation_
  **inv** `EEG` result=normal | ev: _routine EEG one year ago reportedly normal_
  **inv** `MRI` result=normal | ev: _MRI brain without contrast five years ago ... was described as normal_
  **inv** `video_EEG` result=pending | ev: _prolonged EEG monitoring with home ambulatory recording as a first step, followed by inpatient video-EEG if required_
  **inv** `MRI` result=pending | ev: _arrange an MRI brain with epilepsy protocol_
  **inv** `other` result=pending | ev: _requested thyroid function and metabolic profile_

### Letter text

```
King's College Hospital 

Department of Neurosciences 

Clinic Date: 22 November 2024 

Dr Priya Nair
Consultant Neurologist  
King's College Hospital  
Department of Neurosciences, King's College Hospital, London SE5 9RS  

Dear Dr Priya Nair
Consultant Neurologist,  

Daniel Fraser, DOB: 14-03-1986, Hospital No: KCH928374 NHS No. 9432175609  
12 Brookfield Close, London, SE15 3QA

Thank you for asking me to assess this patient, who attended today with his partner. He reports
intermittent episodes over several years characterised by a brief prodrome of tightness across the
chest, a rising internal "surge", and an abrupt loss of awareness witnessed by his partner. On most
occasions there is bilateral hand fumbling and a brief vocalisation. He does not recall the episodes
and is usually confused for 10–15 minutes afterwards, occasionally with a dull bifrontal headache.
He denies tongue biting or incontinence. There is no clear motor convulsion described. He keeps a
diary and, based on this, the episodes are now occurring abs monthly, with intervening weeks free of
events. He links recent clustering to periods of poor sleep and heavy workload.

Of note, he acknowledges high caffeine intake. He typically consumes four to five large coffees by
midday and often an energy drink during late meetings. He and his partner have noticed that on days
with very high caffeine use and reduced sleep, he feels more jittery and has experienced the
prodromal "surge" without progression on two occasions. He has reduced alcohol substantially and
reports no recreational drug use. He does not drive. There is no family history of similar episodes.
He had a normal birth and development and no history of significant head injury or CNS infection.
His medications include ramipril for hypertension and vitamin D. He is not on any antiseizure
medication currently.

Previous investigations: routine EEG one year ago reportedly normal; MRI brain without contrast five
years ago for headaches was described as normal. I have not yet reviewed the original images or
tracings. Cardiovascular review is unremarkable; no syncope, palpitations, or exertional chest pain.
Neurological examination today was normal, including cranial nerves, motor, coordination, and gait.
Mood appears generally stable; he describes situational anxiety around work deadlines but no
persistent low mood, psychotic features, or panic attacks. Sleep is fragmented during busy periods
(often <6 hours).

Overall, there are paroxysmal episodes with impaired awareness and post-event confusion. The
semiology is not sufficiently specific to assign a definitive classification at this stage. Given
the current pattern abs monthly, further characterisation is required to guide management and risk
counselling. I have discussed prolonged EEG monitoring with home ambulatory recording as a first
step, followed by inpatient video-EEG if required. He is agreeable to this plan. I will also arrange
an MRI brain with epilepsy protocol to ensure high-resolution temporal lobe coverage, and I have
requested thyroid function and metabolic profile via his GP to exclude contributory systemic
factors.

In discussion, he independently raised concern about his caffeine habits. He will keep a simple log
of daily caffeine amounts and sleep duration alongside his existing event diary so that we can
correlate potential precipitants with episodes. We have also provided standard seizure first-aid
information to his partner. No treatment changes were initiated today pending further data.

I will review him in clinic after the ambulatory EEG and MRI have been completed and will update you
with the outcomes. Please let me know if there are interim concerns or if additional information
from prior investigations becomes available.

Yours sincerely
```

---
