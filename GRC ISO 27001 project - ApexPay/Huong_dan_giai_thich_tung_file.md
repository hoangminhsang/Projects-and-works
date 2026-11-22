# Hướng dẫn: mỗi file làm gì, kèm ví dụ

Tài liệu này giải thích từng file trong thư mục GRC project. Mỗi file có 4 phần:

- **Để làm gì:** file này trả lời câu hỏi nào.
- **Tôi đã làm gì:** bên trong file có gì.
- **Ví dụ:** một dòng hoặc một mục cụ thể lấy từ chính file đó.
- **Liên kết:** file này lấy dữ liệu từ file nào, và đưa dữ liệu sang file nào.

Tất cả đều là **mô phỏng**. ApexPay là công ty giả. Không có ai thật được phỏng vấn, và không có số liệu thật nào.

---

## 0. Hiểu cả dự án trong 1 phút

Hãy tưởng tượng ApexPay là một **ngôi nhà** và ISO 27001 là **bộ tiêu chuẩn an toàn** mà ngôi nhà phải đạt để được cấp giấy chứng nhận.

| Phase | Giống như việc | Câu hỏi chính |
|---|---|---|
| 1 | Khảo sát ngôi nhà | Nhà ở đâu, ai sống trong đó, đang thiếu gì? |
| 2 | Chủ nhà ra quy định | Ai chịu trách nhiệm việc gì? Mục tiêu là gì? |
| 3 | Tìm chỗ dễ bị trộm vào | Rủi ro nào lớn nhất? Xử lý thế nào? |
| 4 | Viết nội quy, dạy người trong nhà | Mọi người phải làm gì, làm theo cách nào? |
| 5 | Lắp khóa, camera | Tiêu tiền vào đâu? Làm theo thứ tự nào? Kiểm tra ra sao? |
| 6 | Tập tình huống sự cố | Nếu có trộm, cháy, hay hàng xóm gây chuyện thì xử lý ra sao? |
| 7 | Kiểm tra định kỳ | Các biện pháp có thật sự hoạt động không? |
| 8 | Sửa lỗi, chuẩn bị thi | Lỗi gốc là gì? Đã sẵn sàng để được chứng nhận chưa? |

### Từ điển nhanh

| Thuật ngữ | Nghĩa đơn giản |
|---|---|
| ISMS | Hệ thống quản lý an toàn thông tin: toàn bộ quy định, người và quy trình bảo vệ dữ liệu |
| Annex A | Danh sách 93 "biện pháp kiểm soát" mẫu trong ISO 27001 (ví dụ A.8.5 = xác thực an toàn) |
| Rủi ro (risk) | Chuyện xấu có thể xảy ra. Điểm = khả năng (1-5) × mức độ thiệt hại (1-5) |
| Critical / High / Medium / Low | Mức rủi ro: 17-25 / 10-16 / 5-9 / 1-4 |
| Control (kiểm soát) | Biện pháp làm giảm rủi ro, ví dụ MFA, sao lưu, đào tạo |
| MFA | Đăng nhập 2 lớp (mật khẩu cộng mã trên điện thoại) |
| EDR | Phần mềm chống mã độc có giám sát, cài trên laptop |
| MDR | Dịch vụ thuê ngoài, có người theo dõi cảnh báo bảo mật |
| SoA | Bảng nói rõ áp dụng biện pháp nào trong 93 biện pháp và vì sao |
| Nonconformity (NC) | "Không phù hợp": chưa đáp ứng một yêu cầu. Major là lỗi lớn, minor là lỗi nhỏ |
| RTO / RPO / MTD | Thời gian khôi phục mục tiêu / lượng dữ liệu tối đa được mất / thời gian gián đoạn tối đa chịu được |
| Stage 1 / Stage 2 | Hai vòng đánh giá chứng nhận: Stage 1 kiểm tra giấy tờ, Stage 2 kiểm tra thực tế |

### Các mã ID dùng xuyên suốt

Các file nối với nhau bằng mã. Nếu thấy một mã ở file này, bạn có thể tìm nó ở file khác.

- **F-01..F-24:** điểm yếu trong đề bài (ví dụ F-01: 24 trên 120 tài khoản chưa có MFA)
- **IN-/EX-:** vấn đề nội bộ / bên ngoài (Phase 1)
- **A-01..:** tài sản (Phase 3)
- **T-01..:** mối đe dọa (Phase 3)
- **R-01..R-28:** rủi ro (Phase 3, thêm sau)
- **RM-01..22:** việc cần làm trong lộ trình (Phase 5)
- **E-01..E-12:** bằng chứng kiểm toán do đề bài cho
- **AUD-01..12:** phát hiện kiểm toán (Phase 7)
- **CAR-01..09:** hành động khắc phục (Phase 8)

**Ví dụ một chuỗi liên kết hoàn chỉnh:**
F-01 (thiếu MFA) → R-01 (rủi ro bị chiếm tài khoản) → A.8.5 trong SoA → RM-04 (bật MFA) → OBJ-01 (mục tiêu 100%) → E-02 (114/120 đã bật) → AUD-01 (6 người còn thiếu) → CAR-02 (thêm MFA vào quy trình nhận nhân viên mới).

---

## Phase 1: Bối cảnh và đánh giá khoảng cách

### Organisational_Context.pdf
- **Để làm gì:** ISO điều 4.1 yêu cầu hiểu công ty đang ở hoàn cảnh nào, bên trong và bên ngoài.
- **Tôi đã làm gì:** liệt kê 12 vấn đề nội bộ (IN-01..12) và 12 vấn đề bên ngoài (EX-01..12), rồi đánh giá biến đổi khí hậu có liên quan không.
- **Ví dụ:** IN-01 "Văn hóa": nhân viên coi nhắc nhở bảo mật là thứ có thể bỏ qua, chỉ 72/120 người học đào tạo (F-10). Về khí hậu, tôi kết luận là có liên quan nhưng ở mức vừa phải, vì nó ảnh hưởng qua nhà cung cấp như AWS.
- **Liên kết:** đưa dữ liệu sang Scope, Interested Parties và Risk Register.

### Interested_Parties_Register.xlsx
- **Để làm gì:** điều 4.2: ai quan tâm đến bảo mật của ApexPay, và họ cần gì.
- **Tôi đã làm gì:** 22 bên liên quan (IP-01..22) và 46 yêu cầu (REQ-01..46). Mỗi yêu cầu được đánh dấu ISMS có đáp ứng không (Yes / Partly / No).
- **Ví dụ:** REQ-01, IP-01 (CEO và hội đồng): "Sẵn sàng chứng nhận ISO 27001 trong 6 tháng để ký được hợp đồng với khách hàng lớn". Cột "Addressed by ISMS?" ghi Yes.
- **Liên kết:** Scope, Objectives, Regulatory Register.

### ISMS_Scope_Statement.pdf
- **Để làm gì:** điều 4.3: hàng rào của ISMS, cái gì nằm trong và cái gì nằm ngoài.
- **Tôi đã làm gì:** phạm vi rộng: nền tảng, AWS, hệ thống IT văn phòng, cả 120 nhân viên, văn phòng London và làm việc từ xa. Hạ tầng bên trong nhà cung cấp nằm ngoài phạm vi. Có kèm sơ đồ ranh giới.
- **Ví dụ:** trung tâm dữ liệu của AWS nằm ngoài phạm vi, nhưng cách ApexPay cấu hình AWS (IAM, S3) thì nằm trong.
- **Liên kết:** dùng cho mọi file sau, nhất là SoA và kế hoạch kiểm toán.

### ISO27001_Gap_Assessment.xlsx và Gap_Assessment_Report.pdf
- **Để làm gì:** đo xem ApexPay đang ở đâu so với ISO, giống như làm bài kiểm tra đầu vào.
- **Tôi đã làm gì:** chấm điểm trưởng thành 0-5 cho 25 mục của điều 4-10 và 61 biện pháp Annex A. Điểm trung bình là 0.8, trong khi mục tiêu là 3. Mục nào không có bằng chứng thì ghi "Not assessed" (17 mục). Báo cáo PDF tóm tắt 5 việc cần ưu tiên.
- **Ví dụ:** A.5.1 (chính sách): hiện tại 0, mục tiêu 3, khoảng cách 3, vì chưa có chính sách nào được duyệt (F-18). Việc ưu tiên số 1 là đóng S3 bucket đang công khai.
- **Liên kết:** khoảng cách ở đây trở thành rủi ro (Phase 3) và hành động (Phase 5).

---

## Phase 2: Lãnh đạo

### Information_Security_Policy.pdf
- **Để làm gì:** điều 5.2: chính sách tổng do CEO ký, như "hiến pháp" về bảo mật.
- **Tôi đã làm gì:** viết mục đích, nguyên tắc, trách nhiệm và cam kết. Bản này để ở trạng thái "chờ duyệt".
- **Ví dụ:** chính sách này chưa được ký. Chính điều đó trở thành bằng chứng E-01 và phát hiện AUD-02 ở Phase 7. CEO ký trong buổi họp xem xét của lãnh đạo (quyết định D3).
- **Liên kết:** là nền tảng cho 12 chính sách chủ đề ở Phase 4.

### Security_RACI_Matrix.xlsx
- **Để làm gì:** ai làm (R), ai chịu trách nhiệm cuối (A), ai được hỏi ý kiến (C), ai được thông báo (I).
- **Tôi đã làm gì:** 42 hoạt động × 10 vai trò. Có công thức kiểm tra mỗi hoạt động chỉ có đúng 1 chữ A.
- **Ví dụ:** "Approve information security policy": CEO = A; CTO, COO, CFO = C; IT Manager = I.
- **Liên kết:** nguyên nhân gốc của AUD-01 là bước nhận nhân viên mới (onboarding) có 2 chữ R nhưng không có chữ A nào.

### Security_Governance_Framework.pdf
- **Để làm gì:** bảo mật được quản lý qua những cuộc họp nào, báo cáo lên ai.
- **Tôi đã làm gì:** lập ủy ban điều hành (steering committee) họp hằng tháng, xác định đường báo cáo, cách leo thang và quyền chấp nhận rủi ro.
- **Ví dụ:** khi cắt ngân sách ở Case 7, ủy ban này là bên chấp nhận rủi ro R-08 ở mức High.

### ISMS_Objectives_and_Change_Plan.xlsx
- **Để làm gì:** điều 6.2 và 6.3: mục tiêu đo được và kế hoạch thay đổi có kiểm soát.
- **Tôi đã làm gì:** 10 mục tiêu (OBJ-01..10), mỗi mục tiêu có cách tính, giá trị ban đầu, mục tiêu, hạn và người phụ trách, cùng 11 thay đổi (CHG-01..11).
- **Ví dụ:** OBJ-01 "Mọi tài khoản dùng MFA": ban đầu 80% (96/120), mục tiêu tháng 3 là 95%, cuối cùng 100%, hạn 28/02/2027, người phụ trách IT Manager.
- **Liên kết:** Dashboard ở Phase 7 đo đúng những mục tiêu này.

---

## Phase 3: Rủi ro

### Risk_Assessment_Methodology.pdf
- **Để làm gì:** "luật chơi" để chấm điểm rủi ro, sao cho ai chấm cũng ra kết quả giống nhau.
- **Tôi đã làm gì:** ma trận 5×5, định nghĩa từng mức, và ai được chấp nhận rủi ro ở mức nào.
- **Ví dụ:** rủi ro Critical chỉ CEO được chấp nhận, và tối đa 30 ngày. Rủi ro High thì ủy ban điều hành chấp nhận, tối đa 3 tháng. Quy tắc này quyết định ai ký ở Case 5 và Case 7.

### Information_Asset_Register.xlsx
- **Để làm gì:** danh sách những gì cần bảo vệ.
- **Tôi đã làm gì:** 32 mục (A-01..A-27 và dịch vụ S-01..S-05). Mỗi mục có chủ sở hữu, vị trí, phân loại, điểm C/I/A (bảo mật, toàn vẹn, sẵn sàng) và công thức tính mức quan trọng. Có thêm sheet về cách phân loại dữ liệu.
- **Ví dụ:** A-02 Customer database (AWS RDS): khoảng 150.000 hồ sơ khách hàng, chủ sở hữu là CTO, phân loại Restricted, C=3, I=3, A=3.

### Data_Flow_Diagram.drawio
- **Để làm gì:** vẽ dữ liệu chảy đi đâu và đi qua những "ranh giới tin cậy" nào.
- **Tôi đã làm gì:** sơ đồ cấp 1: khách hàng → CloudFront/WAF → ứng dụng → RDS/S3, cùng bên xử lý thanh toán, GitHub và M365. File mở bằng draw.io.
- **Ví dụ:** ranh giới TB3 nằm giữa ApexPay và bên xử lý thanh toán. Đây là chỗ có thể bị giả mạo thông báo thanh toán (T-02).

### STRIDE_Threat_Model.xlsx
- **Để làm gì:** tìm mối đe dọa theo 6 loại: giả mạo danh tính, sửa đổi trái phép, chối bỏ hành vi, lộ thông tin, làm gián đoạn dịch vụ, chiếm quyền cao hơn.
- **Tôi đã làm gì:** 19 mối đe dọa (T-01..T-19). Ở Phase 8 tôi thêm T-20..T-23 vào sheet "Additions 2027".
- **Ví dụ:** T-02 (Spoofing): kẻ tấn công gửi webhook giả để báo "đã thanh toán", làm hóa đơn bị đánh dấu đã trả dù chưa nhận được tiền. Liên kết với R-22.

### Information_Security_Risk_Register.xlsx
- **Để làm gì:** sổ rủi ro, là trái tim của ISMS.
- **Tôi đã làm gì:** 25 rủi ro, mỗi rủi ro có điểm khi chưa có biện pháp (inherent), điểm hiện tại (current) và điểm mục tiêu (target), tính bằng công thức. Có sheet tóm tắt và bản đồ nhiệt. Ở Phase 8 tôi thêm sheet "Update Jun 2027" chấm lại cả 28 rủi ro.
- **Ví dụ:** R-01 "Thiếu MFA": điểm ban đầu 5×5 = 25 (Critical), hiện tại 20, mục tiêu 5 (Medium). Lúc đầu có 7 rủi ro Critical. Đến tháng 6/2027 chỉ còn 1 (R-08).
- **Liên kết:** gần như mọi file sau đều trỏ về R-xx.

### Risk_Treatment_Plan.xlsx
- **Để làm gì:** với mỗi rủi ro, chọn cách xử lý (giảm, tránh, chuyển giao hay chấp nhận), kèm chi phí.
- **Tôi đã làm gì:** chọn khoản đầu tư £98.000 trong ngân sách £100.000. Phần phê duyệt là mô phỏng. Ở Phase 8 tôi thêm sheet ghi các thay đổi.
- **Ví dụ:** dòng "MFA and conditional access": £6.000, được chọn, xử lý R-01 và R-17.

### Statement_of_Applicability.xlsx
- **Để làm gì:** với từng biện pháp trong 93 biện pháp Annex A: có áp dụng không, vì sao, và đã làm đến đâu. Kiểm toán viên luôn xem file này đầu tiên.
- **Tôi đã làm gì:** 93 biện pháp cộng 3 biện pháp bổ sung (X-01..03). Chỉ loại A.8.30 (phát triển thuê ngoài, vì ApexPay không thuê ngoài). Ở Phase 8 tôi thêm sheet "Change log".
- **Ví dụ:** A.5.29 (bảo mật khi gián đoạn): áp dụng, lý do F-14, trạng thái "Not implemented", người phụ trách COO. Ở Phase 7, kiểm toán phát hiện SoA ghi A.8.16 (giám sát) là "đã làm đầy đủ" nhưng không có bằng chứng. Đó là lỗi lớn (major) AUD-06.

---

## Phase 4: Hỗ trợ (chính sách, quy trình, đào tạo)

### Thư mục Policies/ (12 chính sách)
- **Để làm gì:** chính sách nói **phải làm gì**.
- **Tôi đã làm gì:** 12 chính sách, mỗi bản 2 trang (ISMS-POL-002..013): kiểm soát truy cập, sử dụng chấp nhận được, tài sản, phân loại dữ liệu, lưu giữ dữ liệu, quản lý lỗ hổng, sự cố, nhà cung cấp, sao lưu, phát triển an toàn, làm việc từ xa/BYOD, ghi log và giám sát.
- **Ví dụ:** Vulnerability Management Policy (POL-007) đặt hạn sửa lỗi: critical trong 14 ngày, high trong 30 ngày. Khi 5 lỗi quá hạn thì thành phát hiện AUD-04.

### Thư mục Procedures/ (7 quy trình)
- **Để làm gì:** quy trình nói **làm như thế nào**, từng bước.
- **Tôi đã làm gì:** 7 quy trình (PRO-001..007): nhận/chuyển/nghỉ việc, cấp quyền đặc biệt, báo sự cố, sửa lỗ hổng và ngoại lệ, khôi phục sao lưu, thay đổi production, nhận nhà cung cấp mới.
- **Ví dụ:** PRO-001 (Joiner-Mover-Leaver): khi có người nghỉ, HR báo IT để khóa tài khoản. Nhờ đó E-04 cho thấy cả 3 tài khoản người cũ đã bị khóa (AUD-11, phù hợp).

### Security_Awareness_Plan.pdf và Training_Register.xlsx
- **Để làm gì:** đào tạo bảo mật: ai học gì, khi nào, và ai đã học xong.
- **Tôi đã làm gì:** kế hoạch đào tạo theo nhóm vai trò. Sổ đào tạo có 120 nhân viên với mã giả (EMP-001..120), mức ban đầu là 72/120 đã đạt. Trạng thái được tính bằng công thức.
- **Ví dụ:** EMP-001, Engineering, Developer, khóa "CORE-01 Security essentials". Đạt nếu điểm từ 80% trở lên, và hiện "Overdue" nếu quá hạn mà chưa học.

### ISMS_Document_Register.xlsx
- **Để làm gì:** danh sách mọi tài liệu ISMS cùng phiên bản và trạng thái phê duyệt (điều 7.5).
- **Ví dụ:** ISMS-CTX-001 Organisational Context, v0.9, người duyệt CEO, trạng thái "Draft – awaiting approval".

### ISMS_Communication_Plan.xlsx
- **Để làm gì:** thông báo gì, cho ai, khi nào, bằng kênh nào (điều 7.4).
- **Ví dụ:** "All staff": ra mắt ISMS vào tháng 1/2027, CEO trình bày, qua buổi họp toàn công ty, email và intranet. Bằng chứng là bản ghi hình.

---

## Phase 5: Triển khai và kiểm tra

### Security_Budget.xlsx
- **Để làm gì:** chọn đầu tư gì khi chỉ có £100.000.
- **Tôi đã làm gì:** chấm điểm có trọng số: giảm rủi ro 40%, pháp lý/hợp đồng 20%, hiệu quả chi phí 15%, tạo nền tảng 15%, dễ làm 10%. Có xếp hạng và bản ghi quyết định.
- **Ví dụ:** PAM (£18.000) bị hoãn. Thay vào đó dùng tính năng cấp quyền admin khi cần (just-in-time) có sẵn, miễn phí. CSPM £9.000 được thay bằng công cụ có sẵn của AWS giá £3.000.

### Security_Remediation_Roadmap.xlsx
- **Để làm gì:** lộ trình 6 tháng, việc nào làm trước.
- **Ví dụ:** RM-01 "Đóng S3 bucket công khai" làm ở tháng 1 (12/2026), £3.000. RM-21 "Kiểm toán nội bộ" làm ở tháng 5. Tổng cộng £98.000.

### Security_Control_Testing_Register.xlsx
- **Để làm gì:** cách kiểm tra xem biện pháp có hoạt động thật không.
- **Tôi đã làm gì:** 12 bài kiểm tra (CT-001..012), hiện tất cả đang "Not tested". Phần kết quả để bạn điền khi làm lab.
- **Ví dụ:** CT-001 (R-01, A.8.5): thử đăng nhập không có lớp xác thực thứ 2. Kết quả mong đợi là bị chặn hoặc bị hỏi mã MFA. Bài này nối với LAB-01.

### Lab_Writeups/ và Technical_Evidence/
- **Để làm gì:** hướng dẫn làm lab thật (MFA, S3, Wazuh, quét lỗ hổng, sao lưu, quét secret, nghỉ việc).
- **Tôi đã làm gì:** 7 file hướng dẫn, mỗi file có phần "Your results" để trống. Thư mục Technical_Evidence chỉ có README, **cố ý để trống**, vì bằng chứng phải là thật, do bạn tự làm.
- **Ví dụ:** LAB-07: đưa một secret **giả** vào GitHub để xem GitHub có tự phát hiện không, rồi chụp màn hình cảnh báo.

---

## Phase 6: Các tình huống (Cases)

### Case 1: Case01_Account_Compromise_Report.pdf
- **Tình huống:** tài khoản email phòng tài chính bị lừa lấy mật khẩu (phishing). Kẻ tấn công đọc 318 email và tạo quy tắc tự chuyển tiếp thư ra ngoài.
- **Tôi đã làm gì:** báo cáo sự cố: dòng thời gian, cách ngăn chặn, nguyên nhân (không có MFA), các biện pháp đã thất bại và việc cần làm tiếp.
- **Ví dụ:** ngăn chặn = khóa phiên đăng nhập, xóa quy tắc chuyển tiếp, bật MFA. Nguyên nhân gốc nối với R-01.

### Case 2: Case02_Data_Breach_Assessment.pdf, Mock_ICO_Notification.pdf, Personal_Data_Breach_Register.xlsx
- **Tình huống:** một S3 bucket để công khai, chứa 2.400 hóa đơn của khoảng 1.100 người.
- **Tôi đã làm gì:** tách rõ đâu là sự thật, đâu là giả định. Xác định ApexPay là controller (bên quyết định dữ liệu). Đánh giá: có rủi ro nhưng không cao, nên báo ICO trong 72 giờ và gửi cảnh báo lừa đảo tới người bị ảnh hưởng. Mẫu báo ICO có băng đỏ "MOCK", **không bao giờ được nộp thật**.
- **Ví dụ (sổ vi phạm):** PDB-2026-001: biết sự cố lúc 02/11 10:00, ra quyết định lúc 04/11 10:00. Công thức tính ra 48 giờ, dưới mức 72 nên không bị tô đỏ.

### Case 3: Business_Impact_Analysis.xlsx, BCP, DRP, Ransomware_Tabletop_Report.pdf
- **Tình huống:** ransomware tấn công 20 laptop và máy chủ tài liệu. Bản sao lưu gần nhất đã cũ 48 giờ, và khôi phục mất khoảng 12 giờ.
- **BIA:** với 5 dịch vụ, công thức kiểm tra RTO có nhỏ hơn MTD không và RPO có nằm trong mức mất dữ liệu cho phép không. Ví dụ ở dịch vụ quản lý tài liệu: chỉ được mất tối đa 4 giờ dữ liệu, nhưng bản sao lưu cũ 48 giờ, tức gấp 12 lần mức cho phép, nên ô báo "No" màu đỏ.
- **BCP (kế hoạch duy trì kinh doanh):** con người, quyết định và truyền thông khi có sự cố. Ví dụ: đội khủng hoảng họp trong 1 giờ, cập nhật trang trạng thái cho khách hàng trong 2 giờ.
- **DRP (kế hoạch khôi phục kỹ thuật):** các bước kỹ thuật cụ thể. Ví dụ: khôi phục cơ sở dữ liệu về một thời điểm, kiểm tra số dòng, rồi mới chuyển ứng dụng sang.
- **Tabletop (diễn tập trên giấy, mô phỏng):** 6 tình huống được đưa ra theo thời gian. Ví dụ ở T+4h, kẻ tấn công nói đã lấy danh sách khách hàng. Câu trả lời đúng: coi đây là vi phạm dữ liệu có thể xảy ra, và mặc định không trả tiền chuộc.

### Case 4: Vendor_Risk_Register.xlsx, Vendor_Security_Questionnaire.xlsx, SupportFlow_Risk_Assessment.pdf, Third_Party_Risk_Management_Procedure.pdf
- **Tình huống:** nhà cung cấp phần mềm hỗ trợ khách hàng SupportFlow bị tấn công, nhưng 36 giờ sau mới báo cho ApexPay.
- **Vendor register:** 6 nhà cung cấp. Điểm = độ nhạy dữ liệu + mức phụ thuộc + mức truy cập. Ví dụ: AWS 5+5+5 = 15, Critical. Tôi **không bịa chứng chỉ** cho AWS, Microsoft hay GitHub, chỉ ghi nơi tải báo cáo thật (AWS Artifact, Microsoft Service Trust Portal).
- **Questionnaire:** 20 câu hỏi có trọng số. Có câu "knockout": trả lời "No" là không được duyệt. Ví dụ câu Q14: "Có báo sự cố trong 24 giờ không?" SupportFlow trả lời No. Tổng điểm SupportFlow là 46%.
- **SupportFlow assessment:** quyết định không giữ nguyên, cũng không thay ngay, mà cho 60 ngày (đến 20/01/2027) để đáp ứng 5 điều kiện. Nếu không đạt thì thay nhà cung cấp.
- **TPRM procedure:** quy trình 9 bước cho mọi nhà cung cấp, từ khi có nhu cầu mua đến khi kết thúc hợp đồng.

### Case 5: Application_Security_Risk_Assessment.pdf, Risk_Exception_Request.pdf, Secure_Release_Checklist.xlsx
- **Tình huống:** kiểm thử xâm nhập phát hiện lỗi: khách hàng chỉ cần đổi số ID là xem được hóa đơn của công ty khác. Ngày mai phải phát hành.
- **Phân tích:** có 4 lựa chọn. Tôi chọn C: sửa nhanh phần kiểm tra quyền (tenant), phát hành trễ 2 ngày, sửa đầy đủ trước 04/12.
- **Ví dụ so sánh:** giống như phát hiện cửa nhà hàng xóm mở được bằng chìa khóa nhà mình. Không thể "chấp nhận" để vậy. Phải thay ổ khóa tạm trước, rồi mới thay hệ thống khóa đầy đủ.
- **Exception:** chỉ xin ngoại lệ cho phần "chưa kiểm thử lại toàn bộ", có hạn đến 04/12, kèm 6 biện pháp bù đắp. Chỉ CEO được ký, vì rủi ro gốc là Critical.
- **Checklist:** 15 cổng kiểm tra trước khi phát hành. Công thức tự ra kết quả "BLOCKED", "GO" hoặc "GO with exception". Ở bản phát hành mẫu, kết quả là "GO with exception".

### Case 6: AI_Feature_Risk_Assessment.pdf, Data_Protection_Impact_Assessment.pdf, Record_of_Processing_Activities.xlsx
- **Tình huống:** dùng AI bên ngoài để dự đoán khách hàng nào sẽ trả tiền chậm. Bên AI giữ dữ liệu 30 ngày và chưa rõ có dùng để huấn luyện mô hình không.
- **AI risk assessment:** có sơ đồ luồng dữ liệu, xác định vai trò của từng bên và kiểm tra có cần làm DPIA không. Kết luận: phải làm DPIA.
- **DPIA (đánh giá tác động đến quyền riêng tư):** 7 rủi ro cho cá nhân. Ví dụ: một doanh nghiệp nhỏ bán hàng theo mùa bị AI dán nhãn "hay trả chậm" một cách sai. Đi kèm là 7 điều kiện bắt buộc trước khi chạy thử, ví dụ hợp đồng cấm dùng dữ liệu để huấn luyện mô hình.
- **RoPA (sổ ghi hoạt động xử lý dữ liệu, Điều 30):** ví dụ PA-09 "AI assistant" được đánh dấu PROPOSED màu cam, chưa được phép chạy.

### Case 7: Revised_Security_Investment_Business_Case.pdf
- **Tình huống:** ngân sách bị cắt từ £100.000 xuống £70.000.
- **Tôi đã làm gì:** giữ nguyên mọi biện pháp xử lý rủi ro Critical. Cắt MDR £30k xuống £12k (chỉ theo dõi giờ hành chính), EDR £12k xuống £6k (triển khai làm 2 đợt), pháp lý £6k xuống £2k. Giữ tiền cho chứng nhận.
- **Ví dụ hậu quả:** R-08 (phát hiện tấn công chậm) chỉ giảm được xuống High (12) thay vì Medium (8), vì đêm và cuối tuần không có ai theo dõi. Ủy ban chấp nhận rủi ro này đến 18/05/2027 và xin lại £24k cho năm tài chính sau.

### Regulatory_Register.xlsx và UK_GDPR_Assessment.xlsx
- **Regulatory register:** 17 nghĩa vụ. Mỗi nghĩa vụ có nguồn, lý do áp dụng, yêu cầu, người phụ trách, bằng chứng, khoảng cách và hành động. Điểm quan trọng: **không mặc định** mọi luật tài chính đều áp dụng chỉ vì là fintech. Ví dụ REG-08 (giấy phép FCA): ghi "To confirm", vì chưa biết ApexPay có tự cung cấp dịch vụ thanh toán hay chỉ chuyển lệnh cho bên khác.
- **UK GDPR assessment:** 21 mục theo từng điều luật, chấm Compliant / Partial / Gap. Tổng điểm 48%. Ví dụ G-05 (giới hạn lưu trữ) là Gap, vì dữ liệu khách hàng được giữ vô thời hạn, và chính 2.400 hóa đơn cũ đó đã bị lộ ở Case 2.

---

## Phase 7: Đánh giá hiệu quả

### GRC_Performance_Dashboard.xlsx
- **Để làm gì:** bảng điều khiển: các chỉ số đang xanh, vàng hay đỏ.
- **Tôi đã làm gì:** 12 chỉ số. KPI đo kết quả, KRI cảnh báo rủi ro. Mỗi chỉ số có cách tính, nguồn, người phụ trách và ngưỡng leo thang. Màu xanh/vàng/đỏ do công thức tự tính. Có 5 biểu đồ.
- **Ví dụ:** KPI-01 MFA: ban đầu 80%, kế hoạch tháng 3 là 95%, thực tế 95% (E-02: 114/120), nên màu xanh. KRI-11 "Cảnh báo được xem xét": 0%, nên màu đỏ.
- **Đối chiếu:** ban quản lý ước tính có 2 rủi ro Critical, nhưng sổ rủi ro chỉ còn 1. Sheet "Reconciliation" giải thích vì sao khác nhau.

### Internal_Audit_Programme.xlsx
- **Để làm gì:** kế hoạch kiểm toán cả năm: kiểm cái gì, khi nào, ai kiểm.
- **Ví dụ:** IA-02 (rủi ro và SoA) do người đánh giá độc lập bên ngoài làm, vì chính người tư vấn GRC đã viết các tài liệu đó và không được tự kiểm toán việc mình làm. Có sheet tiêu chí phân loại major/minor và sheet cách chọn mẫu.

### Audit_Checklist.xlsx
- **Để làm gì:** danh sách câu hỏi kiểm toán và kết quả.
- **Ví dụ:** C-11 "MFA có được bắt buộc cho mọi tài khoản không?": hỏi IT Manager, xem báo cáo hệ thống cho 120 tài khoản, bằng chứng E-02. Kết quả: Nonconformity, dẫn tới AUD-01.

### Audit_Evidence_Register.xlsx
- **Để làm gì:** ghi nguồn gốc mỗi bằng chứng và kiểm tra chất lượng: đúng phạm vi không, có thật không, có đủ không.
- **Ví dụ:** E-10 "SoA ghi giám sát đầy đủ nhưng không có hồ sơ". Ghi chú: không có hồ sơ chưa chắc là không ai làm, cần hỏi thêm trước khi kết luận. Các dòng LAB đang "Pending" chờ bằng chứng thật của bạn.

### Internal_Audit_Report.pdf
- **Để làm gì:** báo cáo kiểm toán nội bộ (bản mock).
- **Tôi đã làm gì:** 12 phát hiện: 1 major, 6 minor, 2 quan sát, 2 cơ hội cải tiến, 1 phù hợp. Kết luận: chưa sẵn sàng cho Stage 1.
- **Ví dụ:** AUD-06 (major): tiêu chí là điều 6.1.3 d và A.8.16. Tình trạng: SoA ghi đã làm đầy đủ nhưng không có hồ sơ xem xét cảnh báo. Sửa ngay: đổi trạng thái thành "Partially" và bắt đầu ghi nhật ký hằng ngày.

### Management_Review_Minutes.pdf
- **Để làm gì:** điều 9.3: lãnh đạo xem toàn bộ tình hình và ra quyết định.
- **Tôi đã làm gì:** biên bản họp mô phỏng ngày 13/05/2027, đủ các mục bắt buộc, với 9 quyết định có người phụ trách và hạn.
- **Ví dụ:** D5 lùi Stage 1 sang 9/2027. D1: R-08 vẫn là Critical nên chỉ CEO được chấp nhận, tối đa 30 ngày (đến 12/06).

---

## Phase 8: Cải tiến và sẵn sàng chứng nhận

### Root_Cause_Analysis.pdf
- **Để làm gì:** tìm nguyên nhân gốc, không dừng ở việc "ai đó làm sai".
- **Tôi đã làm gì:** dùng phương pháp 5 Whys (hỏi "tại sao" 5 lần) cho 5 phát hiện, và một biểu đồ xương cá cho AUD-06. Mỗi câu trả lời được đánh dấu là "đã xác minh" hay chỉ là "giả thuyết".
- **Ví dụ (AUD-07, thay đổi production không được duyệt):** Tại sao? Kỹ sư đẩy thẳng code lên. Tại sao làm được? Quyền admin cho phép bỏ qua bước bảo vệ. Tại sao không có cách nào khác? Quy trình PRO-006 không có đường xử lý khẩn cấp. Kết luận: lỗi nằm ở hệ thống, không nằm ở người kỹ sư.
- **Nguyên nhân chung:** việc duyệt và lưu bằng chứng chưa được gắn sẵn vào công cụ và quy trình.

### Corrective_Action_Register.xlsx
- **Để làm gì:** theo dõi từng hành động khắc phục cho đến khi được chứng minh là có hiệu quả.
- **Tôi đã làm gì:** 9 hành động. Mỗi hành động có nguyên nhân gốc, cách sửa ngay, hành động khắc phục lâu dài, hạn, cách xác minh, đợt kiểm tra hiệu quả, và câu hỏi "lỗi tương tự có ở chỗ khác không?". Số ngày còn lại do công thức tính.
- **Ví dụ:** CAR-02 (MFA): sửa ngay bằng cách bật MFA cho 6 tài khoản ngày 20/05. Lâu dài: đưa MFA vào checklist nhận nhân viên mới và bỏ nhóm ngoại lệ. Khi kiểm tra chỗ khác, phát hiện EDR cũng bị bỏ sót lúc nhận người mới.

### ISO27001_Certification_Readiness_Report.pdf
- **Để làm gì:** trả lời câu hỏi "đã sẵn sàng để chứng nhận chưa?".
- **Tôi đã làm gì:** so sánh rủi ro ban đầu, hiện tại và mục tiêu. Đánh giá từng điều khoản 4-10. Phân loại bằng chứng (lab thật, mô phỏng, chỉ có thiết kế, không có gì). Liệt kê yêu cầu chưa đạt và quyết định còn treo.
- **Ví dụ:** rủi ro Critical giảm từ 7 xuống 1. Stage 1 gần sẵn sàng (9/2027). Stage 2 chưa sẵn sàng (11/2027), vì 7 trên 26 rủi ro chính chưa có bằng chứng nào.

### Risk_Control_Evidence_Traceability_Matrix.xlsx
- **Để làm gì:** một bảng nối tất cả lại với nhau: rủi ro → biện pháp → chính sách → hành động → bài kiểm tra → bằng chứng → kết quả → quyết định → phát hiện kiểm toán → hành động khắc phục.
- **Ví dụ:** R-15 (thay đổi không được duyệt) → A.8.32 → PRO-006 → RM-14 → CT-010 → E-11 → "Not effective (3 trên 25)" → AUD-07 → CAR-07.
- **Mẹo:** lọc cột "Evidence type" theo NONE để thấy ngay những chỗ kiểm toán viên sẽ hỏi khó.

### README.md
- **Để làm gì:** trang giới thiệu khi bạn đưa dự án lên GitHub, gồm phạm vi, phương pháp, kết quả chính, danh sách file và giới hạn.

### Các file Phase 3 được cập nhật ở Phase 8
- Risk register có thêm sheet **Update Jun 2027**, treatment plan có thêm **Update Jun 2027**, SoA có thêm **Change log**, STRIDE có thêm **Additions 2027**.
- Các sheet gốc **giữ nguyên**, để có thể so sánh trước và sau.

---

## Việc chỉ bạn làm được

1. Làm các lab thật, chụp màn hình, rồi bỏ vào `Technical_Evidence/`.
2. Điền phần "Your results" trong Lab_Writeups và cột kết quả trong Control Testing Register.
3. Đổi các dòng "Pending" trong Audit Evidence Register thành bằng chứng thật.
4. Nếu được, nhờ một người khác xem lại phần kiểm toán, vì bạn vừa là người viết vừa là người kiểm toán.
