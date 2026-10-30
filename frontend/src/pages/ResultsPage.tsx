import React, { useState, useEffect } from "react";
import {
  BarChart3,
  Download,
  FileText,
  CheckCircle2,
  AlertTriangle,
  Layers,
  Cpu,
  Trophy,
  TrendingUp,
  Activity,
  Zap,
} from "lucide-react";
import {
  fetchExperiments,
  fetchExperimentSummary,
  fetchExperimentResources,
  fetchExperimentPlans,
} from "../api";
import { BenchBarChart } from "../components/charts/BenchBarChart";
import { BenchLineChart } from "../components/charts/BenchLineChart";
import { BenchRadarChart } from "../components/charts/BenchRadarChart";
import { CardSkeleton, TableSkeleton } from "../components/LoadingSkeleton";

interface ResultsPageProps {
  initialExpId?: string;
}

export const ResultsPage: React.FC<ResultsPageProps> = ({ initialExpId }) => {
  const [experiments, setExperiments] = useState<any[]>([]);
  const [selectedExpId, setSelectedExpId] = useState<string>(initialExpId || "");
  const [summary, setSummary] = useState<any | null>(null);
  const [resources, setResources] = useState<any[]>([]);
  const [plans, setPlans] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [selectedQuery, setSelectedQuery] = useState<string>("ALL");
  const [selectedPercentile, setSelectedPercentile] = useState<"p50" | "p90" | "p95" | "p99">("p50");
  const [activeChartTab, setActiveChartTab] = useState<"bar" | "radar" | "qps" | "resources">("bar");

  useEffect(() => {
    fetchExperiments().then((exps) => {
      setExperiments(exps);
      if (!selectedExpId && exps.length > 0) {
        setSelectedExpId(exps[0].experiment_id);
      }
    });
  }, []);

  useEffect(() => {
    if (!selectedExpId) return;
    const loadDetails = async () => {
      try {
        setLoading(true);
        setErrorMsg(null);
        const [sumData, resData, planData] = await Promise.all([
          fetchExperimentSummary(selectedExpId).catch((err) => {
            setErrorMsg(err.message);
            return null;
          }),
          fetchExperimentResources(selectedExpId).catch(() => []),
          fetchExperimentPlans(selectedExpId).catch(() => null),
        ]);
        setSummary(sumData);
        setResources(resData);
        setPlans(planData);
      } finally {
        setLoading(false);
      }
    };
    loadDetails();
  }, [selectedExpId]);

  const queryKeys = summary?.queries ? Object.keys(summary.queries) : [];
  const filteredQueries = selectedQuery === "ALL" ? queryKeys : [selectedQuery];

  // Prepare data for BarChart (Latency based on selected percentile)
  const barChartData = filteredQueries.map((qId) => {
    const qData = summary?.queries[qId];
    const key = `${selectedPercentile}_ms` as const;
    return {
      name: qId,
      postgresql: qData?.postgresql?.[key] ?? 0,
      mongodb: qData?.mongodb?.[key] ?? 0,
    };
  });

  // Prepare data for Throughput QPS chart
  const qpsChartData = filteredQueries.map((qId) => {
    const qData = summary?.queries[qId];
    return {
      name: qId,
      postgresql: qData?.postgresql?.throughput_qps ?? 0,
      mongodb: qData?.mongodb?.throughput_qps ?? 0,
    };
  });

  // Prepare dynamic data for RadarChart (Normalized performance score per query category)
  const queryNames: Record<string, string> = {
    Q1: "Point Lookup (Q1)",
    Q2: "Date Range (Q2)",
    Q3: "Multi-Filter (Q3)",
    Q4: "Count Agg (Q4)",
    Q5: "Group Sum (Q5)",
    Q6: "JOIN Top-20 (Q6)",
    Q7: "Keyset Paging (Q7)",
    Q7_keyset: "Keyset Paging (Q7)",
    Q7_offset: "Offset Paging (Q7)",
    Q8: "Embedding (Q8)",
    Q8_track_a: "Referenced (Q8A)",
    Q8_track_b: "Embedded (Q8B)",
  };

  const radarChartData = queryKeys.length > 0
    ? queryKeys.slice(0, 8).map((qId) => {
        const qData = summary?.queries[qId];
        const pgP50 = qData?.postgresql?.p50_ms ?? 0;
        const mongoP50 = qData?.mongodb?.p50_ms ?? 0;
        const pgQps = qData?.postgresql?.throughput_qps ?? 0;
        const mongoQps = qData?.mongodb?.throughput_qps ?? 0;

        let pgScore = 50;
        let mongoScore = 50;

        if (pgQps > 0 || mongoQps > 0) {
          const maxQps = Math.max(pgQps, mongoQps);
          pgScore = maxQps > 0 ? Math.round((pgQps / maxQps) * 100) : 0;
          mongoScore = maxQps > 0 ? Math.round((mongoQps / maxQps) * 100) : 0;
        } else if (pgP50 > 0 && mongoP50 > 0) {
          const minLat = Math.min(pgP50, mongoP50);
          pgScore = Math.round((minLat / pgP50) * 100);
          mongoScore = Math.round((minLat / mongoP50) * 100);
        } else if (pgP50 > 0) {
          pgScore = 100;
          mongoScore = 0;
        } else if (mongoP50 > 0) {
          mongoScore = 100;
          pgScore = 0;
        }

        return {
          subject: queryNames[qId] || qId,
          postgresql: Math.max(10, Math.min(100, pgScore)),
          mongodb: Math.max(10, Math.min(100, mongoScore)),
        };
      })
    : [
        { subject: "Point Lookup (Q1)", postgresql: 50, mongodb: 50 },
        { subject: "Date Range (Q2)", postgresql: 50, mongodb: 50 },
        { subject: "Multi-Filter (Q3)", postgresql: 50, mongodb: 50 },
        { subject: "Count Agg (Q4)", postgresql: 50, mongodb: 50 },
        { subject: "Group Sum (Q5)", postgresql: 50, mongodb: 50 },
        { subject: "JOIN Top-20 (Q6)", postgresql: 50, mongodb: 50 },
      ];

  // Calculate Win/Loss score
  let pgWins = 0;
  let mongoWins = 0;
  queryKeys.forEach((qId) => {
    const qData = summary?.queries[qId];
    const pgP50 = qData?.postgresql?.p50_ms ?? 0;
    const mongoP50 = qData?.mongodb?.p50_ms ?? 0;
    if (pgP50 > 0 && mongoP50 > 0) {
      if (pgP50 < mongoP50) pgWins++;
      else if (mongoP50 < pgP50) mongoWins++;
    }
  });

  return (
    <div className="page-wrapper">
      {/* Page Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: "2rem",
          flexWrap: "wrap",
          gap: "1rem",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
            <span className="badge badge-info">Trực Quan Hóa Đa Chiều</span>
            <span className="badge badge-success">Paired Bootstrap CI 95%</span>
          </div>
          <h1 style={{ fontSize: "1.85rem", marginBottom: "0.5rem" }}>
            Phân Tích Thống Kê & Báo Cáo Hiệu Năng
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem" }}>
            Trực quan hóa độ trễ phân vị p50/p90/p95/p99, thông lượng QPS, radar đa chiều và tiêu
            thụ tài nguyên.
          </p>
        </div>

        {/* Export Buttons */}
        {selectedExpId && (
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <a
              href={`/api/results/${selectedExpId}/export/markdown`}
              download={`${selectedExpId}-report.md`}
              className="btn btn-secondary"
              style={{ fontSize: "0.8rem", textDecoration: "none" }}
            >
              <FileText size={15} /> Xuất Markdown
            </a>
            <a
              href={`/api/results/${selectedExpId}/export/csv`}
              download={`${selectedExpId}-summary.csv`}
              className="btn btn-secondary"
              style={{ fontSize: "0.8rem", textDecoration: "none" }}
            >
              <Download size={15} /> Xuất CSV
            </a>
          </div>
        )}
      </div>

      {/* Select Experiment Selector */}
      <div className="card" style={{ marginBottom: "1.5rem", padding: "1rem 1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "1.5rem", flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <label className="form-label" style={{ marginBottom: 0 }}>
              Chọn Thực Nghiệm:
            </label>
            <select
              className="form-control font-mono"
              style={{ width: "260px" }}
              value={selectedExpId}
              onChange={(e) => setSelectedExpId(e.target.value)}
            >
              {experiments.map((exp) => (
                <option key={exp.experiment_id} value={exp.experiment_id}>
                  {exp.experiment_id} ({exp.config?.mode || "L"}, {exp.status})
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <label className="form-label" style={{ marginBottom: 0 }}>
              Lọc Truy Vấn:
            </label>
            <select
              className="form-control font-mono"
              style={{ width: "160px" }}
              value={selectedQuery}
              onChange={(e) => setSelectedQuery(e.target.value)}
            >
              <option value="ALL">Toàn bộ Q1–Q8</option>
              {queryKeys.map((q) => (
                <option key={q} value={q}>
                  {q}
                </option>
              ))}
            </select>
          </div>

          {/* Quick Win/Loss Counter */}
          {summary && (
            <div
              style={{
                marginLeft: "auto",
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                fontSize: "0.85rem",
              }}
            >
              <Trophy size={16} color="var(--warning)" />
              <span>Tỷ số thắng:</span>
              <span className="badge badge-info">PG: {pgWins}</span>
              <span className="badge badge-success">Mongo: {mongoWins}</span>
            </div>
          )}
        </div>
      </div>

      {errorMsg && (
        <div className="banner banner-warning" style={{ color: "var(--danger)" }}>
          <AlertTriangle size={16} /> {errorMsg}
        </div>
      )}

      {loading && (
        <div style={{ marginBottom: "2rem" }}>
          <CardSkeleton />
        </div>
      )}

      {/* Main Charts & Visualizations */}
      {summary && !loading && (
        <>
          {/* Chart Tabs */}
          <div className="card" style={{ marginBottom: "2rem" }}>
            <div className="card-header" style={{ flexWrap: "wrap", gap: "1rem" }}>
              <div className="tabs" style={{ marginBottom: 0, paddingBottom: 0 }}>
                <button
                  className={`tab-btn ${activeChartTab === "bar" ? "active" : ""}`}
                  onClick={() => setActiveChartTab("bar")}
                >
                  <BarChart3 size={15} /> Biểu Đồ Độ Trễ (Bar Chart)
                </button>
                <button
                  className={`tab-btn ${activeChartTab === "radar" ? "active" : ""}`}
                  onClick={() => setActiveChartTab("radar")}
                >
                  <Activity size={15} /> Hồ Sơ Năng Lực (Radar)
                </button>
                <button
                  className={`tab-btn ${activeChartTab === "qps" ? "active" : ""}`}
                  onClick={() => setActiveChartTab("qps")}
                >
                  <TrendingUp size={15} /> Thông Lượng QPS
                </button>
                <button
                  className={`tab-btn ${activeChartTab === "resources" ? "active" : ""}`}
                  onClick={() => setActiveChartTab("resources")}
                >
                  <Cpu size={15} /> Tiêu Thụ Tài Nguyên ({resources.length})
                </button>
              </div>

              {/* Percentile Selector (Only visible for Bar Chart) */}
              {activeChartTab === "bar" && (
                <div style={{ display: "flex", gap: "0.3rem" }}>
                  {(["p50", "p90", "p95", "p99"] as const).map((p) => (
                    <button
                      key={p}
                      className={`btn ${
                        selectedPercentile === p ? "btn-primary" : "btn-secondary"
                      }`}
                      style={{ padding: "0.25rem 0.6rem", fontSize: "0.75rem" }}
                      onClick={() => setSelectedPercentile(p)}
                    >
                      {p.toUpperCase()}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Tab 1: Latency Bar Chart */}
            {activeChartTab === "bar" && (
              <div style={{ padding: "0.5rem 0" }}>
                <BenchBarChart
                  data={barChartData}
                  title={`So sánh ${selectedPercentile.toUpperCase()} Latency (ms) giữa PostgreSQL 17.2 và MongoDB 8.0.4`}
                  height={380}
                />
              </div>
            )}

            {/* Tab 2: Radar Chart */}
            {activeChartTab === "radar" && (
              <div style={{ padding: "0.5rem 0" }}>
                <BenchRadarChart
                  data={radarChartData}
                  title="Hồ sơ năng lực tổng thể theo loại truy vấn (Điểm số chuẩn hóa 0-100)"
                  height={380}
                />
              </div>
            )}

            {/* Tab 3: QPS Throughput Line/Bar Chart */}
            {activeChartTab === "qps" && (
              <div style={{ padding: "0.5rem 0" }}>
                <BenchLineChart
                  data={qpsChartData}
                  title="Thông lượng truy vấn (Queries Per Second - QPS)"
                  yAxisLabel="QPS"
                  yAxisUnit=" qps"
                  height={380}
                />
              </div>
            )}

            {/* Tab 4: System Resource Monitor */}
            {activeChartTab === "resources" && (
              <div style={{ padding: "0.5rem 0" }}>
                {resources.length === 0 ? (
                  <div style={{ textAlign: "center", color: "var(--text-muted)", padding: "2rem" }}>
                    Chưa có snapshot tài nguyên trong đợt đo này.
                  </div>
                ) : (
                  <div className="table-wrapper">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Thời Điểm (UTC)</th>
                          <th>CPU Đã Dùng (%)</th>
                          <th>Bộ Nhớ RAM (MB)</th>
                          <th>Quota Giới Hạn</th>
                        </tr>
                      </thead>
                      <tbody>
                        {resources.slice(0, 10).map((r, idx) => (
                          <tr key={idx}>
                            <td className="font-mono" style={{ fontSize: "0.75rem" }}>
                              {r.timestamp_utc?.split("T")[1]?.slice(0, 8) || "—"}
                            </td>
                            <td>
                              <strong>{r.cpu_percent?.toFixed(1) ?? "—"}%</strong>
                            </td>
                            <td>
                              <strong>{r.memory_mb?.toFixed(1) ?? "—"} MB</strong>
                            </td>
                            <td style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
                              2048 MB / 2.0 vCPU
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Detailed Performance Metrics Table */}
          <div className="card" style={{ marginBottom: "2rem" }}>
            <div className="card-header">
              <span className="card-title">
                <BarChart3 size={18} /> Bảng Thống Kê Chi Tiết & Paired Bootstrap 95% CI
              </span>
              <span className="badge badge-info">
                Mode {summary.config?.mode || "L"} — Dataset: {summary.config?.dataset}
              </span>
            </div>

            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Truy Vấn</th>
                    <th>CSDL (Engine)</th>
                    <th style={{ textAlign: "right" }}>p50 (ms)</th>
                    <th style={{ textAlign: "right" }}>p90 (ms)</th>
                    <th style={{ textAlign: "right" }}>p95 (ms)</th>
                    <th style={{ textAlign: "right" }}>p99 (ms)</th>
                    <th style={{ textAlign: "right" }}>QPS</th>
                    <th style={{ textAlign: "right" }}>Tỷ lệ lỗi</th>
                    <th>95% Bootstrap CI (PG - Mongo)</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredQueries.map((qId) => {
                    const qData = summary.queries[qId];
                    if (!qData) return null;
                    const pg = qData.postgresql;
                    const mongo = qData.mongodb;
                    const boot = qData.comparison?.paired_bootstrap;
                    const pgP50 = pg?.p50_ms ?? 0;
                    const mongoP50 = mongo?.p50_ms ?? 0;
                    const pgWinsQuery = pgP50 > 0 && mongoP50 > 0 && pgP50 < mongoP50;
                    const mongoWinsQuery = pgP50 > 0 && mongoP50 > 0 && mongoP50 < pgP50;

                    return (
                      <React.Fragment key={qId}>
                        <tr>
                          <td rowSpan={2} style={{ verticalAlign: "middle", fontWeight: 700 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                              <span className="font-mono">{qId}</span>
                              {pgWinsQuery && (
                                <span className="badge badge-info" style={{ fontSize: "0.6rem" }}>
                                  PG nhanh hơn
                                </span>
                              )}
                              {mongoWinsQuery && (
                                <span className="badge badge-success" style={{ fontSize: "0.6rem" }}>
                                  Mongo nhanh hơn
                                </span>
                              )}
                            </div>
                          </td>
                          <td style={{ color: "var(--pg-color)", fontWeight: 600 }}>
                            PostgreSQL
                          </td>
                          <td
                            style={{
                              textAlign: "right",
                              fontWeight: pgWinsQuery ? 700 : 400,
                              color: pgWinsQuery ? "var(--pg-color)" : "inherit",
                            }}
                          >
                            {pg?.p50_ms?.toFixed(3) ?? "—"}
                          </td>
                          <td style={{ textAlign: "right" }}>{pg?.p90_ms?.toFixed(3) ?? "—"}</td>
                          <td style={{ textAlign: "right" }}>{pg?.p95_ms?.toFixed(3) ?? "—"}</td>
                          <td style={{ textAlign: "right" }}>{pg?.p99_ms?.toFixed(3) ?? "—"}</td>
                          <td style={{ textAlign: "right", fontWeight: 600 }}>
                            {pg?.throughput_qps ?? "—"}
                          </td>
                          <td style={{ textAlign: "right" }}>{pg?.error_rate_pct ?? 0}%</td>
                          <td rowSpan={2} style={{ verticalAlign: "middle", fontSize: "0.8rem" }}>
                            {boot ? (
                              <div>
                                <div>
                                  Diff: <strong>{boot.diff_median_ms} ms</strong>
                                </div>
                                <div style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                                  [{boot.ci_95_lower_ms} ~ {boot.ci_95_upper_ms} ms]
                                </div>
                                <span
                                  className="badge badge-warning"
                                  style={{ fontSize: "0.65rem", marginTop: "2px" }}
                                >
                                  {boot.note}
                                </span>
                              </div>
                            ) : (
                              "Chưa đo"
                            )}
                          </td>
                        </tr>
                        <tr>
                          <td style={{ color: "var(--mongo-color)", fontWeight: 600 }}>
                            MongoDB
                          </td>
                          <td
                            style={{
                              textAlign: "right",
                              fontWeight: mongoWinsQuery ? 700 : 400,
                              color: mongoWinsQuery ? "var(--mongo-color)" : "inherit",
                            }}
                          >
                            {mongo?.p50_ms?.toFixed(3) ?? "—"}
                          </td>
                          <td style={{ textAlign: "right" }}>{mongo?.p90_ms?.toFixed(3) ?? "—"}</td>
                          <td style={{ textAlign: "right" }}>{mongo?.p95_ms?.toFixed(3) ?? "—"}</td>
                          <td style={{ textAlign: "right" }}>{mongo?.p99_ms?.toFixed(3) ?? "—"}</td>
                          <td style={{ textAlign: "right", fontWeight: 600 }}>
                            {mongo?.throughput_qps ?? "—"}
                          </td>
                          <td style={{ textAlign: "right" }}>{mongo?.error_rate_pct ?? 0}%</td>
                        </tr>
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
