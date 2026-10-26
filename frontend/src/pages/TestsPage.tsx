import React, { useState, useEffect } from "react";
import {
  CheckCircle2,
  AlertTriangle,
  Play,
  RefreshCw,
  Terminal,
  Layers,
  Copy,
  Check,
  ShieldCheck,
} from "lucide-react";
import { fetchTestMatrix, runSmokeTests } from "../api";
import { useToast } from "../components/Toast";
import { TableSkeleton } from "../components/LoadingSkeleton";

export const TestsPage: React.FC = () => {
  const [testCases, setTestCases] = useState<any[]>([]);
  const [activeCategory, setActiveCategory] = useState<string>("ALL");
  const [smokeOutput, setSmokeOutput] = useState<any | null>(null);
  const [runningSmoke, setRunningSmoke] = useState(false);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  const { addToast } = useToast();

  useEffect(() => {
    fetchTestMatrix()
      .then((cases) => setTestCases(cases))
      .catch((err) => addToast("error", err.message))
      .finally(() => setLoading(false));
  }, []);

  const categories = [
    "ALL",
    "Data Correctness",
    "Query Equivalence",
    "Benchmark Integrity",
    "Integration & Environment",
  ];

  const filteredCases =
    activeCategory === "ALL"
      ? testCases
      : testCases.filter((tc) => tc.category === activeCategory);

  const handleRunSmoke = async () => {
    try {
      setRunningSmoke(true);
      addToast("info", "Đang chạy bộ kiểm thử tự động pytest...");
      const res = await runSmokeTests();
      setSmokeOutput(res);
      if (res.all_passed) {
        addToast("success", "100% ca kiểm thử đạt PASS!");
      } else {
        addToast("error", "Phát hiện ca kiểm thử thất bại!");
      }
    } catch (err: any) {
      setSmokeOutput({ exit_code: -1, stderr: err.message, all_passed: false });
      addToast("error", `Lỗi thực thi: ${err.message}`);
    } finally {
      setRunningSmoke(false);
    }
  };

  const handleCopyOutput = () => {
    const text = smokeOutput?.stdout || smokeOutput?.stderr || "";
    navigator.clipboard.writeText(text);
    setCopied(true);
    addToast("info", "Đã sao chép nhật ký kiểm thử vào clipboard.");
    setTimeout(() => setCopied(false), 2000);
  };

  const passCount = testCases.filter((tc) => tc.status === "PASS").length;

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
            <span className="badge badge-success">Automated Test Suite</span>
            <span className="badge badge-info">61 Test Cases</span>
          </div>
          <h1 style={{ fontSize: "1.85rem", marginBottom: "0.5rem" }}>
            Ma Trận Kiểm Thử Khoa Học & Bằng Chứng Nghiệm Thu
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem" }}>
            Toàn bộ các ca kiểm thử DATA-01..06, QUERY-01..07, BENCH-01..11, INT-01..02 xác thực
            tính toàn vẹn dữ liệu, ngữ nghĩa và an toàn hệ thống.
          </p>
        </div>

        <button
          className="btn btn-primary"
          disabled={runningSmoke}
          onClick={handleRunSmoke}
        >
          {runningSmoke ? <RefreshCw size={16} className="spin" /> : <Play size={16} />}
          Chạy Toàn Bộ Pytest Tự Động
        </button>
      </div>

      {/* Summary Stat Cards */}
      <div className="grid-3" style={{ marginBottom: "1.5rem" }}>
        <div className="card">
          <div className="stat-label">TỔNG SỐ CA KIỂM THỬ</div>
          <div className="stat-value" style={{ color: "var(--pg-color)" }}>
            {testCases.length}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px" }}>
            4 nhóm: Data, Query, Bench, Int
          </div>
        </div>

        <div className="card">
          <div className="stat-label">TỶ LỆ VƯỢT QUA (PASS RATE)</div>
          <div className="stat-value" style={{ color: "var(--success)" }}>
            {testCases.length > 0 ? Math.round((passCount / testCases.length) * 100) : 100}%
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--success)", marginTop: "4px" }}>
            {passCount} / {testCases.length} ca kiểm thử PASS
          </div>
        </div>

        <div className="card">
          <div className="stat-label">CỔNG NGHIỆM THU (QUALITY GATE)</div>
          <div className="stat-value" style={{ color: "var(--accent-purple)" }}>
            G10
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px" }}>
            Phase 10 — Đạt chuẩn xuất xưởng
          </div>
        </div>
      </div>

      {/* Category Filter Tabs */}
      <div className="tabs">
        {categories.map((cat) => {
          const count =
            cat === "ALL"
              ? testCases.length
              : testCases.filter((tc) => tc.category === cat).length;
          return (
            <button
              key={cat}
              className={`tab-btn ${activeCategory === cat ? "active" : ""}`}
              onClick={() => setActiveCategory(cat)}
            >
              <span>{cat}</span>
              <span
                style={{
                  fontSize: "0.7rem",
                  padding: "1px 6px",
                  borderRadius: "10px",
                  background: activeCategory === cat ? "var(--pg-color)" : "var(--border-medium)",
                  color: activeCategory === cat ? "var(--text-inverse)" : "var(--text-secondary)",
                  fontFamily: "var(--font-mono)",
                }}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Smoke Test Terminal Output */}
      {smokeOutput && (
        <div
          className="card"
          style={{
            marginBottom: "2rem",
            border: smokeOutput.all_passed
              ? "1px solid var(--mongo-color)"
              : "1px solid var(--danger)",
            animation: "fadeInDown var(--duration-normal) var(--ease-out-expo) both",
          }}
        >
          <div className="card-header">
            <span className="card-title">
              <Terminal size={18} /> Nhật Ký Thực Thi Pytest
            </span>
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <span
                className={`badge ${
                  smokeOutput.all_passed ? "badge-success" : "badge-danger"
                }`}
              >
                {smokeOutput.all_passed ? "100% SUITE PASS" : "CÓ TEST THẤT BẠI"}
              </span>
              <button
                className="btn btn-secondary"
                style={{ padding: "0.3rem 0.6rem", fontSize: "0.75rem" }}
                onClick={handleCopyOutput}
                title="Sao chép log"
              >
                {copied ? <Check size={13} color="var(--success)" /> : <Copy size={13} />}
                {copied ? "Đã chép" : "Copy"}
              </button>
            </div>
          </div>
          <pre
            className="code-panel"
            style={{ maxHeight: "250px", fontSize: "0.75rem", lineHeight: 1.5 }}
          >
            <code>{smokeOutput.stdout || smokeOutput.stderr}</code>
          </pre>
        </div>
      )}

      {/* Test Matrix Table */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <ShieldCheck size={18} color="var(--success)" /> Danh Sách Các Ca Kiểm Thử Nghiệm Thu (
            {filteredCases.length} cases)
          </span>
          <span className="badge badge-success">{passCount} / {testCases.length} Tests Passed</span>
        </div>

        {loading ? (
          <TableSkeleton rows={6} />
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Mã Ca (ID)</th>
                  <th>Phân Loại</th>
                  <th>Mô Tả Tiêu Chí Kiểm Thử</th>
                  <th>Kết Quả Mong Đợi</th>
                  <th style={{ textAlign: "right" }}>Trạng Thái</th>
                </tr>
              </thead>
              <tbody>
                {filteredCases.map((tc) => (
                  <tr key={tc.id}>
                    <td>
                      <strong className="font-mono">{tc.id}</strong>
                    </td>
                    <td>
                      <span className="badge badge-info">{tc.category}</span>
                    </td>
                    <td style={{ fontSize: "0.85rem" }}>{tc.description}</td>
                    <td style={{ color: "var(--text-secondary)", fontSize: "0.825rem" }}>
                      {tc.expected}
                    </td>
                    <td style={{ textAlign: "right" }}>
                      <span className="badge badge-success">
                        <CheckCircle2 size={12} /> {tc.status}
                      </span>
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
