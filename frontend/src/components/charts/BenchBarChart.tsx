import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

interface BenchBarChartProps {
  data: Array<{
    name: string;
    postgresql: number;
    mongodb: number;
    [key: string]: any;
  }>;
  title?: string;
  yAxisLabel?: string;
  height?: number;
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    const pgVal = payload.find((p: any) => p.dataKey === "postgresql")?.value;
    const mongoVal = payload.find((p: any) => p.dataKey === "mongodb")?.value;
    const diff = pgVal !== undefined && mongoVal !== undefined ? pgVal - mongoVal : null;
    const winner =
      diff !== null && diff < 0
        ? "PostgreSQL nhanh hơn"
        : diff !== null && diff > 0
        ? "MongoDB nhanh hơn"
        : "Tương đương";

    return (
      <div
        className="card chart-tooltip"
        style={{
          padding: "0.75rem 1rem",
          background: "var(--bg-tooltip)",
          border: "1px solid var(--border-medium)",
          boxShadow: "var(--shadow-lg)",
          fontSize: "0.8rem",
          color: "var(--text-primary)",
        }}
      >
        <div style={{ fontWeight: 700, marginBottom: "0.4rem", color: "var(--text-primary)" }}>
          {label}
        </div>
        <div
          style={{
            color: "var(--pg-color)",
            display: "flex",
            justifyContent: "space-between",
            gap: "1.25rem",
            marginBottom: "0.2rem",
          }}
        >
          <span>PostgreSQL:</span>
          <strong>{typeof pgVal === "number" ? pgVal.toFixed(2) : "—"} ms</strong>
        </div>
        <div
          style={{
            color: "var(--mongo-color)",
            display: "flex",
            justifyContent: "space-between",
            gap: "1.25rem",
            marginBottom: "0.2rem",
          }}
        >
          <span>MongoDB:</span>
          <strong>{typeof mongoVal === "number" ? mongoVal.toFixed(2) : "—"} ms</strong>
        </div>
        {diff !== null && (
          <div
            style={{
              marginTop: "0.4rem",
              paddingTop: "0.4rem",
              borderTop: "1px solid var(--border-light)",
              fontSize: "0.75rem",
              color: "var(--warning)",
              fontWeight: 600,
            }}
          >
            {winner} ({Math.abs(diff).toFixed(2)} ms)
          </div>
        )}
      </div>
    );
  }
  return null;
};

export const BenchBarChart: React.FC<BenchBarChartProps> = ({
  data,
  title,
  yAxisLabel = "Độ trễ (ms)",
  height = 360,
}) => {
  return (
    <div style={{ width: "100%", height }}>
      {title && (
        <h4 style={{ fontSize: "0.95rem", marginBottom: "0.75rem", fontWeight: 600 }}>{title}</h4>
      )}
      <ResponsiveContainer width="100%" height={height - (title ? 35 : 0)}>
        <BarChart
          data={data}
          margin={{ top: 10, right: 20, left: 0, bottom: 20 }}
          barGap={6}
          barCategoryGap={16}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="var(--border-light)"
            vertical={false}
          />
          <XAxis
            dataKey="name"
            stroke="var(--text-muted)"
            fontSize={12}
            tickLine={false}
            fontFamily="var(--font-mono)"
          />
          <YAxis
            stroke="var(--text-muted)"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            unit=" ms"
          />
          <Tooltip
            content={<CustomTooltip />}
            cursor={{ fill: "rgba(56, 189, 248, 0.08)" }}
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
          <Bar
            dataKey="postgresql"
            name="postgresql"
            fill="var(--pg-color)"
            radius={[4, 4, 0, 0]}
            maxBarSize={40}
          />
          <Bar
            dataKey="mongodb"
            name="mongodb"
            fill="var(--mongo-color)"
            radius={[4, 4, 0, 0]}
            maxBarSize={40}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};
