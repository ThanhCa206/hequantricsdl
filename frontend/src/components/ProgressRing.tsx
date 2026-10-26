import React from "react";

interface ProgressRingProps {
  radius?: number;
  strokeWidth?: number;
  progress: number; // 0 to 100
  color?: string;
  label?: string;
  sublabel?: string;
}

export const ProgressRing: React.FC<ProgressRingProps> = ({
  radius = 60,
  strokeWidth = 8,
  progress,
  color = "var(--pg-color)",
  label,
  sublabel,
}) => {
  const normalizedRadius = radius - strokeWidth / 2;
  const circumference = normalizedRadius * 2 * Math.PI;
  const strokeDashoffset = circumference - (Math.min(100, Math.max(0, progress)) / 100) * circumference;

  return (
    <div className="progress-ring-container" style={{ width: radius * 2, height: radius * 2 }}>
      <svg height={radius * 2} width={radius * 2} className="progress-ring-svg">
        <circle
          className="progress-ring-bg"
          strokeWidth={strokeWidth}
          r={normalizedRadius}
          cx={radius}
          cy={radius}
        />
        <circle
          className="progress-ring-fill"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray={`${circumference} ${circumference}`}
          style={{ strokeDashoffset }}
          r={normalizedRadius}
          cx={radius}
          cy={radius}
        />
      </svg>
      <div className="progress-ring-label">
        <span style={{ fontSize: "1.25rem", fontWeight: 800, fontFamily: "var(--font-display)" }}>
          {label ?? `${Math.round(progress)}%`}
        </span>
        {sublabel && (
          <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>{sublabel}</span>
        )}
      </div>
    </div>
  );
};
