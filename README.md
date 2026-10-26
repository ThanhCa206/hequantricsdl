# BenchLab: Nền Tảng Thực Nghiệm Đối Chuẩn Hiệu Năng Truy Vấn PostgreSQL 17 vs MongoDB 8

> **Đề tài:** Đánh giá định lượng hiệu năng truy vấn giữa Hệ quản trị CSDL quan hệ (PostgreSQL 17.2) và CSDL NoSQL hướng tài liệu (MongoDB 8.0.4) dưới ngân sách tài nguyên bình đẳng (2.0 vCPU, 2048MB RAM per container).  
> **Phiên bản Đặc tả:** SPEC v1.0 | **Bộ kiểm thử:** 61/61 PASS (100%) | **Trạng thái:** Hoàn tất nghiệm thu (Phase 10 - Gate G10 PASS)

---

## 1. Giới Thiệu Dự Án

**BenchLab** là hệ thống phần mềm đối chuẩn khoa học độc lập được xây dựng nhằm giải quyết tranh luận kinh điển giữa **SQL (PostgreSQL)** và **NoSQL (MongoDB)**. Thay vì đưa ra các nhận định cảm tính, BenchLab áp dụng phương pháp luận đo lường thực nghiệm chặt chẽ:
1. **Ngân sách tài nguyên bình đẳng:** Docker Compose quota cố định `cpus: '2.0'`, `mem_limit: 2048m` cho từng container CSDL.
2. **Loại bỏ biến gây nhiễu dữ liệu:** Sinh dữ liệu đối chuẩn từ một bộ sinh ngẫu nhiên xác định với `seed=42`, đảm bảo cấu trúc và số lượng bản ghi tương đương tuyệt đối giữa hai bên.
3. **Hai mô hình so sánh song song:**
   - **Track A (Mô hình Tham chiếu):** Đối chiếu phép `JOIN` chuẩn hóa 3NF của PostgreSQL với stage `$lookup` của MongoDB.
   - **Track B (Mô hình Nhúng):** Đối chiếu với mô hình mảng document con tự chứa (`Embedded Array`) của MongoDB.
4. **Đo lường đa chiều:** Phân tích độ trễ phân vị ($p50, p90, p95, p99$), thông lượng bão hòa ($QPS$), Kế hoạch thực thi giải phẫu (`EXPLAIN`), và tính toán khoảng tin cậy thống kê **Paired Bootstrap 95% CI**.

---

## 2. Kiến Trúc Hệ Thống

```
+-----------------------------------------------------------------------------------+
|                        BENCHLAB WEB DASHBOARD (React + Vite)                      |
|                  Dark Theme #080c14 | Real-time Metrics | Port 5173               |
+-----------------------------------------+-----------------------------------------+
                                          | REST API / Polling
+-----------------------------------------v-----------------------------------------+
|                          FASTAPI BACKEND SERVICE (Python 3.12)                     |
|         Global ExperimentLock | Runner Daemon | Results Parser | Port 8000        |
+--------------------+--------------------------------------+-----------------------+
                     |                                      |
       psycopg 3 pool|                                      |PyMongo pool
+--------------------v-------------------+    +-------------v-----------------------+
|        PostgreSQL 17.2-alpine          |    |            MongoDB 8.0.4            |
|       Port: 5432 (benchlab-postgres)   |    |      Port: 27017 (benchlab-mongodb)  |
| Quota: 2.0 vCPU | 2048MB RAM | work_mem |    | Quota: 2.0 vCPU | 2048MB RAM | WiredT |
+----------------------------------------+    +-------------------------------------+
```

---

## 3. Tóm Tắt Kết Quả Đo Đạc Thực Nghiệm Chính Thức

Dữ liệu được trích xuất từ 16 bundles đo lường thực tế trên tập dữ liệu `small` (10,000 đơn hàng, 1,000 khách hàng, 500 sản phẩm, 29,887 chi tiết đơn hàng):

### 3.1. Độ trễ tuần tự Mode L (Thực nghiệm E1 - 5 Paired Repeats, 100 fixed iterations)
| Mã Truy Vấn | Tên Nghiệp Vụ | PostgreSQL p50 | MongoDB p50 | Tỷ số Tốc độ (Speedup) | Ghi chú & Kế hoạch thực thi |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Q1** | Point Lookup theo Order ID | **4.56 ms** | 5.70 ms | **PG nhanh hơn 1.25x** | Index Scan vs IXSCAN B-Tree |
| **Q2** | Lọc phạm vi ngày theo Customer | 5.92 ms | **4.64 ms** | **Mongo nhanh hơn 1.28x** | MongoDB gom tài liệu BSON nhanh |
| **Q3** | Lọc đa trường trạng thái + ngày | 7.12 ms | **5.11 ms** | **Mongo nhanh hơn 1.39x** | IXSCAN compound index |
| **Q4** | Đếm vô hướng trạng thái đơn | **2.32 ms** | 3.28 ms | **PG nhanh hơn 1.41x** | Aggregate đếm trên B-Tree |
| **Q5** | Doanh thu theo tháng (Group/Sum) | **3.73 ms** | 8.78 ms | **PG nhanh hơn 2.35x** | Hash Aggregate tối ưu trong RAM |
| **Q6** | Top 20 khách hàng chi tiêu (JOIN) | **7.01 ms** | 24.59 ms | **PG nhanh hơn 3.51x** | **Hash Join in-memory** vs Indexed Nested Loop $lookup |
| **Q7_offset**| Phân trang Offset (Trang sâu 20) | 12.01 ms | **11.45 ms** | Tương đương (p>0.05) | Chi phí quét bỏ qua 200 bản ghi |
| **Q7_keyset**| Phân trang Keyset Seek | 11.73 ms | **4.98 ms** | **Mongo nhanh hơn 2.35x** | Con trỏ nhảy trực tiếp theo index |
| **Q8_embed** | Đọc chi tiết đơn hàng (Track B) | 5.50 ms *(JOIN)* | **1.70 ms** *(Embed)* | **Mongo nhanh hơn 3.24x** | Đọc 1 document tự chứa, không JOIN |

### 3.2. Thông lượng tải đồng thời Mode T (Thực nghiệm E2 - Concurrency C=8 Workers)
* **PostgreSQL:** Thống trị các tác vụ phân tích và tổng hợp:
  - **Q4 (Đếm):** **180.9 QPS** (gấp **2.85 lần** MongoDB 63.4 QPS).
  - **Q5 (Doanh thu gom nhóm):** **79.5 QPS** (gấp **2.91 lần** MongoDB 27.3 QPS).
  - **Q6 (JOIN Top 20):** **51.1 QPS** (gấp **2.62 lần** MongoDB 19.5 QPS).
* **MongoDB:** Duy trì thông lượng ổn định ở các truy vấn đọc đơn giản:
  - **Q1 (Đọc điểm):** **76.2 QPS** vs PG 71.2 QPS.
  - **Q3 (Lọc trạng thái):** **46.2 QPS** vs PG 24.1 QPS.

---

## 4. Hướng Dẫn Tái Lập Nhanh (Clean-Start Quickstart)

### 4.1. Yêu cầu môi trường
* **Hệ điều hành:** Windows 10/11, macOS, hoặc Linux x86_64.
* **Docker Desktop:** Đã cài đặt và đang chạy Docker Engine.
* **Python:** Phiên bản 3.11 hoặc 3.12.
* **Node.js:** Phiên bản 18+ và npm.

### 4.2. Khởi động hạ tầng CSDL qua Docker Compose
```powershell
# 1. Sao chép biến môi trường mẫu
cp .env.example .env

# 2. Khởi động PostgreSQL 17 và MongoDB 8 (áp dụng hạn ngạch 2.0 CPU, 2048MB RAM)
docker compose up -d

# 3. Kiểm tra trạng thái container
docker compose ps
```

### 4.3. Cài đặt phụ thuộc Python & Node.js
```powershell
# Cài đặt backend dependencies
pip install -r requirements.txt

# Cài đặt frontend dependencies
cd frontend
npm install
cd ..
```

### 4.4. Nạp dữ liệu đối chuẩn và tạo chỉ mục
```powershell
# Thiết lập đường dẫn module
$env:PYTHONPATH="backend;. "

# Kiểm tra sức khỏe kết nối CSDL
python -m benchlab health

# Nạp dữ liệu tập small (seed 42)
python -m benchlab dataset load --profile small --seed 42

# Áp dụng bộ chỉ mục chuẩn I1
python -m benchlab indexes apply --profile I1

# Xác thực tính tương đương ngữ nghĩa
python -m benchlab dataset validate
```

### 4.5. Khởi chạy toàn bộ hệ thống kiểm thử tự động
```powershell
$env:PYTHONPATH="backend;. "
python -m pytest tests/ -v
# Kết quả: 61 passed in ~9.89s (100% PASS)
```

### 4.6. Chạy ứng dụng Web Dashboard
Mở 2 cửa sổ terminal độc lập:
```powershell
# Terminal 1: Backend API (Port 8000)
$env:PYTHONPATH="backend;. "
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2: Frontend Vite Dashboard (Port 5173)
cd frontend
npm run dev
```
Truy cập giao diện tại: **`http://localhost:5173`**

### 4.7. Chạy Benchmark dòng lệnh (CLI Mode)
Bạn có thể khởi chạy trực tiếp các thí nghiệm benchmark từ CLI mà không cần qua trình duyệt:
```powershell
$env:PYTHONPATH="backend;. "

# Chạy Smoke Test (E0)
python -m benchlab benchmark --experiment E0

# Chạy đo độ trễ tuần tự Mode L (E1)
python -m benchlab benchmark --experiment E1

# Xuất báo cáo tóm tắt
python -m benchlab report --run-id latest
```

---

## 5. Cấu Trúc Thư Mục Dự Án

```
DETAICSDL/
├── backend/                  # FastAPI Application & Benchmark Engine
│   ├── app/
│   │   ├── adapters/         # Database Drivers (PostgresAdapter, MongoAdapter)
│   │   ├── api/              # REST Endpoints (health, datasets, queries, benchmark, results, tests)
│   │   ├── benchmark/        # ExperimentLock, Protocol Runner, MonotonicTimer, Recorder
│   │   ├── datasets/         # DataGenerator (seed=42), DatasetLoader, Semantic Validator
│   │   ├── domain/           # Models, Schemas, QueryCatalog (Q1-Q8)
│   │   └── reports/          # Exporter (Markdown, CSV), Bootstrap Statistics
│   └── benchlab/             # CLI commands implementation
├── frontend/                 # React 18 + TypeScript + Vite Dashboard
│   ├── src/
│   │   ├── components/       # Header, Navigation, StatusBanner, MetricCard
│   │   ├── pages/            # Overview, Datasets, Queries, Benchmark, Results, Tests, System
│   │   ├── api.ts            # Client API Adapter
│   │   └── index.css         # Dark Theme System (#080c14)
├── configs/                  # Benchmark profiles & Index profiles (I0, I1)
├── docs/                     # Tài liệu nghiên cứu chuẩn mực
│   ├── SPEC.md               # Tài liệu đặc tả kỹ thuật chi tiết v1.0
│   ├── tasks.md              # Nhật ký thực thi 10 Phase và 11 Quality Gates
│   ├── final-report.md       # Báo cáo khoa học hoàn chỉnh 10 chương
│   ├── demo-script.md        # Kịch bản thuyết trình 10-12 phút & 10 câu hỏi phản biện
│   └── walkthrough.md        # Hướng dẫn chi tiết từng tính năng
├── queries/                  # Cú pháp truy vấn chuẩn (SQL & Mongo Aggregation Pipeline)
├── results/                  # 16 bundles dữ liệu đo thô (manifest, samples.jsonl, plans)
├── tests/                    # 61 Automated Tests (Unit, Integration, Correctness, Security, E2E)
├── docker-compose.yml        # Docker Compose cấu hình tài nguyên PostgreSQL 17 & MongoDB 8
├── requirements.txt          # Danh mục thư viện Python có ghim phiên bản
└── README.md                 # Tài liệu hướng dẫn này
```

---

## 6. Đóng Gói Bàn Giao & Nghiệm Thu (Phase 10 - Gate G10)

| Tiêu Chí Nghiệm Thu | Kết Quả Thực Tế | Trạng Thái |
| :--- | :--- | :---: |
| **Docker Compose cách ly tài nguyên** | Giới hạn 2.0 CPU, 2048MB RAM độc lập cho PG & MongoDB | **PASS** |
| **Dữ liệu đối chuẩn thống nhất** | 10,000 đơn hàng, khớp số lượng và SHA-256 trên cả 2 hệ | **PASS** |
| **Độ bao phủ kiểm thử** | 61/61 tests tự động đạt 100% PASS | **PASS** |
| **Bảo mật hệ thống** | Chặn SQL Injection, MongoDB NoSQL Injection, Path Traversal | **PASS** |
| **Báo cáo nghiên cứu khoa học** | Hoàn thành 10 chương theo cấu trúc Mục 14 SPEC.md | **PASS** |
| **Kịch bản thuyết trình & phản biện** | 10–12 phút chi tiết từng phút + 10 câu trả lời cốt lõi | **PASS** |
| **Khả năng tái lập (Reproducibility)** | Clean-start 100% bằng script CLI hoặc Web Dashboard | **PASS** |

---
*Dự án BenchLab được phát triển và nghiệm thu đầy đủ theo đặc tả kỹ thuật SPEC v1.0.*
