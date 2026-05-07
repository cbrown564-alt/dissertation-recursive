export const SYSTEM_COLORS = { S2: "#4a90f7", E2: "#10c98a", E3: "#f5a623" };

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
  if (v >= 0.95) return "rgba(16, 201, 138, 0.14)";
  if (v >= 0.85) return "rgba(74, 144, 247, 0.14)";
  if (v >= 0.75) return "rgba(245, 166, 35, 0.14)";
  return "rgba(232, 72, 72, 0.14)";
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
