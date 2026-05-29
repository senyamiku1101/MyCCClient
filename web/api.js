// 后端 API 封装。

async function j(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return r.json();
}

export const api = {
  projects: () => j("/api/projects"),
  sessions: (pid) => j(`/api/projects/${encodeURIComponent(pid)}/sessions`),
  detail: (pid, sid) => j(`/api/projects/${encodeURIComponent(pid)}/sessions/${encodeURIComponent(sid)}`),
  search: (q) => j(`/api/search?q=${encodeURIComponent(q)}`),
  stats: () => j("/api/stats"),
  live: () => j("/api/live"),
  settings: () => j("/api/settings"),
  export: (pid, sid) => j(`/api/projects/${encodeURIComponent(pid)}/sessions/${encodeURIComponent(sid)}/export`),
  resume: (pid, sid) => j(`/api/projects/${encodeURIComponent(pid)}/sessions/${encodeURIComponent(sid)}/resume`, { method: "POST" }),
  setSessionMeta: (pid, sid, patch) => j(`/api/projects/${encodeURIComponent(pid)}/sessions/${encodeURIComponent(sid)}/meta`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) }),
  setProjectMeta: (pid, patch) => j(`/api/projects/${encodeURIComponent(pid)}/meta`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) }),
  del: (pid, sid) => j(`/api/projects/${encodeURIComponent(pid)}/sessions/${encodeURIComponent(sid)}`, { method: "DELETE" }),
};
