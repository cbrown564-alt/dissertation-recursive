import React from "react";
import { Trash2, Edit2, X, AlertCircle } from "lucide-react";

export default function UserAnnotationsPanel({ annotations, colours, onSelect, onDelete, onClearAll }) {
  if (annotations.length === 0) {
    return (
      <div className="side-panel user-annotations-panel">
        <div className="panel-header">
          <Edit2 size={15} />
          <span>Your Annotations</span>
        </div>
        <div className="ua-empty">
          <AlertCircle size={20} className="ua-empty-icon" />
          <p>No annotations yet.</p>
          <p className="ua-empty-hint">Select text in the letter to begin annotating.</p>
        </div>
      </div>
    );
  }

  const byType = {};
  annotations.forEach((a) => {
    if (!byType[a.type]) byType[a.type] = [];
    byType[a.type].push(a);
  });

  return (
    <div className="side-panel user-annotations-panel">
      <div className="panel-header">
        <Edit2 size={15} />
        <span>Your Annotations</span>
        <span className="ua-count">{annotations.length}</span>
      </div>

      <div className="ua-list">
        {Object.entries(byType).map(([type, items]) => {
          const colour = colours[type] || "#999";
          return (
            <div key={type} className="ua-group">
              <div className="ua-group-header" style={{ color: colour }}>
                <span className="ua-group-swatch" style={{ background: colour }} />
                {type.replace(/([A-Z])/g, " $1").trim()} ({items.length})
              </div>
              {items.map((a) => (
                <div key={a.id} className="ua-item" onClick={() => onSelect(a.id)}>
                  <div className="ua-text">{a.text.replace(/-/g, " ").slice(0, 40)}</div>
                  <div className="ua-attrs">
                    {Object.entries(a.attributes || {})
                      .filter(([k]) => k !== "CUI" && k !== "CUIPhrase")
                      .slice(0, 3)
                      .map(([k, v]) => (
                        <span key={k} className="ua-attr">
                          {k}: {String(v)}
                        </span>
                      ))}
                  </div>
                  <button
                    className="ua-delete"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(a.id);
                    }}
                    title="Delete"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              ))}
            </div>
          );
        })}
      </div>

      <button className="ua-clear" onClick={onClearAll}>
        <X size={12} />
        Clear all annotations
      </button>
    </div>
  );
}
