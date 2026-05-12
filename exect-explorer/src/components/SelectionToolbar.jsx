import React from "react";
import { X } from "lucide-react";

const ENTITY_TYPES = [
  "Diagnosis",
  "Prescription",
  "SeizureFrequency",
  "PatientHistory",
  "Investigations",
  "BirthHistory",
  "Onset",
  "EpilepsyCause",
  "WhenDiagnosed",
];

const TYPE_COLOURS = {
  Diagnosis: "#c45c3e",
  Prescription: "#2d8a5e",
  SeizureFrequency: "#b85cb8",
  PatientHistory: "#5c7db8",
  Investigations: "#b88a5c",
  BirthHistory: "#5cb8a5",
  Onset: "#8a5cb8",
  EpilepsyCause: "#5c8ab8",
  WhenDiagnosed: "#b85c7d",
};

export default function SelectionToolbar({ selection, position, onSelectType, onDismiss }) {
  const style = {};
  if (position) {
    const padding = 16;
    const toolbarWidth = 320;
    const toolbarHeight = 120;
    let left = position.x;
    let top = position.y + 16;
    // Clamp to viewport
    left = Math.max(padding + toolbarWidth / 2, Math.min(window.innerWidth - padding - toolbarWidth / 2, left));
    top = Math.max(padding, Math.min(window.innerHeight - padding - toolbarHeight, top));
    style.left = left;
    style.top = top;
    style.transform = "translateX(-50%)";
  }

  return (
    <div className="selection-toolbar" style={style}>
      <div className="toolbar-header">
        <span className="toolbar-quote">"{selection.text.slice(0, 40)}{selection.text.length > 40 ? "…" : ""}"</span>
        <button className="toolbar-dismiss" onClick={onDismiss}>
          <X size={14} />
        </button>
      </div>
      <div className="toolbar-types">
        {ENTITY_TYPES.map((type) => {
          const colour = TYPE_COLOURS[type] || "#999";
          return (
            <button
              key={type}
              className="toolbar-type-btn"
              style={{ borderColor: colour, color: colour }}
              onClick={() => onSelectType(type)}
            >
              <span className="type-swatch" style={{ background: colour }} />
              {type.replace(/([A-Z])/g, " $1").trim()}
            </button>
          );
        })}
      </div>
    </div>
  );
}
