import React, { useMemo } from "react";
import { PenTool } from "lucide-react";

function countAnnotated(letters) {
  let count = 0;
  for (const l of letters) {
    try {
      const raw = localStorage.getItem(`exect_annotations_${l.id}`);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed) && parsed.length > 0) count++;
      }
    } catch {
      // ignore
    }
  }
  return count;
}

export default function AnnotationProgress({ letters }) {
  const annotated = useMemo(() => countAnnotated(letters), [letters]);
  const total = letters.length;
  const pct = total > 0 ? (annotated / total) * 100 : 0;

  if (total === 0) return null;

  return (
    <div className="annotation-progress">
      <div className="ap-header">
        <PenTool size={11} />
        <span>{annotated} / {total} annotated</span>
      </div>
      <div className="ap-bar">
        <div className="ap-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
