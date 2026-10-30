import React, { useState, useEffect } from "react";
import {
  Database,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Trash2,
  ArrowDownToLine,
  ShieldCheck,
  Hash,
  Layers,
  Sparkles,
} from "lucide-react";
import {
  validateDataset,
  loadDataset,
  resetDatabases,
  fetchEnvironment,
  EnvironmentInfo,
} from "../api";
import { useToast } from "../components/Toast";
import { TableSkeleton } from "../components/LoadingSkeleton";

export const DatasetsPage: React.FC = () => {
  const [profile, setProfile] = useState("fixture");
  const [seed, setSeed] = useState(42);
  const [distribution, setDistribution] = useState("uniform");
  const [indexProfile, setIndexProfile] = useState("I1");
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [validationResult, setValidationResult] = useState<any | null>(null);
  const [showResetModal, setShowResetModal] = useState(false);
  const [env, setEnv] = useState<EnvironmentInfo | null>(null);

  const { addToast } = useToast();

  const loadEnv = async () => {
    try {
      const data = await fetchEnvironment();
      setEnv(data);
    } catch (err) {}
  };

  useEffect(() => {
    loadEnv();
    validateDataset(`${profile}-seed${seed}`)
      .then((res) => {
        if (res && res.counts) {
          setValidationResult(res);
        }
      })
      .catch(() => {});
  }, []);

  const handleValidate = async () => {
    try {
      setLoadingAction("validate");
      addToast("info", "Đang kiểm định tính toàn vẹn và so khớp canonical checksum...");
      const res = await validateDataset(`${profile}-seed${seed}`);
      setValidationResult(res);
      if (res.passed) {
        addToast("success", "Kiểm định hoàn tất: 100% tương đương ngữ nghĩa (PASS)!");
      } else {
        addToast("error", "Kiểm định phát hiện sai lệch dữ liệu giữa 2 CSDL!");
      }
      loadEnv();
    } catch (err: any) {
      addToast("error", `Lỗi kiểm định: ${err.message}`);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleLoad = async () => {
    try {
      setLoadingAction("load");
      addToast("info", `Đang nạp dataset ${profile}-seed${seed} vào cả PostgreSQL và MongoDB...`);
      const datasetId = `${profile}-seed${seed}`;
      const res = await loadDataset(datasetId, undefined, indexProfile, distribution);
      addToast("success", `Nạp thành công: ${res.message || "Hoàn tất nạp dữ liệu vào cả 2 hệ thống"}`);
      await handleValidate();
      loadEnv();
    } catch (err: any) {
      addToast("error", `Lỗi nạp CSDL: ${err.message}`);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleReset = async () => {
    try {
      setLoadingAction("reset");
      setShowResetModal(false);
      addToast("info", "Đang dọn sạch (TRUNCATE & DROP) trên cả 2 CSDL...");
      await resetDatabases();
      addToast("success", "Đã dọn sạch dữ liệu trên cả 2 hệ thống.");
      setValidationResult(null);
      loadEnv();
    } catch (err: any) {
      addToast("error", `Lỗi làm sạch: ${err.message}`);
    } finally {
      setLoadingAction(null);
    }
  };

  const profileDetails: Record<
    string,
    { label: string; customers: number; orders: number; products: number; desc: string }
  > = {
    fixture: {
      label: "Fixture",
      customers: 12,
      orders: 50,
      products: 20,
      desc: "Kiểm tra đúng đắn & Smoke Test nhanh",
    },
    small: {
      label: "Small",
      customers: 1000,
      orders: 10000,
      products: 500,
      desc: "Tập dữ liệu nghiệm thu chính thức",
    },
    medium: {
      label: "Medium",
      customers: 10000,
      orders: 100000,
      products: 5000,
      desc: "Kiểm tra mở rộng quy mô",
    },
    large: {
      label: "Large",
      customers: 100000,
      orders: 1000000,
      products: 20000,
      desc: "Thử thách giới hạn RAM 2048MB",
    },
  };

  const currentProfile = profileDetails[profile] || profileDetails.fixture;

  const activeCounts = validationResult?.counts || env?.counts;
  const pgOrders = activeCounts?.postgresql?.orders;
  const mongoOrders = activeCounts?.mongodb?.orders;
  const pgCustomers = activeCounts?.postgresql?.customers;
  const mongoCustomers = activeCounts?.mongodb?.customers;
  const pgProducts = activeCounts?.postgresql?.products;
  const mongoProducts = activeCounts?.mongodb?.products;

  const calcPercent = (count: number | undefined, target: number) => {
    if (count == null || target <= 0) return 0;
    return Math.min(100, Math.max(0, Math.round((count / target) * 100)));
  };

  const formatCount = (count: number | undefined) => {
    return count != null ? count.toLocaleString() : "—";
  };

  return (
    <div className="page-wrapper">
      {/* Page Header */}
      <div className="page-hero">
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
          <span className="badge badge-info">Deterministic Generator</span>
          <span className="badge badge-success">Seed=42 Canonical</span>
        </div>
        <h1>Quản Lý & Kiểm Định Bộ Dữ Liệu Đối Chuẩn</h1>
        <p>
          Sinh dữ liệu tất định theo seed, nạp idempotent vào PostgreSQL và MongoDB, đối soát số
          lượng bản ghi và SHA-256 canonical checksum.
        </p>
      </div>

      {/* Preset Cards Selector */}
      <div style={{ marginBottom: "1.5rem" }}>
        <div className="form-label" style={{ marginBottom: "0.75rem" }}>
          CHỌN QUY MÔ PROFILE DỮ LIỆU:
        </div>
        <div className="grid-4">
          {Object.entries(profileDetails).map(([key, info]) => {
            const isSelected = profile === key;
            return (
              <div
                key={key}
                className="card"
                onClick={() => setProfile(key)}
                style={{
                  cursor: "pointer",
                  border: isSelected
                    ? "2px solid var(--pg-color)"
                    : "1px solid var(--border-light)",
                  background: isSelected ? "var(--pg-bg)" : "var(--bg-card)",
                  transition: "all var(--duration-normal) var(--ease-out-expo)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                  <strong style={{ fontSize: "1rem", color: isSelected ? "var(--pg-color)" : "inherit" }}>
                    {info.label}
                  </strong>
                  {isSelected && <CheckCircle2 size={16} color="var(--pg-color)" />}
                </div>
                <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "0.75rem" }}>
                  {info.desc}
                </div>
                <div style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
                  <div>{info.orders.toLocaleString()} đơn hàng</div>
                  <div>{info.customers.toLocaleString()} khách hàng</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Configuration & Record Count Preview Grid */}
      <div className="grid-3" style={{ marginBottom: "2rem" }}>
        {/* Left: Configuration Form */}
        <div className="card" style={{ gridColumn: "span 2" }}>
          <div className="card-header">
            <span className="card-title">
              <Database size={18} /> Tham Số Sinh Dữ Liệu
            </span>
            <span className="badge badge-info">
              {profile}-seed{seed}
            </span>
          </div>

          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">Deterministic Seed (Cố định giá trị)</label>
              <input
                type="number"
                className="form-control font-mono"
                value={seed}
                onChange={(e) => setSeed(parseInt(e.target.value) || 42)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Phân phối dữ liệu (Distribution)</label>
              <select
                className="form-control"
                value={distribution}
                onChange={(e) => setDistribution(e.target.value)}
              >
                <option value="uniform">Đều (Uniform Distribution)</option>
                <option value="skewed">Lệch (Skewed 80/20 Zipfian Distribution)</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Chỉ mục áp dụng (Index Catalog)</label>
              <select
                className="form-control"
                value={indexProfile}
                onChange={(e) => setIndexProfile(e.target.value)}
              >
                <option value="I1">I1 — Đầy đủ Workload Secondary Indexes</option>
                <option value="I0">I0 — Chỉ Primary Keys (No Secondary Index)</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Chế độ nạp (Idempotency)</label>
              <input
                type="text"
                className="form-control font-mono"
                value="Idempotent Upsert (Seed 42)"
                disabled
              />
            </div>
          </div>

          {/* Action Buttons */}
          <div style={{ display: "flex", gap: "0.75rem", marginTop: "1.25rem", flexWrap: "wrap" }}>
            <button
              className="btn btn-primary"
              disabled={loadingAction !== null}
              onClick={handleLoad}
            >
              {loadingAction === "load" ? (
                <RefreshCw size={16} className="spin" />
              ) : (
                <ArrowDownToLine size={16} />
              )}
              Nạp vào 2 CSDL (PG & MongoDB)
            </button>

            <button
              className="btn btn-secondary"
              disabled={loadingAction !== null}
              onClick={handleValidate}
            >
              {loadingAction === "validate" ? (
                <RefreshCw size={16} className="spin" />
              ) : (
                <ShieldCheck size={16} />
              )}
              Kiểm Tra Tính Tương Đương
            </button>

            <button
              className="btn btn-danger"
              disabled={loadingAction !== null}
              onClick={() => setShowResetModal(true)}
              style={{ marginLeft: "auto" }}
            >
              <Trash2 size={16} /> Dọn Sạch Dữ Liệu
            </button>
          </div>
        </div>

        {/* Right: Record Counts Comparison */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <CheckCircle2 size={18} color="var(--success)" /> Thống Kê Bản Ghi
            </span>
            <span className="badge badge-success">Idempotent</span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem", fontSize: "0.85rem" }}>
            {/* Orders */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.3rem" }}>
                <span>Đơn hàng (Orders):</span>
                <strong>
                  PG: {formatCount(pgOrders)} / Mongo: {formatCount(mongoOrders)}
                </strong>
              </div>
              <div className="mini-bar-track">
                <div
                  className="mini-bar-fill"
                  style={{
                    width: `${calcPercent(pgOrders, currentProfile.orders)}%`,
                    background: "var(--pg-color)",
                  }}
                />
              </div>
            </div>

            {/* Customers */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.3rem" }}>
                <span>Khách hàng (Customers):</span>
                <strong>
                  PG: {formatCount(pgCustomers)} / Mongo: {formatCount(mongoCustomers)}
                </strong>
              </div>
              <div className="mini-bar-track">
                <div
                  className="mini-bar-fill"
                  style={{
                    width: `${calcPercent(pgCustomers, currentProfile.customers)}%`,
                    background: "var(--mongo-color)",
                  }}
                />
              </div>
            </div>

            {/* Products */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.3rem" }}>
                <span>Sản phẩm (Products):</span>
                <strong>
                  PG: {formatCount(pgProducts)} / Mongo: {formatCount(mongoProducts)}
                </strong>
              </div>
              <div className="mini-bar-track">
                <div
                  className="mini-bar-fill"
                  style={{
                    width: `${calcPercent(pgProducts, currentProfile.products)}%`,
                    background: "var(--accent-purple)",
                  }}
                />
              </div>
            </div>

            {/* Checksum SHA-256 */}
            <div style={{ borderTop: "1px solid var(--border-light)", paddingTop: "0.75rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.3rem", color: "var(--text-muted)", marginBottom: "0.3rem" }}>
                <Hash size={13} /> Checksum Canonical SHA-256:
              </div>
              <div
                className="code-panel font-mono"
                style={{ fontSize: "0.65rem", padding: "0.4rem 0.6rem", wordBreak: "break-all" }}
              >
                {validationResult?.checksum_sha256 ||
                  validationResult?.manifest?.sha256 ||
                  "—"}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Validation Result Table */}
      {validationResult && (
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <ShieldCheck size={18} color="var(--success)" /> Báo Cáo Kiểm Định Toàn Vẹn Ngữ Nghĩa (Canonical Integrity)
            </span>
            <span
              className={`badge ${
                validationResult.passed ? "badge-success" : "badge-danger"
              }`}
            >
              {validationResult.passed
                ? "HOÀN TOÀN TƯƠNG ĐƯƠNG (PASS)"
                : "CẢNH BÁO SAI LỆCH (FAIL)"}
            </span>
          </div>

          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Thực Thể</th>
                  <th>PostgreSQL Count</th>
                  <th>MongoDB Count</th>
                  <th>Chênh Lệch</th>
                  <th style={{ textAlign: "right" }}>Trạng Thái</th>
                </tr>
              </thead>
              <tbody>
                {["customers", "products", "orders", "order_items"].map((entity) => {
                  const pgCount = validationResult.counts?.postgresql?.[entity] ?? 0;
                  const mongoCount = validationResult.counts?.mongodb?.[entity] ?? 0;
                  const diff = Math.abs(pgCount - mongoCount);
                  return (
                    <tr key={entity}>
                      <td>
                        <strong style={{ textTransform: "capitalize" }}>{entity}</strong>
                      </td>
                      <td style={{ color: "var(--pg-color)", fontWeight: 600 }}>
                        {pgCount.toLocaleString()}
                      </td>
                      <td style={{ color: "var(--mongo-color)", fontWeight: 600 }}>
                        {mongoCount.toLocaleString()}
                      </td>
                      <td>{diff === 0 ? "0" : diff}</td>
                      <td style={{ textAlign: "right" }}>
                        <span
                          className={`badge ${
                            diff === 0 ? "badge-success" : "badge-danger"
                          }`}
                        >
                          {diff === 0 ? <CheckCircle2 size={11} /> : <AlertTriangle size={11} />}
                          {diff === 0 ? "MATCH" : "MISMATCH"}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Reset Confirmation Modal */}
      {showResetModal && (
        <div className="modal-overlay" onClick={() => setShowResetModal(false)}>
          <div
            className="card modal-content"
            style={{ maxWidth: "480px", width: "90%", border: "1px solid var(--danger)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ color: "var(--danger)", display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <AlertTriangle size={20} /> Xác Nhận Dọn Sạch Dữ Liệu
            </h3>
            <p style={{ margin: "1rem 0", fontSize: "0.9rem", color: "var(--text-secondary)" }}>
              Hành động này sẽ <strong>TRUNCATE</strong> và xóa toàn bộ dữ liệu trong các bảng
              PostgreSQL và collections MongoDB trong namespace của PT Lab.
            </p>
            <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end" }}>
              <button className="btn btn-secondary" onClick={() => setShowResetModal(false)}>
                Hủy bỏ
              </button>
              <button className="btn btn-danger" onClick={handleReset}>
                Xác Nhận Xóa Hết
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
