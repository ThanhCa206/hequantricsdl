# HẠN CHẾ VỀ PHƯƠNG PHÁP VÀ MÔI TRƯỜNG THỰC NGHIỆM (LIMITATIONS)

**Dự án:** Đánh giá hiệu năng truy vấn giữa CSDL quan hệ (PostgreSQL) và CSDL NoSQL (MongoDB)  
**Phiên bản đặc tả:** 1.0  
**Ngày cập nhật:** 30/09/2026  

Tài liệu này xác định rõ các ranh giới và hạn chế phương pháp luận nhằm bảo đảm tính trung thực khoa học, tránh các kết luận tổng quát hóa sai lầm vượt ra ngoài phạm vi đã đo lường.

---

## 1. Hạn chế về phần cứng và hạ tầng máy chủ
1. **Môi trường máy đơn (Single Host):**
   - Máy trạm thực nghiệm: Intel Core i5-6300U CPU @ 2.40GHz (2 nhân vật lý, 4 luồng logic), 16 GiB RAM (~9.2 GiB khả dụng), ổ cứng SSD trên hệ điều hành Windows 10.
   - Vì là máy đơn, toàn bộ hệ điều hành, tiến trình nền của Windows, Docker daemon, runner đo và container CSDL chia sẻ cùng một bus phần cứng, bộ điều khiển I/O và kênh bộ nhớ.
   - Để kiểm soát biến gây nhiễu, hai CSDL được đo hoàn toàn tuần tự, chỉ một CSDL nhận tải tại một thời điểm. Tuy nhiên, hiện tượng biến động nhiệt độ (thermal throttling) và tác vụ ngầm của hệ điều hành vẫn có thể gây dao động ngẫu nhiên nhỏ giữa các lần chạy.

2. **Hạn ngạch tài nguyên (Resource Quotas):**
   - Hạn ngạch container được điều chỉnh xuống 2 vCPU và 2 GiB RAM cho mỗi DB container nhằm tránh làm kiệt quệ tài nguyên của host (DEC-002).
   - Với quy mô dữ liệu `medium` (100.000 đơn hàng), một phần lớn dữ liệu có thể nằm trong bộ đệm RAM của hệ điều hành và engine cache; do đó kết quả phản ánh hiệu năng khi dữ liệu nằm phần lớn trong bộ nhớ đệm (in-memory/cached working set).

3. **Yêu cầu Docker Desktop / Container:**
   - Hệ thống được thiết kế để cô lập hạ tầng bằng Docker Compose. Tại thời điểm kiểm tra pre-flight Phase 0, Docker CLI chưa có trong PATH của host và thành phần WSL2 chưa được kích hoạt.
   - Cần kích hoạt Docker Desktop for Windows hoặc hỗ trợ chế độ kết nối native cục bộ để triển khai Phase 1.

---

## 2. Hạn chế về phương pháp đo và tải
1. **Mô hình tải Closed-loop (Vòng lặp kín):**
   - Thử nghiệm thông lượng (Mode T) áp dụng mô hình closed-loop với $C \in \{1, 8, 32\}$: mỗi client worker chỉ phát truy vấn mới ngay sau khi nhận được kết quả của truy vấn trước đó.
   - Mô hình closed-loop không phản ánh hiện tượng dồn hàng đợi (queueing delay) của các hệ thống thế giới thực có tốc độ gửi yêu cầu độc lập (open-loop arrival rate), và tiềm ẩn hiện tượng "coordinated omission" khi hệ thống chậm làm giảm luôn tốc độ phát truy vấn.

2. **Giao thức Warm-up (Warm Protocol):**
   - Các phép đo chính thức được thực hiện sau giai đoạn warm-up tối thiểu 20 giây và 100 request nhằm đạt trạng thái ổn định (steady-state).
   - Kết quả không đại diện cho kịch bản khởi động lạnh (cold start) sau khi vừa bật máy chủ hoặc khi bộ đệm OS page cache hoàn toàn trống rỗng.

3. **Số lượt lặp lại (Repeats) và khoảng tin cậy (CI):**
   - Số lượt lặp chuẩn là 5 repeat độc lập theo cặp đối xứng.
   - Khoảng tin cậy 95% tính bằng phương pháp bootstrap 10.000 resamples trên 5 cặp repeat mang tính chất **thăm dò (exploratory)**, phản ánh độ phân tán giữa các lượt chạy chứ chưa đủ cỡ mẫu lớn để khẳng định ý nghĩa thống kê tuyệt đối cho các chênh lệch nhỏ dưới 5%.

---

## 3. Hạn chế về mô hình dữ liệu và so sánh
1. **Dữ liệu giả lập (Synthetic Data):**
   - Dữ liệu được sinh bằng thuật toán ngẫu nhiên có hạt giống cố định (`seed=42`).
   - Phân phối đồng đều (`uniform`) và phân phối lệch (`skewed`) là các mô hình toán học lý tưởng, không chứa các đặc thù phi cấu trúc, dữ liệu rác, hoặc lỗi định dạng thường gặp trong hệ thống sản xuất thực tế.

2. **Tính độc lập giữa Track A và Track B:**
   - Track A so sánh hai CSDL theo mô hình tham chiếu tương đương (Reference model với 4 collections / 4 tables).
   - Track B so sánh giải pháp nhúng (Embedded model) của MongoDB với mô hình chuẩn hóa của PostgreSQL cho riêng thao tác đọc chi tiết đơn hàng (Q8).
   - Không được quy kết kết quả của Track B thành kết luận chung về "tốc độ của engine", bởi vì Track B phản ánh sự đánh đổi về mô hình cấu trúc dữ liệu và chi phí bảo trì lưu trữ.

---

## 4. Tuyên bố phạm vi nghiên cứu
- Không đưa ra kết luận "PostgreSQL luôn nhanh hơn MongoDB" hoặc ngược lại.
- Mọi kết luận chỉ có giá trị hiệu lực trong phạm vi phiên bản đã khóa (PostgreSQL 17.2, MongoDB 8.0.4), cấu hình phần cứng đã kiểm tra, bộ truy vấn Q1–Q8 và các profile dữ liệu đã thực hiện.
