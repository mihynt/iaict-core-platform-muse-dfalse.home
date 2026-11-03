"use strict";
/* IAICT Core — web UI (beta). Vanilla SPA talking to /api/v1 on this origin. */

const $ = (s, el = document) => el.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[c]));
const fmtNum = (v) => (v === null || v === undefined || v === "" ? "—" :
  Number(v).toLocaleString("vi-VN", { maximumFractionDigits: 2 }));
const fmtDate = (v) => {
  if (!v) return "—";
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? String(v) : d.toLocaleDateString("vi-VN");
};
const fmtTs = (v) => {
  if (!v) return "—";
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? String(v) :
    d.toLocaleString("vi-VN", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
};

const ERR_VI = {
  TENANT_REQUIRED: "Thiếu mã tenant trong yêu cầu.",
  TENANT_INVALID: "Mã tenant không đúng định dạng.",
  TENANT_UNKNOWN: "Tenant chưa được đăng ký trên hệ thống. Kiểm tra lại mã tenant ở mục Cài đặt.",
  TENANT_SUSPENDED: "Tenant đang bị khóa (SUSPENDED).",
  TENANT_EXISTS: "Mã tenant đã tồn tại.",
  ACTOR_REQUIRED: "Cần khai báo người dùng thực hiện (actor).",
  ACTOR_UNKNOWN: "Người dùng (actor) không thuộc tenant này. Hãy tạo người dùng trước hoặc sửa ở Cài đặt.",
  ROLE_FORBIDDEN: "Actor không đủ quyền — thao tác ghi cần vai trò OPERATOR trở lên.",
  CODE_EXISTS: "Mã này đã tồn tại trong tenant.",
  CODE_REQUIRED: "Trường mã là bắt buộc.",
  REF_UNKNOWN: "Đối tượng tham chiếu (vùng/kế hoạch/cây) không tồn tại trong tenant này.",
  NOT_FOUND: "Không tìm thấy đối tượng.",
  PLATFORM_DISABLED: "Quản trị platform chưa được bật (chưa đặt khóa).",
  PLATFORM_KEY_INVALID: "Khóa platform không đúng.",
  USER_EXISTS: "Tên người dùng đã tồn tại trong tenant.",
  RECORD_IN_USE: "Đang được dữ liệu khác tham chiếu nên chưa xoá được — hãy xoá hoặc sửa các bản ghi liên quan trước.",
  ACCOUNT_INACTIVE: "Tài khoản đã bị khóa hoặc thu hồi nên không thao tác được.",
  LAST_ADMIN: "Không thể khóa quản trị viên tenant cuối cùng đang hoạt động.",
  ALREADY_WITHDRAWN: "Thửa này đã rút khỏi vùng trước đó.",
};

class ApiError extends Error {
  constructor(code, message, status) {
    super(ERR_VI[code] || message || "Đã xảy ra lỗi không xác định.");
    this.code = code; this.status = status;
  }
}

/* Connection info lives in localStorage when "remember me" is on, and in
   sessionStorage otherwise. All access is defensive: if the browser blocks
   storage (private mode etc.), an in-memory fallback keeps the app usable
   for the session instead of dying silently on the login screen. */
const memFallback = {};
function safeArea(area) {
  try { area.setItem("__iaict_t", "1"); area.removeItem("__iaict_t"); return area; }
  catch { return null; }
}
const LS = safeArea(window.localStorage);
const SS = safeArea(window.sessionStorage);
function areaGet(area, k) { try { return area ? area.getItem(k) : null; } catch { return null; } }
function areaSet(area, k, v) {
  try { if (area) { area.setItem(k, v); return; } } catch { /* fall through */ }
  memFallback[k] = v;
}
function areaDel(area, k) { try { if (area) area.removeItem(k); } catch { /* ignore */ } delete memFallback[k]; }
const LS_KEYS = ["iaict.tenant", "iaict.actor", "iaict.pkey"];
const store = {
  _get(k) { return areaGet(LS, k) ?? areaGet(SS, k) ?? memFallback[k] ?? ""; },
  get tenant() { return this._get("iaict.tenant"); },
  get actor() { return this._get("iaict.actor"); },
  get pkey() { return this._get("iaict.pkey"); },
  remembered() { return areaGet(LS, "iaict.tenant") !== null; },
  save(tenant, actor, pkey, remember = true) {
    this.clear();
    const area = remember ? LS : SS;
    areaSet(area, "iaict.tenant", tenant);
    areaSet(area, "iaict.actor", actor);
    if (pkey) areaSet(area, "iaict.pkey", pkey);
  },
  clear() { LS_KEYS.forEach((k) => { areaDel(LS, k); areaDel(SS, k); }); },
};

async function api(path, { method = "GET", body, platform = false, tenant, actor, pkey } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (platform) headers["X-Platform-Key"] = pkey ?? store.pkey;
  else {
    const t = tenant ?? store.tenant;
    const a = actor ?? store.actor;
    if (t) headers["X-Tenant-Id"] = t;
    if (a) headers["X-Actor"] = a;
  }
  // GETs are retried on ANY transient failure: HTTP 5xx from the free-tier
  // Worker (observed as Cloudflare 1102) AND network-level failures
  // (fetch rejects / our own 20s abort — the connection-drop class seen
  // live on 2026-11-02, which an earlier version of this loop never
  // retried because those errors are not ApiError instances).
  const attempts = method === "GET" ? 3 : 1;
  const backoff = [700, 1600];
  let lastErr;
  for (let attempt = 1; attempt <= attempts; attempt++) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 8000);
    try {
      const res = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined, signal: ctrl.signal });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const d = data.detail || {};
        throw new ApiError(typeof d === "string" ? "" : d.code, typeof d === "string" ? d : d.message, res.status);
      }
      return data;
    } catch (err) {
      lastErr = err;
      const retryable = err instanceof ApiError
        ? (err.code === "NETWORK" || (err.status ?? 0) >= 500 || err.status === 429)
        : true; // fetch-level failure: network drop, DNS, or abort timeout
      if (!retryable || attempt === attempts) throw err;
      await new Promise((r) => setTimeout(r, backoff[attempt - 1] ?? 1600));
    } finally {
      clearTimeout(timer);
    }
  }
  throw lastErr;
}
const T = (p, o) => api(`/api/v1${p}`, o);            // tenant-scoped
const P = (p, o) => api(`/api/v1${p}`, { ...o, platform: true }); // platform-scoped

/* ---------------- toasts ---------------- */
function toast(msg, isErr = false) {
  const el = document.createElement("div");
  el.className = "toast" + (isErr ? " err" : "");
  el.innerHTML = `<span>${isErr ? "⚠️" : "✅"}</span><span>${esc(msg)}</span>`;
  $("#toasts").appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; el.style.transition = "opacity .4s"; setTimeout(() => el.remove(), 420); }, 4200);
}

/* ---------------- bottom sheet forms ---------------- */
let sheetSubmit = null;
let sheetOnCancel = null;
function openSheet(title, fields, onSubmit, opts = {}) {
  sheetOnCancel = opts.onCancel || null;
  $("#sheetTitle").textContent = title;
  const form = $("#sheetForm");
  form.innerHTML = fields.map((f) => {
    if (f.type === "note") return `<p class="sub" style="margin:2px 2px 12px">${esc(f.label)}</p>`;
    const req = f.required ? ' <span class="req">*</span>' : "";
    let control;
    if (f.type === "select" || f.type === "bool") {
      control = `<select name="${f.k}">${(f.options || []).map((o) =>
        `<option value="${esc(o.v)}" ${String(o.v) === String(f.def ?? "") ? "selected" : ""}>${esc(o.t)}</option>`).join("")}</select>`;
    } else if (f.type === "textarea") {
      control = `<textarea name="${f.k}" placeholder="${esc(f.placeholder || "")}">${esc(f.def ?? "")}</textarea>`;
    } else {
      control = `<input name="${f.k}" type="${f.type || "text"}" ${f.step ? `step="${f.step}"` : ""}
        value="${esc(f.def ?? "")}" placeholder="${esc(f.placeholder || "")}" ${f.required ? "required" : ""}
        ${f.type === "text" ? 'autocapitalize="off"' : ""}>`;
    }
    const addBtn = f.addNew ? `<button type="button" class="btn btn-ghost btn-sm add-new" data-addnew="${f.k}">＋ Thêm mới</button>` : "";
    return `<div class="field"><label>${esc(f.label)}${req}</label>${control}${addBtn}</div>`;
  }).join("") + `<div class="form-actions">
      <button type="button" class="btn btn-ghost" id="sheetCancel">Hủy</button>
      <button type="submit" class="btn btn-primary">Lưu lại</button></div>`;
  sheetSubmit = { fields, onSubmit };
  // WordPress-style inline create: a "+ Thêm mới" button beside a reference
  // picker opens a quick-create sheet; on success the parent form reopens
  // with the picker's options refreshed and the new record pre-selected,
  // keeping everything the user had already typed (T-026).
  form.querySelectorAll("[data-addnew]").forEach((btn) => {
    btn.onclick = () => {
      const f = fields.find((x) => x.k === btn.dataset.addnew);
      if (!f || !f.addNew) return;
      const snapshot = {};
      for (const pf of fields) {
        const inp = form.querySelector(`[name="${pf.k}"]`);
        if (inp) snapshot[pf.k] = inp.value;
      }
      const parent = { title, fields, onSubmit };
      const restore = async (newCode) => {
        for (const pf of parent.fields) {
          if (pf.refreshOptions) { try { pf.options = await pf.refreshOptions(); } catch { /* keep */ } }
          pf.def = newCode && pf.k === f.k ? newCode : snapshot[pf.k];
        }
        openSheet(parent.title, parent.fields, parent.onSubmit);
      };
      f.addNew((code) => restore(code), () => restore(null));
    };
  });
  $("#sheetBackdrop").hidden = false;
  $("#sheet").hidden = false;
  $("#sheetCancel").onclick = closeSheet;
  const first = form.querySelector("input,select,textarea");
  if (first) setTimeout(() => first.focus(), 250);
}
function closeSheet() {
  $("#sheetBackdrop").hidden = true;
  $("#sheet").hidden = true;
  sheetSubmit = null;
  const cb = sheetOnCancel;
  sheetOnCancel = null;
  if (cb) cb();
}
$("#sheetClose").addEventListener("click", closeSheet);

/* ---------------- T-026 helpers: detail view, delete, quick-create --------- */
const optOf = (list, emptyLabel, fmt) => [{ v: "", t: emptyLabel }, ...list.map(fmt)];
const fmtZoneOpt = (z) => ({ v: z.code, t: `${z.code} · ${z.name || ""}` });
const fmtActorOpt = (a) => ({ v: a.code, t: `${a.code} · ${a.name || ""}` });
const fmtPlantOpt = (pl) => ({ v: pl.code, t: `${pl.code} · ${pl.species || ""}` });
const fmtParcelOpt = (u) => ({ v: u.code, t: `${u.code} · ${u.name || ""}` });
const fmtInputOpt = (i) => ({ v: i.code, t: `${i.code} · ${i.name || i.substance_code || ""}${i.phi_days != null ? ` · cách ly ${i.phi_days} ngày` : ""}` });
const PUC_STATUSES = [
  { v: "", t: "— Chưa rõ —" }, { v: "PENDING_POST_INSPECTION", t: "Chờ hậu kiểm" },
  { v: "ACTIVE_COMPLIANT", t: "Đang hiệu lực — đạt" }, { v: "SUSPENDED_TEMPORARILY", t: "Tạm đình chỉ" },
  { v: "RESTORED", t: "Đã khôi phục" }, { v: "REVOKED_PERMANENTLY", t: "Thu hồi vĩnh viễn" }];
const MEMBERSHIP_STATUSES = [
  { v: "ACTIVE_MEMBER", t: "Đang tham gia" }, { v: "SUSPENDED_PLOT", t: "Tạm ngưng" },
  { v: "WITHDRAWN_FROM_ZONE", t: "Đã rút khỏi vùng" }];
const FARM_TIERS = [
  { v: "", t: "— Không áp dụng —" }, { v: "HOUSEHOLD_SCALE", t: "Quy mô hộ chăn nuôi" },
  { v: "SMALL_FARM", t: "Trang trại nhỏ" }, { v: "MEDIUM_FARM", t: "Trang trại vừa" },
  { v: "LARGE_FARM", t: "Trang trại lớn" }];
const SUBMIT_CHANNELS = [
  { v: "", t: "— Chưa rõ —" }, { v: "ONLINE_NATIONAL_PORTAL", t: "Trực tuyến qua Cổng DVC Quốc gia" },
  { v: "DIRECT_AT_COMMUNE_COUNTER", t: "Nộp trực tiếp tại UBND xã" },
  { v: "POSTAL_MAIL_TO_COMMUNE", t: "Qua bưu điện về UBND xã" }];
const FOREST_ORIGINS = [
  { v: "", t: "— Không áp dụng —" }, { v: "NATURAL_FOREST", t: "Rừng tự nhiên" },
  { v: "STATE_PLANTATION_FOREST", t: "Rừng trồng nhà nước" },
  { v: "SELF_INVESTED_PROTECTION_FOREST", t: "Rừng phòng hộ tự đầu tư" },
  { v: "PRODUCTION_PLANTATION_FOREST", t: "Rừng trồng sản xuất" },
  { v: "SCATTERED_HOME_GARDEN_TREES", t: "Cây phân tán vườn nhà" }];
const AQUA_WATERS = [
  { v: "", t: "— Không áp dụng —" }, { v: "EARTHEN_POND", t: "Ao đất" },
  { v: "LINED_POND", t: "Ao lót bạt" }, { v: "SALTWATER_TANK", t: "Bể nước mặn" },
  { v: "MARINE_CAGE_RAFT", t: "Lồng bè biển" }, { v: "RIVER_CAGE_RAFT", t: "Lồng bè sông" },
  { v: "INTERTIDAL_MUDFLAT", t: "Bãi triều" }];
const FORESTRY_CLASSES = [
  { v: "", t: "— Không áp dụng —" }, { v: "CLASS_I_COMPLIANT", t: "Loại I — tuân thủ" },
  { v: "CLASS_II_NON_COMPLIANT", t: "Loại II — chưa tuân thủ" }, { v: "UNCLASSIFIED", t: "Chưa phân loại" }];
const BOOL_OPTS = [
  { v: "", t: "— Chưa rõ —" }, { v: "true", t: "Có" }, { v: "false", t: "Không" }];
const ACTOR_TYPES = [
  { v: "HOUSEHOLD", t: "Nông hộ" }, { v: "COMPANY", t: "Doanh nghiệp" },
  { v: "COOPERATIVE", t: "Hợp tác xã" }, { v: "FACILITY", t: "Cơ sở đóng gói/chế biến" },
  { v: "OTHER", t: "Khác" }];

function quickZone(done, back) {
  openSheet("Thêm vùng mới", [
    { k: "code", label: "Mã vùng", required: true, placeholder: "vd: Z-03" },
    { k: "name", label: "Tên vùng" },
    { k: "area_ha", label: "Diện tích (ha)", type: "number", step: "0.01" },
    { k: "puc_code", label: "Mã số vùng trồng (PUC)" },
  ], async (p) => { const r = await T("/zones", { method: "POST", body: p }); invalidate("zones", "zhistory"); toast("Đã thêm vùng " + r.code); done(r.code); }, { onCancel: back });
}
function quickPlant(done, back) {
  openSheet("Thêm cây đầu dòng mới", [
    { k: "code", label: "Mã cây", required: true, placeholder: "vd: MPL-002" },
    { k: "species", label: "Loài cây", required: true },
    { k: "variety", label: "Giống" },
  ], async (p) => { const r = await T("/mother-plants", { method: "POST", body: p }); invalidate("plants"); toast("Đã thêm cây " + r.code); done(r.code); }, { onCancel: back });
}
function quickActor(done, back) {
  openSheet("Thêm chủ thể mới", [
    { k: "code", label: "Mã chủ thể", required: true, placeholder: "vd: H05" },
    { k: "name", label: "Tên chủ thể", required: true },
    { k: "actor_type", label: "Loại chủ thể", type: "select", options: ACTOR_TYPES },
    { k: "phone", label: "Số điện thoại" },
  ], async (p) => { const r = await T("/actors", { method: "POST", body: p }); invalidate("actors"); toast("Đã thêm chủ thể " + r.code); done(r.code); }, { onCancel: back });
}
function quickInputLot(done, back) {
  openSheet("Thêm lô vật tư mới", [
    { k: "code", label: "Mã lô vật tư", required: true, placeholder: "vd: VT-001" },
    { k: "product_name", label: "Tên sản phẩm", required: true },
    { k: "phi_days", label: "Số ngày cách ly (PHI)", type: "number", step: "1" },
    { k: "expiry_date", label: "Hạn dùng", type: "date" },
  ], async (p) => { const r = await T("/input-lots", { method: "POST", body: p }); invalidate("inputs"); toast("Đã thêm lô vật tư " + r.code); done(r.code); }, { onCancel: back });
}
function quickParcel(done, back) {
  openSheet("Thêm thửa đất mới", [
    { k: "code", label: "Mã thửa", required: true, placeholder: "vd: T42" },
    { k: "name", label: "Tên thửa" },
    { k: "unit_type", label: "Loại thửa", type: "select", options: [
      { v: "PARCEL", t: "Thửa ruộng" }, { v: "GREENHOUSE", t: "Nhà kính" },
      { v: "POND", t: "Ao nuôi" }, { v: "PEN", t: "Chuồng trại" }, { v: "OTHER", t: "Khác" }] },
    { k: "area_m2", label: "Diện tích (m²)", type: "number", step: "0.01" },
  ], async (p) => { const r = await T("/spatial-units", { method: "POST", body: p }); invalidate("parcels"); toast("Đã thêm thửa " + r.code); done(r.code); }, { onCancel: back });
}

const DETAIL_LABELS = {
  code: "Mã", name: "Tên", status: "Trạng thái", season: "Mùa vụ", province: "Tỉnh/TP",
  district: "Quận/Huyện", ward: "Xã/Phường", area_ha: "Diện tích (ha)", area_m2: "Diện tích (m²)",
  puc_code: "Mã số vùng trồng (PUC)", puc_status: "Trạng thái mã vùng", vsic_code: "Mã ngành VSIC",
  sector_category: "Ngành", market_scope: "Thị trường", primary_species: "Đối tượng SX chính",
  scientific_name: "Tên khoa học", issue_date: "Ngày cấp mã", issuing_authority: "Cơ quan cấp",
  post_inspect_due_date: "Hạn hậu kiểm", dist_to_residential_m: "Cách khu dân cư (m)",
  dist_to_sensitive_zone_m: "Cách vùng nhạy cảm (m)", bee_site_min_dist_km: "Cách điểm nuôi ong tối thiểu (km)",
  species: "Loài", variety: "Giống", cultivar_code: "Mã giống", origin: "Nguồn gốc",
  recognition_no: "Số quyết định công nhận", valid_to: "Công nhận đến", valid_from: "Hiệu lực từ",
  zone_code: "Vùng", plant_code: "Cây đầu dòng", plan_code: "Kế hoạch", parcel_code: "Thửa đất",
  crop_name: "Cây trồng", start_date: "Ngày bắt đầu", end_date: "Ngày kết thúc",
  target_yield_kg: "Sản lượng mục tiêu (kg)", planting_density: "Mật độ trồng", seed_origin: "Nguồn giống",
  seed_origin_doc: "Hồ sơ nguồn gốc giống", variety_name: "Tên giống", actor_type: "Loại chủ thể",
  gln_code: "Mã GLN", parent_code: "Chủ thể cấp trên", phone: "Số điện thoại", email: "Email", legal_id: "Số CCCD / MST", legal_id_hash: "Mã băm số định danh (HMAC)",
  address: "Địa chỉ", province_code: "Mã tỉnh", district_code: "Mã huyện", commune_code: "Mã xã",
  unit_type: "Loại thửa", operator_code: "Chủ thể vận hành", joined_date: "Ngày tham gia vùng",
  product_name: "Tên sản phẩm", brand_name: "Thương hiệu", registration_no: "Số đăng ký",
  active_ingredient: "Hoạt chất", supplier_code: "Nhà cung cấp", quantity_received: "Số lượng nhập",
  unit: "Đơn vị", purchase_invoice_no: "Số hóa đơn mua", qcvn_scheme_id: "Mã quy chuẩn (QCVN)",
  purchase_date: "Ngày mua", expiry_date: "Hạn dùng", phi_days: "Ngày cách ly (PHI)",
  harvest_date: "Ngày thu hoạch", harvest_time: "Giờ thu hoạch", farmer_code: "Nông hộ", weigh_slip_number: "Số phiếu cân",
  quantity: "Sản lượng", quality_grade: "Phân loại chất lượng", harvested_by: "Người thu hoạch",
  traceability_code: "Mã truy xuất", data_retention_until: "Lưu dữ liệu đến",
  facility_code: "Cơ sở đóng gói", phc_code: "Mã cơ sở đóng gói (PHC)", output_weight_kg: "Sản lượng thành phẩm (kg)",
  yield_norm_ratio: "Định mức thu hồi", storage_type: "Loại bảo quản", packed_at: "Thời điểm đóng gói",
  event_type: "Loại sự kiện", occurred_at: "Thời điểm", input_lot_code: "Lô vật tư đã dùng",
  safe_harvest_date: "Thu hoạch an toàn từ", application_method: "Phương pháp áp dụng",
  fruit_bagging_count: "Số trái đã bao", max_safe_harvest_date: "Ngày thu hoạch an toàn",
  actual_harvest_date: "Ngày thu hoạch thực tế", validation_outcome: "Kết luận",
  last_treatment_ref: "Lần xử lý quyết định", sync_status: "Trạng thái đồng bộ", synced_at: "Đồng bộ lúc",
  created_at: "Tạo lúc", updated_at: "Cập nhật lúc",
  lot_code: "Lô thu hoạch", membership_status: "Trạng thái tham gia",
  registered_area_m2: "Diện tích đăng ký (m²)", left_date: "Ngày rời vùng",
  production_event_time: "Thời điểm sản xuất", business_name: "Tên cơ sở / doanh nghiệp", business_unit_name: "Tên cơ sở / doanh nghiệp", business_unit_address: "Địa chỉ cơ sở", brand_trademark_serial: "Thương hiệu / số seri", owner_actor_code: "Chủ thể sở hữu vùng",
  business_address: "Địa chỉ cơ sở", brand_or_serial: "Thương hiệu / số seri",
  data_carrier_type: "Loại mã mang dữ liệu", cultivar_code: "Mã giống",
  owner_manager: "Chủ sở hữu / người quản lý", crop_group: "Nhóm cây",
  water_source: "Nguồn nước", managing_entity: "Chủ thể quản lý",
  category: "Nhóm vật tư", packaging_unit_code: "Đơn vị đóng gói (SKU)",
  expiration_date: "Hạn dùng", product_image_url: "Ảnh sản phẩm",
  substance_code: "Hoạt chất / thành phần", vn_registration_number: "Số đăng ký lưu hành VN",
  batch_no: "Số lô nhà sản xuất", national_land_parcel_id: "Mã định danh thửa đất quốc gia",
  map_sheet_number: "Số tờ bản đồ", parcel_number: "Số thửa",
  land_tenure_doc_type: "Loại giấy tờ đất", land_cert_serial: "Số giấy chứng nhận",
  land_legal_owner_name: "Chủ đất theo giấy tờ", owner_consent_doc_url: "Văn bản đồng ý của chủ đất", cultivar: "Giống",
  outcome: "Kết luận", harvest_lot_code: "Lô thu hoạch đầu vào",
  packing_lot_code: "Lô đóng gói", allocated_weight_kg: "Khối lượng phân bổ (kg)",
  gtin_code: "Mã GTIN", sscc_code: "Mã SSCC", package_spec: "Quy cách đóng gói",
  units_count: "Số đơn vị", level: "Cấp đóng gói", stage_no: "Công đoạn số",
  stage_name: "Tên công đoạn", applied_scheme_id: "Tiêu chuẩn áp dụng",
  scheme_code: "Mã tiêu chuẩn / chứng nhận", event_time: "Thời điểm sự kiện",
  product_trace_code: "Mã truy xuất sản phẩm", location_trace_code: "Mã truy xuất địa điểm",
  batch_lot_number: "Số lô", quantity_received: "Số lượng nhập", dosage_concentration: "Liều lượng / nồng độ",
  total_quantity_applied: "Tổng lượng đã dùng", crop_animal_growth_stage: "Giai đoạn sinh trưởng",
  target_pest_disease_reason: "Đối tượng / lý do xử lý", gs1_role_ai: "Mã vai trò GS1",
  is_group_leader: "Là tổ trưởng", ics_training_completed: "Đã tập huấn ICS",
  initial_declared_area_ha: "Diện tích khai báo ban đầu (ha)", validated_at: "Thời điểm kiểm tra",
};

const DETAIL_VALUE_MAPS = {
  actor_type: { HOUSEHOLD: "Nông hộ", COMPANY: "Doanh nghiệp", COOPERATIVE: "Hợp tác xã", FACILITY: "Cơ sở đóng gói/chế biến", OTHER: "Khác" },
  unit_type: { LAND_PARCEL: "Thửa ruộng", PARCEL: "Thửa ruộng", GREENHOUSE: "Nhà kính", POND: "Ao nuôi", AQUATIC_POND: "Ao nuôi", PEN: "Chuồng trại", LIVESTOCK_PEN: "Chuồng trại", FOREST_PLOT: "Lô rừng", OTHER: "Khác" },
  storage_type: { FRESH_AMBIENT: "Tươi, nhiệt độ thường", CHILLED_COOL: "Mát lạnh", FROZEN_PROCESSED: "Đông lạnh / chế biến" },
  validation_outcome: { PASSED_SAFE: "Đạt — an toàn", BLOCKED_VIOLATION_PHI: "Chặn — vi phạm thời gian cách ly", CONDITIONAL_LAB_TEST_REQUIRED: "Điều kiện — cần xét nghiệm dư lượng" },
  sync_status: { PENDING_SYNC: "Chờ đồng bộ cổng quốc gia", SYNCED: "Đã đồng bộ", SYNCED_SUCCESS: "Đã đồng bộ cổng quốc gia" },
  data_carrier_type: { QR_CODE: "Mã QR", BARCODE: "Mã vạch", RFID: "RFID" },
};
function fmtDetailVal(k2, v) {
  if (typeof v === "boolean") return v ? "Có" : "Không";
  const vm = DETAIL_VALUE_MAPS[k2];
  if (vm && typeof v === "string" && vm[v]) return vm[v];
  if (typeof v === "object") return JSON.stringify(v);
  if (/_at$/.test(k2)) return String(v).replace("T", " ").slice(0, 16);
  if (/_date$/.test(k2) || ["valid_from", "valid_to", "data_retention_until"].includes(k2)) return fmtDate(v);
  if (typeof v === "number") return fmtNum(v);
  return String(v);
}

// Complete field lists per record kind: the detail sheet shows EVERY
// field in a fixed order, empty ones as "-", so nothing is hidden just
// because it has no value yet (Owner review 2026-11-03).
const DETAIL_SPECS = {
  zones: ["code", "name", "status", "puc_code", "puc_status", "vsic_code", "sector_category", "market_scope", "primary_species", "scientific_name", "crop_group", "area_ha", "initial_declared_area_ha", "province", "district", "ward", "address", "season", "water_source", "managing_entity", "owner_actor_code", "farm_scale_tier", "submission_channel", "application_received_at", "issue_date", "issuing_authority", "post_inspect_due_date", "valid_from", "valid_to", "dist_to_residential_m", "dist_to_sensitive_zone_m", "bee_site_min_dist_km"],
  mother_plants: ["code", "species", "variety", "scientific_name", "cultivar_code", "zone_code", "planting_year", "origin", "owner_manager", "recognition_no", "valid_to", "status"],
  actors: ["code", "name", "actor_type", "gln_code", "gs1_role_ai", "parent_code", "legal_id", "legal_id_hash", "forestry_enterprise_class", "province_code", "district_code", "commune_code", "address", "phone", "email", "is_group_leader", "ics_training_completed", "valid_from", "valid_to", "status"],
  spatial_units: ["code", "name", "unit_type", "operator_code", "province_code", "commune_code", "national_land_parcel_id", "map_sheet_number", "parcel_number", "area_m2", "land_tenure_doc_type", "land_cert_serial", "land_legal_owner_name", "owner_consent_doc_url", "earth_terrace_compliant", "forest_origin_type", "aquaculture_water_type", "vessel_reg_number", "vessel_length_max_m", "tech_safety_cert_no", "vms_device_serial", "valid_from", "valid_to", "status"],
  zone_parcel_links: ["zone_code", "parcel_code", "registered_area_m2", "membership_status", "joined_date", "left_date", "status"],
  input_lots: ["code", "name", "category", "brand_name", "substance_code", "vn_registration_number", "batch_no", "purchase_invoice_no", "qcvn_scheme_id", "supplier_code", "purchase_date", "quantity", "unit", "phi_days", "expiry_date", "status"],
  crop_plans: ["code", "name", "crop_name", "zone_code", "plant_code", "parcel_code", "variety_name", "seed_origin", "seed_origin_doc", "planting_density", "forest_harvest_plan_no", "departure_port_code", "arrival_port_code", "start_date", "end_date", "target_yield_kg", "status"],
  lots: ["code", "zone_code", "plan_code", "harvest_date", "farmer_code", "parcel_code", "weigh_slip_number", "quantity", "unit", "quality_grade", "harvested_by", "expiry_date", "traceability_code", "data_retention_until", "status"],
  packing_lots: ["code", "facility_code", "phc_code", "product_name", "food_safety_cert_id", "carcass_serial_id", "ecdt_cc_cert_number", "cites_permit_number", "output_weight_kg", "yield_norm_ratio", "storage_type", "packed_at", "expiry_date", "status"],
  traceability_records: ["traceability_code", "product_name", "product_image_url", "business_unit_name", "business_unit_address", "production_event_time", "brand_trademark_serial", "expiration_date", "packaging_unit_code", "data_carrier_type", "sync_status", "synced_at", "data_retention_until", "status"],
  phi_validations: ["lot_code", "plan_code", "validation_outcome", "max_safe_harvest_date", "actual_harvest_date", "last_treatment_ref"],
  field_events: ["event_type", "plan_code", "zone_code", "occurred_at", "input_lot_code", "phi_days", "safe_harvest_date", "dosage_concentration", "total_quantity_applied", "application_method", "crop_animal_growth_stage", "target_pest_disease_reason", "fruit_bagging_count", "device", "notes", "actor"],
  packaging_units: ["code", "packing_lot_code", "level", "gtin_code", "sscc_code", "cites_specimen_mark_code", "package_spec", "units_count", "status"],
  cte_stages: ["stage_no", "stage_name", "traceability_code", "product_trace_code", "location_trace_code", "batch_lot_number", "event_time", "scheme_code"],
};

function openDetail(title, rec, kind) {
  $("#sheetTitle").textContent = title;
  const spec = DETAIL_SPECS[kind] || [];
  const internal = new Set(["id", "tenant_id", "data", "created_at", "updated_at"]);
  const row = (k2, v) => `<div class="drow"><span>${esc(DETAIL_LABELS[k2] || k2)}</span><b>${v == null || v === "" ? "—" : esc(fmtDetailVal(k2, v))}</b></div>`;
  let rows = spec.map((k2) => row(k2, rec[k2])).join("");
  const seen = new Set([...internal, ...spec]);
  rows += Object.entries(rec).filter(([k2]) => !seen.has(k2)).map(([k2, v]) => row(k2, v)).join("");
  if (rec.created_at) rows += row("created_at", rec.created_at);
  if (rec.updated_at) rows += row("updated_at", rec.updated_at);
  $("#sheetForm").innerHTML = `<div class="dlist">${rows}</div>
    <div class="form-actions"><button type="button" class="btn btn-primary" id="sheetCancel">Đóng</button></div>`;
  sheetSubmit = null;
  sheetOnCancel = null;
  $("#sheetBackdrop").hidden = false;
  $("#sheet").hidden = false;
  $("#sheetCancel").onclick = closeSheet;
}

function wireCardDetails(container, items, titleOf, kind) {
  container.querySelectorAll("[data-card]").forEach((card) => {
    card.addEventListener("click", (ev) => {
      if (ev.target.closest("button, a")) return;
      const rec = items.find((x) => String(x.code ?? x.id) === card.dataset.card);
      if (rec) openDetail(titleOf(rec), rec, kind);
    });
  });
}

function confirmDelete(label, path, kinds) {
  openSheet(`Xoá ${label}?`, [
    { k: "__note", type: "note", label: "Bản ghi sẽ bị xoá khỏi danh mục và thao tác được ghi vào nhật ký kiểm toán. Nếu bản ghi đang được dữ liệu khác tham chiếu, hệ thống sẽ từ chối xoá." },
  ], async () => {
    await T(path, { method: "DELETE" });
    (kinds || []).forEach(invalidate);
    toast("Đã xoá " + label);
    navigate(state.view);
  });
}
$("#sheetBackdrop").addEventListener("click", closeSheet);
$("#sheetForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!sheetSubmit) return;
  const fd = new FormData(e.target);
  const payload = {};
  for (const f of sheetSubmit.fields) {
    let v = fd.get(f.k);
    if (v === null) continue;
    v = String(v).trim();
    if (v === "") continue;
    payload[f.k] = f.type === "number" ? Number(v) : f.type === "bool" ? v === "true" : v;
  }
  const btn = e.target.querySelector('[type="submit"]');
  btn.disabled = true; btn.textContent = "Đang lưu…";
  try {
    await sheetSubmit.onSubmit(payload);
    invalidate("audit");
    sheetOnCancel = null;
    closeSheet();
    toast("Đã lưu thành công.");
    navigate(state.view, true);
  } catch (err) {
    toast(err.message, true);
    btn.disabled = false; btn.textContent = "Lưu lại";
  }
});

/* ---------------- navigation ---------------- */
const NAV = [
  { id: "dashboard", ic: "🏠", label: "Tổng quan" },
  { id: "zones", ic: "🗺️", label: "Vùng" },
  { id: "plants", ic: "🌳", label: "Cây" },
  { id: "plans", ic: "📅", label: "Mùa vụ" },
  { id: "lots", ic: "📦", label: "Lô" },
  { id: "packing", ic: "🏭", label: "Đóng gói" },
  { id: "inputs", ic: "🧪", label: "Vật tư" },
  { id: "parcels", ic: "🧩", label: "Thửa đất" },
  { id: "actors", ic: "🧑‍🌾", label: "Chủ thể" },
  { id: "philogs", ic: "🛡️", label: "Kiểm tra PHI" },
  { id: "users", ic: "👥", label: "Người dùng" },
  { id: "tenants", ic: "🏢", label: "Tenant" },
  { id: "settings", ic: "⚙️", label: "Cài đặt" },
];
const TABS = ["dashboard", "zones", "plants", "plans", "lots", "users"];
const state = { view: "dashboard", health: null, cache: {} };

function paintNav() {
  $("#sideNav").innerHTML = NAV.map((n) =>
    `<button type="button" data-nav="${n.id}" class="${state.view === n.id ? "active" : ""}">
       <span class="ic">${n.ic}</span>${n.label}</button>`).join("");
  $("#tabBar").innerHTML = TABS.map((id) => {
    const n = NAV.find((x) => x.id === id);
    return `<button type="button" data-nav="${id}" class="${state.view === id ? "active" : ""}">
      <span class="ic">${n.ic}</span>${n.label}</button>`;
  }).join("") + `<button type="button" data-nav="more" class="${["more", "settings", "tenants", "packing", "inputs", "parcels", "actors", "philogs"].includes(state.view) ? "active" : ""}">
      <span class="ic">☰</span>Khác</button>`;
  document.querySelectorAll("[data-nav]").forEach((b) =>
    b.addEventListener("click", () => navigate(b.dataset.nav)));
  const chip = `<span class="dot"></span><span>${esc(store.tenant || "chưa kết nối")}</span>`;
  $("#tenantChipTop").innerHTML = chip;
  $("#tenantChipSide").innerHTML = chip;
  $("#tenantChipTop").onclick = () => navigate("settings");
  $("#tenantChipSide").onclick = () => navigate("settings");
}

const VIEWS = {};
function navigate(view, force = false) {
  if (state.view === view && !force) { /* still re-render on tab tap */ }
  state.view = view;
  paintNav();
  window.scrollTo({ top: 0 });
  VIEWS[view]();
}
function skeleton(n = 3) {
  return `<div class="grid">${Array.from({ length: n }, () => `<div class="skel"></div>`).join("")}</div>`;
}
function banner(err) {
  return `<div class="banner red"><span>⚠️</span><span>${esc(err.message || err)}</span></div>`;
}
function emptyState(icon, title, sub) {
  return `<div class="empty"><div class="big">${icon}</div><b>${esc(title)}</b>${esc(sub || "")}</div>`;
}
function fab(label, onclick) {
  const b = document.createElement("button");
  b.className = "fab"; b.type = "button"; b.textContent = "+"; b.title = label;
  b.onclick = onclick;
  $("#view").appendChild(b);
}
function chipFor(status) {
  const map = { ACTIVE: "", ALIVE: "", RUNNING: "sky", IN_STOCK: "", DRAFT: "grey", ENDED: "violet", SUSPENDED: "red",
    PASSED_SAFE: "", BLOCKED_VIOLATION_PHI: "red", CONDITIONAL_LAB_TEST_REQUIRED: "amber" };
  return `<span class="chip ${map[status] ?? "grey"}">${esc(status || "—")}</span>`;
}
// Stale-while-revalidate cache (T-030): lists persist on this device per
// tenant, so reopening the app renders instantly from the last known data
// while a background refresh catches up — the free-tier Worker's cold
// isolates (2-5 s per fresh isolate, measured 2026-11-04) then cost no
// visible waiting on repeat visits.
const cacheKey = () => "iaict_cache_v1_" + (store.tenant || "");
function persistCache() {
  try { localStorage.setItem(cacheKey(), JSON.stringify(state.cache)); } catch { /* quota */ }
}
function loadPersistedCache() {
  try {
    const raw = localStorage.getItem(cacheKey());
    if (raw) state.cache = { ...JSON.parse(raw), ...state.cache };
  } catch { /* ignore */ }
}
function dropPersistedCache() {
  try { localStorage.removeItem(cacheKey()); } catch { /* ignore */ }
}
const sheetOpen = () => { const sh = $("#sheet"); return !!sh && !sh.hidden; };
const refreshingKinds = {};
function refreshKind(kind, path) {
  if (refreshingKinds[kind]) return;
  refreshingKinds[kind] = true;
  T(path).then((res) => {
    state.cache[kind] = { at: Date.now(), data: res.items ?? res };
    persistCache();
    if (state.view && !sheetOpen()) navigate(state.view, true);
  }).catch(() => {}).finally(() => { delete refreshingKinds[kind]; });
}
async function ensure(kind, path, maxAgeMs = 60000) {
  const c = state.cache[kind];
  if (c && Date.now() - c.at < maxAgeMs) return c.data;
  if (c) { refreshKind(kind, path); return c.data; }  // stale: serve + refresh
  const data = (await T(path)).items;
  state.cache[kind] = { at: Date.now(), data };
  persistCache();
  return data;
}

// Warm every main list once after sign-in so screen switches render from
// cache instead of waiting on a (possibly cold) Worker each time; a light
// /health ping every 4 minutes while the app is open improves the odds the
// next real request lands on a warm isolate (T-027).
let warmStarted = false;
function prefetchAll() {
  const jobs = [["zones", "/zones"], ["plants", "/mother-plants"], ["plans", "/crop-plans"],
    ["events", "/field-events"], ["lots", "/lots"], ["actors", "/actors"],
    ["inputs", "/input-lots"], ["parcels", "/spatial-units"], ["zlinks", "/zone-parcel-links"],
    ["packing", "/packing-lots"], ["trecords", "/traceability-records"],
    ["phi", "/phi-validations"], ["users", "/users"], ["audit", "/audit"],
    ["zhistory", "/zone-status-history"]];
  jobs.forEach(([k, pth]) => { if (!state.cache[k]) ensure(k, pth).catch(() => {}); });
  if (!warmStarted) {
    warmStarted = true;
    setInterval(() => { if (!document.hidden && store.tenant) api("/health").catch(() => {}); }, 240000);
  }
}
function invalidate(...kinds) { kinds.forEach((k) => delete state.cache[k]); persistCache(); }

/* ---------------- dashboard ---------------- */
VIEWS.dashboard = async () => {
  const el = $("#view");
  const paint = (dash) => {
    const health = { env: dash.env, storage: dash.storage, version: dash.version };
    state.health = health;
    const failed = [];
    const cnt = (n) => (typeof n === "number" ? n : "—");
    const zones = dash.counts?.zones, plants = dash.counts?.mother_plants;
    const plans = dash.counts?.crop_plans, lots = dash.counts?.lots;
    const audit = dash.recent_audit || [];
    el.innerHTML = `
      <section class="hero">
        <h1>Xin chào, ${esc(store.actor || "bạn")} 👋</h1>
        <p>Đơn vị <b>${esc(store.tenant)}</b> — tổng quan sản xuất hôm nay.</p>
        <div class="hero-meta">
          <span class="pill">🌐 Môi trường: ${esc(health?.env || "beta")}</span>
          <span class="pill">🗄️ Lưu trữ: ${esc(health?.storage || "—")}</span>
          <span class="pill">⚙️ Phiên bản: ${esc(health?.version || "—")}</span>
        </div>
      </section>
      ${failed.length ? `<div class="banner"><span>⚠️</span><span>Chưa tải được: <b>${esc(failed.join(", "))}</b> (máy chủ đang bận). Các mục khác vẫn xem được — <a href="#" id="dashRetry">thử tải lại</a>.</span></div>` : ""}
      <div class="grid stats">
        <button class="stat-card" data-go="zones"><span class="ic">🗺️</span><b>${cnt(zones)}</b><span>Vùng nguyên liệu</span></button>
        <button class="stat-card" data-go="plants"><span class="ic">🌳</span><b>${cnt(plants)}</b><span>Cây đầu dòng</span></button>
        <button class="stat-card" data-go="plans"><span class="ic">📅</span><b>${cnt(plans)}</b><span>Kế hoạch mùa vụ</span></button>
        <button class="stat-card" data-go="lots"><span class="ic">📦</span><b>${cnt(lots)}</b><span>Lô thu hoạch</span></button>
      </div>
      <div class="section-head"><h2>Hoạt động gần đây</h2><span class="hint">nhật ký hệ thống (audit)</span></div>
      ${audit.length ? `<div class="list">${audit.map((a) => `
        <div class="card"><div class="thumb sky">🧾</div><div class="body">
          <div class="title">${esc(a.action)} <span class="chip ${a.outcome === "OK" ? "" : "amber"}">${esc(a.outcome)}</span></div>
          <div class="sub">Đối tượng: ${esc(a.target)} · bởi ${esc(a.actor)}</div>
          <div class="meta"><span>🕒 ${fmtTs(a.ts)}</span></div>
        </div></div>`).join("")}</div>`
      : emptyState("🧾", "Chưa có hoạt động nào", "Các thao tác tạo/cập nhật sẽ được ghi lại tại đây.")}`;
    el.querySelectorAll("[data-go]").forEach((b) => b.onclick = () => navigate(b.dataset.go));
    const retry = $("#dashRetry");
    if (retry) retry.onclick = (e) => { e.preventDefault(); state.cache = {}; dropPersistedCache(); navigate("dashboard", true); };
  };
  const entry = state.cache.dashboard;
  if (entry) {
    // Instant render from the persisted snapshot; refresh behind if stale.
    paint(entry.data);
    prefetchAll();
    if (Date.now() - entry.at > 60000 && !refreshingKinds.dashboard) {
      refreshingKinds.dashboard = true;
      T("/dashboard").then((fresh) => {
        state.cache.dashboard = { at: Date.now(), data: fresh };
        persistCache();
        if (state.view === "dashboard" && !sheetOpen()) navigate("dashboard", true);
      }).catch(() => {}).finally(() => { delete refreshingKinds.dashboard; });
    }
    return;
  }
  el.innerHTML = skeleton(4);
  try {
    // One summary call (audit T-021, pack P1): counts + recent audit +
    // service info in a single request instead of health + 4 lists + audit.
    const dash = await T("/dashboard");
    state.cache.dashboard = { at: Date.now(), data: dash };
    persistCache();
    paint(dash);
    prefetchAll();
  } catch (err) {
    el.innerHTML = banner(err) + emptyState("🔌", "Chưa kết nối được dữ liệu",
      "Kiểm tra mã tenant và người dùng trong mục Cài đặt, hoặc nhờ quản trị platform kiểm tra trạng thái tenant.");
  }
};

/* ---------------- zones ---------------- */
VIEWS.zones = async () => {
  const el = $("#view");
  el.innerHTML = `<div class="section-head"><h2>🗺️ Vùng nguyên liệu</h2>
    <button class="btn btn-ghost btn-sm" id="reload">↻ Làm mới</button></div>` + (state.cache.zones ? "" : skeleton(3));
  $("#reload").onclick = () => { invalidate("zones", "zhistory"); navigate("zones", true); };
  try {
    const items = await ensure("zones", "/zones");
    el.querySelectorAll(".skel").forEach((s) => s.remove());
    el.insertAdjacentHTML("beforeend", items.length ? `<div class="list">${items.map((z) => `
      <div class="card" data-card="${esc(z.code)}"><div class="thumb">🗺️</div><div class="body">
        <div class="title">${esc(z.name || z.code)} ${chipFor(z.status)}</div>
        <div class="sub">Mã vùng: <b>${esc(z.code)}</b>${z.crop_group ? ` · Nhóm cây: ${esc(z.crop_group)}` : ""}</div>
        <div class="meta">
          ${z.area_ha != null ? `<span>📐 ${fmtNum(z.area_ha)} ha</span>` : ""}
          ${z.puc_code ? `<span>🏷️ MSVT ${esc(z.puc_code)}</span>` : ""}
          ${z.primary_species ? `<span>🌱 ${esc(z.primary_species)}</span>` : ""}
          ${z.season ? `<span>🗓️ ${esc(z.season)}</span>` : ""}
          ${z.water_source ? `<span>💧 ${esc(z.water_source)}</span>` : ""}
          ${z.address ? `<span>📍 ${esc(z.address)}</span>` : ""}
        </div>
        <div style="margin-top:8px"><button class="btn btn-ghost btn-sm" data-edit-zone="${esc(z.code)}">✏️ Sửa</button> <button class="btn btn-ghost btn-sm" data-del-zone="${esc(z.code)}">🗑️ Xoá</button> <button class="btn btn-ghost btn-sm" data-zhist="${esc(z.code)}">🕘 Lịch sử trạng thái mã</button></div>
        <div class="cte-box" hidden style="margin-top:8px"></div>
        </div></div>`).join("")}</div>`
      : emptyState("🗺️", "Chưa có vùng nào", "Bấm nút + để tạo vùng nguyên liệu đầu tiên."));
    el.querySelectorAll("[data-edit-zone]").forEach((b) => b.onclick = async () => {
      const z = items.find((x) => x.code === b.dataset.editZone);
      if (!z) return;
      const actors = await ensure("actors", "/actors").catch(() => []);
      openSheet(`Sửa vùng ${z.code}`, [
        { k: "name", label: "Tên vùng", def: z.name || "" },
        { k: "area_ha", label: "Diện tích (ha)", type: "number", step: "0.01", def: z.area_ha ?? "" },
        { k: "puc_code", label: "Mã số vùng trồng (PUC)", def: z.puc_code || "" },
        { k: "puc_status", label: "Trạng thái mã số vùng trồng", type: "select", def: z.puc_status || "", options: PUC_STATUSES },
        { k: "sector_category", label: "Ngành / lĩnh vực", def: z.sector_category || "" },
        { k: "market_scope", label: "Phạm vi thị trường", def: z.market_scope || "" },
        { k: "scientific_name", label: "Tên khoa học cây trồng chính", def: z.scientific_name || "" },
        { k: "issuing_authority", label: "Cơ quan cấp mã", def: z.issuing_authority || "" },
        { k: "owner_actor_code", label: "Chủ thể sở hữu vùng", type: "select", def: z.owner_actor_code || "",
          options: [{ v: "", t: "— Chưa gắn —" }, ...actors.map(fmtActorOpt)],
          addNew: quickActor,
          refreshOptions: async () => optOf(await ensure("actors", "/actors"), "— Chưa gắn —", fmtActorOpt) },
        { k: "province", label: "Tỉnh/TP", def: z.province || "" },
        { k: "district", label: "Quận/Huyện", def: z.district || "" },
        { k: "ward", label: "Xã/Phường", def: z.ward || "" },
        { k: "initial_declared_area_ha", label: "Diện tích khai báo ban đầu (ha)", type: "number", step: "0.01", def: z.initial_declared_area_ha ?? "" },
        { k: "valid_from", label: "Mã vùng trồng hiệu lực từ", type: "date", def: z.valid_from ? String(z.valid_from).slice(0, 10) : "" },
        { k: "valid_to", label: "Mã vùng trồng hiệu lực đến", type: "date", def: z.valid_to ? String(z.valid_to).slice(0, 10) : "" },
        { k: "dist_to_residential_m", label: "Khoảng cách tới khu dân cư (m)", type: "number", step: "0.1", def: z.dist_to_residential_m ?? "" },
        { k: "dist_to_sensitive_zone_m", label: "Khoảng cách tới vùng nhạy cảm (m)", type: "number", step: "0.1", def: z.dist_to_sensitive_zone_m ?? "" },
        { k: "bee_site_min_dist_km", label: "Khoảng cách tối thiểu tới điểm nuôi ong (km)", type: "number", step: "0.1", def: z.bee_site_min_dist_km ?? "" },
        { k: "farm_scale_tier", label: "Quy mô cơ sở chăn nuôi", type: "select", def: z.farm_scale_tier || "", options: FARM_TIERS },
        { k: "submission_channel", label: "Kênh nộp hồ sơ cấp mã", type: "select", def: z.submission_channel || "", options: SUBMIT_CHANNELS },
        { k: "application_received_at", label: "Thời điểm xã tiếp nhận hồ sơ", type: "datetime-local", def: z.application_received_at ? String(z.application_received_at).slice(0, 16) : "" },
        { k: "status_change_reason", label: "Lý do đổi trạng thái mã (khi sửa trạng thái)", placeholder: "vd: POST_INSPECTION_PASSED" },
        { k: "status_decision_doc", label: "Số văn bản quyết định đổi trạng thái" },
        { k: "status_remediation", label: "Biện pháp khắc phục (nếu bị đình chỉ)" },
        { k: "issue_date", label: "Ngày cấp mã vùng trồng", type: "date", def: z.issue_date || "" },
        { k: "post_inspect_due_date", label: "Hạn hậu kiểm mã vùng trồng", type: "date", def: z.post_inspect_due_date || "" },
        { k: "vsic_code", label: "Mã ngành VSIC", def: z.vsic_code || "" },
        { k: "primary_species", label: "Cây trồng chính", def: z.primary_species || "" },
        { k: "crop_group", label: "Nhóm cây", def: z.crop_group || "" },
        { k: "season", label: "Mùa vụ", def: z.season || "" },
        { k: "water_source", label: "Nguồn nước", def: z.water_source || "" },
        { k: "address", label: "Địa chỉ", def: z.address || "" },
        { k: "managing_entity", label: "Chủ thể quản lý", def: z.managing_entity || "" },
      ], async (p) => { await T(`/zones/${encodeURIComponent(z.code)}`, { method: "PATCH", body: p }); invalidate("zones", "zhistory"); });
    });
    wireCardDetails(el, items, (z) => `Vùng ${z.code}`, "zones");
    el.querySelectorAll("[data-zhist]").forEach((b) => b.onclick = async (ev) => {
      ev.stopPropagation();
      const box = b.closest(".card").querySelector(".cte-box");
      if (!box.hidden) { box.hidden = true; return; }
      box.hidden = false;
      box.innerHTML = `<div class="sub">Đang tải lịch sử…</div>`;
      try {
        const rows = (await ensure("zhistory", "/zone-status-history"))
          .filter((h) => h.zone_code === b.dataset.zhist);
        box.innerHTML = rows.length ? rows.map((h) => `
          <div class="sub" style="margin:3px 0">🕘 ${fmtTs(h.created_at)} — ${esc(h.previous_status || "∅")} → <b>${esc(h.new_status || "")}</b>
          ${h.trigger_reason_code ? `· Lý do: ${esc(h.trigger_reason_code)}` : ""}${h.decision_doc_number ? `· VB: ${esc(h.decision_doc_number)}` : ""} · bởi ${esc(h.changed_by || "")}</div>`).join("")
          : `<div class="sub">Chưa ghi nhận thay đổi trạng thái nào.</div>`;
      } catch (err) { box.innerHTML = banner(err); }
    });
    el.querySelectorAll("[data-del-zone]").forEach((b) => b.onclick = () =>
      confirmDelete(`vùng ${b.dataset.delZone}`, `/zones/${encodeURIComponent(b.dataset.delZone)}`, ["zones"]));
  } catch (err) { el.innerHTML = banner(err); }
  fab("Tạo vùng", async () => {
    const actors = await ensure("actors", "/actors").catch(() => []);
    openSheet("Tạo vùng nguyên liệu", [
    { k: "code", label: "Mã vùng", required: true, placeholder: "vd: Z-01" },
    { k: "name", label: "Tên vùng", required: true, placeholder: "vd: Khu A – Đà Lạt" },
    { k: "area_ha", label: "Diện tích (ha)", type: "number", step: "0.01", placeholder: "vd: 10.5" },
    { k: "puc_code", label: "Mã số vùng trồng (PUC)", placeholder: "vd: VN-66-650-24370-94-21" },
    { k: "puc_status", label: "Trạng thái mã số vùng trồng", type: "select", options: PUC_STATUSES },
    { k: "issue_date", label: "Ngày cấp mã vùng trồng", type: "date" },
    { k: "issuing_authority", label: "Cơ quan cấp mã", placeholder: "vd: Chi cục Trồng trọt và BVTV" },
    { k: "post_inspect_due_date", label: "Hạn hậu kiểm mã vùng trồng", type: "date" },
    { k: "valid_from", label: "Mã vùng trồng hiệu lực từ", type: "date" },
    { k: "valid_to", label: "Mã vùng trồng hiệu lực đến", type: "date" },
    { k: "vsic_code", label: "Mã ngành VSIC", placeholder: "vd: 0119" },
    { k: "sector_category", label: "Ngành / lĩnh vực", placeholder: "vd: Trồng trọt" },
    { k: "market_scope", label: "Phạm vi thị trường", placeholder: "vd: Nội địa, EU, Trung Quốc…" },
    { k: "scientific_name", label: "Tên khoa học cây trồng chính" },
    { k: "owner_actor_code", label: "Chủ thể sở hữu vùng", type: "select",
      options: [{ v: "", t: "— Chưa gắn —" }, ...actors.map(fmtActorOpt)],
      addNew: quickActor,
      refreshOptions: async () => optOf(await ensure("actors", "/actors"), "— Chưa gắn —", fmtActorOpt) },
    { k: "province", label: "Tỉnh/TP" },
    { k: "district", label: "Quận/Huyện" },
    { k: "ward", label: "Xã/Phường" },
    { k: "initial_declared_area_ha", label: "Diện tích khai báo ban đầu (ha)", type: "number", step: "0.01" },
    { k: "dist_to_residential_m", label: "Khoảng cách tới khu dân cư (m)", type: "number", step: "0.1" },
    { k: "dist_to_sensitive_zone_m", label: "Khoảng cách tới vùng nhạy cảm (m)", type: "number", step: "0.1" },
    { k: "bee_site_min_dist_km", label: "Khoảng cách tối thiểu tới điểm nuôi ong (km)", type: "number", step: "0.1" },
    { k: "farm_scale_tier", label: "Quy mô cơ sở chăn nuôi", type: "select", options: FARM_TIERS },
    { k: "submission_channel", label: "Kênh nộp hồ sơ cấp mã", type: "select", options: SUBMIT_CHANNELS },
    { k: "application_received_at", label: "Thời điểm xã tiếp nhận hồ sơ", type: "datetime-local" },
    { k: "primary_species", label: "Cây trồng chính", placeholder: "vd: Bưởi da xanh" },
    { k: "crop_group", label: "Nhóm cây", placeholder: "vd: Rau củ, Sầu riêng…" },
    { k: "season", label: "Mùa vụ", placeholder: "vd: Đông Xuân 2026" },
    { k: "water_source", label: "Nguồn nước", placeholder: "vd: Suối, Giếng khoan…" },
    { k: "address", label: "Địa chỉ", placeholder: "Thôn/xã/huyện" },
    { k: "managing_entity", label: "Chủ thể quản lý", placeholder: "Đội/nhóm phụ trách" },
  ], async (p) => { await T("/zones", { method: "POST", body: p }); invalidate("zones", "zhistory"); });
  });
};

/* ---------------- mother plants ---------------- */
VIEWS.plants = async () => {
  const el = $("#view");
  el.innerHTML = `<div class="section-head"><h2>🌳 Cây đầu dòng</h2>
    <button class="btn btn-ghost btn-sm" id="reload">↻ Làm mới</button></div>` + (state.cache.plants ? "" : skeleton(3));
  $("#reload").onclick = () => { invalidate("plants"); navigate("plants", true); };
  try {
    const items = await ensure("plants", "/mother-plants");
    el.querySelectorAll(".skel").forEach((s) => s.remove());
    el.insertAdjacentHTML("beforeend", items.length ? `<div class="list">${items.map((p) => `
      <div class="card" data-card="${esc(p.code)}"><div class="thumb">🌳</div><div class="body">
        <div class="title">${esc(p.species || p.code)} ${chipFor(p.status)}</div>
        <div class="sub">Mã cây: <b>${esc(p.code)}</b>${p.variety ? ` · Giống: ${esc(p.variety)}` : ""}</div>
        <div class="meta">
          ${p.zone_code ? `<span>🗺️ Vùng ${esc(p.zone_code)}</span>` : ""}
          ${p.planting_year ? `<span>🌱 Trồng năm ${esc(p.planting_year)}</span>` : ""}
          ${p.valid_to ? `<span>📜 Công nhận đến ${fmtDate(p.valid_to)}</span>` : ""}
          ${p.owner_manager ? `<span>👤 ${esc(p.owner_manager)}</span>` : ""}
        </div>
        <div style="margin-top:8px"><button class="btn btn-ghost btn-sm" data-edit-plant="${esc(p.code)}">✏️ Sửa</button> <button class="btn btn-ghost btn-sm" data-del-plant="${esc(p.code)}">🗑️ Xoá</button></div>
        </div></div>`).join("")}</div>`
      : emptyState("🌳", "Chưa có cây đầu dòng nào", "Bấm nút + để cấp mã cho cây/cụm cây đầu dòng."));
    el.querySelectorAll("[data-edit-plant]").forEach((b) => b.onclick = async () => {
      const pl = items.find((x) => x.code === b.dataset.editPlant);
      if (!pl) return;
      const zones = await ensure("zones", "/zones").catch(() => []);
      openSheet(`Sửa cây ${pl.code}`, [
        { k: "species", label: "Loài cây", def: pl.species || "" },
        { k: "variety", label: "Giống", def: pl.variety || "" },
        { k: "scientific_name", label: "Tên khoa học", def: pl.scientific_name || "" },
        { k: "zone_code", label: "Thuộc vùng", type: "select", def: pl.zone_code || "",
          options: [{ v: "", t: "— Không gắn vùng —" }, ...zones.map(fmtZoneOpt)],
          addNew: quickZone,
          refreshOptions: async () => optOf(await ensure("zones", "/zones"), "— Không gắn vùng —", fmtZoneOpt) },
        { k: "planting_year", label: "Năm trồng", type: "number", def: pl.planting_year ?? "" },
        { k: "valid_to", label: "Công nhận đến", type: "date", def: pl.valid_to || "" },
        { k: "cultivar_code", label: "Mã giống", def: pl.cultivar_code || "" },
        { k: "recognition_no", label: "Số quyết định công nhận", def: pl.recognition_no || "" },
        { k: "origin", label: "Nguồn gốc", def: pl.origin || "" },
        { k: "owner_manager", label: "Chủ sở hữu / người quản lý", def: pl.owner_manager || "" },
      ], async (p) => { await T(`/mother-plants/${encodeURIComponent(pl.code)}`, { method: "PATCH", body: p }); invalidate("plants"); });
    });
    wireCardDetails(el, items, (pl) => `Cây ${pl.code}`, "mother_plants");
    el.querySelectorAll("[data-del-plant]").forEach((b) => b.onclick = () =>
      confirmDelete(`cây ${b.dataset.delPlant}`, `/mother-plants/${encodeURIComponent(b.dataset.delPlant)}`, ["plants"]));
  } catch (err) { el.innerHTML = banner(err); }
  fab("Thêm cây đầu dòng", async () => {
    const zones = await ensure("zones", "/zones").catch(() => []);
    openSheet("Thêm cây đầu dòng", [
      { k: "code", label: "Mã cây (dùng cho QR)", required: true, placeholder: "vd: MPL-001" },
      { k: "species", label: "Loài cây", required: true, placeholder: "vd: Sầu riêng" },
      { k: "variety", label: "Giống", placeholder: "vd: Ri6, Monthong…" },
      { k: "scientific_name", label: "Tên khoa học", placeholder: "vd: Durio zibethinus" },
      { k: "zone_code", label: "Thuộc vùng", type: "select",
        options: [{ v: "", t: "— Không gắn vùng —" }, ...zones.map(fmtZoneOpt)],
        addNew: quickZone,
        refreshOptions: async () => optOf(await ensure("zones", "/zones"), "— Không gắn vùng —", fmtZoneOpt) },
      { k: "valid_to", label: "Công nhận đến", type: "date" },
      { k: "planting_year", label: "Năm trồng", type: "number", placeholder: "vd: 2019" },
      { k: "cultivar_code", label: "Mã giống" },
      { k: "recognition_no", label: "Số quyết định công nhận" },
      { k: "origin", label: "Nguồn gốc", placeholder: "Vườn ươm / xuất xứ" },
      { k: "owner_manager", label: "Chủ sở hữu / người quản lý" },
    ], async (p) => { await T("/mother-plants", { method: "POST", body: p }); invalidate("plants"); });
  });
};

/* ---------------- crop plans & field events ---------------- */
const EVENT_TYPES = [
  { v: "IRRIGATION", t: "💧 Tưới" }, { v: "FERTILIZING", t: "🧪 Bón phân" },
  { v: "SOIL", t: "🚜 Làm đất" }, { v: "PRUNING", t: "✂️ Tỉa cành" },
  { v: "PEST", t: "🐛 Xử lý sâu bệnh" }, { v: "INSPECTION", t: "🔎 Kiểm tra" },
  { v: "HARVEST", t: "🧺 Thu hoạch" }, { v: "OTHER", t: "📌 Khác" },
];
VIEWS.plans = async () => {
  const el = $("#view");
  el.innerHTML = `<div class="section-head"><h2>📅 Mùa vụ & nhật ký</h2>
    <button class="btn btn-ghost btn-sm" id="reload">↻ Làm mới</button></div>` + (state.cache.plans && state.cache.events ? "" : skeleton(4));
  $("#reload").onclick = () => { invalidate("plans", "events"); navigate("plans", true); };
  try {
    const settledP = await Promise.allSettled([
      ensure("plans", "/crop-plans"), ensure("events", "/field-events"),
    ]);
    if (settledP.every((r) => r.status === "rejected")) throw settledP[0].reason;
    const plans = settledP[0].status === "fulfilled" ? settledP[0].value : [];
    const events = settledP[1].status === "fulfilled" ? settledP[1].value : [];
    const partialFail = settledP.map((r, i) => (r.status === "rejected" ? ["Kế hoạch mùa vụ", "Nhật ký đồng ruộng"][i] : null)).filter(Boolean);
    el.querySelectorAll(".skel").forEach((s) => s.remove());
    el.insertAdjacentHTML("beforeend", `
      ${partialFail.length ? `<div class="banner"><span>⚠️</span><span>Chưa tải được: <b>${esc(partialFail.join(", "))}</b> (máy chủ đang bận) — bấm Làm mới để thử lại.</span></div>` : ""}
      <div class="section-head"><h2 style="font-size:15.5px">Kế hoạch mùa vụ</h2></div>
      ${plans.length ? `<div class="list">${plans.map((p) => `
        <div class="card"><div class="thumb violet">📅</div><div class="body">
          <div class="title">${esc(p.name || p.crop_name || p.code)} ${chipFor(p.status)}</div>
          <div class="sub">Mã: <b>${esc(p.code)}</b>${p.crop_name ? ` · Cây trồng: ${esc(p.crop_name)}` : ""}</div>
          <div class="meta">
            ${p.zone_code ? `<span>🗺️ ${esc(p.zone_code)}</span>` : ""}
            ${p.start_date ? `<span>▶️ ${fmtDate(p.start_date)}</span>` : ""}
            ${p.end_date ? `<span>⏹️ ${fmtDate(p.end_date)}</span>` : ""}
            ${p.target_yield_kg != null ? `<span>🎯 ${fmtNum(p.target_yield_kg)} kg</span>` : ""}
          </div></div></div>`).join("")}</div>`
      : emptyState("📅", "Chưa có kế hoạch nào", "Tạo kế hoạch mùa vụ để bắt đầu ghi nhật ký.")}
      <div class="section-head"><h2 style="font-size:15.5px">Nhật ký đồng ruộng</h2>
        <button class="btn btn-primary btn-sm" id="addEvent">+ Ghi nhật ký</button></div>
      ${events.length ? `<div class="list">${events.slice().reverse().map((e) => {
        const t = EVENT_TYPES.find((x) => x.v === e.event_type);
        return `<div class="card" data-card="${e.id}"><div class="thumb sky">${t ? t.t.split(" ")[0] : "📌"}</div><div class="body">
          <div class="title">${esc(t ? t.t : e.event_type || "Sự kiện")}</div>
          <div class="sub">${esc(e.notes || "")}</div>
          <div class="meta">
            ${e.plan_code ? `<span>📅 ${esc(e.plan_code)}</span>` : ""}
            ${e.zone_code ? `<span>🗺️ ${esc(e.zone_code)}</span>` : ""}
            <span>🕒 ${fmtTs(e.occurred_at || e.created_at)}</span>
            ${e.actor ? `<span>👤 ${esc(e.actor)}</span>` : ""}
          </div></div></div>`; }).join("")}</div>`
      : emptyState("📝", "Chưa có nhật ký nào", "Ghi lại tưới, bón, kiểm tra… để truy vết về sau.")}`);
    wireCardDetails(el, events, (e) => `Nhật ký · ${e.event_type || ""}`, "field_events");
    $("#addEvent").onclick = async () => {
      const [zones, inputs] = await Promise.all([
        ensure("zones", "/zones").catch(() => []),
        ensure("inputs", "/input-lots").catch(() => []),
      ]);
      openSheet("Ghi nhật ký đồng ruộng", [
        { k: "event_type", label: "Loại sự kiện", type: "select", required: true, options: EVENT_TYPES },
        { k: "plan_code", label: "Kế hoạch mùa vụ", type: "select",
          options: [{ v: "", t: "— Không gắn kế hoạch —" }, ...plans.map((p) => ({ v: p.code, t: `${p.code} · ${p.name || p.crop_name || ""}` }))] },
        { k: "zone_code", label: "Vùng", type: "select",
          options: [{ v: "", t: "— Không gắn vùng —" }, ...zones.map((z) => ({ v: z.code, t: `${z.code} · ${z.name || ""}` }))] },
        { k: "input_lot_code", label: "Lô vật tư đã dùng", type: "select",
          options: [{ v: "", t: "— Không ghi vật tư —" }, ...inputs.map(fmtInputOpt)],
          addNew: quickInputLot,
          refreshOptions: async () => optOf(await ensure("inputs", "/input-lots"), "— Không ghi vật tư —", fmtInputOpt) },
        { k: "phi_days", label: "Số ngày cách ly PHI (để trống = lấy theo lô vật tư)", type: "number", step: "1" },
        { k: "dosage_concentration", label: "Liều lượng / nồng độ", placeholder: "vd: 0.5 lít/ha, 2g/lít…" },
        { k: "total_quantity_applied", label: "Tổng lượng đã dùng", placeholder: "vd: 3.5 lít" },
        { k: "application_method", label: "Phương pháp áp dụng", placeholder: "vd: Phun áp lực, Tưới nhỏ giọt…" },
        { k: "crop_animal_growth_stage", label: "Giai đoạn sinh trưởng", placeholder: "vd: Ra hoa, Nuôi trái…" },
        { k: "target_pest_disease_reason", label: "Đối tượng / lý do xử lý", placeholder: "vd: Rệp sáp, thán thư…" },
        { k: "fruit_bagging_count", label: "Số trái đã bao (nếu có)", type: "number", step: "1" },
        { k: "occurred_at", label: "Thời gian thực hiện", type: "datetime-local" },
        { k: "notes", label: "Ghi chú", type: "textarea", placeholder: "Mô tả công việc, vật tư đã dùng…" },
        { k: "device", label: "Thiết bị", placeholder: "vd: Máy bơm, Drone…" },
      ], async (p) => {
        if (p.occurred_at) p.occurred_at = new Date(p.occurred_at).toISOString();
        p.actor = store.actor;
        await T("/field-events", { method: "POST", body: p });
        invalidate("events");
      });
    };
  } catch (err) { el.innerHTML = banner(err); }
  fab("Tạo kế hoạch mùa vụ", async () => {
    const [zones, plants, parcels] = await Promise.all([
      ensure("zones", "/zones").catch(() => []), ensure("plants", "/mother-plants").catch(() => []),
      ensure("parcels", "/spatial-units").catch(() => []),
    ]);
    openSheet("Tạo kế hoạch mùa vụ", [
      { k: "code", label: "Mã kế hoạch", required: true, placeholder: "vd: PLAN-2026" },
      { k: "name", label: "Tên kế hoạch", placeholder: "vd: Vụ rau Đông Xuân" },
      { k: "crop_name", label: "Cây trồng", placeholder: "vd: Xà lách, Cà chua…" },
      { k: "zone_code", label: "Vùng canh tác", type: "select",
        options: [{ v: "", t: "— Chọn vùng —" }, ...zones.map(fmtZoneOpt)],
        addNew: quickZone,
        refreshOptions: async () => optOf(await ensure("zones", "/zones"), "— Chọn vùng —", fmtZoneOpt) },
      { k: "plant_code", label: "Cây đầu dòng liên quan", type: "select",
        options: [{ v: "", t: "— Không gắn cây —" }, ...plants.map(fmtPlantOpt)],
        addNew: quickPlant,
        refreshOptions: async () => optOf(await ensure("plants", "/mother-plants"), "— Không gắn cây —", fmtPlantOpt) },
      { k: "parcel_code", label: "Thửa đất canh tác", type: "select",
        options: [{ v: "", t: "— Không gắn thửa —" }, ...parcels.map(fmtParcelOpt)],
        addNew: quickParcel,
        refreshOptions: async () => optOf(await ensure("parcels", "/spatial-units"), "— Không gắn thửa —", fmtParcelOpt) },
      { k: "variety_name", label: "Tên giống", placeholder: "vd: Ri6, ST25…" },
      { k: "seed_origin", label: "Nguồn gốc giống", placeholder: "vd: Viện Cây ăn quả miền Nam" },
      { k: "start_date", label: "Ngày bắt đầu", type: "date" },
      { k: "end_date", label: "Ngày kết thúc dự kiến", type: "date" },
      { k: "target_yield_kg", label: "Mục tiêu sản lượng (kg)", type: "number", step: "0.1" },
      { k: "planting_density", label: "Mật độ trồng (cây/ha)", type: "number", step: "0.1" },
      { k: "seed_origin_doc", label: "Hồ sơ nguồn gốc giống", placeholder: "Số giấy chứng nhận / hóa đơn giống" },
      { k: "forest_harvest_plan_no", label: "Số VB phê duyệt PA khai thác rừng (nếu có)" },
      { k: "departure_port_code", label: "Mã cảng xuất bến (thủy sản, nếu có)" },
      { k: "arrival_port_code", label: "Mã cảng cập bến (thủy sản, nếu có)" },
      { k: "status", label: "Trạng thái", type: "select", options: [
        { v: "DRAFT", t: "Dự thảo" }, { v: "RUNNING", t: "Đang chạy" }, { v: "ENDED", t: "Đã kết thúc" }] },
    ], async (p) => { await T("/crop-plans", { method: "POST", body: p }); invalidate("plans"); });
  });
};

/* ---------------- lots ---------------- */
VIEWS.lots = async () => {
  const el = $("#view");
  el.innerHTML = `<div class="section-head"><h2>📦 Lô thu hoạch</h2>
    <button class="btn btn-ghost btn-sm" id="reload">↻ Làm mới</button></div>` + (state.cache.lots ? "" : skeleton(3));
  $("#reload").onclick = () => { invalidate("lots"); navigate("lots", true); };
  try {
    const items = await ensure("lots", "/lots");
    el.querySelectorAll(".skel").forEach((s) => s.remove());
    el.insertAdjacentHTML("beforeend", items.length ? `<div class="list">${items.map((l) => `
      <div class="card" data-card="${esc(l.code)}"><div class="thumb amber">📦</div><div class="body">
        <div class="title">${esc(l.code)} ${chipFor(l.status)} ${l.quality_grade ? `<span class="chip amber">Loại ${esc(l.quality_grade)}</span>` : ""}</div>
        <div class="sub">${l.quantity != null ? `<b>${fmtNum(l.quantity)} ${esc(l.unit || "kg")}</b>` : ""}${l.harvest_date ? ` · Thu hoạch ${fmtDate(l.harvest_date)}` : ""}</div>
        <div class="meta">
          ${l.zone_code ? `<span>🗺️ ${esc(l.zone_code)}</span>` : ""}
          ${l.plan_code ? `<span>📅 ${esc(l.plan_code)}</span>` : ""}
          ${l.farmer_code ? `<span>🧑‍🌾 ${esc(l.farmer_code)}</span>` : ""}
          ${l.weigh_slip_number ? `<span>⚖️ ${esc(l.weigh_slip_number)}</span>` : ""}
          ${l.traceability_code ? `<span>🔎 ${esc(l.traceability_code)}</span>` : ""}
          ${l.harvested_by ? `<span>👤 ${esc(l.harvested_by)}</span>` : ""}
          ${l.expiry_date ? `<span>⏳ HSD ${fmtDate(l.expiry_date)}</span>` : ""}
        </div></div></div>`).join("")}</div>`
      : emptyState("📦", "Chưa có lô thu hoạch nào", "Bấm nút + để tạo lô từ vùng/kế hoạch đã thu hoạch."));
  } catch (err) { el.innerHTML = banner(err); }
  wireCardDetails(el, items, (l) => `Lô thu hoạch ${l.code}`, "lots");
  fab("Tạo lô thu hoạch", async () => {
    const [zones, plans, actors, parcels] = await Promise.all([
      ensure("zones", "/zones").catch(() => []), ensure("plans", "/crop-plans").catch(() => []),
      ensure("actors", "/actors").catch(() => []), ensure("parcels", "/spatial-units").catch(() => []),
    ]);
    openSheet("Tạo lô thu hoạch", [
      { k: "code", label: "Mã lô", required: true, placeholder: "vd: LOT-001" },
      { k: "zone_code", label: "Vùng thu hoạch", type: "select",
        options: [{ v: "", t: "— Chọn vùng —" }, ...zones.map((z) => ({ v: z.code, t: `${z.code} · ${z.name || ""}` }))] },
      { k: "plan_code", label: "Kế hoạch mùa vụ", type: "select",
        options: [{ v: "", t: "— Không gắn kế hoạch —" }, ...plans.map((p) => ({ v: p.code, t: `${p.code} · ${p.name || p.crop_name || ""}` }))] },
      { k: "harvest_date", label: "Ngày thu hoạch", type: "date" },
      { k: "harvest_time", label: "Giờ thu hoạch (nếu cần chi tiết)", type: "time" },
      { k: "farmer_code", label: "Nông hộ thu hoạch", type: "select",
        options: [{ v: "", t: "— Chọn nông hộ —" }, ...actors.map(fmtActorOpt)],
        addNew: quickActor,
        refreshOptions: async () => optOf(await ensure("actors", "/actors"), "— Chọn nông hộ —", fmtActorOpt) },
      { k: "parcel_code", label: "Thửa đất", type: "select",
        options: [{ v: "", t: "— Chọn thửa —" }, ...parcels.map(fmtParcelOpt)],
        addNew: quickParcel,
        refreshOptions: async () => optOf(await ensure("parcels", "/spatial-units"), "— Chọn thửa —", fmtParcelOpt) },
      { k: "weigh_slip_number", label: "Số phiếu cân", placeholder: "vd: WS-2026-0051" },
      { k: "quantity", label: "Sản lượng", type: "number", step: "0.01" },
      { k: "unit", label: "Đơn vị", type: "select", options: [
        { v: "kg", t: "kg" }, { v: "tấn", t: "tấn" }, { v: "thùng", t: "thùng" }, { v: "bao", t: "bao" }] },
      { k: "quality_grade", label: "Phân loại chất lượng", placeholder: "vd: A, B, VIP…" },
      { k: "harvested_by", label: "Người thu hoạch" },
      { k: "expiry_date", label: "Hạn dùng", type: "date" },
    ], async (p) => { await T("/lots", { method: "POST", body: p }); invalidate("lots"); });
  });
};

/* ---------------- packing & traceability ---------------- */
VIEWS.packing = async () => {
  const el = $("#view");
  el.innerHTML = `<div class="section-head"><h2>🏭 Đóng gói & truy xuất</h2>
    <button class="btn btn-ghost btn-sm" id="reload">↻ Làm mới</button></div>` + (state.cache.packing ? "" : skeleton(3));
  $("#reload").onclick = () => { invalidate("packing", "trecords"); navigate("packing", true); };
  try {
    const [plots, records] = await Promise.all([
      ensure("packing", "/packing-lots"), ensure("trecords", "/traceability-records")]);
    el.querySelectorAll(".skel").forEach((s) => s.remove());
    el.insertAdjacentHTML("beforeend",
      (plots.length ? `<div class="list">${plots.map((p) => `
      <div class="card" data-card="${esc(p.code)}"><div class="thumb amber">🏭</div><div class="body">
        <div class="title">${esc(p.product_name || p.code)} ${chipFor(p.status)}</div>
        <div class="sub">Lô đóng gói: <b>${esc(p.code)}</b>${p.phc_code ? ` · PHC: ${esc(p.phc_code)}` : ""}</div>
        <div class="meta">
          ${p.output_weight_kg != null ? `<span>⚖️ ${fmtNum(p.output_weight_kg)} kg thành phẩm</span>` : ""}
          ${p.facility_code ? `<span>🏢 ${esc(p.facility_code)}</span>` : ""}
          ${p.packed_at ? `<span>🗓️ ${esc(String(p.packed_at).slice(0, 10))}</span>` : ""}
        </div>
        <div style="margin-top:8px"><button class="btn btn-primary btn-sm" data-issue="${esc(p.code)}">🔎 Cấp mã truy xuất</button>
        <button class="btn btn-ghost btn-sm" data-edit-packing="${esc(p.code)}">✏️ Sửa</button>
        <button class="btn btn-ghost btn-sm" data-del-packing="${esc(p.code)}">🗑️ Xoá</button></div>
      </div></div>`).join("")}</div>`
        : emptyState("🏭", "Chưa có lô đóng gói nào", "Bấm nút + để tạo lô đóng gói từ các lô thu hoạch."))
      + `<div class="section-head" style="margin-top:18px"><h2 style="font-size:15.5px">🔎 Bản ghi truy xuất nguồn gốc</h2></div>`
      + (records.length ? `<div class="list">${records.map((r) => `
      <div class="card" data-card="${r.id}"><div class="thumb sky">🔎</div><div class="body">
        <div class="title">${esc(r.product_name || "Sản phẩm")}</div>
        <div class="sub" style="word-break:break-all">${esc(r.traceability_code || "")}</div>
        <div class="meta">
          ${r.business_unit_name ? `<span>🏢 ${esc(r.business_unit_name)}</span>` : ""}
          <span>${r.sync_status === "SYNCED_SUCCESS" ? "✅ Đã đồng bộ cổng quốc gia" : "⏳ Chờ đồng bộ cổng quốc gia"}</span>
          ${r.product_image_url ? "" : "<span>⚠️ Thiếu ảnh sản phẩm</span>"}
          ${r.data_retention_until ? `<span>🗄️ Lưu trữ tới ${fmtDate(r.data_retention_until)}</span>` : ""}
          ${r.synced_at ? `<span>🔄 Đồng bộ lúc ${fmtTs(r.synced_at)}</span>` : ""}
        </div>
        <div style="margin-top:8px"><button class="btn btn-ghost btn-sm" data-cte="${esc(r.traceability_code || "")}">🧬 Xem công đoạn</button></div>
        <div class="cte-box" hidden style="margin-top:8px"></div>
        </div></div>`).join("")}</div>`
        : emptyState("🔎", "Chưa có bản ghi truy xuất nào", "Cấp mã truy xuất từ một lô đóng gói để sinh bản ghi.")));
    el.querySelectorAll("[data-issue]").forEach((b) => b.onclick = () => issueTraceCode(b.dataset.issue));
    wireCardDetails(el, plots, (pk) => `Lô đóng gói ${pk.code}`, "packing_lots");
    el.querySelectorAll("[data-del-packing]").forEach((b) => b.onclick = () =>
      confirmDelete(`lô đóng gói ${b.dataset.delPacking}`, `/packing-lots/${encodeURIComponent(b.dataset.delPacking)}`, ["packing"]));
    el.querySelectorAll("[data-edit-packing]").forEach((b) => b.onclick = () => {
      const pk = plots.find((x) => x.code === b.dataset.editPacking);
      if (!pk) return;
      openSheet(`Sửa lô đóng gói ${pk.code}`, [
        { k: "product_name", label: "Tên sản phẩm", def: pk.product_name || "" },
        { k: "phc_code", label: "Mã số cơ sở đóng gói (PHC)", def: pk.phc_code || "" },
        { k: "food_safety_cert_id", label: "Số chứng nhận an toàn thực phẩm của cơ sở", def: pk.food_safety_cert_id || "" },
        { k: "carcass_serial_id", label: "Mã thân thịt (nếu là thịt)", def: pk.carcass_serial_id || "" },
        { k: "ecdt_cc_cert_number", label: "Số giấy chứng nhận nguồn gốc thủy sản (CC)", def: pk.ecdt_cc_cert_number || "" },
        { k: "cites_permit_number", label: "Số giấy phép CITES (nếu có)", def: pk.cites_permit_number || "" },
        { k: "output_weight_kg", label: "Khối lượng thành phẩm (kg)", type: "number", step: "0.01", def: pk.output_weight_kg ?? "" },
        { k: "yield_norm_ratio", label: "Định mức thu hồi (0–1)", type: "number", step: "0.01", def: pk.yield_norm_ratio ?? "" },
        { k: "storage_type", label: "Hình thức bảo quản", type: "select", def: pk.storage_type || "FRESH_AMBIENT", options: [
          { v: "FRESH_AMBIENT", t: "Tươi, nhiệt độ thường" }, { v: "CHILLED_COOL", t: "Mát lạnh" },
          { v: "FROZEN_PROCESSED", t: "Đông lạnh / chế biến" }] },
        { k: "expiry_date", label: "Hạn dùng", type: "date", def: pk.expiry_date ? String(pk.expiry_date).slice(0, 10) : "" },
      ], async (p) => { await T(`/packing-lots/${encodeURIComponent(pk.code)}`, { method: "PATCH", body: p }); invalidate("packing"); });
    });
    wireCardDetails(el, records, (r) => `Bản ghi truy xuất`, "traceability_records");
    el.querySelectorAll("[data-cte]").forEach((b) => b.onclick = async () => {
      const box = b.closest(".card").querySelector(".cte-box");
      if (!box.hidden) { box.hidden = true; return; }
      if (!box.dataset.loaded) {
        box.innerHTML = `<div class="sub">Đang tải công đoạn…</div>`; box.hidden = false;
        try {
          const stages = (await ensure("cte", "/cte-stages"))
            .filter((x) => x.traceability_code === b.dataset.cte)
            .sort((a, b2) => (a.stage_no || 0) - (b2.stage_no || 0));
          box.innerHTML = stages.length
            ? stages.map((x) => `<div class="sub" style="margin:3px 0">🧬 <b>${esc(x.stage_no ?? "")}. ${esc(x.stage_name || "")}</b>${x.location_trace_code ? ` · 📍 ${esc(x.location_trace_code)}` : ""}${x.event_time ? ` · 🕒 ${fmtTs(x.event_time)}` : ""}</div>`).join("")
            : `<div class="sub">Chưa có công đoạn nào được ghi cho mã này.</div>`;
          box.dataset.loaded = "1";
        } catch (err) { box.innerHTML = `<div class="sub">⚠️ ${esc(err.message || err)}</div>`; }
      } else box.hidden = false;
    });
  } catch (err) { el.innerHTML = banner(err); }
  fab("Tạo lô đóng gói", async () => {
    const actors = await ensure("actors", "/actors").catch(() => []);
    const facilityField = actors.length
      ? { k: "facility_code", label: "Cơ sở đóng gói", type: "select",
          options: [{ v: "", t: "— Chọn cơ sở —" }, ...actors.map(fmtActorOpt)],
          addNew: quickActor,
          refreshOptions: async () => optOf(await ensure("actors", "/actors"), "— Chọn cơ sở —", fmtActorOpt) }
      : { k: "facility_code", label: "Mã cơ sở đóng gói", placeholder: "vd: PHC-01" };
    openSheet("Tạo lô đóng gói", [
      { k: "code", label: "Mã lô đóng gói", required: true, placeholder: "vd: PK-1" },
      facilityField,
      { k: "phc_code", label: "Mã số cơ sở đóng gói (PHC)", placeholder: "vd: VN-PHC-66-019" },
      { k: "food_safety_cert_id", label: "Số chứng nhận an toàn thực phẩm của cơ sở" },
      { k: "carcass_serial_id", label: "Mã thân thịt (nếu là thịt)" },
      { k: "ecdt_cc_cert_number", label: "Số giấy chứng nhận nguồn gốc thủy sản (CC)" },
      { k: "cites_permit_number", label: "Số giấy phép CITES (nếu có)" },
      { k: "product_name", label: "Tên sản phẩm", placeholder: "vd: Bưởi da xanh loại 1" },
      { k: "output_weight_kg", label: "Khối lượng thành phẩm (kg)", type: "number", step: "0.01", required: true },
      { k: "yield_norm_ratio", label: "Định mức thu hồi (0–1)", type: "number", step: "0.01", placeholder: "vd: 0.85", required: true },
      { k: "storage_type", label: "Hình thức bảo quản", type: "select", options: [
        { v: "FRESH_AMBIENT", t: "Tươi, nhiệt độ thường" }, { v: "CHILLED_COOL", t: "Mát lạnh" },
        { v: "FROZEN_PROCESSED", t: "Đông lạnh / chế biến" }] },
      { k: "packed_at", label: "Thời gian đóng gói", type: "datetime-local" },
      { k: "expiry_date", label: "Hạn dùng", type: "date" },
    ], async (p) => { await T("/packing-lots", { method: "POST", body: p }); invalidate("packing"); });
  });
};

async function issueTraceCode(packingCode) {
  const lots = await ensure("lots", "/lots").catch(() => []);
  openSheet(`Cấp mã truy xuất · ${packingCode}`, [
    { k: "harvest_lot_code", label: "Lô thu hoạch đầu vào", type: "select", required: true,
      options: [{ v: "", t: "— Chọn lô thu hoạch —" }, ...lots.map((l) => ({ v: l.code, t: `${l.code} · ${l.quantity ?? "?"} ${l.unit || "kg"}` }))] },
    { k: "allocated_weight_kg", label: "Khối lượng đưa vào đóng gói (kg)", type: "number", step: "0.01", required: true },
    { k: "gtin_code", label: "Mã GTIN sản phẩm", required: true, placeholder: "vd: 08935049501234" },
    { k: "level", label: "Cấp đóng gói", type: "select", options: [
      { v: "SHIPPING_CASE_CARTON", t: "Thùng vận chuyển" }, { v: "RETAIL_UNIT", t: "Đơn vị bán lẻ" },
      { v: "PALLET", t: "Pallet" }, { v: "OTHER", t: "Khác" }] },
    { k: "sscc_code", label: "Mã SSCC (nếu có)", placeholder: "vd: 089350495000000018" },
    { k: "brand_trademark_serial", label: "Thương hiệu / số seri (nếu có)" },
    { k: "cites_specimen_mark_code", label: "Mã nhãn đánh dấu mẫu vật CITES (nếu có)" },
    { k: "product_image_url", label: "URL hình ảnh sản phẩm (trường bắt buộc TT 02/2024)", placeholder: "https://…" },
    { k: "package_spec", label: "Quy cách bao gói", placeholder: "vd: Thùng carton 10 kg" },
    { k: "units_count", label: "Số đơn vị bao gói", type: "number", step: "1" },
  ], async (p) => {
    if (!p.harvest_lot_code) throw new Error("Hãy chọn lô thu hoạch đầu vào.");
    try {
      await T("/packing-inputs", { method: "POST", body: {
        packing_lot_code: packingCode, harvest_lot_code: p.harvest_lot_code,
        allocated_weight_kg: p.allocated_weight_kg } });
    } catch (err) { if (err.status !== 409) throw err; } // already linked: continue
    const sku = "SKU-" + Date.now().toString(36).toUpperCase();
    await T("/packaging-units", { method: "POST", body: {
      code: sku, packing_lot_code: packingCode, level: p.level || "SHIPPING_CASE_CARTON",
      gtin_code: p.gtin_code, sscc_code: p.sscc_code,
      cites_specimen_mark_code: p.cites_specimen_mark_code,
      package_spec: p.package_spec, units_count: p.units_count } });
    await T("/traceability-records", { method: "POST", body: {
      packaging_unit_code: sku, product_image_url: p.product_image_url,
      brand_trademark_serial: p.brand_trademark_serial } });
    invalidate("packing", "trecords", "cte");
  });
}

/* ---------------- input lots (vat tu dau vao) ---------------- */
const INPUT_CATEGORIES = [
  { v: "PESTICIDE", t: "Thuốc bảo vệ thực vật" }, { v: "FERTILIZER", t: "Phân bón" },
  { v: "SEED", t: "Giống / hạt giống" }, { v: "FEED", t: "Thức ăn chăn nuôi/thủy sản" },
  { v: "OTHER", t: "Vật tư khác" },
];
VIEWS.inputs = async () => {
  const el = $("#view");
  el.innerHTML = `<div class="section-head"><h2>🧪 Vật tư đầu vào</h2>
    <button class="btn btn-ghost btn-sm" id="reload">↻ Làm mới</button></div>` + (state.cache.inputs ? "" : skeleton(3));
  $("#reload").onclick = () => { invalidate("inputs"); navigate("inputs", true); };
  try {
    const items = await ensure("inputs", "/input-lots");
    el.querySelectorAll(".skel").forEach((x) => x.remove());
    el.insertAdjacentHTML("beforeend", items.length ? `<div class="list">${items.map((i) => `
      <div class="card" data-card="${esc(i.code)}"><div class="thumb">🧪</div><div class="body">
        <div class="title">${esc(i.name || i.code)}</div>
        <div class="sub">Mã lô vật tư: <b>${esc(i.code)}</b>${i.substance_code ? ` · Hoạt chất: ${esc(i.substance_code)}` : ""}</div>
        <div class="meta">
          ${i.phi_days != null ? `<span>🛡️ Cách ly ${fmtNum(i.phi_days)} ngày</span>` : ""}
          ${i.batch_no ? `<span>🔖 Lô NSX ${esc(i.batch_no)}</span>` : ""}
          ${i.quantity != null ? `<span>⚖️ ${fmtNum(i.quantity)} ${esc(i.unit || "")}</span>` : ""}
          ${i.supplier_code ? `<span>🏢 ${esc(i.supplier_code)}</span>` : ""}
          ${i.expiry_date ? `<span>⏳ HSD ${fmtDate(i.expiry_date)}</span>` : ""}
        </div>
        <div style="margin-top:8px"><button class="btn btn-ghost btn-sm" data-edit-input="${esc(i.code)}">✏️ Sửa</button> <button class="btn btn-ghost btn-sm" data-del-input="${esc(i.code)}">🗑️ Xoá</button></div>
      </div></div>`).join("")}</div>`
      : emptyState("🧪", "Chưa có lô vật tư nào", "Bấm nút + để nhập lô thuốc/phân/giống đầu tiên — nhật ký đồng ruộng sẽ chọn được từ đây."));
    wireCardDetails(el, items, (i) => `Lô vật tư ${i.code}`, "input_lots");
    el.querySelectorAll("[data-del-input]").forEach((b) => b.onclick = () =>
      confirmDelete(`lô vật tư ${b.dataset.delInput}`, `/input-lots/${encodeURIComponent(b.dataset.delInput)}`, ["inputs"]));
    el.querySelectorAll("[data-edit-input]").forEach((b) => b.onclick = async () => {
      const it = items.find((x) => x.code === b.dataset.editInput);
      if (!it) return;
      const actors = await ensure("actors", "/actors").catch(() => []);
      openSheet(`Sửa lô vật tư ${it.code}`, [
        { k: "name", label: "Tên vật tư", def: it.name || "" },
        { k: "category", label: "Nhóm vật tư", type: "select", def: it.category || "OTHER", options: INPUT_CATEGORIES },
        { k: "substance_code", label: "Hoạt chất / thành phần", def: it.substance_code || "" },
        { k: "vn_registration_number", label: "Số đăng ký lưu hành VN", def: it.vn_registration_number || "" },
        { k: "batch_no", label: "Số lô nhà sản xuất", def: it.batch_no || "" },
        { k: "brand_name", label: "Thương hiệu", def: it.brand_name || "" },
        { k: "purchase_invoice_no", label: "Số hóa đơn mua", def: it.purchase_invoice_no || "" },
        { k: "qcvn_scheme_id", label: "Mã quy chuẩn (QCVN)", def: it.qcvn_scheme_id || "" },
        { k: "supplier_code", label: "Nhà cung cấp", type: "select", def: it.supplier_code || "",
          options: [{ v: "", t: "— Không ghi —" }, ...actors.map(fmtActorOpt)],
          addNew: quickActor,
          refreshOptions: async () => optOf(await ensure("actors", "/actors"), "— Không ghi —", fmtActorOpt) },
        { k: "quantity", label: "Số lượng nhập", type: "number", step: "0.01", def: it.quantity ?? "" },
        { k: "unit", label: "Đơn vị", def: it.unit || "" },
        { k: "phi_days", label: "Số ngày cách ly PHI (theo nhãn)", type: "number", step: "1", def: it.phi_days ?? "" },
        { k: "expiry_date", label: "Hạn dùng", type: "date", def: it.expiry_date ? String(it.expiry_date).slice(0, 10) : "" },
      ], async (p) => { await T(`/input-lots/${encodeURIComponent(it.code)}`, { method: "PATCH", body: p }); invalidate("inputs"); });
    });
  } catch (err) { el.innerHTML = banner(err); }
  fab("Nhập lô vật tư", async () => {
    const actors = await ensure("actors", "/actors").catch(() => []);
    openSheet("Nhập lô vật tư đầu vào", [
      { k: "code", label: "Mã lô vật tư", required: true, placeholder: "vd: VT-01" },
      { k: "name", label: "Tên vật tư", placeholder: "vd: Thuốc trừ sâu X" },
      { k: "category", label: "Nhóm vật tư", type: "select", options: INPUT_CATEGORIES },
      { k: "substance_code", label: "Hoạt chất / thành phần", placeholder: "vd: Abamectin" },
      { k: "vn_registration_number", label: "Số đăng ký lưu hành VN" },
      { k: "batch_no", label: "Số lô nhà sản xuất" },
      { k: "brand_name", label: "Thương hiệu" },
      { k: "purchase_invoice_no", label: "Số hóa đơn mua" },
      { k: "qcvn_scheme_id", label: "Mã quy chuẩn (QCVN)" },
      { k: "supplier_code", label: "Nhà cung cấp", type: "select",
        options: [{ v: "", t: "— Không ghi —" }, ...actors.map(fmtActorOpt)],
        addNew: quickActor,
        refreshOptions: async () => optOf(await ensure("actors", "/actors"), "— Không ghi —", fmtActorOpt) },
      { k: "purchase_date", label: "Ngày nhập", type: "date" },
      { k: "quantity", label: "Số lượng nhập", type: "number", step: "0.01" },
      { k: "unit", label: "Đơn vị", placeholder: "kg / lít / bao…" },
      { k: "phi_days", label: "Số ngày cách ly PHI (theo nhãn)", type: "number", step: "1" },
      { k: "expiry_date", label: "Hạn dùng", type: "date" },
    ], async (p) => { await T("/input-lots", { method: "POST", body: p }); invalidate("inputs"); });
  });
};

/* ---------------- spatial units & zone links ---------------- */
const UNIT_TYPES = [
  { v: "LAND_PARCEL", t: "Thửa đất" }, { v: "POND", t: "Ao nuôi" },
  { v: "FOREST_PLOT", t: "Lô rừng" }, { v: "GREENHOUSE", t: "Nhà kính / nhà lưới" },
  { v: "OTHER", t: "Khác" },
];
VIEWS.parcels = async () => {
  const el = $("#view");
  el.innerHTML = `<div class="section-head"><h2>🧩 Thửa đất & liên kết vùng</h2>
    <button class="btn btn-ghost btn-sm" id="reload">↻ Làm mới</button></div>` + (state.cache.parcels ? "" : skeleton(3));
  $("#reload").onclick = () => { invalidate("parcels", "zlinks"); navigate("parcels", true); };
  try {
    const [items, links] = await Promise.all([
      ensure("parcels", "/spatial-units"), ensure("zlinks", "/zone-parcel-links")]);
    el.querySelectorAll(".skel").forEach((x) => x.remove());
    el.insertAdjacentHTML("beforeend",
      (items.length ? `<div class="list">${items.map((u) => `
      <div class="card" data-card="${esc(u.code)}"><div class="thumb sky">🧩</div><div class="body">
        <div class="title">${esc(u.name || u.national_land_parcel_id || u.code)}</div>
        <div class="sub">Mã thửa: <b>${esc(u.code)}</b>${u.unit_type ? ` · ${esc(u.unit_type)}` : ""}</div>
        <div class="meta">
          ${u.area_m2 != null ? `<span>📐 ${fmtNum(u.area_m2)} m²</span>` : ""}
          ${u.parcel_number ? `<span>🔢 Thửa số ${esc(u.parcel_number)}</span>` : ""}
          ${u.map_sheet_number ? `<span>🗺️ Tờ bản đồ ${esc(u.map_sheet_number)}</span>` : ""}
          ${u.operator_code ? `<span>👤 ${esc(u.operator_code)}</span>` : ""}
        </div>
        <div style="margin-top:8px"><button class="btn btn-ghost btn-sm" data-edit-parcel="${esc(u.code)}">✏️ Sửa</button> <button class="btn btn-ghost btn-sm" data-del-parcel="${esc(u.code)}">🗑️ Xoá</button></div>
      </div></div>`).join("")}</div>`
        : emptyState("🧩", "Chưa có thửa đất nào", "Bấm nút + để khai thửa/ao/lô rừng đầu tiên."))
      + `<div class="section-head" style="margin-top:18px"><h2 style="font-size:15.5px">🔗 Thửa thuộc vùng</h2>
           <button class="btn btn-ghost btn-sm" id="addLink">+ Liên kết</button></div>`
      + (links.length ? `<div class="list">${links.map((l) => `
      <div class="card" data-card="${l.id}"><div class="thumb">🔗</div><div class="body">
        <div class="title">${esc(l.zone_code || "")} ↔ ${esc(l.parcel_code || "")} ${chipFor(l.membership_status)}</div>
        <div class="meta">
          ${l.registered_area_m2 != null ? `<span>📐 Đăng ký ${fmtNum(l.registered_area_m2)} m²</span>` : ""}
          ${l.joined_date ? `<span>🗓️ Từ ${fmtDate(l.joined_date)}</span>` : ""}
          ${l.left_date ? `<span>↩️ Rút ngày ${fmtDate(l.left_date)}</span>` : ""}
        </div>
        ${l.membership_status !== "WITHDRAWN_FROM_ZONE" ? `<div style="margin-top:8px"><button class="btn btn-ghost btn-sm" data-withdraw="${l.id}">↩️ Rút khỏi vùng</button></div>` : ""}
        </div></div>`).join("")}</div>`
        : emptyState("🔗", "Chưa có liên kết nào", "Liên kết thửa vào vùng để vùng trồng gồm đúng các thửa thành viên.")));
    wireCardDetails(el, items, (u) => `Thửa ${u.code}`, "spatial_units");
    wireCardDetails(el, links, (l) => `Liên kết ${l.zone_code || ""} ↔ ${l.parcel_code || ""}`, "zone_parcel_links");
    el.querySelectorAll("[data-withdraw]").forEach((b) => b.onclick = async (ev) => {
      ev.stopPropagation();
      const l = links.find((x) => String(x.id) === b.dataset.withdraw);
      if (!l) return;
      openSheet(`Rút thửa ${l.parcel_code} khỏi vùng ${l.zone_code}`, [
        { k: "note", type: "note", label: `Thao tác này ghi ngày rút = hôm nay và đặt trạng thái "Đã rút khỏi vùng". Liên kết vẫn được lưu để truy vết, không bị xoá.` },
      ], async () => {
        await T(`/zone-parcel-links/${l.id}/withdraw`, { method: "POST", body: {} });
        invalidate("zlinks");
        toast("Đã rút thửa khỏi vùng");
      });
    });
    el.querySelectorAll("[data-del-parcel]").forEach((b) => b.onclick = () =>
      confirmDelete(`thửa ${b.dataset.delParcel}`, `/spatial-units/${encodeURIComponent(b.dataset.delParcel)}`, ["parcels"]));
    el.querySelectorAll("[data-edit-parcel]").forEach((b) => b.onclick = async () => {
      const u = items.find((x) => x.code === b.dataset.editParcel);
      if (!u) return;
      const actors = await ensure("actors", "/actors").catch(() => []);
      openSheet(`Sửa thửa ${u.code}`, [
        { k: "name", label: "Tên thửa", def: u.name || "" },
        { k: "unit_type", label: "Loại đơn vị", type: "select", def: u.unit_type || "LAND_PARCEL", options: UNIT_TYPES },
        { k: "operator_code", label: "Người/hộ vận hành", type: "select", def: u.operator_code || "",
          addNew: quickActor,
          refreshOptions: async () => optOf(await ensure("actors", "/actors"), "— Không ghi —", fmtActorOpt),
          options: [{ v: "", t: "— Không ghi —" }, ...actors.map((a) => ({ v: a.code, t: `${a.code} · ${a.name || ""}` }))] },
        { k: "national_land_parcel_id", label: "Mã định danh thửa đất quốc gia", def: u.national_land_parcel_id || "" },
        { k: "map_sheet_number", label: "Số tờ bản đồ", def: u.map_sheet_number || "" },
        { k: "parcel_number", label: "Số thửa", def: u.parcel_number || "" },
        { k: "area_m2", label: "Diện tích (m²)", type: "number", step: "0.01", def: u.area_m2 ?? "" },
        { k: "land_tenure_doc_type", label: "Loại giấy tờ đất", def: u.land_tenure_doc_type || "" },
        { k: "land_cert_serial", label: "Số giấy chứng nhận", def: u.land_cert_serial || "" },
        { k: "land_legal_owner_name", label: "Chủ đất theo giấy tờ", def: u.land_legal_owner_name || "" },
        { k: "owner_consent_doc_url", label: "Văn bản đồng ý của chủ đất (URL)", def: u.owner_consent_doc_url || "" },
        { k: "earth_terrace_compliant", label: "Đã làm băng đất đồng mức (vùng dốc)", type: "bool", def: u.earth_terrace_compliant == null ? "" : String(u.earth_terrace_compliant), options: BOOL_OPTS },
        { k: "forest_origin_type", label: "Nguồn gốc rừng (nếu là lô rừng)", type: "select", def: u.forest_origin_type || "", options: FOREST_ORIGINS },
        { k: "aquaculture_water_type", label: "Loại hình mặt nước (nếu nuôi thủy sản)", type: "select", def: u.aquaculture_water_type || "", options: AQUA_WATERS },
        { k: "vessel_reg_number", label: "Số đăng ký tàu cá (nếu là tàu cá)", def: u.vessel_reg_number || "" },
        { k: "vessel_length_max_m", label: "Chiều dài lớn nhất tàu (m)", type: "number", step: "0.01", def: u.vessel_length_max_m ?? "" },
        { k: "tech_safety_cert_no", label: "Số GCN an toàn kỹ thuật tàu cá", def: u.tech_safety_cert_no || "" },
        { k: "vms_device_serial", label: "Số seri thiết bị giám sát hành trình (VMS)", def: u.vms_device_serial || "" },
      ], async (p) => { await T(`/spatial-units/${encodeURIComponent(u.code)}`, { method: "PATCH", body: p }); invalidate("parcels"); });
    });
    $("#addLink").onclick = async () => {
      const [zones, parcels] = await Promise.all([
        ensure("zones", "/zones").catch(() => []),
        ensure("parcels", "/spatial-units").catch(() => []),
      ]);
      openSheet("Liên kết thửa vào vùng", [
        { k: "zone_code", label: "Vùng", type: "select", required: true,
          options: [{ v: "", t: "— Chọn vùng —" }, ...zones.map(fmtZoneOpt)],
          addNew: quickZone,
          refreshOptions: async () => optOf(await ensure("zones", "/zones"), "— Chọn vùng —", fmtZoneOpt) },
        { k: "parcel_code", label: "Thửa đất", type: "select", required: true,
          options: [{ v: "", t: "— Chọn thửa —" }, ...parcels.map(fmtParcelOpt)],
          addNew: quickParcel,
          refreshOptions: async () => optOf(await ensure("parcels", "/spatial-units"), "— Chọn thửa —", fmtParcelOpt) },
        { k: "registered_area_m2", label: "Diện tích đăng ký trong vùng (m²)", type: "number", step: "0.01" },
        { k: "membership_status", label: "Trạng thái tham gia", type: "select", options: MEMBERSHIP_STATUSES },
        { k: "joined_date", label: "Ngày tham gia vùng", type: "date" },
      ], async (p) => {
        if (!p.zone_code || !p.parcel_code) throw new Error("Hãy chọn cả vùng và thửa đất.");
        await T("/zone-parcel-links", { method: "POST", body: p }); invalidate("zlinks");
      });
    };
  } catch (err) { el.innerHTML = banner(err); }
  fab("Khai thửa đất", async () => {
    const actors = await ensure("actors", "/actors").catch(() => []);
    openSheet("Khai thửa / ao / lô rừng", [
      { k: "code", label: "Mã thửa", required: true, placeholder: "vd: TH-01" },
      { k: "name", label: "Tên thửa", placeholder: "vd: Thửa ruộng đầu kênh" },
      { k: "unit_type", label: "Loại đơn vị", type: "select", options: UNIT_TYPES },
      { k: "operator_code", label: "Người/hộ vận hành", type: "select",
        options: [{ v: "", t: "— Không ghi —" }, ...actors.map(fmtActorOpt)],
        addNew: quickActor,
        refreshOptions: async () => optOf(await ensure("actors", "/actors"), "— Không ghi —", fmtActorOpt) },
      { k: "national_land_parcel_id", label: "Mã định danh thửa đất quốc gia" },
      { k: "map_sheet_number", label: "Số tờ bản đồ" },
      { k: "parcel_number", label: "Số thửa" },
      { k: "area_m2", label: "Diện tích (m²)", type: "number", step: "0.01" },
      { k: "land_tenure_doc_type", label: "Loại giấy tờ đất", placeholder: "vd: GCN QSDĐ" },
      { k: "land_cert_serial", label: "Số giấy chứng nhận" },
      { k: "land_legal_owner_name", label: "Chủ đất theo giấy tờ" },
      { k: "owner_consent_doc_url", label: "Văn bản đồng ý của chủ đất (URL)", placeholder: "https://…" },
      { k: "earth_terrace_compliant", label: "Đã làm băng đất đồng mức (vùng dốc)", type: "bool", options: BOOL_OPTS },
      { k: "forest_origin_type", label: "Nguồn gốc rừng (nếu là lô rừng)", type: "select", options: FOREST_ORIGINS },
      { k: "aquaculture_water_type", label: "Loại hình mặt nước (nếu nuôi thủy sản)", type: "select", options: AQUA_WATERS },
      { k: "vessel_reg_number", label: "Số đăng ký tàu cá (nếu là tàu cá)" },
      { k: "vessel_length_max_m", label: "Chiều dài lớn nhất tàu (m)", type: "number", step: "0.01" },
      { k: "tech_safety_cert_no", label: "Số GCN an toàn kỹ thuật tàu cá" },
      { k: "vms_device_serial", label: "Số seri thiết bị giám sát hành trình (VMS)" },
    ], async (p) => { await T("/spatial-units", { method: "POST", body: p }); invalidate("parcels"); });
  });
};

/* ---------------- PHI validation log ---------------- */
VIEWS.philogs = async () => {
  const el = $("#view");
  el.innerHTML = `<div class="section-head"><h2>🛡️ Kiểm tra PHI trước thu hoạch</h2>
    <button class="btn btn-ghost btn-sm" id="reload">↻ Làm mới</button></div>` + (state.cache.phi ? "" : skeleton(3));
  $("#reload").onclick = () => { invalidate("phi"); navigate("philogs", true); };
  try {
    const items = await ensure("phi", "/phi-validations");
    el.querySelectorAll(".skel").forEach((x) => x.remove());
    el.insertAdjacentHTML("beforeend", items.length ? `<div class="list">${items.map((v) => `
      <div class="card" data-card="${v.id}"><div class="thumb ${v.validation_outcome === "BLOCKED_VIOLATION_PHI" ? "red" : "sky"}">🛡️</div><div class="body">
        <div class="title">Lô ${esc(v.lot_code || "—")} ${chipFor(v.validation_outcome)}</div>
        <div class="sub">Kế hoạch: <b>${esc(v.plan_code || "—")}</b></div>
        <div class="meta">
          ${v.max_safe_harvest_date ? `<span>📅 An toàn từ ${fmtDate(v.max_safe_harvest_date)}</span>` : "<span>📅 Không có lần xử lý nào còn hạn cách ly</span>"}
          ${v.actual_harvest_date ? `<span>🧺 Thu hoạch ${fmtDate(v.actual_harvest_date)}</span>` : ""}
          ${v.last_treatment_ref ? `<span>🧪 Lần xử lý quyết định #${esc(v.last_treatment_ref)}</span>` : ""}
          <span>🕒 ${fmtTs(v.created_at)}</span>
        </div></div></div>`).join("")}</div>`
      : emptyState("🛡️", "Chưa có lượt kiểm tra nào", "Mỗi lần tạo lô thu hoạch, hệ thống tự kiểm tra thời gian cách ly và ghi lại tại đây."));
    wireCardDetails(el, items, (v) => `Kiểm tra PHI · Lô ${v.lot_code || ""}`, "phi_validations");
  } catch (err) { el.innerHTML = banner(err); }
};


/* ---------------- actors (catalogue) ---------------- */
const ACTOR_TYPE_VI = Object.fromEntries(ACTOR_TYPES.map((t) => [t.v, t.t]));
VIEWS.actors = async () => {
  const el = $("#view");
  el.innerHTML = `<div class="section-head"><h2>🧑‍🌾 Chủ thể</h2>
    <button class="btn btn-ghost btn-sm" id="reload">↻ Làm mới</button></div>` + (state.cache.actors ? "" : skeleton(3));
  $("#reload").onclick = () => { invalidate("actors"); navigate("actors", true); };
  try {
    const items = await ensure("actors", "/actors");
    el.querySelectorAll(".skel").forEach((x) => x.remove());
    el.insertAdjacentHTML("beforeend", items.length ? `<div class="list">${items.map((a) => `
      <div class="card" data-card="${esc(a.code)}"><div class="thumb">${a.actor_type === "FACILITY" ? "🏭" : a.actor_type === "COMPANY" ? "🏢" : "🧑‍🌾"}</div><div class="body">
        <div class="title">${esc(a.name || a.code)}</div>
        <div class="sub">Mã chủ thể: <b>${esc(a.code)}</b>${a.actor_type ? ` · ${esc(ACTOR_TYPE_VI[a.actor_type] || a.actor_type)}` : ""}</div>
        <div class="meta">
          ${a.gln_code ? `<span>🏷️ GLN ${esc(a.gln_code)}</span>` : ""}
          ${a.phone ? `<span>📞 ${esc(a.phone)}</span>` : ""}
          ${a.parent_code ? `<span>🔗 Thuộc ${esc(a.parent_code)}</span>` : ""}
          ${a.commune_code ? `<span>📍 Xã ${esc(a.commune_code)}</span>` : ""}
        </div>
        <div style="margin-top:8px"><button class="btn btn-ghost btn-sm" data-edit-actor="${esc(a.code)}">✏️ Sửa</button> <button class="btn btn-ghost btn-sm" data-del-actor="${esc(a.code)}">🗑️ Xoá</button></div>
      </div></div>`).join("")}</div>`
      : emptyState("🧑‍🌾", "Chưa có chủ thể nào", "Bấm nút + để khai nông hộ, cơ sở đóng gói hoặc nhà cung cấp đầu tiên."));
    wireCardDetails(el, items, (a) => `Chủ thể ${a.code}`, "actors");
    el.querySelectorAll("[data-del-actor]").forEach((b) => b.onclick = () =>
      confirmDelete(`chủ thể ${b.dataset.delActor}`, `/actors/${encodeURIComponent(b.dataset.delActor)}`, ["actors"]));
    el.querySelectorAll("[data-edit-actor]").forEach((b) => b.onclick = async () => {
      const a = items.find((x) => x.code === b.dataset.editActor);
      if (!a) return;
      const parents = items.filter((x) => x.code !== a.code);
      openSheet(`Sửa chủ thể ${a.code}`, [
        { k: "name", label: "Tên chủ thể", def: a.name || "" },
        { k: "actor_type", label: "Loại chủ thể", type: "select", def: a.actor_type || "HOUSEHOLD", options: ACTOR_TYPES },
        { k: "gln_code", label: "Mã GLN", def: a.gln_code || "" },
        { k: "gs1_role_ai", label: "Mã vai trò GS1", def: a.gs1_role_ai || "" },
        { k: "forestry_enterprise_class", label: "Phân loại DN gỗ (TT 26/2025)", type: "select", def: a.forestry_enterprise_class || "", options: FORESTRY_CLASSES },
        { k: "is_group_leader", label: "Là tổ trưởng", type: "bool", def: a.is_group_leader == null ? "" : String(a.is_group_leader), options: BOOL_OPTS },
        { k: "ics_training_completed", label: "Đã tập huấn ICS", type: "bool", def: a.ics_training_completed == null ? "" : String(a.ics_training_completed), options: BOOL_OPTS },
        { k: "parent_code", label: "Chủ thể cấp trên", type: "select", def: a.parent_code || "",
          options: [{ v: "", t: "— Không có —" }, ...parents.map(fmtActorOpt)] },
        { k: "province_code", label: "Mã tỉnh", def: a.province_code || "" },
        { k: "district_code", label: "Mã huyện", def: a.district_code || "" },
        { k: "commune_code", label: "Mã xã", def: a.commune_code || "" },
        { k: "address", label: "Địa chỉ", def: a.address || "" },
        { k: "legal_id", label: "Số CCCD / mã số thuế", def: a.legal_id || "" },
        { k: "phone", label: "Số điện thoại", def: a.phone || "" },
        { k: "email", label: "Email", def: a.email || "" },
        { k: "valid_from", label: "Hiệu lực từ", type: "date", def: a.valid_from ? String(a.valid_from).slice(0, 10) : "" },
        { k: "valid_to", label: "Hiệu lực đến", type: "date", def: a.valid_to ? String(a.valid_to).slice(0, 10) : "" },
      ], async (p) => { await T(`/actors/${encodeURIComponent(a.code)}`, { method: "PATCH", body: p }); invalidate("actors"); });
    });
  } catch (err) { el.innerHTML = banner(err); }
  fab("Thêm chủ thể", async () => {
    const items = await ensure("actors", "/actors").catch(() => []);
    openSheet("Thêm chủ thể", [
      { k: "code", label: "Mã chủ thể", required: true, placeholder: "vd: H05, PHC-01" },
      { k: "name", label: "Tên chủ thể", required: true },
      { k: "actor_type", label: "Loại chủ thể", type: "select", options: ACTOR_TYPES },
      { k: "gln_code", label: "Mã GLN" },
      { k: "gs1_role_ai", label: "Mã vai trò GS1" },
      { k: "forestry_enterprise_class", label: "Phân loại DN gỗ (TT 26/2025)", type: "select", options: FORESTRY_CLASSES },
      { k: "is_group_leader", label: "Là tổ trưởng", type: "bool", options: BOOL_OPTS },
      { k: "ics_training_completed", label: "Đã tập huấn ICS", type: "bool", options: BOOL_OPTS },
      { k: "parent_code", label: "Chủ thể cấp trên", type: "select",
        options: [{ v: "", t: "— Không có —" }, ...items.map(fmtActorOpt)] },
      { k: "province_code", label: "Mã tỉnh" },
      { k: "district_code", label: "Mã huyện" },
      { k: "commune_code", label: "Mã xã" },
      { k: "address", label: "Địa chỉ" },
      { k: "legal_id", label: "Số CCCD / mã số thuế" },
      { k: "phone", label: "Số điện thoại" },
      { k: "email", label: "Email" },
      { k: "valid_from", label: "Hiệu lực từ", type: "date" },
      { k: "valid_to", label: "Hiệu lực đến", type: "date" },
    ], async (p) => { await T("/actors", { method: "POST", body: p }); invalidate("actors"); });
  });
};

/* ---------------- users & audit ---------------- */
const ROLE_VI = { TENANT_ADMIN: "Quản trị tenant", OPERATOR: "Vận hành", VIEWER: "Chỉ xem" };
VIEWS.users = async () => {
  const el = $("#view");
  el.innerHTML = `<div class="section-head"><h2>👥 Người dùng & nhật ký</h2>
    <button class="btn btn-ghost btn-sm" id="reload">↻ Làm mới</button></div>` + (state.cache.users ? "" : skeleton(4));
  $("#reload").onclick = () => { invalidate("users", "audit"); navigate("users", true); };
  try {
    const [users, audit] = await Promise.all([ensure("users", "/users"), ensure("audit", "/audit")]);
    el.querySelectorAll(".skel").forEach((s) => s.remove());
    el.insertAdjacentHTML("beforeend", `
      <div class="section-head"><h2 style="font-size:15.5px">Người dùng trong tenant</h2></div>
      <div class="list">${users.items.map((u) => `
        <div class="card"><div class="thumb sky">👤</div><div class="body">
          <div class="title">${esc(u.display_name)} <span class="chip ${u.role === "TENANT_ADMIN" ? "violet" : u.role === "OPERATOR" ? "" : "grey"}">${esc(ROLE_VI[u.role] || u.role)}</span>
          ${u.account_status && u.account_status !== "ACTIVE" ? `<span class="chip amber">${u.account_status === "LOCKED" ? "🔒 Đã khóa" : "⛔ Đã thu hồi"}</span>` : ""}</div>
          <div class="sub">@${esc(u.username)} · tạo ${fmtDate(u.created_at)}${u.linked_actor_code ? ` · 🔗 Chủ thể ${esc(u.linked_actor_code)}` : ""}</div>
          ${(users.items.find((x) => x.username === store.actor)?.role === "TENANT_ADMIN") ? `<div style="margin-top:8px"><button class="btn btn-ghost btn-sm" data-user-admin="${esc(u.username)}">⚙️ Quản trị tài khoản</button></div>` : ""}
        </div></div>`).join("")}</div>
      <div class="section-head"><h2 style="font-size:15.5px">Nhật ký hệ thống (audit)</h2><span class="hint">${audit.items.length} mục · chỉ ghi thêm</span></div>
      <div class="list">${audit.items.slice().reverse().slice(0, 30).map((a) => `
        <div class="card"><div class="thumb">🧾</div><div class="body">
          <div class="title" style="font-size:14.5px">${esc(a.action)} <span class="chip ${a.outcome === "OK" ? "" : "amber"}">${esc(a.outcome)}</span></div>
          <div class="meta"><span>🎯 ${esc(a.target)}</span><span>👤 ${esc(a.actor)}</span><span>🕒 ${fmtTs(a.ts)}</span></div>
        </div></div>`).join("") || emptyState("🧾", "Chưa có nhật ký", "")}</div>`);
  } catch (err) { el.innerHTML = banner(err); }
  el.querySelectorAll("[data-user-admin]").forEach((b) => b.onclick = async () => {
    const u = users.items.find((x) => x.username === b.dataset.userAdmin);
    if (!u) return;
    const actors = await ensure("actors", "/actors").catch(() => []);
    openSheet(`Quản trị tài khoản @${u.username}`, [
      { k: "display_name", label: "Tên hiển thị", def: u.display_name || "" },
      { k: "account_status", label: "Trạng thái tài khoản", type: "select", def: u.account_status || "ACTIVE", options: [
        { v: "ACTIVE", t: "Hoạt động" }, { v: "LOCKED", t: "Khóa" }, { v: "REVOKED", t: "Thu hồi" }] },
      { k: "linked_actor_code", label: "Chủ thể liên kết", type: "select", def: u.linked_actor_code || "",
        options: [{ v: "", t: "— Không liên kết —" }, ...actors.map(fmtActorOpt)] },
      { k: "jurisdiction_admin_code", label: "Mã đơn vị hành chính phụ trách", def: u.jurisdiction_admin_code || "" },
      { k: "auth_provider_type", label: "Phương thức xác thực", type: "select", def: u.auth_provider_type || "", options: [
        { v: "", t: "— Chưa xác định —" }, { v: "VNEID_NATIONAL_SSO", t: "VNeID / SSO quốc gia" },
        { v: "ECDT_MOBILE_AUTH", t: "eCDT di động" }, { v: "INTERNAL_PKI_MFA", t: "PKI nội bộ + MFA" }] },
    ], async (p) => {
      await T(`/users/${encodeURIComponent(u.username)}`, { method: "PATCH", body: p });
      invalidate("users", "audit");
      toast("Đã cập nhật tài khoản");
    });
  });
  fab("Thêm người dùng", async () => {
    const actors = await ensure("actors", "/actors").catch(() => []);
    openSheet("Thêm người dùng", [
    { k: "username", label: "Tên đăng nhập", required: true, placeholder: "vd: van.an" },
    { k: "display_name", label: "Tên hiển thị", required: true, placeholder: "vd: Văn An" },
    { k: "role", label: "Vai trò", type: "select", options: [
      { v: "VIEWER", t: "Chỉ xem" }, { v: "OPERATOR", t: "Vận hành (ghi dữ liệu)" }, { v: "TENANT_ADMIN", t: "Quản trị tenant" }] },
    { k: "linked_actor_code", label: "Chủ thể liên kết", type: "select",
      options: [{ v: "", t: "— Không liên kết —" }, ...actors.map(fmtActorOpt)] },
    { k: "jurisdiction_admin_code", label: "Mã đơn vị hành chính phụ trách" },
    { k: "auth_provider_type", label: "Phương thức xác thực", type: "select", options: [
      { v: "", t: "— Chưa xác định —" }, { v: "VNEID_NATIONAL_SSO", t: "VNeID / SSO quốc gia" },
      { v: "ECDT_MOBILE_AUTH", t: "eCDT di động" }, { v: "INTERNAL_PKI_MFA", t: "PKI nội bộ + MFA" }] },
  ], async (p) => { await T("/users", { method: "POST", body: p }); invalidate("users", "audit"); });
  });
};

/* ---------------- platform tenants ---------------- */
VIEWS.tenants = async () => {
  const el = $("#view");
  if (!store.pkey) {
    el.innerHTML = `<div class="section-head"><h2>🏢 Quản trị tenant</h2></div>` +
      emptyState("🔐", "Cần khóa platform", "Thêm khóa quản trị platform trong mục Cài đặt để xem và quản lý danh sách tenant.") +
      `<div style="margin-top:14px"><button class="btn btn-primary btn-block" onclick="navigate('settings')">Tới Cài đặt</button></div>`;
    return;
  }
  el.innerHTML = `<div class="section-head"><h2>🏢 Quản trị tenant</h2>
    <button class="btn btn-ghost btn-sm" id="reload">↻ Làm mới</button></div>` + skeleton(3);
  $("#reload").onclick = () => navigate("tenants", true);
  try {
    const data = await P("/platform/tenants");
    el.querySelectorAll(".skel").forEach((s) => s.remove());
    el.insertAdjacentHTML("beforeend", `<div class="list">${data.items.map((t) => `
      <div class="card"><div class="thumb violet">🏢</div><div class="body">
        <div class="title">${esc(t.name)} ${chipFor(t.status)}</div>
        <div class="sub">Mã: <b>${esc(t.slug)}</b> · tạo ${fmtDate(t.created_at)}</div>
        <div class="meta"><button class="btn ${t.status === "ACTIVE" ? "btn-danger" : "btn-primary"} btn-sm" data-toggle="${esc(t.slug)}" data-next="${t.status === "ACTIVE" ? "SUSPENDED" : "ACTIVE"}">
          ${t.status === "ACTIVE" ? "🔒 Khóa tenant" : "🔓 Mở lại"}</button></div>
      </div></div>`).join("")}</div>`);
    el.querySelectorAll("[data-toggle]").forEach((b) => b.onclick = async () => {
      try {
        await P(`/platform/tenants/${b.dataset.toggle}/status`, { method: "PATCH", body: { status: b.dataset.next } });
        toast(`Đã ${b.dataset.next === "SUSPENDED" ? "khóa" : "mở lại"} tenant ${b.dataset.toggle}.`);
        navigate("tenants", true);
      } catch (err) { toast(err.message, true); }
    });
  } catch (err) { el.innerHTML = banner(err); }
  fab("Tạo tenant mới", () => openSheet("Tạo tenant mới", [
    { k: "slug", label: "Mã tenant (slug)", required: true, placeholder: "vd: dalat-foods" },
    { k: "name", label: "Tên hiển thị", required: true, placeholder: "vd: Công ty TNHH XNK Thực phẩm Đà Lạt" },
  ], async (p) => { await P("/platform/tenants", { method: "POST", body: p }); }));
};

/* ---------------- settings ---------------- */
VIEWS.settings = () => {
  const el = $("#view");
  el.innerHTML = `
    <div class="section-head"><h2>⚙️ Cài đặt kết nối</h2></div>
    <div class="panel">
      <div class="kv"><span>Địa chỉ API</span><b>${esc(location.host)}</b></div>
      <div class="kv"><span>Môi trường</span><b>${esc(state.health?.env || "beta")}</b></div>
      <div class="kv"><span>Chế độ lưu trữ</span><b>${esc(state.health?.storage || "—")}</b></div>
    </div>
    <form id="settingsForm" autocomplete="off">
      <div class="field"><label>Mã tenant</label>
        <input name="tenant" value="${esc(store.tenant)}" autocapitalize="off"></div>
      <div class="field"><label>Tên người dùng (actor)</label>
        <input name="actor" value="${esc(store.actor)}" autocapitalize="off"></div>
      <div class="field"><label>Khóa platform (tùy chọn, chỉ khi quản trị tenant)</label>
        <input name="pkey" type="password" value="${esc(store.pkey)}" placeholder="Để trống nếu không dùng"></div>
      <div class="form-actions">
        <button type="button" class="btn btn-danger" id="disconnect">Ngắt kết nối</button>
        <button type="submit" class="btn btn-primary">Lưu cài đặt</button>
      </div>
    </form>
    <div class="section-head"><h2 style="font-size:15.5px">Truy cập nhanh</h2></div>
    <div class="list">
      <button class="card" onclick="navigate('tenants')"><div class="thumb violet">🏢</div>
        <div class="body"><div class="title">Quản trị tenant</div><div class="sub">Danh sách, tạo mới, khóa/mở tenant (cần khóa platform)</div></div></button>
      <button class="card" onclick="navigate('users')"><div class="thumb sky">👥</div>
        <div class="body"><div class="title">Người dùng & audit</div><div class="sub">Thành viên trong tenant và nhật ký hệ thống</div></div></button>
      <button class="card" onclick="navigate('packing')"><div class="thumb amber">🏭</div>
        <div class="body"><div class="title">Đóng gói & truy xuất</div><div class="sub">Lô đóng gói PHC, cấp mã truy xuất nguồn gốc quốc gia</div></div></button>
      <button class="card" onclick="navigate('inputs')"><div class="thumb">🧪</div>
        <div class="body"><div class="title">Vật tư đầu vào</div><div class="sub">Lô thuốc/phân/giống và số ngày cách ly PHI</div></div></button>
      <button class="card" onclick="navigate('parcels')"><div class="thumb sky">🧩</div>
        <div class="body"><div class="title">Thửa đất & liên kết vùng</div><div class="sub">Thửa/ao/lô rừng thuộc vùng nguyên liệu</div></div></button>
      <button class="card" onclick="navigate('philogs')"><div class="thumb violet">🛡️</div>
        <div class="body"><div class="title">Kiểm tra PHI</div><div class="sub">Lịch sử chặn/cho thu hoạch theo thời gian cách ly</div></div></button>
    </div>`;
  $("#settingsForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    store.save(normTenant(fd.get("tenant")), String(fd.get("actor")).trim(),
      String(fd.get("pkey")).trim(), store.remembered());
    state.cache = {};
    toast("Đã lưu cài đặt kết nối.");
    navigate("dashboard", true);
  });
  $("#disconnect").onclick = () => { dropPersistedCache(); store.clear(); location.reload(); };
};

/* ---------------- all-functions menu (mobile "Khac" tab) ----------------
   On phones the sidebar is hidden and the tab bar holds only six views;
   every other function lives behind this menu so nothing is buried
   inside Settings (mobile navigation fix, 2026-11-03). */
const MORE_TITLES = {
  dashboard: "Tổng quan", zones: "Vùng nguyên liệu", plants: "Cây đầu dòng",
  plans: "Mùa vụ & nhật ký đồng ruộng", lots: "Lô thu hoạch",
  packing: "Đóng gói & truy xuất", inputs: "Vật tư đầu vào",
  parcels: "Thửa đất & liên kết vùng", actors: "Chủ thể (nông hộ, cơ sở, nhà cung cấp)", philogs: "Kiểm tra PHI",
  users: "Người dùng & audit", tenants: "Quản trị tenant",
  settings: "Cài đặt kết nối",
};
const MORE_SUBS = {
  dashboard: "Số liệu sản xuất và hoạt động gần đây",
  zones: "Vùng trồng, mã số vùng trồng PUC",
  plants: "Cây/cụm cây đầu dòng",
  plans: "Kế hoạch mùa vụ và nhật ký tưới, bón, xử lý…",
  lots: "Lô thu hoạch, phiếu cân, mã truy xuất",
  packing: "Lô đóng gói PHC, cấp mã truy xuất quốc gia, công đoạn CTE",
  inputs: "Lô thuốc/phân/giống và số ngày cách ly PHI",
  parcels: "Thửa/ao/lô rừng và liên kết thửa vào vùng", actors: "Nông hộ, doanh nghiệp, cơ sở đóng gói, nhà cung cấp — dùng cho các ô chọn liên kết.",
  philogs: "Lịch sử chặn/cho thu hoạch theo thời gian cách ly",
  users: "Thành viên trong tenant và nhật ký hệ thống",
  tenants: "Danh sách, tạo mới, khóa/mở tenant (cần khóa platform)",
  settings: "Tenant, người dùng, khóa platform trên thiết bị này",
};
VIEWS.more = () => {
  const el = $("#view");
  const thumbs = ["", "sky", "amber", "violet"];
  el.innerHTML = `
    <div class="section-head"><h2>☰ Tất cả chức năng</h2></div>
    <div class="list">
      ${NAV.map((n, i) => `
      <button class="card" onclick="navigate('${n.id}')"><div class="thumb ${thumbs[i % 4]}">${n.ic}</div>
        <div class="body"><div class="title">${esc(MORE_TITLES[n.id] || n.label)}</div><div class="sub">${esc(MORE_SUBS[n.id] || "")}</div></div></button>`).join("")}
    </div>`;
};

/* ---------------- boot & login ---------------- */
const normTenant = (v) => String(v || "").trim().toLowerCase();
let setupUsers = null; // users of the tenant currently typed on the login form
let setupUsersFor = "";

function setupFail(msg) {
  const box = $("#setupError");
  box.textContent = "⚠️ " + msg;
  box.hidden = false;
}
function setupClearError() { $("#setupError").hidden = true; }

async function loadAccounts() {
  const form = $("#setupForm");
  const tenant = normTenant(form.elements.tenant.value);
  form.elements.tenant.value = tenant;
  setupClearError();
  if (!tenant) { setupFail("Hãy nhập mã tenant trước (vd: beta-pilot)."); return; }
  const btn = $("#loadAccounts");
  btn.disabled = true; btn.textContent = "⏳ Đang tải tài khoản…";
  try {
    const data = await api("/api/v1/users", { tenant, actor: "" });
    setupUsers = data.items; setupUsersFor = tenant;
    const box = $("#accountBox");
    box.hidden = false;
    $("#accountList").innerHTML = setupUsers.length ? setupUsers.map((u) => `
      <button type="button" class="acct-card" data-user="${esc(u.username)}">
        <span class="avatar">${esc((u.display_name || u.username).trim().charAt(0).toUpperCase())}</span>
        <span class="who"><b>${esc(u.display_name)}</b><span>@${esc(u.username)}</span></span>
        <span class="chip ${u.role === "TENANT_ADMIN" ? "violet" : u.role === "OPERATOR" ? "" : "grey"}">${esc(ROLE_VI[u.role] || u.role)}</span>
      </button>`).join("")
      : `<div class="acct-note">Tenant này chưa có tài khoản nào. Người đầu tiên đăng nhập và tạo tài khoản sẽ trở thành Quản trị tenant (bootstrap).</div>`;
    $("#accountList").querySelectorAll("[data-user]").forEach((b) => b.onclick = () => {
      form.elements.actor.value = b.dataset.user;
      if (form.requestSubmit) form.requestSubmit();
      else form.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
    });
  } catch (err) {
    setupUsers = null; setupUsersFor = "";
    $("#accountBox").hidden = true;
    setupFail(err.message);
  } finally {
    btn.disabled = false; btn.textContent = "👥 Xem tài khoản của tenant này";
  }
}
async function loadTenants() {
  const form = $("#setupForm");
  const pkey = String(form.elements.pkey.value || "").trim();
  setupClearError();
  if (!pkey) { setupFail("Hãy dán khóa platform vào ô ở trên trước, rồi mới xem được danh sách tenant."); return; }
  const btn = $("#loadTenants");
  btn.disabled = true; btn.textContent = "⏳ Đang tải danh sách tenant…";
  try {
    const data = await api("/api/v1/platform/tenants", { platform: true, pkey });
    $("#tenantBox").hidden = false;
    $("#tenantList").innerHTML = data.items.length ? data.items.map((t) => `
      <button type="button" class="acct-card" data-tenant="${esc(t.slug)}">
        <span class="avatar">🏢</span>
        <span class="who"><b>${esc(t.name)}</b><span>${esc(t.slug)}</span></span>
        ${chipFor(t.status)}
      </button>`).join("")
      : `<div class="acct-note">Chưa có tenant nào trên hệ thống.</div>`;
    $("#tenantList").querySelectorAll("[data-tenant]").forEach((b) => b.onclick = () => {
      form.elements.tenant.value = b.dataset.tenant;
      loadAccounts();
    });
  } catch (err) {
    $("#tenantBox").hidden = true;
    setupFail(err.message);
  } finally {
    btn.disabled = false; btn.textContent = "🏢 Xem danh sách tenant (dùng khóa platform ở trên)";
  }
}
$("#loadTenants").addEventListener("click", loadTenants);
$("#loadAccounts").addEventListener("click", loadAccounts);
$("#setupForm").elements.tenant.addEventListener("change", () => {
  if (normTenant($("#setupForm").elements.tenant.value)) loadAccounts();
});

$("#setupForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const fd = new FormData(form);
  const tenant = normTenant(fd.get("tenant"));
  const actor = String(fd.get("actor") || "").trim();
  const pkey = String(fd.get("pkey") || "").trim();
  const remember = fd.get("remember") !== null;
  setupClearError();
  if (!tenant || !actor) { setupFail("Cần nhập đủ mã tenant và tên người dùng, hoặc chạm vào một tài khoản trong danh sách."); return; }
  const btn = form.querySelector('[type="submit"]');
  btn.disabled = true; btn.textContent = "Đang kết nối…";
  try {
    if (setupUsersFor !== tenant) {
      const data = await api("/api/v1/users", { tenant, actor: "" });
      setupUsers = data.items; setupUsersFor = tenant;
    }
    if (setupUsers.length && !setupUsers.some((u) => u.username === actor)) {
      throw new ApiError("ACTOR_UNKNOWN");
    }
    store.save(tenant, actor, pkey, remember);
    $("#setup").hidden = true;
    boot();
  } catch (err) {
    setupFail(err.message);
    btn.disabled = false; btn.textContent = "Vào không gian làm việc";
  }
});
async function boot() {
  paintNav();
  loadPersistedCache();
  navigate(store.tenant ? "dashboard" : "settings", true);
  // Health resolves in the background: it must not gate the first screen
  // (a cold /health alone measured 2.4-3.0 s on 2026-11-04).
  api("/health").then((h) => { state.health = h; $("#envLabel").textContent = h.env; }).catch(() => {});
}
if (store.tenant) { $("#setup").hidden = true; boot(); }
else {
  $("#setup").hidden = false; paintNav();
  fetch("/health").catch(() => {});  // warm-up while the user signs in
}
