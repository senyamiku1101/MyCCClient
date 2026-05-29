"""解析 Claude Code 的会话 JSONL。

提供两个层次：
- session_meta(path): 列表用的轻量元数据（标题/时间/模型/计数/token 合计），按 mtime 缓存。
- session_detail(path): 查看器用的完整事件流（human/assistant/tool_result/system…）。

所有文件一律按 UTF-8 读取。单行损坏会被跳过而不是让整个会话失败。
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from .config import estimate_cost

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
MAX_BLOCK = 100_000  # 单个块文本上限，避免超大文件拖垮前端

_meta_cache: dict[str, dict] = {}


# ── 文本工具 ──────────────────────────────────────────────────────────
def clean_title(text: str) -> str:
    """把一段用户输入压成适合做标题的一行。"""
    if not text:
        return ""
    # 去掉 slash 命令 / 系统提醒等 XML 式标签包裹
    text = re.sub(r"<command-[^>]*>.*?</command-[^>]*>", " ", text, flags=re.S)
    text = re.sub(r"<local-command-[^>]*>.*?</local-command-[^>]*>", " ", text, flags=re.S)
    text = re.sub(r"<system-reminder>.*?</system-reminder>", " ", text, flags=re.S)
    text = _TAG_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def text_from_content(content) -> str:
    """把 message.content（字符串或块数组）里的**人类文本**抽出来。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text":
                parts.append(b.get("text", ""))
        return "\n".join(parts)
    return ""


def _truncate(s: str) -> tuple[str, bool]:
    if s and len(s) > MAX_BLOCK:
        return s[:MAX_BLOCK], True
    return s, False


def _tool_result_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if not isinstance(b, dict):
                parts.append(str(b))
            elif b.get("type") == "text":
                parts.append(b.get("text", ""))
            elif b.get("type") == "image":
                parts.append("[图片]")
            else:
                parts.append(json.dumps(b, ensure_ascii=False))
        return "\n".join(parts)
    return "" if content is None else str(content)


# ── 低层读取 ──────────────────────────────────────────────────────────
def read_lines(path: Path):
    """逐行 yield 解析后的 dict，跳过空行与损坏行。"""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


# ── 轻量元数据（列表用）────────────────────────────────────────────────
def session_meta(path: Path) -> dict:
    try:
        st = path.stat()
    except OSError:
        return {}
    key = f"{path}:{st.st_mtime_ns}:{st.st_size}"
    cached = _meta_cache.get(str(path))
    if cached and cached.get("_key") == key:
        return cached

    sid = path.stem
    title = ""
    cwd = git_branch = version = ""
    first_ts = last_ts = ""
    n_user = n_assistant = n_tool = 0
    usage = {"input_tokens": 0, "output_tokens": 0,
             "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    cost = 0.0
    cost_known = False
    models = Counter()

    for obj in read_lines(path):
        t = obj.get("type")
        ts = obj.get("timestamp")
        if ts:
            first_ts = first_ts or ts
            last_ts = ts
        if not cwd and obj.get("cwd"):
            cwd = obj["cwd"]
        if not git_branch and obj.get("gitBranch"):
            git_branch = obj["gitBranch"]
        if not version and obj.get("version"):
            version = obj["version"]

        if t == "user":
            msg = obj.get("message") or {}
            content = msg.get("content")
            human = clean_title(text_from_content(content))
            if human:
                n_user += 1
                if not title:
                    title = human[:120]
            # 统计该 user 行里的 tool_result 数（不计入 user 消息数）
            if isinstance(content, list):
                n_tool += sum(1 for b in content
                              if isinstance(b, dict) and b.get("type") == "tool_result")
        elif t == "assistant":
            n_assistant += 1
            msg = obj.get("message") or {}
            model = msg.get("model")
            if model:
                models[model] += 1
            u = msg.get("usage") or {}
            for k in usage:
                usage[k] += u.get(k, 0)
            c = estimate_cost(model, u)
            if c is not None:
                cost += c
                cost_known = True

    primary_model = models.most_common(1)[0][0] if models else ""
    meta = {
        "_key": key,
        "id": sid,
        "title": title,
        "cwd": cwd,
        "git_branch": git_branch,
        "version": version,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "mtime": st.st_mtime,
        "size": st.st_size,
        "n_user": n_user,
        "n_assistant": n_assistant,
        "n_tool": n_tool,
        "model": primary_model,
        "models": list(models.keys()),
        "usage": usage,
        "total_tokens": sum(usage.values()),
        "cost": round(cost, 4) if cost_known else None,
    }
    _meta_cache[str(path)] = meta
    return meta


# ── 完整事件流（查看器用）──────────────────────────────────────────────
def session_detail(path: Path) -> dict:
    events = []
    for obj in read_lines(path):
        t = obj.get("type")
        ts = obj.get("timestamp")

        if t == "user":
            msg = obj.get("message") or {}
            content = msg.get("content")
            if isinstance(content, list):
                # 先发 tool_result，再发人类文本（保持可读顺序）
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        txt, trunc = _truncate(_tool_result_text(b.get("content")))
                        events.append({
                            "kind": "tool_result",
                            "tool_use_id": b.get("tool_use_id"),
                            "is_error": bool(b.get("is_error")),
                            "text": txt, "truncated": trunc, "ts": ts,
                        })
                human = text_from_content(content)
                if human.strip():
                    events.append({"kind": "human", "text": human, "ts": ts})
            else:
                if (content or "").strip():
                    events.append({"kind": "human", "text": content, "ts": ts})

        elif t == "assistant":
            msg = obj.get("message") or {}
            blocks = []
            for b in (msg.get("content") or []):
                if not isinstance(b, dict):
                    continue
                bt = b.get("type")
                if bt == "thinking":
                    txt, trunc = _truncate(b.get("thinking", ""))
                    blocks.append({"type": "thinking", "text": txt, "truncated": trunc})
                elif bt == "text":
                    txt, trunc = _truncate(b.get("text", ""))
                    blocks.append({"type": "text", "text": txt, "truncated": trunc})
                elif bt == "tool_use":
                    blocks.append({"type": "tool_use", "id": b.get("id"),
                                   "name": b.get("name"), "input": b.get("input")})
            if blocks:
                events.append({
                    "kind": "assistant",
                    "model": msg.get("model"),
                    "usage": msg.get("usage") or {},
                    "blocks": blocks, "ts": ts,
                })

        elif t == "system":
            txt, trunc = _truncate(clean_title(obj.get("content", "")))
            if txt:
                events.append({"kind": "system", "subtype": obj.get("subtype", ""),
                               "text": txt, "truncated": trunc, "ts": ts})

        elif t == "last-prompt":
            events.append({"kind": "checkpoint", "leaf": obj.get("leafUuid")})

    meta = session_meta(path)
    return {"meta": meta, "events": events}
