import React, { useState, useEffect } from "react";
import {
  PlayCircle,
  StopCircle,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Zap,
  Activity,
  ArrowRight,
  Sparkles,
} from "lucide-react";
import {
  fetchBenchmarkStatus,
  dryRunBenchmark,
  startBenchmark,
  cancelBenchmark,
  BenchmarkStatus,
} from "../api";
import { ProgressRing } from "../components/ProgressRing";
import { useToast } from "../components/Toast";

interface BenchmarkPageProps {
  onNavigate?: (page: string) => void;
}

export const BenchmarkPage: React.FC<BenchmarkPageProps> = ({ onNavigate }) => {
  const [experimentPreset, setExperimentPreset] = useState("E0");
  const [experimentId, setExperimentId] = useState(`E0-smoke-${Date.now().toString().slice(-4)}`);
  const [mode, setMode] = useState<"L" | "T">("L");
  const [dataset, setDataset] = useState("fixture-seed42");
  const [profile, setProfile] = useState("fixture");
  const [indexProfile, setIndexProfile] = useState<"I0" | "I1">("I1");
  const [concurrency, setConcurrency] = useState(1);
  const [repeats, setRepeats] = useState(1);
  const [fixedCount, setFixedCount] = useState(20);
  const [durationSeconds, setDurationSeconds] = useState(30.0);
  const [warmupMinReqs, setWarmupMinReqs] = useState(5);
  const [warmupMinDuration, setWarmupMinDuration] = useState(0.2);

  const [status, setStatus] = useState<BenchmarkStatus | null>(null);
  const [dryRunInfo, setDryRunInfo] = useState<any | null>(null);
  const [loadingAction, setLoadingAction] = useState<string | null>(null);

  const { addToast } = useToast();

  useEffect(() => {
    let isMounted = true;
    const poll = async () => {
      try {
        const s = await fetchBenchmarkStatus();
        if (isMounted) setStatus(s);
      } catch (err) {}
    };
    poll();
    const interval = setInterval(poll, 800);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const presets: Record<
    string,
    { label: string; desc: string; mode: "L" | "T"; dataset: string; repeats: number; count: number }
  > = {
    E0: {
      label: "E0 (Smoke Fixture)",
      desc: "Chạy thử nhanh 20 reqs / seed 42",
      mode: "L",
      dataset: "fixture-seed42",
      repeats: 1,
      count: 20,
    },
    E1: {
      label: "E1 (Small Latency)",
      desc: "Nghiệm thu chuẩn 10,000 đơn hàng, 5 repeats",
      mode: "L",
      dataset: "small-seed42",
      repeats: 5,
      count: 1000,
    },
    E2: {
      label: "E2 (Concurrency T1)",
      desc: "Throughput bão hòa C=8 workers, 60 giây",
      mode: "T",
      dataset: "small-seed42",
      repeats: 3,
      count: 0,
    },
    E3: {
      label: "E3 (Index I0 vs I1)",
      desc: "Tác động chỉ mục B-Tree vs Không index",
      mode: "L",
      dataset: "small-seed42",
      repeats: 3,
      count: 500,
    },
  };

  const handlePresetChange = (preset: string) => {
    setExperimentPreset(preset);
    const ts = Date.now().toString().slice(-4);
    switch (preset) {
      case "E0":
        setExperimentId(`E0-smoke-${ts}`);
        setMode("L");
        setProfile("fixture");
        setDataset("fixture-seed42");
        setIndexProfile("I1");
        setRepeats(1);
        setFixedCount(20);
        setWarmupMinReqs(5);
        setWarmupMinDuration(0.2);
        break;
      case "E1":
        setExperimentId(`E1-latency-small-${ts}`);
        setMode("L");
        setProfile("small");
        setDataset("small-seed42");
        setIndexProfile("I1");
        setRepeats(5);
        setFixedCount(1000);
        setWarmupMinReqs(100);
        setWarmupMinDuration(20.0);
        break;
      case "E2":
        setExperimentId(`E2-concurrency-t1-${ts}`);
        setMode("T");
        setProfile("small");
        setDataset("small-seed42");
        setIndexProfile("I1");
        setConcurrency(8);
        setRepeats(3);
        setDurationSeconds(60.0);
        break;
      case "E3":
        setExperimentId(`E3-index-i0-${ts}`);
        setMode("L");
        setProfile("small");
        setDataset("small-seed42");
        setIndexProfile("I0");
        setRepeats(3);
        setFixedCount(500);
        break;
    }
  };

  const getPayload = () => ({
    experiment_id: experimentId,
    mode,
    dataset,
    profile,
    index_profile: indexProfile,
    queries: ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7_offset", "Q7_keyset", "Q8_track_a"],
    engines: ["postgresql", "mongodb"],
    repeats,
    fixed_count: fixedCount,
    concurrency,
    duration_seconds: durationSeconds,
    warmup_min_requests: warmupMinReqs,
    warmup_min_duration_s: warmupMinDuration,
    seed: 42,
  });

  const handleDryRun = async () => {
    try {
      setLoadingAction("dry-run");
      const res = await dryRunBenchmark(getPayload());
      setDryRunInfo(res);
      addToast("info", `Dry-run thành công: ${res.total_cells} cells, dự kiến ~${res.estimated_duration_s}s`);
    } catch (err: any) {
      addToast("error", err.message);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleStart = async () => {
    try {
      setLoadingAction("start");
      await startBenchmark(getPayload());
      addToast("success", `Đã bắt đầu thực nghiệm ${experimentId}!`);
      const s = await fetchBenchmarkStatus();
      setStatus(s);
    } catch (err: any) {
      addToast("error", err.message);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleCancel = async () => {
    try {
      setLoadingAction("cancel");
      await cancelBenchmark();
      addToast("warning", "Đã gửi lệnh dừng benchmark.");
      const s = await fetchBenchmarkStatus();
      setStatus(s);
    } catch (err: any) {
      addToast("error", err.message);
    } finally {
      setLoadingAction(null);
    }
  };

  const isRunning =
    status?.is_locked ||
    status?.state === "RUNNING" ||
    status?.state === "DRAINING" ||
    (status as any)?.status === "RUNNING";

  const totalCells = status?.progress?.total_cells || dryRunInfo?.total_cells || 18;
  const completedCells = status?.progress?.completed_cells ?? 0;
  const progressPercent =
    typeof (status?.progress as any)?.percent === "number"
      ? (status?.progress as any).percent
      : totalCells > 0
      ? Math.min(100, Math.round((completedCells / totalCells) * 100))
      : 0;
  const activeJobId = status?.active_job_id || (status as any)?.experiment_id || "";
  const currentStep = (status?.progress as any)?.step || (status as any)?.current_step || "";

  return (
    <div className="page-wrapper">
      {/* Page Header */}
      <div className="page-hero">
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
          <span className="badge badge-info">Benchmark Engine v2.0</span>
          <span className="badge badge-success">Paired Alternating Execution</span>
          <span className="badge badge-purple">Monotonic ns Timer</span>
        </div>
        <h1>Điều Phối & Thực Thi Benchmark Khoa Học</h1>
        <p>
          Hỗ trợ Mode L (Sequential Latency) và Mode T (Throughput Concurrency), warm-up cách ly,
          và paired engine ordering để loại trừ trôi nhiệt/JIT.
        </p>
      </div>

      {/* Real-time Benchmark Progress Display */}
      {isRunning && (
        <div
          className="card"
          style={{
            marginBottom: "2rem",
            border: "1px solid var(--border-focus)",
            background: "rgba(56, 189, 248, 0.05)",
            animation: "borderGlow 2s infinite",
          }}
        >
          <div className="card-header">
            <span className="card-title">
              <RefreshCw size={18} className="spin" color="var(--pg-color)" /> Thực Nghiệm Đang Chạy:{" "}
              <span className="font-mono">{activeJobId}</span>
            </span>
            <span className="badge badge-warning">
              {status?.state || (status as any)?.status || "RUNNING"}
            </span>
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "2rem",
              marginBottom: "1.5rem",
              flexWrap: "wrap",
            }}
          >
            {/* Animated SVG Progress Ring */}
            <ProgressRing
              progress={progressPercent}
              radius={55}
              strokeWidth={8}
              color="var(--pg-color)"
              sublabel="HOÀN TẤT"
            />

            {/* Metrics Breakdown */}
            <div style={{ flex: 1, minWidth: "250px" }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: "0.4rem",
                  fontSize: "0.85rem",
                }}
              >
                <span>
                  Tiến độ: <strong>{completedCells} / {totalCells} cells</strong>
                </span>
                <span>
                  <strong>{progressPercent}%</strong>
                </span>
              </div>
              <div className="mini-bar-track" style={{ height: "10px", marginBottom: "1rem" }}>
                <div
                  className="mini-bar-fill"
                  style={{
                    width: `${progressPercent}%`,
                    background: "linear-gradient(90deg, #38bdf8, #10b981)",
                  }}
                />
              </div>

              <div className="grid-4" style={{ fontSize: "0.85rem" }}>
                <div>
                  <span style={{ color: "var(--text-muted)" }}>Engine: </span>
                  <strong style={{ textTransform: "uppercase", color: "var(--pg-color)" }}>
                    {status?.progress?.engine || "Đang đo"}
                  </strong>
                </div>
                <div>
                  <span style={{ color: "var(--text-muted)" }}>Truy vấn: </span>
                  <strong className="font-mono">{status?.progress?.query_id || "Đang đo"}</strong>
                </div>
                <div>
                  <span style={{ color: "var(--text-muted)" }}>Repeat: </span>
                  <strong>
                    {status?.progress?.repeat ?? 1} / {status?.progress?.total_repeats ?? repeats}
                  </strong>
                </div>
                <div>
                  <span style={{ color: "var(--text-muted)" }}>Giai đoạn: </span>
                  <span className="badge badge-info">{status?.progress?.phase || "MEASURING"}</span>
                </div>
              </div>
            </div>
          </div>

          {currentStep && (
            <div
              style={{
                fontSize: "0.8rem",
                color: "var(--text-secondary)",
                padding: "0.5rem 0.75rem",
                background: "var(--bg-card)",
                border: "1px solid var(--border-light)",
                borderRadius: "6px",
                fontFamily: "var(--font-mono)",
              }}
            >
              Bước hiện tại: <span style={{ color: "var(--text-primary)" }}>{currentStep}</span>
            </div>
          )}

          <div style={{ marginTop: "1.25rem", display: "flex", justifyContent: "flex-end" }}>
            <button
              className="btn btn-danger"
              disabled={loadingAction === "cancel"}
              onClick={handleCancel}
            >
              <StopCircle size={16} /> Dừng Thực Nghiệm (Cancel & Retain Partial)
            </button>
          </div>
        </div>
      )}

      {/* Completed Banner */}
      {!isRunning &&
        (status?.state === "COMPLETED" || (status as any)?.status === "COMPLETED") && (
          <div
            className="card"
            style={{
              marginBottom: "2rem",
              border: "1px solid var(--mongo-color)",
              background: "rgba(16, 185, 129, 0.08)",
              padding: "1.25rem 1.5rem",
              animation: "fadeInDown var(--duration-normal) var(--ease-out-expo) both",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: "1rem",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                <CheckCircle2 size={28} color="var(--mongo-color)" />
                <div>
                  <strong style={{ fontSize: "1.05rem", color: "var(--mongo-color)", display: "block" }}>
                    Thực Nghiệm {activeJobId} Đã Hoàn Thành Thành Công!
                  </strong>
                  <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                    Đo toàn bộ {totalCells}/{totalCells} cells chuẩn xác. Dữ liệu phân vị p50/p90/p95/p99
                    đã sẵn sàng.
                  </span>
                </div>
              </div>
              {onNavigate && (
                <button
                  className="btn btn-primary"
                  style={{ fontSize: "0.85rem" }}
                  onClick={() => onNavigate(`results:${activeJobId}`)}
                >
                  Xem Báo Cáo & Biểu Đồ Kết Quả →
                </button>
              )}
            </div>
          </div>
        )}

      {/* Preset Cards Selector */}
      <div style={{ marginBottom: "1.5rem" }}>
        <div className="form-label" style={{ marginBottom: "0.75rem" }}>
          CHỌN KỊCH BẢN THỰC NGHIỆM CHUẨN (PRESET):
        </div>
        <div className="grid-4">
          {Object.entries(presets).map(([key, p]) => {
            const isSelected = experimentPreset === key;
            return (
              <div
                key={key}
                className="card"
                onClick={() => !isRunning && handlePresetChange(key)}
                style={{
                  cursor: isRunning ? "not-allowed" : "pointer",
                  border: isSelected
                    ? "2px solid var(--pg-color)"
                    : "1px solid var(--border-light)",
                  background: isSelected ? "var(--pg-bg)" : "var(--bg-card)",
                  opacity: isRunning ? 0.6 : 1,
                  transition: "all var(--duration-normal) var(--ease-out-expo)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.4rem" }}>
                  <strong style={{ fontSize: "0.95rem", color: isSelected ? "var(--pg-color)" : "inherit" }}>
                    {p.label}
                  </strong>
                  {isSelected && <Sparkles size={14} color="var(--pg-color)" />}
                </div>
                <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>
                  {p.desc}
                </div>
                <div style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
                  Mode {p.mode} • {p.repeats} repeats
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Configuration Form & Pre-flight Assessment Grid */}
      <div className="grid-3">
        <div className="card" style={{ gridColumn: "span 2" }}>
          <div className="card-header">
            <span className="card-title">
              <Zap size={18} /> Cấu Hình Chi Tiết Kịch Bản
            </span>
            <span className="badge badge-info">Preset: {experimentPreset}</span>
          </div>

          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">Mã thực nghiệm (Experiment ID)</label>
              <input
                type="text"
                className="form-control font-mono"
                value={experimentId}
                disabled={isRunning}
                onChange={(e) => setExperimentId(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Chế độ đo (Benchmark Mode)</label>
              <select
                className="form-control"
                value={mode}
                disabled={isRunning}
                onChange={(e) => setMode(e.target.value as "L" | "T")}
              >
                <option value="L">Mode L — Sequential Latency (Fixed-Count)</option>
                <option value="T">Mode T — Throughput Closed-Loop (Concurrency C)</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Index Profile áp dụng</label>
              <select
                className="form-control"
                value={indexProfile}
                disabled={isRunning}
                onChange={(e) => setIndexProfile(e.target.value as "I0" | "I1")}
              >
                <option value="I1">I1 (Đầy đủ Index thứ cấp — Workload)</option>
                <option value="I0">I0 (Chỉ có Primary Keys / Không Index)</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Số lần lặp Paired Repeats</label>
              <input
                type="number"
                className="form-control font-mono"
                value={repeats}
                disabled={isRunning}
                min={1}
                max={20}
                onChange={(e) => setRepeats(parseInt(e.target.value) || 1)}
              />
            </div>

            {mode === "L" ? (
              <div className="form-group">
                <label className="form-label">Số truy vấn đo chính thức (Fixed Count)</label>
                <input
                  type="number"
                  className="form-control font-mono"
                  value={fixedCount}
                  disabled={isRunning}
                  onChange={(e) => setFixedCount(parseInt(e.target.value) || 100)}
                />
              </div>
            ) : (
              <>
                <div className="form-group">
                  <label className="form-label">Mức Concurrency (Số clients đồng thời)</label>
                  <select
                    className="form-control"
                    value={concurrency}
                    disabled={isRunning}
                    onChange={(e) => setConcurrency(parseInt(e.target.value) || 1)}
                  >
                    <option value={1}>C = 1 worker</option>
                    <option value={8}>C = 8 workers (Chuẩn E2)</option>
                    <option value={32}>C = 32 workers (Stress Test)</option>
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Thời gian phát tải (Duration giây)</label>
                  <input
                    type="number"
                    className="form-control font-mono"
                    value={durationSeconds}
                    disabled={isRunning}
                    onChange={(e) => setDurationSeconds(parseFloat(e.target.value) || 30.0)}
                  />
                </div>
              </>
            )}
          </div>

          <div style={{ display: "flex", gap: "1rem", marginTop: "1.5rem" }}>
            <button
              className="btn btn-secondary"
              disabled={isRunning || loadingAction !== null}
              onClick={handleDryRun}
            >
              {loadingAction === "dry-run" ? (
                <RefreshCw size={16} className="spin" />
              ) : (
                <Clock size={16} />
              )}
              Dry-run Kiểm Tra Ma Trận
            </button>
            <button
              className="btn btn-primary"
              disabled={isRunning || loadingAction !== null}
              onClick={handleStart}
            >
              <PlayCircle size={16} /> Bắt Đầu Chạy Benchmark
            </button>
          </div>
        </div>

        {/* Pre-flight Assessment Card */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <Clock size={18} /> Đánh Giá Tiền Thực Thi
            </span>
          </div>

          {dryRunInfo ? (
            <div style={{ fontSize: "0.85rem", display: "flex", flexDirection: "column", gap: "0.8rem" }}>
              <div>
                <span style={{ color: "var(--text-muted)" }}>Tổng số Cell ma trận: </span>
                <strong>{dryRunInfo.total_cells} cells</strong>
              </div>
              <div>
                <span style={{ color: "var(--text-muted)" }}>Tổng requests dự kiến: </span>
                <strong>{dryRunInfo.total_requests_est?.toLocaleString()} reqs</strong>
              </div>
              <div>
                <span style={{ color: "var(--text-muted)" }}>Ước lượng thời gian: </span>
                <strong style={{ color: "var(--pg-color)" }}>
                  {dryRunInfo.estimated_duration_s} giây
                </strong>
              </div>
              <div>
                <span style={{ color: "var(--text-muted)" }}>Nguyên tắc luân phiên: </span>
                <span className="badge badge-success">Paired (PG ↔ Mongo)</span>
              </div>
              <div>
                <span style={{ color: "var(--text-muted)" }}>Quy cách timer: </span>
                <span className="badge badge-info">Monotonic High-Res (ns)</span>
              </div>
            </div>
          ) : (
            <div
              style={{
                color: "var(--text-muted)",
                fontSize: "0.85rem",
                textAlign: "center",
                padding: "2rem 0",
              }}
            >
              Nhấn <em>"Dry-run Kiểm Tra Ma Trận"</em> để xem tổng quan số cell và thời gian ước tính
              trước khi bắt đầu.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
