import React, { useMemo, useRef, useEffect, useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import AnnotationCard from "./AnnotationCard.jsx";

const ORACLE_RATES_BY_TYPE = {
  Prescription: 0.108,
  Diagnosis: 0.133,
  SeizureFrequency: 0.292,
};

function buildSegments(text, entities, visibleLayers) {
  const active = entities.filter((e) => visibleLayers.has(e.type));
  if (active.length === 0) {
    return [{ start: 0, end: text.length, text, entities: [] }];
  }

  const breaks = new Set([0, text.length]);
  active.forEach((e) => {
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
    const segEntities = active.filter((ent) => ent.start <= s && ent.end >= e);
    segments.push({ start: s, end: e, text: segText, entities: segEntities });
  }
  return segments;
}

function blendColours(colours) {
  if (colours.length === 0) return null;
  if (colours.length === 1) return colours[0];
  // Create a gradient blend for multiple colours
  const stops = colours.map((c, i) => {
    const pct = Math.round((i / (colours.length - 1)) * 100);
    return `${c}18 ${pct}%`;
  });
  return `linear-gradient(90deg, ${stops.join(", ")})`;
}

function SegmentSpan({ segment, colours, lens, onHover, onSelect, hoveredId, selectedId }) {
  const { text, entities } = segment;
  if (entities.length === 0) {
    return <span className="plain-seg">{text}</span>;
  }

  const entityIds = entities.map((e) => e.id);
  const isHovered = entityIds.includes(hoveredId);
  const isSelected = entityIds.includes(selectedId);

  const typeColours = entities.map((e) => colours[e.type] || "#999");
  const bg = blendColours(typeColours);

  // Oracle thermal overlay
  let thermalStyle = {};
  if (lens === "oracle") {
    const maxOracle = Math.max(
      ...entities.map((e) => ORACLE_RATES_BY_TYPE[e.type] || 0)
    );
    if (maxOracle > 0) {
      const intensity = maxOracle;
      thermalStyle.background = `rgba(220, 60, 40, ${intensity * 0.25})`;
    }
  }

  const style = {
    background: lens === "oracle" && thermalStyle.background
      ? thermalStyle.background
      : bg || undefined,
    cursor: "pointer",
  };

  // Build underline shadows for each entity type
  const shadows = typeColours.map((c, i) => `0 ${2 + i * 3}px 0 0 ${c}99`);
  if (shadows.length > 0 && lens !== "oracle") {
    style.boxShadow = shadows.join(", ");
  }

  const className = [
    "annotated-seg",
    isHovered ? "is-hovered" : "",
    isSelected ? "is-selected" : "",
    lens === "oracle" ? "oracle-seg" : "",
  ].join(" ");

  const primaryId = entities[0]?.id;

  return (
    <span
      className={className}
      style={style}
      data-eid={primaryId}
      onMouseEnter={() => onHover(primaryId)}
      onMouseLeave={() => onHover(null)}
      onClick={() => onSelect(primaryId)}
    >
      {text}
      {lens === "oracle" && entities.length > 1 && (
        <span className="overlap-indicator" title={`${entities.length} overlapping entities`}>
          {entities.length}
        </span>
      )}
    </span>
  );
}

export default function ReaderView({
  data,
  lens,
  visibleLayers,
  hoveredEntity,
  selectedEntity,
  onHover,
  onSelect,
}) {
  const containerRef = useRef(null);
  const [cardPos, setCardPos] = useState(null);
  const [showGold, setShowGold] = useState(true);

  const colours = {
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

  const displayEntities = useMemo(() => {
    if (!data) return [];
    return showGold ? data.entities.filter((e) => visibleLayers.has(e.type)) : [];
  }, [data, visibleLayers, showGold]);

  const segments = useMemo(() => {
    if (!data) return [];
    return buildSegments(data.text, displayEntities, visibleLayers);
  }, [data, displayEntities, visibleLayers]);

  const selectedEntityData = useMemo(() => {
    if (!data || !selectedEntity) return null;
    return data.entities.find((e) => e.id === selectedEntity) || null;
  }, [data, selectedEntity]);

  // Position card near selected entity
  useEffect(() => {
    if (!selectedEntity || !containerRef.current) {
      setCardPos(null);
      return;
    }
    const el = containerRef.current.querySelector(`[data-eid="${selectedEntity}"]`);
    if (el) {
      const rect = el.getBoundingClientRect();
      const containerRect = containerRef.current.getBoundingClientRect();
      const containerWidth = containerRect.width;
      let left = rect.left - containerRect.left;
      // Clamp so card (320px) doesn't overflow right edge
      if (left + 340 > containerWidth) {
        left = Math.max(0, containerWidth - 340);
      }
      setCardPos({
        top: rect.top - containerRect.top + 28,
        left,
      });
    }
  }, [selectedEntity]);

  if (!data) {
    return (
      <div className="reader-view empty">
        <p>Loading letter…</p>
      </div>
    );
  }

  return (
    <div className="reader-view" ref={containerRef}>
      <div className="letter-sheet">
        <div className="letter-header">
          <h1>{data.id}</h1>
          <p className="letter-meta">
            {data.text.split(/\n/).length} lines · {displayEntities.length} annotations
            {data.flaws.length > 0 && (
              <span className="flaw-badge">{data.flaws.length} flaw(s)</span>
            )}
            <button
              className={`gold-toggle ${showGold ? "is-on" : ""}`}
              onClick={() => setShowGold((s) => !s)}
              title={showGold ? "Hide gold annotations" : "Show gold annotations"}
            >
              {showGold ? <Eye size={13} /> : <EyeOff size={13} />}
              {showGold ? "Gold visible" : "Gold hidden"}
            </button>
          </p>
        </div>

        <div className="letter-body">
          {segments.map((seg, i) => (
            <SegmentSpan
              key={i}
              segment={seg}
              colours={colours}
              lens={lens}
              onHover={onHover}
              onSelect={onSelect}
              hoveredId={hoveredEntity}
              selectedId={selectedEntity}
            />
          ))}
        </div>

        {lens === "oracle" && (
          <OracleMarginalia flaws={data.flaws} entities={data.entities} colours={colours} />
        )}
      </div>

      {selectedEntityData && cardPos && (
        <div className="floating-card" style={{ top: cardPos.top, left: cardPos.left }}>
          <AnnotationCard
            entity={selectedEntityData}
            colours={colours}
            onClose={() => onSelect(null)}
          />
        </div>
      )}
    </div>
  );
}

function OracleMarginalia({ flaws, entities, colours }) {
  if (!flaws || flaws.length === 0) return null;

  return (
    <div className="oracle-marginalia">
      <div className="marginalia-header">
        <span className="marginalia-dot" />
        Oracle Analysis
      </div>
      <div className="marginalia-list">
        {flaws.map((flaw, i) => (
          <div key={i} className={`marginalia-item severity-${flaw.oracle_impact ? 'high' : 'low'}`}>
            <div className="marginalia-category">{flaw.category.replace(/_/g, " ")}</div>
            <div className="marginalia-desc">{flaw.description}</div>
            {flaw.oracle_impact && (
              <div className="marginalia-oracle">
                Oracle impact: <strong>{flaw.oracle_impact}</strong>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
