# DANH MỤC CÔNG VIỆC THEO PHASE (TASKS CHECKLIST)

**Dự án:** Đánh giá hiệu năng truy vấn giữa CSDL quan hệ (PostgreSQL) và CSDL NoSQL (MongoDB)  
**Phiên bản đặc tả:** 1.0  
**Ngày cập nhật:** 30/09/2026  

Trạng thái:
- `[x]` ĐÃ HOÀN TẤT (COMPLETED)
- `[/]` ĐANG THỰC HIỆN (IN_PROGRESS)
- `[ ]` CHƯA BẮT ĐẦU (PENDING)
- `[!]` BỊ CHẶN (BLOCKED)

---

## Phase 0: Khởi tạo phạm vi và kiểm tra môi trường
- **Mục tiêu:** Xác minh phần cứng, công cụ thực tế, chốt phiên bản, tạo kế hoạch, lập skeleton repo và vượt qua Gate G0.
- **Tiêu chí nghiệm thu Gate G0:** Mọi giả định được ghi; biết rõ chạy profile nào và cách tái lập môi trường. Lệnh doctor kiểm tra prereqs không lỗi chặn; secret không nằm trong git.

| ID | Nhiệm vụ | Trạng thái | Bằng chứng / Đường dẫn |
|---|---|:---:|---|
| T0.1 | Kiểm tra cấu trúc repo hiện có, bảo đảm không đè file ngoài phạm vi | [x] | Chỉ có `docs/SPEC.md`, đã khởi tạo git repo sạch |
| T0.2 | Kiểm tra phần cứng (CPU, RAM, ổ đĩa), OS/WSL, công cụ (Python, Node, Docker) và port khả dụng | [x] | i5-6300U (2 cores, 4 threads), 15.86 GiB RAM, Python 3.12.6, Node v22.16.0; port 5432, 27017, 8000, 5173 đều trống |
| T0.3 | Chốt phiên bản CSDL (PG 17.2, Mongo 8.0.4) và hạn ngạch tài nguyên (2 vCPU, 2048MB) | [x] | `docs/decisions.md` (DEC-001, DEC-002) |
| T0.4 | Tạo `.env.example`, `.gitignore`, `pyproject.toml`, `requirements.txt` | [x] | File tạo tại root; kiểm tra `git status --ignored` không lọt secret |
| T0.5 | Khởi tạo skeleton cấu trúc thư mục repo theo mục 3.3 đặc tả | [x] | `backend/app/`, `backend/benchlab/`, `queries/`, `configs/`, `tests/`, `scripts/`, `results/` |
| T0.6 | Xây dựng kịch bản kiểm tra môi trường `scripts/doctor.py` và `python -m benchlab doctor` | [x] | `scripts/doctor.py`, `backend/benchlab/cli.py`; test chạy đạt 9 pass, 0 lỗi chặn |
| T0.7 | Xây dựng Implementation Plan, Tasks checklist, Decisions, Limitations, Test Report, Walkthrough | [x] | `docs/*.md` |

**Kết quả Gate G0:** **PASS** (Đủ điều kiện chuyển sang Phase 1 sau khi review).

---

## Phase 1: Hạ tầng và kết nối (G1)
- **Phụ thuộc:** Gate G0.

| ID | Nhiệm vụ | Trạng thái | Bằng chứng / Đường dẫn |
|---|---|:---:|---|
| T1.1 | Soạn thảo Docker Compose cho PostgreSQL 17.2, MongoDB 8.0.4, API/worker và Frontend | [ ] | `docker-compose.yml` |
| T1.2 | Cấu hình volume, network namespace, tài nguyên cpus: 2.0, mem_limit: 2048m | [ ] | `docker-compose.yml` |
| T1.3 | Cấu hình healthcheck, retry giới hạn và log cho container | [ ] | `docker-compose.yml` |
| T1.4 | Xây dựng giao diện adapter cốt lõi: `health`, `prepare`, `execute`, `explain`, `describe_indexes` | [ ] | `backend/app/adapters/` |
| T1.5 | Xây dựng API `/api/health` và `/api/environment` | [ ] | `backend/app/api/` |
| T1.6 | Viết kiểm thử kết nối: DB online/down, sai credential, timeout, kiểm chứng limits | [ ] | `tests/integration/test_connectivity.py` |

---

## Phase 2: Schema, generator và nạp dữ liệu (G2)
- **Phụ thuộc:** Gate G1.

| ID | Nhiệm vụ | Trạng thái | Bằng chứng / Đường dẫn |
|---|---|:---:|---|
| T2.1 | Tạo DDL PostgreSQL, MongoDB validators cho Track A (Reference) và Track B (Embedded) | [ ] | `backend/app/domain/schema.py`, `queries/` |
| T2.2 | Viết bộ sinh dữ liệu streaming chuẩn từ một nguồn (seed cố định, tiền nguyên, UTC ms, ID int64) | [ ] | `backend/app/datasets/generator.py` |
| T2.3 | Tạo dataset fixture (50 orders) và các profile small/medium/large | [ ] | `configs/profiles/` |
| T2.4 | Viết bộ nạp bulk import theo batch, xử lý idempotent | [ ] | `backend/app/datasets/loader.py` |
| T2.5 | Xây dựng công cụ kiểm tra toàn vẹn và tính canonical checksums độc lập | [ ] | `backend/app/datasets/validator.py` |
| T2.6 | Tạo danh mục index I0 và I1 có version | [ ] | `configs/indexes.py` |
| T2.7 | Kiểm thử DATA-01 đến DATA-06: seed determinism, duplicate rejection, foreign key failure | [ ] | `tests/correctness/test_data_integrity.py` |

---

## Phase 3: Query catalog và kiểm tra kết quả (G3)
- **Phụ thuộc:** Gate G2.

| ID | Nhiệm vụ | Trạng thái | Bằng chứng / Đường dẫn |
|---|---|:---:|---|
| T3.1 | Hiện thực hóa Q1–Q8 và biến thể Q7 trên cả PostgreSQL và MongoDB adapters | [ ] | `queries/postgresql/`, `queries/mongodb/` |
| T3.2 | Tạo schema output chuẩn hóa, parameter pools (>= 200 bộ) và deterministic traces | [ ] | `backend/app/domain/query_catalog.py` |
| T3.3 | Xây dựng oracle Python độc lập tính toán kết quả trên fixture dataset | [ ] | `tests/correctness/oracle.py` |
| T3.4 | Xây dựng endpoint `/api/queries`, `/api/queries/{id}/execute`, `/api/queries/{id}/explain` | [ ] | `backend/app/api/queries.py` |
| T3.5 | Kiểm thử QUERY-01 đến QUERY-07 trên fixture và small | [ ] | `tests/correctness/test_queries_correctness.py` |

---

## Phase 4: Benchmark runner và lưu trữ dữ liệu thô (G4)
- **Phụ thuộc:** Gate G3.

| ID | Nhiệm vụ | Trạng thái | Bằng chứng / Đường dẫn |
|---|---|:---:|---|
| T4.1 | Hiện thực hóa Mode L (Latency tuần tự, fixed-count) và Mode T (Throughput, closed-loop) | [ ] | `backend/app/benchmark/runner.py` |
| T4.2 | Quản lý connection pool trước timed region; đo bằng `time.perf_counter_ns()` | [ ] | `backend/app/benchmark/timer.py` |
| T4.3 | Hiện thực warm-up protocol, alternating engine order, randomized query seed | [ ] | `backend/app/benchmark/protocol.py` |
| T4.4 | Xây dựng cơ chế thu thập mẫu raw (samples.jsonl, resources.csv, manifest.json) | [ ] | `backend/app/benchmark/recorder.py` |
| T4.5 | Hiện thực exclusive lock toàn cục, graceful cancel, và crash recovery (INTERRUPTED) | [ ] | `backend/app/benchmark/lock.py` |
| T4.6 | Kiểm thử BENCH-01 đến BENCH-11 bằng fake adapter và DB thật cho E0 smoke | [ ] | `tests/unit/test_benchmark_runner.py` |

---

## Phase 5: Dashboard và điều phối job (G5)
- **Phụ thuộc:** Gate G4.

| ID | Nhiệm vụ | Trạng thái | Bằng chứng / Đường dẫn |
|---|---|:---:|---|
| T5.1 | Khởi tạo frontend React + TypeScript + Vite, thiết kế hệ thống giao diện cao cấp | [ ] | `frontend/` |
| T5.2 | Xây dựng Trang Tổng quan (`/`), Trang Dữ liệu (`/datasets`) | [ ] | `frontend/src/pages/` |
| T5.3 | Xây dựng Trang Truy vấn (`/queries`) có syntax highlight và diff kết quả | [ ] | `frontend/src/pages/` |
| T5.4 | Xây dựng Trang Benchmark (`/benchmark`) với dry-run, progress và cancel | [ ] | `frontend/src/pages/` |
| T5.5 | Xây dựng Trang Kết quả (`/results/:id`) và Trang Kiểm thử (`/tests`) | [ ] | `frontend/src/pages/` |
| T5.6 | Kiểm thử E2E: Data -> Validate -> Query -> E0 -> Results | [ ] | `tests/e2e/test_dashboard_flow.py` |

---

## Phase 6: Phân tích, biểu đồ và xuất báo cáo (G6)
- **Phụ thuộc:** Gate G4, G5.

| ID | Nhiệm vụ | Trạng thái | Bằng chứng / Đường dẫn |
|---|---|:---:|---|
| T6.1 | Hiện thực module phân tích thống kê: median per-run, bootstrap 95% CI theo cặp | [ ] | `backend/app/reports/statistics.py` |
| T6.2 | Tạo module vẽ biểu đồ (latency p50/p95/p99, throughput, error rate, CPU/RAM) | [ ] | `backend/app/reports/charts.py` |
| T6.3 | Hiện thực chức năng xuất bundle: `report.md`, `summary.csv`, `comparison.csv`, ZIP | [ ] | `backend/app/reports/exporter.py` |
| T6.4 | Kiểm thử STAT-01 đến STAT-05 và REPORT-01, REPORT-02 với dữ liệu độc lập | [ ] | `tests/unit/test_statistics.py` |

---

## Phase 7: Kiểm thử toàn diện hệ thống và ổn định hóa (G7)
- **Phụ thuộc:** Gate G1 đến G6.

| ID | Nhiệm vụ | Trạng thái | Bằng chứng / Đường dẫn |
|---|---|:---:|---|
| T7.1 | Chạy toàn bộ ma trận test 33 ca (ENV-01 -> RELEASE-01) | [ ] | `tests/` |
| T7.2 | Kiểm tra an toàn: ngăn chặn SQL injection, chống path traversal trong export | [ ] | `tests/unit/test_security.py` |
| T7.3 | Xử lý triệt để mọi lỗi Critical và High; cập nhật `docs/test-report.md` | [ ] | `docs/test-report.md` |

---

## Phase 8: Thực nghiệm benchmark chính thức (G8)
- **Phụ thuộc:** Gate G7; commit và cấu hình đã khóa.

| ID | Nhiệm vụ | Trạng thái | Bằng chứng / Đường dẫn |
|---|---|:---:|---|
| T8.1 | Chạy E0 (Smoke test), kiểm chứng luồng hoạt động | [ ] | `results/E0-...` |
| T8.2 | Chạy E1 (Quy mô dữ liệu & Index) trên small và medium với 5 repeat | [ ] | `results/E1-...` |
| T8.3 | Chạy E2 (Tải đồng thời C=1, 8, 32) trên medium với 5 repeat | [ ] | `results/E2-...` |
| T8.4 | Chạy E3 (Mô hình Track A vs Track B cho Q8) với 5 repeat | [ ] | `results/E3-...` |
| T8.5 | Chạy thử nghiệm pilot E1-large và tổng hợp kết quả chính thức | [ ] | `results/manifest.json` |

---

## Phase 9: Đánh giá, báo cáo và diễn tập demo (G9)
- **Phụ thuộc:** Gate G8.

| ID | Nhiệm vụ | Trạng thái | Bằng chứng / Đường dẫn |
|---|---|:---:|---|
| T9.1 | Soạn thảo báo cáo nghiên cứu hoàn chỉnh theo 10 chương quy định tại mục 14 | [ ] | `docs/final-report.md` |
| T9.2 | Phân tích giải thích kết quả dựa trên Execution Plans (`EXPLAIN`) | [ ] | `docs/final-report.md` |
| T9.3 | Soạn kịch bản trình bày demo 10–12 phút chi tiết theo phân bổ thời gian mục 13 | [ ] | `docs/demo-script.md` |
| T9.4 | Chuẩn bị bộ câu trả lời phản biện cho 10 câu hỏi cốt lõi | [ ] | `docs/demo-script.md` |

---

## Phase 10: Đóng gói và bàn giao (G10)
- **Phụ thuộc:** Gate G9.

| ID | Nhiệm vụ | Trạng thái | Bằng chứng / Đường dẫn |
|---|---|:---:|---|
| T10.1 | Hoàn thiện `README.md` với quy trình clean-start tái lập từ đầu | [ ] | `README.md` |
| T10.2 | Kiểm tra lockfile, `.env.example`, không rò rỉ bí mật | [ ] | `README.md`, `checksums.sha256` |
| T10.3 | Đóng gói mã nguồn và tài liệu nghiệm thu | [ ] | Release bundle |
