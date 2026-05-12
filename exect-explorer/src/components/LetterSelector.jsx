import React, { useState, useMemo } from "react";
import { Search, AlertTriangle, Star, PenTool } from "lucide-react";

const NOTABLE = ["EA0001", "EA0006", "EA0012", "EA0034", "EA0056"];

function hasUserAnnotations(letterId) {
  try {
    const raw = localStorage.getItem(`exect_annotations_${letterId}`);
    if (!raw) return false;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) && parsed.length > 0;
  } catch {
    return false;
  }
}

export default function LetterSelector({ letters, currentId, onSelect }) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all"); // all | notable | flawed | annotated

  const filtered = useMemo(() => {
    let result = letters;
    if (filter === "notable") {
      result = result.filter((l) => NOTABLE.includes(l.id));
    } else if (filter === "flawed") {
      result = result.filter((l) => l.flaw_count > 0);
    } else if (filter === "annotated") {
      result = result.filter((l) => hasUserAnnotations(l.id));
    }
    const q = query.trim().toLowerCase();
    if (q) {
      result = result.filter((l) => l.id.toLowerCase().includes(q));
    }
    return result;
  }, [letters, query, filter]);

  return (
    <div className="letter-selector">
      <div className="selector-search">
        <Search size={13} />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Find letter…"
        />
      </div>
      <div className="selector-filters">
        <button className={filter === "all" ? "is-active" : ""} onClick={() => setFilter("all")}>All</button>
        <button className={filter === "notable" ? "is-active" : ""} onClick={() => setFilter("notable")} title="Phase 6 audited cases">
          <Star size={10} /> Notable
        </button>
        <button className={filter === "flawed" ? "is-active" : ""} onClick={() => setFilter("flawed")}>
          <AlertTriangle size={10} /> Flawed
        </button>
        <button className={filter === "annotated" ? "is-active" : ""} onClick={() => setFilter("annotated")}>
          <PenTool size={10} /> Annotated
        </button>
      </div>
      <div className="selector-list">
        {filtered.map((l) => (
          <button
            key={l.id}
            className={`selector-item ${l.id === currentId ? "is-active" : ""}`}
            onClick={() => onSelect(l.id)}
          >
            <span className="selector-id">{l.id}</span>
            {hasUserAnnotations(l.id) && (
              <span className="selector-annotated" title="You have annotated this letter">
                <PenTool size={10} />
              </span>
            )}
            {NOTABLE.includes(l.id) && (
              <span className="selector-star" title="Notable case from Phase 6 audit">
                <Star size={10} />
              </span>
            )}
            {l.flaw_count > 0 && (
              <span className="selector-flaw" title={`${l.flaw_count} flaw(s)`}>
                <AlertTriangle size={10} />
              </span>
            )}
            <span className="selector-count">
              {Object.values(l.type_counts).reduce((a, b) => a + b, 0)}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
