import React from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

interface BenchLineChartProps {
  data: Array<{
    name: string;
    postgresql: number;
    mongodb: number;
    [key: string]: any;
  }>;
  title?: string;
  yAxisLabel?: string;
  yAxisUnit?: string;
  height?: number;
}

export const BenchLineChart: React.FC<BenchLineChartProps> = ({
  data,
  title,
  yAxisLabel = "Thông lượng",
  yAxisUnit = " QPS",
  height = 300,
}) => {
  return (
    <div style={{ width: "100%", height }}>
      {title && (
        <h4 style={{ fontSize: "0.95rem", marginBottom: "0.75rem", fontWeight: 600 }}>{title}</h4>
      )}
      <ResponsiveContainer width="100%" height={height - (title ? 35 : 0)}>
        <LineChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" vertical={false} />
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
            unit={yAxisUnit}
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
          <Line
            type="monotone"
            dataKey="postgresql"
            stroke="var(--pg-color)"
            strokeWidth={2.5}
            dot={{ r: 4, fill: "var(--pg-color)" }}
            activeDot={{ r: 6 }}
          />
          <Line
            type="monotone"
            dataKey="mongodb"
            stroke="var(--mongo-color)"
            strokeWidth={2.5}
            dot={{ r: 4, fill: "var(--mongo-color)" }}
            activeDot={{ r: 6 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};
