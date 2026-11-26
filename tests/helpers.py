# -*- coding: utf-8 -*-
"""用例共用的小工具：造临时仓库、拷脚本、跑子进程。

**这些用例测的是本库自己的检查器，不是任何项目的产物。**
所以每个用例都在临时目录里造一个最小仓库，拷进被测脚本，
绝不拿真实仓库当靶子——那样「测试通过」只说明当前仓库恰好干净。
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# 固定提交者身份：CI 的干净机器没有 git user.name，不写这一步第一次 commit 就卡住。
GIT_ID = ("-c", "user.name=tester", "-c", "user.email=tester@example.com",
          "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false")


def git(cwd, *args):
    return subprocess.run(
        ["git"] + list(GIT_ID) + list(args),
        cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def new_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    r = git(path, "init", "-q")
    assert r.returncode == 0, r.stderr
    return path


def copy_into(root, *rel_paths):
    """把本仓库的脚本按原相对路径拷进临时仓库（脚本靠 __file__ 找 ROOT）。"""
    if any(rel.startswith("tools/") for rel in rel_paths):
        rel_paths = (*rel_paths, "tools/_common.py")
    for rel in rel_paths:
        src = REPO / rel
        dst = Path(root) / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def write(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def run(root, script, *args, env=None):
    e = os.environ.copy()
    e["PYTHONIOENCODING"] = "utf-8"
    # 宿主环境里的 LEAK_WORDS 会偷偷给扫描器一份词表，让「没给词表」的用例失真
    e.pop("LEAK_WORDS", None)
    if env:
        e.update(env)
    return subprocess.run(
        [sys.executable, str(Path(root) / script), *args],
        cwd=str(root), capture_output=True, text=True, encoding="utf-8", errors="replace", env=e,
    )


def commit(root, msg, allow_empty=False):
    git(root, "add", "-A")
    args = ["commit", "-q", "-m", msg]
    if allow_empty:
        args.insert(1, "--allow-empty")
    r = git(root, *args)
    assert r.returncode == 0, r.stderr
    return git(root, "rev-parse", "HEAD").stdout.strip()
