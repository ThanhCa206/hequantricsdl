/**
 * BenchLab Frontend API Client
 * Connects to FastAPI Backend endpoints
 */

export interface SystemHealth {
  status: string;
  timestamp: string;
  api: string;
  engines: {
    postgresql?: {
      is_healthy: boolean;
      latency_ms: number;
      version?: string;
      error?: string | null;
    };
    mongodb?: {
      is_healthy: boolean;
      latency_ms: number;
      version?: string;
      error?: string | null;
    };
  };
}

export interface EnvironmentInfo {
  os: string;
  cpu_count: number;
  memory_total_gb: number;
  container_quota: { cpus: number; memory: string };
  target_versions: { postgresql: string; mongodb: string };
  dataset_active: string;
  correctness_passed: boolean;
  counts: {
    postgresql: { customers: number; products: number; orders: number; order_items: number };
    mongodb: { customers: number; products: number; orders: number; order_items: number };
  };
}

export interface QueryItem {
  id: string;
  name: string;
  description: string;
  complexity: string;
  category: string;
  variants?: string[];
  track: string;
}

export interface BenchmarkStatus {
  is_locked: boolean;
  active_job_id: string | null;
  state: "IDLE" | "RUNNING" | "DRAINING" | "COMPLETED" | "FAILED" | "CANCELLED" | "INTERRUPTED";
  progress: {
    engine?: string;
    query_id?: string;
    repeat?: number;
    total_repeats?: number;
    phase?: string;
    completed_cells?: number;
    total_cells?: number;
    total_samples?: number;
    percent?: number;
    step?: string;
  };
}

const API_BASE = "/api";

export async function fetchHealth(): Promise<SystemHealth> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error("Failed to fetch health");
  return res.json();
}

export async function fetchEnvironment(): Promise<EnvironmentInfo> {
  const res = await fetch(`${API_BASE}/environment`);
  if (!res.ok) throw new Error("Failed to fetch environment");
  return res.json();
}

export async function fetchQueries(): Promise<QueryItem[]> {
  const res = await fetch(`${API_BASE}/queries`);
  if (!res.ok) throw new Error("Failed to fetch queries");
  const data = await res.json();
  return data.map((d: any) => ({
    id: d.query_id || d.id,
    name: d.name,
    description: d.description,
    complexity: d.track === "B" ? "Complex" : "Medium",
    category: "Workload",
    track: d.track,
  }));
}

export async function executeSingleQuery(queryId: string, params: any = {}, variant?: string) {
  const res = await fetch(`${API_BASE}/queries/${queryId}/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ engine: "both", params, timed: true }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function explainQuery(queryId: string, params: any = {}, variant?: string) {
  const res = await fetch(`${API_BASE}/queries/${queryId}/explain`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ engine: "both", params }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchBenchmarkStatus(): Promise<BenchmarkStatus> {
  const res = await fetch(`${API_BASE}/benchmark/status`);
  if (!res.ok) throw new Error("Failed to fetch benchmark status");
  return res.json();
}

export async function dryRunBenchmark(payload: any) {
  const res = await fetch(`${API_BASE}/benchmark/dry-run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function startBenchmark(payload: any) {
  const res = await fetch(`${API_BASE}/benchmark/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorData.detail || "Failed to start benchmark");
  }
  return res.json();
}

export async function cancelBenchmark() {
  const res = await fetch(`${API_BASE}/benchmark/cancel`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to cancel benchmark");
  return res.json();
}

export async function fetchExperiments() {
  const res = await fetch(`${API_BASE}/benchmark/experiments`);
  if (!res.ok) throw new Error("Failed to fetch experiments");
  return res.json();
}

export async function fetchExperimentSummary(expId: string) {
  const res = await fetch(`${API_BASE}/results/${expId}/summary`);
  if (!res.ok) throw new Error("Failed to fetch summary");
  return res.json();
}

export async function fetchExperimentResources(expId: string) {
  const res = await fetch(`${API_BASE}/results/${expId}/resources`);
  if (!res.ok) throw new Error("Failed to fetch resources");
  return res.json();
}

export async function fetchExperimentPlans(expId: string) {
  const res = await fetch(`${API_BASE}/results/${expId}/plans`);
  if (!res.ok) throw new Error("Failed to fetch plans");
  return res.json();
}

export async function fetchTestMatrix() {
  const res = await fetch(`${API_BASE}/tests/matrix`);
  if (!res.ok) throw new Error("Failed to fetch test matrix");
  return res.json();
}

export async function runSmokeTests() {
  const res = await fetch(`${API_BASE}/tests/run-smoke`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to run smoke tests");
  return res.json();
}

export async function validateDataset(datasetId: string) {
  const res = await fetch(`${API_BASE}/datasets/${datasetId}/validate`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function loadDataset(datasetId: string, engine?: string, indexProfile: string = "I1") {
  const res = await fetch(`${API_BASE}/datasets/${datasetId}/load`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ engine, index_profile: indexProfile }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function resetDatabases() {
  const res = await fetch(`${API_BASE}/datasets/reset`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
