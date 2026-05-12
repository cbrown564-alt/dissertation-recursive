import React from "react";

export default function RadialProgress({ value, size = 110, stroke = 5, color = "#2d8a5e" }) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - value * circumference;

  return (
    <svg width={size} height={size} className="radial-progress">
      <circle
        className="rp-track"
        cx={size / 2}
        cy={size / 2}
        r={radius}
        strokeWidth={stroke}
      />
      <circle
        className="rp-bar"
        cx={size / 2}
        cy={size / 2}
        r={radius}
        strokeWidth={stroke}
        stroke={color}
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
      />
    </svg>
  );
}
