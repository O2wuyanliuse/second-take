# -*- coding: utf-8 -*-
"""_quote_scan.py — 查「分发包里有没有正文原句」，并卡住上限。

退出码：0 在限内／1 超限／2 没得查（目录空或原文缺失，**不是通过**）

完整说明：docs/maintain/代码内长文档/packaging/_quote_scan.py.md
"""

import io
import os
import re
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
        pass  # 吞：输出流不支持 reconfigure 时保留原编码，不让输出配置阻断检查。
# ---------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ── 上限（改这里必须写明理由）─────────────────────────────
# 首次测量（2026-11-02，包内 76 个文件）：
#   ≥10 字 232 处，但其中 188 处正好是 10 字 —— 那是常用词组的巧合，不是引文。
#   ≥15 字 20 处 / 386 字 / 单处最长 29 字，集中在两份「标准件」的教学举例里。
# 所以：
#   计数门槛 15 字 —— 低于它的不算引文，只作参考列出。
#   单处 30 字、合计 450 字 —— 比现状（29／386）留一点余量，但**不许翻倍**。
#   真要放宽，先改这里并写清理由；那比悄悄变多好。
MAX_RUN = 30
MAX_TOTAL = 450
MIN_RUN = 15      # 低于这个长度不计入超限，只列为「短片段／巧合」
MIN_FILES = 20    # 扫到的文件数低于这个，判「没真扫」，不算通过

# ── 匹配参数 ────────────────────────────────────────────
K = 10            # 种子长度。10 个连续汉字雷同，人工写成一样基本不可能
SCAN_EXT = (".md", ".py", ".html", ".txt", "pre-commit")
SRC_DIRS = ["00_原著", "00_原著/_原始归档"]
SKIP_SRC = ("_anchor_baseline",)


def norm(t):
    """去掉一切空白（含不换行空格 \\xa0 ／ 全角空格）。原文里这三样都有，
    不去掉就会把「同一句话」判成「不一样」。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", t)


def load_sources():
    """载入原文池。返回 [(路径, 归一化文本)]。"""
    out = []
    for d in SRC_DIRS:
        p = os.path.join(ROOT, d)
        if not os.path.isdir(p):
            continue
        for f in os.listdir(p):
            if f.startswith("."):
                continue
            fp = os.path.join(p, f)
            if not os.path.isfile(fp):
                continue
            if not (f.endswith(".txt") or f == "第9章"):
                continue
            if any(s in f for s in SKIP_SRC):
                continue
            try:
                out.append((os.path.relpath(fp, ROOT),
                            norm(io.open(fp, encoding="utf-8", errors="ignore").read())))
            except Exception as e:
                raise RuntimeError("读取待扫文件失败: %s" % fp) from e
    return out


def build_index(srcs):
    grams, blob = set(), []
    for _, s in srcs:
        for i in range(len(s) - K + 1):
            grams.add(s[i:i + K])
        blob.append(s)
    # 用 \x00 隔开：正文里不会有这个字符，跨文件拼接处不会造成假命中
    return grams, "\x00".join(blob)


def prose_ok(s):
    """只认「像正文」的片段。
    2026-11-02 抓到两类误判：`>**建立**：2026-10-29`、`2026-10-292` ——
    那是中间稿文件头的日期，跟正文撞了，不是引文。
    判据：汉字占比 ≥ 0.65 且汉字数 ≥ 10。"""
    han = sum(1 for ch in s if "\u4e00" <= ch <= "\u9fff")
    return han >= 10 and han / max(1, len(s)) >= 0.65


def scan(target, grams, blob, srcs):
    """返回 (命中列表[(相对路径, 片段, 原文文件)], 扫描文件数)。"""
    hits, scanned = [], 0
    for dp, _, fs in os.walk(target):
        for fn in fs:
            if not fn.endswith(SCAN_EXT):
                continue
            fp = os.path.join(dp, fn)
            scanned += 1
            try:
                pkg = norm(io.open(fp, encoding="utf-8", errors="ignore").read())
            except Exception:
                continue  # 吞：单文件读不到时跳过，继续扫描其余命中。
            i, last_end = 0, -1
            n = len(pkg)
            while i <= n - K:
                if pkg[i:i + K] not in grams:
                    i += 1
                    continue
                # 向后扩展
                end = i + K
                while end < n and blob.find(pkg[i:end + 1]) >= 0:
                    end += 1
                # 向前扩展
                start = i
                while start > 0 and blob.find(pkg[start - 1:end]) >= 0:
                    start -= 1
                if start >= last_end:
                    piece = pkg[start:end]
                    if prose_ok(piece):
                        owner = next((f for f, s in srcs if piece in s), "?")
                        hits.append((os.path.relpath(fp, target), piece, owner))
                        last_end = end
                i = max(end, i + 1)
    return hits, scanned


def report(hits, scanned, target):
    from collections import Counter

    big = [h for h in hits if len(h[1]) >= MIN_RUN]      # 算引文
    small = [h for h in hits if len(h[1]) < MIN_RUN]     # 短片段／巧合
    total = sum(len(h[1]) for h in big)
    longest = max((len(h[1]) for h in big), default=0)

    print("[scope] 目标目录：%s" % target)
    print("[scope] 扫描文件 %d 个；判据：连续 %d 个汉字与原文逐字相同、且像正文" % (scanned, K))
    print("[scope] 查不了：改过字的意译（换了词就查不出）、跨文件拼出来的句子")

    print("\n≥%d 字（计为引文）：%d 处 / %d 字，单处最长 %d 字"
          % (MIN_RUN, len(big), total, longest))
    print("<%d 字（短片段／词组合，只列不判）：%d 处 / %d 字"
          % (MIN_RUN, len(small), sum(len(h[1]) for h in small)))

    if big:
        print("\n%-52s %s" % ("文件", "处数 / 字数"))
        print("-" * 72)
        c = Counter(h[0] for h in big)
        for k in sorted(c, key=lambda x: -sum(len(h[1]) for h in big if h[0] == x)):
            print("%-52s %2d 处 / %3d 字"
                  % (k[:52], c[k], sum(len(h[1]) for h in big if h[0] == k)))

        print("\n全部引文（按长度）：")
        for rel, piece, owner in sorted(big, key=lambda x: -len(x[1])):
            print("  %-38s %2d字  %s" % (rel[:38], len(piece), piece[:52]))

    ok = True
    if longest > MAX_RUN:
        print("\n✗ 单处最长 %d 字，超上限 %d" % (longest, MAX_RUN))
        ok = False
    if total > MAX_TOTAL:
        print("\n✗ 合计 %d 字，超上限 %d" % (total, MAX_TOTAL))
        ok = False
    return ok


def strip(target, grams, blob, srcs):
    """就地替换命中的原文片段为标记。**默认不用**，因为会毁掉举例的可读性。"""
    changed = 0
    for dp, _, fs in os.walk(target):
        for fn in fs:
            if not fn.endswith((".md", ".py")):
                continue
            fp = os.path.join(dp, fn)
            raw = io.open(fp, encoding="utf-8", errors="ignore").read()
            new = raw
            for _, piece, _ in sorted(scan_file(fp, grams, blob, srcs),
                                      key=lambda x: -len(x[0])):
                new = new.replace(piece, "〔原文引文·已删〕")
            if new != raw:
                io.open(fp, "w", encoding="utf-8", newline="").write(new)
                changed += 1
                print("  已替换：%s" % os.path.relpath(fp, target))
    print("共改动 %d 个文件" % changed)


def scan_file(fp, grams, blob, srcs):
    """单文件扫描，供 --strip 用。返回 [(片段, 原文文件)]。"""
    out = []
    try:
        pkg = norm(io.open(fp, encoding="utf-8", errors="ignore").read())
    except Exception:
        return out
    i, last_end, n = 0, -1, len(pkg)
    while i <= n - K:
        if pkg[i:i + K] not in grams:
            i += 1
            continue
        end = i + K
        while end < n and blob.find(pkg[i:end + 1]) >= 0:
            end += 1
        start = i
        while start > 0 and blob.find(pkg[start - 1:end]) >= 0:
            start -= 1
        if start >= last_end:
            out.append((pkg[start:end], "?"))
            last_end = end
        i = max(end, i + 1)
    return out


def selftest():
    """反向验：造一个必中的样本，抓不到就是脚本坏了。
    **不做这一步，跑出来的「0 处」没有任何意义。**"""
    srcs = load_sources()
    if not srcs:
        print("✗ 原文池为空，无法自检")
        return 2
    grams, blob = build_index(srcs)
    # 从原文中间截 30 字当探针
    probe_src = max(srcs, key=lambda x: len(x[1]))[1]
    probe = probe_src[len(probe_src) // 2: len(probe_src) // 2 + 30]
    if blob.find(probe) < 0:
        print("✗ 探针在原文池里都找不到，索引建错了")
        return 2
    if probe[:K] not in grams:
        print("✗ 探针的 %d-gram 没进索引" % K)
        return 2
    # 再造一个「改了一个字」的对照，必须**查不到**
    mutated = probe[:10] + "改" + probe[11:]
    fake_hit = blob.find(mutated) >= 0
    print("自检① 探针原样 → 命中判定：%s（应 True）" % (blob.find(probe) >= 0))
    print("自检② 改一个字的探针 → 命中判定：%s（应 False）" % fake_hit)
    ok = blob.find(probe) >= 0 and not fake_hit
    print("自检结论：%s" % ("✅ 检测器有效" if ok else "✗ 检测器坏了"))
    return 0 if ok else 1


def main():
    args = sys.argv[1:]
    if "--selftest" in args:
        sys.exit(selftest())

    do_strip = "--strip" in args
    args = [a for a in args if a != "--strip"]
    if not args:
        print(__doc__)
        sys.exit(2)

    target = os.path.abspath(args[0])
    # 防线 1：目录不存在，不许装作通过
    if not os.path.isdir(target):
        print("✗ 目标目录不存在：%s" % target)
        print("  （注意：Git Bash 的 /tmp 与 Python 的 /tmp 不是同一个位置，用绝对路径）")
        sys.exit(2)

    srcs = load_sources()
    # 防线 3：没有尺子，量出来的 0 不算数
    if not srcs:
        print("✗ 找不到原文文件（00_原著/*.txt）。没有原文就无法判残留，不是通过。")
        sys.exit(2)

    grams, blob = build_index(srcs)
    print("[scope] 原文池 %d 份 / %d 字" % (len(srcs), sum(len(s) for _, s in srcs)))

    if do_strip:
        strip(target, grams, blob, srcs)
    hits, scanned = scan(target, grams, blob, srcs)

    # 防线 2：没真扫到东西，不算通过
    if scanned < MIN_FILES:
        print("\n✗ 只扫到 %d 个文件（低于 %d）。这大概率是路径错了，不是没残留。"
              % (scanned, MIN_FILES))
        sys.exit(2)

    ok = report(hits, scanned, target)
    print("\n%s" % ("✅ 在限内（单处 ≤ %d 字，合计 ≤ %d 字）" % (MAX_RUN, MAX_TOTAL)
                    if ok else "✗ 超限"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
