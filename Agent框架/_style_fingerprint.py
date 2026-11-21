# -*- coding: utf-8 -*-
"""_style_fingerprint.py · 文笔结构指纹（通用层工具）

它干什么
    把「人机味」拆成几项**结构指标**，拿某个作者自己的原文当基线，再拿新稿去比。
    只测结构，不测好坏——**指标全绿也可能写得烂**。

它为什么存在
    作者 2026-10-29 02:20 点破：续写最难的不是逻辑（框架会填），是文笔统一——
    「为了自洽，你写的东西过于方便自己通过；但读者容易一眼人机」。

    "像不像"不能靠 AI 自评（自评必然给自己放水）。所以把判断挪到可数的东西上。
    完整方法论见 `06_数据采集与迭代规范.md` → `四·补一 文笔校准`（**待验**）。

一条硬规矩
    **阈值不许写死。** 每个作者基线不同（实测一位作者「四字整句」0.47，AI 稿普遍 1.8–3.8 倍）。
    所以必须 `--base` 先算这个人的基线，再比。拿固定阈值套所有人，是在制造新的"人机味"。

用法
    python _style_fingerprint.py --base 原文.txt
    python _style_fingerprint.py --base 原文目录/ --check 新稿.md
    python _style_fingerprint.py --base a.txt --base b.txt --check 新稿.md    # 多文件累加
    python _style_fingerprint.py --base 原文.txt --check 新稿.md --json       # 机器可读
"""

import io
import os
import re
import sys
import json
import statistics

EXPLAIN = ["因为", "所以", "也就是说", "这说明", "换句话说", "于是",
           "这意味着", "这样一来", "既然如此", "毕竟"]
ADVERB = re.compile(r"[\u4e00-\u9fa5]{1,2}地(?=[\u4e00-\u9fa5])")
DIALOG = re.compile(r'[\u201c]([^\u201d]*)[\u201d]')
SENT = re.compile(r"[^。！？…\n]+")

TEXT_EXT = (".txt", ".md")


def collect(paths):
    """收文件：给目录就取里面的文本文件"""
    out = []
    for p in paths:
        if os.path.isdir(p):
            for f in sorted(os.listdir(p)):
                if f.lower().endswith(TEXT_EXT):
                    out.append(os.path.join(p, f))
        elif os.path.isfile(p):
            out.append(p)
    return out


def metrics(text):
    n = len(text)
    if n < 500:
        return None
    per_k = 1000.0 / n

    explain = sum(text.count(w) for w in EXPLAIN) * per_k
    adverb = len(ADVERB.findall(text)) * per_k

    # 四字整句：整句正好四个汉字。宁可少算，不虚高
    four = 0
    for seg in SENT.findall(text):
        if len(re.sub(r"[^\u4e00-\u9fa5]", "", seg.strip())) == 4:
            four += 1
    four *= per_k

    dlg = sum(len(m) for m in DIALOG.findall(text))
    dlg_ratio = dlg / float(n) * 100

    sents = [s.strip() for s in SENT.findall(text) if len(s.strip()) > 3]
    lens = [len(s) for s in sents]
    if not lens:
        return None
    avg = statistics.mean(lens)
    cv = statistics.pstdev(lens) / avg if avg else 0
    short = sum(1 for x in lens if x <= 12) / float(len(lens)) * 100

    paras = [p for p in text.split("\n") if p.strip()]
    plen = statistics.mean(len(p) for p in paras) if paras else 0

    return {
        "解释性连词": round(explain, 2),
        "四字整句": round(four, 2),
        "副词地": round(adverb, 2),
        "句长变异": round(cv, 2),
        "对话占比": round(dlg_ratio, 1),
        "短句率": round(short, 1),
        "段均长": round(plen, 1),
    }


# 偏离到多少算"值得看一眼"。**这些不是判定线，是提示线**
WARN = {
    "解释性连词": ("high", 1.6, "偏高——可能在给设定做解释（\"方便自己通过\"的头号特征）"),
    "四字整句":   ("high", 2.0, "偏高——成语/四字对仗堆叠，读着顺但假"),
    "副词地":     ("low", 0.5, "偏低——少了\"缓缓地／轻轻地\"这类动作颗粒"),
    "句长变异":   ("low", 0.7, "偏低——句子太匀，节奏平"),
    "短句率":     ("low", 0.6, "偏低——少了短促的断句，读起来不透气"),
}


def main():
    argv = sys.argv
    if "--base" not in argv:
        print(__doc__)
        return 1

    bases, checks = [], []
    cur = None
    for a in argv[1:]:
        if a == "--base":
            cur = bases
        elif a == "--check":
            cur = checks
        elif a.startswith("--"):
            cur = None
        elif cur is not None:
            cur.append(a)

    bfiles = collect(bases)
    if not bfiles:
        print("❌ 没找到基线文件")
        return 1
    btext = "\n".join(io.open(f, encoding="utf-8", errors="ignore").read() for f in bfiles)
    base = metrics(btext)
    if not base:
        print("❌ 基线文本太短（至少 500 字才稳）")
        return 1

    result = {"base_files": [os.path.basename(f) for f in bfiles],
              "base_chars": len(btext), "baseline": base}

    ctext, cname = None, None
    cfiles = collect(checks)
    if cfiles:
        ctext = "\n".join(io.open(f, encoding="utf-8", errors="ignore").read() for f in cfiles)
        cname = "、".join(os.path.basename(f) for f in cfiles)

    if "--json" in argv:
        if ctext:
            m = metrics(ctext)
            result["check"] = {"files": [os.path.basename(f) for f in cfiles], "metrics": m}
            if m:
                result["ratio"] = {k: round(m[k] / base[k], 2) for k in base if base[k]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print("文笔结构指纹 · 基线")
    print("  来源：%s（%d 字）" % ("、".join(result["base_files"]), len(btext)))
    print()
    for k, v in base.items():
        unit = "%" if k in ("对话占比", "短句率") else ""
        print("    %-8s %7.2f%s" % (k, v, unit))
    print()

    if not ctext:
        print("  （加 --check <新稿> 就能拿它跟基线比）")
        return 0

    m = metrics(ctext)
    if not m:
        print("❌ 对比稿太短")
        return 1
    print("对比稿：%s（%d 字）" % (cname, len(ctext)))
    print()
    print("  指标        基线      新稿      倍数")
    flags = []
    for k in base:
        if not base[k]:
            continue
        r = m[k] / base[k]
        print("    %-8s %8.2f %9.2f %9.2fx" % (k, base[k], m[k], r))
        if k in WARN:
            side, thr, why = WARN[k]
            if (side == "high" and r >= thr) or (side == "low" and r <= thr):
                flags.append("    ⚠ %s %.2fx —— %s" % (k, r, why))
    print()
    if flags:
        print("值得看一眼的地方：")
        for f in flags:
            print(f)
        print()
        print("  ⚠ 这些是**提示**，不是判错。文体不同（纯心理／纯对话）会天然偏离。")
    else:
        print("  没有明显偏离。")
    print()
    print("  ⚠ 指标绿了不等于写得好。这只拦\"一眼人机\"，拦不住\"平庸\"。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
