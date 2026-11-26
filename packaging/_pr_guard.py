# -*- coding: utf-8 -*-
"""_pr_guard.py — 给**不懂代码的维护者**看 PR 的第一遍。

用法：
    python packaging/_pr_guard.py --range origin/master..HEAD   # 看本地领先远端的提交
    python packaging/_pr_guard.py --range HEAD~1..HEAD          # 看最近一次提交
    git diff xxx | python packaging/_pr_guard.py                # 读 stdin
    python packaging/_pr_guard.py --file pr.diff                # 读文件

输出：动了几个文件、有没有新增、哪些是脚本、**可疑点在哪一行**。
退出码：`0` 没发现可疑点 ／ `1` 有可疑点（不是错，是"这里要人看"）

## 它不做什么——这一条比功能重要

**它不判断对错，也不代替你看。** 它只做一件事：**把「人该看哪里」从几百行里圈出来。**

为什么需要它：维护者可能不是工程师。要求「看懂每一行 diff」是不现实的，
而放弃审查更危险——那等于把仓库交给任何提交 PR 的人。

所以正确的做法不是让人变专家，而是**把要看的面积缩小到三五行**。

## 可疑点的判据（按"藏东西的常见手法"排）

1. **新增文件** —— 新文件可以藏任何东西，比改旧文件危险
2. **网络请求**（`urllib`／`requests`／`http`）—— 可以把数据带出去
3. **子进程／执行**（`subprocess`／`os.system`／`eval`／`exec`）—— 可以跑任意命令
4. **编码与压缩**（`base64`／`zlib`／`marshal`）—— 可以把东西藏成看不懂的样子
5. **删除文件** —— 删掉证据比加上东西更难发现
6. **写文件到仓库外**（绝对路径、`..`）—— 可以改到别处
7. **`.py` 改动超过 50 行** —— 超过这个量，人看不完
"""

import io
import os
import re
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
        # 吞：输出流不支持 reconfigure 时保留原编码，不让输出配置阻断检查。

SUSPICIOUS = [
    ("网络请求", re.compile(r"\b(urllib|requests\.|http\.client|socket\.|urlopen|httpx)\b")),
    ("执行外部命令", re.compile(r"\b(subprocess\.|os\.system|os\.popen|eval\(|exec\(|__import__)\b")),
    ("编码／压缩（可藏东西）", re.compile(r"\b(base64\.|zlib\.|marshal\.|codecs\.decode|bytes\.fromhex)\b")),
    ("写仓库外路径", re.compile(r"(open\(\s*[\"'][/\\]|open\(\s*[\"']\.\.|shutil\.(rmtree|move))")),
    ("读环境变量（可能取密钥）", re.compile(r"os\.environ(\.get)?\s*[\[\(]")),
    ("脚本里硬编码网址（可能外传）", re.compile(r"https?://")),
]

FILE_RE = re.compile(r"^diff --git a/(.+?) b/(.+)$")
NEW_RE = re.compile(r"^new file mode")
DEL_RE = re.compile(r"^deleted file mode")
HUNK_RE = re.compile(r"^@@ .* \+(\d+)")


def read_diff(argv):
    if "--range" in argv:
        i = argv.index("--range")
        rng = argv[i + 1] if i + 1 < len(argv) else "HEAD~1..HEAD"
        p = subprocess.run(["git", "diff", "--unified=0", rng],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if p.returncode != 0:
            print("[guard] git diff 失败：%s" % (p.stderr or "").strip(), file=sys.stderr)
            return None
        return p.stdout
    if "--file" in argv:
        i = argv.index("--file")
        if i + 1 < len(argv) and os.path.isfile(argv[i + 1]):
            return io.open(argv[i + 1], encoding="utf-8", errors="replace").read()
        print("[guard] --file 指向的文件不存在", file=sys.stderr)
        return None
    if not sys.stdin.isatty():
        # 非 tty 又没给 --range/--file：**不许默默去读 stdin**。
        # 原来的写法在 CI／后台里会一直等管道，60 秒超时——
        # 而"超时"最容易被读成"跑过了"，这是「读不懂就绿」的同一族。
        # 真要从管道喂数据，显式设 _PR_GUARD_ALLOW_STDIN=1，语义是"我确实在喂"。
        if os.environ.get("_PR_GUARD_ALLOW_STDIN") != "1":
            print("[guard] 没有 diff 输入（非 tty 且未给 --range/--file）——"
                  "这一项没查成，退出码 2，不算通过。", file=sys.stderr)
            sys.exit(2)
        return sys.stdin.read()
    return None


def main():
    diff = read_diff(sys.argv)
    if not diff:
        print(__doc__)
        # 2026-11-20：没拿到 diff 不是「没问题」，是**这一项没查成**。
        # 原来 return 0，等于把「没查」说成「通过」——与「超时算未判」同型。
        print("[guard] 没拿到 diff（裸跑）——**这一项没查成，rc=2，不算通过**。"
              "用法：`--range HEAD~1..HEAD` 或 `--file pr.diff`。", file=sys.stderr)
        return 2

    cur = None
    added, removed = 0, 0
    per_added = {}
    files, newfiles, delfiles, pyfiles = [], [], [], []
    hits = []          # (类型, 文件, 行号, 片段)
    newline = 0

    for ln in diff.split("\n"):
        m = FILE_RE.match(ln)
        if m:
            cur = m.group(2)
            files.append(cur)
            if cur.endswith(".py"):
                pyfiles.append(cur)
            continue
        if NEW_RE.match(ln) and cur:
            if cur not in newfiles:      # 同一文件可能有多段 diff（重命名／多次改动），别列两遍
                newfiles.append(cur)
            continue
        if DEL_RE.match(ln) and cur:
            if cur not in delfiles:
                delfiles.append(cur)
            continue
        h = HUNK_RE.match(ln)
        if h:
            newline = int(h.group(1))
            continue
        if not cur:
            continue
        if ln.startswith("+") and not ln.startswith("+++"):
            text = ln[1:]
            added += 1
            per_added[cur] = per_added.get(cur, 0) + 1
            for label, pat in SUSPICIOUS:
                if label.startswith("脚本里硬编码") and not cur.endswith(".py"):
                    continue
                if pat.search(text):
                    hits.append((label, cur, newline, text.strip()[:100]))
                    break
            newline += 1
        elif ln.startswith("-") and not ln.startswith("---"):
            removed += 1

    print("=" * 54)
    print("这个 PR 动了什么")
    print("=" * 54)
    print("  文件 %d 个 ／ 新增 %d 行 ／ 删除 %d 行" % (len(files), added, removed))
    print("  其中脚本（.py）：%d 个" % len(pyfiles))

    if newfiles:
        print("\n  ⚠ 新增文件 %d 个（**新文件最容易藏东西，逐个看**）：" % len(newfiles))
        for f in newfiles:
            print("      + %s" % f)

    if delfiles:
        print("\n  ⚠ 删除文件 %d 个（删证据比加东西更难发现）：" % len(delfiles))
        for f in delfiles:
            print("      − %s" % f)

    big = [f for f in pyfiles if per_added.get(f, 0) > 50]
    if big:
        print("\n  ⚠ 这些脚本改动超过 50 行——**请对方拆小再提**：")
        for f in big:
            print("      %s（+%d 行）" % (f, per_added[f]))

    if hits:
        print("\n" + "=" * 54)
        print("可疑点 %d 处（不是错，是「这里要人看」）" % len(hits))
        print("=" * 54)
        for label, f, n, snip in hits:
            print("  ⚠ [%s] %s:%d" % (label, f, n))
            print("      %s" % snip)
        print("\n  怎么问对方：**这几行是干什么的？为什么需要它？**")
        print("  答不清就关——这不是不信任，是只接受自己能负责的改动。")
        return 1

    print("\n  ✅ 没发现可疑点。")
    print("  ⚠ 但「没发现」不等于「安全」：它只查了七类常见手法，判不了语义。")
    print("     纯文档改动可以放心；动了 .py 的，仍请对方说清「改了什么、为什么」。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
