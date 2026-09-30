# BÁO CÁO KIỂM THỬ HỆ THỐNG (TEST REPORT)

**Dự án:** Đánh giá hiệu năng truy vấn giữa CSDL quan hệ (PostgreSQL) và CSDL NoSQL (MongoDB)  
**Phiên bản đặc tả:** 1.0  
**Ngày cập nhật:** 30/09/2026  
**Trạng thái kiểm định:** Phase 0 (Gate G0)  

---

## 1. Tổng quan kết quả kiểm thử Phase 0

| Tổng số ca kiểm thử | Đạt (PASS) | Không đạt (FAIL) | Bỏ qua (SKIPPED) | Cảnh báo (WARNING) |
|:---:|:---:|:---:|:---:|:---:|
| 6 | 6 | 0 | 0 | 1 (Hạ tầng Docker) |

**Kết luận Gate G0:** **PASS** (Đủ điều kiện chuyển sang Phase 1).

---

## 2. Nhật ký chi tiết các ca kiểm thử Phase 0

### TC-P0-01: Thu thập và xác minh thông số phần cứng & Hệ điều hành
- **Mục tiêu:** Thu thập thông tin máy chủ thật để lập hạn ngạch tài nguyên, không bịa đặt số liệu.
- **Thao tác:** Chạy lệnh PowerShell truy vấn WMI `Win32_Processor`, `Win32_OperatingSystem`, `PSDrive`.
- **Kết quả thực tế:**
  - OS: `Microsoft Windows 10 Pro Education`, build `10.0.19045`, 64-bit.
  - CPU: `Intel(R) Core(TM) i5-6300U CPU @ 2.40GHz` (2 physical cores, 4 logical processors).
  - RAM: `15.86 GiB` tổng visible (~9.2 GiB RAM vật lý khả dụng).
  - Ổ đĩa: Ổ D: trống 62.64 GB; Ổ C: trống 44.79 GB.
- **Đánh giá:** **PASS**. Dữ liệu được ghi nhận vào `docs/decisions.md` (DEC-002).

---

### TC-P0-02: Kiểm tra bộ công cụ và môi trường thực thi (Toolchain)
- **Mục tiêu:** Xác nhận các phiên bản ngôn ngữ và trình quản lý gói có sẵn trên máy.
- **Thao tác:** Thực thi kiểm tra phiên bản qua command line.
- **Kết quả thực tế:**
  - Python: `3.12.6` (pip `26.2.1`). Đạt yêu cầu >= 3.11.
  - Node.js: `v22.16.0` (npm `10.9.2`). Đạt yêu cầu >= 18.
  - Git: `2.51.1.windows.1`. Đạt yêu cầu.
  - Docker / Compose: Chưa phát hiện trong biến môi trường PATH của host (xem mục Cảnh báo).
- **Đánh giá:** **PASS** cho môi trường code; **WARNING** cho Docker.

---

### TC-P0-03: Kiểm tra tính khả dụng của các Port dịch vụ
- **Mục tiêu:** Xác nhận các cổng mạng tiêu chuẩn không bị chiếm dụng bởi dịch vụ khác trước khi triển khai.
- **Thao tác:** Kiểm tra kết nối TCP socket trên `127.0.0.1`: 5432, 27017, 8000, 5173.
- **Kết quả thực tế:**
  - Port 5432 (PostgreSQL): TRỐNG (connect_ex != 0).
  - Port 27017 (MongoDB): TRỐNG.
  - Port 8000 (FastAPI API): TRỐNG.
  - Port 5173 (Vite Frontend): TRỐNG.
- **Đánh giá:** **PASS**. Sẵn sàng cho việc phân bổ cổng trong Phase 1.

---

### TC-P0-04: Kiểm tra an toàn bảo mật và chống rò rỉ bí mật qua Git
- **Mục tiêu:** Bảo đảm không có file `.env`, mật khẩu hoặc token lọt vào version control.
- **Thao tác:** Tạo `.gitignore`, tạo `.env.example`, copy sinh `.env`, chạy `git status --ignored`.
- **Kết quả thực tế:**
  - `.env` nằm trong danh sách `Ignored files`.
  - Không có thông tin nhạy cảm nào xuất hiện trong các file commit.
  - `.env.example` chỉ chứa placeholder mẫu `benchlab_dev_password_change_me`.
- **Đánh giá:** **PASS**. Đạt chuẩn an toàn theo quy định 2.2 của đặc tả.

---

### TC-P0-05: Kiểm tra lệnh Doctor chẩn đoán môi trường
- **Mục tiêu:** Xác minh lệnh chẩn đoán `scripts/doctor.py` và `python -m benchlab doctor` chạy độc lập, in thông báo rõ ràng có cách xử lý.
- **Thao tác:**
  ```bash
  python scripts/doctor.py
  python -m benchlab doctor
  ```
- **Kết quả thực tế:**
  - Lệnh trả về exit code `0`.
  - In đầy đủ 10 tiêu chí kiểm tra: OS, CPU, RAM, Ổ đĩa, Python, Node, Git, Docker, Ports, Config files.
  - Tự động tạo `.env` từ `.env.example` nếu chưa tồn tại.
- **Đánh giá:** **PASS**.

---

### TC-P0-06: Kiểm tra cấu trúc khung dự án (Skeleton Repository)
- **Mục tiêu:** Khởi tạo đầy đủ các thư mục theo kiến trúc phân lớp tại mục 3.3 đặc tả.
- **Thao tác:** Chạy `python scripts/setup_skeleton.py` và duyệt cấu trúc cây thư mục.
- **Kết quả thực tế:**
  - Các thư mục đã sẵn sàng: `backend/app/api`, `backend/app/domain`, `backend/app/adapters`, `backend/app/benchmark`, `backend/app/datasets`, `backend/app/reports`, `frontend/src`, `queries/postgresql`, `queries/mongodb`, `configs/profiles`, `tests/unit`, `tests/integration`, `tests/correctness`, `tests/e2e`, `results`.
- **Đánh giá:** **PASS**.

---

## 3. Danh sách các vấn đề và hành động xử lý (Defects / Warnings)

| ID | Mức độ | Mô tả vấn đề | Ảnh hưởng | Hướng xử lý |
|---|---|---|---|---|
| **WARN-P0-01** | Medium | Docker / Docker Compose chưa có trong PATH của host | Không thể tự động chạy `docker compose up -d` ở Phase 1 nếu chưa cài đặt Docker Desktop | Cài đặt Docker Desktop for Windows hoặc cấu hình dịch vụ native cho PostgreSQL 17 và MongoDB 8.0 |
| **NOTE-P0-02** | Low | CPU host có 2 nhân vật lý / 4 luồng xử lý | Nếu cấp 4 vCPU cho container sẽ làm nghẽn host | Đã hạ hạn ngạch container xuống 2 vCPU và 2048 MB RAM (DEC-002) |
