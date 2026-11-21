#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""维护方法双写检查。

规则: 一次改动若触及流程相关目录, 必须同时改 docs/maintain/维护方法.md;
      否则 commit message 里要带 [no-procedure-change: 理由]。

用法:
    python tools/check_maintenance.py                 # 查 HEAD 这一个提交
    python tools/check_maintenance.py --base origin/master
    python tools/check_maintenance.py --staged --message-file .git/COMMIT_EDITMSG
"""

import argparse
import re
import subprocess
import sys

PROTECTED = ("scripts/", "gate/", "packaging/", ".github/", "tools/")
DOC = "docs/maintain/维护方法.md"
TAG = "[no-procedure-change"


def git(*args):
    r = subprocess.run(["git", "-c", "core.quotepath=false"] + list(args), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit("git %s 失败: %s" % (" ".join(args), (r.stderr or "").strip()))
    return r.stdout


def changed_files(args):
    if args.staged:
        return [p for p in git("diff", "--cached", "--name-only").splitlines() if p.strip()]
    base = args.base or "HEAD~1"
    try:
        out = git("diff", "--name-only", "%s...HEAD" % base)
    except SystemExit:
        out = git("diff", "--name-only", base, "HEAD")
    return [p for p in out.splitlines() if p.strip()]


def message(args):
    if args.message_file:
        try:
            with open(args.message_file, encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return ""
    return git("log", "-1", "--format=%B", "HEAD")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--base", default=None)
    ap.add_argument("--message-file", default=None)
    args = ap.parse_args()

    files = changed_files(args)
    touched = [f for f in files if any(f.startswith(p) for p in PROTECTED)]
    if not touched:
        print("无流程相关改动, 通过。")
        return 0

    if any(f == DOC for f in files):
        print("已同步维护方法 (%s), 通过。" % DOC)
        return 0

    msg = message(args)
    if TAG in msg and re.search(r"\[no-procedure-change[:：][^\]\n]{2,}\]", msg):
        print("提交信息已声明流程未变, 通过。")
        return 0

    print("改动触及流程目录:")
    for f in touched:
        print("  - %s" % f)
    print("")
    print("但 %s 没有一起改。" % DOC)
    print("")
    print("两条路, 选一条:")
    print("  1) 把步骤 / 命令 / 边界的实际变化写进 %s, 并在 §9 追加一条变更记录;" % DOC)
    print("  2) 在提交信息里写一行:")
    print("     [no-procedure-change: 说明为什么这次改了代码但流程没变]")
    print("")
    print("只改脚本不改流程, 下一个人照着旧步骤做会踩同一个坑。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
