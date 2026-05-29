// 把会话事件流渲染成可读对话。
import { esc, mdLite, compact, money, relTime, absTime, fullNum } from "./util.js";

// 从工具输入里挑一个有代表性的字段做摘要
function toolPreview(input) {
  if (!input || typeof input !== "object") return "";
  for (const k of ["command", "file_path", "path", "pattern", "url", "query", "description", "prompt"]) {
    if (input[k]) return String(input[k]).replace(/\s+/g, " ").slice(0, 90);
  }
  const v = Object.values(input)[0];
  return v ? String(v).replace(/\s+/g, " ").slice(0, 90) : "";
}

function truncNote(ev) {
  return ev.truncated ? `<div class="trunc">⚠ 内容过长已截断（仅展示前 100k 字符）</div>` : "";
}

function renderAssistant(ev) {
  let inner = `<div class="msg-role">🤖 Claude <span class="msg-ts">${ev.model || ""} · ${relTime(ev.ts)}</span></div>`;
  for (const b of ev.blocks) {
    if (b.type === "thinking") {
      inner += `<details class="block thinking"><summary>💭 思考过程</summary>
        <div class="block-body">${esc(b.text)}${truncNote(b)}</div></details>`;
    } else if (b.type === "text") {
      inner += `<div class="bubble">${mdLite(b.text)}${truncNote(b)}</div>`;
    } else if (b.type === "tool_use") {
      const prev = esc(toolPreview(b.input));
      inner += `<details class="block toolcall"><summary>🔧 ${esc(b.name || "tool")}<span style="color:var(--text-faint)">  ${prev}</span></summary>
        <div class="block-body"><pre>${esc(JSON.stringify(b.input, null, 2))}</pre></div></details>`;
    }
  }
  return `<div class="msg assistant">${inner}</div>`;
}

function renderEvent(ev) {
  switch (ev.kind) {
    case "human":
      return `<div class="msg human"><div class="msg-role">👤 用户 <span class="msg-ts">${relTime(ev.ts)}</span></div>
        <div class="bubble">${mdLite(ev.text)}</div></div>`;
    case "assistant":
      return renderAssistant(ev);
    case "tool_result": {
      const cls = ev.is_error ? "toolres err" : "toolres";
      const label = ev.is_error ? "❌ 工具错误" : "✅ 工具结果";
      return `<details class="block ${cls}"><summary>${label}</summary>
        <div class="block-body"><pre>${esc(ev.text)}</pre>${truncNote(ev)}</div></details>`;
    }
    case "system":
      return `<div class="sysmsg">⚙️ <b>${esc(ev.subtype || "system")}</b> · ${esc(ev.text).slice(0, 600)}</div>`;
    case "checkpoint":
      return `<div class="checkpoint">↩ 检查点</div>`;
    default:
      return "";
  }
}

export function renderHeader(m) {
  const title = esc(m.custom_title || m.title || "（无标题会话）");
  const u = m.usage || {};
  const tags = [];
  if (m.model) tags.push(`<span class="tag model">${esc(m.model)}</span>`);
  tags.push(`<span class="tag tok" title="${fullNum(m.total_tokens)} tokens">${compact(m.total_tokens)} tok</span>`);
  tags.push(`<span class="tag" title="估算花费（仅 Anthropic 模型）">${money(m.cost)}</span>`);
  if (m.live) tags.push(`<span class="tag live">● ${m.live.status || "在线"}</span>`);
  if (m.git_branch) tags.push(`<span class="tag">⎇ ${esc(m.git_branch)}</span>`);
  if (m.pinned) tags.push(`<span class="tag" style="color:var(--yellow)">📌 置顶</span>`);
  if (m.archived) tags.push(`<span class="tag">🗄 归档</span>`);

  const usageLine = `输入 ${fullNum(u.input_tokens)} · 输出 ${fullNum(u.output_tokens)} · 缓存读 ${fullNum(u.cache_read_input_tokens)} · 缓存写 ${fullNum(u.cache_creation_input_tokens)}`;

  return `<div class="detail-head">
    <h2>${title}</h2>
    <div class="meta-row">${tags.join("")}
      <span class="msg-ts" title="${absTime(m.last_ts)}">${relTime(m.last_ts)}</span></div>
    <div class="meta-row"><span class="proj-path" style="direction:ltr" title="${esc(m.cwd)}">${esc(m.cwd)}</span></div>
    <div class="meta-row" style="color:var(--text-faint);font-size:11px">${usageLine} · ${m.n_user||0} 轮对话 · ${m.n_tool||0} 次工具调用</div>
    <div class="actions">
      <button class="btn sm" data-act="resume" title="在新终端继续这个会话">▶ 继续会话</button>
      <button class="btn sm" data-act="pin">${m.pinned ? "取消置顶" : "📌 置顶"}</button>
      <button class="btn sm" data-act="archive">${m.archived ? "取消归档" : "🗄 归档"}</button>
      <button class="btn sm" data-act="export">⬇ 导出 Markdown</button>
      <button class="btn sm danger" data-act="delete">🗑 删除</button>
    </div>
  </div>`;
}

export function renderDetail(detail) {
  const events = detail.events || [];
  const body = events.length
    ? events.map(renderEvent).join("")
    : `<div class="empty">这个会话没有可显示的内容（可能是空会话）。</div>`;
  return renderHeader(detail.meta) + `<div class="conv">${body}</div>`;
}
