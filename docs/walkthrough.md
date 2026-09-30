# HƯỚNG DẪN VẬN HÀNH VÀ BẰNG CHỨNG THỰC HIỆN (WALKTHROUGH)

**Dự án:** Đánh giá hiệu năng truy vấn giữa CSDL quan hệ (PostgreSQL) và CSDL NoSQL (MongoDB)  
**Phiên bản đặc tả:** 1.0  
**Giai đoạn hiện tại:** Hoàn tất Phase 0 (Gate G0)  
**Ngày thực hiện:** 30/09/2026  

---

## 1. Các lệnh đã được kiểm chứng trong Phase 0

Toàn bộ các lệnh dưới đây đã được thực thi trực tiếp trên máy trạm và cho kết quả thành công:

### 1.1. Khởi tạo kho mã nguồn và cấu hình môi trường
```bash
# 1. Khởi tạo Git repository sạch
git init

# 2. Tạo skeleton thư mục và các gói mã nguồn
python scripts/setup_skeleton.py

# 3. Kiểm tra tính an toàn của gitignore và bí mật
git status --ignored
```

### 1.2. Chạy lệnh chẩn đoán môi trường Pre-flight (Doctor)
Có thể chạy theo một trong hai cách:

```bash
# Cách 1: Sử dụng script trực tiếp
python scripts/doctor.py

# Cách 2: Sử dụng BenchLab CLI module
python -m benchlab doctor
```

---

## 2. Bằng chứng thực thi thực tế (Execution Evidence)

### 2.1. Đầu ra thực tế từ `python -m benchlab doctor`

```text
======================================================================
 BenchLab Environment Doctor (Pre-flight Checks)
 SPEC Version: 1.0 | Target: PostgreSQL vs MongoDB Benchmark
======================================================================

[1] Hệ điều hành: Windows 10 (10.0.19045)
[2] CPU Logical Processors: 4
[3] RAM tổng: 15.86 GiB
[4] Dung lượng ổ đĩa tại D:: 62.64 GB trống
[5] Python: 3.12.6
[6] Node.js: v22.16.0 | npm: 10.9.2
[7] Git: git version 2.51.1.windows.1
[8] Docker: CHƯA PHÁT HIỆN TRONG PATH (Cần thiết cho Phase 1 hạ tầng)

[9] Kiểm tra các port dịch vụ:
    - Port  5432 (PostgreSQL        ): TRỐNG (Sẵn sàng)
    - Port 27017 (MongoDB           ): TRỐNG (Sẵn sàng)
    - Port  8000 (FastAPI Backend   ): TRỐNG (Sẵn sàng)
    - Port  5173 (Vite Frontend     ): TRỐNG (Sẵn sàng)

[10] Kiểm tra tệp cấu hình:
    - .env.example: TỒN TẠI (Đạt chuẩn)
    - .env: TỒN TẠI

======================================================================
 KẾT QUẢ ĐÁNH GIÁ MÔI TRƯỜNG PRE-FLIGHT
======================================================================
 Pass: 9 mục
 Cảnh báo: 1 mục
 Lỗi chặn: 0 mục

--- CÁC CẢNH BÁO / LƯU Ý HẠ TẦNG ---
 [!] Docker / Compose: Docker hoặc Docker Compose chưa được cài đặt hoặc chưa có trong PATH.
     Cách xử lý: Để chạy theo kiến trúc container: Cài đặt Docker Desktop for Windows (hoặc cấu hình native PostgreSQL 17 và MongoDB 8.0 cho môi trường phát triển cục bộ).

>>> KẾT LUẬN PRE-FLIGHT: ĐẠT ĐIỀU KIỆN TIÊN QUYẾT CHO PHASE 0 <<<
```

### 2.2. Bằng chứng kiểm tra Git status và chống rò rỉ bí mật

```text
On branch master

No commits yet

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	.env.example
	.gitignore
	backend/
	benchlab/
	configs/
	docs/
	frontend/
	pyproject.toml
	queries/
	requirements.txt
	results/
	scripts/
	tests/

Ignored files:
  (use "git add -f <file>..." to include in what will be committed)
	.env
	backend/benchlab/__pycache__/
	benchlab/__pycache__/
	scripts/__pycache__/

nothing added to commit but untracked files present (use "git add" to track)
```

File `.env` chứa mật khẩu cục bộ được `.gitignore` nhận diện và bảo vệ tuyệt đối, không cho phép commit lên Git.

---

## 3. Cấu trúc kho mã nguồn sau Phase 0

```text
D:\DETAICSDL\
├── .env.example              # Mẫu cấu hình môi trường chuẩn
├── .env                      # Cấu hình môi trường cục bộ (được gitignore)
├── .gitignore                # Quy tắc bỏ qua file tạm, build, secrets
├── pyproject.toml            # Khai báo gói benchlab, build system và cấu hình pytest
├── requirements.txt          # Phiên bản thư viện Python đã pin cố định
│
├── backend/                  # Mã nguồn phía máy chủ và runner
│   ├── app/                  # Phân lớp ứng dụng theo mục 3.3 đặc tả
│   │   ├── api/              # Endpoints FastAPI
│   │   ├── domain/           # Models, schemas, query registry
│   │   ├── adapters/         # PostgreSQL, Mongo reference, Mongo embedded
│   │   ├── benchmark/        # Timer monotonic, workers, metrics
│   │   ├── datasets/         # Data generator, bulk loader, validator
│   │   └── reports/          # Thống kê, xuất biểu đồ và báo cáo
│   └── benchlab/             # CLI package chính thức
│
├── benchlab/                 # Root wrapper cho lệnh python -m benchlab
├── frontend/src/             # Mã nguồn giao diện người dùng
├── queries/                  # Truy vấn SQL và MongoDB có phiên bản
│   ├── postgresql/
│   └── mongodb/
├── configs/profiles/         # Cấu hình các profile và index catalog
├── tests/                    # Bộ kiểm thử tự động
│   ├── unit/
│   ├── integration/
│   ├── correctness/
│   └── e2e/
├── scripts/                  # Kịch bản bảo trì và chẩn đoán
│   ├── doctor.py             # Script kiểm tra pre-flight
│   └── setup_skeleton.py     # Script khởi tạo skeleton thư mục
├── results/                  # Thư mục chứa kết quả thực nghiệm bất biến
└── docs/                     # Tài liệu đặc tả và kiểm thử
    ├── SPEC.md               # Đặc tả kỹ thuật gốc v1.0
    ├── implementation-plan.md# Kế hoạch chi tiết và ma trận test
    ├── tasks.md              # Checklist tiến độ từng phase
    ├── decisions.md          # Nhật ký quyết định kiến trúc và tài nguyên
    ├── limitations.md        # Giới hạn phương pháp và môi trường
    ├── test-report.md        # Báo cáo kết quả kiểm thử
    └── walkthrough.md        # Hướng dẫn thao tác và bằng chứng thực tế
```

---

## 4. Hướng dẫn các bước tiếp theo (Chuyển tiếp sang Phase 1)

1. Cài đặt / kích hoạt Docker Desktop for Windows (nếu muốn chạy qua container).
2. Tạo tệp `docker-compose.yml` với các image PostgreSQL `postgres:17.2-alpine` và MongoDB `mongo:8.0.4`, gắn hạn ngạch `cpus: 2.0`, `mem_limit: 2048m`.
3. Triển khai các adapter kết nối `PostgreSQLAdapter` và `MongoDBAdapter` trong `backend/app/adapters/`.
4. Viết kiểm thử tích hợp kết nối `tests/integration/test_connectivity.py` và xác minh Gate G1.
