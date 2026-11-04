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
  GTIN_INVALID: "Mã GTIN phải là GTIN-8/12/13/14, chỉ gồm chữ số.",
  GTIN_CHECK_DIGIT_INVALID: "Mã GTIN sai số kiểm tra GS1 — kiểm tra lại mã trên bao bì.",
  PROOF_NOT_SEALED: "Bản ghi này chưa nằm trong checkpoint nào — hãy tạo checkpoint trước.",
  KEY_UNAVAILABLE: "Checkpoint được niêm phong bằng khóa toàn vẹn khác — cần đúng khóa để kiểm chứng.",
  INTEGRITY_BROKEN: "Dữ liệu đã niêm phong không còn khớp — hãy chạy Kiểm chứng để xem chi tiết.",
  PACKING_OUTPUT_EXCEEDED: "Tổng khối lượng đã cấp mã cho lô đóng gói này vượt sản lượng thành phẩm đã khai.",
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
    return `<div class="field" data-k="${f.k}"><label>${esc(f.label)}${req}</label>${control}${addBtn}</div>`;
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
      const parentOpts = sheetOnCancel ? { onCancel: sheetOnCancel } : {};
      const restore = async (newCode) => {
        for (const pf of parent.fields) {
          if (pf.refreshOptions) { try { pf.options = await pf.refreshOptions(); } catch { /* keep */ } }
          pf.def = newCode && pf.k === f.k ? newCode : snapshot[pf.k];
        }
        openSheet(parent.title, parent.fields, parent.onSubmit, parentOpts);
      };
      f.addNew((code) => restore(code), () => restore(null));
    };
  });
  // Core + Vertical (T-035): a field may declare visIf {k, in:[...]} and is
  // shown only while the driver field holds one of those values.
  const applyVis = () => {
    for (const f of fields) {
      if (!f.visIf) continue;
      const wrap = form.querySelector(`.field[data-k="${f.k}"]`);
      const driver = form.querySelector(`[name="${f.visIf.k}"]`);
      if (!wrap || !driver) continue;
      wrap.style.display = f.visIf.in.includes(driver.value) ? "" : "none";
    }
  };
  form.querySelectorAll("select").forEach((sel) => sel.addEventListener("change", applyVis));
  applyVis();
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
const fmtZoneOpt = (z) => ({ v: z.code, t: `${z.code}${z.puc_code ? " · " + z.puc_code : ""}` });
const fmtActorOpt = (a) => ({ v: a.code, t: `${a.code} · ${a.name || ""}` });
const fmtPlantOpt = (pl) => ({ v: pl.code, t: `${pl.code} · ${pl.species || ""}` });
const fmtParcelOpt = (u) => ({ v: u.code, t: `${u.code}${u.parcel_number ? " · Thửa " + u.parcel_number : ""}` });
const fmtInputOpt = (i) => ({ v: i.code, t: `${i.code} · ${i.name || i.substance_code || ""}${i.phi_days != null ? ` · cách ly ${i.phi_days} ngày` : ""}` });
const fmtPlanOpt = (p) => ({ v: p.code, t: `${p.code} · ${p.name || p.crop_name || ""}` });
const fmtLotOpt = (l) => ({ v: l.code, t: `${l.code} · ${l.quantity ?? "?"} ${l.unit || "kg"}` });
const PUC_STATUSES = window.IAICT_META.enums.PUC_STATUSES;
const MEMBERSHIP_STATUSES = window.IAICT_META.enums.MEMBERSHIP_STATUSES;
const FARM_TIERS = window.IAICT_META.enums.FARM_TIERS;
const SUBMIT_CHANNELS = window.IAICT_META.enums.SUBMIT_CHANNELS;
const SECTORS = window.IAICT_META.enums.SECTORS;
const FOREST_ORIGINS = window.IAICT_META.enums.FOREST_ORIGINS;
const AQUA_WATERS = window.IAICT_META.enums.AQUA_WATERS;
const FORESTRY_CLASSES = window.IAICT_META.enums.FORESTRY_CLASSES;
const BOOL_OPTS = window.IAICT_META.enums.BOOL_OPTS;
const ACTOR_TYPES = [
  { v: "HOUSEHOLD", t: "Nông hộ" }, { v: "COMPANY", t: "Doanh nghiệp" },
  { v: "COOPERATIVE", t: "Hợp tác xã" }, { v: "FACILITY", t: "Cơ sở đóng gói/chế biến" },
  { v: "OTHER", t: "Khác" }];

/* Create-form field builders (T-037): ONE definition per kind, shared by the
   main create form and the "+ Thêm mới" quick-create inside other forms, so
   the quick form is always the full original form - never a stripped copy. */
async function zoneCreateFields() {
  const actors = await ensure("actors", "/actors").catch(() => []);
  const adminUnits = await ensure("ref_admin_units", "/ref-admin-units").catch(() => []);
  return [
    { k: "code", label: "Mã vùng", required: true, placeholder: "vd: Z-01" },
    { k: "puc_code", label: "Mã số vùng trồng (PUC)", placeholder: "vd: VN-66-650-24370-94-21" },
    { k: "puc_status", label: "Trạng thái mã số vùng trồng", type: "select", options: PUC_STATUSES },
    { k: "issue_date", label: "Ngày cấp mã vùng trồng", type: "date" },
    { k: "issuing_authority", label: "Cơ quan cấp mã", placeholder: "vd: Chi cục Trồng trọt và BVTV" },
    { k: "post_inspect_due_date", label: "Hạn hậu kiểm mã vùng trồng", type: "date" },
    { k: "valid_from", label: "Mã vùng trồng hiệu lực từ", type: "date" },
    { k: "valid_to", label: "Mã vùng trồng hiệu lực đến", type: "date" },
    { k: "vsic_code", label: "Mã ngành VSIC", placeholder: "vd: 0119" },
    { k: "sector_category", label: "Ngành / lĩnh vực", type: "select", options: [{ v: "", t: "— Chọn ngành —" }, ...SECTORS] },
    { k: "market_scope", label: "Phạm vi thị trường", placeholder: "vd: Nội địa, EU, Trung Quốc…" },
    { k: "scientific_name", label: "Tên khoa học cây trồng chính" },
    { k: "owner_actor_code", label: "Chủ thể sở hữu vùng", type: "select",
      options: [{ v: "", t: "— Chưa gắn —" }, ...actors.map(fmtActorOpt)],
      addNew: quickActor,
      refreshOptions: async () => optOf(await ensure("actors", "/actors"), "— Chưa gắn —", fmtActorOpt) },
    { k: "jurisdiction_commune_code", label: "Đơn vị hành chính quản lý (xã)", type: "select",
      options: [{ v: "", t: "— Chưa gắn —" }, ...adminUnits.map(fmtRefOpt("ref_admin_units"))],
      addNew: (done, back) => quickRef("ref_admin_units", done, back),
      refreshOptions: async () => optOf(await ensure("ref_admin_units", "/ref-admin-units"), "— Chưa gắn —", fmtRefOpt("ref_admin_units")) },
    { k: "initial_declared_area_ha", label: "Diện tích khai báo ban đầu (ha)", type: "number", step: "0.01" },
    { k: "dist_to_residential_m", label: "Khoảng cách tới khu dân cư (m)", type: "number", step: "0.1", visIf: { k: "sector_category", in: ["LIVESTOCK_FARMING"] } },
    { k: "dist_to_sensitive_zone_m", label: "Khoảng cách tới vùng nhạy cảm (m)", type: "number", step: "0.1", visIf: { k: "sector_category", in: ["LIVESTOCK_FARMING"] } },
    { k: "bee_site_min_dist_km", label: "Khoảng cách tối thiểu tới điểm nuôi ong (km)", type: "number", step: "0.1", visIf: { k: "sector_category", in: ["LIVESTOCK_FARMING"] } },
    { k: "farm_scale_tier", label: "Quy mô cơ sở chăn nuôi", type: "select", options: FARM_TIERS, visIf: { k: "sector_category", in: ["LIVESTOCK_FARMING"] } },
    { k: "submission_channel", label: "Kênh nộp hồ sơ cấp mã", type: "select", options: SUBMIT_CHANNELS },
    { k: "application_received_at", label: "Thời điểm xã tiếp nhận hồ sơ", type: "datetime-local" },
    { k: "primary_species", label: "Cây trồng chính", placeholder: "vd: Bưởi da xanh" },
  ];
}
async function plantCreateFields() {
  const zones = await ensure("zones", "/zones").catch(() => []);
  return [
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
  ];
}
async function actorCreateFields() {
  const items = await ensure("actors", "/actors").catch(() => []);
  return [
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
  ];
}
async function inputLotCreateFields() {
  const actors = await ensure("actors", "/actors").catch(() => []);
  return [
    { k: "code", label: "Mã lô vật tư", required: true, placeholder: "vd: VT-01" },
    { k: "name", label: "Tên vật tư", placeholder: "vd: Thuốc trừ sâu X" },
    { k: "category", label: "Nhóm vật tư", type: "select", options: INPUT_CATEGORIES },
    { k: "substance_code", label: "Hoạt chất / thành phần", placeholder: "vd: Abamectin" },
    { k: "vn_registration_number", label: "Số đăng ký lưu hành VN" },
    { k: "batch_no", label: "Số lô nhà sản xuất" },
    { k: "purchase_invoice_no", label: "Số hóa đơn mua" },
    { k: "qcvn_scheme_id", label: "Mã quy chuẩn (QCVN)" },
    { k: "supplier_code", label: "Nhà cung cấp", type: "select",
      options: [{ v: "", t: "— Không ghi —" }, ...actors.map(fmtActorOpt)],
      addNew: quickActor,
      refreshOptions: async () => optOf(await ensure("actors", "/actors"), "— Không ghi —", fmtActorOpt) },
    { k: "purchase_date", label: "Ngày nhập", type: "date" },
    { k: "quantity", label: "Số lượng nhập", type: "number", step: "0.01" },
    { k: "phi_days", label: "Số ngày cách ly PHI (theo nhãn)", type: "number", step: "1" },
    { k: "expiry_date", label: "Hạn dùng", type: "date" },
  ];
}
async function parcelCreateFields() {
  const actors = await ensure("actors", "/actors").catch(() => []);
  return [
    { k: "code", label: "Mã thửa", required: true, placeholder: "vd: TH-01" },
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
    { k: "slope_degree", label: "Độ dốc (°)", type: "number", step: "0.1", visIf: { k: "unit_type", in: ["AGRICULTURAL_LAND_PARCEL", "FOREST_PLOT_STAND"] } },
    { k: "earth_terrace_compliant", label: "Đã làm băng đất đồng mức (vùng dốc)", type: "bool", options: BOOL_OPTS, visIf: { k: "unit_type", in: ["AGRICULTURAL_LAND_PARCEL", "FOREST_PLOT_STAND"] } },
    { k: "forest_subzone_code", label: "Mã tiểu khu", visIf: { k: "unit_type", in: ["FOREST_PLOT_STAND"] } },
    { k: "forest_compartment_code", label: "Mã khoảnh", visIf: { k: "unit_type", in: ["FOREST_PLOT_STAND"] } },
    { k: "forest_plot_code", label: "Mã lô rừng", visIf: { k: "unit_type", in: ["FOREST_PLOT_STAND"] } },
    { k: "forest_origin_type", label: "Nguồn gốc rừng (nếu là lô rừng)", type: "select", options: FOREST_ORIGINS, visIf: { k: "unit_type", in: ["FOREST_PLOT_STAND"] } },
    { k: "aquaculture_water_type", label: "Loại hình mặt nước (nếu nuôi thủy sản)", type: "select", options: AQUA_WATERS, visIf: { k: "unit_type", in: ["AQUACULTURE_POND_CAGE"] } },
    { k: "vessel_reg_number", label: "Số đăng ký tàu cá (nếu là tàu cá)", visIf: { k: "unit_type", in: ["FISHING_VESSEL"] } },
    { k: "vessel_length_max_m", label: "Chiều dài lớn nhất tàu (m)", type: "number", step: "0.01", visIf: { k: "unit_type", in: ["FISHING_VESSEL"] } },
    { k: "tech_safety_cert_no", label: "Số GCN an toàn kỹ thuật tàu cá", visIf: { k: "unit_type", in: ["FISHING_VESSEL"] } },
    { k: "vms_device_serial", label: "Số seri thiết bị giám sát hành trình (VMS)", visIf: { k: "unit_type", in: ["FISHING_VESSEL"] } },
  ];
}

async function quickZone(done, back) {
  try {
    openSheet("Tạo vùng nguyên liệu", await zoneCreateFields(), async (p) => { const r = await T("/zones", { method: "POST", body: p }); invalidate("zones", "zhistory"); toast("Đã thêm vùng " + r.code); done(r.code); }, { onCancel: back });
  } catch { toast("Không mở được form vùng.", true); back(); }
}
async function quickPlant(done, back) {
  try {
    openSheet("Thêm cây đầu dòng", await plantCreateFields(), async (p) => { const r = await T("/mother-plants", { method: "POST", body: p }); invalidate("plants"); toast("Đã thêm cây " + r.code); done(r.code); }, { onCancel: back });
  } catch { toast("Không mở được form cây đầu dòng.", true); back(); }
}
async function quickActor(done, back) {
  try {
    openSheet("Thêm chủ thể", await actorCreateFields(), async (p) => { const r = await T("/actors", { method: "POST", body: p }); invalidate("actors"); toast("Đã thêm chủ thể " + r.code); done(r.code); }, { onCancel: back });
  } catch { toast("Không mở được form chủ thể.", true); back(); }
}
async function quickInputLot(done, back) {
  try {
    openSheet("Nhập lô vật tư đầu vào", await inputLotCreateFields(), async (p) => { const r = await T("/input-lots", { method: "POST", body: p }); invalidate("inputs"); toast("Đã thêm lô vật tư " + r.code); done(r.code); }, { onCancel: back });
  } catch { toast("Không mở được form lô vật tư.", true); back(); }
}
async function quickParcel(done, back) {
  try {
    openSheet("Khai thửa / ao / lô rừng", await parcelCreateFields(), async (p) => { const r = await T("/spatial-units", { method: "POST", body: p }); invalidate("parcels"); toast("Đã thêm thửa " + r.code); done(r.code); }, { onCancel: back });
  } catch { toast("Không mở được form thửa đất.", true); back(); }
}

async function planCreateFields() {
  const [zones, plants, parcels] = await Promise.all([
    ensure("zones", "/zones").catch(() => []), ensure("plants", "/mother-plants").catch(() => []),
    ensure("parcels", "/spatial-units").catch(() => []),
  ]);
  const forestZones = zones.filter((z) => z.sector_category === "FORESTRY_PLANTATION").map((z) => z.code);
  const aquaZones = zones.filter((z) => z.sector_category === "AQUACULTURE").map((z) => z.code);
  return [
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
    { k: "start_date", label: "Ngày bắt đầu", type: "date" },
    { k: "end_date", label: "Ngày kết thúc dự kiến", type: "date" },
    { k: "target_yield_kg", label: "Mục tiêu sản lượng (kg)", type: "number", step: "0.1" },
    { k: "planting_density", label: "Mật độ trồng (cây/ha)", type: "number", step: "0.1" },
    { k: "seed_origin_doc", label: "Hồ sơ nguồn gốc giống", placeholder: "Số giấy chứng nhận / hóa đơn giống" },
    { k: "forest_harvest_plan_no", label: "Số VB phê duyệt PA khai thác rừng (nếu có)", visIf: { k: "zone_code", in: forestZones } },
    { k: "departure_port_code", label: "Mã cảng xuất bến (thủy sản, nếu có)", visIf: { k: "zone_code", in: aquaZones } },
    { k: "arrival_port_code", label: "Mã cảng cập bến (thủy sản, nếu có)", visIf: { k: "zone_code", in: aquaZones } },
    { k: "status", label: "Trạng thái chu kỳ", type: "select", options: [
      { v: "IN_PROGRESS", t: "Đang thực hiện" }, { v: "HARVESTING", t: "Đang thu hoạch" },
      { v: "COMPLETED_CLOSED", t: "Đã kết thúc" }, { v: "ABORTED_BY_DISASTER_DISEASE", t: "Hủy do thiên tai / dịch bệnh" }] },
  ];
}
async function lotCreateFields() {
  const [zones, plans, actors, parcels] = await Promise.all([
    ensure("zones", "/zones").catch(() => []), ensure("plans", "/crop-plans").catch(() => []),
    ensure("actors", "/actors").catch(() => []), ensure("parcels", "/spatial-units").catch(() => []),
  ]);
  return [
    { k: "code", label: "Mã lô", required: true, placeholder: "vd: LOT-001" },
    { k: "zone_code", label: "Vùng thu hoạch", type: "select",
      options: [{ v: "", t: "— Chọn vùng —" }, ...zones.map(fmtZoneOpt)],
      addNew: quickZone,
      refreshOptions: async () => optOf(await ensure("zones", "/zones"), "— Chọn vùng —", fmtZoneOpt) },
    { k: "plan_code", label: "Kế hoạch mùa vụ", type: "select",
      options: [{ v: "", t: "— Không gắn kế hoạch —" }, ...plans.map(fmtPlanOpt)],
      addNew: quickPlan,
      refreshOptions: async () => optOf(await ensure("plans", "/crop-plans"), "— Không gắn kế hoạch —", fmtPlanOpt) },
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
    { k: "expiry_date", label: "Hạn dùng", type: "date" },
  ];
}
async function quickPlan(done, back) {
  try {
    openSheet("Tạo kế hoạch mùa vụ", await planCreateFields(), async (p) => { const r = await T("/crop-plans", { method: "POST", body: p }); invalidate("plans"); toast("Đã thêm kế hoạch " + r.code); done(r.code); }, { onCancel: back });
  } catch { toast("Không mở được form kế hoạch.", true); back(); }
}
async function quickLot(done, back) {
  try {
    openSheet("Tạo lô thu hoạch", await lotCreateFields(), async (p) => { const r = await T("/lots", { method: "POST", body: p }); invalidate("lots"); toast("Đã thêm lô " + r.code); done(r.code); }, { onCancel: back });
  } catch { toast("Không mở được form lô thu hoạch.", true); back(); }
}

const DETAIL_LABELS = window.IAICT_META.labels;

const DETAIL_VALUE_MAPS = {
  actor_type: { HOUSEHOLD: "Nông hộ", COMPANY: "Doanh nghiệp", COOPERATIVE: "Hợp tác xã", FACILITY: "Cơ sở đóng gói/chế biến", OTHER: "Khác" },
  unit_type: { AGRICULTURAL_LAND_PARCEL: "Thửa đất nông nghiệp", FOREST_PLOT_STAND: "Lô rừng", LIVESTOCK_BARN_HOUSE: "Chuồng trại chăn nuôi", BEEKEEPING_SITE: "Điểm nuôi ong", AQUACULTURE_POND_CAGE: "Ao/bè thủy sản", FISHING_VESSEL: "Tàu cá", LAND_PARCEL: "Thửa ruộng", PARCEL: "Thửa ruộng", GREENHOUSE: "Nhà kính", POND: "Ao nuôi", AQUATIC_POND: "Ao nuôi", PEN: "Chuồng trại", LIVESTOCK_PEN: "Chuồng trại", FOREST_PLOT: "Lô rừng", OTHER: "Khác" },
  storage_type: { FRESH_AMBIENT: "Tươi, nhiệt độ thường", CHILLED_COOL: "Mát lạnh", FROZEN_PROCESSED: "Đông lạnh / chế biến" },
  validation_outcome: { PASSED_SAFE: "Đạt — an toàn", BLOCKED_VIOLATION_PHI: "Chặn — vi phạm thời gian cách ly", CONDITIONAL_LAB_TEST_REQUIRED: "Điều kiện — cần xét nghiệm dư lượng" },
  sync_status: { PENDING_SYNC: "Chờ đồng bộ cổng quốc gia", SYNCED: "Đã đồng bộ", SYNCED_SUCCESS: "Đã đồng bộ cổng quốc gia" },
  data_carrier_type: { QR_CODE: "Mã QR", BARCODE: "Mã vạch", RFID: "RFID" },
};
const _enumMap = (key) => Object.fromEntries((window.IAICT_META.enums[key] || []).filter((o) => o.v).map((o) => [o.v, o.t]));
Object.assign(DETAIL_VALUE_MAPS, {
  admin_level: _enumMap("ADMIN_LEVELS"),
  substance_category: _enumMap("SUBSTANCE_CATEGORIES"),
  approval_status: _enumMap("SUBSTANCE_APPROVAL_STATUSES"),
  mrl_measurement_unit: _enumMap("MRL_UNITS"),
  scheme_level: _enumMap("SCHEME_LEVELS"),
  applicable_sector: _enumMap("SCHEME_SECTORS"),
  foreign_market_status: _enumMap("FOREIGN_MARKET_STATUSES"),
  violation_type: _enumMap("VIOLATION_TYPES"),
  foreign_sanction_action: _enumMap("FOREIGN_SANCTION_ACTIONS"),
  certified_entity_type: _enumMap("CERT_ENTITY_TYPES"),
  cert_status: _enumMap("CERT_STATUSES"),
  management_granularity: _enumMap("LIVESTOCK_GRANULARITY"),
  lifecycle_status: _enumMap("LIVESTOCK_LIFECYCLE"),
  supervision_outcome: _enumMap("SUPERVISION_OUTCOMES"),
  monitoring_type: _enumMap("MONITORING_TYPES"),
  compliance_conclusion: _enumMap("COMPLIANCE_CONCLUSIONS"),
  species_category_code: _enumMap("DECL_SPECIES_CATEGORIES"),
  quantity_unit: _enumMap("DECL_QUANTITY_UNITS"),
  recall_initiation_type: _enumMap("RECALL_INITIATION_TYPES"),
  risk_classification: _enumMap("RISK_CLASSES"),
  post_recall_handling_method: _enumMap("RECALL_HANDLING_METHODS"),
  device_type: _enumMap("IOT_DEVICE_TYPES"),
});

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
const DETAIL_SPECS = window.IAICT_META.detailSpecs;

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
    const wrap = e.target.querySelector(`.field[data-k="${f.k}"]`);
    if (wrap && wrap.style.display === "none") continue;
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
  { id: "refs", ic: "📚", label: "Danh mục" },
  { id: "market", ic: "🌏", label: "Thị trường" },
  { id: "monitor", ic: "🔬", label: "Giám sát" },
  { id: "logistics", ic: "🚚", label: "Vận chuyển" },
  { id: "reports", ic: "📊", label: "Báo cáo" },
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
        <div class="title">${esc(z.code)}</div>
        <div class="sub">Mã vùng: <b>${esc(z.code)}</b></div>
        <div class="meta">
          ${z.initial_declared_area_ha != null ? `<span>📐 ${fmtNum(z.initial_declared_area_ha)} ha</span>` : ""}
          ${z.puc_code ? `<span>🏷️ MSVT ${esc(z.puc_code)}</span>` : ""}
          ${z.primary_species ? `<span>🌱 ${esc(z.primary_species)}</span>` : ""}
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
      const adminUnits = await ensure("ref_admin_units", "/ref-admin-units").catch(() => []);
      openSheet(`Sửa vùng ${z.code}`, [
        { k: "puc_code", label: "Mã số vùng trồng (PUC)", def: z.puc_code || "" },
        { k: "puc_status", label: "Trạng thái mã số vùng trồng", type: "select", def: z.puc_status || "", options: PUC_STATUSES },
        { k: "sector_category", label: "Ngành / lĩnh vực", type: "select", def: z.sector_category || "", options: [{ v: "", t: "— Chọn ngành —" }, ...SECTORS] },
        { k: "market_scope", label: "Phạm vi thị trường", def: z.market_scope || "" },
        { k: "scientific_name", label: "Tên khoa học cây trồng chính", def: z.scientific_name || "" },
        { k: "issuing_authority", label: "Cơ quan cấp mã", def: z.issuing_authority || "" },
        { k: "owner_actor_code", label: "Chủ thể sở hữu vùng", type: "select", def: z.owner_actor_code || "",
          options: [{ v: "", t: "— Chưa gắn —" }, ...actors.map(fmtActorOpt)],
          addNew: quickActor,
          refreshOptions: async () => optOf(await ensure("actors", "/actors"), "— Chưa gắn —", fmtActorOpt) },
        { k: "jurisdiction_commune_code", label: "Đơn vị hành chính quản lý (xã)", type: "select", def: z.jurisdiction_commune_code || "",
          options: [{ v: "", t: "— Chưa gắn —" }, ...adminUnits.map(fmtRefOpt("ref_admin_units"))],
          addNew: (done, back) => quickRef("ref_admin_units", done, back),
          refreshOptions: async () => optOf(await ensure("ref_admin_units", "/ref-admin-units"), "— Chưa gắn —", fmtRefOpt("ref_admin_units")) },
        { k: "initial_declared_area_ha", label: "Diện tích khai báo ban đầu (ha)", type: "number", step: "0.01", def: z.initial_declared_area_ha ?? "" },
        { k: "valid_from", label: "Mã vùng trồng hiệu lực từ", type: "date", def: z.valid_from ? String(z.valid_from).slice(0, 10) : "" },
        { k: "valid_to", label: "Mã vùng trồng hiệu lực đến", type: "date", def: z.valid_to ? String(z.valid_to).slice(0, 10) : "" },
        { k: "dist_to_residential_m", label: "Khoảng cách tới khu dân cư (m)", type: "number", step: "0.1", def: z.dist_to_residential_m ?? "" , visIf: { k: "sector_category", in: ["LIVESTOCK_FARMING"] } },
        { k: "dist_to_sensitive_zone_m", label: "Khoảng cách tới vùng nhạy cảm (m)", type: "number", step: "0.1", def: z.dist_to_sensitive_zone_m ?? "" , visIf: { k: "sector_category", in: ["LIVESTOCK_FARMING"] } },
        { k: "bee_site_min_dist_km", label: "Khoảng cách tối thiểu tới điểm nuôi ong (km)", type: "number", step: "0.1", def: z.bee_site_min_dist_km ?? "" , visIf: { k: "sector_category", in: ["LIVESTOCK_FARMING"] } },
        { k: "farm_scale_tier", label: "Quy mô cơ sở chăn nuôi", type: "select", def: z.farm_scale_tier || "", options: FARM_TIERS , visIf: { k: "sector_category", in: ["LIVESTOCK_FARMING"] } },
        { k: "submission_channel", label: "Kênh nộp hồ sơ cấp mã", type: "select", def: z.submission_channel || "", options: SUBMIT_CHANNELS },
        { k: "application_received_at", label: "Thời điểm xã tiếp nhận hồ sơ", type: "datetime-local", def: z.application_received_at ? String(z.application_received_at).slice(0, 16) : "" },
        { k: "status_change_reason", label: "Lý do đổi trạng thái mã (khi sửa trạng thái)", placeholder: "vd: POST_INSPECTION_PASSED" },
        { k: "status_decision_doc", label: "Số văn bản quyết định đổi trạng thái" },
        { k: "status_remediation", label: "Biện pháp khắc phục (nếu bị đình chỉ)" },
        { k: "issue_date", label: "Ngày cấp mã vùng trồng", type: "date", def: z.issue_date || "" },
        { k: "post_inspect_due_date", label: "Hạn hậu kiểm mã vùng trồng", type: "date", def: z.post_inspect_due_date || "" },
        { k: "vsic_code", label: "Mã ngành VSIC", def: z.vsic_code || "" },
        { k: "primary_species", label: "Cây trồng chính", def: z.primary_species || "" },
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
    openSheet("Tạo vùng nguyên liệu", await zoneCreateFields(), async (p) => { await T("/zones", { method: "POST", body: p }); invalidate("zones", "zhistory"); });
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
    openSheet("Thêm cây đầu dòng", await plantCreateFields(), async (p) => { await T("/mother-plants", { method: "POST", body: p }); invalidate("plants"); });
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
      const cropZones = zones.filter((z) => z.sector_category === "CROP_FARMING").map((z) => z.code);
      openSheet("Ghi nhật ký đồng ruộng", [
        { k: "event_type", label: "Loại sự kiện", type: "select", required: true, options: EVENT_TYPES },
        { k: "plan_code", label: "Kế hoạch mùa vụ", type: "select",
          options: [{ v: "", t: "— Không gắn kế hoạch —" }, ...plans.map(fmtPlanOpt)],
          addNew: quickPlan,
          refreshOptions: async () => optOf(await ensure("plans", "/crop-plans"), "— Không gắn kế hoạch —", fmtPlanOpt) },
        { k: "zone_code", label: "Vùng", type: "select",
          options: [{ v: "", t: "— Không gắn vùng —" }, ...zones.map(fmtZoneOpt)],
          addNew: quickZone,
          refreshOptions: async () => optOf(await ensure("zones", "/zones"), "— Không gắn vùng —", fmtZoneOpt) },
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
        { k: "fruit_bagging_count", label: "Số trái đã bao (nếu có)", type: "number", step: "1" , visIf: { k: "zone_code", in: cropZones } },
        { k: "occurred_at", label: "Thời gian thực hiện", type: "datetime-local" },
      ], async (p) => {
        if (p.occurred_at) p.occurred_at = new Date(p.occurred_at).toISOString();
        p.actor = store.actor;
        await T("/field-events", { method: "POST", body: p });
        invalidate("events");
      });
    };
  } catch (err) { el.innerHTML = banner(err); }
  fab("Tạo kế hoạch mùa vụ", async () => {
    openSheet("Tạo kế hoạch mùa vụ", await planCreateFields(), async (p) => { await T("/crop-plans", { method: "POST", body: p }); invalidate("plans"); });
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
        <div class="title">${esc(l.code)}</div>
        <div class="sub">${l.quantity != null ? `<b>${fmtNum(l.quantity)} ${esc(l.unit || "kg")}</b>` : ""}${l.harvest_date ? ` · Thu hoạch ${fmtDate(l.harvest_date)}` : ""}</div>
        <div class="meta">
          ${l.zone_code ? `<span>🗺️ ${esc(l.zone_code)}</span>` : ""}
          ${l.plan_code ? `<span>📅 ${esc(l.plan_code)}</span>` : ""}
          ${l.farmer_code ? `<span>🧑‍🌾 ${esc(l.farmer_code)}</span>` : ""}
          ${l.weigh_slip_number ? `<span>⚖️ ${esc(l.weigh_slip_number)}</span>` : ""}
          ${l.traceability_code ? `<span>🔎 ${esc(l.traceability_code)}</span>` : ""}
          ${l.expiry_date ? `<span>⏳ HSD ${fmtDate(l.expiry_date)}</span>` : ""}
        </div></div></div>`).join("")}</div>`
      : emptyState("📦", "Chưa có lô thu hoạch nào", "Bấm nút + để tạo lô từ vùng/kế hoạch đã thu hoạch."));
    wireCardDetails(el, items, (l) => `Lô thu hoạch ${l.code}`, "lots");
  } catch (err) { el.innerHTML = banner(err); }
  fab("Tạo lô thu hoạch", async () => {
    openSheet("Tạo lô thu hoạch", await lotCreateFields(), async (p) => { await T("/lots", { method: "POST", body: p }); invalidate("lots"); });
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
        <div class="title">${esc(p.code)}</div>
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
    el.querySelectorAll("[data-edit-packing]").forEach((b) => b.onclick = async () => {
      const pk = plots.find((x) => x.code === b.dataset.editPacking);
      if (!pk) return;
      const actors = await ensure("actors", "/actors").catch(() => []);
      openSheet(`Sửa lô đóng gói ${pk.code}`, [
        { k: "facility_code", label: "Cơ sở đóng gói", type: "select", def: pk.facility_code || "",
          options: [{ v: "", t: "— Chọn cơ sở —" }, ...actors.map(fmtActorOpt)],
          addNew: quickActor,
          refreshOptions: async () => optOf(await ensure("actors", "/actors"), "— Chọn cơ sở —", fmtActorOpt) },
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
      options: [{ v: "", t: "— Chọn lô thu hoạch —" }, ...lots.map(fmtLotOpt)],
      addNew: quickLot,
      refreshOptions: async () => optOf(await ensure("lots", "/lots"), "— Chọn lô thu hoạch —", fmtLotOpt) },
    { k: "allocated_weight_kg", label: "Khối lượng đưa vào đóng gói (kg)", type: "number", step: "0.01", required: true },
    { k: "product_name", label: "Tên sản phẩm (Bảng 29)", required: true, placeholder: "vd: Bưởi da xanh loại 1" },
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
    { k: "unit_weight_kg", label: "Trọng lượng 1 đơn vị (kg)", type: "number", step: "0.01" },
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
      package_spec: p.package_spec, units_count: p.units_count, unit_weight_kg: p.unit_weight_kg } });
    await T("/traceability-records", { method: "POST", body: {
      packaging_unit_code: sku, product_name: p.product_name, product_image_url: p.product_image_url,
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
        { k: "purchase_invoice_no", label: "Số hóa đơn mua", def: it.purchase_invoice_no || "" },
        { k: "qcvn_scheme_id", label: "Mã quy chuẩn (QCVN)", def: it.qcvn_scheme_id || "" },
        { k: "supplier_code", label: "Nhà cung cấp", type: "select", def: it.supplier_code || "",
          options: [{ v: "", t: "— Không ghi —" }, ...actors.map(fmtActorOpt)],
          addNew: quickActor,
          refreshOptions: async () => optOf(await ensure("actors", "/actors"), "— Không ghi —", fmtActorOpt) },
        { k: "quantity", label: "Số lượng nhập", type: "number", step: "0.01", def: it.quantity ?? "" },
        { k: "phi_days", label: "Số ngày cách ly PHI (theo nhãn)", type: "number", step: "1", def: it.phi_days ?? "" },
        { k: "expiry_date", label: "Hạn dùng", type: "date", def: it.expiry_date ? String(it.expiry_date).slice(0, 10) : "" },
      ], async (p) => { await T(`/input-lots/${encodeURIComponent(it.code)}`, { method: "PATCH", body: p }); invalidate("inputs"); });
    });
  } catch (err) { el.innerHTML = banner(err); }
  fab("Nhập lô vật tư", async () => {
    openSheet("Nhập lô vật tư đầu vào", await inputLotCreateFields(), async (p) => { await T("/input-lots", { method: "POST", body: p }); invalidate("inputs"); });
  });
};

/* ---------------- spatial units & zone links ---------------- */
const UNIT_TYPES = [
  { v: "AGRICULTURAL_LAND_PARCEL", t: "Thửa đất nông nghiệp" }, { v: "FOREST_PLOT_STAND", t: "Lô rừng" },
  { v: "LIVESTOCK_BARN_HOUSE", t: "Chuồng trại chăn nuôi" }, { v: "BEEKEEPING_SITE", t: "Điểm nuôi ong" },
  { v: "AQUACULTURE_POND_CAGE", t: "Ao/bè thủy sản" }, { v: "FISHING_VESSEL", t: "Tàu cá" },
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
        <div class="title">${esc(u.national_land_parcel_id || u.code)}</div>
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
        { k: "unit_type", label: "Loại đơn vị", type: "select", def: u.unit_type || "", options: [{ v: "", t: "— Chọn loại đơn vị —" }, ...UNIT_TYPES] },
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
        { k: "slope_degree", label: "Độ dốc (°)", type: "number", step: "0.1", def: u.slope_degree ?? "", visIf: { k: "unit_type", in: ["AGRICULTURAL_LAND_PARCEL", "FOREST_PLOT_STAND"] } },
        { k: "earth_terrace_compliant", label: "Đã làm băng đất đồng mức (vùng dốc)", type: "bool", def: u.earth_terrace_compliant == null ? "" : String(u.earth_terrace_compliant), options: BOOL_OPTS, visIf: { k: "unit_type", in: ["AGRICULTURAL_LAND_PARCEL", "FOREST_PLOT_STAND"] } },
        { k: "forest_subzone_code", label: "Mã tiểu khu", def: u.forest_subzone_code || "", visIf: { k: "unit_type", in: ["FOREST_PLOT_STAND"] } },
        { k: "forest_compartment_code", label: "Mã khoảnh", def: u.forest_compartment_code || "", visIf: { k: "unit_type", in: ["FOREST_PLOT_STAND"] } },
        { k: "forest_plot_code", label: "Mã lô rừng", def: u.forest_plot_code || "", visIf: { k: "unit_type", in: ["FOREST_PLOT_STAND"] } },
        { k: "forest_origin_type", label: "Nguồn gốc rừng (nếu là lô rừng)", type: "select", def: u.forest_origin_type || "", options: FOREST_ORIGINS, visIf: { k: "unit_type", in: ["FOREST_PLOT_STAND"] } },
        { k: "aquaculture_water_type", label: "Loại hình mặt nước (nếu nuôi thủy sản)", type: "select", def: u.aquaculture_water_type || "", options: AQUA_WATERS , visIf: { k: "unit_type", in: ["AQUACULTURE_POND_CAGE"] } },
        { k: "vessel_reg_number", label: "Số đăng ký tàu cá (nếu là tàu cá)", def: u.vessel_reg_number || "" , visIf: { k: "unit_type", in: ["FISHING_VESSEL"] } },
        { k: "vessel_length_max_m", label: "Chiều dài lớn nhất tàu (m)", type: "number", step: "0.01", def: u.vessel_length_max_m ?? "" , visIf: { k: "unit_type", in: ["FISHING_VESSEL"] } },
        { k: "tech_safety_cert_no", label: "Số GCN an toàn kỹ thuật tàu cá", def: u.tech_safety_cert_no || "" , visIf: { k: "unit_type", in: ["FISHING_VESSEL"] } },
        { k: "vms_device_serial", label: "Số seri thiết bị giám sát hành trình (VMS)", def: u.vms_device_serial || "" , visIf: { k: "unit_type", in: ["FISHING_VESSEL"] } },
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
    openSheet("Khai thửa / ao / lô rừng", await parcelCreateFields(), async (p) => { await T("/spatial-units", { method: "POST", body: p }); invalidate("parcels"); });
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
    openSheet("Thêm chủ thể", await actorCreateFields(), async (p) => { await T("/actors", { method: "POST", body: p }); invalidate("actors"); });
  });
};

/* ---------------- reference catalogues (GD3, Bang 1-5) ---------------- */
const REF_KINDS = {
  ref_admin_units: { path: "/ref-admin-units", title: "Đơn vị hành chính", nameKey: "official_name", fields: [
    { k: "code", label: "Mã đơn vị hành chính", required: true, placeholder: "vd: 66, 650, 24370" },
    { k: "parent_unit_code", label: "Đơn vị cấp trên", type: "select", refKind: "ref_admin_units", empty: "— Cấp cao nhất —" },
    { k: "admin_level", label: "Cấp hành chính", type: "select", enum: "ADMIN_LEVELS" },
    { k: "official_name", label: "Tên chính thức" },
    { k: "puc_prefix_code", label: "Mã ghép mã số vùng trồng (PUC)" },
    { k: "is_active", label: "Đang hiệu lực", type: "bool" },
    { k: "boundary_polygon_gis", label: "Ranh giới GIS (GeoJSON)", type: "textarea" },
  ]},
  ref_market_regulations: { path: "/ref-market-regulations", title: "Thị trường & kiểm dịch", nameKey: "market_name", fields: [
    { k: "code", label: "Mã thị trường (ISO alpha-2)", required: true, placeholder: "vd: CN, US, EU" },
    { k: "market_name", label: "Tên thị trường" },
    { k: "requires_bilateral_pre_approval", label: "Bắt buộc phê duyệt trước song phương", type: "bool" },
    { k: "competent_authority_name", label: "Cơ quan thẩm quyền nước nhập khẩu" },
    { k: "protocol_reference_doc", label: "Nghị định thư / thỏa thuận dẫn chiếu" },
    { k: "quarantine_special_rules", label: "Quy định kiểm dịch đặc thù", type: "textarea" },
  ]},
  ref_active_substance_mrls: { path: "/ref-active-substance-mrls", title: "Hoạt chất & ngưỡng MRL", nameKey: "substance_name", fields: [
    { k: "code", label: "Mã quy tắc MRL", required: true, placeholder: "vd: MRL-CLP-CN" },
    { k: "substance_code", label: "Mã hoạt chất (CAS/CIPAC)" },
    { k: "substance_name", label: "Tên hoạt chất" },
    { k: "substance_category", label: "Phân loại hoạt chất", type: "select", enum: "SUBSTANCE_CATEGORIES" },
    { k: "market_code", label: "Thị trường áp dụng", type: "select", refKind: "ref_market_regulations", empty: "— Chọn thị trường —", addNew: true },
    { k: "commodity_group_code", label: "Mã nhóm nông sản" },
    { k: "approval_status", label: "Trạng thái pháp lý", type: "select", enum: "SUBSTANCE_APPROVAL_STATUSES" },
    { k: "mrl_threshold_value", label: "Ngưỡng MRL tối đa", type: "number", step: "0.000001" },
    { k: "mrl_measurement_unit", label: "Đơn vị đo MRL", type: "select", enum: "MRL_UNITS" },
    { k: "default_phi_days", label: "PHI mặc định (ngày)", type: "number" },
    { k: "legal_circular_ref", label: "Văn bản pháp quy dẫn chiếu" },
    { k: "effective_from", label: "Hiệu lực từ ngày", type: "date" },
    { k: "effective_to", label: "Hiệu lực đến ngày", type: "date" },
  ]},
  ref_certification_schemes: { path: "/ref-certification-schemes", title: "Tiêu chuẩn & quy chuẩn", nameKey: "scheme_name", fields: [
    { k: "code", label: "Mã tiêu chuẩn / quy chuẩn", required: true, placeholder: "vd: GLOBALGAP_V6" },
    { k: "scheme_name", label: "Tên tiêu chuẩn / quy chuẩn" },
    { k: "scheme_level", label: "Cấp độ tiêu chuẩn", type: "select", enum: "SCHEME_LEVELS" },
    { k: "applicable_sector", label: "Ngành áp dụng", type: "select", enum: "SCHEME_SECTORS" },
    { k: "cb_accreditation_req", label: "Yêu cầu với tổ chức chứng nhận" },
  ]},
  ref_transport_modes: { path: "/ref-transport-modes", title: "Phương thức vận tải", nameKey: "mode_name", fields: [
    { k: "code", label: "Mã phương thức vận tải", required: true, placeholder: "vd: ROAD_TRUCK" },
    { k: "mode_name", label: "Tên phương thức" },
    { k: "vehicle_id_format_rule", label: "Quy tắc định danh phương tiện" },
    { k: "customs_circular_ref", label: "Văn bản hải quan dẫn chiếu" },
  ]},
};
const fmtRefOpt = (kind) => (r) => ({ v: r.code, t: `${r.code}${r[REF_KINDS[kind].nameKey] ? " · " + r[REF_KINDS[kind].nameKey] : ""}` });
async function refFormFields(kind, rec) {
  const cfg = REF_KINDS[kind];
  const out = [];
  for (const f of cfg.fields) {
    const nf = { k: f.k, label: f.label, type: f.type, required: f.required, placeholder: f.placeholder, step: f.step };
    if (rec && rec[f.k] !== undefined && rec[f.k] !== null) nf.def = typeof rec[f.k] === "object" ? JSON.stringify(rec[f.k]) : rec[f.k];
    if (f.type === "select" && f.enum) nf.options = (window.IAICT_META.enums[f.enum] || []).map((o) => ({ ...o }));
    if (f.type === "select" && f.refKind) {
      const items = await ensure(f.refKind, REF_KINDS[f.refKind].path).catch(() => []);
      nf.options = [{ v: "", t: f.empty || "— Chọn —" }, ...items.map(fmtRefOpt(f.refKind))];
      if (f.addNew) {
        nf.addNew = (done, back) => quickRef(f.refKind, done, back);
        nf.refreshOptions = async () => optOf(await ensure(f.refKind, REF_KINDS[f.refKind].path), f.empty || "— Chọn —", fmtRefOpt(f.refKind));
      }
    }
    out.push(nf);
  }
  return out;
}
async function quickRef(kind, done, back) {
  try {
    openSheet("Thêm " + REF_KINDS[kind].title.toLowerCase(), await refFormFields(kind), async (p) => {
      const r = await T(REF_KINDS[kind].path, { method: "POST", body: p });
      invalidate(kind); toast("Đã thêm " + r.code); done(r.code);
    }, { onCancel: back });
  } catch { toast("Không mở được form danh mục.", true); back(); }
}
let refTab = "ref_admin_units";
VIEWS.refs = async () => {
  const el = $("#view");
  el.innerHTML = `<div class="section-head"><h2>📚 Danh mục tham chiếu</h2>
    <button class="btn btn-ghost btn-sm" id="reload">↻ Làm mới</button></div>
    <div class="chips">${Object.entries(REF_KINDS).map(([k, c]) => `<button class="chip${k === refTab ? " on" : ""}" data-reftab="${k}">${c.title}</button>`).join("")}</div>
    <div id="refBody"></div>`;
  $("#reload").onclick = () => { invalidate(refTab); navigate("refs", true); };
  el.querySelectorAll("[data-reftab]").forEach((b) => b.onclick = () => { refTab = b.dataset.reftab; navigate("refs", true); });
  const cfg = REF_KINDS[refTab];
  const body = el.querySelector("#refBody");
  try {
    const items = await ensure(refTab, cfg.path);
    body.innerHTML = items.length ? `<div class="list">${items.map((r) => `
      <div class="card" data-card="${esc(r.code)}"><div class="thumb slate">📚</div><div class="body">
        <div class="title">${esc(r.code)}</div>
        <div class="sub">${esc(r[cfg.nameKey] || "")}</div>
        <div style="margin-top:8px"><button class="btn btn-ghost btn-sm" data-edit-ref="${esc(r.code)}">✏️ Sửa</button> <button class="btn btn-ghost btn-sm" data-del-ref="${esc(r.code)}">🗑️ Xoá</button></div>
      </div></div>`).join("")}</div>`
      : emptyState("📚", "Chưa có mục nào", "Bấm nút + để thêm vào danh mục " + cfg.title.toLowerCase() + ".");
    body.querySelectorAll("[data-edit-ref]").forEach((b) => b.onclick = async () => {
      const rec = items.find((x) => x.code === b.dataset.editRef);
      openSheet("Sửa " + rec.code, await refFormFields(refTab, rec), async (p) => {
        delete p.code;
        await T(`${cfg.path}/${encodeURIComponent(rec.code)}`, { method: "PATCH", body: p });
        invalidate(refTab);
      });
    });
    body.querySelectorAll("[data-del-ref]").forEach((b) => b.onclick = () =>
      confirmDelete(`mục ${b.dataset.delRef}`, `${cfg.path}/${encodeURIComponent(b.dataset.delRef)}`, [refTab]));
    wireCardDetails(body, items, (r) => `${cfg.title} ${r.code}`, refTab);
  } catch (err) { body.innerHTML = banner(err); }
  fab("Thêm vào danh mục", async () => {
    openSheet("Thêm " + cfg.title.toLowerCase(), await refFormFields(refTab), async (p) => {
      await T(cfg.path, { method: "POST", body: p }); invalidate(refTab);
    });
  });
};

/* ---------------- market approvals, warnings, certifications (GD3 Bang 8-10) ---------------- */
const GD3A_KINDS = {
  zone_market_approvals: { path: "/zone-market-approvals", title: "Phê duyệt thị trường", editable: true,
    titleOf: (r) => `${r.zone_code || "?"} · ${r.market_code || "?"}`,
    subOf: (r) => r.foreign_approval_code || "",
    fields: [
      { k: "zone_code", label: "Vùng sản xuất", type: "select", target: "zones", empty: "— Chọn vùng —" },
      { k: "market_code", label: "Thị trường đích", type: "select", target: "ref_market_regulations", empty: "— Chọn thị trường —" },
      { k: "foreign_approval_code", label: "Mã phê duyệt của nước nhập khẩu" },
      { k: "submitted_to_foreign_date", label: "Ngày gửi hồ sơ sang nước nhập khẩu", type: "date" },
      { k: "foreign_approved_date", label: "Ngày nước nhập khẩu phê duyệt", type: "date" },
      { k: "foreign_market_status", label: "Trạng thái tại thị trường đích", type: "select", enum: "FOREIGN_MARKET_STATUSES" },
    ]},
  foreign_warnings: { path: "/foreign-warnings", title: "Cảnh báo quốc tế", editable: false,
    titleOf: (r) => r.official_notice_number || `${r.zone_code || "?"} · ${r.market_code || "?"}`,
    subOf: (r) => r.detected_pest_or_substance || "",
    fields: [
      { k: "zone_code", label: "Vùng bị cảnh báo", type: "select", target: "zones", empty: "— Chọn vùng —" },
      { k: "market_code", label: "Thị trường cảnh báo", type: "select", target: "ref_market_regulations", empty: "— Chọn thị trường —" },
      { k: "violated_facility_actor_code", label: "Cơ sở đóng gói liên đới", type: "select", target: "actors", empty: "— Không có —" },
      { k: "violated_packing_lot_code", label: "Lô thành phẩm bị vi phạm", type: "select", target: "packing_lots", empty: "— Không có —", noAdd: true },
      { k: "official_notice_number", label: "Số công hàm / thông báo cảnh báo" },
      { k: "notification_date", label: "Ngày phát hành cảnh báo", type: "date" },
      { k: "violation_type", label: "Loại vi phạm", type: "select", enum: "VIOLATION_TYPES" },
      { k: "detected_pest_or_substance", label: "Sinh vật / hoạt chất bị phát hiện" },
      { k: "foreign_sanction_action", label: "Biện pháp chế tài", type: "select", enum: "FOREIGN_SANCTION_ACTIONS" },
      { k: "remediation_report_sent_at", label: "Ngày gửi báo cáo khắc phục", type: "date" },
      { k: "sanction_lifted_date", label: "Ngày được khôi phục mã số", type: "date" },
    ]},
  entity_certifications: { path: "/entity-certifications", title: "Chứng nhận", editable: true,
    titleOf: (r) => r.certificate_number || r.scheme_code || "Chứng nhận",
    subOf: (r) => r.cert_body_name || "",
    fields: [
      { k: "certified_entity_type", label: "Loại thực thể được chứng nhận", type: "select", enum: "CERT_ENTITY_TYPES" },
      { k: "zone_code", label: "Vùng sản xuất", type: "select", target: "zones", empty: "— Không gắn —" },
      { k: "facility_actor_code", label: "Cơ sở đóng gói / chế biến", type: "select", target: "actors", empty: "— Không gắn —" },
      { k: "scheme_code", label: "Tiêu chuẩn / quy chuẩn", type: "select", target: "ref_certification_schemes", empty: "— Chọn tiêu chuẩn —" },
      { k: "certificate_number", label: "Số giấy chứng nhận" },
      { k: "cert_body_name", label: "Tổ chức chứng nhận" },
      { k: "issue_date", label: "Ngày cấp", type: "date" },
      { k: "expiry_date", label: "Ngày hết hạn", type: "date" },
      { k: "cert_status", label: "Trạng thái chứng nhận", type: "select", enum: "CERT_STATUSES" },
      { k: "cert_scan_url", label: "Bản sao điện tử (URL)" },
    ]},
};
const GD3A_TARGETS = {
  zones: { path: "/zones", fmt: fmtZoneOpt, addNew: (d, b) => quickZone(d, b) },
  actors: { path: "/actors", fmt: fmtActorOpt, addNew: (d, b) => quickActor(d, b) },
  packing_lots: { path: "/packing-lots", fmt: (r) => ({ v: r.code, t: r.code }), addNew: null },
};
async function gd3FormFields(kind, rec, cfgs) {
  const cfg = (cfgs || GD3A_KINDS)[kind];
  const out = [];
  for (const f of cfg.fields) {
    const nf = { k: f.k, label: f.label, type: f.type };
    if (rec && rec[f.k] !== undefined && rec[f.k] !== null) nf.def = rec[f.k];
    if (f.type === "select" && f.enum) nf.options = (window.IAICT_META.enums[f.enum] || []).map((o) => ({ ...o }));
    if (f.type === "select" && f.target) {
      const tgt = GD3A_TARGETS[f.target] || (REF_KINDS[f.target] ? { path: REF_KINDS[f.target].path, fmt: fmtRefOpt(f.target), addNew: (d, b) => quickRef(f.target, d, b) } : null);
      const items = await ensure(f.target, tgt.path).catch(() => []);
      nf.options = [{ v: "", t: f.empty || "— Chọn —" }, ...items.map(tgt.fmt)];
      if (tgt.addNew && !f.noAdd) {
        nf.addNew = tgt.addNew;
        nf.refreshOptions = async () => optOf(await ensure(f.target, tgt.path), f.empty || "— Chọn —", tgt.fmt);
      }
    }
    out.push(nf);
  }
  return out;
}
let gd3Tab = "zone_market_approvals";
VIEWS.market = async () => {
  const el = $("#view");
  el.innerHTML = `<div class="section-head"><h2>🌏 Thị trường & chứng nhận</h2>
    <button class="btn btn-ghost btn-sm" id="reload">↻ Làm mới</button></div>
    <div class="chips">${Object.entries(GD3A_KINDS).map(([k, c]) => `<button class="chip${k === gd3Tab ? " on" : ""}" data-gd3tab="${k}">${c.title}</button>`).join("")}</div>
    <div id="gd3Body"></div>`;
  $("#reload").onclick = () => { invalidate(gd3Tab); navigate("market", true); };
  el.querySelectorAll("[data-gd3tab]").forEach((b) => b.onclick = () => { gd3Tab = b.dataset.gd3tab; navigate("market", true); });
  const cfg = GD3A_KINDS[gd3Tab];
  const body = el.querySelector("#gd3Body");
  try {
    const items = await ensure(gd3Tab, cfg.path);
    body.innerHTML = items.length ? `<div class="list">${items.map((r) => `
      <div class="card" data-card="${esc(r.code ?? r.id)}"><div class="thumb slate">🌏</div><div class="body">
        <div class="title">${esc(cfg.titleOf(r))}</div>
        <div class="sub">${esc(cfg.subOf(r))}</div>
        ${cfg.editable ? `<div style="margin-top:8px"><button class="btn btn-ghost btn-sm" data-edit-gd3="${r.id}">✏️ Sửa</button></div>` : ""}
      </div></div>`).join("")}</div>`
      : emptyState("🌏", "Chưa có bản ghi nào", "Bấm nút + để thêm " + cfg.title.toLowerCase() + ".");
    if (cfg.editable) body.querySelectorAll("[data-edit-gd3]").forEach((b) => b.onclick = async () => {
      const rec = items.find((x) => x.id === Number(b.dataset.editGd3));
      openSheet("Sửa " + cfg.titleOf(rec), await gd3FormFields(gd3Tab, rec), async (p) => {
        await T(`${cfg.path}/${rec.id}`, { method: "PATCH", body: p });
        invalidate(gd3Tab);
      });
    });
    wireCardDetails(body, items, (r) => cfg.titleOf(r), gd3Tab);
  } catch (err) { body.innerHTML = banner(err); }
  fab("Thêm " + cfg.title.toLowerCase(), async () => {
    openSheet("Thêm " + cfg.title.toLowerCase(), await gd3FormFields(gd3Tab), async (p) => {
      await T(cfg.path, { method: "POST", body: p }); invalidate(gd3Tab);
    });
  });
};

/* ---------------- livestock + monitoring logs (GD3 Bang 14, 16, 19-22) ---------------- */
const GD3B_KINDS = {
  iot_devices: { path: "/iot-devices", title: "Thiết bị IoT", editable: false,
    titleOf: (r) => `${r.code || "Thiết bị"}${r.device_type ? " · " + r.device_type : ""}`,
    subOf: (r) => r.parcel_code ? "Thửa/ao: " + r.parcel_code : (r.zone_code ? "Vùng: " + r.zone_code : ""),
    fields: [
      { k: "code", label: "Mã thiết bị" },
      { k: "device_type", label: "Loại thiết bị", type: "select", enum: "IOT_DEVICE_TYPES" },
      { k: "zone_code", label: "Vùng lắp đặt", type: "select", target: "zones", empty: "— Chọn vùng —" },
      { k: "parcel_code", label: "Thửa / ao lắp đặt", type: "select", target: "spatial_units", empty: "— Không gắn —" },
      { k: "firmware_version", label: "Phiên bản firmware" },
      { k: "installed_at", label: "Ngày lắp đặt", type: "date" },
    ]},
  livestock_units: { path: "/livestock-units", title: "Cá thể / đàn vật nuôi", editable: true,
    titleOf: (r) => `${r.code || "?"}${r.species_code ? " · " + r.species_code : ""}`,
    subOf: (r) => r.facility_actor_code ? "Cơ sở: " + r.facility_actor_code : "",
    fields: [
      { k: "code", label: "Mã thẻ tai / mã đàn" },
      { k: "facility_actor_code", label: "Cơ sở chăn nuôi", type: "select", target: "actors", empty: "— Chọn cơ sở —" },
      { k: "management_granularity", label: "Cấp độ định danh", type: "select", enum: "LIVESTOCK_GRANULARITY" },
      { k: "species_code", label: "Mã loài (VD: CATTLE, BUFFALO)" },
      { k: "breed_variety_name", label: "Tên giống / nguồn gốc giống" },
      { k: "birth_or_import_date", label: "Ngày sinh / nhập đàn", type: "date" },
      { k: "initial_head_count", label: "Số lượng ban đầu (con)", type: "number" },
      { k: "current_head_count", label: "Số lượng hiện tại (con)", type: "number" },
      { k: "lifecycle_status", label: "Trạng thái vòng đời", type: "select", enum: "LIVESTOCK_LIFECYCLE" },
    ]},
  pre_harvest_supervisions: { path: "/pre-harvest-supervisions", title: "Giám sát trước thu hoạch", editable: false,
    titleOf: (r) => `${r.zone_code || "?"} · ${r.report_minutes_no || r.registration_date || ""}`,
    subOf: (r) => r.supervising_agency_name || "",
    fields: [
      { k: "plan_code", label: "Vụ mùa / kế hoạch", type: "select", target: "crop_plans", empty: "— Chọn vụ mùa —" },
      { k: "zone_code", label: "Vùng được giám sát", type: "select", target: "zones", empty: "— Chọn vùng —" },
      { k: "registration_date", label: "Ngày đăng ký giám sát", type: "date" },
      { k: "expected_harvest_start", label: "Ngày dự kiến bắt đầu thu hoạch", type: "date" },
      { k: "supervising_agency_name", label: "Cơ quan giám sát" },
      { k: "supervision_date", label: "Ngày giám sát thực địa", type: "date" },
      { k: "pest_control_compliant", label: "Quản lý sinh vật gây hại đạt (IPM)", type: "bool" },
      { k: "diary_records_compliant", label: "Nhật ký & chứng từ đạt", type: "bool" },
      { k: "supervision_outcome", label: "Kết quả giám sát", type: "select", enum: "SUPERVISION_OUTCOMES" },
      { k: "report_minutes_no", label: "Số biên bản giám sát" },
    ]},
  monitoring_declarations: { path: "/monitoring-declarations", title: "Biên bản giám sát / kê khai", editable: false,
    titleOf: (r) => `${r.zone_code || "?"} · ${r.inspection_timestamp || ""}`,
    subOf: (r) => r.pest_species_detected || "",
    fields: [
      { k: "zone_code", label: "Vùng", type: "select", target: "zones", empty: "— Chọn vùng —" },
      { k: "plan_code", label: "Vụ mùa liên quan", type: "select", target: "crop_plans", empty: "— Không gắn —" },
      { k: "declarant_actor_code", label: "Đơn vị kê khai / được kiểm tra", type: "select", target: "actors", empty: "— Chọn đơn vị —" },
      { k: "monitoring_type", label: "Loại hình giám sát", type: "select", enum: "MONITORING_TYPES" },
      { k: "inspection_timestamp", label: "Thời điểm giám sát / kê khai", type: "datetime-local" },
      { k: "pest_species_detected", label: "Sinh vật gây hại phát hiện" },
      { k: "pest_density_index", label: "Mật độ / tỷ lệ hại" },
      { k: "quarantine_cert_no", label: "Số giấy chứng nhận kiểm dịch" },
      { k: "compliance_conclusion", label: "Kết luận kiểm tra", type: "select", enum: "COMPLIANCE_CONCLUSIONS" },
    ]},
  water_quality_tests: { path: "/water-quality-tests", title: "Quan trắc nước", editable: false,
    titleOf: (r) => `${r.parcel_code || "Nước"} · ${r.measured_timestamp || ""}`,
    subOf: (r) => r.ph_value !== undefined && r.ph_value !== null ? "pH " + r.ph_value : "",
    fields: [
      { k: "monitoring_id", label: "Biên bản giám sát (ID)", type: "number" },
      { k: "parcel_code", label: "Thửa / ao được đo", type: "select", target: "spatial_units", empty: "— Chọn thửa / ao —" },
      { k: "measured_timestamp", label: "Thời điểm lấy mẫu đo", type: "datetime-local" },
      { k: "water_salinity_permille", label: "Độ mặn (‰)", type: "number" },
      { k: "ph_value", label: "Độ pH", type: "number" },
      { k: "dissolved_oxygen_mg_l", label: "Oxy hòa tan DO (mg/l)", type: "number" },
      { k: "water_temp_celsius", label: "Nhiệt độ nước (°C)", type: "number" },
      { k: "nh3_unionized_mg_l", label: "NH3 tự do (mg/l)", type: "number" },
      { k: "no2_nitrite_mg_l", label: "NO2 nitrit (mg/l)", type: "number" },
      { k: "alkalinity_mg_l", label: "Độ kiềm (mg CaCO3/l)", type: "number" },
      { k: "is_within_safe_range", label: "Đạt ngưỡng an toàn", type: "bool" },
    ]},
  residue_test_details: { path: "/residue-test-details", title: "Xét nghiệm dư lượng", editable: false,
    titleOf: (r) => r.lab_test_report_no || r.mrl_rule_code || "Xét nghiệm",
    subOf: (r) => r.testing_lab_name || "",
    fields: [
      { k: "monitoring_id", label: "Biên bản giám sát (ID)", type: "number" },
      { k: "sampling_standard_code", label: "Phương pháp lấy mẫu" },
      { k: "mrl_rule_code", label: "Quy tắc MRL áp dụng", type: "select", target: "ref_active_substance_mrls", empty: "— Chọn quy tắc —" },
      { k: "measured_value", label: "Giá trị đo được", type: "number" },
      { k: "measurement_unit", label: "Đơn vị đo", type: "select", enum: "MRL_UNITS" },
      { k: "applied_mrl_limit", label: "Ngưỡng MRL áp dụng", type: "number" },
      { k: "testing_lab_name", label: "Phòng thử nghiệm" },
      { k: "lab_test_report_no", label: "Số phiếu kết quả thử nghiệm" },
    ]},
  livestock_decl_items: { path: "/livestock-decl-items", title: "Dòng kê khai chăn nuôi", editable: false,
    titleOf: (r) => `${r.species_category_code || "?"} · ${r.declared_quantity ?? ""}`,
    subOf: (r) => r.farming_purpose || "",
    fields: [
      { k: "monitoring_id", label: "Bản kê khai (ID)", type: "number" },
      { k: "species_category_code", label: "Nhóm vật nuôi", type: "select", enum: "DECL_SPECIES_CATEGORIES" },
      { k: "declared_quantity", label: "Số lượng kê khai", type: "number" },
      { k: "quantity_unit", label: "Đơn vị tính", type: "select", enum: "DECL_QUANTITY_UNITS" },
      { k: "farming_purpose", label: "Mục đích nuôi" },
    ]},
};
Object.assign(GD3A_TARGETS, {
  crop_plans: { path: "/crop-plans", fmt: fmtPlanOpt, addNew: (d, b) => quickPlan(d, b) },
  spatial_units: { path: "/spatial-units", fmt: fmtParcelOpt, addNew: (d, b) => quickParcel(d, b) },
});
let gd3bTab = "iot_devices";
let pendingDeviceKey = null;
function showDeviceKey(code, key) {
  openSheet("🔑 Khóa thiết bị " + code, [
    { k: "note1", type: "note", label: "Khóa này chỉ hiện MỘT LẦN — hệ thống chỉ lưu bản băm nên không xem lại được. Hãy sao chép và cấu hình ngay vào thiết bị / gateway; thiết bị gửi số đo kèm tiêu đề X-Iot-Key với khóa này." },
    { k: "_device_key", label: "Khóa thiết bị", def: key },
  ], async () => {});
}
VIEWS.monitor = async () => {
  const el = $("#view");
  el.innerHTML = `<div class="section-head"><h2>🔬 Giám sát & kê khai</h2>
    <button class="btn btn-ghost btn-sm" id="reload">↻ Làm mới</button></div>
    <div class="chips">${Object.entries(GD3B_KINDS).map(([k, c]) => `<button class="chip${k === gd3bTab ? " on" : ""}" data-gd3btab="${k}">${c.title}</button>`).join("")}</div>
    <div id="gd3bBody"></div>`;
  $("#reload").onclick = () => { invalidate(gd3bTab); navigate("monitor", true); };
  el.querySelectorAll("[data-gd3btab]").forEach((b) => b.onclick = () => { gd3bTab = b.dataset.gd3btab; navigate("monitor", true); });
  const cfg = GD3B_KINDS[gd3bTab];
  const body = el.querySelector("#gd3bBody");
  try {
    const items = await ensure(gd3bTab, cfg.path);
    body.innerHTML = items.length ? `<div class="list">${items.map((r) => `
      <div class="card" data-card="${esc(r.code ?? r.id)}"><div class="thumb slate">🔬</div><div class="body">
        <div class="title">${esc(cfg.titleOf(r))}</div>
        <div class="sub">${esc(cfg.subOf(r))}</div>
        ${cfg.editable ? `<div style="margin-top:8px"><button class="btn btn-ghost btn-sm" data-edit-gd3b="${r.id}">✏️ Sửa</button></div>` : ""}
        ${gd3bTab === "iot_devices" ? `<div style="margin-top:8px"><button class="btn btn-ghost btn-sm" data-iot-rotate="${esc(r.code)}">🔑 Cấp / đổi khóa</button> <button class="btn btn-ghost btn-sm" data-iot-revoke="${esc(r.code)}">🚫 Thu hồi khóa</button></div>` : ""}
      </div></div>`).join("")}</div>`
      : emptyState("🔬", "Chưa có bản ghi nào", "Bấm nút + để thêm " + cfg.title.toLowerCase() + ".");
    if (cfg.editable) body.querySelectorAll("[data-edit-gd3b]").forEach((b) => b.onclick = async () => {
      const rec = items.find((x) => x.id === Number(b.dataset.editGd3b));
      openSheet("Sửa " + cfg.titleOf(rec), await gd3FormFields(gd3bTab, rec, GD3B_KINDS), async (p) => {
        await T(`${cfg.path}/${rec.id}`, { method: "PATCH", body: p });
        invalidate(gd3bTab);
      });
    });
    if (gd3bTab === "iot_devices") {
      body.querySelectorAll("[data-iot-rotate]").forEach((b) => b.onclick = () => {
        const code = b.dataset.iotRotate;
        openSheet("Cấp / đổi khóa cho " + code, [
          { k: "note", type: "note", label: "Khóa mới sẽ thay thế khóa hiện tại ngay lập tức — thiết bị đang dùng khóa cũ sẽ bị từ chối cho tới khi được cấu hình khóa mới." },
        ], async () => {
          const res = await T(`/iot-devices/${code}/rotate-key`, { method: "POST" });
          pendingDeviceKey = { code, key: res.device_key };
        });
      });
      body.querySelectorAll("[data-iot-revoke]").forEach((b) => b.onclick = () => {
        const code = b.dataset.iotRevoke;
        openSheet("Thu hồi khóa của " + code, [
          { k: "note", type: "note", label: "Thiết bị sẽ không gửi được số đo nữa cho tới khi được cấp khóa mới." },
        ], async () => { await T(`/iot-devices/${code}/revoke-key`, { method: "POST" }); });
      });
    }
    wireCardDetails(body, items, (r) => cfg.titleOf(r), gd3bTab);
    if (pendingDeviceKey) { const pk = pendingDeviceKey; pendingDeviceKey = null; showDeviceKey(pk.code, pk.key); }
  } catch (err) { body.innerHTML = banner(err); }
  fab("Thêm " + cfg.title.toLowerCase(), async () => {
    openSheet("Thêm " + cfg.title.toLowerCase(), await gd3FormFields(gd3bTab, null, GD3B_KINDS), async (p) => {
      const res = await T(cfg.path, { method: "POST", body: p }); invalidate(gd3bTab);
      if (gd3bTab === "iot_devices" && res && res.device_key) pendingDeviceKey = { code: p.code, key: res.device_key };
    });
  });
};

/* ---------------- transport + recall (GD3 Bang 28, 31) ---------------- */
const GD3C_KINDS = {
  transport_trips: { path: "/transport-trips", title: "Chuyến vận chuyển", editable: true,
    titleOf: (r) => `${r.vehicle_vessel_identifier || r.despatch_advice_asn_no || "Chuyến"} · ${r.departure_timestamp || ""}`,
    subOf: (r) => r.driver_captain_name || "",
    fields: [
      { k: "carrier_actor_code", label: "Đơn vị vận chuyển", type: "select", target: "actors", empty: "— Chọn đơn vị —" },
      { k: "packing_lot_code", label: "Lô thành phẩm vận chuyển", type: "select", target: "packing_lots", empty: "— Không có —", noAdd: true },
      { k: "harvest_lot_code", label: "Lô thu hoạch vận chuyển trực tiếp", type: "select", target: "lots", empty: "— Không có —" },
      { k: "transport_mode_code", label: "Phương thức vận chuyển", type: "select", target: "ref_transport_modes", empty: "— Chọn phương thức —" },
      { k: "vehicle_vessel_identifier", label: "Biển số xe / số hiệu tàu / container" },
      { k: "driver_captain_name", label: "Người điều khiển phương tiện" },
      { k: "despatch_advice_asn_no", label: "Số ASN / vận đơn / hóa đơn" },
      { k: "origin_actor_code", label: "Cơ sở giao hàng", type: "select", target: "actors", empty: "— Chọn cơ sở —" },
      { k: "destination_actor_code", label: "Cơ sở nhận hàng", type: "select", target: "actors", empty: "— Chọn cơ sở —" },
      { k: "departure_timestamp", label: "Thời gian xuất phát", type: "datetime-local" },
      { k: "arrival_timestamp", label: "Thời gian đến đích", type: "datetime-local" },
      { k: "storage_temp_celsius", label: "Nhiệt độ bảo quản TB (°C)", type: "number" },
    ]},
  recall_cases: { path: "/recall-cases", title: "Hồ sơ thu hồi", editable: true,
    titleOf: (r) => r.traceability_code || r.recall_reason || "Hồ sơ thu hồi",
    subOf: (r) => r.primary_collection_address || "",
    fields: [
      { k: "traceability_code", label: "Mã truy xuất của lô bị thu hồi" },
      { k: "affected_zone_code", label: "Vùng liên đới", type: "select", target: "zones", empty: "— Không gắn —" },
      { k: "isolated_household_actor_code", label: "Hộ bị khoanh vùng", type: "select", target: "actors", empty: "— Không gắn —" },
      { k: "recall_initiation_type", label: "Hình thức thu hồi", type: "select", enum: "RECALL_INITIATION_TYPES" },
      { k: "risk_classification", label: "Phân loại rủi ro", type: "select", enum: "RISK_CLASSES" },
      { k: "recall_reason", label: "Lý do thu hồi" },
      { k: "qty_produced_imported", label: "Số lượng đã sản xuất / nhập khẩu", type: "number" },
      { k: "qty_consumed_sold", label: "Số lượng đã tiêu thụ", type: "number" },
      { k: "qty_recovered", label: "Số lượng đã thu hồi", type: "number" },
      { k: "primary_collection_address", label: "Địa điểm tập kết thu hồi" },
      { k: "post_recall_handling_method", label: "Xử lý sau thu hồi", type: "select", enum: "RECALL_HANDLING_METHODS" },
      { k: "handling_plan_approved_date", label: "Ngày duyệt phương án xử lý", type: "date" },
      { k: "fix_report_submitted_date", label: "Thời điểm gửi báo cáo khắc phục", type: "datetime-local" },
      { k: "authority_recirc_reply_due", label: "Hạn trả lời cho lưu thông lại", type: "datetime-local" },
      { k: "recirculation_approval_doc", label: "Số VB đồng ý lưu thông lại" },
      { k: "repurpose_or_reexport_doc", label: "Số HĐ chuyển mục đích / tờ khai tái xuất" },
    ]},
};
Object.assign(GD3A_TARGETS, {
  lots: { path: "/lots", fmt: fmtLotOpt, addNew: (d, b) => quickLot(d, b) },
});
let gd3cTab = "transport_trips";
VIEWS.logistics = async () => {
  const el = $("#view");
  el.innerHTML = `<div class="section-head"><h2>🚚 Vận chuyển & thu hồi</h2>
    <button class="btn btn-ghost btn-sm" id="reload">↻ Làm mới</button></div>
    <div class="chips">${Object.entries(GD3C_KINDS).map(([k, c]) => `<button class="chip${k === gd3cTab ? " on" : ""}" data-gd3ctab="${k}">${c.title}</button>`).join("")}</div>
    <div id="gd3cBody"></div>`;
  $("#reload").onclick = () => { invalidate(gd3cTab); navigate("logistics", true); };
  el.querySelectorAll("[data-gd3ctab]").forEach((b) => b.onclick = () => { gd3cTab = b.dataset.gd3ctab; navigate("logistics", true); });
  const cfg = GD3C_KINDS[gd3cTab];
  const body = el.querySelector("#gd3cBody");
  try {
    const items = await ensure(gd3cTab, cfg.path);
    body.innerHTML = items.length ? `<div class="list">${items.map((r) => `
      <div class="card" data-card="${esc(r.code ?? r.id)}"><div class="thumb slate">🚚</div><div class="body">
        <div class="title">${esc(cfg.titleOf(r))}</div>
        <div class="sub">${esc(cfg.subOf(r))}</div>
        ${cfg.editable ? `<div style="margin-top:8px"><button class="btn btn-ghost btn-sm" data-edit-gd3c="${r.id}">✏️ Sửa</button></div>` : ""}
      </div></div>`).join("")}</div>`
      : emptyState("🚚", "Chưa có bản ghi nào", "Bấm nút + để thêm " + cfg.title.toLowerCase() + ".");
    if (cfg.editable) body.querySelectorAll("[data-edit-gd3c]").forEach((b) => b.onclick = async () => {
      const rec = items.find((x) => x.id === Number(b.dataset.editGd3c));
      openSheet("Sửa " + cfg.titleOf(rec), await gd3FormFields(gd3cTab, rec, GD3C_KINDS), async (p) => {
        await T(`${cfg.path}/${rec.id}`, { method: "PATCH", body: p });
        invalidate(gd3cTab);
      });
    });
    wireCardDetails(body, items, (r) => cfg.titleOf(r), gd3cTab);
  } catch (err) { body.innerHTML = banner(err); }
  fab("Thêm " + cfg.title.toLowerCase(), async () => {
    openSheet("Thêm " + cfg.title.toLowerCase(), await gd3FormFields(gd3cTab, null, GD3C_KINDS), async (p) => {
      await T(cfg.path, { method: "POST", body: p }); invalidate(gd3cTab);
    });
  });
};

/* ---------------- reports: the 3 dossier views, computed live ---------------- */
const REPORT_TABS = [
  { id: "zone", path: "/reports/zone-metrics", title: "Chỉ số vùng",
    cols: [["zone_code", "Vùng"], ["puc_status", "Trạng thái mã"], ["declared_area_ha", "Diện tích khai (ha)"], ["linked_parcels", "Thửa liên kết"], ["linked_area_m2", "Diện tích liên kết (m²)"], ["plans", "Vụ mùa"], ["lots", "Lô"], ["harvested_kg", "Đã thu (kg)"]] },
  { id: "cycle", path: "/reports/cycle-mass-balance", title: "Cân bằng vụ mùa",
    cols: [["plan_code", "Vụ mùa"], ["zone_code", "Vùng"], ["target_yield_kg", "Trần sản lượng (kg)"], ["harvested_kg", "Đã thu (kg)"], ["remaining_kg", "Còn lại (kg)"], ["harvested_pct", "% đạt"]] },
  { id: "packing", path: "/reports/packing-mass-balance", title: "Cân bằng đóng gói",
    cols: [["packing_lot_code", "Lô đóng gói"], ["facility_code", "Cơ sở"], ["inputs_kg", "Đầu vào (kg)"], ["yield_norm_ratio", "Định mức thu hồi"], ["expected_output_kg", "Đầu ra kỳ vọng (kg)"], ["output_weight_kg", "Đầu ra thực (kg)"], ["variance_kg", "Chênh lệch (kg)"]] },
  { id: "integrity", path: null, title: "🧾 Toàn vẹn dữ liệu" },
];
let reportTab = "zone";
VIEWS.reports = async () => {
  const el = $("#view");
  const tab = REPORT_TABS.find((t) => t.id === reportTab);
  el.innerHTML = `<div class="section-head"><h2>📊 Báo cáo truy xuất</h2>
    <button class="btn btn-ghost btn-sm" id="reload">↻ Làm mới</button></div>
    <div class="chips">${REPORT_TABS.map((t) => `<button class="chip${t.id === reportTab ? " on" : ""}" data-reptab="${t.id}">${t.title}</button>`).join("")}</div>
    <div id="repBody"></div>`;
  $("#reload").onclick = () => navigate("reports", true);
  el.querySelectorAll("[data-reptab]").forEach((b) => b.onclick = () => { reportTab = b.dataset.reptab; navigate("reports", true); });
  const body = el.querySelector("#repBody");
  if (reportTab === "integrity") { renderIntegrity(body); return; }
  try {
    const data = await T(tab.path);
    const items = data.items || [];
    body.innerHTML = items.length ? `<div class="card" style="overflow-x:auto"><table class="tbl">
      <thead><tr>${tab.cols.map((c) => `<th>${c[1]}</th>`).join("")}</tr></thead>
      <tbody>${items.map((r) => `<tr>${tab.cols.map((c) => `<td>${esc(r[c[0]] === null || r[c[0]] === undefined ? "—" : r[c[0]])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`
      : emptyState("📊", "Chưa có dữ liệu", "Báo cáo sẽ hiện khi có dữ liệu tương ứng.");
  } catch (err) { body.innerHTML = banner(err); }
};

/* ---------------- data integrity (D-10): checkpoints, verify, proofs ---------------- */
const IG_REASON_VI = {
  ROW_COUNT_MISMATCH: "Số bản ghi trong khoảng niêm phong đã thay đổi (bị xóa hoặc chèn thêm)",
  CHAIN_MISMATCH: "Chuỗi băm không khớp — nội dung một bản ghi đã bị sửa sau khi niêm phong",
  ROOT_MISMATCH: "Merkle root không khớp với dữ liệu hiện tại",
  PREV_ROOT_MISMATCH: "Liên kết giữa các checkpoint liên tiếp bị đứt",
};
async function renderIntegrity(body) {
  const short = (h) => (h ? h.slice(0, 16) + "…" : "—");
  async function draw() {
    const data = await T("/integrity/checkpoints");
    const items = data.items || [];
    body.innerHTML = `
      <div class="card"><div class="body">
        <div class="title">Niêm phong & kiểm chứng nhật ký kiểm toán</div>
        <div class="sub">Đã niêm phong <b>${data.sealed_rows}</b> bản ghi · Chưa niêm phong <b>${data.unsealed_rows}</b> · Chuẩn hoá RFC 8785 (JCS) + SHA-256/Merkle · Neo blockchain: <b>chưa kích hoạt</b> (chờ quyết định Q.2)</div>
        <div style="margin-top:10px; display:flex; gap:8px; flex-wrap:wrap">
          <button class="btn btn-primary btn-sm" id="igSeal">🔒 Tạo checkpoint</button>
          <button class="btn btn-ghost btn-sm" id="igVerify">🔍 Kiểm chứng toàn chuỗi</button>
        </div>
        <div id="igResult" style="margin-top:10px"></div>
        <div style="margin-top:12px; display:flex; gap:8px; align-items:center; flex-wrap:wrap">
          <input id="igSeq" type="number" min="1" placeholder="Số seq của bản ghi audit" style="padding:8px 10px; border:1px solid var(--line, #ddd); border-radius:8px; width:220px">
          <button class="btn btn-ghost btn-sm" id="igProofBtn">Xem bằng chứng Merkle</button>
        </div>
        <div id="igProofOut" style="margin-top:10px"></div>
      </div></div>
      ${items.length ? `<div class="card" style="overflow-x:auto; margin-top:12px"><table class="tbl">
        <thead><tr><th>Ngày</th><th>Khoảng seq</th><th>Bản ghi</th><th>Merkle root</th><th>Thuật toán</th><th>Khóa</th><th>Niêm phong lúc</th></tr></thead>
        <tbody>${items.map((c) => `<tr><td>${esc(c.day)}</td><td>${c.from_seq}–${c.to_seq}</td><td>${c.leaf_count}</td><td title="${esc(c.merkle_root)}">${short(c.merkle_root)}</td><td>${esc(c.hash_alg)}</td><td>${esc(c.key_id)}</td><td>${fmtTs(c.created_at)}</td></tr>`).join("")}</tbody></table></div>`
      : emptyState("🧾", "Chưa có checkpoint nào", "Bấm \"Tạo checkpoint\" để niêm phong toàn bộ nhật ký hiện có.")}`;
    const result = body.querySelector("#igResult");
    body.querySelector("#igSeal").onclick = async () => {
      try {
        const r = await T("/integrity/checkpoints", { method: "POST" });
        toast(r.created.length ? `Đã tạo ${r.created.length} checkpoint — niêm phong thêm ${r.created.reduce((s, c) => s + c.leaf_count, 0)} bản ghi.` : "Không có bản ghi mới để niêm phong.");
        draw();
      } catch (err) { result.innerHTML = banner(err); }
    };
    body.querySelector("#igVerify").onclick = async () => {
      result.innerHTML = `<div class="sub">Đang tính lại toàn bộ chuỗi băm…</div>`;
      try {
        const v = await T("/integrity/verify");
        if (v.status === "VALID") result.innerHTML = `<div class="card" style="border-left:4px solid #2e7d32"><div class="body"><div class="title">✅ Toàn vẹn</div><div class="sub">${v.sealed_rows} bản ghi đã niêm phong khớp hoàn toàn chuỗi băm và Merkle root của ${v.checkpoints.length} checkpoint. Còn ${v.unsealed_rows} bản ghi mới chưa niêm phong.</div></div></div>`;
        else if (v.status === "INVALID") result.innerHTML = `<div class="card" style="border-left:4px solid #c62828"><div class="body"><div class="title">❌ Phát hiện sai lệch</div><div class="sub">Checkpoint #${v.first_break.checkpoint_id}, khoảng seq ${v.first_break.from_seq}–${v.first_break.to_seq}: ${esc(IG_REASON_VI[v.first_break.reason] || v.first_break.reason)}</div></div></div>`;
        else if (v.status === "UNVERIFIABLE") result.innerHTML = `<div class="card" style="border-left:4px solid #ef6c00"><div class="body"><div class="title">⚠️ Chưa kiểm chứng được</div><div class="sub">Một số checkpoint được niêm phong bằng khóa toàn vẹn khác với khóa hiện tại (xoay vòng khóa) — cần khóa cũ để kiểm chứng lại phần lịch sử đó.</div></div></div>`;
        else result.innerHTML = `<div class="sub">Chưa có checkpoint nào để kiểm chứng.</div>`;
      } catch (err) { result.innerHTML = banner(err); }
    };
    body.querySelector("#igProofBtn").onclick = async () => {
      const out = body.querySelector("#igProofOut");
      const seq = body.querySelector("#igSeq").value;
      if (!seq) { out.innerHTML = `<div class="sub">Nhập số seq trước đã.</div>`; return; }
      try {
        const p = await T(`/integrity/proof/${seq}`);
        out.innerHTML = `<div class="card"><div class="body">
          <div class="title" style="font-size:14.5px">Bằng chứng cho bản ghi seq ${p.seq} ${p.root_matches_checkpoint ? "✅ khớp checkpoint" : "❌ không khớp"}</div>
          <div class="sub" style="word-break:break-all">Event hash: ${esc(p.event_hash)}<br>Chain hash: ${esc(p.chain_hash)}<br>Merkle root: ${esc(p.merkle_root)}</div>
          <div class="sub">Checkpoint #${p.checkpoint.id} · ngày ${esc(p.checkpoint.day)} · seq ${p.checkpoint.from_seq}–${p.checkpoint.to_seq} · ${esc(p.checkpoint.canon_id)} / ${esc(p.checkpoint.hash_alg)} · ${p.proof.length} bước Merkle · Neo chuỗi: chưa kích hoạt</div>
        </div></div>`;
      } catch (err) { out.innerHTML = banner(err); }
    };
  }
  try { await draw(); } catch (err) { body.innerHTML = banner(err); }
}

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
      <div class="list">${users.map((u) => `
        <div class="card"><div class="thumb sky">👤</div><div class="body">
          <div class="title">${esc(u.display_name)} <span class="chip ${u.role === "TENANT_ADMIN" ? "violet" : u.role === "OPERATOR" ? "" : "grey"}">${esc(ROLE_VI[u.role] || u.role)}</span>
          ${u.account_status && u.account_status !== "ACTIVE" ? `<span class="chip amber">${u.account_status === "LOCKED" ? "🔒 Đã khóa" : "⛔ Đã thu hồi"}</span>` : ""}</div>
          <div class="sub">@${esc(u.username)} · tạo ${fmtDate(u.created_at)}${u.linked_actor_code ? ` · 🔗 Chủ thể ${esc(u.linked_actor_code)}` : ""}</div>
          ${(users.find((x) => x.username === store.actor)?.role === "TENANT_ADMIN") ? `<div style="margin-top:8px"><button class="btn btn-ghost btn-sm" data-user-admin="${esc(u.username)}">⚙️ Quản trị tài khoản</button></div>` : ""}
        </div></div>`).join("")}</div>
      <div class="section-head"><h2 style="font-size:15.5px">Nhật ký hệ thống (audit)</h2><span class="hint">${audit.length} mục · chỉ ghi thêm</span></div>
      <div class="list">${audit.slice().reverse().slice(0, 30).map((a) => `
        <div class="card"><div class="thumb">🧾</div><div class="body">
          <div class="title" style="font-size:14.5px">${esc(a.action)} <span class="chip ${a.outcome === "OK" ? "" : "amber"}">${esc(a.outcome)}</span></div>
          <div class="meta"><span>🎯 ${esc(a.target)}</span><span>👤 ${esc(a.actor)}</span><span>🕒 ${fmtTs(a.ts)}</span></div>
        </div></div>`).join("") || emptyState("🧾", "Chưa có nhật ký", "")}</div>`);
  } catch (err) { el.innerHTML = banner(err); }
  el.querySelectorAll("[data-user-admin]").forEach((b) => b.onclick = async () => {
    const u = users.find((x) => x.username === b.dataset.userAdmin);
    if (!u) return;
    const actors = await ensure("actors", "/actors").catch(() => []);
    openSheet(`Quản trị tài khoản @${u.username}`, [
      { k: "display_name", label: "Tên hiển thị", def: u.display_name || "" },
      { k: "account_status", label: "Trạng thái tài khoản", type: "select", def: u.account_status || "ACTIVE", options: [
        { v: "ACTIVE", t: "Hoạt động" }, { v: "LOCKED", t: "Khóa" }, { v: "REVOKED", t: "Thu hồi" }] },
      { k: "linked_actor_code", label: "Chủ thể liên kết", type: "select", def: u.linked_actor_code || "",
        options: [{ v: "", t: "— Không liên kết —" }, ...actors.map(fmtActorOpt)],
        addNew: quickActor,
        refreshOptions: async () => optOf(await ensure("actors", "/actors"), "— Không liên kết —", fmtActorOpt) },
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
      options: [{ v: "", t: "— Không liên kết —" }, ...actors.map(fmtActorOpt)],
      addNew: quickActor,
      refreshOptions: async () => optOf(await ensure("actors", "/actors"), "— Không liên kết —", fmtActorOpt) },
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
