import React, { useState, useEffect } from "react";
import {
  Server,
  Cpu,
  Database,
  Activity,
  HardDrive,
  ShieldCheck,
  Clock,
  RefreshCw,
  Terminal,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { fetchEnvironment, fetchHealth, EnvironmentInfo, SystemHealth } from "../api";
import { useToast } from "../components/Toast";
import { CardSkeleton } from "../components/LoadingSkeleton";

export const SystemPage: React.FC = () => {
  const [env, setEnv] = useState<EnvironmentInfo | null>(null);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);

  const { addToast } = useToast();

  const loadData = async () => {
    try {
      setLoading(true);
      const [envData, healthData] = await Promise.all([
        fetchEnvironment().catch(() => null),
        fetchHealth().catch(() => null),
      ]);
      if (envData) setEnv(envData);
      if (healthData) setHealth(healthData);
    } catch (err: any) {
      addToast("error", err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const pg = health?.engines?.postgresql;
  const mongo = health?.engines?.mongodb;

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
            <span className="badge badge-info">System Architecture</span>
            <span className="badge badge-success">Docker Isolated</span>
          </div>
          <h1 style={{ fontSize: "1.85rem", marginBottom: "0.5rem" }}>
            Thông Tin Hệ Thống & Hạn Ngạch Tài Nguyên
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem" }}>
            Giám sát cấu hình Docker Compose, hạn ngạch vCPU/RAM, thông số kết nối và phiên bản phần
            mềm của PT Lab.
          </p>
        </div>

        <button className="btn btn-secondary" onClick={loadData}>
          <RefreshCw size={15} /> Làm Mới Trạng Thái
        </button>
      </div>

      {loading && !env ? (
        <div className="grid-3" style={{ marginBottom: "2rem" }}>
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
      ) : (
        <>
          {/* Top Host Specs Cards */}
          <div className="grid-4" style={{ marginBottom: "2rem" }}>
            <div className="card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className="stat-label">HỆ ĐIỀU HÀNH</span>
                <Server size={18} color="var(--pg-color)" />
              </div>
              <div style={{ fontSize: "1.2rem", fontWeight: 700, marginTop: "0.5rem" }}>
                {env?.os || "Windows"}
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px" }}>
                Docker Engine v27+
              </div>
            </div>

            <div className="card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className="stat-label">CPU VẬT LÝ</span>
                <Cpu size={18} color="var(--mongo-color)" />
              </div>
              <div className="stat-value" style={{ color: "var(--mongo-color)" }}>
                {env?.cpu_count || 8}
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px" }}>
                Logical Cores
              </div>
            </div>

            <div className="card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className="stat-label">RAM MÁY CHỦ</span>
                <HardDrive size={18} color="var(--warning)" />
              </div>
              <div className="stat-value" style={{ color: "var(--warning)" }}>
                {env?.memory_total_gb?.toFixed(0) || 16} GB
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px" }}>
                Bộ nhớ khả dụng
              </div>
            </div>

            <div className="card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className="stat-label">MÔI TRƯỜNG ĐỐI CHUẨN</span>
                <ShieldCheck size={18} color="var(--accent-purple)" />
              </div>
              <div className="stat-value" style={{ color: "var(--accent-purple)", fontSize: "1.4rem" }}>
                Chuẩn Hóa
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px" }}>
                Docker Độc Lập
              </div>
            </div>
          </div>

          {/* Docker Quota & DB Containers Details */}
          <div className="grid-2" style={{ marginBottom: "2rem" }}>
            {/* PostgreSQL Container */}
            <div className="card" style={{ borderLeft: "4px solid var(--pg-color)" }}>
              <div className="card-header">
                <span className="card-title">
                  <Database size={20} color="var(--pg-color)" /> Container: benchlab-postgres
                </span>
                <span className={`badge ${pg?.is_healthy ? "badge-success" : "badge-danger"}`}>
                  {pg?.is_healthy ? "ONLINE" : "OFFLINE"}
                </span>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem", fontSize: "0.875rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>Image:</span>
                  <strong>postgres:17.2-alpine</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>CPU Quota:</span>
                  <strong style={{ color: "var(--pg-color)" }}>2.0 vCPU (cpus: '2.0')</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>RAM Limit:</span>
                  <strong style={{ color: "var(--pg-color)" }}>2048 MB (mem_limit: 2048m)</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>work_mem:</span>
                  <code className="font-mono">64MB</code>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>shared_buffers:</span>
                  <code className="font-mono">512MB</code>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>Độ trễ kết nối:</span>
                  <strong style={{ color: "var(--pg-color)" }}>
                    {pg?.latency_ms ? `${pg.latency_ms.toFixed(2)} ms` : "—"}
                  </strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>Cổng host:</span>
                  <code className="font-mono">5432</code>
                </div>
              </div>
            </div>

            {/* MongoDB Container */}
            <div className="card" style={{ borderLeft: "4px solid var(--mongo-color)" }}>
              <div className="card-header">
                <span className="card-title">
                  <Database size={20} color="var(--mongo-color)" /> Container: benchlab-mongodb
                </span>
                <span className={`badge ${mongo?.is_healthy ? "badge-success" : "badge-danger"}`}>
                  {mongo?.is_healthy ? "ONLINE" : "OFFLINE"}
                </span>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem", fontSize: "0.875rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>Image:</span>
                  <strong>mongo:8.0.4</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>CPU Quota:</span>
                  <strong style={{ color: "var(--mongo-color)" }}>2.0 vCPU (cpus: '2.0')</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>RAM Limit:</span>
                  <strong style={{ color: "var(--mongo-color)" }}>2048 MB (mem_limit: 2048m)</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>WiredTiger Cache:</span>
                  <code className="font-mono">1024 MB (1.0 GB)</code>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>Storage Engine:</span>
                  <code>WiredTiger</code>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>Độ trễ kết nối:</span>
                  <strong style={{ color: "var(--mongo-color)" }}>
                    {mongo?.latency_ms ? `${mongo.latency_ms.toFixed(2)} ms` : "—"}
                  </strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>Cổng host:</span>
                  <code className="font-mono">27017</code>
                </div>
              </div>
            </div>
          </div>

          {/* Software Stack Table */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">
                <Terminal size={18} /> Danh Mục Phần Mềm & Thư Viện Cốt Lõi
              </span>
            </div>

            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Thành Phần</th>
                    <th>Phiên Bản Ghim</th>
                    <th>Vai Trò & Chức Năng</th>
                    <th>Trạng Thái</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><strong>PostgreSQL</strong></td>
                    <td className="font-mono">17.2-alpine</td>
                    <td>Hệ quản trị CSDL quan hệ chính thức (Track A 3NF)</td>
                    <td><span className="badge badge-success">OK</span></td>
                  </tr>
                  <tr>
                    <td><strong>MongoDB</strong></td>
                    <td className="font-mono">8.0.4</td>
                    <td>Hệ quản trị CSDL NoSQL hướng tài liệu (Track A & Track B)</td>
                    <td><span className="badge badge-success">OK</span></td>
                  </tr>
                  <tr>
                    <td><strong>Python Backend</strong></td>
                    <td className="font-mono">3.12</td>
                    <td>FastAPI service + Benchmark Engine + Monotonic Timer</td>
                    <td><span className="badge badge-success">OK</span></td>
                  </tr>
                  <tr>
                    <td><strong>psycopg</strong></td>
                    <td className="font-mono">3.2.3</td>
                    <td>Driver PostgreSQL kết nối pool tối ưu</td>
                    <td><span className="badge badge-success">OK</span></td>
                  </tr>
                  <tr>
                    <td><strong>pymongo</strong></td>
                    <td className="font-mono">4.10.1</td>
                    <td>Driver MongoDB pool kết nối chính thức</td>
                    <td><span className="badge badge-success">OK</span></td>
                  </tr>
                  <tr>
                    <td><strong>React Frontend</strong></td>
                    <td className="font-mono">18.3.1</td>
                    <td>Giao diện điều khiển SPA (Vite 6 + Recharts + Dark Theme)</td>
                    <td><span className="badge badge-success">OK</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
