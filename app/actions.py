"""管理操作：导出 Markdown、（软）删除、在新终端 resume 会话。"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from .config import TRASH_DIR


def export_markdown(detail: dict) -> str:
    m = detail.get("meta", {})
    lines = [
        f"# 会话 {m.get('id', '')}",
        "",
        f"- **项目**: `{m.get('cwd', '')}`",
        f"- **模型**: {m.get('model', '') or '—'}",
        f"- **时间**: {m.get('first_ts', '')} → {m.get('last_ts', '')}",
        f"- **消息**: 用户 {m.get('n_user', 0)} · 助手 {m.get('n_assistant', 0)} · 工具 {m.get('n_tool', 0)}",
        f"- **Token**: {m.get('total_tokens', 0):,}",
        "",
        "---",
        "",
    ]
    for ev in detail.get("events", []):
        kind = ev.get("kind")
        if kind == "human":
            lines += ["### 👤 用户", "", ev.get("text", "").rstrip(), ""]
        elif kind == "assistant":
            lines += [f"### 🤖 Claude  ·  `{ev.get('model') or '—'}`", ""]
            for b in ev.get("blocks", []):
                bt = b.get("type")
                if bt == "thinking":
                    lines += ["<details><summary>💭 思考</summary>", "",
                              b.get("text", "").rstrip(), "", "</details>", ""]
                elif bt == "text":
                    lines += [b.get("text", "").rstrip(), ""]
                elif bt == "tool_use":
                    inp = json.dumps(b.get("input", {}), ensure_ascii=False, indent=2)
                    lines += [f"**🔧 工具调用 `{b.get('name')}`**", "",
                              "```json", inp, "```", ""]
        elif kind == "tool_result":
            tag = "❌ 工具错误" if ev.get("is_error") else "✅ 工具结果"
            body = ev.get("text", "").rstrip()
            lines += [f"<details><summary>{tag}</summary>", "",
                      "```", body, "```", "", "</details>", ""]
        elif kind == "system":
            lines += [f"> ⚙️ *{ev.get('subtype', '')}*: {ev.get('text', '')[:200]}", ""]
    return "\n".join(lines)


def soft_delete(session_file: Path) -> str:
    """把会话文件（及同名子目录）移到 data/trash，可恢复。

    用 shutil.move 而非 Path.replace：会话在 C: 盘、回收站在 D: 盘时，
    os.replace 会因跨盘失败（WinError 17），shutil.move 会自动退化为复制+删除。
    """
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = TRASH_DIR / f"{stamp}__{session_file.name}"
    shutil.move(str(session_file), str(dest))
    sibling = session_file.with_suffix("")  # <sid>/ 目录
    if sibling.is_dir():
        try:
            shutil.move(str(sibling), str(TRASH_DIR / f"{stamp}__{sibling.name}"))
        except OSError:
            pass
    return str(dest)


def resume_session(cwd: str, sid: str) -> dict:
    """在新终端窗口里 `claude --resume <sid>`，工作目录设为项目 cwd。"""
    workdir = cwd if cwd and Path(cwd).is_dir() else None
    if os.name == "nt":
        try:
            subprocess.Popen(
                ["cmd", "/k", "claude", "--resume", sid],
                cwd=workdir,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}
    else:
        term = os.environ.get("TERMINAL", "x-terminal-emulator")
        try:
            subprocess.Popen([term, "-e", f"claude --resume {sid}"], cwd=workdir)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e),
                    "hint": f"请手动运行：cd {cwd} && claude --resume {sid}"}
    return {"ok": True, "command": f"claude --resume {sid}", "cwd": workdir or cwd}
