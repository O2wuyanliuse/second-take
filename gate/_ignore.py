# -*- coding: utf-8 -*-
"""_ignore.py · 扫描时要跳过的目录，唯一来源

为什么单开一份：`_links` / `_orphan` / `_redline` 各写一套 `SKIP_DIRS`，里面都钉着
同一个**本机 AI 工具的目录名**。通用层不该知道某台机器上那个工具叫什么——要跳过的是
「不知道名字的缓存目录」，不是「叫某个固定名字的目录」。名字一变，四处同时失效，
而且每处都要跟着泄一次。

三层来源，后者覆盖前者：
  1. 内置中性集——任何项目都该跳的（`__pycache__` 之类）
  2. `gate_profile.json` 的 `"忽略目录": [...]`——本库/本项目的配置
  3. 环境变量 `GATE_IGNORE_DIRS`（冒号或分号分隔）——临时跑、CI 用

私库侧跑的时候给一条 `GATE_IGNORE_DIRS=<你的缓存目录名>` 就恢复原行为；
不给也不影响任何判据，只是少跳一个目录、多扫几个文件。
"""

import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 中性集：与任何具体工具无关
BUILTIN = (".git", "__pycache__", "node_modules", ".venv", ".idea", ".vscode", ".ruff_cache")


def ignored_dirs():
    """返回要跳过的**目录名**集合（不含路径分隔符）。"""
    names = set(BUILTIN)
    prof = os.path.join(ROOT, "gate_profile.json")
    if os.path.isfile(prof):
        try:
            data = json.loads(io.open(prof, encoding="utf-8").read())
            for x in (data.get("忽略目录") or []):
                if str(x).strip():
                    names.add(str(x).strip())
        except (ValueError, OSError):
            pass
    env = os.environ.get("GATE_IGNORE_DIRS", "")
    for x in env.replace(";", ":").split(":"):
        if x.strip():
            names.add(x.strip())
    return names


def is_ignored(rel_path, names=None):
    """相对路径的第一段是否落在忽略集合里。"""
    names = names if names is not None else ignored_dirs()
    return rel_path.replace("\\", "/").split("/")[0] in names
