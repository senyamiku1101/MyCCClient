"""跨所有会话的用量聚合：token、花费、模型占比、按天活跃度。"""
from __future__ import annotations

from collections import defaultdict

from .parser import session_meta
from .paths import short_label
from .scanner import _project_real_path, iter_all_sessions
from .config import projects_dir


def usage_stats() -> dict:
    totals = {"input_tokens": 0, "output_tokens": 0,
              "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    total_cost = 0.0
    cost_known = False
    n_sessions = n_user = n_assistant = 0

    by_model = defaultdict(lambda: {"sessions": 0, "tokens": 0, "input": 0, "output": 0})
    by_day = defaultdict(lambda: {"tokens": 0, "sessions": 0})
    by_project_tokens = defaultdict(int)

    project_paths = {}
    pd = projects_dir()
    if pd.is_dir():
        for d in pd.iterdir():
            if d.is_dir():
                metas = [session_meta(f) for f in d.glob("*.jsonl")]
                project_paths[d.name] = _project_real_path(d, metas)

    for pid, f in iter_all_sessions():
        m = session_meta(f)
        if not m:
            continue
        n_sessions += 1
        n_user += m.get("n_user", 0)
        n_assistant += m.get("n_assistant", 0)
        u = m.get("usage", {})
        for k in totals:
            totals[k] += u.get(k, 0)
        if m.get("cost") is not None:
            total_cost += m["cost"]
            cost_known = True

        model = m.get("model") or "（未知）"
        bm = by_model[model]
        bm["sessions"] += 1
        bm["tokens"] += m.get("total_tokens", 0)
        bm["input"] += u.get("input_tokens", 0)
        bm["output"] += u.get("output_tokens", 0)

        day = (m.get("last_ts") or "")[:10]
        if day:
            by_day[day]["tokens"] += m.get("total_tokens", 0)
            by_day[day]["sessions"] += 1

        label = short_label(project_paths.get(pid, pid))
        by_project_tokens[label] += m.get("total_tokens", 0)

    models = [{"model": k, **v} for k, v in
              sorted(by_model.items(), key=lambda kv: -kv[1]["tokens"])]
    days = [{"date": k, **v} for k, v in sorted(by_day.items())]
    projects = [{"label": k, "tokens": v} for k, v in
                sorted(by_project_tokens.items(), key=lambda kv: -kv[1])]

    return {
        "totals": totals,
        "total_tokens": sum(totals.values()),
        "total_cost": round(total_cost, 4) if cost_known else None,
        "n_projects": len(project_paths),
        "n_sessions": n_sessions,
        "n_user": n_user,
        "n_assistant": n_assistant,
        "by_model": models,
        "by_day": days,
        "by_project": projects,
    }
