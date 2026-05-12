import React from "react";

export default function LensBar({ lenses, active, onSelect }) {
  return (
    <div className="lens-bar" role="tablist" aria-label="Lens selector">
      {lenses.map((l) => {
        const isActive = l.id === active;
        const Icon = l.icon;
        return (
          <button
            key={l.id}
            role="tab"
            aria-selected={isActive}
            className={`lens-btn ${isActive ? "is-active" : ""} ${l.disabled ? "is-disabled" : ""}`}
            onClick={() => !l.disabled && onSelect(l.id)}
            title={l.desc}
          >
            <Icon size={14} />
            <span>{l.label}</span>
            {l.disabled && <span className="lens-badge">Soon</span>}
          </button>
        );
      })}
    </div>
  );
}
