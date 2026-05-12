import React from "react";

export default function EntityLayers({ types, colours, visible, onToggle }) {
  return (
    <div className="entity-layers">
      <div className="layers-header">Layers</div>
      <div className="layers-list">
        {types.map((t) => {
          const isOn = visible.has(t);
          const colour = colours[t] || "#999";
          return (
            <button
              key={t}
              className={`layer-btn ${isOn ? "is-on" : ""}`}
              onClick={() => onToggle(t)}
              title={t}
            >
              <span className="layer-swatch" style={{ background: colour }} />
              <span className="layer-name">{t.replace(/([A-Z])/g, " $1").trim()}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
