"""项目目录名 ↔ 真实路径。

Claude 把项目 cwd 编码成目录名：把 ':' '\\' '/' 都替换成 '-'。
解码本身有歧义（无法区分原来是 '-' 还是分隔符），所以真实路径优先
从会话 JSONL 里的 cwd 字段读取，本模块的 decode 仅作兜底显示。
"""
from __future__ import annotations

import re

_DRIVE_RE = re.compile(r"^([A-Za-z])--(.*)$")


def decode_project_name(name: str) -> str:
    """兜底：'D--Documents-AIProjects-Foo' -> 'D:\\Documents\\AIProjects\\Foo'。"""
    m = _DRIVE_RE.match(name)
    if m:
        drive, rest = m.group(1), m.group(2)
        return f"{drive}:\\" + rest.replace("-", "\\")
    # 类 Unix 路径：'-home-user-foo' -> '/home/user/foo'
    if name.startswith("-"):
        return "/" + name[1:].replace("-", "/")
    return name.replace("-", "/")


def short_label(path: str) -> str:
    """取路径最后一段作为短标签。"""
    p = path.replace("\\", "/").rstrip("/")
    return p.rsplit("/", 1)[-1] if "/" in p else p
