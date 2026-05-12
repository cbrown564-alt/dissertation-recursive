// ── LocalStorage persistence ────────────────────────────────────────────────

const STORAGE_KEY = (letterId) => `exect_annotations_${letterId}`;

export function loadAnnotations(letterId) {
  try {
    const raw = localStorage.getItem(STORAGE_KEY(letterId));
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function saveAnnotations(letterId, annotations) {
  try {
    localStorage.setItem(STORAGE_KEY(letterId), JSON.stringify(annotations));
  } catch {
    // ignore
  }
}

export function clearAnnotations(letterId) {
  localStorage.removeItem(STORAGE_KEY(letterId));
}

// ── Selection offsets ───────────────────────────────────────────────────────

export function getSelectionOffsets(container) {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0) return null;
  const range = selection.getRangeAt(0);

  if (!container.contains(range.commonAncestorContainer)) return null;
  const text = selection.toString();
  if (!text || text.trim().length === 0) return null;

  const preRange = document.createRange();
  preRange.selectNodeContents(container);
  preRange.setEnd(range.startContainer, range.startOffset);
  const start = preRange.toString().length;
  const end = start + text.length;

  // Clamp to container text length
  const containerText = container.textContent || "";
  if (start < 0 || end > containerText.length) return null;

  return { start, end, text: text };
}

// ── Scoring ─────────────────────────────────────────────────────────────────

function computeIoU(aStart, aEnd, bStart, bEnd) {
  const interStart = Math.max(aStart, bStart);
  const interEnd = Math.min(aEnd, bEnd);
  const inter = Math.max(0, interEnd - interStart);
  const union = (aEnd - aStart) + (bEnd - bStart) - inter;
  return union > 0 ? inter / union : 0;
}

function compareAttributes(userAttrs = {}, goldAttrs = {}) {
  const keys = new Set([
    ...Object.keys(userAttrs),
    ...Object.keys(goldAttrs),
  ]);
  if (keys.size === 0) return 1;
  let matches = 0;
  let checked = 0;
  for (const k of keys) {
    // Skip CUI and CUIPhrase for scoring — too granular
    if (k === "CUI" || k === "CUIPhrase") continue;
    checked++;
    const u = String(userAttrs[k] ?? "").toLowerCase().trim();
    const g = String(goldAttrs[k] ?? "").toLowerCase().trim();
    if (u === g) matches++;
  }
  return checked > 0 ? matches / checked : 1;
}

export function scoreAnnotations(userEntities, goldEntities) {
  const allTypes = new Set([
    ...userEntities.map((e) => e.type),
    ...goldEntities.map((e) => e.type),
  ]);

  const byType = {};
  let totalSpanTP = 0,
    totalSpanFP = 0,
    totalSpanFN = 0;
  let fullTP = 0,
    fullFP = 0,
    fullFN = 0;

  for (const type of allTypes) {
    const user = userEntities.filter((e) => e.type === type);
    const gold = goldEntities.filter((e) => e.type === type);

    const matched = [];
    const unmatchedUser = [];
    const unmatchedGold = [...gold];

    for (const u of user) {
      let bestMatch = null;
      let bestIoU = 0;
      for (const g of unmatchedGold) {
        const iou = computeIoU(u.start, u.end, g.start, g.end);
        if (iou > bestIoU) {
          bestIoU = iou;
          bestMatch = g;
        }
      }
      if (bestIoU >= 0.5) {
        matched.push({ user: u, gold: bestMatch, iou: bestIoU });
        unmatchedGold = unmatchedGold.filter((g) => g !== bestMatch);
      } else {
        unmatchedUser.push(u);
      }
    }

    let attrMatches = 0;
    for (const m of matched) {
      const score = compareAttributes(m.user.attributes, m.gold.attributes);
      if (score >= 0.5) attrMatches++;
    }

    const spanTP = matched.length;
    const spanFP = unmatchedUser.length;
    const spanFN = unmatchedGold.length;

    totalSpanTP += spanTP;
    totalSpanFP += spanFP;
    totalSpanFN += spanFN;
    fullTP += attrMatches;
    fullFP += spanFP + (matched.length - attrMatches);
    fullFN += spanFN + (matched.length - attrMatches);

    byType[type] = {
      spanTP,
      spanFP,
      spanFN,
      fullTP: attrMatches,
      fullFP: spanFP + (matched.length - attrMatches),
      fullFN: spanFN + (matched.length - attrMatches),
      matches: matched,
      falsePositives: unmatchedUser,
      falseNegatives: unmatchedGold,
    };
  }

  const spanPrecision =
    totalSpanTP + totalSpanFP > 0 ? totalSpanTP / (totalSpanTP + totalSpanFP) : 0;
  const spanRecall =
    totalSpanTP + totalSpanFN > 0 ? totalSpanTP / (totalSpanTP + totalSpanFN) : 0;
  const spanF1 =
    spanPrecision + spanRecall > 0
      ? (2 * spanPrecision * spanRecall) / (spanPrecision + spanRecall)
      : 0;

  const fullPrecision = fullTP + fullFP > 0 ? fullTP / (fullTP + fullFP) : 0;
  const fullRecall = fullTP + fullFN > 0 ? fullTP / (fullTP + fullFN) : 0;
  const fullF1 =
    fullPrecision + fullRecall > 0
      ? (2 * fullPrecision * fullRecall) / (fullPrecision + fullRecall)
      : 0;

  return {
    byType,
    overall: {
      spanPrecision,
      spanRecall,
      spanF1,
      fullPrecision,
      fullRecall,
      fullF1,
    },
  };
}

// ── Attribute schemas ───────────────────────────────────────────────────────

export const ENTITY_SCHEMAS = {
  Diagnosis: {
    fields: [
      { key: "DiagCategory", label: "Category", type: "select", options: ["Epilepsy", "SingleSeizure", "MultipleSeizures"] },
      { key: "Certainty", label: "Certainty", type: "select", options: ["1", "2", "3", "4", "5"] },
      { key: "Negation", label: "Negation", type: "select", options: ["Affirmed", "Negated"] },
    ],
  },
  Prescription: {
    fields: [
      { key: "DrugName", label: "Drug Name", type: "text" },
      { key: "DrugDose", label: "Dose", type: "text" },
      { key: "DoseUnit", label: "Unit", type: "select", options: ["mg", "g", "ml", "mcg"] },
      { key: "Frequency", label: "Frequency", type: "text", placeholder: "e.g. 2, twice daily, As required" },
    ],
  },
  SeizureFrequency: {
    fields: [
      { key: "NumberOfSeizures", label: "Number", type: "text" },
      { key: "LowerNumberOfSeizures", label: "Lower", type: "text" },
      { key: "UpperNumberOfSeizures", label: "Upper", type: "text" },
      { key: "TimePeriod", label: "Period", type: "select", options: ["Week", "Month", "Year", "Day"] },
      { key: "NumberOfTimePeriods", label: "Period Count", type: "text" },
      { key: "YearDate", label: "Year", type: "text" },
      { key: "TimeSince_or_TimeOfEvent", label: "Time Relation", type: "select", options: ["During", "Since", "Before"] },
    ],
  },
  PatientHistory: {
    fields: [
      { key: "YearDate", label: "Year", type: "text" },
      { key: "Certainty", label: "Certainty", type: "select", options: ["1", "2", "3", "4", "5"] },
      { key: "Negation", label: "Negation", type: "select", options: ["Affirmed", "Negated"] },
    ],
  },
  Investigations: {
    fields: [
      { key: "CT_Performed", label: "CT Performed", type: "select", options: ["Yes", "No"] },
      { key: "CT_Results", label: "CT Results", type: "select", options: ["Normal", "Abnormal"] },
      { key: "MRI_Performed", label: "MRI Performed", type: "select", options: ["Yes", "No"] },
      { key: "MRI_Results", label: "MRI Results", type: "select", options: ["Normal", "Abnormal"] },
      { key: "EEG_Performed", label: "EEG Performed", type: "select", options: ["Yes", "No"] },
      { key: "EEG_Results", label: "EEG Results", type: "select", options: ["Normal", "Abnormal"] },
    ],
  },
  BirthHistory: {
    fields: [
      { key: "Certainty", label: "Certainty", type: "select", options: ["1", "2", "3", "4", "5"] },
      { key: "Negation", label: "Negation", type: "select", options: ["Affirmed", "Negated"] },
    ],
  },
  Onset: {
    fields: [
      { key: "YearDate", label: "Year", type: "text" },
      { key: "Certainty", label: "Certainty", type: "select", options: ["1", "2", "3", "4", "5"] },
    ],
  },
  EpilepsyCause: {
    fields: [
      { key: "Certainty", label: "Certainty", type: "select", options: ["1", "2", "3", "4", "5"] },
    ],
  },
  WhenDiagnosed: {
    fields: [
      { key: "YearDate", label: "Year", type: "text" },
      { key: "Certainty", label: "Certainty", type: "select", options: ["1", "2", "3", "4", "5"] },
    ],
  },
};

// ── Text segment builder (shared with ReaderView) ───────────────────────────

export function buildSegments(text, entities) {
  if (entities.length === 0) {
    return [{ start: 0, end: text.length, text, entities: [] }];
  }
  const breaks = new Set([0, text.length]);
  entities.forEach((e) => {
    breaks.add(e.start);
    breaks.add(e.end);
  });
  const sortedBreaks = Array.from(breaks).sort((a, b) => a - b);
  const segments = [];
  for (let i = 0; i < sortedBreaks.length - 1; i++) {
    const s = sortedBreaks[i];
    const e = sortedBreaks[i + 1];
    if (s === e) continue;
    const segText = text.slice(s, e);
    const segEntities = entities.filter((ent) => ent.start <= s && ent.end >= e);
    segments.push({ start: s, end: e, text: segText, entities: segEntities });
  }
  return segments;
}
