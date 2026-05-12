import React, { useMemo } from "react";
import { Clock, Calendar, AlertCircle } from "lucide-react";

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

export default function TimelineView({ data, lens, visibleLayers }) {
  const events = useMemo(() => {
    if (!data) return [];
    return data.timeline_events.filter((e) => visibleLayers.has(e.type));
  }, [data, visibleLayers]);

  const sparse = useMemo(() => {
    if (!data) return [];
    return data.temporal_sparse.filter((e) => visibleLayers.has(e.type));
  }, [data, visibleLayers]);

  if (!data) {
    return (
      <div className="timeline-view empty">
        <p>Loading timeline…</p>
      </div>
    );
  }

  // Group events by year if possible, otherwise by type
  const byYear = {};
  const unanchored = [];
  events.forEach((ev) => {
    const y = ev.year ? parseInt(ev.year, 10) : null;
    if (y && !isNaN(y)) {
      if (!byYear[y]) byYear[y] = [];
      byYear[y].push(ev);
    } else {
      unanchored.push(ev);
    }
  });

  const sortedYears = Object.keys(byYear)
    .map((y) => parseInt(y, 10))
    .sort((a, b) => a - b);

  return (
    <div className="timeline-view">
      <div className="timeline-header">
        <h2>Clinical Timeline</h2>
        <p className="timeline-sub">
          Temporal reconstruction from annotated entities
          {sparse.length > 0 && (
            <span className="sparse-warning">
              <AlertCircle size={12} />
              {sparse.length} unanchored
            </span>
          )}
        </p>
      </div>

      <div className="timeline-body">
        {sortedYears.length === 0 && unanchored.length === 0 && (
          <div className="timeline-empty">No temporal events found for visible layers.</div>
        )}

        {sortedYears.map((year) => (
          <div key={year} className="timeline-year">
            <div className="year-marker">
              <Calendar size={14} />
              <span>{year}</span>
            </div>
            <div className="year-events">
              {byYear[year].map((ev) => (
                <TimelineEvent key={ev.id} event={ev} lens={lens} />
              ))}
            </div>
          </div>
        ))}

        {unanchored.length > 0 && (
          <div className="timeline-year limbo">
            <div className="year-marker">
              <Clock size={14} />
              <span>Unanchored</span>
            </div>
            <div className="year-events">
              {unanchored.map((ev) => (
                <TimelineEvent key={ev.id} event={ev} lens={lens} limbo />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function TimelineEvent({ event, lens, limbo }) {
  const colour = TYPE_COLOURS[event.type] || "#999";
  const attrs = [];
  if (event.num_seizures) attrs.push(`${event.num_seizures} seizure(s)`);
  if (event.lower_seizures && event.upper_seizures) {
    attrs.push(`${event.lower_seizures}–${event.upper_seizures} seizures`);
  }
  if (event.period) attrs.push(`per ${event.period.toLowerCase()}`);
  if (event.num_periods) attrs.push(`×${event.num_periods}`);
  if (event.time_since) attrs.push(event.time_since);
  if (event.point_in_time) attrs.push(event.point_in_time);

  return (
    <div className={`timeline-event ${limbo ? "is-limbo" : ""}`} style={{ borderLeftColor: colour }}>
      <div className="event-type" style={{ color: colour }}>
        {event.type.replace(/([A-Z])/g, " $1").trim()}
      </div>
      <div className="event-text">{event.text.replace(/-/g, " ")}</div>
      {attrs.length > 0 && (
        <div className="event-attrs">{attrs.join(" · ")}</div>
      )}
      {lens === "oracle" && limbo && (
        <div className="event-oracle">
          Temporal sparsity — gold assumes "current" when empty
        </div>
      )}
    </div>
  );
}
