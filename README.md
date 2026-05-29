# MyCCClient

一个本地、零依赖前端的 **Claude Code 项目 / 会话可视化管理器**。

它读取你本机 `~/.claude/` 下的真实数据，用浏览器界面浏览、搜索、管理你用 Claude Code CLI 跑过的所有项目和会话——无需联网、不上传任何数据。

```
┌──────────────────────────────────────────────────────────────────┐
│  ◆ MyCCClient        [ 全局搜索 Ctrl+K ]      📊 看板  ⚙  ↻        │
├──────────────┬───────────────────────┬─────────────────────────────┤
│ 项目          │ 会话                   │ 完整对话                     │
│ ● MyCCClient │ ◉ 你好                 │ 👤 用户 / 🤖 Claude          │
│   TOKENICODE │   model · 4.4M · ●在线 │ 💭 思考  🔧 工具  ✅ 结果     │
│   …          │   ▶ 📌 ⬇ 🗑           │ ↩ 检查点                     │
└──────────────┴───────────────────────┴─────────────────────────────┘
```

## 快速开始

```bash
pip install -r requirements.txt   # 仅需 fastapi + uvicorn
python run.py                     # 启动后自动打开浏览器 → http://127.0.0.1:8765
```

可选参数：`python run.py --port 9000 --no-browser`

## 功能

- **项目总览** — 自动从会话内容读取真实路径，展示会话数、累计 token、估算花费、最近活动；**在线指示灯**标出正在运行的会话
- **会话列表** — 自动标题（取首条用户输入）、模型、token、消息数、实时状态（busy/idle）
- **会话查看器** — 完整还原对话：用户 / 助手 / 💭思考 / 🔧工具调用 / ✅工具结果 / ↩检查点，长内容自动折叠，轻量 Markdown 渲染
- **全局搜索**（`Ctrl+K`）— 跨所有项目搜会话标题、对话内容、历史输入，点击直达
- **用量看板** — 总量卡片、Token 构成、按模型 / 按项目 / 按天的条形图
- **管理操作** — ▶ 在新终端 `claude --resume` 继续会话、📌 置顶、🗄 归档、⬇ 导出 Markdown、🗑 删除（软删除到回收站）
- **配置查看** — 一览 `~/.claude/settings.json`

## 架构

```
app/                后端（Python + FastAPI）
  config.py         定位 ~/.claude、应用数据目录、价格表
  paths.py          项目目录名 ↔ 真实路径（兜底解码）
  parser.py         JSONL 解析：轻量元数据 + 完整事件流（UTF-8、容错）
  scanner.py        扫描项目/会话/实时进程/history、全局搜索
  stats.py          跨会话用量聚合
  meta.py           sidecar 元数据（置顶/归档/备注），存 data/meta.json
  actions.py        导出 Markdown、软删除、resume
  main.py           FastAPI 路由 + 托管前端
web/                前端（原生 HTML/CSS/JS，零 CDN、零构建）
  index.html  styles.css  util.js  api.js  viewer.js  app.js
data/               应用自身数据：meta.json、trash/（不污染 ~/.claude）
run.py              启动入口
```

数据来源（只读，删除除外）：
| 数据 | 位置 |
|---|---|
| 项目 / 会话记录 | `~/.claude/projects/<编码路径>/<id>.jsonl` |
| 实时运行的会话 | `~/.claude/sessions/<pid>.json` |
| 历史输入 | `~/.claude/history.jsonl` |
| 全局配置 | `~/.claude/settings.json` |

## 数据与安全

- **纯本地**：只起 `127.0.0.1` 上的本地服务，不向外发送任何数据。
- **只读为主**：除"删除"外，绝不修改 Claude 的原始文件；置顶/归档/备注等都存在本应用的 `data/meta.json`。
- **删除是软删除**：会话文件被移动到 `data/trash/`（带时间戳），可手动恢复，不会真正抹掉。

## 注意事项 / 已知限制

- **花费为粗略估算**：仅对可识别的 Anthropic 模型（opus/sonnet/haiku）按公开价计算；第三方供应商（DeepSeek、GLM、Kimi、MiniMax 等）的 token 仍统计，但花费显示为 `—`。
- **"继续会话"** 在 Windows 下会新开一个 `cmd` 窗口运行 `claude --resume <id>`，需 `claude` 已在 PATH 中。
- 首次加载会完整解析一遍会话文件以统计 token；之后按文件 mtime 缓存，再次打开很快。
- 支持环境变量 `CLAUDE_CONFIG_DIR` 覆盖 `~/.claude` 位置。

## 后续可扩展

- 会话内关键字定位 / 跳转检查点
- 按日期范围筛选、活跃度热力图日历
- 用 Tauri 包成单文件桌面 App
