"""全局配置：定位 ~/.claude、应用数据目录、价格表。"""
from __future__ import annotations

import os
from pathlib import Path


def claude_dir() -> Path:
    """Claude Code 的配置/数据根目录。支持用环境变量覆盖。"""
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".claude"


def projects_dir() -> Path:
    return claude_dir() / "projects"


def sessions_dir() -> Path:
    """正在运行的会话注册表（每个进程一个 <pid>.json）。"""
    return claude_dir() / "sessions"


def history_file() -> Path:
    return claude_dir() / "history.jsonl"


def settings_file() -> Path:
    return claude_dir() / "settings.json"


# ── 应用自身的目录（绝不污染 ~/.claude）──────────────────────────────
APP_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = APP_ROOT / "web"
DATA_DIR = APP_ROOT / "data"
TRASH_DIR = DATA_DIR / "trash"
META_FILE = DATA_DIR / "meta.json"

DATA_DIR.mkdir(exist_ok=True)
TRASH_DIR.mkdir(exist_ok=True)


# ── 粗略价格表（美元 / 百万 token）。仅用于 Anthropic 模型的估算 ────────
# 顺序：input, output, cache_read, cache_write。第三方供应商一律按未知处理。
PRICING = {
    "opus": (15.0, 75.0, 1.5, 18.75),
    "sonnet": (3.0, 15.0, 0.30, 3.75),
    "haiku": (0.80, 4.0, 0.08, 1.0),
}


def price_for(model: str | None):
    """按模型名子串匹配价格；匹配不到返回 None（视为未知/第三方）。"""
    if not model:
        return None
    m = model.lower()
    if "claude" not in m and not any(k in m for k in PRICING):
        return None
    for key, rates in PRICING.items():
        if key in m:
            return rates
    return None


def estimate_cost(model: str | None, usage: dict) -> float | None:
    rates = price_for(model)
    if not rates:
        return None
    pin, pout, pcr, pcw = rates
    return (
        usage.get("input_tokens", 0) * pin
        + usage.get("output_tokens", 0) * pout
        + usage.get("cache_read_input_tokens", 0) * pcr
        + usage.get("cache_creation_input_tokens", 0) * pcw
    ) / 1_000_000
