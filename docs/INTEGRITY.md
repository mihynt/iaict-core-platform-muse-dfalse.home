# Data Integrity — đặc tả bộ kiểm chứng toàn vẹn (SOW D-10 / nhóm BLC)

Trạng thái: đã triển khai ở T-050 (2026-11-04). Mã nguồn: `backend/app/integrity.py`
(thuần, không phụ thuộc store) + các endpoint `/integrity/*` trong
`backend/app/production.py` + tab "Toàn vẹn dữ liệu" trong mục Báo cáo
(BLC-06, RPT-10). Kiểm thử: `backend/tests/test_integrity.py`.

## 1. Phạm vi

Đối tượng niêm phong là **nhật ký kiểm toán theo tenant** (Bảng 33
SYS_AUDIT_LOG) — sổ sự kiện append-only ghi mọi thao tác ghi dữ liệu trên
nền tảng. Các bản ghi audit có `tenant_id = NULL` (thao tác platform thuần
túy) nằm ngoài chuỗi của tenant; đây là giới hạn đã biết của bản baseline.

Niêm phong diễn ra theo **checkpoint**: một thao tác tường minh (endpoint
`POST /integrity/checkpoints`, quyền TENANT_ADMIN) đóng dấu mọi bản ghi
chưa niêm phong, gom **theo ngày UTC**. Hệ quả: cửa sổ bằng chứng là
"mọi bản ghi tính đến checkpoint gần nhất" — bản ghi mới ghi sau checkpoint
chưa được bảo vệ cho tới checkpoint kế tiếp. Đây là lựa chọn thiết kế có
chủ đích (không chạm đường ghi nóng của 4 store); nhịp checkpoint là tham
số vận hành (đề xuất: hằng ngày khi vào pilot).

## 2. Canonicalization (BLC-01)

- Chuẩn: **RFC 8785 — JSON Canonicalization Scheme (JCS)**, định danh
  `canon_id = "RFC8785-JCS"`. Khóa đối tượng sắp xếp theo đơn vị mã UTF-16;
  số theo thuật toán ECMAScript `Number::toString`; chuỗi thoát đúng tập
  ký tự bắt buộc của RFC. Bộ test vector của RFC (các số
  `333333333.3333333`, `1e+30`, `4e-50`, `0.002`, `1e+21`, `1e-7`,
  `0.000001`, `123456789012345680000`) nằm trong test tự động.
- **Event envelope, schema_version 1** — cố định, không thay đổi âm thầm
  giữa các release (đổi envelope = tăng schema_version):

  `{v, seq, ts, tenant, actor, action, target, outcome, old, new}`

  trong đó `old`/`new` là snapshot JSON đã parse (hoặc `null`). Metadata
  yêu cầu HTTP (`client_ip`, `user_agent`) **không** vào envelope.
- Hash sự kiện: `SHA-256(JCS(envelope))`. Khi có khóa toàn vẹn
  (`IAICT_INTEGRITY_KEY`, xem mục 5): `HMAC-SHA-256(key, JCS(envelope))`
  và checkpoint ghi `hash_alg = "HMAC-SHA-256"`.

## 3. Chuỗi băm và Merkle (BLC-02) — tree_version 1

- Chuỗi băm (domain separation bằng tiền tố `0x01`):

  `chain_0 = SHA-256("IAICT-INTEGRITY-GENESIS-v1:" | tenant_id)`
  `chain_i = SHA-256(0x01 | chain_{i-1} | event_hash_i)`

- Merkle trên các event hash của một checkpoint (tiền tố nút `0x02`):
  - Thứ tự lá: `seq` tăng dần trong khoảng checkpoint.
  - Nút cha: `SHA-256(0x02 | left | right)`.
  - Số lá lẻ: lá cuối được **nhân đôi** (duplicate-last).
  - Một lá duy nhất: root chính là event hash đó.
- Mỗi checkpoint lưu đủ metadata để tái tạo bằng chứng (BLC-01/02):
  `day, from_seq, to_seq, leaf_count, merkle_root, head_chain, prev_root`
  (Merkle root của checkpoint trước — liên kết các checkpoint thành một
  chuỗi duy nhất theo tenant), `schema_version, canon_id, hash_alg,
  tree_version, key_id, created_at`. Bảng `integrity_checkpoints`
  (migration D1 v12; không khóa ngoại tới tenants để bằng chứng tồn tại
  độc lập với vòng đời tenant).

## 4. Kiểm chứng và proof (BLC-06)

- `GET /integrity/verify`: tính lại toàn bộ từ dữ liệu audit hiện tại và
  đối chiếu từng checkpoint. Kết quả: `VALID | INVALID | UNVERIFIABLE |
  EMPTY`, kèm điểm gãy đầu tiên (checkpoint + khoảng seq + lý do:
  `ROW_COUNT_MISMATCH` — bị xóa/chèn; `CHAIN_MISMATCH` — nội dung bị sửa;
  `ROOT_MISMATCH`; `PREV_ROOT_MISMATCH`). Độ phân giải của điểm gãy là
  khoảng seq của checkpoint (theo ngày) — baseline không lưu neo con
  trong ngày.
- `GET /integrity/proof/{seq}`: bằng chứng Merkle (inclusion proof) cho
  một bản ghi đã niêm phong: event hash, chain hash, các bước anh em,
  Merkle root và metadata checkpoint — bên thứ ba tự tái tạo được root
  từ `(event_hash, proof)` mà không cần truy cập hệ thống.
- Giao diện: tab Toàn vẹn trong mục Báo cáo hiển thị trạng thái niêm
  phong, danh sách checkpoint, nút kiểm chứng và tra proof theo seq.

## 5. Khóa và lưu ký (BLC-07, SEC-21, NFR-40)

- Khóa HMAC (nếu dùng) nằm ở **secret store của hạ tầng**
  (`IAICT_INTEGRITY_KEY` trên Cloudflare — Owner tự đặt ở dashboard,
  trợ lý không giữ giá trị). Không đặt khóa: dùng SHA-256 thuần,
  `key_id = "none"`.
- Mỗi checkpoint ghi `key_id` = 16 ký tự hex đầu của `SHA-256(key)` —
  đủ để truy vết checkpoint thuộc khóa nào mà không lộ khóa. Sau khi
  xoay vòng khóa, checkpoint cũ vẫn truy thuộc được nhưng chỉ kiểm
  chứng lại được khi còn khóa cũ (kết quả `KEY_UNAVAILABLE` /
  `UNVERIFIABLE`, không báo sai thành INVALID).

## 6. Neo blockchain (BLC-03/04/05/08/09) — chưa kích hoạt, có điều kiện

Nhóm điều khoản này chỉ áp dụng **khi** IAICT quyết định dùng anchoring
(SOW Q.2). Baseline để sẵn đường may adapter: trường `anchor` trong đáp
ứng của proof mang `status = NOT_ENABLED` và Merkle root — giá trị duy
nhất một adapter neo sẽ ghi on-chain (không ghi dữ liệu cá nhân/tài liệu
lên chuỗi, đúng BLC-05). Khi kích hoạt phải bổ sung hồ sơ mạng chính
theo BLC-09 (Polygon PoS là phương án tham chiếu của SOW, không khóa
hãng) và hiển thị reference/thời điểm neo ở trang xác minh (BLC-06).

## 7. Test vector chính thức (D-10 yêu cầu)

Tenant `demo`, không khóa (SHA-256), 3 bản ghi:

| seq | JCS(envelope) |
|---|---|
| 1 | `{"action":"ZON_CREATE","actor":"admin","new":{"code":"Z-01","initial_declared_area_ha":10.5},"old":null,"outcome":"OK","seq":1,"target":"zones/Z-01","tenant":"demo","ts":"2026-11-04T01:00:00Z","v":1}` |
| 2 | `{"action":"PLAN_CREATE","actor":"admin","new":{"code":"PLAN-2026","target_yield_kg":5000},"old":null,"outcome":"OK","seq":2,"target":"crop_plans/PLAN-2026","tenant":"demo","ts":"2026-11-04T01:05:00Z","v":1}` |
| 3 | `{"action":"LOT_CREATE","actor":"op1","new":{"code":"L-01","quantity":120},"old":null,"outcome":"OK","seq":3,"target":"lots/L-01","tenant":"demo","ts":"2026-11-04T02:00:00Z","v":1}` |

- event_hash: seq 1 `1568c700a9b86b722cecc45d527b91b81cdf1d1cb9b8dbf08e3bcc29e6c42e9d` ·
  seq 2 `a781ec8aab86fd22b21cd32e39640b75205f34099ee8cbbdd2d14db3ae69e21f` ·
  seq 3 `9ace13dee2cc6764ca8372b16b0219d0a19c0cc81668a0f94003f059de9dcdc2`
- head_chain: `ca2be75624a9a96d608301b021eb790d2a81828c6a1620ae6bffbb0652cb15a4`
- merkle_root: `d041bb003a0ad41e6da70ce297d8da6774f87a56dcaf0ff823e412d0664e12d3`
- Proof mẫu cho seq 2: `[{side: L, hash: 1568c700…c42e9d}, {side: R, hash: d50196f2b02cdefdff6fa45c520e5f2d8ae06d9a0674635ddc1e0bf8a3c65186}]`
  — gấp lên theo quy tắc mục 3 cho đúng `merkle_root` trên.

Các giá trị này được khóa bằng test tự động trong
`backend/tests/test_integrity.py` (cùng họ vector, chạy mọi chế độ store).

## 8. Giới hạn đã biết

- Điểm gãy chỉ khoanh được tới khoảng seq của checkpoint (theo ngày).
- Bản ghi chưa niêm phong (sau checkpoint gần nhất) chưa có bằng chứng.
- Hàng audit `tenant_id = NULL` ngoài phạm vi chuỗi tenant.
- Đối thủ có quyền ghi cả DB lẫn bảng checkpoints có thể viết lại toàn
  bộ lịch sử rồi niêm phong lại — chống ở mức này cần neo ngoài hệ
  thống (mục 6) hoặc sao lưu root ra kênh độc lập; vận hành pilot nên
  xuất root định kỳ ra ngoài (email/biên bản) như một neo thủ công.
