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
  let res;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 20000);
  try {
    res = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined, signal: ctrl.signal });
  } catch {
    throw new ApiError("NETWORK", "Không kết nối được tới máy chủ (quá thời gian chờ). Kiểm tra mạng và thử lại.");
  } finally {
    clearTimeout(timer);
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail || {};
    throw new ApiError(typeof d === "string" ? "" : d.code, typeof d === "string" ? d : d.message, res.status);
  }
  return data;
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
function openSheet(title, fields, onSubmit) {
  $("#sheetTitle").textContent = title;
  const form = $("#sheetForm");
  form.innerHTML = fields.map((f) => {
    const req = f.required ? ' <span class="req">*</span>' : "";
    let control;
    if (f.type === "select") {
      control = `<select name="${f.k}">${(f.options || []).map((o) =>
        `<option value="${esc(o.v)}" ${String(o.v) === String(f.def ?? "") ? "selected" : ""}>${esc(o.t)}</option>`).join("")}</select>`;
    } else if (f.type === "textarea") {
      control = `<textarea name="${f.k}" placeholder="${esc(f.placeholder || "")}">${esc(f.def ?? "")}</textarea>`;
    } else {
      control = `<input name="${f.k}" type="${f.type || "text"}" ${f.step ? `step="${f.step}"` : ""}
        value="${esc(f.def ?? "")}" placeholder="${esc(f.placeholder || "")}" ${f.required ? "required" : ""}
        ${f.type === "text" ? 'autocapitalize="off"' : ""}>`;
    }
    return `<div class="field"><label>${esc(f.label)}${req}</label>${control}</div>`;
  }).join("") + `<div class="form-actions">
      <button type="button" class="btn btn-ghost" id="sheetCancel">Hủy</button>
      <button type="submit" class="btn btn-primary">Lưu lại</button></div>`;
  sheetSubmit = { fields, onSubmit };
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
}
$("#sheetClose").addEventListener("click", closeSheet);
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
    payload[f.k] = f.type === "number" ? Number(v) : v;
  }
  const btn = e.target.querySelector('[type="submit"]');
  btn.disabled = true; btn.textContent = "Đang lưu…";
  try {
    await sheetSubmit.onSubmit(payload);
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
  }).join("") + `<button type="button" data-nav="settings" class="${state.view === "settings" || state.view === "tenants" ? "active" : ""}">
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
  const map = { ACTIVE: "", ALIVE: "", RUNNING: "sky", IN_STOCK: "", DRAFT: "grey", ENDED: "violet", SUSPENDED: "red" };
  return `<span class="chip ${map[status] ?? "grey"}">${esc(status || "—")}</span>`;
}
async function ensure(kind, path) {
  if (!state.cache[kind]) state.cache[kind] = (await T(path)).items;
  return state.cache[kind];
}
function invalidate(...kinds) { kinds.forEach((k) => delete state.cache[k]); }

/* ---------------- dashboard ---------------- */
VIEWS.dashboard = async () => {
  const el = $("#view");
  el.innerHTML = skeleton(4);
  try {
    const health = await api("/health");
    state.health = health;
    const [zones, plants, plans, lots] = await Promise.all([
      ensure("zones", "/zones"), ensure("plants", "/mother-plants"),
      ensure("plans", "/crop-plans"), ensure("lots", "/lots"),
    ]);
    let audit = [];
    try { audit = (await T("/audit")).items.slice(-5).reverse(); } catch { /* read-only tolerance */ }
    el.innerHTML = `
      <section class="hero">
        <h1>Xin chào, ${esc(store.actor || "bạn")} 👋</h1>
        <p>Đơn vị <b>${esc(store.tenant)}</b> — tổng quan sản xuất hôm nay.</p>
        <div class="hero-meta">
          <span class="pill">🌐 Môi trường: ${esc(health.env)}</span>
          <span class="pill">🗄️ Lưu trữ: ${esc(health.storage)}</span>
          <span class="pill">⚙️ Phiên bản: ${esc(health.version)}</span>
        </div>
      </section>
      <div class="grid stats">
        <button class="stat-card" data-go="zones"><span class="ic">🗺️</span><b>${zones.length}</b><span>Vùng nguyên liệu</span></button>
        <button class="stat-card" data-go="plants"><span class="ic">🌳</span><b>${plants.length}</b><span>Cây đầu dòng</span></button>
        <button class="stat-card" data-go="plans"><span class="ic">📅</span><b>${plans.length}</b><span>Kế hoạch mùa vụ</span></button>
        <button class="stat-card" data-go="lots"><span class="ic">📦</span><b>${lots.length}</b><span>Lô thu hoạch</span></button>
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
  } catch (err) {
    el.innerHTML = banner(err) + emptyState("🔌", "Chưa kết nối được dữ liệu",
      "Kiểm tra mã tenant và người dùng trong mục Cài đặt, hoặc nhờ quản trị platform kiểm tra trạng thái tenant.");
  }
};

/* ---------------- zones ---------------- */
VIEWS.zones = async () => {
  const el = $("#view");
  el.innerHTML = `<div class="section-head"><h2>🗺️ Vùng nguyên liệu</h2>
    <button class="btn btn-ghost btn-sm" id="reload">↻ Làm mới</button></div>` + skeleton(3);
  $("#reload").onclick = () => { invalidate("zones"); navigate("zones", true); };
  try {
    const items = await ensure("zones", "/zones");
    el.querySelectorAll(".skel").forEach((s) => s.remove());
    el.insertAdjacentHTML("beforeend", items.length ? `<div class="list">${items.map((z) => `
      <div class="card"><div class="thumb">🗺️</div><div class="body">
        <div class="title">${esc(z.name || z.code)} ${chipFor(z.status)}</div>
        <div class="sub">Mã vùng: <b>${esc(z.code)}</b>${z.crop_group ? ` · Nhóm cây: ${esc(z.crop_group)}` : ""}</div>
        <div class="meta">
          ${z.area_ha != null ? `<span>📐 ${fmtNum(z.area_ha)} ha</span>` : ""}
          ${z.season ? `<span>🗓️ ${esc(z.season)}</span>` : ""}
          ${z.water_source ? `<span>💧 ${esc(z.water_source)}</span>` : ""}
          ${z.address ? `<span>📍 ${esc(z.address)}</span>` : ""}
        </div></div></div>`).join("")}</div>`
      : emptyState("🗺️", "Chưa có vùng nào", "Bấm nút + để tạo vùng nguyên liệu đầu tiên."));
  } catch (err) { el.innerHTML = banner(err); }
  fab("Tạo vùng", async () => openSheet("Tạo vùng nguyên liệu", [
    { k: "code", label: "Mã vùng", required: true, placeholder: "vd: Z-01" },
    { k: "name", label: "Tên vùng", required: true, placeholder: "vd: Khu A – Đà Lạt" },
    { k: "area_ha", label: "Diện tích (ha)", type: "number", step: "0.01", placeholder: "vd: 10.5" },
    { k: "crop_group", label: "Nhóm cây", placeholder: "vd: Rau củ, Sầu riêng…" },
    { k: "season", label: "Mùa vụ", placeholder: "vd: Đông Xuân 2026" },
    { k: "water_source", label: "Nguồn nước", placeholder: "vd: Suối, Giếng khoan…" },
    { k: "address", label: "Địa chỉ", placeholder: "Thôn/xã/huyện" },
    { k: "managing_entity", label: "Chủ thể quản lý", placeholder: "Đội/nhóm phụ trách" },
  ], async (p) => { await T("/zones", { method: "POST", body: p }); invalidate("zones"); }));
};

/* ---------------- mother plants ---------------- */
VIEWS.plants = async () => {
  const el = $("#view");
  el.innerHTML = `<div class="section-head"><h2>🌳 Cây đầu dòng</h2>
    <button class="btn btn-ghost btn-sm" id="reload">↻ Làm mới</button></div>` + skeleton(3);
  $("#reload").onclick = () => { invalidate("plants"); navigate("plants", true); };
  try {
    const items = await ensure("plants", "/mother-plants");
    el.querySelectorAll(".skel").forEach((s) => s.remove());
    el.insertAdjacentHTML("beforeend", items.length ? `<div class="list">${items.map((p) => `
      <div class="card"><div class="thumb">🌳</div><div class="body">
        <div class="title">${esc(p.species || p.code)} ${chipFor(p.status)}</div>
        <div class="sub">Mã cây: <b>${esc(p.code)}</b>${p.variety ? ` · Giống: ${esc(p.variety)}` : ""}</div>
        <div class="meta">
          ${p.zone_code ? `<span>🗺️ Vùng ${esc(p.zone_code)}</span>` : ""}
          ${p.planting_year ? `<span>🌱 Trồng năm ${esc(p.planting_year)}</span>` : ""}
          ${p.valid_to ? `<span>📜 Công nhận đến ${fmtDate(p.valid_to)}</span>` : ""}
          ${p.owner_manager ? `<span>👤 ${esc(p.owner_manager)}</span>` : ""}
        </div></div></div>`).join("")}</div>`
      : emptyState("🌳", "Chưa có cây đầu dòng nào", "Bấm nút + để cấp mã cho cây/cụm cây đầu dòng."));
  } catch (err) { el.innerHTML = banner(err); }
  fab("Thêm cây đầu dòng", async () => {
    const zones = await ensure("zones", "/zones").catch(() => []);
    openSheet("Thêm cây đầu dòng", [
      { k: "code", label: "Mã cây (dùng cho QR)", required: true, placeholder: "vd: MPL-001" },
      { k: "species", label: "Loài cây", required: true, placeholder: "vd: Sầu riêng" },
      { k: "variety", label: "Giống", placeholder: "vd: Ri6, Monthong…" },
      { k: "scientific_name", label: "Tên khoa học", placeholder: "vd: Durio zibethinus" },
      { k: "zone_code", label: "Thuộc vùng", type: "select",
        options: [{ v: "", t: "— Không gắn vùng —" }, ...zones.map((z) => ({ v: z.code, t: `${z.code} · ${z.name || ""}` }))] },
      { k: "planting_year", label: "Năm trồng", type: "number", placeholder: "vd: 2019" },
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
    <button class="btn btn-ghost btn-sm" id="reload">↻ Làm mới</button></div>` + skeleton(4);
  $("#reload").onclick = () => { invalidate("plans", "events"); navigate("plans", true); };
  try {
    const [plans, events] = await Promise.all([
      ensure("plans", "/crop-plans"), ensure("events", "/field-events"),
    ]);
    el.querySelectorAll(".skel").forEach((s) => s.remove());
    el.insertAdjacentHTML("beforeend", `
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
        return `<div class="card"><div class="thumb sky">${t ? t.t.split(" ")[0] : "📌"}</div><div class="body">
          <div class="title">${esc(t ? t.t : e.event_type || "Sự kiện")}</div>
          <div class="sub">${esc(e.notes || "")}</div>
          <div class="meta">
            ${e.plan_code ? `<span>📅 ${esc(e.plan_code)}</span>` : ""}
            ${e.zone_code ? `<span>🗺️ ${esc(e.zone_code)}</span>` : ""}
            <span>🕒 ${fmtTs(e.occurred_at || e.created_at)}</span>
            ${e.actor ? `<span>👤 ${esc(e.actor)}</span>` : ""}
          </div></div></div>`; }).join("")}</div>`
      : emptyState("📝", "Chưa có nhật ký nào", "Ghi lại tưới, bón, kiểm tra… để truy vết về sau.")}`);
    $("#addEvent").onclick = async () => {
      const zones = await ensure("zones", "/zones").catch(() => []);
      openSheet("Ghi nhật ký đồng ruộng", [
        { k: "event_type", label: "Loại sự kiện", type: "select", required: true, options: EVENT_TYPES },
        { k: "plan_code", label: "Kế hoạch mùa vụ", type: "select",
          options: [{ v: "", t: "— Không gắn kế hoạch —" }, ...plans.map((p) => ({ v: p.code, t: `${p.code} · ${p.name || p.crop_name || ""}` }))] },
        { k: "zone_code", label: "Vùng", type: "select",
          options: [{ v: "", t: "— Không gắn vùng —" }, ...zones.map((z) => ({ v: z.code, t: `${z.code} · ${z.name || ""}` }))] },
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
    const [zones, plants] = await Promise.all([
      ensure("zones", "/zones").catch(() => []), ensure("plants", "/mother-plants").catch(() => []),
    ]);
    openSheet("Tạo kế hoạch mùa vụ", [
      { k: "code", label: "Mã kế hoạch", required: true, placeholder: "vd: PLAN-2026" },
      { k: "name", label: "Tên kế hoạch", placeholder: "vd: Vụ rau Đông Xuân" },
      { k: "crop_name", label: "Cây trồng", placeholder: "vd: Xà lách, Cà chua…" },
      { k: "zone_code", label: "Vùng canh tác", type: "select",
        options: [{ v: "", t: "— Chọn vùng —" }, ...zones.map((z) => ({ v: z.code, t: `${z.code} · ${z.name || ""}` }))] },
      { k: "plant_code", label: "Cây đầu dòng liên quan", type: "select",
        options: [{ v: "", t: "— Không gắn cây —" }, ...plants.map((p) => ({ v: p.code, t: `${p.code} · ${p.species || ""}` }))] },
      { k: "start_date", label: "Ngày bắt đầu", type: "date" },
      { k: "end_date", label: "Ngày kết thúc dự kiến", type: "date" },
      { k: "target_yield_kg", label: "Mục tiêu sản lượng (kg)", type: "number", step: "0.1" },
      { k: "status", label: "Trạng thái", type: "select", options: [
        { v: "DRAFT", t: "Dự thảo" }, { v: "RUNNING", t: "Đang chạy" }, { v: "ENDED", t: "Đã kết thúc" }] },
    ], async (p) => { await T("/crop-plans", { method: "POST", body: p }); invalidate("plans"); });
  });
};

/* ---------------- lots ---------------- */
VIEWS.lots = async () => {
  const el = $("#view");
  el.innerHTML = `<div class="section-head"><h2>📦 Lô thu hoạch</h2>
    <button class="btn btn-ghost btn-sm" id="reload">↻ Làm mới</button></div>` + skeleton(3);
  $("#reload").onclick = () => { invalidate("lots"); navigate("lots", true); };
  try {
    const items = await ensure("lots", "/lots");
    el.querySelectorAll(".skel").forEach((s) => s.remove());
    el.insertAdjacentHTML("beforeend", items.length ? `<div class="list">${items.map((l) => `
      <div class="card"><div class="thumb amber">📦</div><div class="body">
        <div class="title">${esc(l.code)} ${chipFor(l.status)} ${l.quality_grade ? `<span class="chip amber">Loại ${esc(l.quality_grade)}</span>` : ""}</div>
        <div class="sub">${l.quantity != null ? `<b>${fmtNum(l.quantity)} ${esc(l.unit || "kg")}</b>` : ""}${l.harvest_date ? ` · Thu hoạch ${fmtDate(l.harvest_date)}` : ""}</div>
        <div class="meta">
          ${l.zone_code ? `<span>🗺️ ${esc(l.zone_code)}</span>` : ""}
          ${l.plan_code ? `<span>📅 ${esc(l.plan_code)}</span>` : ""}
          ${l.harvested_by ? `<span>👤 ${esc(l.harvested_by)}</span>` : ""}
          ${l.expiry_date ? `<span>⏳ HSD ${fmtDate(l.expiry_date)}</span>` : ""}
        </div></div></div>`).join("")}</div>`
      : emptyState("📦", "Chưa có lô thu hoạch nào", "Bấm nút + để tạo lô từ vùng/kế hoạch đã thu hoạch."));
  } catch (err) { el.innerHTML = banner(err); }
  fab("Tạo lô thu hoạch", async () => {
    const [zones, plans] = await Promise.all([
      ensure("zones", "/zones").catch(() => []), ensure("plans", "/crop-plans").catch(() => []),
    ]);
    openSheet("Tạo lô thu hoạch", [
      { k: "code", label: "Mã lô", required: true, placeholder: "vd: LOT-001" },
      { k: "zone_code", label: "Vùng thu hoạch", type: "select",
        options: [{ v: "", t: "— Chọn vùng —" }, ...zones.map((z) => ({ v: z.code, t: `${z.code} · ${z.name || ""}` }))] },
      { k: "plan_code", label: "Kế hoạch mùa vụ", type: "select",
        options: [{ v: "", t: "— Không gắn kế hoạch —" }, ...plans.map((p) => ({ v: p.code, t: `${p.code} · ${p.name || p.crop_name || ""}` }))] },
      { k: "harvest_date", label: "Ngày thu hoạch", type: "date" },
      { k: "quantity", label: "Sản lượng", type: "number", step: "0.01" },
      { k: "unit", label: "Đơn vị", type: "select", options: [
        { v: "kg", t: "kg" }, { v: "tấn", t: "tấn" }, { v: "thùng", t: "thùng" }, { v: "bao", t: "bao" }] },
      { k: "quality_grade", label: "Phân loại chất lượng", placeholder: "vd: A, B, VIP…" },
      { k: "harvested_by", label: "Người thu hoạch" },
      { k: "expiry_date", label: "Hạn dùng", type: "date" },
    ], async (p) => { await T("/lots", { method: "POST", body: p }); invalidate("lots"); });
  });
};

/* ---------------- users & audit ---------------- */
const ROLE_VI = { TENANT_ADMIN: "Quản trị tenant", OPERATOR: "Vận hành", VIEWER: "Chỉ xem" };
VIEWS.users = async () => {
  const el = $("#view");
  el.innerHTML = `<div class="section-head"><h2>👥 Người dùng & nhật ký</h2>
    <button class="btn btn-ghost btn-sm" id="reload">↻ Làm mới</button></div>` + skeleton(4);
  $("#reload").onclick = () => navigate("users", true);
  try {
    const [users, audit] = await Promise.all([T("/users"), T("/audit")]);
    el.querySelectorAll(".skel").forEach((s) => s.remove());
    el.insertAdjacentHTML("beforeend", `
      <div class="section-head"><h2 style="font-size:15.5px">Người dùng trong tenant</h2></div>
      <div class="list">${users.items.map((u) => `
        <div class="card"><div class="thumb sky">👤</div><div class="body">
          <div class="title">${esc(u.display_name)} <span class="chip ${u.role === "TENANT_ADMIN" ? "violet" : u.role === "OPERATOR" ? "" : "grey"}">${esc(ROLE_VI[u.role] || u.role)}</span></div>
          <div class="sub">@${esc(u.username)} · tạo ${fmtDate(u.created_at)}</div>
        </div></div>`).join("")}</div>
      <div class="section-head"><h2 style="font-size:15.5px">Nhật ký hệ thống (audit)</h2><span class="hint">${audit.items.length} mục · chỉ ghi thêm</span></div>
      <div class="list">${audit.items.slice().reverse().slice(0, 30).map((a) => `
        <div class="card"><div class="thumb">🧾</div><div class="body">
          <div class="title" style="font-size:14.5px">${esc(a.action)} <span class="chip ${a.outcome === "OK" ? "" : "amber"}">${esc(a.outcome)}</span></div>
          <div class="meta"><span>🎯 ${esc(a.target)}</span><span>👤 ${esc(a.actor)}</span><span>🕒 ${fmtTs(a.ts)}</span></div>
        </div></div>`).join("") || emptyState("🧾", "Chưa có nhật ký", "")}</div>`);
  } catch (err) { el.innerHTML = banner(err); }
  fab("Thêm người dùng", () => openSheet("Thêm người dùng", [
    { k: "username", label: "Tên đăng nhập", required: true, placeholder: "vd: van.an" },
    { k: "display_name", label: "Tên hiển thị", required: true, placeholder: "vd: Văn An" },
    { k: "role", label: "Vai trò", type: "select", options: [
      { v: "VIEWER", t: "Chỉ xem" }, { v: "OPERATOR", t: "Vận hành (ghi dữ liệu)" }, { v: "TENANT_ADMIN", t: "Quản trị tenant" }] },
  ], async (p) => { await T("/users", { method: "POST", body: p }); }));
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
  $("#disconnect").onclick = () => { store.clear(); location.reload(); };
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
  try { state.health = await api("/health"); $("#envLabel").textContent = state.health.env; } catch { /* offline tolerance */ }
  navigate(store.tenant ? "dashboard" : "settings", true);
}
if (store.tenant) { $("#setup").hidden = true; boot(); }
else { $("#setup").hidden = false; paintNav(); }
