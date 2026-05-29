"""FastAPI 应用：JSON API + 托管前端静态文件。"""
from __future__ import annotations

import json
import mimetypes

# Windows 注册表常把 .js 映射成 text/plain，会导致浏览器拒绝执行 ES module。
# 这里强制纠正，必须在挂载 StaticFiles 之前完成。
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import meta as sidecar
from . import scanner
from .actions import export_markdown, resume_session, soft_delete
from .config import WEB_DIR, claude_dir, settings_file
from .parser import session_detail
from .stats import usage_stats

app = FastAPI(title="MyCCClient", version="0.1.0")


class MetaPatch(BaseModel):
    pinned: bool | None = None
    archived: bool | None = None
    title: str | None = None
    note: str | None = None


def _require_session(pid: str, sid: str):
    p = scanner.session_path(pid, sid)
    if not p:
        raise HTTPException(404, "会话不存在")
    return p


# ── 只读端点 ──────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"ok": True, "claude_dir": str(claude_dir()), "exists": claude_dir().is_dir()}


@app.get("/api/projects")
def api_projects():
    return scanner.list_projects()


@app.get("/api/projects/{pid}/sessions")
def api_sessions(pid: str):
    out = scanner.list_sessions(pid)
    if out is None:
        raise HTTPException(404, "项目不存在")
    return out


@app.get("/api/projects/{pid}/sessions/{sid}")
def api_session_detail(pid: str, sid: str):
    p = _require_session(pid, sid)
    detail = session_detail(p)
    sm = sidecar.get_session(sid)
    detail["meta"]["pinned"] = bool(sm.get("pinned"))
    detail["meta"]["archived"] = bool(sm.get("archived"))
    detail["meta"]["note"] = sm.get("note", "")
    if sm.get("title"):
        detail["meta"]["custom_title"] = sm["title"]
    detail["meta"]["pid"] = pid
    return detail


@app.get("/api/search")
def api_search(q: str = ""):
    return scanner.search(q)


@app.get("/api/stats")
def api_stats():
    return usage_stats()


@app.get("/api/live")
def api_live():
    return list(scanner.live_map().values())


@app.get("/api/history")
def api_history(limit: int = 200):
    return scanner.read_history(limit)


@app.get("/api/settings")
def api_settings():
    f = settings_file()
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return {"error": str(e)}


# ── 操作端点 ──────────────────────────────────────────────────────────
@app.post("/api/projects/{pid}/sessions/{sid}/resume")
def api_resume(pid: str, sid: str):
    p = _require_session(pid, sid)
    from .parser import session_meta
    cwd = session_meta(p).get("cwd", "")
    return resume_session(cwd, sid)


@app.get("/api/projects/{pid}/sessions/{sid}/export")
def api_export(pid: str, sid: str):
    p = _require_session(pid, sid)
    return {"markdown": export_markdown(session_detail(p)), "filename": f"{sid}.md"}


@app.post("/api/projects/{pid}/sessions/{sid}/meta")
def api_session_meta(pid: str, sid: str, patch: MetaPatch):
    _require_session(pid, sid)
    return sidecar.set_session(sid, **patch.model_dump(exclude_none=True))


@app.delete("/api/projects/{pid}/sessions/{sid}")
def api_delete(pid: str, sid: str):
    p = _require_session(pid, sid)
    return {"ok": True, "trash": soft_delete(p)}


@app.post("/api/projects/{pid}/meta")
def api_project_meta(pid: str, patch: MetaPatch):
    if not scanner.safe_project_dir(pid):
        raise HTTPException(404, "项目不存在")
    return sidecar.set_project(pid, **patch.model_dump(exclude_none=True))


# ── 静态前端（必须最后挂载，避免盖住 /api）────────────────────────────
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
