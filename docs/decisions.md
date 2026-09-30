# NHẬT KÝ QUYẾT ĐỊNH THIẾT KẾ VÀ KIẾN TRÚC (DECISIONS LOG)

**Dự án:** Đánh giá hiệu năng truy vấn giữa CSDL quan hệ (PostgreSQL) và CSDL NoSQL (MongoDB)  
**Phiên bản đặc tả:** 1.0  
**Ngày cập nhật:** 30/09/2026  

---

## DEC-001: Chốt phiên bản CSDL và môi trường thực thi
- **Ngày:** 30/09/2026 (Phase 0)
- **Bối cảnh:** Đặc tả yêu cầu chốt phiên bản patch cụ thể và image digest tại Phase 0, không dùng thẻ `latest` trong bản nộp nhằm bảo đảm tính tái lập hoàn toàn (reproducibility).
- **Quyết định:**
  - **PostgreSQL:** Chọn phiên bản `17.2-alpine` (Image: `postgres:17.2-alpine`).
  - **MongoDB:** Chọn phiên bản `8.0.4` (Image: `mongo:8.0.4`).
  - **Python:** Khóa runtime tại `3.12.6` với driver `psycopg 3.2.4` (kèm pool và binary C-extension) và `pymongo 4.10.1`.
  - **Node.js:** Runtime `v22.16.0` với `npm 10.9.2`.
- **Hệ quả:** Mọi cấu hình docker-compose và image manifest sẽ cố định phiên bản này; không cập nhật phiên bản âm thầm trong suốt quá trình đo.

---

## DEC-002: Đánh giá phần cứng máy chủ và điều chỉnh hạn ngạch tài nguyên (Quota)
- **Ngày:** 30/09/2026 (Phase 0)
- **Bối cảnh:**
  - Cấu hình đề xuất ban đầu trong đặc tả (mục 6.2): 4 vCPU và 4 GiB RAM cho mỗi DB container.
  - Kết quả kiểm tra phần cứng thực tế tại máy thí nghiệm:
    - CPU: `Intel(R) Core(TM) i5-6300U CPU @ 2.40GHz` (2 physical cores, 4 logical processors).
    - RAM: `15.86 GiB` tổng visible (~9.2 GiB khả dụng).
    - Ổ đĩa: D: trống 62.64 GB, C: trống 44.79 GB.
  - Nếu cấp phát 4 vCPU cho container DB, toàn bộ luồng CPU của CPU 2 nhân/4 luồng sẽ bị chiếm dụng, gây nghẽn nghiêm trọng (starvation) cho OS, tiến trình API runner, client worker và hệ thống giám sát.
- **Quyết định:**
  - Điều chỉnh hạn ngạch mỗi DB container xuống: **2 vCPU** (`cpus: 2.0`) và **2 GiB RAM** (`mem_limit: 2048m`).
  - Cấu hình này vẫn bảo đảm tỷ lệ đối xứng công bằng 1:1 tuyệt đối giữa PostgreSQL và MongoDB, đồng thời giải phóng 2 logical processors và hơn 6 GiB RAM cho OS host và runner tiến hành đo đạc chính xác, tránh hiện tượng throttling ngoại vi.
- **Hệ quả:** Cập nhật `.env.example`, `.env`, docker-compose.yml và tài liệu limitations.

---

## DEC-003: Nguyên tắc đo lường luân phiên và cô lập tuyệt đối (Fairness)
- **Ngày:** 30/09/2026 (Phase 0)
- **Bối cảnh:** Máy thí nghiệm là máy đơn (single host). Nếu chạy workload trên cả hai CSDL đồng thời, tranh chấp CPU, I/O ổ đĩa và RAM cache sẽ làm sai lệch dữ liệu đo.
- **Quyết định:**
  - Hai CSDL được đo hoàn toàn tuần tự, chỉ một CSDL nhận workload tại một thời điểm.
  - CSDL còn lại phải ở trạng thái nhàn rỗi (idle) hoặc tạm dừng (stopped) và không có bất kỳ tác vụ nền nào (import, build index, vacuum).
  - Áp dụng thứ tự luân phiên có đối xứng: repeat lẻ chạy `PostgreSQL -> MongoDB`, repeat chẵn chạy `MongoDB -> PostgreSQL`.
  - Giữ cùng snapshot dữ liệu, cùng trace tham số và cùng hạt giống ngẫu nhiên (seed) trong từng cặp so sánh.

---

## DEC-004: Ranh giới đo lường thời gian (Timing Boundaries)
- **Ngày:** 30/09/2026 (Phase 0)
- **Bối cảnh:** Cần đo chính xác độ trễ truy vấn CSDL thuần túy từ góc nhìn ứng dụng mà không bị nhiễu bởi các thao tác ngoài.
- **Quyết định:**
  - Đồng hồ đo: Sử dụng `time.perf_counter_ns()` (độ phân giải nano-giây, monotonic clock).
  - Vùng được tính thời gian (`timed region`): Bắt đầu ngay trước khi gửi truy vấn trên connection đã mượn sẵn từ pool, kéo dài qua quá trình thực thi trên máy chủ CSDL, và kết thúc ngay sau khi driver client đã decode và nạp toàn bộ kết quả vào bộ nhớ (consume all cursor rows/docs).
  - Các thao tác nằm **ngoài** timed region: Mở/mượn kết nối, sinh tham số, kiểm tra checksum/hash, chuẩn hóa dữ liệu so sánh, flush log ra đĩa, serialize HTTP JSON và vẽ biểu đồ.
  - Không lấy thời gian click trình duyệt hay HTTP round-trip làm thời gian truy vấn CSDL.

---

## DEC-005: Khả thi hóa các profile dữ liệu trên phần cứng thực tế
- **Ngày:** 30/09/2026 (Phase 0)
- **Bối cảnh:** Đánh giá 4 profile dữ liệu quy định trong đặc tả: `fixture`, `small`, `medium`, `large`.
- **Quyết định:**
  - **`fixture`** (50 đơn hàng): Hoàn toàn khả thi, dùng cho kiểm thử tính đúng (correctness oracle).
  - **`small`** (10.000 đơn hàng, ~30.000 items): Hoàn toàn khả thi, dùng cho smoke test, CI và demo live 10–12 phút.
  - **`medium`** (100.000 đơn hàng, ~300.000 items): Hoàn toàn khả thi, là tâm điểm so sánh chính cho môi trường máy trạm cá nhân.
  - **`large`** (1.000.000 đơn hàng, ~3.000.000 items): Khả thi về mặt dung lượng lưu trữ (chiếm ~2-4 GB đĩa trên 62 GB trống), nhưng trên CPU di động 2 nhân i5-6300U, thời gian sinh dữ liệu, nạp batch, tạo index và chạy 5 repeat cho 8 truy vấn sẽ mất nhiều giờ. Do đó, profile `large` được gắn nhãn **conditional / pilot test**: sẽ chạy thử nghiệm thí điểm trước, nếu vượt quá ngân sách thời gian sẽ công bố rõ phần chưa thực hiện thay vì bịa số liệu.

---

## DEC-006: Chuẩn hóa kiểu dữ liệu và quy ước biểu diễn
- **Ngày:** 30/09/2026 (Phase 0)
- **Quyết định:**
  - **Định danh (ID):** Số nguyên 64-bit (`BIGINT` trong PostgreSQL, BSON `Int64` trong MongoDB). Khi truyền qua JSON API đến trình duyệt, luôn serialize thành kiểu String để tránh mất độ chính xác do giới hạn 53-bit float của JavaScript (`Number.MAX_SAFE_INTEGER`).
  - **Tiền tệ:** Lưu dưới dạng số nguyên `_minor` (đối với VND: 1 đơn vị = 1 đồng; không dùng số thực `FLOAT/DOUBLE` để tránh sai số dấu phẩy động).
  - **Thời gian:** Chuẩn UTC, định dạng ISO-8601 millisecond (`YYYY-MM-DDTHH:mm:ss.sssZ`), dải thời gian cố định `[2023-01-01T00:00:00Z, 2026-01-01T00:00:00Z)`.
  - **Tính toàn vẹn:** Tất cả trường cốt lõi `NOT NULL`. Kiểm tra toàn vẹn quan hệ ở MongoDB bằng integrity checker độc lập.

---

## DEC-007: Tách biệt rạch ròi giữa Track A và Track B
- **Ngày:** 30/09/2026 (Phase 0)
- **Bối cảnh:** Tránh các kết luận ngụy biện "NoSQL nhanh hơn SQL" hoặc ngược lại khi so sánh hai mô hình dữ liệu khác nhau.
- **Quyết định:**
  - **Track A:** PostgreSQL chuẩn hóa vs MongoDB tham chiếu (Reference model, 4 collections). So sánh cùng bài toán tham chiếu và liên kết dữ liệu (`$lookup` vs `JOIN`).
  - **Track B:** PostgreSQL chuẩn hóa vs MongoDB nhúng (`orders_embedded` chứa `items[]`). So sánh giải pháp thiết kế mô hình dữ liệu hướng ứng dụng cho truy vấn đọc chi tiết đơn hàng (Q8).
  - Không bao giờ gộp điểm hay tính trung bình Track A và Track B vào một chỉ số chung.

---

## DEC-008: Chiến lược đánh chỉ mục I0 và I1
- **Ngày:** 30/09/2026 (Phase 0)
- **Quyết định:**
  - **I0:** Chỉ giữ các index bắt buộc để bảo toàn khóa chính và ràng buộc định danh duy nhất (PK, `_id`, unique compound `(order_id, line_no)`).
  - **I1:** Bổ sung tập index phục vụ workload đã xác định trước theo bảng mục 6.1 của đặc tả.
  - Phân tích `EXPLAIN` độc lập ngoài timed region để giải thích hành vi quét index hay quét toàn bảng/collection.
