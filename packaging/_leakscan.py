# -*- coding: utf-8 -*-
"""_leakscan.py — 反向泄漏扫描：拿**项目私有词表**去扫**这个通用库**。

用法：
    python packaging/_leakscan.py --words <词表.txt> [--words <又一份.txt>] [--no-history]
    LEAK_WORDS=<词表1>;<词表2> python packaging/_leakscan.py

退出码：`0` 干净 ／ `1` 有命中 ／ `2` **没给词表（没查成，不算通过）**

## 它跟 `_sync_check.py` 的泄漏闸有什么不同

那个闸查的是「**私库要送出去的那份**里有没有专名」——有源码，有词表，有靶子。
这个查的是「**通用库自己**里有没有残留」：注释里的举例、docstring 里的事故复盘、
正则里写死的本机目录名……**这些不是从私库搬过来的，是自己长出来的**，所以那个闸看不见。

## 为什么词表必须从外面给

通用库不含项目内容 → 它**没有**词表，这是设计。所以反向扫描只能由项目侧发起：
词表留在私库，脚本留在通用库，两边都不越界。脚本自己带一份词表，就等于把项目搬进来了。

## 为什么默认连历史一起扫

文件改掉 ≠ 泄漏消失。被改的那行还躺在上一个提交里，仓库一转公开，`git log -p` 就能看。
**当前文件是绿的、历史是红的，整体就是红的。**

## 已知边界

- 只扫**被跟踪**的文件（工作区）与**全部 blob**（历史）。未跟踪的临时文件不扫——它们不进仓库。
- 二进制文件按字节扫，只在命中时提示「二进制」，不打印上下文。
- 大小写不敏感：同一个词的大小写变体算同一个词。
- 不判断语义。命中一处报一处，是不是真泄漏由人定。**宁可多报。**
"""

import io
import os
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
        # 吞：输出流不支持 reconfigure 时保留原编码，不让输出配置阻断检查。

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 这三份文件的内容**就是待扫的词本身**（`占位词=替换词` 这种行），
# 扫它们等于拿尺子去量尺子——样例词表必然自命中，红了也读不出信息。
# 跳过，但**必须出声**（见 main）：静默跳过就是第二个「读不懂就绿」。
WORDLIST_BASENAMES = ("脱敏词表_样例.txt", "脱敏补充词.txt", "leak_allow.txt",
                      "leak_known_history.txt", "public_denylist.txt")
_skipped = []

# 词表里这些段不扫：它们的值是「替换成什么」，不是「要查什么」
SKIP_SECTIONS = ("替换", "映射", "说明")


def die(msg, code=2):
    print("[leak] ⛔ " + msg, file=sys.stderr)
    sys.exit(code)


def load_words(paths):
    """读一份或多份词表。支持两种格式：
        A. `[类别]` 分段，一行一个词（`包/脱钩词表_项目.txt`）
        B. `原词=替换`，一行一条（`包/脱敏补充词.txt`）
    两种混在一份里也认。返回 [(词, 来源文件)]，按词去重、长的在前。
    """
    seen, out = set(), []
    for p in paths:
        if not os.path.isfile(p):
            die("词表不存在：%s" % p)
        section = ""
        with io.open(p, encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                if s.startswith("[") and s.endswith("]"):
                    section = s[1:-1]
                    continue
                if any(k in section for k in SKIP_SECTIONS):
                    continue
                w = s.split("=", 1)[0].strip() if "=" in s else s
                if len(w) < 2:
                    continue
                k = w.lower()
                if k in seen:
                    continue
                seen.add(k)
                out.append((w, os.path.basename(p)))
    # 长的先扫：长词命中时，不必再报一次它的子串（否则一处泄漏报两遍）
    out.sort(key=lambda x: len(x[0]), reverse=True)
    return out


def load_allow():
    """读 `packaging/leak_allow.txt`。没写理由的行不算（返回 (白名单, 缺理由的词)）。"""
    path = os.path.join(HERE, "leak_allow.txt")
    allow, noreason = {}, []
    if not os.path.isfile(path):
        return allow, noreason
    with io.open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            w, why = s.split("=", 1)
            w, why = w.strip(), why.strip()
            if len(w) < 2:
                continue
            if not why:
                noreason.append(w)
                continue
            allow[w.lower()] = why
    return allow, noreason


def tracked_files():
    r = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        die("`git ls-files` 失败——这里不是 git 仓库？\n%s"
            % r.stderr.decode("utf-8", "replace"))
    return [x for x in r.stdout.decode("utf-8", "replace").split("\0") if x]


KNOWN_PATH = os.path.join(HERE, "leak_known_history.txt")


def load_known_history():
    """读「已知历史残留」登记。返回 ({(词, 提交前缀): 理由}, 没写理由的行)。

    跟 `leak_allow.txt` 的分工：
      · allow：**这个词在通用层是正当用法**（如中文常用比喻）→ 全库永久豁免
      · 本文件：**这处命中躺在某个旧提交里，已经决定不重写历史** → 只对那个提交前缀生效

    同一个词在**新提交**里再出现，本文件不管，照样红。**它不是豁免，是记账。**
    没有这一层，已登记的旧残留每次扫都红——红变日常，真泄漏那天就没人看了。
    """
    known, noreason = {}, []
    if not os.path.isfile(KNOWN_PATH):
        return known, noreason
    with io.open(KNOWN_PATH, encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            parts = [x.strip() for x in s.split("|")]
            if len(parts) < 2:
                continue
            why = parts[2] if len(parts) > 2 else ""
            if not why:
                noreason.append(s)
                continue
            known[(parts[0].lower(), parts[1])] = why
    return known, noreason


def scan_worktree(words):
    """扫当前被跟踪的文件。返回 [(词, 位置, 行号, 上下文)]。"""
    hits = []
    for rel in tracked_files():
        if os.path.basename(rel) in WORDLIST_BASENAMES:
            _skipped.append(rel)
            continue
        full = os.path.join(ROOT, rel)
        try:
            with io.open(full, "rb") as f:
                raw = f.read()
        except OSError:
            continue
        low = raw.lower()
        if not any(w.lower().encode("utf-8") in low for w, _ in words):
            continue
        if b"\0" in raw[:4096]:
            for w, _ in words:
                if w.lower().encode("utf-8") in low:
                    hits.append((w, "工作区", 0, "%s（二进制）" % rel))
            continue
        text = raw.decode("utf-8", "replace")
        lines = text.splitlines()
        for w, _ in words:
            lw = w.lower()
            for i, line in enumerate(lines, 1):
                if lw in line.lower():
                    ctx = line.strip()
                    if len(ctx) > 120:
                        k = ctx.lower().find(lw)
                        a = max(0, k - 50)
                        ctx = "…" + ctx[a:a + 110] + "…"
                    hits.append((w, "工作区", i, "%s:%d  %s" % (rel, i, ctx)))
    return hits


def all_blobs():
    """全部历史里出现过的 blob：(sha, 最早见到的路径)。"""
    r = subprocess.run(["git", "rev-list", "--objects", "--all"], cwd=ROOT,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        die("`git rev-list --objects --all` 失败\n%s"
            % r.stderr.decode("utf-8", "replace"))
    seen, order = {}, []
    for line in r.stdout.decode("utf-8", "replace").splitlines():
        sha, _, path = line.partition(" ")
        if sha not in seen:
            seen[sha] = path or "(无路径)"
            order.append(sha)
    return [(s, seen[s]) for s in order]


def blob_meta(shas):
    """一次问清 type/size：返回 {sha: (type, size)}。"""
    if not shas:
        return {}
    p = subprocess.Popen(["git", "cat-file", "--batch-check"], cwd=ROOT,
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    out, _ = p.communicate(("\n".join(shas) + "\n").encode())
    meta = {}
    for line in out.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) >= 3:
            meta[parts[0]] = (parts[1], int(parts[2]))
    return meta


def blob_texts(shas):
    """按顺序吐出 (sha, bytes)。"""
    p = subprocess.Popen(["git", "cat-file", "--batch"], cwd=ROOT,
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    for sha in shas:
        p.stdin.write((sha + "\n").encode())
        p.stdin.flush()
        header = p.stdout.readline()
        if not header:
            break
        parts = header.split()
        if len(parts) < 3 or parts[1] != b"blob":
            if len(parts) >= 2 and parts[1] == b"missing":
                continue
            # commit / tree：header 后面没有紧跟内容，直接跳过
            if len(parts) >= 3 and parts[1] != b"missing":
                try:
                    p.stdout.read(int(parts[2]))
                except Exception as e:
                    raise RuntimeError("读取 git blob 内容失败") from e
                p.stdout.read(1)
            continue
        size = int(parts[2])
        data = p.stdout.read(size)
        p.stdout.read(1)
        yield sha, data
    p.stdin.close()
    p.wait()


def scan_history(words):
    objs = all_blobs()
    meta = blob_meta([s for s, _ in objs])
    blobs = [(s, p) for s, p in objs if meta.get(s, ("", 0))[0] == "blob"]
    pathof = dict(blobs)
    hits, seen_pairs = [], set()

    for sha, data in blob_texts([s for s, _ in blobs]):
        path = pathof.get(sha, "?")
        if os.path.basename(path) in WORDLIST_BASENAMES:
            _skipped.append(path)
            continue
        low = data.lower()
        for w, _ in words:
            lw = w.lower()
            if lw.encode("utf-8") not in low:
                continue
            key = (w, sha)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            if b"\0" in data[:4096]:
                hits.append((w, sha[:7], 0, "%s（二进制）" % path))
                continue
            text = data.decode("utf-8", "replace")
            for i, line in enumerate(text.splitlines(), 1):
                if lw in line.lower():
                    ctx = line.strip()
                    if len(ctx) > 120:
                        k = ctx.lower().find(lw)
                        a = max(0, k - 50)
                        ctx = "…" + ctx[a:a + 110] + "…"
                    hits.append((w, sha[:7], i, "%s:%d  %s" % (path, i, ctx)))
                    break
    return hits


def main():
    args = sys.argv[1:]
    if "-h" in args or "--help" in args:
        print(__doc__)
        return 0

    word_paths, do_history, strict = [], True, False
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--words":
            i += 1
            if i >= len(args):
                die("`--words` 后面要跟文件路径")
            word_paths.append(args[i])
        elif a.startswith("--words="):
            word_paths.append(a.split("=", 1)[1])
        elif a == "--deny":
            i += 1
            if i >= len(args):
                die("`--deny` 后面要跟文件路径")
            word_paths.append(args[i])
        elif a.startswith("--deny="):
            word_paths.append(a.split("=", 1)[1])
        elif a == "--no-history":
            do_history = False
        elif a == "--strict":
            strict = True
        elif a in ("--all",):
            pass
        else:
            die("不认识的参数：%s（只认 --words / --deny / --no-history / --strict）" % a)
        i += 1

    if not word_paths:
        env = os.environ.get("LEAK_WORDS", "")
        word_paths = [p for p in env.replace(",", ";").split(";") if p.strip()]

    if not word_paths:
        # 退出码 2 不是「干净」，是「这一项没查成」。门禁与发布清单都按这个判。
        die("没给词表——**这一项没查成，不算通过。**\n"
            "       指定法：`--words <私库的词表.txt>` 或设 `LEAK_WORDS`。\n"
            "       通用库自己不带词表（这是设计，不是缺文件）："
            "项目侧发起，才知道该查什么。")

    words = load_words(word_paths)
    if not words:
        die("词表读出来是空的：%s → 空词表会让任何仓库都显示「干净」。"
            % "、".join(word_paths))

    print("[leak] 通用库：%s" % ROOT)
    print("[leak] 词表　：%d 个词，来自 %s"
          % (len(words), "、".join(sorted({s for _, s in words}))))

    allow, noreason = load_allow()
    known_hist, known_noreason = load_known_history()

    def split(hs):
        """(豁免的, 已登记的旧残留, 待处理的)。先分再报数——否则「工作区 11 处」会把人吓一跳，
        而那 11 处全是同一句话里的工具名。**数字要能读，不然红就白红了。**"""
        ax, kx, rest = [], [], []
        for h in hs:
            if h[0].lower() in allow:
                ax.append(h)
            elif (h[0].lower(), h[1]) in known_hist:
                kx.append(h)
            else:
                rest.append(h)
        return ax, kx, rest

    hits = scan_worktree(words)
    pw, kw, rw = split(hits)
    print("[leak] 工作区：%d 处（豁免 %d ／ 已登记 %d ／ 待处理 %d）"
          % (len(hits), len(pw), len(kw), len(rw)))

    hist = []
    if do_history:
        hist = scan_history(words)
        ph, kh, rh = split(hist)
        print("[leak] 历史　：%d 处（豁免 %d ／ 已登记 %d ／ 待处理 %d）—— 全部提交的全部 blob"
              % (len(hist), len(ph), len(kh), len(rh)))
    else:
        ph, kh, rh = [], [], []
        print("[leak] 历史　：已跳过（`--no-history`）—— **这一半没查**")

    if _skipped:
        # 去重后再数：同一份词表在工作区和历史里各命中一次，按次数报会把 2 说成 4。
        uniq = sorted(set(_skipped))
        print("[leak] 跳过　：%d 个词表文件（它们的内容就是待扫的词本身）：%s"
              % (len(uniq), "、".join(uniq)))

    allhits = rw + rh
    pardoned = pw + ph
    known_all = kw + kh

    if noreason:
        print("\n[leak] ⚠️ `leak_allow.txt` 里这几行**没写理由，不算豁免**：%s"
              % "、".join(noreason))
    if known_noreason:
        print("\n[leak] ⚠️ `leak_known_history.txt` 里这几行**没写理由，不算登记**：%s"
              % "；".join(known_noreason))
    if pardoned:
        print("[leak] 豁免　：%d 处（%s）—— 理由见 `packaging/leak_allow.txt`"
              % (len(pardoned), "、".join(sorted({h[0] for h in pardoned}))))
    if known_all:
        print("[leak] 已登记：%d 处（旧提交·决定不重写历史）—— 见 `packaging/leak_known_history.txt`"
              % len(known_all))

    if not allhits:
        if strict and not do_history:
            print("\n[leak] ❌ --strict：历史没扫（`--no-history`）——"
                  "**这一半没查，不算干净**。本库的哲学：跳过不算绿。")
            return 1
        print("\n[leak] ✅ 干净：扣掉豁免后，工作区与历史都没有命中。")
        return 0

    print("\n[leak] ❌ 有命中：\n")
    byword = {}
    for w, where, _, detail in allhits:
        byword.setdefault(w, []).append((where, detail))
    for w in sorted(byword, key=lambda x: -len(x)):
        rows = byword[w]
        print("  「%s」 %d 处" % (w, len(rows)))
        for where, detail in rows[:6]:
            print("     [%s] %s" % (where, detail))
        if len(rows) > 6:
            print("     …… 另 %d 处" % (len(rows) - 6))
        print("")

    print("怎么修：")
    print("  1. 工作区命中 → 直接改，改完再跑一次。")
    print("  2. 只有历史命中 → **改文件不够**，那一行还在旧提交里。")
    print("     要么 `git filter-repo` 精确改写，要么重建初始提交（老办法）。")
    print("  3. 判断是**真泄漏**还是**误报**：确实是通用示例（不含具体人／组织／路径），")
    print("     就把该词从词表里拿掉，别把库改坏。")
    print("")
    print("[leak] 结论：**红。转公开之前必须清零。**")
    return 1


if __name__ == "__main__":
    sys.exit(main())
