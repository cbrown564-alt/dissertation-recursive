import React from "react";
import { X, AlertTriangle, CheckCircle2, HelpCircle } from "lucide-react";

export default function AnnotationCard({ entity, colours, onClose, position = "right" }) {
  if (!entity) return null;
  const colour = colours[entity.type] || "#999";
  const attrs = entity.attributes || {};

  const certainty = attrs.Certainty ? parseInt(attrs.Certainty, 10) : null;
  const negation = attrs.Negation;

  return (
    <div className={`annotation-card position-${position}`} style={{ borderColor: colour }}>
      <div className="card-header" style={{ background: colour + "18" }}>
        <span className="card-type" style={{ color: colour }}>{entity.type}</span>
        <button className="card-close" onClick={onClose}><X size={14} /></button>
      </div>

      <div className="card-body">
        <div className="card-quote">"{entity.text.replace(/-/g, " ")}"</div>

        <div className="card-attrs">
          {Object.entries(attrs).map(([k, v]) => (
            <div key={k} className="card-attr">
              <span className="card-attr-key">{k}</span>
              <span className="card-attr-val">{String(v)}</span>
            </div>
          ))}
        </div>

        <div className="card-badges">
          {certainty !== null && (
            <span className={`badge certainty certainty-${certainty}`}>
              {certainty === 5 ? <CheckCircle2 size={11} /> : <HelpCircle size={11} />}
              Certainty {certainty}/5
            </span>
          )}
          {negation && negation.toLowerCase() === "negated" && (
            <span className="badge negated">
              <AlertTriangle size={11} />
              Negated
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
