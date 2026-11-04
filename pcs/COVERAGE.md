# Sổ phủ yêu cầu theo mã SOW (Coverage Register)

Lập tại T-049 (2026-11-04), từ rà soát T-048. Bản máy đọc: `pcs/coverage.json` (sinh từ cùng một nguồn — sửa ở script lập sổ, không sửa tay hai nơi).

## Vũ trụ yêu cầu

- Nguồn: SOW R30 Hiệu Đính (SHA-256 `1904e7fe…e8049`), chiết xuất theo từng bảng trong DOCX; đối chiếu khớp tuyệt đối với con số SOW tự công bố: **389 mã FR/NFR/SEC duy nhất = 302 FR (22 nhóm, không thiếu số nào trong từng nhóm) + 56 NFR + 31 SEC**. Đây đúng là vũ trụ của file `IAICT_R30_Traceability_Ledger.csv` mà SOW nhắc tới (file CSV không được bàn giao kèm — sổ này thay thế nó).
- Ngoài vũ trụ 389: các họ D (64 đầu ra), UAT (115), REP (82), HW (11), GL (25), OPT (8), CMP (12) được theo dõi ở biên bản rà soát/ma trận §12.4, không nằm trong sổ này.

## Quy tắc trạng thái (theo chính quy tắc sổ truy vết của SOW)

- **COVERED**: đã triển khai VÀ có bằng chứng kiểm thử tự động hoặc probe trên bản live.
- **PARTIAL**: đã triển khai một phần, hoặc đã triển khai nhưng thiếu bằng chứng trực tiếp, hoặc lệch mô hình so với SOW (ghi rõ ở cột ghi chú).
- **NOT_STARTED**: chưa triển khai. Không mã nào được nâng lên COVERED khi chưa có test run/bằng chứng — đúng điều SOW cấm ("Không được chuyển PENDING_MAPPING/NOT_RUN thành PASS").
- **Duy trì**: mỗi checkpoint PCS chạm tới mã nào thì cập nhật mã đó trong `coverage.json` và sinh lại file này; task liên quan ghi mã vào `srs_refs` của STATE.

## Tổng hợp

- Toàn bộ 389 mã: **COVERED 33 · PARTIAL 111 · NOT_STARTED 245**.
- Riêng 302 FR: COVERED 25 · PARTIAL 77 · NOT_STARTED 200 — phần đã phủ tập trung ở lõi sản xuất/truy xuất (ZON/MPL/FLD/LOT/TRC + Phụ lục U); phần chưa phủ lớn nhất là lớp thương mại/vận hành (COM/CRM/PAY/MOP/AIX) thuộc mốc M5–M7 và nền tảng lõi còn thiếu (BLC = D-10, entitlement/metering trong COM/ADM).

| Nhóm | Tên | Tổng | COVERED | PARTIAL | NOT_STARTED |
|---|---|---|---|---|---|
| TEN | Tenant Experience & thương hiệu | 12 | 0 | 2 | 10 |
| ADM | Quản trị & danh tính | 15 | 1 | 7 | 7 |
| GEN | Khung lõi / Vertical Pack | 12 | 2 | 6 | 4 |
| ZON | Vùng sản xuất & PUC | 10 | 2 | 4 | 4 |
| MPL | Cây đầu dòng | 16 | 0 | 6 | 10 |
| FLD | Canh tác & tuân thủ PHI | 20 | 6 | 5 | 9 |
| LOT | Lô, đóng gói, vận chuyển, thu hồi | 17 | 5 | 6 | 6 |
| TRC | Truy xuất & mã GS1 | 17 | 2 | 5 | 10 |
| IOT | IoT | 15 | 0 | 5 | 10 |
| MOB | Ứng dụng di động | 13 | 1 | 1 | 11 |
| AIX | AI Gateway | 10 | 0 | 0 | 10 |
| LFC | Vòng đời & Event Ledger | 13 | 1 | 8 | 4 |
| BLC | Toàn vẹn dữ liệu / blockchain | 9 | 0 | 0 | 9 |
| HLT | Sức khỏe & dịch tễ | 12 | 0 | 5 | 7 |
| PRO | Chủ thể & địa giới | 10 | 2 | 5 | 3 |
| CRM | CRM | 12 | 0 | 0 | 12 |
| MOP | Vận hành ủy thác | 10 | 0 | 0 | 10 |
| STD | Tiêu chuẩn & đánh giá tuân thủ | 10 | 0 | 5 | 5 |
| COM | Thương mại / subscription / metering | 41 | 0 | 2 | 39 |
| RPT | Báo cáo | 12 | 1 | 3 | 8 |
| PAY | Thanh toán | 12 | 1 | 0 | 11 |
| API | API & tích hợp | 4 | 1 | 2 | 1 |
| NFR | Phi chức năng | 56 | 4 | 23 | 29 |
| SEC | An toàn thông tin | 31 | 4 | 11 | 16 |

## TEN — Tenant Experience & thương hiệu

| Mã | Yêu cầu (rút gọn) | Trạng thái | Bằng chứng (task · test) | Ghi chú |
|---|---|---|---|---|
| TEN-01 | Tenant Experience Profile versioned: display name, short name, logo, favicon, color tokens, cov… | NOT_STARTED | — | Trải nghiệm tenant/thương hiệu/tên miền — chưa xây. |
| TEN-02 | Subdomain IAICT cấp theo slug cấu hình, ví dụ phuyen.iaict-platform.com; slug/host chỉ là alias… | NOT_STARTED | — | Trải nghiệm tenant/thương hiệu/tên miền — chưa xây. |
| TEN-03 | Custom domain hỗ trợ verify ownership, DNS/CAA hướng dẫn, TLS tự động, expiry/renewal/health và… | NOT_STARTED | — | Trải nghiệm tenant/thương hiệu/tên miền — chưa xây. |
| TEN-04 | Hỗ trợ Primary Domain + Alias Domains + Redirect/Canonical; thay primary không đổi tenant ID ho… | NOT_STARTED | — | Trải nghiệm tenant/thương hiệu/tên miền — chưa xây. |
| TEN-05 | Ba mode thương hiệu: IAICT Branding, Co-branding/Powered by IAICT, Full White-label; mode do pl… | NOT_STARTED | — | Trải nghiệm tenant/thương hiệu/tên miền — chưa xây. |
| TEN-06 | Menu, landing page, dashboard mặc định, module visible, terminology label, banner/news/help lin… | NOT_STARTED | — | Trải nghiệm tenant/thương hiệu/tên miền — chưa xây. |
| TEN-07 | Trang QR/public trace có branding tenant/sản phẩm và dữ liệu công khai versioned; logo/HTML/con… | NOT_STARTED | — | Trải nghiệm tenant/thương hiệu/tên miền — chưa xây. |
| TEN-08 | Brand asset lưu object storage theo tenant/version, có kích thước/định dạng/virus scan/checksum… | NOT_STARTED | — | Trải nghiệm tenant/thương hiệu/tên miền — chưa xây. |
| TEN-09 | Provision tenant từ template gồm plan/module/role/workflow/branding/subdomain; baseline hợp lệ … | PARTIAL | — | Provision tenant + bootstrap admin + workspace có; template plan/module/branding/subdomain chưa có. |
| TEN-10 | Theme/branding thay đổi phải có draft→review→publish, owner/effective date; thay đổi domain/whi… | NOT_STARTED | — | Trải nghiệm tenant/thương hiệu/tên miền — chưa xây. |
| TEN-11 | Một product baseline: cấm branch/fork per tenant để đổi giao diện/nghiệp vụ; extension qua conf… | PARTIAL | — | Một codebase duy nhất, cấu hình theo tenant; feature flag chưa có. |
| TEN-12 | Customer-facing email/template/notification cơ sở hỗ trợ tenant branding nhưng domain gửi, DKIM… | NOT_STARTED | — | Trải nghiệm tenant/thương hiệu/tên miền — chưa xây. |

## ADM — Quản trị & danh tính

| Mã | Yêu cầu (rút gọn) | Trạng thái | Bằng chứng (task · test) | Ghi chú |
|---|---|---|---|---|
| ADM-01 | Tạo và quản lý nhiều tenant; dữ liệu các tenant tách biệt ở tầng ứng dụng và truy vấn. | COVERED | T-003 · test_platform/test_identity | Registry tenant + guard + khóa ngoại phức hợp chống chéo tenant; test ở cả 4 chế độ store. |
| ADM-02 | Quản lý OrganizationUnit, Site, vai trò và trạng thái tài khoản; Producer/AdministrativeUnit dù… | PARTIAL | T-003 · test_platform/test_identity | Có actors/users/trạng thái tài khoản (Bảng 32); OrganizationUnit/Site chưa là thực thể riêng (site ≈ vùng). |
| ADM-03 | RBAC Core tối thiểu: quản trị IAICT, quản trị tenant, vận hành, kiểm tra/chất lượng và chỉ xem.… | PARTIAL | T-003 · test_platform/test_identity | 3 vai trò VIEWER/OPERATOR/TENANT_ADMIN + platform admin, cưỡng chế ở backend; thiếu vai trò kiểm tra/chất lượng riêng. |
| ADM-04 | Đăng nhập bằng email/số điện thoại; chính sách mật khẩu; khóa sau nhiều lần sai. | NOT_STARTED | T-003 · test_platform/test_identity | Chưa có đăng nhập mật khẩu — mô hình hiện tại là định danh actor qua header; khác thiết kế SOW, cần quyết định. |
| ADM-05 | MFA bắt buộc cho super-admin/quản trị IAICT và có thể cấu hình bắt buộc theo vai trò/plan; TOTP… | NOT_STARTED | T-003 · test_platform/test_identity |  |
| ADM-06 | Nhật ký đăng nhập, đăng xuất, đổi quyền, xuất dữ liệu và thao tác quản trị. | PARTIAL | T-003 · test_platform/test_identity | Audit thao tác quản trị kèm snapshot trước/sau + IP/thiết bị; không có sự kiện đăng nhập/đăng xuất (không có phiên). |
| ADM-07 | Cấu hình thương hiệu theo tenant: logo, tên hiển thị, tên miền/slug, thông tin liên hệ. | NOT_STARTED | T-003 · test_platform/test_identity |  |
| ADM-08 | Nhập/xuất người dùng bằng mẫu có kiểm tra lỗi và báo cáo kết quả. | NOT_STARTED | T-003 · test_platform/test_identity |  |
| ADM-09 | Super-admin IAICT tạo, cấu hình, tạm ngừng, khôi phục và kết thúc tenant theo quyền bốn mắt với… | PARTIAL | T-003 · test_platform/test_identity | Tạo/tạm ngừng/khôi phục tenant qua platform API có; thiếu duyệt bốn mắt và kết thúc tenant. |
| ADM-10 | Quản lý tên miền riêng/tên miền con (custom domain/subdomain), logo, màu, thông tin hỗ trợ và m… | NOT_STARTED | T-003 · test_platform/test_identity |  |
| ADM-11 | Quản lý named account; cấm dùng chung tài khoản nghiệp vụ; tài khoản dịch vụ/API và định danh t… | PARTIAL | T-003 · test_platform/test_identity | Tài khoản đặt tên riêng; định danh thiết bị tách riêng (T-046); tài khoản dịch vụ/API chưa có. |
| ADM-12 | API key/client credential theo tenant, scope, hạn dùng, quota, xoay vòng và thu hồi. | PARTIAL | T-003 · test_platform/test_identity | Khóa thiết bị có xoay vòng/thu hồi; API key tổng quát theo tenant (scope/hạn/quota) chưa có. |
| ADM-13 | Feature flag/module entitlement theo plan và scope tenant/OrganizationUnit/Producer/Site; thay … | NOT_STARTED | T-003 · test_platform/test_identity |  |
| ADM-14 | Quản trị viên tenant xem người dùng, site, thiết bị, hạn mức và audit thuộc tenant nhưng không … | PARTIAL | T-003 · test_platform/test_identity | Màn hình tenant chỉ thấy dữ liệu tenant mình (user/audit/thiết bị); hạn mức chưa có. |
| ADM-15 | Hỗ trợ cấu hình SSO OIDC/SAML cho gói tùy chọn mà không thay đổi cơ chế đăng nhập tenant khác. | NOT_STARTED | T-003 · test_platform/test_identity |  |

## GEN — Khung lõi / Vertical Pack

| Mã | Yêu cầu (rút gọn) | Trạng thái | Bằng chứng (task · test) | Ghi chú |
|---|---|---|---|---|
| GEN-01 | Core Domain phải dùng mô hình trung lập ngành trong phạm vi tenant: AdministrativeUnit/Organiza… | COVERED | T-032 · test_fields_codegen | Mô hình lõi trung lập ngành đã chạy cho 4 ngành (T-035/T-036). |
| GEN-02 | Mỗi Vertical Pack có ID/version/manifest, phụ thuộc Core version, schema extension, form, workf… | NOT_STARTED | T-032 · test_fields_codegen | Khung lõi + registry là nền; pack/entitlement chưa có. |
| GEN-03 | Tenant bật/tắt Vertical Pack bằng entitlement; một tenant có thể dùng nhiều pack nếu không xung… | NOT_STARTED | T-032 · test_fields_codegen | Khung lõi + registry là nền; pack/entitlement chưa có. |
| GEN-04 | Form/field/checklist đặc thù ngành được cấu hình qua schema/metadata trong giới hạn framework. … | COVERED | T-032 · test_fields_codegen | Form/trường sinh từ field registry duy nhất; test chống lệch (drift) khóa hành vi này. |
| GEN-05 | Rule/approval/exception đặc thù ngành được version hóa, có ngày hiệu lực và quản trị bốn mắt kh… | PARTIAL | T-032 · test_fields_codegen | Luật tuân thủ đang là cổng cứng trong code, chưa version hóa/cấu hình hiệu lực. |
| GEN-06 | Báo cáo/dashboard đặc thù ngành dùng template/dataset contract, không viết logic truy vấn hard-… | PARTIAL | T-032 · test_fields_codegen | 3 endpoint báo cáo tính trực tiếp từ dữ liệu vận hành; chưa có template/dataset contract. |
| GEN-07 | IoT dùng Device Profile và Measurement Profile để thêm model, codec, kênh đo, đơn vị, calibrati… | PARTIAL | T-032 · test_fields_codegen | Có loại thiết bị + registry ingest; Device/Measurement Profile và codec versioned chưa có. |
| GEN-08 | Traceability engine hỗ trợ event/relationship generic; Vertical Pack chỉ mapping CTE/KDE/bizSte… | PARTIAL | T-032 · test_fields_codegen | CTE stages là event truy xuất tổng quát; mapping KDE/bizStep chưa theo EPCIS. |
| GEN-09 | Không fork Core theo tenant/vertical. Mọi ngoại lệ cần code phải đi qua extension point/plugin … | PARTIAL | T-032 · test_fields_codegen | Không fork theo tenant (một bản dựng); extension point/plugin contract chưa có. |
| GEN-10 | Vertical Pack có compatibility matrix với Core, migration versioned và test regression. | PARTIAL | T-032 · test_fields_codegen | Migration đánh số phiên bản + bộ test hồi quy đầy đủ có; ma trận tương thích pack chưa có. |
| GEN-11 | IAICT có thể tự tạo/cập nhật pack sau bàn giao bằng tài liệu/công cụ được chuyển giao, không cầ… | NOT_STARTED | T-032 · test_fields_codegen | Khung lõi + registry là nền; pack/entitlement chưa có. |
| GEN-12 | M7 phải qualification bằng ít nhất hai miền khác biệt với pilot: Aquaculture Qualification Pack… | NOT_STARTED | T-032 · test_fields_codegen | Khung lõi + registry là nền; pack/entitlement chưa có. |

## ZON — Vùng sản xuất & PUC

| Mã | Yêu cầu (rút gọn) | Trạng thái | Bằng chứng (task · test) | Ghi chú |
|---|---|---|---|---|
| ZON-01 | Tạo vùng nguyên liệu, site, thửa/ô vùng trồng với tên, mã, diện tích, địa chỉ và tọa độ. | PARTIAL | T-004, T-015, T-031, T-040, T-041 · test_m3_traceability, test_gd3_market | Vùng/thửa theo Bảng 7 hồ sơ chuẩn; tên/địa chỉ/tọa độ của ZON-01 không nằm trong 33 bảng nên đã cắt ở T-034 (lệch có ghi nhận). |
| ZON-02 | Vẽ/chỉnh sửa polygon trên bản đồ hoặc nhập GeoJSON/KML; tính diện tích tham chiếu. Lưu/chuẩn hó… | NOT_STARTED | T-004, T-015, T-031, T-040, T-041 · test_m3_traceability, test_gd3_market | Chưa có bản đồ/polygon; boundary_polygon_gis mới là trường lưu ở danh mục hành chính. |
| ZON-03 | Gắn chủ thể quản lý, nhóm cây, mùa vụ, nguồn nước, tình trạng và hồ sơ liên quan. | PARTIAL | T-004, T-015, T-031, T-040, T-041 · test_m3_traceability, test_gd3_market | Chủ thể quản lý + ngành + trạng thái PUC có; nhóm cây/nguồn nước đã cắt theo 33 bảng; hồ sơ đính kèm chưa có. |
| ZON-04 | Quản lý phiên bản ranh giới; lưu người sửa, thời gian và lý do. | NOT_STARTED | T-004, T-015, T-031, T-040, T-041 · test_m3_traceability, test_gd3_market | Bảng zone_boundary_versions có trong schema nhưng chưa có luồng API/UI. |
| ZON-05 | Gắn cảm biến/gateway vào vị trí địa lý và hiển thị trạng thái trên bản đồ. | PARTIAL | T-004, T-015, T-031, T-040, T-041 · test_m3_traceability, test_gd3_market | Thiết bị gắn vùng/thửa (T-045); chưa hiển thị trên bản đồ. |
| ZON-06 | Tra cứu vùng theo mã, tên, cây trồng, trạng thái, site và người quản lý. | PARTIAL | T-004, T-015, T-031, T-040, T-041 · test_m3_traceability, test_gd3_market | Danh sách + lọc phía client; chưa có tìm kiếm phía server. |
| ZON-07 | Đính kèm giấy tờ, biên bản, ảnh và tài liệu; phân loại công khai/nội bộ. | NOT_STARTED | T-004, T-015, T-031, T-040, T-041 · test_m3_traceability, test_gd3_market | Chưa có hệ thống đính kèm tài liệu/ảnh (chỉ vài trường URL đơn lẻ). |
| ZON-08 | Hỗ trợ lớp bản đồ nền thay thế và không hard-code nhà cung cấp. | NOT_STARTED | T-004, T-015, T-031, T-040, T-041 · test_m3_traceability, test_gd3_market | Chưa có bản đồ. |
| ZON-09 | Quản lý mã số vùng trồng theo thửa hoặc site: số mã, thị trường xuất khẩu tương ứng, cơ quan cấ… | COVERED | T-004, T-015, T-031, T-040, T-041 · test_m3_traceability, test_gd3_market | Khối PUC đủ vòng đời 5 trạng thái + lịch sử trạng thái (Bảng 7/13). |
| ZON-10 | Gán thị trường xuất khẩu đích cho thửa hoặc site, làm căn cứ áp dụng danh mục hoạt chất bị hạn … | COVERED | T-004, T-015, T-031, T-040, T-041 · test_m3_traceability, test_gd3_market | Phê duyệt thị trường theo vùng (Bảng 8) — gán ở cấp vùng, không phải cấp thửa. |

## MPL — Cây đầu dòng

| Mã | Yêu cầu (rút gọn) | Trạng thái | Bằng chứng (task · test) | Ghi chú |
|---|---|---|---|---|
| MPL-01 | Cấp mã duy nhất và QR cho từng cây/cụm cây đầu dòng. | PARTIAL | T-004, T-024 · test_m3_traceability | Mã duy nhất có; QR cho cây chưa có. |
| MPL-02 | Lưu loài, giống, tên khoa học, nguồn gốc, năm trồng, vị trí, chủ sở hữu/quản lý. | PARTIAL | T-004, T-024 · test_m3_traceability | Loài/giống/tên khoa học/nguồn gốc/chủ quản có trong registry; năm trồng/vị trí chỉ ở mức mô tả. |
| MPL-03 | Lưu quyết định/công nhận, cơ quan cấp, ngày hiệu lực/hết hạn và tệp hồ sơ. | PARTIAL | T-004, T-024 · test_m3_traceability | Trường quyết định/cơ quan/hiệu lực có dạng mô tả; tệp hồ sơ chưa có. |
| MPL-04 | Theo dõi trạng thái sống, sinh trưởng, sức khỏe, sâu bệnh, nguy cơ và tình trạng bảo tồn. | PARTIAL | T-004, T-024 · test_m3_traceability | Có bảng lịch sử trạng thái cây; chỉ tiêu sinh trưởng/sức khỏe chi tiết chưa có. |
| MPL-05 | Ghi nhận kiểm tra định kỳ với checklist, ảnh, GPS, người kiểm tra và kết luận. | NOT_STARTED | T-004, T-024 · test_m3_traceability | Hồ sơ cây cơ bản có; gói định mức/báo cáo D-44 chưa có. |
| MPL-06 | Ghi nhận chăm sóc, tưới, bón, tỉa, phòng trừ, lấy mẫu và kết quả xét nghiệm. | PARTIAL | T-004, T-024 · test_m3_traceability | Chăm sóc ghi qua nhật ký đồng ruộng theo mùa vụ; chưa gắn trực tiếp từng cây. |
| MPL-07 | Quản lý vật liệu nhân giống lấy từ cây đầu dòng: loại, ngày, số lượng, lô đích. | NOT_STARTED | T-004, T-024 · test_m3_traceability | Hồ sơ cây cơ bản có; gói định mức/báo cáo D-44 chưa có. |
| MPL-08 | Cho phép khóa hồ sơ cây ngừng sử dụng nhưng không xóa lịch sử. | PARTIAL | T-004, T-024 · test_m3_traceability | Không có luồng khóa hồ sơ; xóa bị chặn khi đang được tham chiếu (409 RECORD_IN_USE). |
| MPL-09 | Cảnh báo lịch kiểm tra, hết hạn hồ sơ, tình trạng bất thường và mất dữ liệu cảm biến liên quan. | NOT_STARTED | T-004, T-024 · test_m3_traceability | Hồ sơ cây cơ bản có; gói định mức/báo cáo D-44 chưa có. |
| MPL-10 | Báo cáo danh sách cây, tình trạng, lịch sử bảo tồn, vật liệu nhân giống và điểm cần xử lý. | NOT_STARTED | T-004, T-024 · test_m3_traceability | Hồ sơ cây cơ bản có; gói định mức/báo cáo D-44 chưa có. |
| MPL-11 | Định mức khai thác vật liệu nhân giống theo dòng cây và theo kỳ; cảnh báo và chặn khi vượt định… | NOT_STARTED | T-004, T-024 · test_m3_traceability | Thuộc gói cấu hình D-44. |
| MPL-12 | Quản lý lô cây giống nhân từ cây đầu dòng: mã lô, số lượng, vườn ươm, tỷ lệ sống, ngày xuất và … | NOT_STARTED | T-004, T-024 · test_m3_traceability | Thuộc gói cấu hình D-44. |
| MPL-13 | Cảnh báo suy giảm khi năng suất hoặc chỉ tiêu sinh trưởng giảm quá ngưỡng cấu hình so với trung… | NOT_STARTED | T-004, T-024 · test_m3_traceability | Thuộc gói cấu hình D-44. |
| MPL-14 | Bản đồ vườn cây đầu dòng có lớp phủ trạng thái: bình thường, cần theo dõi, suy giảm, sắp hết hạ… | NOT_STARTED | T-004, T-024 · test_m3_traceability | Thuộc gói cấu hình D-44. |
| MPL-15 | Hồ sơ sức khỏe cây: kết quả kiểm nghiệm sạch bệnh theo chỉ tiêu, đơn vị kiểm nghiệm, tệp phiếu … | NOT_STARTED | T-004, T-024 · test_m3_traceability | Thuộc gói cấu hình D-44. |
| MPL-16 | Kết xuất hồ sơ cây đầu dòng và vườn cây đầu dòng theo biểu mẫu phục vụ báo cáo cơ quan quản lý … | NOT_STARTED | T-004, T-024 · test_m3_traceability | Thuộc gói cấu hình D-44. |

## FLD — Canh tác & tuân thủ PHI

| Mã | Yêu cầu (rút gọn) | Trạng thái | Bằng chứng (task · test) | Ghi chú |
|---|---|---|---|---|
| FLD-01 | Tạo mùa vụ/kế hoạch canh tác theo vùng, cây, thời gian và mục tiêu sản lượng. | COVERED | T-004, T-015, T-043 · test_m3_traceability, test_gd3_logistics |  |
| FLD-02 | Ghi nhật ký tưới, bón, làm đất, tỉa, xử lý sâu bệnh, kiểm tra và thu hoạch. | COVERED | T-004, T-015, T-043 · test_m3_traceability, test_gd3_logistics |  |
| FLD-03 | Liên kết vật tư với tên, nhà cung cấp, lô vật tư, số lượng, đơn vị và người sử dụng. | COVERED | T-004, T-015, T-043 · test_m3_traceability, test_gd3_logistics |  |
| FLD-04 | Ghi thời gian, GPS, người thực hiện, thiết bị, ảnh và ghi chú cho mỗi sự kiện. | PARTIAL | T-004, T-015, T-043 · test_m3_traceability, test_gd3_logistics | Thời gian/người thực hiện có; GPS/ảnh/thiết bị đã cắt theo 33 bảng ở T-034 (lệch có ghi nhận). |
| FLD-05 | Cho phép mẫu checklist động cho kiểm tra cây/vùng/kho. | NOT_STARTED | T-004, T-015, T-043 · test_m3_traceability, test_gd3_logistics |  |
| FLD-06 | Hỗ trợ nhập nhanh nhiều cây/lô và sao chép kế hoạch có kiểm soát. | NOT_STARTED | T-004, T-015, T-043 · test_m3_traceability, test_gd3_logistics |  |
| FLD-07 | Sự kiện đã chốt không sửa trực tiếp; hiệu chỉnh bằng phiên bản hoặc bản ghi đảo. | PARTIAL | T-004, T-015, T-043 · test_m3_traceability, test_gd3_logistics | Nhật ký append-only, không sửa/xóa qua API; cơ chế bản ghi đảo/hiệu chỉnh chưa có. |
| FLD-08 | Đính kèm ảnh trước/sau, tài liệu và kết quả đo thủ công. | NOT_STARTED | T-004, T-015, T-043 · test_m3_traceability, test_gd3_logistics |  |
| FLD-09 | Tạo nhiệm vụ, giao người, hạn xử lý và trạng thái hoàn thành. | NOT_STARTED | T-004, T-015, T-043 · test_m3_traceability, test_gd3_logistics |  |
| FLD-10 | Hiển thị số liệu IoT liên quan tại thời điểm/sự kiện để tham khảo. | NOT_STARTED | T-004, T-015, T-043 · test_m3_traceability, test_gd3_logistics |  |
| FLD-11 | Xuất nhật ký theo vùng, mùa vụ, cây, khoảng thời gian và loại hoạt động. | NOT_STARTED | T-004, T-015, T-043 · test_m3_traceability, test_gd3_logistics |  |
| FLD-12 | Cơ chế duyệt hai bước cho sự kiện quan trọng do IAICT cấu hình. | NOT_STARTED | T-004, T-015, T-043 · test_m3_traceability, test_gd3_logistics |  |
| FLD-13 | Danh mục vật tư đầu vào lưu hoạt chất, hàm lượng, số đăng ký lưu hành, liều khuyến cáo, thời gi… | COVERED | T-004, T-015, T-043 · test_m3_traceability, test_gd3_logistics | Danh mục vật tư theo Bảng 17 + danh mục hoạt chất/MRL (Bảng 3); dữ liệu danh mục trên beta đang rỗng. |
| FLD-14 | Danh mục hoạt chất bị cấm hoặc bị hạn chế theo từng thị trường xuất khẩu, cấu hình và cập nhật … | PARTIAL | T-004, T-015, T-043 · test_m3_traceability, test_gd3_logistics | Khung danh mục theo thị trường có (Bảng 2/3); ngữ nghĩa cấm/hạn chế theo thị trường mới một phần; dữ liệu rỗng. |
| FLD-15 | Khi ghi nhật ký sử dụng vật tư, hệ thống kiểm tra và cảnh báo tức thời ba trường hợp: vật tư ng… | PARTIAL | T-004, T-015, T-043 · test_m3_traceability, test_gd3_logistics | Kiểm tra PHI có; kiểm tra hoạt chất bị cấm theo thị trường đích tại thời điểm ghi nhật ký chưa có. |
| FLD-16 | Kiểm tra điều kiện cách ly của mọi lần sử dụng thuốc liên quan trên từng thửa trước khi cho lô … | COVERED | T-004, T-015, T-043 · test_m3_traceability, test_gd3_logistics | Cổng PHI theo từng thửa, hoàn thiện ở T-043 (kế thừa FLD-17 của SRS). |
| FLD-17 | Tính và hiển thị hạn được phép thu hoạch của thửa bằng giá trị lớn nhất của thời điểm từng lần … | COVERED | T-004, T-015, T-043 · test_m3_traceability, test_gd3_logistics | safe_harvest_date = max(áp dụng + PHI); thiếu PHI → chặn + CONDITIONAL_LAB_TEST_REQUIRED (T-043). |
| FLD-18 | Ứng dụng hiện trường thực hiện được kiểm tra tại FLD-15 và FLD-16 khi mất mạng, bằng danh mục v… | PARTIAL | T-004, T-015, T-043 · test_m3_traceability, test_gd3_logistics |  |
| FLD-19 | Quản lý tồn kho vật tư đầu vào theo lô và hạn dùng; đối chiếu lượng xuất kho với lượng ghi tron… | NOT_STARTED | T-004, T-015, T-043 · test_m3_traceability, test_gd3_logistics | Có đăng ký lô vật tư; quản lý tồn kho/xuất kho/đối chiếu chưa có. |
| FLD-20 | Báo cáo tuân thủ canh tác: số lần cảnh báo theo loại, số lần phê duyệt ngoại lệ, số thửa chưa đ… | NOT_STARTED | T-004, T-015, T-043 · test_m3_traceability, test_gd3_logistics | Dữ liệu cảnh báo PHI có ở mục nhật ký PHI; báo cáo tuân thủ chuyên dụng chưa có. |

## LOT — Lô, đóng gói, vận chuyển, thu hồi

| Mã | Yêu cầu (rút gọn) | Trạng thái | Bằng chứng (task · test) | Ghi chú |
|---|---|---|---|---|
| LOT-01 | Tạo lô thu hoạch từ vùng/cây/mùa vụ; ghi ngày, sản lượng, người thực hiện và tiêu chí chất lượn… | COVERED | T-015, T-016, T-017, T-043 · test_m3_traceability, test_m4_packing, test_gd3_logistics | Kèm cổng PHI + cổng khối lượng theo mùa vụ. |
| LOT-02 | Hỗ trợ tách, gộp và chuyển đổi lô; lưu quan hệ cha-con và tỷ lệ/số lượng. | PARTIAL | T-015, T-016, T-017, T-043 · test_m3_traceability, test_m4_packing, test_gd3_logistics | Bảng lot_relations có trong schema; luồng tách/gộp lô chưa có API/UI. |
| LOT-03 | Nhập kho, chuyển kho, xuất kho, hao hụt và kiểm kê theo lô. | NOT_STARTED | T-015, T-016, T-017, T-043 · test_m3_traceability, test_m4_packing, test_gd3_logistics |  |
| LOT-04 | Gắn dữ liệu nhiệt độ/độ ẩm kho theo thời gian lưu lô. | NOT_STARTED | T-015, T-016, T-017, T-043 · test_m3_traceability, test_m4_packing, test_gd3_logistics |  |
| LOT-05 | Tạo mẻ chế biến/đóng gói từ một hoặc nhiều lô nguyên liệu. | COVERED | T-015, T-016, T-017, T-043 · test_m3_traceability, test_m4_packing, test_gd3_logistics | Mẻ đóng gói từ nhiều lô thu hoạch (quan hệ N-N, chặn phân bổ vượt). |
| LOT-06 | Quản lý sản phẩm/SKU, đơn vị, quy cách, GTIN tùy chọn và nội dung công khai. | COVERED | T-015, T-016, T-017, T-043 · test_m3_traceability, test_m4_packing, test_gd3_logistics | SKU/GTIN/SSCC + kiểm chứng GS1 đầy đủ (T-047). |
| LOT-07 | Tạo lô thành phẩm, ngày sản xuất, hạn dùng, số lượng và trạng thái phát hành. | PARTIAL | T-015, T-016, T-017, T-043 · test_m3_traceability, test_m4_packing, test_gd3_logistics | Ngày sản xuất/hạn dùng/số lượng có; trạng thái phát hành đã cắt theo 33 bảng ở T-034. |
| LOT-08 | Quản lý đóng gói, kiện/thùng và SSCC tùy chọn. | COVERED | T-015, T-016, T-017, T-043 · test_m3_traceability, test_m4_packing, test_gd3_logistics |  |
| LOT-09 | Ghi nhận giao nhận/vận chuyển: nguồn, đích, phương tiện, thời gian và người nhận. | COVERED | T-015, T-016, T-017, T-043 · test_m3_traceability, test_m4_packing, test_gd3_logistics | Chuyến vận chuyển theo Bảng 28 (T-043). |
| LOT-10 | Chức năng truy tìm và khoanh vùng lô bị ảnh hưởng để hỗ trợ thu hồi. | PARTIAL | T-015, T-016, T-017, T-043 · test_m3_traceability, test_m4_packing, test_gd3_logistics | Có hồ sơ thu hồi + chuỗi truy vết; truy vấn khoanh vùng tự động chưa có. |
| LOT-11 | Gán thị trường xuất khẩu đích cho lô thành phẩm hoặc cho phiếu xuất; kiểm tra điều kiện xuất th… | PARTIAL | T-015, T-016, T-017, T-043 · test_m3_traceability, test_m4_packing, test_gd3_logistics | Thị trường gán ở cấp vùng; gán cho lô/phiếu xuất + kiểm tra điều kiện xuất chưa có. |
| LOT-12 | Chặn xuất lô có nguồn gốc từ thửa đã sử dụng hoạt chất bị hạn chế tại thị trường đích, hoặc lô … | NOT_STARTED | T-015, T-016, T-017, T-043 · test_m3_traceability, test_m4_packing, test_gd3_logistics | Điều kiện dữ liệu đã có (phê duyệt thị trường + PHI); cổng chặn xuất theo lô chưa có. |
| LOT-13 | Quản lý kết quả kiểm nghiệm theo lô: chỉ tiêu, kết quả, ngưỡng cho phép, đơn vị kiểm nghiệm, số… | PARTIAL | T-015, T-016, T-017, T-043 · test_m3_traceability, test_m4_packing, test_gd3_logistics | Chi tiết xét nghiệm dư lượng có cờ vượt MRL tự sinh; liên kết trực tiếp theo lô còn gián tiếp qua giám sát. |
| LOT-14 | Cảnh báo vi phạm điều kiện bảo quản của lô dựa trên dữ liệu cảm biến kho: thời gian và mức độ v… | NOT_STARTED | T-015, T-016, T-017, T-043 · test_m3_traceability, test_m4_packing, test_gd3_logistics |  |
| LOT-15 | Quy trình thu hồi: lập hồ sơ thu hồi từ một tem hoặc một lô, xác định phạm vi lô và khách hàng … | PARTIAL | T-015, T-016, T-017, T-043 · test_m3_traceability, test_m4_packing, test_gd3_logistics | Hồ sơ thu hồi có số lượng chưa thu hồi tự sinh + phương án xử lý; phạm vi khách hàng/thông báo chưa có. |
| LOT-16 | Quản lý khiếu nại từ khách hàng và từ người tiêu dùng qua trang truy xuất: liên kết lô, phân lo… | NOT_STARTED | T-015, T-016, T-017, T-043 · test_m3_traceability, test_m4_packing, test_gd3_logistics | Chưa có trang công khai để tiếp nhận khiếu nại. |
| LOT-17 | Chốt và khóa dữ liệu lô sau khi phát hành hoặc xuất hàng; sửa đổi sau đó phải có phê duyệt, ghi… | NOT_STARTED | T-015, T-016, T-017, T-043 · test_m3_traceability, test_m4_packing, test_gd3_logistics | Có audit snapshot mọi thay đổi; khóa lô + duyệt sửa sau phát hành chưa có. |

## TRC — Truy xuất & mã GS1

| Mã | Yêu cầu (rút gọn) | Trạng thái | Bằng chứng (task · test) | Ghi chú |
|---|---|---|---|---|
| TRC-01 | Quản lý GLN địa điểm, GTIN sản phẩm, mã lô/batch và SSCC tùy chọn. | PARTIAL | T-016, T-017, T-047 · test_m4_packing, test_cleanup_t047 | GTIN/SSCC/lô có; GLN không dùng — định danh địa điểm bằng PUC/PHC theo TT 02/2024. |
| TRC-02 | Kiểm tra cấu trúc/check digit đối với mã GS1 do người dùng nhập. | COVERED | T-016, T-017, T-047 · test_m4_packing, test_cleanup_t047 | Độ dài 8/12/13/14 + số kiểm tra mod-10 (T-047). |
| TRC-03 | Sinh QR theo GS1 Digital Link hoặc URL truy xuất tương thích. | NOT_STARTED | T-016, T-017, T-047 · test_m4_packing, test_cleanup_t047 | Mã truy xuất dạng chuỗi nối theo TT 02/2024; QR/GS1 Digital Link chưa sinh. |
| TRC-04 | Sinh đơn lẻ và hàng loạt; xuất PDF/PNG và dữ liệu in tem. Template phải quản lý X-dimension/qui… | NOT_STARTED | T-016, T-017, T-047 · test_m4_packing, test_cleanup_t047 | Cấp mã + chuỗi CTE có; trang công khai/QR/EPCIS chưa có. |
| TRC-05 | Cấu hình nội dung công khai theo tenant/sản phẩm/lô; tách dữ liệu nội bộ. | PARTIAL | T-016, T-017, T-047 · test_m4_packing, test_cleanup_t047 | Bản ghi mang đủ 10 trường công khai TT 02/2024; cấu hình nội dung công khai theo tenant chưa có. |
| TRC-06 | Trang truy xuất responsive, tải nhanh, có logo/thông tin liên hệ và hành vi vòng đời rõ ràng kh… | NOT_STARTED | T-016, T-017, T-047 · test_m4_packing, test_cleanup_t047 | Chưa có trang truy xuất công khai (cả TRC-06/07/08/14/16/17 phụ thuộc trang này). |
| TRC-07 | Hiển thị sản phẩm, lô, vùng, dòng thời gian, hồ sơ công bố và trạng thái xác minh. | NOT_STARTED | T-016, T-017, T-047 · test_m4_packing, test_cleanup_t047 | Chi tiết nội bộ có trong app; trang công khai chưa có. |
| TRC-08 | Ghi nhật ký quét ở mức tối thiểu: thời gian, mã, referrer và vùng địa lý thô nếu được phép. | NOT_STARTED | T-016, T-017, T-047 · test_m4_packing, test_cleanup_t047 | Cấp mã + chuỗi CTE có; trang công khai/QR/EPCIS chưa có. |
| TRC-09 | Hỗ trợ vô hiệu hóa/thu hồi mã và thông báo trạng thái rõ ràng. | PARTIAL | T-016, T-017, T-047 · test_m4_packing, test_cleanup_t047 | Có hồ sơ thu hồi; vô hiệu hóa từng mã chưa có. |
| TRC-10 | Mô hình sự kiện tương thích GS1 EPCIS 2.0.1 và CBV 2.0.0 ở mức dữ liệu. | PARTIAL | T-016, T-017, T-047 · test_m4_packing, test_cleanup_t047 | Mô hình CTE tương thích về ý nghĩa; chưa serial hóa EPCIS 2.0/CBV. |
| TRC-11 | Xuất dữ liệu sự kiện theo JSON/CSV; endpoint capture/query EPCIS là tùy chọn. | NOT_STARTED | T-016, T-017, T-047 · test_m4_packing, test_cleanup_t047 | Chưa có endpoint xuất JSON/CSV. |
| TRC-12 | Không tự nhận hệ thống hoặc sản phẩm được GS1/TCVN chứng nhận khi chưa có xác nhận. | COVERED | T-016, T-017, T-047 · test_m4_packing, test_cleanup_t047 | Điều cấm về tuyên bố: sản phẩm/tài liệu không tự nhận chứng nhận GS1/TCVN. |
| TRC-13 | Cơ chế chống làm giả: mã kích hoạt hoặc mã ẩn dưới lớp phủ; tem chưa kích hoạt khi bị tra cứu h… | NOT_STARTED | T-016, T-017, T-047 · test_m4_packing, test_cleanup_t047 | Cấp mã + chuỗi CTE có; trang công khai/QR/EPCIS chưa có. |
| TRC-14 | Phát hiện tra cứu bất thường: một tem vượt số lần tra cứu cấu hình được, hoặc bị tra cứu từ nhi… | NOT_STARTED | T-016, T-017, T-047 · test_m4_packing, test_cleanup_t047 | Cấp mã + chuỗi CTE có; trang công khai/QR/EPCIS chưa có. |
| TRC-15 | Truy vết ngược từ tem hoặc lô về thửa và cây đầu dòng; truy vết xuôi từ một thửa hoặc một lần s… | PARTIAL | T-016, T-017, T-047 · test_m4_packing, test_cleanup_t047 | Chuỗi dữ liệu truy ngược/xuôi đủ đầu-cuối; chưa có truy vấn truy vết chuyên dụng. |
| TRC-16 | Kết xuất bộ dữ liệu và báo cáo phục vụ lập hồ sơ công bố hợp chuẩn TCVN 12850:2019: kiểm tra tí… | NOT_STARTED | T-016, T-017, T-047 · test_m4_packing, test_cleanup_t047 | Cấp mã + chuỗi CTE có; trang công khai/QR/EPCIS chưa có. |
| TRC-17 | Trang truy xuất công khai hỗ trợ tiếng Việt và tiếng Anh; bổ sung ngôn ngữ khác bằng cấu hình. | NOT_STARTED | T-016, T-017, T-047 · test_m4_packing, test_cleanup_t047 | Giao diện hiện chỉ tiếng Việt; trang công khai chưa có. |

## IOT — IoT

| Mã | Yêu cầu (rút gọn) | Trạng thái | Bằng chứng (task · test) | Ghi chú |
|---|---|---|---|---|
| IOT-01 | Đăng ký thiết bị với loại, model, serial, DevEUI, AppEUI/JoinEUI, vị trí và trạng thái. | PARTIAL | T-045, T-046 · test_iot | Đăng ký thiết bị: loại/vùng/thửa/firmware; model/serial/DevEUI chưa có. |
| IOT-02 | Provision thiết bị LoRaWAN bằng OTAA; quản lý khóa an toàn. | PARTIAL | T-045, T-046 · test_iot | Khóa riêng từng thiết bị + xoay vòng/thu hồi (T-046) cho kênh HTTPS; OTAA LoRaWAN chưa có. |
| IOT-03 | Tiếp nhận payload từ LoRaWAN Network Server qua MQTT/HTTP. | PARTIAL | T-045, T-046 · test_iot | Nhận qua HTTPS POST; MQTT/LoRaWAN Network Server chưa có. |
| IOT-04 | Codec payload có phiên bản theo model/firmware và kiểm thử tự động. | NOT_STARTED | T-045, T-046 · test_iot | Nền ingest + khóa thiết bị có; LoRaWAN/codec/cảnh báo chưa có. |
| IOT-05 | Chuẩn hóa đại lượng, đơn vị, thời gian, chất lượng dữ liệu và nguồn thiết bị. | PARTIAL | T-045, T-046 · test_iot | Số đo rơi thẳng vào Bảng 19/20 đã chuẩn hóa; lớp chuẩn hóa tổng quát chưa có. |
| IOT-06 | Lưu cả dữ liệu thô và dữ liệu chuẩn hóa; không ghi đè dữ liệu thô. | NOT_STARTED | T-045, T-046 · test_iot | Nền ingest + khóa thiết bị có; LoRaWAN/codec/cảnh báo chưa có. |
| IOT-07 | Cấu hình chu kỳ gửi, ngưỡng cảnh báo, hysteresis và số lần vượt liên tiếp. | NOT_STARTED | T-045, T-046 · test_iot | Nền ingest + khóa thiết bị có; LoRaWAN/codec/cảnh báo chưa có. |
| IOT-08 | Cảnh báo mất kết nối, pin thấp, dữ liệu ngoài miền, sai thời gian và bản tin trùng. | NOT_STARTED | T-045, T-046 · test_iot | Nền ingest + khóa thiết bị có; LoRaWAN/codec/cảnh báo chưa có. |
| IOT-09 | Gửi cảnh báo qua web/app/email; SMS/Zalo là tùy chọn tách giá. | NOT_STARTED | T-045, T-046 · test_iot | Nền ingest + khóa thiết bị có; LoRaWAN/codec/cảnh báo chưa có. |
| IOT-10 | Theo dõi RSSI, SNR, pin, firmware, bản tin cuối và tỷ lệ thành công. | NOT_STARTED | T-045, T-046 · test_iot | Nền ingest + khóa thiết bị có; LoRaWAN/codec/cảnh báo chưa có. |
| IOT-11 | Hỗ trợ dữ liệu đến muộn và gửi bù; giữ timestamp đo gốc. | PARTIAL | T-045, T-046 · test_iot | Giữ measured_at gốc của thiết bị khi ingest. |
| IOT-12 | Tổng hợp 10 phút/giờ/ngày với min, max, avg, sum phù hợp từng đại lượng. | NOT_STARTED | T-045, T-046 · test_iot | Nền ingest + khóa thiết bị có; LoRaWAN/codec/cảnh báo chưa có. |
| IOT-13 | Biểu đồ theo thiết bị, đại lượng, site/zone và khoảng thời gian; xuất CSV. | NOT_STARTED | T-045, T-046 · test_iot | Nền ingest + khóa thiết bị có; LoRaWAN/codec/cảnh báo chưa có. |
| IOT-14 | Quản lý ngày/hệ số/chứng từ hiệu chuẩn và lịch hiệu chuẩn kế tiếp dựa trên model, khuyến cáo hã… | NOT_STARTED | T-045, T-046 · test_iot | Nền ingest + khóa thiết bị có; LoRaWAN/codec/cảnh báo chưa có. |
| IOT-15 | Core phải có command/actuation framework để Vertical Pack tương lai có thể điều khiển thiết bị/… | NOT_STARTED | T-045, T-046 · test_iot | Nền ingest + khóa thiết bị có; LoRaWAN/codec/cảnh báo chưa có. |

## MOB — Ứng dụng di động

| Mã | Yêu cầu (rút gọn) | Trạng thái | Bằng chứng (task · test) | Ghi chú |
|---|---|---|---|---|
| MOB-01 | Ứng dụng Android cho PDA/điện thoại; đăng nhập và tải dữ liệu được phân quyền. Min runtime Andr… | NOT_STARTED | — | Chưa có ứng dụng Android; web responsive đang thay thế — chờ quyết định Owner (F3/T-048). |
| MOB-02 | Offline-first: tải trước danh mục, lưu cục bộ mã hóa và đồng bộ khi có mạng. | NOT_STARTED | — | Chưa có ứng dụng Android; web responsive đang thay thế — chờ quyết định Owner (F3/T-048). |
| MOB-03 | Quét QR/1D/2D bằng scanner tích hợp hoặc camera. | NOT_STARTED | — | Chưa có ứng dụng Android; web responsive đang thay thế — chờ quyết định Owner (F3/T-048). |
| MOB-04 | Ghi nhật ký, kiểm tra cây/vùng, thu hoạch, nhập kho và giao nhận. | NOT_STARTED | — | Chưa có ứng dụng Android; web responsive đang thay thế — chờ quyết định Owner (F3/T-048). |
| MOB-05 | Chụp ảnh, nén ảnh, ghi GPS, thời gian và người dùng; lưu device-reported location accuracy/sour… | NOT_STARTED | — | Chưa có ứng dụng Android; web responsive đang thay thế — chờ quyết định Owner (F3/T-048). |
| MOB-06 | Hiển thị bản đồ, danh sách công việc và dữ liệu cảm biến gần nhất. | NOT_STARTED | — | Chưa có ứng dụng Android; web responsive đang thay thế — chờ quyết định Owner (F3/T-048). |
| MOB-07 | Hàng đợi đồng bộ, trạng thái từng bản ghi và cơ chế thử lại. | NOT_STARTED | — | Chưa có ứng dụng Android; web responsive đang thay thế — chờ quyết định Owner (F3/T-048). |
| MOB-08 | Quy tắc xử lý xung đột; không âm thầm ghi đè bản ghi đã sửa trên server. | NOT_STARTED | — | Chưa có ứng dụng Android; web responsive đang thay thế — chờ quyết định Owner (F3/T-048). |
| MOB-09 | Thu hồi phiên/quyền máy chủ ngay khi tài khoản bị khóa; quyền ngoại tuyến dùng lease tối đa 24 … | PARTIAL | — | Khóa/thu hồi tài khoản chặn ghi ngay ở server (T-031); lease ngoại tuyến 24h chưa có vì chưa có app. |
| MOB-10 | Nhật ký lỗi có thể gửi về hệ thống sau khi được người dùng xác nhận. | NOT_STARTED | — | Chưa có ứng dụng Android; web responsive đang thay thế — chờ quyết định Owner (F3/T-048). |
| MOB-11 | Tự động cập nhật có kiểm soát hoặc cung cấp quy trình phát hành APK nội bộ. | NOT_STARTED | — | Chưa có ứng dụng Android; web responsive đang thay thế — chờ quyết định Owner (F3/T-048). |
| MOB-12 | Giao diện tiếng Việt; cỡ chữ và nút phù hợp thao tác bằng găng tay. | NOT_STARTED | — | Chưa có ứng dụng Android; web responsive đang thay thế — chờ quyết định Owner (F3/T-048). |
| MOB-13 | Không bắt buộc ứng dụng iOS trong giai đoạn này. | COVERED | — | Điều khoản loại trừ: không yêu cầu iOS trong giai đoạn này. |

## AIX — AI Gateway

| Mã | Yêu cầu (rút gọn) | Trạng thái | Bằng chứng (task · test) | Ghi chú |
|---|---|---|---|---|
| AIX-01 | AI Gateway tách provider/model khỏi Core; thay provider/model qua cấu hình/adapter, không sửa n… | NOT_STARTED | — | Thuộc M7 (D-51) — chưa tới mốc. |
| AIX-02 | Mọi inference lưu provider, model, version, request/input reference, timestamp, confidence/scor… | NOT_STARTED | — | Thuộc M7 (D-51) — chưa tới mốc. |
| AIX-03 | Hỗ trợ use case phân tích ảnh sâu/bệnh hoặc bất thường ở mức framework: ảnh, inference, top can… | NOT_STARTED | — | Thuộc M7 (D-51) — chưa tới mốc. |
| AIX-04 | Hỗ trợ anomaly/advisory từ Current State, Event Ledger và IoT theo quyền; output phải dẫn nguồn… | NOT_STARTED | — | Thuộc M7 (D-51) — chưa tới mốc. |
| AIX-05 | Khi inference có thể tạo Observation/DiseaseCase/Activity, phải qua human confirmation hoặc wor… | NOT_STARTED | — | Thuộc M7 (D-51) — chưa tới mốc. |
| AIX-06 | Không cho AI tự phê duyệt ngoại lệ pháp lý, tiêu chuẩn bắt buộc, tiêu hủy, chứng nhận hoặc quyế… | NOT_STARTED | — | Thuộc M7 (D-51) — chưa tới mốc. |
| AIX-07 | Entitlement/quota AI theo tenant/Producer/user/use-case; metering idempotent theo request/ảnh/t… | NOT_STARTED | — | Thuộc M7 (D-51) — chưa tới mốc. |
| AIX-08 | Dữ liệu gửi provider ngoài phải tuân policy dữ liệu cá nhân/bí mật kinh doanh; hỗ trợ redaction… | NOT_STARTED | — | Thuộc M7 (D-51) — chưa tới mốc. |
| AIX-09 | Hệ thống degrade gracefully khi AI lỗi/hết quota; workflow nghiệp vụ cốt lõi vẫn hoạt động. | NOT_STARTED | — | Thuộc M7 (D-51) — chưa tới mốc. |
| AIX-10 | Feedback người dùng/chuyên gia về inference được lưu để đánh giá chất lượng nhưng không tự dùng… | NOT_STARTED | — | Thuộc M7 (D-51) — chưa tới mốc. |

## LFC — Vòng đời & Event Ledger

| Mã | Yêu cầu (rút gọn) | Trạng thái | Bằng chứng (task · test) | Ghi chú |
|---|---|---|---|---|
| LFC-01 | Subject hỗ trợ Individual, Group, Cohort, Population và AreaBasedAsset; type mở rộng qua Vertic… | PARTIAL | T-042 · test_gd3_monitoring | Đơn vị chăn nuôi theo cá thể/đàn (Bảng 14) + đơn vị không gian; mô hình Subject hợp nhất chưa có. |
| LFC-02 | Một Subject/Cohort gắn Producer, Site/ProductionUnit, loài/giống/dòng và trạng thái vòng đời. | PARTIAL | T-042 · test_gd3_monitoring | Đơn vị chăn nuôi gắn cơ sở + trạng thái vòng đời. |
| LFC-03 | ProductionCycle quản lý vụ/lứa/chu kỳ sản xuất-sinh trưởng-nuôi-khai thác, ngày bắt đầu-kết thú… | COVERED | T-042 · test_gd3_monitoring | Chu kỳ sản xuất = mùa vụ (Bảng 15) dùng chung đa ngành. |
| LFC-04 | Event Ledger ghi event_id, event_type, occurred_at, recorded_at, actor, subject/cycle, quantity… | PARTIAL | T-042 · test_gd3_monitoring | Nhật ký + audit là sổ sự kiện dạng đơn giản; event lượng thay đổi (quantity delta) chưa có. |
| LFC-05 | Các event biến động số lượng tối thiểu: opening/import/birth/addition, mortality, culling, tran… | NOT_STARTED | T-042 · test_gd3_monitoring | Đơn vị chăn nuôi có; Event Ledger/Current State projection chưa có. |
| LFC-06 | Current State projection được tính/đối soát từ Event Ledger; có snapshot/version và rebuild. | NOT_STARTED | T-042 · test_gd3_monitoring | Đơn vị chăn nuôi có; Event Ledger/Current State projection chưa có. |
| LFC-07 | Không cho Current State âm hoặc vượt ràng buộc sinh học/nghiệp vụ được cấu hình; ngoại lệ phải … | PARTIAL | T-042 · test_gd3_monitoring | Các cổng khối lượng/PHI chặn trạng thái âm/vượt ở điểm nghiệp vụ chính. |
| LFC-08 | Mortality event lưu số lượng, nguyên nhân biết/nghi ngờ, triệu chứng/health case liên quan, các… | NOT_STARTED | T-042 · test_gd3_monitoring | Đơn vị chăn nuôi có; Event Ledger/Current State projection chưa có. |
| LFC-09 | Hỗ trợ membership Group↔Individual khi ngành cần quản lý từng cá thể trong đàn/nhóm. Chuyển mem… | NOT_STARTED | T-042 · test_gd3_monitoring | Đơn vị chăn nuôi có; Event Ledger/Current State projection chưa có. |
| LFC-10 | Hỗ trợ area/quantity state cho cây trồng, rừng và thủy sản theo đơn vị phù hợp; không áp một đơ… | PARTIAL | T-042 · test_gd3_monitoring | Trạng thái theo diện tích/số đầu/sản lượng tùy ngành có trong mô hình dữ liệu. |
| LFC-11 | Activity/Observation không làm thay đổi quantity nếu không khai báo effect; event effect phải d… | PARTIAL | T-042 · test_gd3_monitoring | Sự kiện và số lượng tách riêng theo thiết kế; hiệu ứng xác định ở các cổng. |
| LFC-12 | Đóng/mở lại cycle, merge/split cohort hoặc chuyển ProductionUnit phải có rule, approval khi cần… | PARTIAL | T-042 · test_gd3_monitoring | Đổi trạng thái chu kỳ có audit; merge/split cohort chưa có. |
| LFC-13 | Dashboard Current State hiển thị số hiện tại và giải thích được từ các event chính; hỗ trợ snap… | PARTIAL | T-042 · test_gd3_monitoring | Dashboard + báo cáo hiện trạng có; giải thích từ sự kiện/snapshot theo ngày chưa có. |

## BLC — Toàn vẹn dữ liệu / blockchain

| Mã | Yêu cầu (rút gọn) | Trạng thái | Bằng chứng (task · test) | Ghi chú |
|---|---|---|---|---|
| BLC-01 | Canonicalize event envelope theo RFC 8785 JCS (baseline) hoặc cơ chế tương đương được IAICT phê… | NOT_STARTED | — | = D-10 — chưa xây (đã khuyến nghị ở T-048). |
| BLC-02 | Gom event hash thành Merkle root theo lô/ngày bằng quy tắc deterministic đã tài liệu hóa: leaf … | NOT_STARTED | — | = D-10 — chưa xây (đã khuyến nghị ở T-048). |
| BLC-03 | Nếu sử dụng blockchain anchoring, hồ sơ kỹ thuật/giá phải nêu đích danh 01 mạng chính để làm cơ… | NOT_STARTED | — | = D-10 — chưa xây (đã khuyến nghị ở T-048). |
| BLC-04 | Khi dùng blockchain, adapter phải tách rời để thay mạng/cơ chế anchoring mà không sửa nghiệp vụ… | NOT_STARTED | — | = D-10 — chưa xây (đã khuyến nghị ở T-048). |
| BLC-05 | Nếu ghi on-chain, tuyệt đối không ghi dữ liệu cá nhân, tài liệu, bí mật kinh doanh hoặc cảm biế… | NOT_STARTED | — | = D-10 — chưa xây (đã khuyến nghị ở T-048). |
| BLC-06 | Trang/công cụ xác minh cho biết bằng chứng toàn vẹn hợp lệ/không hợp lệ, thời điểm tạo/chốt bằn… | NOT_STARTED | — | = D-10 — chưa xây (đã khuyến nghị ở T-048). |
| BLC-07 | Khóa ký Data Integrity phải lưu bằng secret store/KMS. Nếu dùng blockchain, ví/account producti… | NOT_STARTED | — | = D-10 — chưa xây (đã khuyến nghị ở T-048). |
| BLC-08 | Nếu dùng blockchain, không yêu cầu người dùng sở hữu ví/tiền mã hóa; hệ thống quản lý service a… | NOT_STARTED | — | = D-10 — chưa xây (đã khuyến nghị ở T-048). |
| BLC-09 | Nếu dùng blockchain, hồ sơ mạng chính phải nêu tên mạng, chain ID, mainnet/L2, native token, RP… | NOT_STARTED | — | = D-10 — chưa xây (đã khuyến nghị ở T-048). |

## HLT — Sức khỏe & dịch tễ

| Mã | Yêu cầu (rút gọn) | Trạng thái | Bằng chứng (task · test) | Ghi chú |
|---|---|---|---|---|
| HLT-01 | Ghi HealthObservation theo subject/cohort/cycle: tình trạng, triệu chứng, chỉ số, ảnh/tệp, vị t… | PARTIAL | T-042 · test_gd3_monitoring | Khai báo giám sát + giám sát trước thu hoạch ghi quan sát tuân thủ. |
| HLT-02 | Tạo DiseaseCase từ quan sát hoặc khai báo; lưu suspected/confirmed/rejected, disease code, onse… | NOT_STARTED | T-042 · test_gd3_monitoring | Giám sát/xét nghiệm có một phần; ca bệnh/dịch tễ chưa có. |
| HLT-03 | Quản lý Sample/LabResult: mã mẫu, loại, ngày lấy, nơi xét nghiệm, chỉ tiêu, kết quả, tệp và liê… | PARTIAL | T-042 · test_gd3_monitoring | Kết quả xét nghiệm nước/dư lượng có; mẫu gắn ca bệnh chưa có. |
| HLT-04 | Quản lý Vaccination/Prevention theo cohort/individual: vaccine/chế phẩm, lô, liều, người thực h… | NOT_STARTED | T-042 · test_gd3_monitoring | Giám sát/xét nghiệm có một phần; ca bệnh/dịch tễ chưa có. |
| HLT-05 | Quản lý Treatment: thuốc/chế phẩm, liều, thời gian, người thực hiện, thời gian ngừng/cách ly kh… | PARTIAL | T-042 · test_gd3_monitoring | Xử lý thuốc cho cây trồng có kèm PHI; điều trị động vật chưa có. |
| HLT-06 | Mortality/Culling liên kết Event Ledger và DiseaseCase khi có; hỗ trợ nguyên nhân chưa xác định… | NOT_STARTED | T-042 · test_gd3_monitoring | Giám sát/xét nghiệm có một phần; ca bệnh/dịch tễ chưa có. |
| HLT-07 | Tạo Outbreak/Incident sức khỏe với phạm vi địa lý, danh sách Producer/site/cohort liên quan, th… | NOT_STARTED | T-042 · test_gd3_monitoring | Giám sát/xét nghiệm có một phần; ca bệnh/dịch tễ chưa có. |
| HLT-08 | Quản lý BiosecurityAction: cách ly, vệ sinh/tiêu độc, kiểm soát ra vào, khoanh vùng, tiêu hủy h… | NOT_STARTED | T-042 · test_gd3_monitoring | Giám sát/xét nghiệm có một phần; ca bệnh/dịch tễ chưa có. |
| HLT-09 | Rule cảnh báo tỷ lệ chết/số ca bất thường theo cửa sổ thời gian và baseline cấu hình. | NOT_STARTED | T-042 · test_gd3_monitoring | Giám sát/xét nghiệm có một phần; ca bệnh/dịch tễ chưa có. |
| HLT-10 | Tổng hợp dịch bệnh/sức khỏe theo địa giới và Producer mà vẫn tôn trọng quyền truy cập dữ liệu c… | NOT_STARTED | T-042 · test_gd3_monitoring | Giám sát/xét nghiệm có một phần; ca bệnh/dịch tễ chưa có. |
| HLT-11 | Shared Engine không hard-code tên bệnh; disease/symptom/action catalog nằm trong Vertical Pack/… | PARTIAL | T-042 · test_gd3_monitoring | Engine không hard-code tên bệnh; danh mục qua khai báo/giám sát. |
| HLT-12 | Hệ thống hỗ trợ quy trình khai báo→xác minh→lấy mẫu→kết quả→xử lý→theo dõi→kết thúc; pack có th… | PARTIAL | T-042 · test_gd3_monitoring | Quy trình khai báo → kết luận giám sát có một phần; vòng đời ca bệnh đầy đủ chưa có. |

## PRO — Chủ thể & địa giới

| Mã | Yêu cầu (rút gọn) | Trạng thái | Bằng chứng (task · test) | Ghi chú |
|---|---|---|---|---|
| PRO-01 | Quản lý AdministrativeUnit có mã, tên, loại, cha-con, thời gian hiệu lực và trạng thái; không h… | COVERED | T-015, T-040 · test_gd3_refs, test_m3_traceability | Cây đơn vị hành chính tự tham chiếu, không hard-code số cấp (Bảng 1). |
| PRO-02 | Cho phép ánh xạ tenant/OrganizationUnit với một hoặc nhiều AdministrativeUnit mà vẫn giữ hai kh… | PARTIAL | T-015, T-040 · test_gd3_refs, test_m3_traceability | Vùng gắn mã xã quản lý; khái niệm OrganizationUnit độc lập chưa có. |
| PRO-03 | Quản lý Producer/Operator: hộ, cá nhân, trang trại, HTX, tổ hợp tác, doanh nghiệp, ban quản lý,… | COVERED | T-015, T-040 · test_gd3_refs, test_m3_traceability | Chủ thể đủ loại hình theo Bảng 6 (hộ/cá nhân/trang trại/HTX/doanh nghiệp/cơ sở). |
| PRO-04 | Một Producer có nhiều Site, ProductionUnit, ngành/Vertical Pack, đàn/lứa/vụ cùng lúc. | PARTIAL | T-015, T-040 · test_gd3_refs, test_m3_traceability | Chủ thể liên kết được nhiều vùng/đơn vị/chu kỳ qua các quan hệ hiện có. |
| PRO-05 | Quản lý quan hệ Producer với HTX/doanh nghiệp liên kết, chủ sở hữu, đơn vị vận hành, cán bộ phụ… | PARTIAL | T-015, T-040 · test_gd3_refs, test_m3_traceability | Có quan hệ cha-con (parent_code); loại quan hệ liên kết/đơn vị vận hành/cán bộ phụ trách chưa có. |
| PRO-06 | Phân quyền theo subtree địa giới, OrganizationUnit, Producer group và Site/ProductionUnit. | NOT_STARTED | T-015, T-040 · test_gd3_refs, test_m3_traceability | Phân quyền hiện phẳng theo tenant + vai trò. |
| PRO-07 | Import/export Producer và mapping địa giới bằng CSV/XLSX/API; có dedup/matching và báo cáo lỗi. | NOT_STARTED | T-015, T-040 · test_gd3_refs, test_m3_traceability |  |
| PRO-08 | Không bắt buộc Producer là tenant; Producer có thể có account/role riêng trong tenant và cổng s… | PARTIAL | T-015, T-040 · test_gd3_refs, test_m3_traceability | User liên kết chủ thể (linked_actor_code) có; cổng tự phục vụ cho Producer chưa có. |
| PRO-09 | Cho phép Producer tự khai báo có kiểm soát và cán bộ xác minh/phê duyệt theo workflow. | NOT_STARTED | T-015, T-040 · test_gd3_refs, test_m3_traceability | Có khai báo giám sát; quy trình Producer tự khai + cán bộ duyệt chưa có. |
| PRO-10 | Cho phép tổng hợp chỉ tiêu theo tenant, AdministrativeUnit, Producer type, Vertical Pack và thờ… | PARTIAL | T-015, T-040 · test_gd3_refs, test_m3_traceability | Báo cáo tổng hợp theo vùng có; tổng hợp theo địa giới/loại chủ thể chưa có. |

## CRM — CRM

| Mã | Yêu cầu (rút gọn) | Trạng thái | Bằng chứng (task · test) | Ghi chú |
|---|---|---|---|---|
| CRM-01 | Customer/Account trong CRM phải reuse Customer/Payer/BusinessParty hiện có; không tạo master kh… | NOT_STARTED | — | Thuộc M7 (D-54) — chưa tới mốc. |
| CRM-02 | Quản lý Contact: họ tên, chức vụ, kênh liên hệ, organization/account, consent/nguồn và vai trò … | NOT_STARTED | — | Thuộc M7 (D-54) — chưa tới mốc. |
| CRM-03 | Lead có nguồn, nhu cầu, địa bàn, vertical/service quan tâm, owner, trạng thái, qualification và… | NOT_STARTED | — | Thuộc M7 (D-54) — chưa tới mốc. |
| CRM-04 | Opportunity có pipeline/stage, giá trị dự kiến, xác suất, expected close date, payer/beneficiar… | NOT_STARTED | — | Thuộc M7 (D-54) — chưa tới mốc. |
| CRM-05 | Activity/Task cho call/email/meeting/follow-up, due date, owner, reminder, liên kết lead/opport… | NOT_STARTED | — | Thuộc M7 (D-54) — chưa tới mốc. |
| CRM-06 | Quote tạo từ Commercial Service Catalog/Price Book: plan, add-on, quota, managed service, white… | NOT_STARTED | — | Thuộc M7 (D-54) — chưa tới mốc. |
| CRM-07 | Workflow phê duyệt Quote/discount theo threshold/role; exception bắt buộc lý do, người duyệt, t… | NOT_STARTED | — | Thuộc M7 (D-54) — chưa tới mốc. |
| CRM-08 | Won Opportunity/Quote được convert sang Contract/Order reference và Subscription/Entitlement bằ… | NOT_STARTED | — | Thuộc M7 (D-54) — chưa tới mốc. |
| CRM-09 | Lost Opportunity bắt buộc lost reason và optional competitor; dashboard win rate/sales cycle/pi… | NOT_STARTED | — | Thuộc M7 (D-54) — chưa tới mốc. |
| CRM-10 | Renewal Opportunity tự sinh từ subscription/contract sắp hết hạn; hỗ trợ upsell/cross-sell/add-… | NOT_STARTED | — | Thuộc M7 (D-54) — chưa tới mốc. |
| CRM-11 | Commercial handoff sau Won tạo checklist onboarding/support/managed-ops; owner và trạng thái gi… | NOT_STARTED | — | Thuộc M7 (D-54) — chưa tới mốc. |
| CRM-12 | CRM Lite cung cấp API/export/event; không yêu cầu marketing automation, call center, social lis… | NOT_STARTED | — | Thuộc M7 (D-54) — chưa tới mốc. |

## MOP — Vận hành ủy thác

| Mã | Yêu cầu (rút gọn) | Trạng thái | Bằng chứng (task · test) | Ghi chú |
|---|---|---|---|---|
| MOP-01 | Managed Service Plan xác định phạm vi IAICT vận hành: onboarding/import, user/role, QR/IoT, con… | NOT_STARTED | — | Managed operations — chưa xây. |
| MOP-02 | DelegatedAdminGrant gồm tenant, operator/user/group, permission set, purpose, contract/order re… | NOT_STARTED | — | Managed operations — chưa xây. |
| MOP-03 | Role IAICT Managed Operator tách Super-admin; chỉ thấy tenant được grant, không mặc định thấy g… | NOT_STARTED | — | Managed operations — chưa xây. |
| MOP-04 | Managed-ops task/checklist/evidence cho thao tác định kỳ/one-off, owner, due date, before/after… | NOT_STARTED | — | Managed operations — chưa xây. |
| MOP-05 | IAICT có thể import/cấu hình thay khách hàng nhưng dữ liệu nghiệp vụ trọng yếu hoặc bulk change… | NOT_STARTED | — | Managed operations — chưa xây. |
| MOP-06 | Monitoring/alerting và Monthly Managed Operations Report gồm availability, incident, ticket, ba… | NOT_STARTED | — | Managed operations — chưa xây. |
| MOP-07 | Support identity theo tenant: hotline/email/helpdesk/SLA/contact tree; ticket từ customer porta… | NOT_STARTED | — | Managed operations — chưa xây. |
| MOP-08 | Baseline hỗ trợ bằng delegated operation với tài khoản người vận hành riêng. Impersonation khôn… | NOT_STARTED | — | Managed operations — chưa xây. |
| MOP-09 | Managed Operations là service có price/quota/SLA/metering riêng; usage/time/task nếu dùng tính … | NOT_STARTED | — | Managed operations — chưa xây. |
| MOP-10 | Kết thúc managed service có handback: export config/data, danh sách access/secret/domain, revok… | NOT_STARTED | — | Managed operations — chưa xây. |

## STD — Tiêu chuẩn & đánh giá tuân thủ

| Mã | Yêu cầu (rút gọn) | Trạng thái | Bằng chứng (task · test) | Ghi chú |
|---|---|---|---|---|
| STD-01 | Quản lý Standard Profile có mã, tên, version, owner/source, phạm vi, thị trường, ngày hiệu lực/… | PARTIAL | T-040, T-041 · test_gd3_refs, test_gd3_market | Danh mục scheme/thị trường có mã + nguồn + phạm vi; vòng đời profile đầy đủ chưa có. |
| STD-02 | Quản lý Criteria theo standard: mã, mô tả, mức bắt buộc/khuyến nghị, trọng số, rule/checklist, … | NOT_STARTED | T-040, T-041 · test_gd3_refs, test_gd3_market | Danh mục + chứng nhận có khung; engine đánh giá chuẩn chưa có. |
| STD-03 | Cho Producer/Site/ProductionCycle/Lot lựa chọn hoặc được gán một/nhiều Standard Profile phù hợp… | PARTIAL | T-040, T-041 · test_gd3_refs, test_gd3_market | Chứng nhận gán cho vùng/cơ sở theo scheme (Bảng 10). |
| STD-04 | Tạo ComplianceAssessment/GAP với trạng thái từng criteria, evidence, người đánh giá, thời gian … | PARTIAL | T-040, T-041 · test_gd3_refs, test_gd3_market | Kết luận giám sát ở mức bản ghi; thực thể đánh giá GAP theo từng tiêu chí chưa có. |
| STD-05 | Quản lý CorrectiveAction cho criteria chưa đạt: owner, deadline, evidence, verification và clos… | NOT_STARTED | T-040, T-041 · test_gd3_refs, test_gd3_market | Danh mục + chứng nhận có khung; engine đánh giá chuẩn chưa có. |
| STD-06 | Rule có thể warn/block/require approval; điều kiện pháp luật/market bắt buộc không được bypass … | PARTIAL | T-040, T-041 · test_gd3_refs, test_gd3_market | Cổng cứng PHI/khối lượng không bypass được; chế độ warn/approve chưa có. |
| STD-07 | Tái sử dụng dữ liệu Activity, InputMaterial, Health, IoT, test/lab và Traceability làm evidence… | PARTIAL | T-040, T-041 · test_gd3_refs, test_gd3_market | Các cổng đã dùng chéo dữ liệu nhật ký/vật tư/xét nghiệm/truy xuất làm bằng chứng. |
| STD-08 | Dashboard hiển thị %/mức hoàn thành, tiêu chí thiếu, bằng chứng thiếu, vi phạm và readiness the… | NOT_STARTED | T-040, T-041 · test_gd3_refs, test_gd3_market | Danh mục + chứng nhận có khung; engine đánh giá chuẩn chưa có. |
| STD-09 | Danh mục standard/criteria phải export/import/version/migrate qua Vertical Pack Framework. | NOT_STARTED | T-040, T-041 · test_gd3_refs, test_gd3_market | Danh mục + chứng nhận có khung; engine đánh giá chuẩn chưa có. |
| STD-10 | Các tiêu chuẩn/điều kiện xuất hiện có của Vertical Pack 01 tiếp tục áp dụng và được ánh xạ vào … | NOT_STARTED | T-040, T-041 · test_gd3_refs, test_gd3_market | Danh mục + chứng nhận có khung; engine đánh giá chuẩn chưa có. |

## COM — Thương mại / subscription / metering

| Mã | Yêu cầu (rút gọn) | Trạng thái | Bằng chứng (task · test) | Ghi chú |
|---|---|---|---|---|
| COM-01 | Quản lý danh mục plan có mã, phiên bản, kỳ hạn, module, hạn mức, retention, SLA và trạng thái p… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-02 | Quản lý subscription theo Customer/Payer và phạm vi tenant/beneficiary với ngày hiệu lực/hết hạ… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-03 | Mô hình hỗ trợ 07 nhãn trạng thái: Draft, Trial, Active, Grace, Read-only, Suspended, Terminate… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-04 | Nhắc hết hạn mặc định 60/30/7 ngày; thời gian ân hạn và read-only cấu hình theo hợp đồng; mọi t… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-05 | Entitlement theo module/dịch vụ và hạn mức tối thiểu: named user, site, thiết bị, QR phát hành,… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-06 | Mỗi hạn mức có soft/hard policy; cảnh báo mặc định 80/90/100%; không tự thu phí hoặc chặn dữ li… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-07 | Metering idempotent theo tenant/beneficiary/module/site/device/kỳ khi áp dụng; lưu nguồn, thời … | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-08 | Chốt sổ sử dụng theo tháng/kỳ; điều chỉnh chỉ bằng bút toán bù có lý do, người duyệt và before/… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-09 | Lưu metadata hợp đồng, order, hóa đơn và trạng thái thanh toán tham chiếu; đính kèm tài liệu th… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-10 | Cổng khách hàng hiển thị plan, kỳ hạn, hạn mức, usage, thông báo, tài liệu/hóa đơn tham chiếu v… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-11 | Dashboard IAICT hiển thị tenant/subscription sắp hết hạn, trạng thái dịch vụ, usage, overage, t… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-12 | Onboarding tenant từ template gồm plan, module, danh mục, role, workflow, branding và dữ liệu m… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-13 | Nâng/hạ plan và add-on có effective date; kiểm tra phụ thuộc, dữ liệu vượt hạn mức và hiển thị … | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-14 | Kết thúc dịch vụ có export đầy đủ, checksum/manifest, thời gian lưu chờ xóa, phê duyệt và xác n… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-15 | Tiếp nhận yêu cầu hỗ trợ từ portal/email với mã ticket, tenant, mức độ, SLA, owner, trao đổi và… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-16 | Feature flag có phạm vi global/plan/tenant, lịch hiệu lực, owner, rollback và audit; flag hết h… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-17 | Quản lý version/release, maintenance window, release note, migration tương thích ngược và thông… | PARTIAL | — | Phiên bản Worker + migration tương thích ngược có; cửa sổ bảo trì/release note/thông báo tenant chưa có. |
| COM-18 | Cung cấp API/webhook versioned cho hệ thống ngoài: CRM bên thứ ba, ERP/kế toán, hóa đơn điện tử… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-19 | Core quản lý sản xuất hoạt động độc lập khi không bật IoT, traceability/QR hoặc AI; capability … | PARTIAL | — | Lõi vận hành độc lập không cần IoT/AI; bật/tắt capability theo cấu hình chưa có. |
| COM-20 | Danh mục gói và bảng giá mẫu tại Phụ lục F chỉ là cấu hình UAT; IAICT sửa tên, hạn mức, giá và … | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-21 | Quản lý danh mục đơn giá chi phí vận hành tham chiếu cho cloud/compute, storage/backup, SIM, em… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-22 | Subscription/entitlement phải hỗ trợ scope tenant, OrganizationUnit, Producer và Site; cùng ten… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-23 | Tách Payer khỏi Beneficiary; payer có thể là tenant/cơ quan nhà nước, HTX, doanh nghiệp hoặc ch… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-24 | Không bắt buộc mỗi Producer/hộ thành tenant; Producer account có quyền tự xem/cập nhật phạm vi … | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-25 | Hỗ trợ catalog dịch vụ Core, IoT, Traceability/QR, AI/Decision Support, Compliance nâng cao, In… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-26 | Metering phải có dimension tenant/beneficiary/module/site/device/period khi applicable; cho phé… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-27 | Chính sách sponsored service cho phép tỉnh/HTX/doanh nghiệp cấp quota hoặc thời hạn dịch vụ cho… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-28 | Self-service của Producer chỉ được bật nếu tenant/plan cho phép; mua/nâng dịch vụ không được tự… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-29 | Blockchain/anchoring không xuất hiện như SKU bắt buộc hoặc add-on bán độc lập; nếu kỹ thuật sử … | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-30 | Phân loại Funding Class tách khỏi lifecycle: Free/Freemium, Self-paid, Sponsored-paid, Complime… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-31 | Dashboard phân khúc tối thiểu: total account/named user/Producer, Active Paid subscription, Fre… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-32 | Tính KPI recurring revenue: MRR/ARR, New/Expansion/Contraction/Churned MRR, renewal; định nghĩa… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-33 | Tính GRR/NRR, ARPA/ARPU, Free→Paid, Trial→Paid, cohort retention và churn theo customer/subscri… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-34 | Revenue dashboard IAICT theo payer type, plan, module/add-on, vertical, địa bàn, sales owner và… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-35 | Price Book versioned: recurring/one-time/usage price, discount, annual discount, volume/tier và… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-36 | Nâng/hạ plan, add-on, pause/resume/cancel hỗ trợ effective date và proration rule cấu hình; hiể… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-37 | Tự tạo renewal signal/opportunity trước hết hạn theo mốc cấu hình; nhận diện upsell/cross-sell … | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-38 | Commercial snapshot theo ngày/tháng cho KPI và dashboard; khóa snapshot đã phát hành, adjustmen… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-39 | Tách money metric và usage metric; currency, tax mode, rounding, timezone và exchange-rate refe… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-40 | Self-service thương mại của customer/Producer chỉ hoạt động theo policy tenant: xem plan, yêu c… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |
| COM-41 | Commercial service catalog thống nhất Core, Vertical Pack, IoT, Traceability/QR, AI, Integratio… | NOT_STARTED | — | Lớp thương mại thuộc M5–M7 (D-53..D-64) — chưa tới mốc. |

## RPT — Báo cáo

| Mã | Yêu cầu (rút gọn) | Trạng thái | Bằng chứng (task · test) | Ghi chú |
|---|---|---|---|---|
| RPT-01 | Dashboard tổng quan vùng, cây đầu dòng, lô, sự kiện, cảnh báo và thiết bị. | COVERED | T-022, T-043 · test_dashboard | Dashboard một lần gọi: vùng/cây/lô/sự kiện/thiết bị + audit gần nhất. |
| RPT-02 | Biểu đồ thời tiết, đất, kho và thống kê cảnh báo. | NOT_STARTED | T-022, T-043 · test_dashboard | Mới có dashboard + 3 báo cáo truy xuất trên tổng số REP 82. |
| RPT-03 | Báo cáo hồ sơ cây đầu dòng và lịch sử bảo tồn. | NOT_STARTED | T-022, T-043 · test_dashboard | Mới có dashboard + 3 báo cáo truy xuất trên tổng số REP 82. |
| RPT-04 | Báo cáo nhật ký canh tác, vật tư, thu hoạch và truy vết lô. | PARTIAL | T-022, T-043 · test_dashboard | Báo cáo cân bằng khối lượng theo chu kỳ/đóng gói có; báo cáo nhật ký đầy đủ chưa có. |
| RPT-05 | Báo cáo thiết bị: uptime, pin, RSSI/SNR, dữ liệu thiếu và hiệu chuẩn. | NOT_STARTED | T-022, T-043 · test_dashboard | Mới có dashboard + 3 báo cáo truy xuất trên tổng số REP 82. |
| RPT-06 | Xuất dữ liệu nghiệp vụ và IoT theo CSV/JSON có giới hạn và audit. | NOT_STARTED | T-022, T-043 · test_dashboard | Mới có dashboard + 3 báo cáo truy xuất trên tổng số REP 82. |
| RPT-07 | Báo cáo tuân thủ canh tác theo FLD-20 và báo cáo điều kiện xuất theo từng thị trường. | NOT_STARTED | T-022, T-043 · test_dashboard | Mới có dashboard + 3 báo cáo truy xuất trên tổng số REP 82. |
| RPT-08 | Báo cáo mã số vùng trồng: hiệu lực, sắp hết hạn, vùng đủ và không đủ điều kiện theo thị trường. | PARTIAL | T-022, T-043 · test_dashboard | Báo cáo chỉ số vùng có PUC + trạng thái; điều kiện theo thị trường nằm ở mục phê duyệt. |
| RPT-09 | Báo cáo thu hồi và khiếu nại: số hồ sơ, phạm vi ảnh hưởng, thời gian xử lý và kết quả. | NOT_STARTED | T-022, T-043 · test_dashboard | Mới có dashboard + 3 báo cáo truy xuất trên tổng số REP 82. |
| RPT-10 | Báo cáo đối soát toàn vẹn dữ liệu theo kỳ và trạng thái checkpoint hash/Merkle. Chỉ bổ sung ref… | NOT_STARTED | T-022, T-043 · test_dashboard | Mới có dashboard + 3 báo cáo truy xuất trên tổng số REP 82. |
| RPT-11 | Báo cáo dành riêng cho IAICT: mức sử dụng theo tenant và theo hạn mức, doanh thu thuê bao tham … | NOT_STARTED | T-022, T-043 · test_dashboard | Mới có dashboard + 3 báo cáo truy xuất trên tổng số REP 82. |
| RPT-12 | Danh mục báo cáo có sẵn theo các mã REP tại Phụ lục I; công cụ tự tạo báo cáo vẫn là khuyến ngh… | PARTIAL | T-022, T-043 · test_dashboard | Mới 3/82 báo cáo REP dạng endpoint; chưa có danh mục báo cáo trong sản phẩm. |

## PAY — Thanh toán

| Mã | Yêu cầu (rút gọn) | Trạng thái | Bằng chứng (task · test) | Ghi chú |
|---|---|---|---|---|
| PAY-01 | Billing Account gắn Customer/Payer, billing contact, currency/tax mode, term, payment terms và … | NOT_STARTED | — | Thanh toán thuộc M7 (D-58) — chưa tới mốc. |
| PAY-02 | Billing Schedule/Billing Document tạo từ subscription/usage/proration; tách one-time, recurring… | NOT_STARTED | — | Thanh toán thuộc M7 (D-58) — chưa tới mốc. |
| PAY-03 | Payment Order state machine tối thiểu Created/Pending/Paid/Failed/Cancelled/Expired; liên kết b… | NOT_STARTED | — | Thanh toán thuộc M7 (D-58) — chưa tới mốc. |
| PAY-04 | Payment Orchestrator thay được adapter; 01 provider production bắt buộc theo baseline 4.11.2.1.… | NOT_STARTED | — | Thanh toán thuộc M7 (D-58) — chưa tới mốc. |
| PAY-05 | Webhook/callback phải xác minh chữ ký, timestamp/replay protection, idempotency, retry/backoff,… | NOT_STARTED | — | Thanh toán thuộc M7 (D-58) — chưa tới mốc. |
| PAY-06 | Reconciliation đối chiếu Payment Order/Transaction với provider settlement và file/API ngân hàn… | NOT_STARTED | — | Thanh toán thuộc M7 (D-58) — chưa tới mốc. |
| PAY-07 | Failed-payment/revenue recovery: retry schedule, notification, dunning, grace period, escalatio… | NOT_STARTED | — | Thanh toán thuộc M7 (D-58) — chưa tới mốc. |
| PAY-08 | Trạng thái thanh toán và lý do chặn truy cập được lưu riêng. Dunning có thể áp dụng Grace/Read-… | NOT_STARTED | — | Thanh toán thuộc M7 (D-58) — chưa tới mốc. |
| PAY-09 | Refund/partial refund/void/adjustment có reason, amount, original transaction, approval và prov… | NOT_STARTED | — | Thanh toán thuộc M7 (D-58) — chưa tới mốc. |
| PAY-10 | Không lưu PAN/CVV hoặc secret thanh toán nhạy cảm; chỉ lưu token/reference do provider cho phép… | COVERED | — | Điều cấm về lưu trữ: hệ thống không lưu PAN/CVV (chưa có thanh toán). |
| PAY-11 | 01 adapter hóa đơn điện tử theo API/event/export versioned là baseline: tạo draft/request, nhận… | NOT_STARTED | — | Thanh toán thuộc M7 (D-58) — chưa tới mốc. |
| PAY-12 | Customer Billing Portal hiển thị billing history, payment status, receipt/reference, due date, … | NOT_STARTED | — | Thanh toán thuộc M7 (D-58) — chưa tới mốc. |

## API — API & tích hợp

| Mã | Yêu cầu (rút gọn) | Trạng thái | Bằng chứng (task · test) | Ghi chú |
|---|---|---|---|---|
| API-01 | REST API được mô tả bằng OpenAPI 3.x; versioning và pagination. | COVERED | T-002, T-047 · test_cleanup_t047 | REST /api/v1 + OpenAPI 3.x (FastAPI) + phân trang toàn bộ danh sách (T-047). |
| API-02 | OAuth2/JWT hoặc cơ chế tương đương; rate limit và scope. | PARTIAL | T-002, T-047 · test_cleanup_t047 | Định danh header + scope theo vai trò; OAuth2/JWT và rate limit chưa có. |
| API-03 | Webhook cho sự kiện/cảnh báo quan trọng; cấu hình subscription theo tenant/module; retry/backof… | NOT_STARTED | T-002, T-047 · test_cleanup_t047 | Chưa có webhook (xem T-048, phát hiện F/D-29). |
| API-04 | Không khóa khả năng kết nối cổng truy xuất hoặc ERP trong tương lai. | PARTIAL | T-002, T-047 · test_cleanup_t047 | Kiến trúc mở (API + contract Protobuf/GraphQL sinh sẵn) giữ đường nối cổng/ERP; tích hợp thật chưa có (Q-TX-02). |

## NFR — Phi chức năng

| Mã | Yêu cầu (rút gọn) | Trạng thái | Bằng chứng (task · test) | Ghi chú |
|---|---|---|---|---|
| NFR-01 | Sẵn sàng | PARTIAL | — | Chạy trên hạ tầng Cloudflare; chưa có đo/cam kết 99,5% theo tháng. |
| NFR-02 | Hiệu năng web | PARTIAL | — | Đã đo thực tế: ấm 0,4–2s; lần gọi đầu sau nghỉ 2–5s (T-030) — chưa đạt p95 ≤2s mọi lúc. |
| NFR-03 | Tải đồng thời | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-04 | IoT throughput | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-05 | Khả năng mở rộng | PARTIAL | — | Worker stateless + D1; chưa kiểm thử quy mô lớn. |
| NFR-06 | RPO — RPO ≤01 giờ cho Event Ledger/Current State trọng yếu, nhật ký, lô và sự kiện truy xuất; ≤… | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-07 | RTO — Không quá 08 giờ cho sự cố production nghiêm trọng | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-08 | Khả dụng mobile | PARTIAL | — | Web mobile-first + cache SWR đọc khi mạng yếu; ghi ngoại tuyến chưa có. |
| NFR-09 | Tương thích | PARTIAL | — | Chạy trên trình duyệt hiện đại; chưa có ma trận tương thích chính thức. |
| NFR-10 | Quốc tế hóa | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-11 | Quan sát | PARTIAL | — | Có /health + audit + log Worker; metrics/cảnh báo vận hành chưa có. |
| NFR-12 | Bảo trì | COVERED | — | Registry một nguồn + codegen + migration versioned + test chống lệch (T-032/T-039/T-044). |
| NFR-13 | Dữ liệu | PARTIAL | — | Hạn lưu trữ tính theo từng bản ghi truy xuất; sao lưu/chính sách dữ liệu tổng thể chưa có. |
| NFR-14 | Khả năng tiếp cận | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-15 | Không khóa nhà cung cấp | PARTIAL | — | Store trừu tượng + gói Docker/Fly thoát hiểm (T-013); D1 là điểm khóa duy nhất đã ghi nhận (DEC-008). |
| NFR-16 | Hiệu năng mobile | PARTIAL | — | UI mobile-first, đã đo tải trang tĩnh 0,3–0,9s. |
| NFR-17 | Đồng bộ offline | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-18 | Khả năng phục hồi cloud | PARTIAL | — | Edge đa điểm; D1 một vùng — phục hồi vùng chưa có. |
| NFR-19 | Dư địa tài nguyên | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-20 | Cách ly tenant | COVERED | — | Cách ly tenant bằng guard + khóa ngoại phức hợp; test chéo tenant ở mọi chế độ store. |
| NFR-21 | Noisy-neighbor | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-22 | Quy mô thương mại | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-23 | Onboarding | PARTIAL | — | Tạo tenant + tài khoản đầu trong vài phút; template onboarding chưa có. |
| NFR-24 | Độ chính xác metering | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-25 | Xuất và thoát dữ liệu | PARTIAL | — | API đọc toàn bộ dữ liệu theo tenant; gói export kèm checksum/manifest chưa có. |
| NFR-26 | Nâng cấp sản phẩm | PARTIAL | — | Migration versioned + deploy không gián đoạn; canary/rollback tự động chưa có. |
| NFR-27 | Domain và thương hiệu | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-28 | Tính sẵn sàng theo gói | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-29 | Thử tải tái lập | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-30 | Hiệu năng truy xuất | PARTIAL | — | Truy vấn chuỗi truy xuất tính trực tiếp; quy mô pilot đáp ứng, chưa đo tải lớn. |
| NFR-31 | Giấy phép mã nguồn mở | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-32 | Kiểm tra tuân thủ ngoại tuyến | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-33 | Cấu hình danh mục và luật nghiệp vụ theo Vertical Pack | PARTIAL | — | Danh mục theo tenant có; luật nghiệp vụ vẫn trong code. |
| NFR-34 | Mở rộng ngành hàng | COVERED | — | Một lõi chạy 4 ngành trồng trọt/chăn nuôi/lâm nghiệp/thủy sản (T-035/T-036). |
| NFR-35 | Đồng bộ thời gian | PARTIAL | — | Timestamp server UTC; giờ đo của thiết bị được giữ nguyên khi ingest. |
| NFR-36 | Audit chống sửa | PARTIAL | — | Audit append-only + snapshot trước/sau; chuỗi băm chống sửa thuộc D-10, chưa có. |
| NFR-37 | API/Webhook lifecycle | PARTIAL | — | API versioning có; webhook lifecycle chưa có. |
| NFR-38 | Device profile extensibility | PARTIAL | — | Thêm loại thiết bị qua registry; profile mở rộng chưa có. |
| NFR-39 | IoT lifecycle security | PARTIAL | — | Khóa riêng từng thiết bị + xoay vòng/thu hồi (T-046); vòng đời thiết bị đầy đủ chưa có. |
| NFR-40 | Data Integrity/anchoring key custody | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-41 | Data residency | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-42 | Vertical Pack portability | PARTIAL | — | Contract Protobuf/GraphQL sinh từ registry là đường may portability (T-032). |
| NFR-43 | Event Ledger consistency | PARTIAL | — | Nhật ký append-only + toàn vẹn FK; projection nhất quán chưa có. |
| NFR-44 | Query hiện trạng | COVERED | — | Dashboard/báo cáo tính hiện trạng trực tiếp từ dữ liệu vận hành. |
| NFR-45 | Historical snapshot | PARTIAL | — | Snapshot audit + lịch sử trạng thái cho điểm thời gian; truy vấn snapshot tổng quát chưa có. |
| NFR-46 | AI resilience & provenance | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-47 | Scoped entitlement enforcement | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-48 | Commercial metric determinism | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-49 | Payment idempotency | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-50 | Payment webhook reliability | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-51 | Commercial audit | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-52 | Tenant experience isolation | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-53 | Domain/TLS automation | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-54 | Managed-ops authorization | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-55 | CRM/commercial performance | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |
| NFR-56 | Commercial export & portability | NOT_STARTED | — | Đánh giá theo từng mã; bằng chứng: đo tải T-027/T-030, kiểm thử đa store. |

## SEC — An toàn thông tin

| Mã | Yêu cầu (rút gọn) | Trạng thái | Bằng chứng (task · test) | Ghi chú |
|---|---|---|---|---|
| SEC-01 | TLS 1.2/1.3 cho mọi kết nối Internet; cấm SSL/TLS <1.2 và cipher/thuật toán lỗi thời; ưu tiên E… | COVERED | T-003, T-031, T-046 · test_t031_sys, test_iot | HTTPS qua Cloudflare edge (TLS 1.2/1.3) cho toàn bộ bề mặt beta. |
| SEC-02 | Mật khẩu cục bộ băm bằng Argon2id hoặc bcrypt/scrypt/PBKDF2 với tham số hiện hành được phê duyệ… | NOT_STARTED | T-003, T-031, T-046 · test_t031_sys, test_iot | Chưa tồn tại mật khẩu cục bộ (định danh bằng header) — khác mô hình SOW, cần quyết định phê duyệt. |
| SEC-03 | RBAC và kiểm tra quyền ở backend; chống IDOR/truy cập chéo tenant. | COVERED | T-003, T-031, T-046 · test_t031_sys, test_iot | RBAC backend + guard tenant + test truy cập chéo (T-003). |
| SEC-04 | Xác thực thiết bị IoT bằng khóa/credential riêng; quản lý DevEUI/AppKey và xoay vòng. Downlink/… | COVERED | T-003, T-031, T-046 · test_t031_sys, test_iot | Credential riêng từng thiết bị, chỉ lưu băm, xoay vòng/thu hồi (T-046); khóa LoRaWAN thuộc phạm vi thiết bị thật. |
| SEC-05 | Dữ liệu lưu trữ production DB/volume, object storage, backup và dữ liệu cục bộ mobile phải mã h… | PARTIAL | T-003, T-031, T-046 · test_t031_sys, test_iot | Mã hóa lưu trữ ở tầng hạ tầng; mã hóa trường PII chờ Owner đặt IAICT_PII_KEY (T-031). |
| SEC-06 | Kiểm tra input, chống SQLi/XSS/CSRF/SSRF, upload độc hại và traversal. | PARTIAL | T-003, T-031, T-046 · test_t031_sys, test_iot | SQL tham số hóa + validation + thoát XSS phía UI; bề mặt upload chưa tồn tại. |
| SEC-07 | Rate limit, API scope, token expiry/revocation và audit export. | PARTIAL | T-003, T-031, T-046 · test_t031_sys, test_iot | Scope theo vai trò + thu hồi khóa thiết bị có; rate limit và xuất audit chưa có. |
| SEC-08 | Quét dependency/SBOM; không dùng thư viện hết hỗ trợ hoặc giấy phép không phù hợp. | NOT_STARTED | T-003, T-031, T-046 · test_t031_sys, test_iot | Đánh giá theo từng mã; chưa có pentest/SBOM (D-18/D-26). |
| SEC-09 | SAST/DAST và kiểm thử theo OWASP ASVS v5.0.0 Level 2 cho web/API; ứng dụng Android theo OWASP M… | NOT_STARTED | T-003, T-031, T-046 · test_t031_sys, test_iot | Đánh giá theo từng mã; chưa có pentest/SBOM (D-18/D-26). |
| SEC-10 | Không còn lỗ hổng Critical/High chưa khắc phục tại thời điểm Go-live. | NOT_STARTED | T-003, T-031, T-046 · test_t031_sys, test_iot | Đánh giá theo từng mã; chưa có pentest/SBOM (D-18/D-26). |
| SEC-11 | Giữ log bảo mật/audit trọng yếu từ beta qua hết 18 tháng pilot kể từ Go-live. Retention sau đó … | PARTIAL | T-003, T-031, T-046 · test_t031_sys, test_iot | Audit lưu trong D1 không thời hạn mặc định; chính sách retention 18 tháng chưa ban hành văn bản. |
| SEC-12 | Quy trình thông báo sự cố, cô lập, phục hồi và báo cáo nguyên nhân gốc. | NOT_STARTED | T-003, T-031, T-046 · test_t031_sys, test_iot | Đánh giá theo từng mã; chưa có pentest/SBOM (D-18/D-26). |
| SEC-13 | Quét dependency/lỗ hổng tối thiểu hằng tháng và tại mỗi bản phát hành; lưu kết quả, đối chiếu S… | NOT_STARTED | T-003, T-031, T-046 · test_t031_sys, test_iot | Đánh giá theo từng mã; chưa có pentest/SBOM (D-18/D-26). |
| SEC-14 | Trước Go-live phải có ít nhất 01 đợt pentest do pháp nhân bên thứ ba được IAICT chọn/phê duyệt … | NOT_STARTED | T-003, T-031, T-046 · test_t031_sys, test_iot | Đánh giá theo từng mã; chưa có pentest/SBOM (D-18/D-26). |
| SEC-15 | Kiểm thử chống truy cập chéo tenant bao phủ IDOR, query thiếu tenant filter, cache poisoning, q… | PARTIAL | T-003, T-031, T-046 · test_t031_sys, test_iot | Test chức năng chéo tenant có (kể cả FK ở tầng DB); pentest/cache/queue chưa có bề mặt. |
| SEC-16 | Cơ chế subscription/entitlement phải có mã nguồn, tài liệu, test và khóa/cấu hình do IAICT kiểm… | NOT_STARTED | T-003, T-031, T-046 · test_t031_sys, test_iot | Đánh giá theo từng mã; chưa có pentest/SBOM (D-18/D-26). |
| SEC-17 | Giá, hợp đồng, hóa đơn tham chiếu và usage ledger là dữ liệu hạn chế; phân quyền riêng, mã hóa … | NOT_STARTED | T-003, T-031, T-046 · test_t031_sys, test_iot | Đánh giá theo từng mã; chưa có pentest/SBOM (D-18/D-26). |
| SEC-18 | Impersonation ngoài baseline theo Q.2; hỗ trợ mặc định bằng DelegatedAdminGrant và danh tính op… | PARTIAL | T-003, T-031, T-046 · test_t031_sys, test_iot | Không có impersonation; vận hành qua tài khoản riêng + khóa platform tách biệt. |
| SEC-19 | Xóa tenant là thao tác hủy dữ liệu: xác minh phạm vi, phê duyệt hai bước, export window, legal … | PARTIAL | T-003, T-031, T-046 · test_t031_sys, test_iot | Chưa có đường xóa tenant trong API — thao tác hủy chưa tồn tại để mà bảo vệ. |
| SEC-20 | Build artifact/container image production và mọi executable plugin/adapter phải truy vết được t… | PARTIAL | T-003, T-031, T-046 · test_t031_sys, test_iot | Mỗi bản deploy gắn commit + phiên bản Worker trong STATE; ký artifact chưa có. |
| SEC-21 | Data Integrity/anchoring key (nếu dùng), app signing key, API root secret và credential quản tr… | PARTIAL | T-003, T-031, T-046 · test_t031_sys, test_iot | Secret để trong Cloudflare secret store; khóa toàn vẹn (D-10) chưa có. |
| SEC-22 | Thiết bị IoT khi mất, thay thế hoặc kết thúc vòng đời phải revoke credential, ngừng nhận dữ liệ… | PARTIAL | T-003, T-031, T-046 · test_t031_sys, test_iot | Thu hồi khóa thiết bị có; đánh dấu trạng thái thiết bị mất/thay thế chưa có. |
| SEC-23 | Payment data minimization: cấm lưu PAN/CVV/PIN hoặc credential ngân hàng; chỉ lưu token/referen… | COVERED | T-003, T-031, T-046 · test_t031_sys, test_iot | Điều cấm về dữ liệu thanh toán: không lưu PAN/CVV — hệ thống không có dữ liệu thanh toán. |
| SEC-24 | Payment/provider webhook secret, API key và signing key do IAICT kiểm soát trong secret store; … | NOT_STARTED | T-003, T-031, T-046 · test_t031_sys, test_iot | Đánh giá theo từng mã; chưa có pentest/SBOM (D-18/D-26). |
| SEC-25 | Dữ liệu CRM thương mại, quote, price, billing, payment, revenue và margin có permission set riê… | NOT_STARTED | T-003, T-031, T-046 · test_t031_sys, test_iot | Đánh giá theo từng mã; chưa có pentest/SBOM (D-18/D-26). |
| SEC-26 | Contact/lead/customer PII áp dụng data minimization, purpose/consent/source khi cần, retention/… | NOT_STARTED | T-003, T-031, T-046 · test_t031_sys, test_iot | Đánh giá theo từng mã; chưa có pentest/SBOM (D-18/D-26). |
| SEC-27 | DelegatedAdminGrant và Managed Operator áp dụng least privilege, MFA, effective period, approva… | NOT_STARTED | T-003, T-031, T-046 · test_t031_sys, test_iot | Đánh giá theo từng mã; chưa có pentest/SBOM (D-18/D-26). |
| SEC-28 | Brand HTML/text/template/asset upload phải sanitize, allowlist type, malware scan và CSP phù hợ… | NOT_STARTED | T-003, T-031, T-046 · test_t031_sys, test_iot | Đánh giá theo từng mã; chưa có pentest/SBOM (D-18/D-26). |
| SEC-29 | Custom domain chống takeover: verify ownership trước bind, uniqueness, domain lifecycle, revoke… | NOT_STARTED | T-003, T-031, T-046 · test_t031_sys, test_iot | Đánh giá theo từng mã; chưa có pentest/SBOM (D-18/D-26). |
| SEC-30 | Discount/refund/write-off/manual payment adjustment vượt threshold áp dụng four-eyes/approval; … | NOT_STARTED | T-003, T-031, T-046 · test_t031_sys, test_iot | Đánh giá theo từng mã; chưa có pentest/SBOM (D-18/D-26). |
| SEC-31 | Audit tài chính/thương mại và managed operation phải có correlation ID, actor/service account, … | PARTIAL | T-003, T-031, T-046 · test_t031_sys, test_iot | Audit có actor/tenant/đối tượng/snapshot; correlation ID và dữ liệu thương mại chưa có. |
