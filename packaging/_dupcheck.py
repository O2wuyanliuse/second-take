"""同一段文字连贴两遍的检查器 —— 可对任意目录跑。

## 为什么要单独一个文件

2026-11-02（`G-150` / `G-151`）：外部实测在分发包的 `安装.md` 第 3 步看到同一个
`⚠ 改名之后…` 警告**逐字连贴两遍**。成因不是手滑，是**插入式补丁跑了两遍**——
补丁写成「原处 → 原处 ＋ 新增」，于是 `assert 原处 in 文本` 挡不住第二遍：
原处原样还在，替换照样成功，新增就叠一层。**幂等性取决于补丁的形状，不是加断言能保证的。**

当时把判据塞进了 `packaging/_verify_package.py` 的 V8。但那只在**打包时**跑，
覆盖的是「包里的文件」，而且打包不是每天都打。外部实测随即指出：
`发布前检查清单` 里搜不到 V8 的影子——**一个只在打包脚本里存在、文档零提及的检查，
等于只有写它的人会用。**

所以把它抽出来：
  · `_verify_package.py` 调 `scan()`，V8 就是它；
  · 人也可以用一条命令对**整个项目**扫一遍（`发布前检查清单` 里那条就是这个命令）。

一套判据只有一份实现，两处入口 —— 这是本项目对「副本必漂」的一贯处理。

## 判据

连续 ≥3 行内容，在**紧邻位置**原样重复（忽略行首行尾空白，**空行也参与比对**，
两边要一样）。**不设长度上限**。

为什么不是「全文出现两次」：同一个示例块在不同小节各用一次是合理的；
紧邻重复几乎只可能是误操作。

## 判据自己修过一次（2026-11-02）

第一版有两个洞，都是「整段连贴」最常见的形态，**而它两个都报绿**：

    · `HI = 8`：最多只比到 8 行。12 行的一整段贴两遍，k=12 才比得上，
      于是**从头到尾一个候选都不试**，报「干净」。
    · 块里不许有空格行：跨一个空行的一整段（两小段加中间空行）永远凑不出
      连续非空的 k 行，同样报「干净」。

两个洞都不靠读代码发现，是补一个「12 行整段重复」的夹具才炸出来的——
而这条检查存在的理由，恰恰是上一次「查不出就等于没有」。**所以夹具必须有**：
`python packaging/_dupcheck.py --selftest` 那四例（12 行／跨空行／3 行／不相邻）
就是钉这两个洞的钉子。**改判据先跑它，绿了才算改对。**

## 退出码

    0  干净
    1  有重复（列出文件、行号、行数）
    2  没法判（目录不存在／一份 md 或 txt 都没扫到）——**零覆盖不许报绿**
"""

import io
import os
import sys

# ---- 输出编码兜底（2026-11-04，G-299）------------------------------------
# 为什么必须有这几行：Windows 上 stdout 被重定向到文件（`python x.py > out.txt`）
# 或接管道时，Python 走 locale 编码（中文机是 cp936），打印 ✅ ✗ ⚠ 这类符号会抛
# UnicodeEncodeError —— 退出码变成 1，看起来像"脚本坏了"。而在控制台里跑是好的，
# 因为 WriteConsoleW 绕过了编码，**所以本机永远测不出来**。
# 这里按 utf-8 重设，errors="replace" 兜底：宁可打问号，不许整篇不出。
for _std_stream in (sys.stdout, sys.stderr):
    try:
        _std_stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
# ---------------------------------------------------------------------------

TEXT_EXT = (".md", ".txt")
LO = 3          # 最少连续行数
# 曾有一个 `HI = 8`（最多试到 8 行）。它让「12 行的一整段贴两遍」全程一个候选都
# 没试过就报绿——**上限是假绿的来源，不是性能的必需品**（本机 33k 行毫秒级）。
# 现在按「起点行必须相等」先筛候选，再逐行核，不设上限。

# 正文与过程稿的 `.txt` 不扫（2026-11-02，G-151）。
# 第一次对项目根跑、LO=2 时，18 处命中**全在小说正文里**，全是这种：
#     403
#     403
#     403        ← 角色在无意识状态下反复念同一个错误码，是修辞，不是错
# **对作品来说，逐字重复是手法；对规矩文档来说，逐字重复才是事故。**
# 所以按路径排除，并且**把跳过的份数打出来**——静默跳过就是我们自己批过的「空转排除」。
PROSE_DIRS = ("00_原著/", "99_过程稿/")


def _is_prose(rel):
    return rel.endswith(".txt") and rel.startswith(PROSE_DIRS)


def scan(root, lo=LO, skipped=None):
    """返回 [(相对路径, 起始行号(1 起), 重复行数, 首行预览)]。

    `skipped` 传一个 list 进来，会把「按正文规则跳过」的份数记在里面，
    好让调用方打出来——不许静默跳过。
    """
    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames
                             if not d.startswith(".") and d != "__pycache__")
        for fn in sorted(filenames):
            if not fn.lower().endswith(TEXT_EXT):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if _is_prose(rel):
                if skipped is not None:
                    skipped.append(rel)
                continue
            try:
                with io.open(full, encoding="utf-8-sig", errors="replace") as f:
                    lines = f.read().splitlines()
            except OSError:
                continue
            L = [x.strip() for x in lines]        # 去空白只做一次
            n = len(L)
            for i in range(n):
                if not L[i]:                       # 起点必须是内容行
                    continue
                maxk = (n - i) // 2
                for k in range(lo, maxk + 1):
                    # 先拿「首行是否相等」筛候选：绝大多数 k 在这一步就被否掉，
                    # 所以不加长度上限也不会变成平方级的慢。
                    if L[i] != L[i + k]:
                        continue
                    j = 1
                    while j < k and L[i + j] == L[i + k + j]:
                        j += 1
                    if j == k:
                        hits.append((rel, i + 1, k, L[i][:40]))
                        break
    return hits


SELFTEST_CASES = [
    # (文件名, 内容行, 应当报的重复行数, 说明)
    ("十二行整段", ["规则甲：%d" % i for i in range(12)], 12,
     "旧版 `HI=8` 直接漏——这是「整段连贴两遍」最像的样子"),
    ("跨空行一段", ["第一段 1", "第一段 2", "", "第一段 3"], 4,
     "旧版要求块内无空行，跨一个空行就永远凑不出来"),
    ("三行重复", ["甲乙丙", "甲乙丙", "甲乙丙"], 3, "最小形态"),
    ("不相邻", ["甲", "乙", "丙", "丁", "戊", "己", "甲", "乙", "丙"], 0,
     "同一段在别处再出现一次是合理写法，**不报**"),
]


def selftest():
    """判据自证：夹具在临时目录里搭，跑完就删。**不靠人记得**，一条命令就能重放。"""
    import shutil
    import tempfile
    d = tempfile.mkdtemp(prefix="dupcheck_selftest_")
    try:
        want = []
        for name, block, expect, _why in SELFTEST_CASES:
            fn = os.path.join(d, name + ".md")
            body = "\n".join(block)
            if expect:
                body = body + "\n" + body        # 紧邻贴两遍
            io.open(fn, "w", encoding="utf-8", newline="").write(body + "\n")
            want.append((name + ".md", expect))
        got = {}
        for rel, ln, k, head in scan(d):
            got[rel] = max(got.get(rel, 0), k)
        bad = 0
        for rel, expect in want:
            real = got.get(rel, 0)
            ok = (real == expect)
            if not ok:
                bad += 1
            print("  %s %-16s 应报 %d 行 ／ 实报 %d 行 —— %s"
                  % ("✅" if ok else "✗", rel.replace(".md", ""), expect, real,
                     "对" if ok else "判据没抓住它，改判据别改夹具"))
        print("\n判据自证：%d 例，%s" % (len(want), "全过" if not bad else "%d 例不过" % bad))
        return 0 if not bad else 1
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main(argv):
    if "--selftest" in argv[1:]:
        return selftest()
    args = [a for a in argv[1:] if not a.startswith("-")]
    root = args[0] if args else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if not os.path.isdir(root):
        print("[阻断] 没有这个目录：%s" % root)
        print("        路径打错时 os.walk 会**静默扫 0 个文件**，然后报「干净」。")
        print("        本项目栽过一次（`_quote_scan` 那次 0 处），所以这里直接判没法判。")
        return 2

    files = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "__pycache__"]
        files += sum(1 for f in filenames if f.lower().endswith(TEXT_EXT))
    if files == 0:
        print("[阻断] %s 下一份 .md／.txt 都没扫到 —— 这不是「干净」，是「没东西可查」" % root)
        return 2

    skipped = []
    print("扫描 %s（%d 份 md／txt）；判据：连续 %d 行以上内容在紧邻位置原样重复"
          "（空行也算一行，两边要一样；不设长度上限）" % (root, files, LO))
    print("  （正文与过程稿的 .txt 不在此列：那里逐字重复是写法，不是错）")
    hits = scan(root, skipped=skipped)
    if skipped:
        print("  跳过 %d 份正文／过程稿 txt" % len(skipped))
    if not hits:
        # 份数必须说准：跳过的不能算进「扫过」，否则「285 份全扫过」和「跳过 17 份」
        # 会同时出现在屏幕上，两句互相打脸（2026-11-02 第一次跑就撞上了）。
        print("✅ 没有整段重复（实扫 %d 份，跳过 %d 份正文／过程稿）"
              % (files - len(skipped), len(skipped)))
        return 0

    print("✗ 整段连贴两遍 %d 处：" % len(hits))
    for rel, ln, k, head in hits:
        print("   %s:%d 起，%d 行 —— 首行：%s" % (rel, ln, k, head))
    print("   改法：删掉重复的那一遍；如果两处本来就该各留一份（不同小节举例），")
    print("         把其中一份换个说法，别逐字复制。")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
