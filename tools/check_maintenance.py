#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""维护方法双写检查。

规则：一个**提交**若触及流程相关目录，必须同时改 docs/maintain/维护方法.md；
      否则那个提交的信息里要带 [no-procedure-change: 理由]。

2026-11-21 · v1.8：从「只看最后一个提交」改成**逐提交判**。
原实现 diff 看 `base...HEAD` 整个范围、message 只读 HEAD，于是这一串能混过去：
  · 提交 A：改 `gate/`，没同步维护方法
  · 提交 B：只改 README，信息里写 `[no-procedure-change: 排版]`
检查读的是 B 的消息、看的是 A+B 的文件，判「有免责标签」→ 通过。
**范围按整个区间取、消息只取一条，这两个口径一旦错配，标签就能替别人免责。**
经过写在 docs/maintain/维护方法.md §9 v1.8。

用法：
    python tools/check_maintenance.py                 # 只查 HEAD 这一个提交
    python tools/check_maintenance.py --base origin/master
    python tools/check_maintenance.py --staged --message-file .git/COMMIT_EDITMSG

退出码：0 通过 ／ 1 有提交触犯（或这一步没查成——**没查成不算通过**）
"""

import argparse
import re
import subprocess
import sys

PROTECTED = ("scripts/", "gate/", "packaging/", ".github/", "tools/")
DOC = "docs/maintain/维护方法.md"
TAG_RE = re.compile(r"\[no-procedure-change[:：][^\]\n]{2,}\]")


def die(msg):
    print("[check] ⛔ " + msg, file=sys.stderr)
    print("[check] 这一步没查成 —— **不算通过**。", file=sys.stderr)
    raise SystemExit(1)


def git(*args):
    r = subprocess.run(
        ["git", "-c", "core.quotepath=false"] + list(args),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        die("git %s 失败：%s" % (" ".join(args), (r.stderr or "").strip()[:300]))
    return r.stdout


def files_of_commit(sha):
    """一个提交改了什么。根提交没有父，用 diff-tree --root。

    合并提交按**第一个父**取 diff：合并本身如果带进了流程改动，至少会被看见一次；
    逐父展开会把同一处改动报两遍，读数更难。
    """
    parents = git("rev-list", "--parents", "-n", "1", sha).split()[1:]
    if parents:
        out = git("diff", "--name-only", parents[0], sha)
    else:
        out = git("diff-tree", "--root", "--no-commit-id", "--name-only", "-r", sha)
    return [p for p in out.splitlines() if p.strip()]


def staged_files():
    return [p for p in git("diff", "--cached", "--name-only").splitlines() if p.strip()]


def message(args):
    if args.message_file:
        try:
            with open(args.message_file, encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return ""
    return git("log", "-1", "--format=%B", "HEAD")


def verdict(files, msg):
    """这个提交触犯了吗？返回触犯的流程文件（空＝通过）。

    三个条件必须落在**同一个提交**里：它改的文件、它自己的消息。
    把 A 的文件配 B 的消息，就是 v1.7 那个洞。
    """
    touched = [f for f in files if any(f.startswith(p) for p in PROTECTED)]
    if not touched:
        return []
    if DOC in files:
        return []
    if TAG_RE.search(msg):
        return []
    return touched


def report(rows, checked):
    if not rows:
        print("[check] 逐提交判：%d 个提交，全部通过。" % checked)
        return 0

    print("[check] ❌ 有提交改了流程目录，却没有同步维护方法：")
    for label, files in rows:
        print("  提交 %s" % label)
        for f in files:
            print("    - %s" % f)
    print("")
    print("每条提交都要**自己**满足下面两条之一（下一条提交的免责标签不能替上一条免责）：")
    print("  1) 同一个提交里把步骤 / 命令 / 边界的实际变化写进 %s，并在 §9 追加一条变更记录；" % DOC)
    print("  2) 那个提交的信息里写一行：")
    print("     [no-procedure-change: 说明为什么这次改了代码但流程没变]")
    print("")
    print("只改脚本不改流程，下一个人照着旧步骤做会踩同一个坑。")
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--base", default=None)
    ap.add_argument("--message-file", default=None)
    args = ap.parse_args()

    if args.staged:
        bad = verdict(staged_files(), message(args))
        return report([("(暂存区)", bad)] if bad else [], 1)

    if args.base:
        shas = git("rev-list", "--reverse", "%s..HEAD" % args.base).split()
        if not shas:
            print("[check] 基准 %s 与 HEAD 之间没有提交，通过。" % args.base)
            return 0
        rows = []
        for sha in shas:
            bad = verdict(files_of_commit(sha), git("log", "-1", "--format=%B", sha))
            if bad:
                rows.append((sha[:7], bad))
        return report(rows, len(shas))

    bad = verdict(files_of_commit("HEAD"), message(args))
    return report([("HEAD", bad)] if bad else [], 1)


if __name__ == "__main__":
    sys.exit(main())
