"""扫描 ~/.claude：项目、会话、实时进程、history、全局搜索。"""
from __future__ import annotations

import json
from pathlib import Path

from . import meta as sidecar
from .config import history_file, projects_dir, sessions_dir
from .parser import clean_title, read_lines, session_meta, text_from_content
from .paths import decode_project_name, short_label


# ── 项目目录定位与校验 ────────────────────────────────────────────────
def safe_project_dir(pid: str) -> Path | None:
    """把前端传来的 pid 安全地映射回 projects 下的目录，防目录穿越。"""
    if not pid or "/" in pid or "\\" in pid or pid in (".", ".."):
        return None
    d = projects_dir() / pid
    try:
        if d.is_dir() and d.parent == projects_dir():
            return d
    except OSError:
        return None
    return None


def session_path(pid: str, sid: str) -> Path | None:
    d = safe_project_dir(pid)
    if not d:
        return None
    if not sid or any(c in sid for c in "/\\") or sid in (".", ".."):
        return None
    p = d / f"{sid}.jsonl"
    return p if p.exists() else None


def iter_all_sessions():
    """yield (pid, path) 覆盖所有项目的所有会话文件。"""
    pd = projects_dir()
    if not pd.is_dir():
        return
    for d in pd.iterdir():
        if not d.is_dir():
            continue
        for f in d.glob("*.jsonl"):
            yield d.name, f


# ── 实时会话（正在运行的进程）─────────────────────────────────────────
def live_map() -> dict:
    """{sessionId: {status, cwd, pid, updatedAt, ...}}。"""
    out = {}
    sd = sessions_dir()
    if not sd.is_dir():
        return out
    for f in sd.glob("*.json"):
        try:
            obj = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        sid = obj.get("sessionId")
        if sid:
            out[sid] = obj
    return out


# ── 项目列表 ──────────────────────────────────────────────────────────
def _project_real_path(d: Path, metas: list[dict]) -> str:
    for m in metas:
        if m.get("cwd"):
            return m["cwd"]
    return decode_project_name(d.name)


def list_projects() -> list[dict]:
    pd = projects_dir()
    out = []
    if not pd.is_dir():
        return out
    live = live_map()
    for d in sorted(pd.iterdir()):
        if not d.is_dir():
            continue
        files = list(d.glob("*.jsonl"))
        if not files:
            continue
        metas = [session_meta(f) for f in files]
        path = _project_real_path(d, metas)
        last_activity = max((m.get("mtime", 0) for m in metas), default=0)
        total_tokens = sum(m.get("total_tokens", 0) for m in metas)
        costs = [m.get("cost") for m in metas if m.get("cost") is not None]
        n_live = sum(1 for m in metas if m["id"] in live)
        pm = sidecar.get_project(d.name)
        out.append({
            "id": d.name,
            "path": path,
            "label": short_label(path),
            "n_sessions": len(files),
            "n_live": n_live,
            "last_activity": last_activity,
            "total_tokens": total_tokens,
            "cost": round(sum(costs), 4) if costs else None,
            "pinned": bool(pm.get("pinned")),
            "archived": bool(pm.get("archived")),
        })
    out.sort(key=lambda p: (not p["pinned"], -p["last_activity"]))
    return out


# ── 某项目下的会话列表 ────────────────────────────────────────────────
def list_sessions(pid: str) -> list[dict] | None:
    d = safe_project_dir(pid)
    if not d:
        return None
    live = live_map()
    out = []
    for f in d.glob("*.jsonl"):
        m = dict(session_meta(f))
        sm = sidecar.get_session(m["id"])
        m["pinned"] = bool(sm.get("pinned"))
        m["archived"] = bool(sm.get("archived"))
        if sm.get("title"):
            m["custom_title"] = sm["title"]
        m["note"] = sm.get("note", "")
        lv = live.get(m["id"])
        m["live"] = {"status": lv.get("status"), "updatedAt": lv.get("updatedAt")} if lv else None
        m["pid"] = pid
        out.append(m)
    out.sort(key=lambda s: (not s["pinned"], -(s.get("mtime") or 0)))
    return out


# ── history.jsonl（全局提示历史）──────────────────────────────────────
def read_history(limit: int = 200) -> list[dict]:
    f = history_file()
    if not f.exists():
        return []
    rows = []
    for obj in read_lines(f):
        rows.append({
            "display": obj.get("display", ""),
            "ts": obj.get("timestamp"),
            "project": obj.get("project", ""),
            "sessionId": obj.get("sessionId", ""),
        })
    rows.reverse()
    return rows[:limit]


# ── 全局搜索 ──────────────────────────────────────────────────────────
def search(query: str, limit: int = 60) -> dict:
    q = (query or "").strip().lower()
    if not q:
        return {"sessions": [], "prompts": []}

    # 1) 历史输入命中
    prompts = []
    for obj in read_lines(history_file()):
        disp = obj.get("display", "")
        if q in disp.lower():
            prompts.append({
                "display": disp[:300], "ts": obj.get("timestamp"),
                "project": obj.get("project", ""), "sessionId": obj.get("sessionId", ""),
            })
            if len(prompts) >= limit:
                break

    # 2) 会话内容命中（标题/人类发言/助手文本/工具名）
    sessions = []
    for pid, f in iter_all_sessions():
        m = session_meta(f)
        snippet = None
        hit_in = None
        if q in (m.get("title", "").lower()):
            snippet, hit_in = m["title"], "标题"
        else:
            for obj in read_lines(f):
                t = obj.get("type")
                if t == "user":
                    txt = text_from_content((obj.get("message") or {}).get("content"))
                elif t == "assistant":
                    txt = " ".join(
                        b.get("text", "") for b in ((obj.get("message") or {}).get("content") or [])
                        if isinstance(b, dict) and b.get("type") == "text")
                else:
                    continue
                low = txt.lower()
                pos = low.find(q)
                if pos >= 0:
                    start = max(0, pos - 40)
                    snippet = clean_title(txt[start:pos + 120])
                    hit_in = "对话"
                    break
        if snippet is not None:
            sessions.append({
                "id": m["id"], "pid": pid, "title": m.get("title", ""),
                "cwd": m.get("cwd", ""), "last_ts": m.get("last_ts"),
                "hit_in": hit_in, "snippet": snippet[:200],
            })
            if len(sessions) >= limit:
                break
    sessions.sort(key=lambda s: s.get("last_ts") or "", reverse=True)
    return {"sessions": sessions, "prompts": prompts}
