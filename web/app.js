// 主控制器：状态、渲染、事件绑定。
import { api } from "./api.js";
import { esc, compact, money, relTime, fullNum, highlight, toast } from "./util.js";
import { renderDetail } from "./viewer.js";

const $ = (id) => document.getElementById(id);
const state = {
  projects: [], pid: null, sessions: [], sid: null,
  detail: null, showArchived: false,
};

// ── 渲染：项目列表 ────────────────────────────────────────────────
function renderProjects() {
  const list = state.projects.filter(p => state.showArchived || !p.archived);
  $("proj-count").textContent = `(${list.length})`;
  $("project-list").innerHTML = list.map(p => `
    <div class="proj ${p.id === state.pid ? "active" : ""}" data-pid="${esc(p.id)}">
      <div class="proj-label">
        ${p.n_live ? '<span class="dot-live"></span>' : ""}
        ${p.pinned ? '<span class="pin">📌</span>' : ""}
        ${esc(p.label)}
      </div>
      <div class="proj-path" title="${esc(p.path)}">${esc(p.path)}</div>
      <div class="proj-meta">
        <span>${p.n_sessions} 会话</span>
        <span>${compact(p.total_tokens)} tok</span>
        <span>${money(p.cost)}</span>
        <span>${relTime(p.last_activity)}</span>
      </div>
    </div>`).join("") || '<div class="empty">还没有任何项目</div>';
}

// ── 渲染：会话列表 ────────────────────────────────────────────────
function renderSessions() {
  const proj = state.projects.find(p => p.id === state.pid);
  $("sessions-title").textContent = proj ? proj.label : "会话";
  const list = state.sessions.filter(s => state.showArchived || !s.archived);
  $("sess-count").textContent = `(${list.length})`;
  $("session-list").innerHTML = list.map(s => {
    const title = s.custom_title || s.title || "（空会话）";
    return `
    <div class="sess ${s.id === state.sid ? "active" : ""} ${s.archived ? "archived" : ""}" data-sid="${esc(s.id)}">
      <div class="sess-title">${s.pinned ? "📌 " : ""}${esc(title)}</div>
      <div class="sess-meta">
        ${s.model ? `<span class="tag model">${esc(s.model)}</span>` : ""}
        <span class="tag tok">${compact(s.total_tokens)}</span>
        ${s.live ? `<span class="tag live">● ${esc(s.live.status || "在线")}</span>` : ""}
        <span>${relTime(s.mtime)}</span>
        <span>💬${s.n_user}/${s.n_assistant}</span>
      </div>
      <div class="sess-actions">
        <button class="btn sm" data-sact="resume" title="继续会话">▶</button>
        <button class="btn sm" data-sact="pin" title="置顶">${s.pinned ? "★" : "📌"}</button>
        <button class="btn sm" data-sact="export" title="导出">⬇</button>
        <button class="btn sm danger" data-sact="delete" title="删除">🗑</button>
      </div>
    </div>`;
  }).join("") || '<div class="empty">该项目下没有会话</div>';
}

// ── 数据加载 ──────────────────────────────────────────────────────
async function loadProjects() {
  try { state.projects = await api.projects(); renderProjects(); }
  catch (e) { toast("加载项目失败：" + e.message, true); }
}
async function selectProject(pid) {
  state.pid = pid; renderProjects();
  $("session-list").innerHTML = '<div class="empty">加载中…</div>';
  try { state.sessions = await api.sessions(pid); renderSessions(); }
  catch (e) { toast("加载会话失败：" + e.message, true); }
}
async function selectSession(sid) {
  state.sid = sid; renderSessions();
  $("detail").innerHTML = '<div class="empty big">加载中…</div>';
  try {
    state.detail = await api.detail(state.pid, sid);
    $("detail").innerHTML = renderDetail(state.detail);
  } catch (e) { toast("加载详情失败：" + e.message, true); }
}

// ── 操作（置顶/归档/继续/导出/删除）───────────────────────────────
async function doResume(pid, sid) {
  try { const r = await api.resume(pid, sid);
    toast(r.ok ? `已在新终端继续：${r.command}` : "继续失败：" + (r.error || ""), !r.ok);
  } catch (e) { toast("继续失败：" + e.message, true); }
}
async function doExport(pid, sid) {
  try {
    const { markdown, filename } = await api.export(pid, sid);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([markdown], { type: "text/markdown" }));
    a.download = filename; a.click(); URL.revokeObjectURL(a.href);
    toast("已导出 " + filename);
  } catch (e) { toast("导出失败：" + e.message, true); }
}
async function doToggle(pid, sid, field) {
  const s = state.sessions.find(x => x.id === sid) || (state.detail && state.detail.meta);
  const cur = s ? s[field] : false;
  try {
    await api.setSessionMeta(pid, sid, { [field]: !cur });
    state.sessions = await api.sessions(pid); renderSessions();
    if (state.sid === sid) { state.detail = await api.detail(pid, sid); $("detail").innerHTML = renderDetail(state.detail); }
    toast(field === "pinned" ? (!cur ? "已置顶" : "已取消置顶") : (!cur ? "已归档" : "已取消归档"));
  } catch (e) { toast("操作失败：" + e.message, true); }
}
async function doDelete(pid, sid) {
  if (!confirm("删除该会话？\n（软删除：文件会移到 data/trash，可手动恢复）")) return;
  try {
    await api.del(pid, sid);
    if (state.sid === sid) { state.sid = null; state.detail = null; $("detail").innerHTML = '<div class="empty big">选择一个会话查看完整对话</div>'; }
    state.sessions = await api.sessions(pid); renderSessions();
    await loadProjects();
    toast("已删除（移至回收站）");
  } catch (e) { toast("删除失败：" + e.message, true); }
}

// ── 看板 / 设置 弹层 ──────────────────────────────────────────────
function openModal(title, html) {
  $("modal-title").textContent = title; $("modal-body").innerHTML = html;
  $("overlay").classList.remove("hidden");
}
function bars(rows, nameKey, valKey, fmt) {
  const max = Math.max(1, ...rows.map(r => r[valKey]));
  return rows.map(r => `
    <div class="bar-row"><span class="name" title="${esc(r[nameKey])}">${esc(r[nameKey])}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${(r[valKey] / max * 100).toFixed(1)}%"></div></div>
      <span class="val">${fmt(r[valKey])}</span></div>`).join("");
}
async function openDashboard() {
  openModal("📊 用量看板", '<div class="empty">统计中…</div>');
  try {
    const s = await api.stats();
    const cards = [
      ["项目", s.n_projects], ["会话", s.n_sessions],
      ["总 Token", compact(s.total_tokens)], ["估算花费", money(s.total_cost)],
      ["用户消息", fullNum(s.n_user)], ["助手消息", fullNum(s.n_assistant)],
    ].map(([l, n]) => `<div class="stat-card"><div class="n">${n}</div><div class="l">${l}</div></div>`).join("");
    const u = s.totals;
    const tokenBreak = bars([
      { k: "缓存读取", v: u.cache_read_input_tokens }, { k: "输入", v: u.input_tokens },
      { k: "输出", v: u.output_tokens }, { k: "缓存写入", v: u.cache_creation_input_tokens },
    ], "k", "v", compact);
    openModal("📊 用量看板", `
      <div class="stat-grid">${cards}</div>
      <div class="section-title">Token 构成</div>${tokenBreak}
      <div class="section-title">按模型</div>${bars(s.by_model, "model", "tokens", compact)}
      <div class="section-title">按项目</div>${bars(s.by_project, "label", "tokens", compact)}
      <div class="section-title">按天活跃（Token）</div>${bars(s.by_day, "date", "tokens", compact)}
      <p style="color:var(--text-faint);font-size:11px;margin-top:16px">花费为粗略估算，仅对可识别的 Anthropic 模型（opus/sonnet/haiku）计算；第三方供应商按未知处理。</p>`);
  } catch (e) { openModal("📊 用量看板", `<div class="empty">统计失败：${esc(e.message)}</div>`); }
}
async function openSettings() {
  openModal("⚙ Claude 配置", '<div class="empty">读取中…</div>');
  try {
    const s = await api.settings();
    openModal("⚙ Claude 配置 (settings.json)",
      `<pre class="settings-pre">${esc(JSON.stringify(s, null, 2))}</pre>`);
  } catch (e) { openModal("⚙ 配置", `<div class="empty">读取失败：${esc(e.message)}</div>`); }
}

// ── 搜索 ──────────────────────────────────────────────────────────
let searchTimer;
function findPidByPath(path) {
  const p = state.projects.find(x => x.path === path);
  return p ? p.id : null;
}
async function runSearch(q) {
  const box = $("search-results");
  if (!q.trim()) { box.classList.add("hidden"); return; }
  try {
    const r = await api.search(q);
    let html = "";
    if (r.sessions.length) {
      html += '<div class="sr-group">会话</div>';
      html += r.sessions.map(s => `
        <div class="sr-item" data-pid="${esc(s.pid)}" data-sid="${esc(s.id)}">
          <div class="t">${highlight(s.title || "（空会话）", q)}</div>
          <div class="s">${esc(s.hit_in)} · ${highlight(s.snippet, q)}</div></div>`).join("");
    }
    if (r.prompts.length) {
      html += '<div class="sr-group">历史输入</div>';
      html += r.prompts.slice(0, 20).map(p => `
        <div class="sr-item" data-path="${esc(p.project)}" data-sid="${esc(p.sessionId)}">
          <div class="t">${highlight(p.display, q)}</div>
          <div class="s">${esc(p.project)} · ${relTime(p.ts)}</div></div>`).join("");
    }
    box.innerHTML = html || '<div class="empty">无匹配结果</div>';
    box.classList.remove("hidden");
  } catch (e) { toast("搜索失败：" + e.message, true); }
}
async function gotoSession(pid, sid) {
  $("search-results").classList.add("hidden"); $("search").value = "";
  if (pid !== state.pid) await selectProject(pid);
  await selectSession(sid);
}

// ── 事件绑定 ──────────────────────────────────────────────────────
function bind() {
  $("project-list").addEventListener("click", e => {
    const el = e.target.closest("[data-pid]"); if (el) selectProject(el.dataset.pid);
  });
  $("session-list").addEventListener("click", e => {
    const act = e.target.closest("[data-sact]");
    const row = e.target.closest("[data-sid]"); if (!row) return;
    const sid = row.dataset.sid, pid = state.pid;
    if (act) {
      e.stopPropagation();
      ({ resume: doResume, export: doExport, delete: doDelete,
         pin: (p, s) => doToggle(p, s, "pinned") }[act.dataset.sact])(pid, sid);
    } else selectSession(sid);
  });
  $("detail").addEventListener("click", e => {
    const b = e.target.closest("[data-act]"); if (!b) return;
    const pid = state.pid, sid = state.sid;
    ({ resume: doResume, export: doExport, delete: doDelete,
       pin: (p, s) => doToggle(p, s, "pinned"),
       archive: (p, s) => doToggle(p, s, "archived") }[b.dataset.act])(pid, sid);
  });
  $("search").addEventListener("input", e => {
    clearTimeout(searchTimer); searchTimer = setTimeout(() => runSearch(e.target.value), 220);
  });
  $("search-results").addEventListener("click", e => {
    const it = e.target.closest(".sr-item"); if (!it) return;
    const pid = it.dataset.pid || findPidByPath(it.dataset.path);
    if (pid) gotoSession(pid, it.dataset.sid);
    else toast("找不到对应项目（可能已归档/移动）", true);
  });
  document.addEventListener("click", e => {
    if (!e.target.closest(".search-wrap")) $("search-results").classList.add("hidden");
  });
  $("show-archived").addEventListener("change", e => {
    state.showArchived = e.target.checked; renderProjects(); renderSessions();
  });
  $("btn-dashboard").addEventListener("click", openDashboard);
  $("btn-settings").addEventListener("click", openSettings);
  $("btn-refresh").addEventListener("click", async () => {
    await loadProjects();
    if (state.pid) { state.sessions = await api.sessions(state.pid); renderSessions(); }
    toast("已刷新");
  });
  $("modal-close").addEventListener("click", () => $("overlay").classList.add("hidden"));
  $("overlay").addEventListener("click", e => { if (e.target.id === "overlay") $("overlay").classList.add("hidden"); });
  document.addEventListener("keydown", e => {
    if ((e.ctrlKey || e.metaKey) && e.key === "k") { e.preventDefault(); $("search").focus(); }
    if (e.key === "Escape") { $("overlay").classList.add("hidden"); $("search-results").classList.add("hidden"); }
  });
}

// ── 启动 ──────────────────────────────────────────────────────────
(async function init() {
  bind();
  await loadProjects();
  if (state.projects.length) selectProject(state.projects[0].id);
})();
