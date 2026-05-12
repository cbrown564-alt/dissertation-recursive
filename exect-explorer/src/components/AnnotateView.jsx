import React, { useState, useRef, useEffect, useMemo, useCallback } from "react";
import { Highlighter, Trash2, Edit2, CheckCircle2, Trophy, Eye, EyeOff } from "lucide-react";
import { loadAnnotations, saveAnnotations, buildSegments, getSelectionOffsets, ENTITY_SCHEMAS, scoreAnnotations } from "../utils/annotations.js";
import SelectionToolbar from "./SelectionToolbar.jsx";
import AttributeForm from "./AttributeForm.jsx";
import ScoringView from "./ScoringView.jsx";
import GuidelinesPanel from "./GuidelinesPanel.jsx";
import UserAnnotationsPanel from "./UserAnnotationsPanel.jsx";

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

export default function AnnotateView({ data, visibleLayers }) {
  const containerRef = useRef(null);
  const [annotations, setAnnotations] = useState([]);
  const [selection, setSelection] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [showGold, setShowGold] = useState(false);
  const [showScore, setShowScore] = useState(false);
  const [showGuidelines, setShowGuidelines] = useState(true);
  const [hoveredId, setHoveredId] = useState(null);
  const [draftType, setDraftType] = useState(null);

  // Load saved annotations
  useEffect(() => {
    if (!data) return;
    setAnnotations(loadAnnotations(data.id));
    setShowScore(false);
    setSelection(null);
    setEditingId(null);
    setDraftType(null);
  }, [data?.id]);

  // Save on change
  useEffect(() => {
    if (!data) return;
    saveAnnotations(data.id, annotations);
  }, [annotations, data?.id]);

  const [toolbarPos, setToolbarPos] = useState({ x: 0, y: 0 });

  const handleMouseUp = useCallback((e) => {
    // Don't create selection if clicking on an existing annotation
    if (e.target.closest(".annotate-seg")) {
      return;
    }
    if (!containerRef.current) return;
    const sel = getSelectionOffsets(containerRef.current);
    if (sel && sel.text.trim().length > 0) {
      setSelection(sel);
      setEditingId(null);
      setDraftType(null);
      setToolbarPos({ x: e.clientX, y: e.clientY });
    } else {
      setSelection(null);
    }
  }, []);

  const handleKeyDown = useCallback((e) => {
    if (e.key === "Escape") {
      setSelection(null);
      setEditingId(null);
      setShowScore(false);
      window.getSelection()?.removeAllRanges();
    }
  }, []);

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  const handleAddAnnotation = (type, attributes) => {
    if (!selection) return;
    const newAnn = {
      id: `user-${Date.now()}`,
      type,
      start: selection.start,
      end: selection.end,
      text: selection.text,
      attributes: attributes || {},
    };
    setAnnotations((prev) => [...prev, newAnn]);
    setSelection(null);
    window.getSelection()?.removeAllRanges();
  };

  const handleUpdateAnnotation = (id, updates) => {
    setAnnotations((prev) =>
      prev.map((a) => (a.id === id ? { ...a, ...updates } : a))
    );
    setEditingId(null);
  };

  const handleDeleteAnnotation = (id) => {
    setAnnotations((prev) => prev.filter((a) => a.id !== id));
    if (editingId === id) setEditingId(null);
  };

  const handleSelectEntity = (id) => {
    setEditingId(id);
    setSelection(null);
    window.getSelection()?.removeAllRanges();
  };

  const goldEntities = useMemo(() => {
    if (!data) return [];
    return data.entities.filter((e) => visibleLayers.has(e.type));
  }, [data, visibleLayers]);

  const displayEntities = useMemo(() => {
    if (showGold && data) {
      // Merge user annotations with gold, but mark gold as readonly
      const goldMarked = goldEntities.map((g) => ({ ...g, isGold: true }));
      return [...annotations, ...goldMarked];
    }
    return annotations;
  }, [showGold, goldEntities, annotations, data]);

  const segments = useMemo(() => {
    if (!data) return [];
    return buildSegments(data.text, displayEntities);
  }, [data, displayEntities]);

  const editingAnnotation = annotations.find((a) => a.id === editingId) || null;

  const scoreResult = useMemo(() => {
    if (!data) return null;
    return scoreAnnotations(annotations, data.entities);
  }, [annotations, data]);

  if (!data) {
    return (
      <div className="annotate-view empty">
        <p>Loading letter…</p>
      </div>
    );
  }

  return (
    <div className="annotate-view">
      <div className="annotate-main">
        <div className="annotate-toolbar-row">
          <div className="annotate-title">
            <Highlighter size={16} />
            <span>Annotate {data.id}</span>
          </div>
          <div className="annotate-actions">
            <button
              className={`action-btn ${showGuidelines ? "is-active" : ""}`}
              onClick={() => setShowGuidelines((s) => !s)}
            >
              Guidelines
            </button>
            <button
              className={`action-btn ${showGold ? "is-active" : ""}`}
              onClick={() => setShowGold((s) => !s)}
            >
              {showGold ? <Eye size={14} /> : <EyeOff size={14} />}
              {showGold ? "Gold On" : "Gold Off"}
            </button>
            <button
              className={`action-btn score-btn ${annotations.length > 0 ? "" : "is-disabled"}`}
              onClick={() => annotations.length > 0 && setShowScore(true)}
            >
              <Trophy size={14} />
              Score
            </button>
          </div>
        </div>

        <div
          className="annotate-text-area"
          ref={containerRef}
          onMouseUp={handleMouseUp}
        >
          <div className="annotate-sheet">
            <div className="annotate-body">
              {segments.map((seg, i) => (
                <AnnotateSegment
                  key={i}
                  segment={seg}
                  colours={TYPE_COLOURS}
                  hoveredId={hoveredId}
                  onHover={setHoveredId}
                  onSelect={handleSelectEntity}
                />
              ))}
            </div>
          </div>
        </div>

        {selection && !editingId && (
          <SelectionToolbar
            selection={selection}
            position={toolbarPos}
            onSelectType={(type) => {
              setDraftType(type);
              setEditingId(`new-${type}-${Date.now()}`);
            }}
            onDismiss={() => {
              setSelection(null);
              window.getSelection()?.removeAllRanges();
            }}
          />
        )}
      </div>

      {showGuidelines && (
        <GuidelinesPanel
          onClose={() => setShowGuidelines(false)}
        />
      )}

      {!showGuidelines && !showScore && !editingId && !selection && (
        <UserAnnotationsPanel
          annotations={annotations}
          colours={TYPE_COLOURS}
          onSelect={handleSelectEntity}
          onDelete={handleDeleteAnnotation}
          onClearAll={() => {
            if (confirm("Clear all annotations for this letter?")) {
              setAnnotations([]);
            }
          }}
        />
      )}

      {(editingId || selection) && !showScore && (
        <AttributeForm
          key={editingId || "new"}
          annotation={editingAnnotation}
          selection={selection}
          schema={ENTITY_SCHEMAS[editingAnnotation?.type] || null}
          onSave={editingAnnotation
            ? (attrs) => handleUpdateAnnotation(editingAnnotation.id, { attributes: attrs })
            : handleAddAnnotation
          }
          onCancel={() => {
            setEditingId(null);
            setSelection(null);
          }}
          onDelete={editingAnnotation ? () => handleDeleteAnnotation(editingAnnotation.id) : null}
        />
      )}

      {showScore && scoreResult && (
        <ScoringView
          result={scoreResult}
          userAnnotations={annotations}
          goldEntities={data.entities}
          colours={TYPE_COLOURS}
          onClose={() => setShowScore(false)}
          onHighlightGold={(id) => {
            setShowGold(true);
            setHoveredId(id);
          }}
        />
      )}
    </div>
  );
}

function AnnotateSegment({ segment, colours, hoveredId, onHover, onSelect }) {
  const { text, entities } = segment;
  if (entities.length === 0) {
    return <span className="annotate-plain">{text}</span>;
  }

  const primary = entities[0];
  const isHovered = primary.id === hoveredId;
  const isGold = primary.isGold;
  const colour = colours[primary.type] || "#999";

  const style = {
    background: isGold ? `${colour}15` : `${colour}25`,
    borderBottom: `2px solid ${isGold ? colour + "60" : colour + "99"}`,
    cursor: "pointer",
  };

  if (isGold) {
    style.borderStyle = "dashed";
  }

  return (
    <span
      className={`annotate-seg ${isHovered ? "is-hovered" : ""} ${isGold ? "is-gold" : ""}`}
      style={style}
      data-aid={primary.id}
      onMouseEnter={() => onHover(primary.id)}
      onMouseLeave={() => onHover(null)}
      onClick={() => onSelect(primary.id)}
    >
      {text}
      {entities.length > 1 && (
        <span className="overlap-badge">{entities.length}</span>
      )}
    </span>
  );
}
