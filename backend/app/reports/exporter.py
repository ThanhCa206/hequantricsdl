"""Report and Dataset Exporter.
Exports benchmark results to Markdown reports, summary CSVs, and zipped bundles.
Strictly implements SPEC.md Section 8.3, 10.7, 14.
"""

import csv
import io
import json
from pathlib import Path
from typing import Any, Dict

from .statistics import analyze_experiment_samples


def generate_markdown_report(summary: Dict[str, Any]) -> str:
    """Generate professional, fully transparent Markdown report based directly on raw results."""
    exp_id = summary.get("experiment_id", "Unknown")
    cfg = summary.get("config", {})
    created_at = summary.get("created_at_utc", "Unknown")
    status = summary.get("status", "Unknown")

    lines = [
        f"# BÁO CÁO KẾT QUẢ THỰC NGHIỆM BENCHMARK: {exp_id}",
        "",
        "## 1. Thông tin cấu hình thực nghiệm",
        "",
        f"- **Mã thực nghiệm (Experiment ID):** `{exp_id}`",
        f"- **Thời gian khởi tạo:** `{created_at}`",
        f"- **Trạng thái kết thúc:** `{status}`",
        f"- **Chế độ đo (Mode):** `{cfg.get('mode', 'L')}` ({'Sequential Latency' if cfg.get('mode') == 'L' else 'Closed-loop Throughput'})",
        f"- **Bộ dữ liệu (Dataset):** `{cfg.get('dataset', 'fixture-seed42')}` (Profile: `{cfg.get('profile', 'fixture')}`)",
        f"- **Index Profile:** `{cfg.get('index_profile', 'I1')}`",
        f"- **Số repeats luân phiên:** `{cfg.get('repeats', 1)}`",
        f"- **Deterministic Seed:** `{cfg.get('seed', 42)}`",
        "",
        "## 2. Bảng tổng hợp số liệu hiệu năng (PostgreSQL vs MongoDB)",
        "",
        "| Query | Engine | p50 (ms) | p90 (ms) | p95 (ms) | p99 (ms) | Throughput (QPS) | Error Rate (%) |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]

    queries_data = summary.get("queries", {})
    for q_id, q_data in queries_data.items():
        pg = q_data.get("postgresql", {})
        mongo = q_data.get("mongodb", {})

        lines.append(
            f"| `{q_id}` | PostgreSQL | {pg.get('p50_ms', 0):.3f} | {pg.get('p90_ms', 0):.3f} | {pg.get('p95_ms', 0):.3f} | {pg.get('p99_ms', 0):.3f} | {pg.get('throughput_qps', 0):.1f} | {pg.get('error_rate_pct', 0):.2f}% |"
        )
        lines.append(
            f"| `{q_id}` | MongoDB | {mongo.get('p50_ms', 0):.3f} | {mongo.get('p90_ms', 0):.3f} | {mongo.get('p95_ms', 0):.3f} | {mongo.get('p99_ms', 0):.3f} | {mongo.get('throughput_qps', 0):.1f} | {mongo.get('error_rate_pct', 0):.2f}% |"
        )

    lines.extend([
        "",
        "## 3. Phân tích Paired Bootstrap Confidence Interval (95% CI)",
        "",
        "| Query | Độ lệch Trung vị (PG - Mongo ms) | 95% CI Thấp | 95% CI Cao | Ghi chú thống kê |",
        "|---|---:|---:|---:|---|",
    ])

    for q_id, q_data in queries_data.items():
        comp = q_data.get("comparison", {})
        boot = comp.get("paired_bootstrap", {})
        lines.append(
            f"| `{q_id}` | {boot.get('diff_median_ms', 0):.3f} | {boot.get('ci_95_lower_ms', 0):.3f} | {boot.get('ci_95_upper_ms', 0):.3f} | {boot.get('note', '')} |"
        )

    lines.extend([
        "",
        "## 4. Tuyên bố phương pháp luận & Hạn chế",
        "",
        "- Mọi phép đo latency chỉ bao gồm thời gian thực thi tại database adapter + fetch cursor (loại bỏ hoàn toàn network HTTP, JSON serialization, logging, canonical hashing).",
        "- Cả 2 hệ quản trị CSDL chạy trong container Docker độc lập với cùng quota CPU/RAM (2.0 vCPU, 2048MB RAM).",
        "- Không kết luận chung chung 'hệ nào nhanh hơn tuyệt đối'; hiệu năng phụ thuộc trực tiếp vào đặc thù cấu trúc dữ liệu quan hệ (JOIN, aggregation) và document schema (lookup vs embedding).",
        "",
        "---",
        "*Báo cáo được sinh tự động bởi BenchLab Reporting Engine tuân thủ SPEC.md.*",
    ])

    return "\n".join(lines)


def generate_csv_summary(summary: Dict[str, Any]) -> str:
    """Generate RFC 4180 compliant CSV summary of the experiment."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "experiment_id",
        "query_id",
        "engine",
        "p50_ms",
        "p90_ms",
        "p95_ms",
        "p99_ms",
        "mean_ms",
        "std_ms",
        "min_ms",
        "max_ms",
        "throughput_qps",
        "total_requests",
        "error_count",
        "error_rate_pct",
    ])

    exp_id = summary.get("experiment_id", "")
    queries_data = summary.get("queries", {})
    for q_id, q_data in queries_data.items():
        for engine in ["postgresql", "mongodb"]:
            e_data = q_data.get(engine, {})
            writer.writerow([
                exp_id,
                q_id,
                engine,
                e_data.get("p50_ms", 0),
                e_data.get("p90_ms", 0),
                e_data.get("p95_ms", 0),
                e_data.get("p99_ms", 0),
                e_data.get("mean_ms", 0),
                e_data.get("std_ms", 0),
                e_data.get("min_ms", 0),
                e_data.get("max_ms", 0),
                e_data.get("throughput_qps", 0),
                e_data.get("total_requests", 0),
                e_data.get("error_count", 0),
                e_data.get("error_rate_pct", 0),
            ])

    return output.getvalue()
