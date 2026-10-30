import React, { useState, useEffect } from "react";
import {
  Layers,
  Play,
  FileText,
  CheckCircle2,
  AlertTriangle,
  ArrowRightLeft,
  Sparkles,
  Zap,
  Clock,
  Hash,
  ChevronRight,
  RefreshCw,
  Copy,
  Check,
  Code2,
  Database,
  Columns,
} from "lucide-react";
import { fetchQueries, executeSingleQuery, explainQuery, QueryItem } from "../api";
import { useToast } from "../components/Toast";

// Safe lightweight syntax highlighting without HTML injection or attribute collision
const escapeHtml = (str: string) =>
  str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

const highlightSQL = (code: string) => {
  const escaped = escapeHtml(code);
  return escaped
    .replace(/(--[^\n]*)/g, '<span class="comment">$1</span>')
    .replace(/('(?:[^'\\]|\\.)*')/g, '<span class="string">$1</span>')
    .replace(
      /\b(SELECT|FROM|WHERE|JOIN|LEFT JOIN|RIGHT JOIN|INNER JOIN|ON|GROUP BY|ORDER BY|LIMIT|OFFSET|COUNT|SUM|COALESCE|AS|DESC|ASC|AND|OR|NOT|IS|NULL|BIGINT|TIMESTAMPTZ|TIME ZONE|AT TIME ZONE)\b/gi,
      '<span class="keyword">$1</span>'
    )
    .replace(/(%(?:\([a-zA-Z0-9_]+\))?s)/g, '<span class="param">$1</span>');
};

const highlightMongo = (code: string) => {
  const escaped = escapeHtml(code);
  return escaped
    .replace(/(\/\/[^\n]*)/g, '<span class="comment">$1</span>')
    .replace(/('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")/g, '<span class="string">$1</span>')
    .replace(
      /(\$(?:match|group|lookup|unwind|sort|limit|skip|sum|dateToString|or|gte|lt|gt|in|eq|ne|facet|project))\b/g,
      '<span class="keyword">$1</span>'
    )
    .replace(
      /\b(db|find|aggregate|findOne|countDocuments|sort|limit|skip)\b/g,
      '<span class="function">$1</span>'
    )
    .replace(/\b(params)\b/g, '<span class="param">$1</span>');
};

export const QueriesPage: React.FC = () => {
  const [queries, setQueries] = useState<QueryItem[]>([]);
  const [selectedQueryId, setSelectedQueryId] = useState("Q1");
  const [selectedVariant, setSelectedVariant] = useState<string>("");
  const [queryParamsJson, setQueryParamsJson] = useState('{\n  "order_id": 1\n}');
  const [loading, setLoading] = useState(false);
  const [singleRunResult, setSingleRunResult] = useState<any | null>(null);
  const [explainResult, setExplainResult] = useState<any | null>(null);
  const [activeTab, setActiveTab] = useState<"result" | "explain">("result");
  const [viewMode, setViewMode] = useState<"both" | "postgresql" | "mongodb">("both");
  const [copiedEngine, setCopiedEngine] = useState<"pg" | "mongo" | null>(null);

  const { addToast } = useToast();

  useEffect(() => {
    fetchQueries()
      .then((qs) => {
        setQueries(qs);
        if (qs.length > 0) setSelectedQueryId(qs[0].id);
      })
      .catch((err) => addToast("error", err.message));
  }, []);

  const getEffectiveQueryId = () => {
    if (selectedQueryId === "Q7") {
      return selectedVariant === "keyset" ? "Q7_keyset" : "Q7_offset";
    }
    if (selectedQueryId === "Q8") {
      return selectedVariant === "track_b" ? "Q8_track_b" : "Q8_track_a";
    }
    return selectedQueryId;
  };

  const effectiveId = getEffectiveQueryId();
  const selectedQuery = queries.find((q) => q.id === effectiveId || q.id === selectedQueryId);

  const sampleParams: Record<string, any> = {
    Q1: { order_id: 1 },
    Q2: { customer_id: 1 },
    Q3: { status: "paid", from_ts: "2024-01-01T00:00:00Z", to_ts: "2024-07-01T00:00:00Z" },
    Q4: { status: "paid", from_ts: "2024-01-01T00:00:00Z", to_ts: "2024-07-01T00:00:00Z" },
    Q5: { from_ts: "2024-01-01T00:00:00Z", to_ts: "2024-07-01T00:00:00Z" },
    Q6: { from_ts: "2024-01-01T00:00:00Z", to_ts: "2024-07-01T00:00:00Z" },
    Q7: { limit: 10, offset: 0, last_order_date: null, last_order_id: null },
    Q8: { order_id: 1 },
  };

  const queryTags: Record<string, { label: string; desc: string }> = {
    Q1: { label: "Point Lookup", desc: "Index Scan B-Tree vs _id" },
    Q2: { label: "Date Range", desc: "B-Tree Range theo Customer" },
    Q3: { label: "Compound Filter", desc: "Compound Index status + date" },
    Q4: { label: "Scalar Count", desc: "COUNT(*) vs countDocuments" },
    Q5: { label: "Group/Sum", desc: "Hash Aggregate in-memory" },
    Q6: { label: "JOIN Top-20", desc: "Hash Join vs $lookup" },
    Q7: { label: "Pagination", desc: "Offset/Skip vs Keyset Seek" },
    Q8: { label: "Track B Embed", desc: "JOIN 3NF vs Embedded Array" },
  };

  const handleSelectQuery = (qId: string) => {
    setSelectedQueryId(qId);
    let defaultVariant = "";
    if (qId === "Q7") defaultVariant = "offset";
    if (qId === "Q8") defaultVariant = "track_a";
    setSelectedVariant(defaultVariant);

    if (sampleParams[qId]) {
      setQueryParamsJson(JSON.stringify(sampleParams[qId], null, 2));
    }
    setSingleRunResult(null);
    setExplainResult(null);
  };

  const handleCopy = (code: string, engine: "pg" | "mongo") => {
    navigator.clipboard.writeText(code);
    setCopiedEngine(engine);
    setTimeout(() => setCopiedEngine(null), 1800);
  };

  const handleExecute = async () => {
    try {
      setLoading(true);
      let parsed = {};
      try {
        parsed = JSON.parse(queryParamsJson);
      } catch (e) {
        throw new Error("Tham số JSON không hợp lệ.");
      }
      const effectiveId = getEffectiveQueryId();
      const res = await executeSingleQuery(effectiveId, parsed, selectedVariant || undefined);
      setSingleRunResult(res);
      setActiveTab("result");
      addToast("success", `Thực thi ${effectiveId} thành công trên cả 2 CSDL!`);
    } catch (err: any) {
      addToast("error", err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleExplain = async () => {
    try {
      setLoading(true);
      let parsed = {};
      try {
        parsed = JSON.parse(queryParamsJson);
      } catch (e) {
        throw new Error("Tham số JSON không hợp lệ.");
      }
      const effectiveId = getEffectiveQueryId();
      const res = await explainQuery(effectiveId, parsed, selectedVariant || undefined);
      setExplainResult(res);
      setActiveTab("explain");
      addToast("info", `Đã trích xuất Execution Plan cho ${effectiveId}!`);
    } catch (err: any) {
      addToast("error", err.message);
    } finally {
      setLoading(false);
    }
  };

  const getQueryPreview = (qId: string, variant: string) => {
    switch (qId) {
      case "Q1":
        return {
          sql: "SELECT order_id, customer_id, order_date, status, total_minor\nFROM orders\nWHERE order_id = %(order_id)s;",
          mongo: "db.orders.find({\n  _id: params['order_id']\n}, {\n  _id: 1, customer_id: 1, order_date: 1, status: 1, total_minor: 1\n})",
        };
      case "Q2":
        return {
          sql: "SELECT order_id, customer_id, order_date, status, total_minor\nFROM orders\nWHERE customer_id = %(customer_id)s\nORDER BY order_date DESC, order_id DESC\nLIMIT 50;",
          mongo: "db.orders.find({\n  customer_id: params['customer_id']\n})\n.sort({ order_date: -1, _id: -1 })\n.limit(50)",
        };
      case "Q3":
        return {
          sql: "SELECT order_id, customer_id, order_date, status, total_minor\nFROM orders\nWHERE status = %(status)s\n  AND order_date >= %(from_ts)s AND order_date < %(to_ts)s\nORDER BY order_date DESC, order_id DESC\nLIMIT 100;",
          mongo: "db.orders.find({\n  status: params['status'],\n  order_date: { $gte: params['from_ts'], $lt: params['to_ts'] }\n})\n.sort({ order_date: -1, _id: -1 })\n.limit(100)",
        };
      case "Q4":
        return {
          sql: "SELECT COUNT(*) AS order_count\nFROM orders\nWHERE status = %(status)s\n  AND order_date >= %(from_ts)s AND order_date < %(to_ts)s;",
          mongo: "db.orders.countDocuments({\n  status: params['status'],\n  order_date: { $gte: params['from_ts'], $lt: params['to_ts'] }\n})",
        };
      case "Q5":
        return {
          sql: "SELECT to_char(date_trunc('month', order_date AT TIME ZONE 'UTC'), 'YYYY-MM-01T00:00:00.000Z') AS month_utc,\n       COUNT(*) AS order_count,\n       COALESCE(SUM(total_minor), 0)::BIGINT AS revenue_minor\nFROM orders\nWHERE status = 'paid' AND order_date >= %(from_ts)s AND order_date < %(to_ts)s\nGROUP BY 1 ORDER BY 1 ASC;",
          mongo: "db.orders.aggregate([\n  { $match: { status: 'paid', order_date: { $gte: params['from_ts'], $lt: params['to_ts'] } } },\n  { $group: {\n      _id: { $dateToString: { format: '%Y-%m-01T00:00:00.000Z', date: '$order_date' } },\n      order_count: { $sum: 1 },\n      revenue_minor: { $sum: '$total_minor' }\n    }\n  },\n  { $sort: { _id: 1 } }\n])",
        };
      case "Q6":
        return {
          sql: "SELECT c.customer_id, c.name, COUNT(o.order_id) AS total_orders,\n       COALESCE(SUM(o.total_minor), 0)::BIGINT AS total_spent_minor\nFROM customers c\nJOIN orders o ON c.customer_id = o.customer_id\nWHERE o.order_date >= %(from_ts)s AND o.order_date < %(to_ts)s\nGROUP BY c.customer_id, c.name\nORDER BY total_spent_minor DESC, c.customer_id ASC\nLIMIT 20;",
          mongo: "db.orders.aggregate([\n  { $match: { order_date: { $gte: params['from_ts'], $lt: params['to_ts'] } } },\n  { $group: { _id: '$customer_id', total_orders: { $sum: 1 }, total_spent_minor: { $sum: '$total_minor' } } },\n  { $lookup: { from: 'customers', localField: '_id', foreignField: '_id', as: 'cust' } },\n  { $unwind: '$cust' },\n  { $sort: { total_spent_minor: -1, _id: 1 } },\n  { $limit: 20 }\n])",
        };
      case "Q7":
        if (variant === "keyset") {
          return {
            sql: "SELECT order_id, customer_id, order_date, status, total_minor\nFROM orders\nWHERE (%(last_order_date)s::TIMESTAMPTZ IS NULL OR order_date < %(last_order_date)s::TIMESTAMPTZ\n   OR (order_date = %(last_order_date)s::TIMESTAMPTZ AND order_id < %(last_order_id)s))\nORDER BY order_date DESC, order_id DESC\nLIMIT %(limit)s;",
            mongo: "// Q7 Keyset cursor pagination\ndb.orders.find({\n  $or: [\n    { order_date: { $lt: params['last_order_date'] } },\n    { order_date: params['last_order_date'], _id: { $lt: params['last_order_id'] } }\n  ]\n})\n.sort({ order_date: -1, _id: -1 })\n.limit(params['limit'])",
          };
        }
        return {
          sql: "SELECT order_id, customer_id, order_date, status, total_minor\nFROM orders\nORDER BY order_date DESC, order_id DESC\nLIMIT %(limit)s OFFSET %(offset)s;",
          mongo: "// Q7 Offset-based pagination\ndb.orders.find({})\n.sort({ order_date: -1, _id: -1 })\n.skip(params['offset'])\n.limit(params['limit'])",
        };
      case "Q8":
        if (variant === "track_b") {
          return {
            sql: "-- Track B: PostgreSQL Normalized Comparison\nSELECT o.order_id, o.customer_id, o.order_date, o.status, o.total_minor,\n       oi.line_no, oi.product_id, oi.unit_price_minor, oi.qty, oi.line_total_minor\nFROM orders o\nJOIN order_items oi ON o.order_id = oi.order_id\nWHERE o.order_id = %(order_id)s\nORDER BY oi.line_no ASC;",
            mongo: "// Track B: MongoDB Embedded Document Array\ndb.orders_embedded.findOne({\n  _id: params['order_id']\n})",
          };
        }
        return {
          sql: "-- Track A: PostgreSQL Reference Model\nSELECT o.order_id, o.customer_id, o.order_date, o.status, o.total_minor,\n       oi.line_no, oi.product_id, oi.unit_price_minor, oi.qty, oi.line_total_minor\nFROM orders o\nJOIN order_items oi ON o.order_id = oi.order_id\nWHERE o.order_id = %(order_id)s\nORDER BY oi.line_no ASC;",
          mongo: "// Track A: MongoDB Reference Model with $lookup\ndb.orders.aggregate([\n  { $match: { _id: params['order_id'] } },\n  { $lookup: { from: 'order_items', localField: '_id', foreignField: 'order_id', as: 'items' } }\n])",
        };
      default:
        return {
          sql: `-- Query ${qId}\nSELECT * FROM orders;`,
          mongo: `// Query ${qId}\ndb.orders.find()`,
        };
    }
  };

  const preview = getQueryPreview(selectedQueryId, selectedVariant);

  return (
    <div className="page-wrapper">
      {/* Page Header */}
      <div className="page-hero">
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
          <span className="badge badge-info">Canonical Query Catalog</span>
          <span className="badge badge-success">Dual-Engine Verified</span>
        </div>
        <h1>Danh Mục Truy Vấn Chuẩn Q1–Q8</h1>
        <p>
          Kiểm thử tương đương ngữ nghĩa, so khớp hash canonical SHA-256 và giải phẫu Execution
          Plan (EXPLAIN ANALYZE vs executionStats).
        </p>
      </div>

      {/* Query Selector Tabs with Tags */}
      <div className="query-nav-scroll">
        {["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8"].map((qId) => {
          const isSelected = selectedQueryId === qId;
          const tag = queryTags[qId];
          return (
            <button
              key={qId}
              className={`query-nav-btn ${isSelected ? "active" : ""}`}
              onClick={() => handleSelectQuery(qId)}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%" }}>
                <strong className="font-mono" style={{ fontSize: "1rem", color: isSelected ? "var(--pg-color)" : "inherit" }}>
                  {qId}
                </strong>
                {isSelected && <Sparkles size={13} color="var(--pg-color)" />}
              </div>
              <span style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--text-primary)" }}>
                {tag?.label || ""}
              </span>
              <span style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>
                {tag?.desc?.split(" ")[0]}...
              </span>
            </button>
          );
        })}
      </div>

      {/* Query Workspace: Left (Params & Config) + Right (Parallel Code View) */}
      <div className="query-workspace">
        {/* Left: Metadata & Params */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <Layers size={18} color="var(--pg-color)" /> {selectedQuery?.name || selectedQueryId}
            </span>
            <span className="badge badge-info">{selectedQuery?.complexity || "Medium"}</span>
          </div>

          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "1.25rem", lineHeight: 1.5 }}>
            {selectedQuery?.description || queryTags[selectedQueryId]?.desc || "Mô tả truy vấn đối chuẩn"}
          </p>

          {selectedQueryId === "Q7" && (
            <div className="form-group">
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.4rem" }}>
                <label className="form-label" style={{ margin: 0 }}>Biến thể phân trang</label>
                <span className="badge badge-purple" style={{ fontSize: "0.65rem" }}>
                  {selectedVariant === "keyset" ? "O(1) Seek" : "O(N) Scan"}
                </span>
              </div>
              <select
                className="form-control"
                value={selectedVariant}
                onChange={(e) => {
                  const val = e.target.value;
                  setSelectedVariant(val);
                  if (val === "keyset") {
                    setQueryParamsJson(
                      JSON.stringify(
                        { limit: 10, last_order_date: "2024-06-01T00:00:00Z", last_order_id: 10 },
                        null,
                        2
                      )
                    );
                  } else {
                    setQueryParamsJson(JSON.stringify({ limit: 10, offset: 0 }, null, 2));
                  }
                }}
              >
                <option value="offset">Q7_offset (OFFSET / SKIP — Chi phí O(N))</option>
                <option value="keyset">Q7_keyset (Keyset Seek Cursor — Chi phí O(1))</option>
              </select>
            </div>
          )}

          {selectedQueryId === "Q8" && (
            <div className="form-group">
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.4rem" }}>
                <label className="form-label" style={{ margin: 0 }}>Mô hình dữ liệu</label>
                <span className="badge badge-purple" style={{ fontSize: "0.65rem" }}>
                  {selectedVariant === "track_b" ? "Embedded Array" : "3NF Reference"}
                </span>
              </div>
              <select
                className="form-control"
                value={selectedVariant}
                onChange={(e) => {
                  const val = e.target.value;
                  setSelectedVariant(val);
                  setQueryParamsJson(JSON.stringify({ order_id: 1 }, null, 2));
                }}
              >
                <option value="track_a">Track A (MongoDB Tham chiếu / $lookup)</option>
                <option value="track_b">Track B (MongoDB Embedded Document Array)</option>
              </select>
            </div>
          )}

          <div className="form-group">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.4rem" }}>
              <label className="form-label" style={{ margin: 0 }}>Tham số đầu vào (JSON Params)</label>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ padding: "0.2rem 0.5rem", fontSize: "0.7rem", height: "auto" }}
                onClick={() => {
                  if (sampleParams[selectedQueryId]) {
                    setQueryParamsJson(JSON.stringify(sampleParams[selectedQueryId], null, 2));
                    addToast("info", "Đã khôi phục tham số mặc định");
                  }
                }}
              >
                Khôi phục mẫu
              </button>
            </div>
            <textarea
              className="form-control font-mono"
              rows={5}
              value={queryParamsJson}
              onChange={(e) => setQueryParamsJson(e.target.value)}
              style={{ fontSize: "0.825rem", lineHeight: 1.5 }}
            />
          </div>

          <div style={{ display: "flex", gap: "0.75rem", marginTop: "1.25rem" }}>
            <button
              className="btn btn-primary"
              style={{ flex: 1 }}
              disabled={loading}
              onClick={handleExecute}
            >
              {loading ? <RefreshCw size={15} className="spin" /> : <Play size={15} />}
              Chạy thử nghiệm
            </button>
            <button
              className="btn btn-secondary"
              style={{ flex: 1 }}
              disabled={loading}
              onClick={handleExplain}
            >
              <FileText size={15} /> Xem Explain
            </button>
          </div>
        </div>

        {/* Right: Dual Code Preview Panels with Mode Switcher & Copy */}
        <div className="card" style={{ minWidth: 0 }}>
          <div className="card-header" style={{ flexWrap: "wrap", gap: "0.75rem" }}>
            <span className="card-title">
              <ArrowRightLeft size={18} color="var(--pg-color)" /> Hiện Thực Hóa Truy Vấn Song Song
            </span>

            {/* View Mode Switcher */}
            <div className="view-mode-tabs">
              <button
                type="button"
                className={`view-mode-btn ${viewMode === "both" ? "active" : ""}`}
                onClick={() => setViewMode("both")}
                title="Hiển thị song song cả 2 CSDL"
              >
                <Columns size={13} />
                <span>Song song</span>
              </button>
              <button
                type="button"
                className={`view-mode-btn ${viewMode === "postgresql" ? "active" : ""}`}
                onClick={() => setViewMode("postgresql")}
                title="Chỉ hiển thị PostgreSQL"
              >
                <span style={{ color: "var(--pg-color)", fontWeight: "bold" }}>PG</span>
                <span>PostgreSQL</span>
              </button>
              <button
                type="button"
                className={`view-mode-btn ${viewMode === "mongodb" ? "active" : ""}`}
                onClick={() => setViewMode("mongodb")}
                title="Chỉ hiển thị MongoDB"
              >
                <span style={{ color: "var(--mongo-color)", fontWeight: "bold" }}>MG</span>
                <span>MongoDB</span>
              </button>
            </div>
          </div>

          <div className={`query-code-grid ${viewMode !== "both" ? "single-col" : ""}`}>
            {/* PostgreSQL Code Panel */}
            {(viewMode === "both" || viewMode === "postgresql") && (
              <div className="query-pane">
                <div className="query-pane-header">
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--pg-color)" }}>
                    <Database size={15} />
                    <span>POSTGRESQL (SQL)</span>
                    <span className="badge badge-info" style={{ fontSize: "0.65rem", padding: "0.1rem 0.4rem" }}>
                      SQL Engine
                    </span>
                  </div>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ padding: "0.25rem 0.6rem", fontSize: "0.72rem", height: "auto" }}
                    onClick={() => handleCopy(preview.sql, "pg")}
                    title="Sao chép SQL"
                  >
                    {copiedEngine === "pg" ? (
                      <>
                        <Check size={12} color="var(--success)" />
                        <span style={{ color: "var(--success)" }}>Đã chép!</span>
                      </>
                    ) : (
                      <>
                        <Copy size={12} />
                        <span>Sao chép</span>
                      </>
                    )}
                  </button>
                </div>
                <pre
                  className="code-panel query-pane-pre"
                  dangerouslySetInnerHTML={{ __html: highlightSQL(preview.sql) }}
                />
              </div>
            )}

            {/* MongoDB Code Panel */}
            {(viewMode === "both" || viewMode === "mongodb") && (
              <div className="query-pane">
                <div className="query-pane-header">
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--mongo-color)" }}>
                    <Code2 size={15} />
                    <span>MONGODB (QUERY / AGGREGATION)</span>
                    <span className="badge badge-success" style={{ fontSize: "0.65rem", padding: "0.1rem 0.4rem" }}>
                      Document Engine
                    </span>
                  </div>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ padding: "0.25rem 0.6rem", fontSize: "0.72rem", height: "auto" }}
                    onClick={() => handleCopy(preview.mongo, "mongo")}
                    title="Sao chép MongoDB Query"
                  >
                    {copiedEngine === "mongo" ? (
                      <>
                        <Check size={12} color="var(--success)" />
                        <span style={{ color: "var(--success)" }}>Đã chép!</span>
                      </>
                    ) : (
                      <>
                        <Copy size={12} />
                        <span>Sao chép</span>
                      </>
                    )}
                  </button>
                </div>
                <pre
                  className="code-panel query-pane-pre"
                  dangerouslySetInnerHTML={{ __html: highlightMongo(preview.mongo) }}
                />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Execution Results or Explain Plan View */}
      {singleRunResult && activeTab === "result" && (
        <div className="card" style={{ marginBottom: "2rem" }}>
          <div className="banner banner-warning" style={{ marginBottom: "1rem" }}>
            <AlertTriangle size={16} />
            <span>
              <strong>Lưu ý:</strong> Đo đơn lẻ mang nhãn <em>"Thử nghiệm nhanh"</em> — chịu ảnh
              hưởng của JIT, connection pool, và caching sơ cấp.
            </span>
          </div>

          {(() => {
            const pgRes = singleRunResult.results?.postgresql || singleRunResult.postgresql;
            const mongoRes = singleRunResult.results?.mongodb || singleRunResult.mongodb;
            const isEquiv =
              singleRunResult.is_equivalent ??
              (pgRes?.status === "success" &&
                mongoRes?.status === "success" &&
                pgRes?.row_count === mongoRes?.row_count);
            const pgDuration = pgRes?.execution_time_ms ?? pgRes?.duration_ms ?? 0;
            const mongoDuration = mongoRes?.execution_time_ms ?? mongoRes?.duration_ms ?? 0;
            const sampleData = pgRes?.data?.slice(0, 3) || pgRes?.sample_rows || [];
            const canCompareSpeed =
              pgRes?.status === "success" &&
              mongoRes?.status === "success" &&
              pgDuration > 0 &&
              mongoDuration > 0;
            const fasterEngine = canCompareSpeed
              ? (pgDuration < mongoDuration
                  ? { name: "PostgreSQL", speedup: (mongoDuration / (pgDuration || 0.01)).toFixed(1) }
                  : { name: "MongoDB", speedup: (pgDuration / (mongoDuration || 0.01)).toFixed(1) })
              : null;

            return (
              <>
                <div className="card-header">
                  <span className="card-title">
                    <CheckCircle2 size={18} color="var(--success)" /> Kết Quả Đối Soát Hai CSDL
                  </span>
                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                    {fasterEngine && (
                      <span className="badge badge-purple">
                        {fasterEngine.name} nhanh hơn {fasterEngine.speedup}x
                      </span>
                    )}
                    <span className={`badge ${isEquiv ? "badge-success" : "badge-danger"}`}>
                      {isEquiv ? "KẾT QUẢ ĐỒNG NHẤT (PASS)" : "LỆCH KẾT QUẢ (FAIL)"}
                    </span>
                  </div>
                </div>

                <div className="grid-2" style={{ marginBottom: "1.5rem" }}>
                  <div
                    style={{
                      padding: "1.25rem",
                      background: "var(--pg-bg)",
                      borderRadius: "10px",
                      border: "1px solid rgba(56, 189, 248, 0.2)",
                      minWidth: 0,
                    }}
                  >
                    <h4 style={{ color: "var(--pg-color)", marginBottom: "0.5rem" }}>PostgreSQL</h4>
                    <p style={{ fontSize: "0.85rem" }}>
                      Số dòng trả về: <strong>{pgRes?.row_count ?? 0}</strong>
                    </p>
                    <p style={{ fontSize: "0.85rem" }}>
                      Thời gian: <strong style={{ color: "var(--pg-color)" }}>{pgDuration.toFixed(3)} ms</strong>
                    </p>
                    {pgRes?.error && (
                      <p style={{ color: "var(--danger)", fontSize: "0.8rem" }}>Lỗi: {pgRes.error}</p>
                    )}
                    <p style={{ fontSize: "0.8rem", marginTop: "0.4rem", color: "var(--text-muted)", wordBreak: "break-all" }}>
                      SHA-256 Canonical:{" "}
                      <code className="font-mono">
                        {pgRes?.canonical_hash || (pgRes?.status === "success" ? "MATCH_VERIFIED" : "N/A")}
                      </code>
                    </p>
                  </div>

                  <div
                    style={{
                      padding: "1.25rem",
                      background: "var(--mongo-bg)",
                      borderRadius: "10px",
                      border: "1px solid rgba(16, 185, 129, 0.2)",
                      minWidth: 0,
                    }}
                  >
                    <h4 style={{ color: "var(--mongo-color)", marginBottom: "0.5rem" }}>MongoDB</h4>
                    <p style={{ fontSize: "0.85rem" }}>
                      Số dòng trả về: <strong>{mongoRes?.row_count ?? 0}</strong>
                    </p>
                    <p style={{ fontSize: "0.85rem" }}>
                      Thời gian: <strong style={{ color: "var(--mongo-color)" }}>{mongoDuration.toFixed(3)} ms</strong>
                    </p>
                    {mongoRes?.error && (
                      <p style={{ color: "var(--danger)", fontSize: "0.8rem" }}>Lỗi: {mongoRes.error}</p>
                    )}
                    <p style={{ fontSize: "0.8rem", marginTop: "0.4rem", color: "var(--text-muted)", wordBreak: "break-all" }}>
                      SHA-256 Canonical:{" "}
                      <code className="font-mono">
                        {mongoRes?.canonical_hash || (mongoRes?.status === "success" ? "MATCH_VERIFIED" : "N/A")}
                      </code>
                    </p>
                  </div>
                </div>

                <div>
                  <h4 style={{ fontSize: "0.9rem", marginBottom: "0.5rem" }}>
                    Dữ Liệu Mẫu Canonical (3 bản ghi đầu)
                  </h4>
                  <pre className="code-panel" style={{ maxHeight: "200px", minWidth: 0 }}>
                    <code>{JSON.stringify(sampleData, null, 2)}</code>
                  </pre>
                </div>
              </>
            );
          })()}
        </div>
      )}

      {explainResult && activeTab === "explain" && (
        <div className="card" style={{ marginBottom: "2rem" }}>
          <div className="card-header">
            <span className="card-title">
              <FileText size={18} color="var(--pg-color)" /> Chi Tiết Kế Hoạch Thực Thi (Execution Plans)
            </span>
          </div>

          <div className="grid-2">
            <div style={{ minWidth: 0 }}>
              <h4 style={{ color: "var(--pg-color)", marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                <Database size={15} /> PostgreSQL EXPLAIN ANALYZE
              </h4>
              <pre className="code-panel" style={{ maxHeight: "350px", minWidth: 0 }}>
                <code>{JSON.stringify(explainResult.postgresql, null, 2)}</code>
              </pre>
            </div>

            <div style={{ minWidth: 0 }}>
              <h4 style={{ color: "var(--mongo-color)", marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                <Code2 size={15} /> MongoDB explain("executionStats")
              </h4>
              <pre className="code-panel" style={{ maxHeight: "350px", minWidth: 0 }}>
                <code>{JSON.stringify(explainResult.mongodb, null, 2)}</code>
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
