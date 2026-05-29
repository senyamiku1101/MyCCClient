"""启动入口：拉起本地服务并自动打开浏览器。

用法： python run.py  [--port 8765] [--no-browser]
"""
from __future__ import annotations

import argparse
import threading
import webbrowser

import uvicorn


def main():
    ap = argparse.ArgumentParser(description="MyCCClient — Claude Code 项目/会话管理器")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = ap.parse_args()

    url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    print(f"\n  MyCCClient 已启动 →  {url}\n  按 Ctrl+C 退出。\n")
    uvicorn.run("app.main:app", host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
