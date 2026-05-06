export const SYSTEM_COLORS = { S2: "#58a6ff", E2: "#3fb950", E3: "#d29922" };

export function pct(value, options = {}) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "n/a";
  const n = Number(value);
  const sign = options.signed && n > 0 ? "+" : "";
  const dec = options.decimals ?? 1;
  return `${sign}${(n * 100).toFixed(dec)}%`;
}

export function ms(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "n/a";
  return `${Number(value).toFixed(1)} ms`;
}

export function clamp(value, min = 0, max = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 0;
  return Math.max(min, Math.min(max, Number(value)));
}

export function heat(value) {
  if (value === null || value === undefined) return "transparent";
  const v = clamp(value);
  if (v >= 0.95) return "rgba(63,185,80,0.22)";
  if (v >= 0.85) return "rgba(88,166,255,0.18)";
  if (v >= 0.75) return "rgba(210,153,34,0.20)";
  return "rgba(248,81,73,0.20)";
}

export function shortPert(value) {
  return String(value)
    .replace("reordered_sections", "reordered")
    .replace("removed_headings", "headings")
    .replace("bullets_to_prose", "bullets")
    .replace("historical_medication_trap", "hist. med")
    .replace("planned_medication_trap", "plan. med")
    .replace("family_history_trap", "family hx")
    .replace("negated_investigation_trap", "neg. MRI")
    .replaceAll("_", " ");
}
