"""Sidecar 元数据：置顶 / 归档 / 自定义标题 / 备注。

存在应用自己的 data/meta.json，**绝不**写入 Claude 的原始文件。
"""
from __future__ import annotations

import json
import threading

from .config import META_FILE

_lock = threading.Lock()


def _load() -> dict:
    if not META_FILE.exists():
        return {"sessions": {}, "projects": {}}
    try:
        data = json.loads(META_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"sessions": {}, "projects": {}}
    data.setdefault("sessions", {})
    data.setdefault("projects", {})
    return data


def _save(data: dict) -> None:
    tmp = META_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(META_FILE)


def get_session(sid: str) -> dict:
    return _load()["sessions"].get(sid, {})


def get_project(pid: str) -> dict:
    return _load()["projects"].get(pid, {})


def all_sessions() -> dict:
    return _load()["sessions"]


def all_projects() -> dict:
    return _load()["projects"]


def _set(bucket: str, key: str, patch: dict) -> dict:
    with _lock:
        data = _load()
        cur = data[bucket].get(key, {})
        cur.update({k: v for k, v in patch.items() if v is not None})
        # 允许显式清空：值为 "" 删除该字段
        for k, v in patch.items():
            if v == "" and k in cur:
                del cur[k]
        data[bucket][key] = cur
        _save(data)
        return cur


def set_session(sid: str, **patch) -> dict:
    return _set("sessions", sid, patch)


def set_project(pid: str, **patch) -> dict:
    return _set("projects", pid, patch)
