# -*- coding: utf-8 -*-
"""_e0.py · 投喂登记（E0·1–E0·3）有没有做过

退出码（与全库同语义）
    0 ＝ 三样齐、有数据行
    1 ＝ 有 `00_原著/` 但台账缺、或三样缺、或没有数据行  ← 阻断：分格/定调不许开始
    2 ＝ 还没有 `00_原著/`  ← 提示（本库是方法仓，或项目还没建档）。**提示不是通过。**

用法
    python gate/_e0.py            # 查本仓库
    python gate/_e0.py --gate     # 同上（门禁调用口径，输出更短）
    python gate/_e0.py --self     # 自测：五种形态，全在内存里造，不写盘

完整说明：docs/maintain/代码内长文档/gate/_e0.py.md
"""

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass  # 吞：输出流不支持 reconfigure 时保留原编码，不让输出配置阻断检查。

# 三样要素的识别词。**只认这些词，不认列序**——各项目表头写法不同，绑列序等于绑项目。
RE_WHERE = re.compile(r"原文.{0,6}(在哪|位置|来源|出处)|文件路径|投喂来源")
RE_KIND = re.compile(r"文体|正文.{0,4}(还是|或).{0,4}设定|设定相关")
RE_RELA = re.compile(r"与原著|关系|原创|他人作品|同人")

LEDGER_GLOB = re.compile(r"投喂.*台账.*\.md$|投喂.*授权.*\.md$")


def find_ledger(gdir):
    """在 00_原著/ 下找投喂台账。找得到返回文件名，找不到 None。"""
    if not os.path.isdir(gdir):
        return None
    cands = [f for f in os.listdir(gdir) if LEDGER_GLOB.search(f)]
    if not cands:
        return None
    # 有多个时取修改时间最新的那份（改名/升版不会让闸失灵）
    cands.sort(key=lambda f: os.path.getmtime(os.path.join(gdir, f)), reverse=True)
    return cands[0]


def data_rows(txt):
    """台账里「真的填了字」的行。

    两条排除，缺一条就假绿（2026-11-20 自测当场抓到过）：
      1. `|---|---|` 分隔行；
      2. **表头行**——它紧跟着分隔行，而且三格都填着列名（「原文在哪／文体／关系」），
         非空格数一样是 3。只按「非空格 ≥3」判，表头会被当成一条数据，于是
         「只有表头」那种形态直接判绿。
    """
    lines = [l.strip() for l in txt.split("\n")]
    rows = []
    for i, s in enumerate(lines):
        if not s.startswith("|"):
            continue
        if re.match(r"^\|[\s:\-|]+\|?$", s):      # 分隔行
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if re.match(r"^\|[\s:\-|]+\|?$", nxt):      # 下一行是分隔行 → 本行是表头
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        nonempty = [c for c in cells if c and not re.match(r"^[-—\s]+$", c)]
        if len(nonempty) >= 3:
            rows.append(s)
    return rows


def judge_core(has_gdir, ledger_name, txt):
    """纯判定：不碰磁盘。`--self` 与 `judge()` 共用这一份，判定只有一处。

    分成纯函数是有理由的：自测要造「只有表头」「缺两栏」这些形态，
    真去写临时目录既慢又会被沙箱拦；但判定逻辑绝不能因此复制两份——复制就会漂。
    """
    if not has_gdir:
        return 2, "还没有 `00_原著/` —— E0 投喂登记没建", [
            "这不是错误，但它是冷启动那次跳过 E0 的同一个缺口。",
            "开工前先建 `00_原著/投喂与授权台账.md`，记三样：原文在哪 / 文体（正文·设定·混合）/ 与原著的关系（原创·他人作品）。",
            "没有这三样，后面每一格都答不出「依据哪一份原文」。",
        ]

    if not ledger_name:
        return 1, "有 `00_原著/`，但找不到投喂台账", [
            "期望：`00_原著/投喂与授权台账.md`（文件名含「投喂」与「台账」即可）。",
            "E0·1–E0·3 的产物就是这一行登记——没有它，E1 的裁决没有基底，E2 的分格没有依据。",
        ]

    txt = txt or ""
    miss = []
    if not RE_WHERE.search(txt):
        miss.append("原文在哪（来源/出处/路径）")
    if not RE_KIND.search(txt):
        miss.append("文体（正文 / 设定相关 / 混合）")
    if not RE_RELA.search(txt):
        miss.append("与原著的关系（原创 / 他人作品）")
    if miss:
        return 1, "投喂台账缺要素：%s" % "／".join(miss), [
            "文件：`00_原著/%s`" % ledger_name,
            "三样要素缺任何一样，E0 都算没做完——不是「写得不好」，是「没有记录」。",
        ]

    rows = data_rows(txt)
    if not rows:
        return 1, "投喂台账只有表头，没有数据行", [
            "文件：`00_原著/%s`" % ledger_name,
            "表头建好了，但这一份投喂没登记——等于没做。",
        ]

    return 0, "投喂登记在（%d 行）" % len(rows), []


def judge(gdir):
    """去盘上取三样东西，判定交给 `judge_core`。"""
    has = os.path.isdir(gdir)
    name = find_ledger(gdir) if has else None
    txt = ""
    if name:
        try:
            txt = io.open(os.path.join(gdir, name), encoding="utf-8", errors="replace").read()
        except Exception as exc:  # noqa: BLE001
            return 1, "投喂台账读不出：%s" % exc, ["文件：`00_原著/%s`" % name]
    return judge_core(has, name, txt)


# ---------------------------------------------------------------- 自测 ----
CASES = [
    ("无 00_原著", (False, None, ""), 2),
    ("有目录无台账", (True, None, ""), 2 - 1),
    ("只有表头", (True, "投喂与授权台账.md",
              "| 原文在哪 | 文体 | 与原著的关系 |\n|---|---|---|\n"), 1),
    ("缺两栏", (True, "投喂与授权台账.md",
             "| 原文在哪 | 备注 |\n|---|---|\n| 用户贴的第 3 章 | 待补 |\n"), 1),
    ("三样齐", (True, "投喂与授权台账.md",
             "| 原文在哪 | 文体 | 与原著的关系 |\n|---|---|---|\n"
             "| 用户贴的第 3 章 | 正文 | 原创 |\n"), 0),
]


def selftest():
    bad = 0
    for why, args, want in CASES:
        rc, msg, _ = judge_core(*args)
        ok = rc == want
        print("%s %-8s 期望 rc=%d 实得 rc=%d  %s" % ("✅" if ok else "✗", why, want, rc, msg))
        if not ok:
            bad += 1
    print("")
    print("自测：%d 例，失败 %d 例" % (len(CASES), bad))
    return 1 if bad else 0


def main():
    if "--self" in sys.argv:
        return selftest()

    gdir = os.path.join(ROOT, "00_原著")
    rc, msg, extra = judge(gdir)
    mark = {0: "✅", 1: "✗", 2: "⚠"}[rc]
    # 自报范围（项目规矩：没有 `[scope]` 的绿不认，`gate/_gate.py` 会扫这一行）
    print("[scope] 判对象：`00_原著/` 在不在 ＋ 台账文件名（含「投喂」「台账」）＋ 三样要素是否出现")
    print("[scope] 判形状不判内容：不解析列序，只问「三样出现过没有、有没有一行真填了字」")
    print("[scope] **查不了**：三样写得对不对／来源是不是真的／文体判得准不准——那要人读（E0·5）")
    print("%s 投喂登记（E0·1–E0·3）：%s" % (mark, msg))
    if "--gate" not in sys.argv:
        for line in extra:
            print("   · %s" % line)
    else:
        for line in extra[:1]:
            print("   · %s" % line)
    return rc


if __name__ == "__main__":
    sys.exit(main())
