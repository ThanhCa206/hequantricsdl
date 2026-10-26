# PT Lab: Nền Tảng Đối Chuẩn Hiệu Năng Truy Vấn PostgreSQL 17.2 vs MongoDB 8.0.4

> **PT Lab** là hệ thống phần mềm thực nghiệm đo lường và đối sánh định lượng hiệu năng truy vấn giữa Hệ quản trị CSDL quan hệ (**PostgreSQL 17.2**) và CSDL NoSQL hướng tài liệu (**MongoDB 8.0.4**) dưới ngân sách tài nguyên bình đẳng (2.0 vCPU, 2048MB RAM per container).

---

## 1. Giới Thiệu

**PT Lab** được thiết kế để giải quyết bài toán so sánh hiệu năng giữa SQL và NoSQL một cách khách quan, loại bỏ các biến gây nhiễu:
- **Tài nguyên kiểm soát chặt chẽ:** Giới hạn quota cứng cố định `cpus: '2.0'`, `mem_limit: 2048m` bằng Docker cgroups cho từng hệ quản trị CSDL.
- **Dữ liệu đồng nhất tuyệt đối:** Sinh dữ liệu đối chuẩn tự động từ một nguồn phát tất định theo hạt giống (`seed=42`), bảo đảm số lượng bản ghi và quan hệ tương đương 100% giữa hai hệ.
- **8 Mẫu truy vấn nghiệp vụ chuẩn hóa (Q1–Q8):** Bao gồm Point Lookup, Range Filter, Aggregation, Group/Sum, Multi-table JOIN vs `$lookup`, Phân trang Keyset/Offset, và so sánh Mô hình Tham chiếu (Track A) với Mô hình Nhúng (Track B - Embedded Array).
- **Bộ kiểm thử toàn diện:** Tích hợp 61 bài kiểm thử tự động (Unit, Integration, Correctness, E2E) xác minh tính đúng đắn và an toàn hệ thống.

---

## 2. Hướng Dẫn Cài Đặt & Vận Hành (Quickstart)

### 2.1. Yêu cầu môi trường
* **Hệ điều hành:** Windows 10/11, macOS, hoặc Linux x86_64.
* **Docker Desktop:** Đã cài đặt và đang chạy Docker Engine.
* **Python:** Phiên bản 3.11 hoặc 3.12.
* **Node.js:** Phiên bản 18 trở lên và npm.

---

### 2.2. Bước 1: Khởi động cơ sở dữ liệu qua Docker Compose

Khởi động PostgreSQL 17.2 và MongoDB 8.0.4 trong môi trường container cách ly:

```bash
# 1. Tạo tệp cấu hình môi trường từ mẫu
cp .env.example .env

# 2. Khởi động 2 container CSDL chạy ngầm (đã cấu hình sẵn quota 2 vCPU, 2048MB RAM)
docker compose up -d

# 3. Kiểm tra trạng thái hoạt động của container
docker compose ps
```

---

### 2.3. Bước 2: Cài đặt thư viện Backend & Frontend

```bash
# Cài đặt thư viện Python (FastAPI, Psycopg3, PyMongo, Pytest,...)
pip install -r requirements.txt

# Cài đặt thư viện Frontend (React, Vite, Recharts, Lucide,...)
cd frontend
npm install
cd ..
```

---

### 2.4. Bước 3: Nạp dữ liệu đối chuẩn & Tạo chỉ mục (CLI)

Mở terminal tại thư mục gốc của dự án:

**Trên Windows (PowerShell):**
```powershell
$env:PYTHONPATH="backend;."

# Kiểm tra sức khỏe kết nối CSDL
python -m benchlab health

# Nạp dữ liệu đối chuẩn tập 'small' (seed 42)
python -m benchlab dataset load --profile small --seed 42

# Áp dụng bộ chỉ mục tối ưu I1
python -m benchlab indexes apply --profile I1

# Xác thực tính toàn vẹn và tương đương ngữ nghĩa
python -m benchlab dataset validate
```

**Trên Linux / macOS (Bash):**
```bash
export PYTHONPATH="backend:."

# Kiểm tra sức khỏe kết nối CSDL
python -m benchlab health

# Nạp dữ liệu đối chuẩn tập 'small' (seed 42)
python -m benchlab dataset load --profile small --seed 42

# Áp dụng bộ chỉ mục tối ưu I1
python -m benchlab indexes apply --profile I1

# Xác thực tính toàn vẹn và tương đương ngữ nghĩa
python -m benchlab dataset validate
```

---

### 2.5. Bước 4: Chạy bộ kiểm thử tự động (Verification)

Xác minh toàn bộ tính năng kết nối, an toàn SQL, thuật toán thống kê và tính tương đương truy vấn:

```powershell
# Windows
$env:PYTHONPATH="backend;."
python -m pytest tests/ -v

# Linux/macOS
export PYTHONPATH="backend:."
python -m pytest tests/ -v
```
> Kết quả mong đợi: **61 passed** (100% PASS).

---

### 2.6. Bước 5: Khởi chạy ứng dụng Web Dashboard (PT Lab)

Mở 2 cửa sổ terminal độc lập:

**Terminal 1 — Backend API Server (Port 8000):**
```powershell
# Windows
$env:PYTHONPATH="backend;."
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Linux/macOS
export PYTHONPATH="backend:."
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 — Frontend Single Page App (Port 5173):**
```bash
cd frontend
npm run dev
```

Mở trình duyệt web và truy cập: **`http://localhost:5173`**

---

## 3. Các Tính Năng Trên Giao Diện PT Lab

Giao diện Web **PT Lab** hỗ trợ song song cả hai chế độ **Giao diện Sáng (Light Theme)** và **Giao diện Tối (Dark Theme)** với các phân hệ chính:

1. **Tổng Quan (Overview):** Giám sát trạng thái hoạt động của PostgreSQL & MongoDB, quota tài nguyên, và thống kê tổng quan.
2. **Dữ Liệu (Datasets):** Tùy chọn quy mô profile (Fixture, Small, Medium, Large), sinh dữ liệu streaming theo seed và xác thực mã băm SHA-256.
3. **Truy Vấn (Queries):** Khảo sát mã nguồn SQL và MQL tương đương của 8 nhóm truy vấn Q1–Q8, thực thi trực tiếp trên giao diện và so sánh kết quả trả về.
4. **Benchmark Studio:** Thiết lập và khởi chạy bài đo độ trễ tuần tự (Mode L) hoặc tải thông lượng đồng thời (Mode T), hỗ trợ Dry-run và hủy tác vụ an toàn.
5. **Kết Quả & Báo Cáo (Results):** Biểu đồ Bar Chart độ trễ phân vị (p50/p90/p95/p99), biểu đồ Radar hồ sơ năng lực, tính toán khoảng tin cậy thống kê **Paired Bootstrap 95% CI**, cùng tính năng xuất báo cáo định dạng Markdown và CSV.
6. **Kiểm Thử (Tests):** Trung tâm giám sát và chạy trực tiếp ma trận kiểm thử hệ thống ngay trên giao diện web.

---

## 4. Tóm Tắt Lệnh Dòng Lệnh CLI (`benchlab`)

Hệ thống cung cấp CLI độc lập phục vụ tự động hóa mà không cần mở trình duyệt:

| Lệnh | Ý nghĩa |
|---|---|
| `python -m benchlab doctor` | Kiểm tra hệ điều hành, cổng mạng và các công cụ cần thiết |
| `python -m benchlab health` | Kiểm tra kết nối và độ trễ ping tới PostgreSQL & MongoDB |
| `python -m benchlab dataset load --profile small` | Tải dữ liệu vào cả 2 cơ sở dữ liệu |
| `python -m benchlab indexes apply --profile I1` | Tạo bộ chỉ mục tối ưu cho các bảng và collection |
| `python -m benchlab dataset validate` | Đối chiếu SHA-256 kiểm tra tính tương đương dữ liệu |
| `python -m benchlab benchmark --experiment E0` | Chạy nhanh thực nghiệm kiểm chứng (Smoke Test) |
| `python -m benchlab benchmark --experiment E1` | Chạy đo đạc độ trễ phân vị Mode L (Latency) |
| `python -m benchlab benchmark --experiment E2` | Chạy đo tải đồng thời Mode T (Throughput Concurrency) |

---

## 5. Cấu Trúc Thư Mục

```
.
├── backend/                  # Mã nguồn FastAPI Backend & Benchmark Runner
│   ├── app/
│   │   ├── adapters/         # Adapter kết nối PostgreSQL & MongoDB
│   │   ├── api/              # REST API endpoints (datasets, benchmark, results,...)
│   │   ├── benchmark/        # Timer chính xác cao nano-second, locks, runner
│   │   ├── datasets/         # Generator dữ liệu streaming, loader, validator
│   │   └── reports/          # Tính toán thống kê percentiles, bootstrap 95% CI, exporter
│   └── benchlab/             # CLI command-line interface
├── frontend/                 # Giao diện Web SPA (React + TypeScript + Vite + Recharts)
│   ├── src/
│   │   ├── components/       # UI components, biểu đồ trực quan hóa, ThemeToggle
│   │   └── pages/            # 7 màn hình chức năng chính của PT Lab
├── configs/                  # Cấu hình dataset profiles (small/medium/large) & indexes (I0/I1)
├── queries/                  # Mã nguồn truy vấn mẫu SQL (PostgreSQL) và MQL (MongoDB)
├── scripts/                  # Kịch bản kiểm tra môi trường doctor.py
├── tests/                    # 61 ca kiểm thử tự động (Unit, Correctness, Integration, E2E)
├── docker-compose.yml        # Cấu hình container hóa môi trường kiểm soát tài nguyên
├── requirements.txt          # Danh sách thư viện Python
└── README.md                 # Tài liệu hướng dẫn cài đặt & vận hành PT Lab
```
