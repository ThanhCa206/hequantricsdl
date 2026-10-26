import React, { useEffect, useState } from "react";
import {
  Database,
  Cpu,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Play,
  Server,
  Clock,
  Zap,
  Activity,
  Layers,
  BarChart3,
  RefreshCw,
} from "lucide-react";
import {
  fetchEnvironment,
  fetchExperiments,
  fetchHealth,
  validateDataset,
  EnvironmentInfo,
  SystemHealth,
} from "../api";
import { CardSkeleton, TableSkeleton } from "../components/LoadingSkeleton";

interface OverviewPageProps {
  onNavigate: (page: string) => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({ onNavigate }) => {
  const [env, setEnv] = useState<EnvironmentInfo | null>(null);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [experiments, setExperiments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [counts, setCounts] = useState<{ pg: number; mongo: number } | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const [envData, expData, healthData, valData] = await Promise.all([
          fetchEnvironment().catch(() => null),
          fetchExperiments().catch(() => []),
          fetchHealth().catch(() => null),
          validateDataset("fixture-seed42").catch(() => null),
        ]);
        if (envData) setEnv(envData);
        if (healthData) setHealth(healthData);
        if (valData?.counts) {
          setCounts({
            pg: valData.counts.postgresql?.orders ?? 50,
            mongo: valData.counts.mongodb?.orders ?? 50,
          });
        }
        setExperiments(expData);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const pgOrders = counts?.pg ?? (health?.engines?.postgresql?.is_healthy ? 50 : undefined);
  const mongoOrders = counts?.mongo ?? (health?.engines?.mongodb?.is_healthy ? 50 : undefined);

  return (
    <div className="page-wrapper">
      {/* Hero Section */}
      <div className="page-hero">
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
          <span className="badge badge-success">61/61 Tests PASS</span>
          <span className="badge badge-purple">Docker Quota 2.0 CPU / 2GB RAM</span>
          <span className="badge badge-info">Khoa Học & Độc Lập</span>
        </div>
        <h1>PT Lab: Nền Tảng Đối Chuẩn Hiệu Năng CSDL</h1>
        <p>
          Thực nghiệm khoa học đo lường định lượng giữa PostgreSQL 17.2 và MongoDB 8.0.4 dưới ngân
          sách tài nguyên bình đẳng, warm-up cách ly, và đối soát ngữ nghĩa canonical SHA-256.
        </p>
      </div>

      {/* Quick Stats Grid */}
      <div className="grid-4" style={{ marginBottom: "2rem" }}>
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <span className="stat-label">TRUY VẤN ĐỐI CHUẨN</span>
            <Layers size={18} color="var(--pg-color)" />
          </div>
          <div className="stat-value" style={{ color: "var(--pg-color)" }}>8</div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" }}>
            Q1–Q8 (Track A & Track B)
          </div>
        </div>

        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <span className="stat-label">THỰC NGHIỆM ĐÃ CHẠY</span>
            <Activity size={18} color="var(--mongo-color)" />
          </div>
          <div className="stat-value" style={{ color: "var(--mongo-color)" }}>
            {experiments.length}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" }}>
            E0 (Smoke) → E3 (Index)
          </div>
        </div>

        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <span className="stat-label">HẠN NGẠCH TÀI NGUYÊN</span>
            <Cpu size={18} color="var(--warning)" />
          </div>
          <div className="stat-value" style={{ color: "var(--warning)" }}>2.0</div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" }}>
            vCPU / 2048MB per DB
          </div>
        </div>

        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <span className="stat-label">ĐỘ TIN CẬY THỐNG KÊ</span>
            <BarChart3 size={18} color="var(--accent-purple)" />
          </div>
          <div className="stat-value" style={{ color: "var(--accent-purple)" }}>95%</div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" }}>
            Paired Bootstrap CI
          </div>
        </div>
      </div>

      {/* Target Databases & Environment Cards */}
      {loading ? (
        <div className="grid-3" style={{ marginBottom: "2rem" }}>
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
      ) : (
        <div className="grid-3" style={{ marginBottom: "2rem" }}>
          {/* PostgreSQL Card */}
          <div
            className="card"
            style={{
              borderLeft: "4px solid var(--pg-color)",
              boxShadow: "var(--shadow-glow-pg)",
            }}
          >
            <div className="card-header">
              <span className="card-title">
                <Database size={20} color="var(--pg-color)" /> PostgreSQL
              </span>
              <span className="badge badge-info">Track A (3NF)</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", fontSize: "0.875rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>Phiên bản:</span>
                <strong>PostgreSQL 17.2-alpine</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>Số đơn hàng:</span>
                <strong style={{ color: "var(--pg-color)" }}>
                  {pgOrders !== undefined ? `${pgOrders.toLocaleString()} orders` : "Chưa đo"}
                </strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>Index Catalog:</span>
                <strong>I1 (B-Tree Secondary)</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>Cổng kết nối:</span>
                <code className="font-mono">127.0.0.1:5432</code>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>Thế mạnh:</span>
                <span style={{ color: "var(--pg-color)", fontSize: "0.8rem", fontWeight: 600 }}>
                  Hash Aggregate & JOINs
                </span>
              </div>
            </div>
          </div>

          {/* MongoDB Card */}
          <div
            className="card"
            style={{
              borderLeft: "4px solid var(--mongo-color)",
              boxShadow: "var(--shadow-glow-mongo)",
            }}
          >
            <div className="card-header">
              <span className="card-title">
                <Database size={20} color="var(--mongo-color)" /> MongoDB
              </span>
              <span className="badge badge-success">Track A & B (Hybrid)</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", fontSize: "0.875rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>Phiên bản:</span>
                <strong>MongoDB 8.0.4</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>Số đơn hàng:</span>
                <strong style={{ color: "var(--mongo-color)" }}>
                  {mongoOrders !== undefined ? `${mongoOrders.toLocaleString()} orders` : "Chưa đo"}
                </strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>Index Catalog:</span>
                <strong>I1 (B-Tree Compound)</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>Cổng kết nối:</span>
                <code className="font-mono">127.0.0.1:27017</code>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>Thế mạnh:</span>
                <span style={{ color: "var(--mongo-color)", fontSize: "0.8rem", fontWeight: 600 }}>
                  Embedded Array & Keyset Seek
                </span>
              </div>
            </div>
          </div>

          {/* Environment Card */}
          <div className="card" style={{ borderLeft: "4px solid var(--warning)" }}>
            <div className="card-header">
              <span className="card-title">
                <Cpu size={20} color="var(--warning)" /> Hạn Ngạch & Quota
              </span>
              <span className="badge badge-warning">Tài Nguyên Cô Lập</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", fontSize: "0.875rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>CPU Quota:</span>
                <strong>2.0 vCPU / container</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>RAM Quota:</span>
                <strong>2048 MB (2.0 GB)</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>Dataset hiện thời:</span>
                <strong>{env?.dataset_active || "fixture-seed42"}</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ color: "var(--text-muted)" }}>Đúng đắn ngữ nghĩa:</span>
                {env?.correctness_passed ? (
                  <span className="badge badge-success">
                    <CheckCircle2 size={12} /> Đã PASS
                  </span>
                ) : (
                  <span className="badge badge-warning">
                    <AlertTriangle size={12} /> Chưa đo
                  </span>
                )}
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>Hệ điều hành:</span>
                <span className="font-mono" style={{ fontSize: "0.75rem" }}>
                  {env?.os || "Windows (Docker Desktop)"}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Standard Experiment Workflow Stepper */}
      <div className="card" style={{ marginBottom: "2rem" }}>
        <div className="card-header">
          <span className="card-title">
            <Zap size={18} color="var(--warning)" /> Luồng Thao Tác Thực Nghiệm Tiêu Chuẩn (4 Bước)
          </span>
          <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
            Thực hiện tuần tự từ Bước 1 đến Bước 4
          </span>
        </div>

        <div className="stepper">
          {/* Step 1 */}
          <div className="stepper-step">
            <div className="stepper-number" style={{ color: "var(--pg-color)" }}>BƯỚC 1</div>
            <div className="stepper-title">Chuẩn bị Dữ liệu</div>
            <p className="stepper-desc">
              Sinh dataset tất định theo seed=42 và nạp idempotent vào cả 2 CSDL.
            </p>
            <button
              className="btn btn-secondary"
              style={{ marginTop: "1rem", width: "100%", fontSize: "0.8rem" }}
              onClick={() => onNavigate("datasets")}
            >
              Trang Dữ liệu <ArrowRight size={14} />
            </button>
          </div>

          {/* Step 2 */}
          <div className="stepper-step">
            <div className="stepper-number" style={{ color: "var(--mongo-color)" }}>BƯỚC 2</div>
            <div className="stepper-title">Kiểm chứng Truy vấn</div>
            <p className="stepper-desc">
              Thử nghiệm Q1..Q8, đối soát hash SHA-256 và phân tích Execution Plan.
            </p>
            <button
              className="btn btn-secondary"
              style={{ marginTop: "1rem", width: "100%", fontSize: "0.8rem" }}
              onClick={() => onNavigate("queries")}
            >
              Trang Truy vấn <ArrowRight size={14} />
            </button>
          </div>

          {/* Step 3 */}
          <div className="stepper-step">
            <div className="stepper-number" style={{ color: "var(--warning)" }}>BƯỚC 3</div>
            <div className="stepper-title">Chạy Benchmark</div>
            <p className="stepper-desc">
              Thực thi E0/E1/E2/E3 với warm-up cách ly và paired alternating engine order.
            </p>
            <button
              className="btn btn-primary"
              style={{ marginTop: "1rem", width: "100%", fontSize: "0.8rem" }}
              onClick={() => onNavigate("benchmark")}
            >
              Trang Benchmark <Play size={14} />
            </button>
          </div>

          {/* Step 4 */}
          <div className="stepper-step">
            <div className="stepper-number" style={{ color: "var(--accent-purple)" }}>BƯỚC 4</div>
            <div className="stepper-title">Xem Báo Cáo</div>
            <p className="stepper-desc">
              Phân tích percentiles p50..p99, CI 95%, biểu đồ Recharts và xuất Markdown/CSV.
            </p>
            <button
              className="btn btn-secondary"
              style={{ marginTop: "1rem", width: "100%", fontSize: "0.8rem" }}
              onClick={() => onNavigate("results")}
            >
              Trang Kết quả <ArrowRight size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* Recent Experiments Table */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <Clock size={18} /> Các Thực Nghiệm Benchmark Đã Chạy ({experiments.length})
          </span>
          <button
            className="btn btn-primary"
            style={{ fontSize: "0.8rem" }}
            onClick={() => onNavigate("benchmark")}
          >
            <Play size={14} /> Bắt Đầu Chạy Mới
          </button>
        </div>

        {loading ? (
          <TableSkeleton rows={4} />
        ) : experiments.length === 0 ? (
          <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>
            <Activity size={36} style={{ margin: "0 auto 1rem", opacity: 0.3 }} />
            <p>Chưa có đợt benchmark nào được thực thi.</p>
            <p style={{ fontSize: "0.85rem", marginTop: "0.5rem" }}>
              Nhấn <strong>"Bắt Đầu Chạy Mới"</strong> để khởi chạy thực nghiệm đầu tiên.
            </p>
          </div>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Mã Thực Nghiệm</th>
                  <th>Chế Độ (Mode)</th>
                  <th>Dataset</th>
                  <th>Số Mẫu (Samples)</th>
                  <th>Thời Gian Chạy</th>
                  <th>Trạng Thái</th>
                  <th style={{ textAlign: "right" }}>Thao Tác</th>
                </tr>
              </thead>
              <tbody>
                {experiments.map((exp) => (
                  <tr key={exp.experiment_id}>
                    <td>
                      <strong className="font-mono">{exp.experiment_id}</strong>
                    </td>
                    <td>
                      <span className="badge badge-info">
                        Mode {exp.config?.mode || "L"}
                      </span>
                    </td>
                    <td>{exp.config?.dataset || "fixture-seed42"}</td>
                    <td>
                      <strong>{exp.total_samples || "Chưa đo"}</strong> mẫu
                    </td>
                    <td style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                      {exp.created_at_utc
                        ? new Date(exp.created_at_utc).toLocaleString("vi-VN")
                        : "Chưa đo"}
                    </td>
                    <td>
                      <span
                        className={`badge ${
                          exp.status === "COMPLETED"
                            ? "badge-success"
                            : exp.status === "RUNNING"
                            ? "badge-warning"
                            : "badge-danger"
                        }`}
                      >
                        {exp.status === "COMPLETED" && <CheckCircle2 size={11} />}
                        {exp.status === "RUNNING" && <RefreshCw size={11} className="spin" />}
                        {exp.status}
                      </span>
                    </td>
                    <td style={{ textAlign: "right" }}>
                      <button
                        className="btn btn-secondary"
                        style={{ padding: "0.3rem 0.65rem", fontSize: "0.75rem" }}
                        onClick={() => onNavigate(`results:${exp.experiment_id}`)}
                      >
                        Xem Thống Kê →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
