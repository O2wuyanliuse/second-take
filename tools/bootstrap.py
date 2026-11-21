#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""second-take 启动自检/初始化。

用法:
    python tools/bootstrap.py            # 初始化: 缺什么建什么, 已存在不动
    python tools/bootstrap.py --check    # 只检查, 不写盘; 退出码 0 = 环境合格
    python tools/bootstrap.py --root /some/where/workspace

路径优先级: --root > 环境变量 SECOND_TAKE_HOME > config.local.json 的 workspace_root > 仓库内 workspace/
原则: 不假设任何目录存在; 缺了就建; 建了什么要说出来。
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONFIG_EXAMPLE = REPO / "config.example.json"
CONFIG_LOCAL = REPO / "config.local.json"
SUBDIRS = ("input", "output", "cache")
MIN_PY = (3, 10)


def utf8_stdio():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def say(msg=""):
    print(msg)


def resolve_root(arg):
    if arg:
        return Path(arg).expanduser().resolve()
    env = os.environ.get("SECOND_TAKE_HOME")
    if env:
        return Path(env).expanduser().resolve()
    if CONFIG_LOCAL.exists():
        try:
            data = json.loads(CONFIG_LOCAL.read_text(encoding="utf-8"))
            value = data.get("workspace_root")
            if value:
                p = Path(value).expanduser()
                return p.resolve() if p.is_absolute() else (REPO / p).resolve()
        except Exception:
            say("[提示] config.local.json 读不出来, 忽略其中的 workspace_root。")
    return REPO / "workspace"


def probe():
    problems = []
    if sys.version_info[:2] < MIN_PY:
        problems.append(
            "python 版本 %d.%d 太低, 需要 %d.%d 以上"
            % (sys.version_info[0], sys.version_info[1], MIN_PY[0], MIN_PY[1])
        )
    if shutil.which("git") is None:
        problems.append("找不到 git: 请先安装 git 并让它出现在 PATH 里")
    return problems


def git_ignores_workspace():
    gi = REPO / ".gitignore"
    if not gi.exists():
        return False
    text = gi.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        if line.strip() in ("workspace/", "/workspace/", "workspace"):
            return True
    return False


def run_check(root):
    problems = probe()
    say("== 检查 ==")
    say("仓库根: %s" % REPO)
    say("工作区: %s" % root)
    for sub in SUBDIRS:
        if not (root / sub).is_dir():
            problems.append(
                "缺少目录 %s: 运行 python tools/bootstrap.py 会自动创建" % (root / sub)
            )
    if not CONFIG_LOCAL.exists():
        problems.append(
            "缺少 %s: 参考 config.example.json 复制一份 (bootstrap 会自动做)" % CONFIG_LOCAL
        )
    if problems:
        say("")
        for p in problems:
            say("[缺] %s" % p)
        say("")
        say("结论: 环境未合格。按上面逐条补齐后再跑一次 --check。")
        return 1
    say("")
    # 钩子只是**本机**的快速反馈，缺了不算环境不合格（CI 里还有同一套），
    # 所以这里给提示、不进 problems——否则 CI 的 --check 会永远红。
    hrc, hcur = git_out("config", "--local", "--get", "core.hooksPath")
    if (REPO / ".githooks").is_dir() and (hrc != 0 or not hcur):
        say("[提示] 本机还没接 .githooks：跑 python tools/bootstrap.py 会接上（CI 不需要它）")
    say("结论: 可以开工。")
    return 0


def git_out(*args):
    """跑一条只读/写入本机配置的 git 命令。失败返回 (rc, "")，不抛。"""
    try:
        r = subprocess.run(["git"] + list(args), cwd=str(REPO), capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
    except OSError:
        return 1, ""
    return r.returncode, (r.stdout or "").strip()


def wire_hooks():
    """把仓库自带的钩子接到本机：只写 `--local`，不覆盖已有的设定。

    为什么必须由 bootstrap 做：`.githooks/` 在仓库里，`core.hooksPath` 在**本机**配置里。
    新 clone 的人没有那一行，于是「门禁在我机器上是绿的」只对作者成立——
    评价里那句「门禁在你这儿绿，等于假安全」说的就是它。
    """
    if not (REPO / ".git").exists():
        return
    if not (REPO / ".githooks").is_dir():
        say("[4/6] 本仓库没有 .githooks/, 跳过钩子。")
        return
    rc, cur = git_out("config", "--local", "--get", "core.hooksPath")
    if rc != 0 or not cur:
        rc2, _ = git_out("config", "--local", "core.hooksPath", ".githooks")
        if rc2 == 0:
            try:
                (REPO / ".git" / "second-take-python").write_text(sys.executable, encoding="utf-8")
            except OSError:
                pass
            say("[4/6] 钩子已接: core.hooksPath → .githooks（本机配置, 不进仓库）")
        else:
            say("[提示] 钩子没接上（git config 失败）。手动跑: git config core.hooksPath .githooks")
        return
    # pre-push 要找一个能跑的 python：把当前解释器路径记在本机（不进仓库）。
    try:
        (REPO / ".git" / "second-take-python").write_text(sys.executable, encoding="utf-8")
    except OSError:
        pass
    if cur.replace("\\", "/").rstrip("/") in (".githooks", str(REPO / ".githooks").replace("\\", "/")):
        say("[4/6] 钩子已指向 .githooks, 不动。")
        return
    say("[提醒] core.hooksPath 已指向 %s, 不动它。要用本仓库钩子: git config core.hooksPath .githooks" % cur)


def run_init(root):
    problems = probe()
    if problems:
        for p in problems:
            say("[停] %s" % p)
        return 1

    say("== 初始化 ==")
    say("[1/6] 探测: python %s / git 可用 / 输出强制 UTF-8" % sys.version.split()[0])

    for name in ("",) + SUBDIRS:
        d = root / name if name else root
        if d.is_dir():
            continue
        d.mkdir(parents=True, exist_ok=True)
        say("[2/6] 已创建工作区目录: %s" % d)
    if root.is_dir() and not any(True for _ in [1]):
        pass

    if CONFIG_LOCAL.exists():
        say("[3/6] 配置文件已存在, 不动: %s" % CONFIG_LOCAL.name)
    elif CONFIG_EXAMPLE.exists():
        data = json.loads(CONFIG_EXAMPLE.read_text(encoding="utf-8"))
        data.setdefault("workspace_root", "workspace")
        CONFIG_LOCAL.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        say("[3/6] 已生成配置文件: %s (来自 config.example.json)" % CONFIG_LOCAL.name)
    else:
        CONFIG_LOCAL.write_text(
            json.dumps({"workspace_root": "workspace"}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        say("[3/6] 没有 config.example.json, 已写最小配置: %s" % CONFIG_LOCAL.name)

    wire_hooks()

    gate = REPO / "gate" / "_gate.py"
    if gate.exists():
        say("[5/6] 跑一次最小门禁 ...")
        try:
            r = subprocess.run(
                [sys.executable, str(gate)],
                cwd=str(REPO),
                capture_output=True,
                timeout=180,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            say((r.stdout or "").strip() or "(门禁无输出)")
            if r.returncode != 0:
                say("[注意] 门禁返回 %d: 不影响首次启动, 但开工前请按上面的提示处理。" % r.returncode)
        except Exception as e:
            say("[注意] 门禁没跑起来 (%s), 跳过。" % e)
    else:
        say("[5/6] 本仓库没有 gate/_gate.py, 跳过门禁。")

    if not git_ignores_workspace() and (REPO / ".git").exists():
        say("[提醒] .gitignore 里还没有 workspace/, 建议加一行, 免得把用户材料提交上去。")

    say("[6/6] 下一步:")
    say("  python tools/bootstrap.py --check")
    say("  (然后按 README 的三条命令走到第一格)")
    say("")
    say("结论: 环境就绪。")
    return 0


def main():
    utf8_stdio()
    ap = argparse.ArgumentParser(description="second-take 启动自检 / 初始化")
    ap.add_argument("--check", action="store_true", help="只检查, 不写盘")
    ap.add_argument("--root", default=None, help="工作区根目录 (覆盖环境变量与配置)")
    args = ap.parse_args()
    root = resolve_root(args.root)
    return run_check(root) if args.check else run_init(root)


if __name__ == "__main__":
    sys.exit(main())
