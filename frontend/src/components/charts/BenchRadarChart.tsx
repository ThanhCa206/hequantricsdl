import React from "react";
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Legend,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface BenchRadarChartProps {
  data: Array<{
    subject: string;
    postgresql: number;
    mongodb: number;
    fullMark?: number;
  }>;
  title?: string;
  height?: number;
}

export const BenchRadarChart: React.FC<BenchRadarChartProps> = ({
  data,
  title,
  height = 360,
}) => {
  return (
    <div style={{ width: "100%", height }}>
      {title && (
        <h4 style={{ fontSize: "0.95rem", marginBottom: "0.75rem", fontWeight: 600 }}>{title}</h4>
      )}
      <ResponsiveContainer width="100%" height={height - (title ? 35 : 0)}>
        <RadarChart data={data} margin={{ top: 10, right: 30, left: 30, bottom: 10 }}>
          <PolarGrid stroke="var(--border-light)" />
          <PolarAngleAxis
            dataKey="subject"
            stroke="var(--text-secondary)"
            fontSize={11}
            tickLine={false}
          />
          <PolarRadiusAxis
            angle={30}
            stroke="var(--border-light)"
            fontSize={10}
            tick={false}
          />
          <Tooltip
            contentStyle={{
              background: "var(--bg-tooltip)",
              border: "1px solid var(--border-medium)",
              borderRadius: "8px",
              boxShadow: "var(--shadow-lg)",
              fontSize: "0.8rem",
              color: "var(--text-primary)",
            }}
            labelStyle={{
              color: "var(--text-primary)",
              fontWeight: 600,
            }}
            itemStyle={{
              color: "var(--text-secondary)",
            }}
          />
          <Legend
            verticalAlign="top"
            height={36}
            formatter={(value) => (
              <span
                style={{
                  color: "var(--text-secondary)",
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  textTransform: "capitalize",
                }}
              >
                {value === "postgresql" ? "PostgreSQL 17.2" : "MongoDB 8.0.4"}
              </span>
            )}
          />
          <Radar
            name="postgresql"
            dataKey="postgresql"
            stroke="var(--pg-color)"
            fill="var(--pg-color)"
            fillOpacity={0.25}
          />
          <Radar
            name="mongodb"
            dataKey="mongodb"
            stroke="var(--mongo-color)"
            fill="var(--mongo-color)"
            fillOpacity={0.25}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
};
