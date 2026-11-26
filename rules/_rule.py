#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""规则引擎：把「判据的形状」和「项目的绑定」物理分开。

用法
    python rules/_rule.py --list
    python rules/_rule.py 同一实体两种定性
    python rules/_rule.py 同一实体两种定性 --bind rules/别的.bind.json

完整说明：docs/maintain/代码内长文档/rules/_rule.py.md
"""

from __future__ import print_function

import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)          # 仓库根：规则里的路径一律相对它


# ---------------------------------------------------------------- 基础读写

def rd(p):
    try:
        return io.open(p, encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def load_json(p):
    t = rd(p)
    if not t:
        return None
    try:
        return json.loads(t)
    except Exception:
        return None


def shape_of(name):
    return load_json(os.path.join(HERE, name + ".rule.json"))


def bind_of(name, bind_path=None):
    p = bind_path or os.path.join(HERE, name + ".bind.json")
    return load_json(p), p


# ---------------------------------------------------------------- 参数校验

def _dig(d, dotted):
    cur = d
    for k in dotted.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def missing_params(shape, bind):
    """返回缺哪些必填参数（点号路径 + 人话说明 + 建议填什么）。"""
    out = []
    for prm in shape.get("params", []):
        if not prm.get("required"):
            continue
        val = _dig(bind or {}, prm["key"])
        empty = val is None or val == "" or val == [] or val == {}
        if empty:
            out.append(prm)
    return out


# ---------------------------------------------------------------- 取字段

def _table_status_cell(row, markers):
    """按行取「带状态记号的那个单元格」。锚定表用这条。"""
    for cell in row.split("|"):
        if any(m in cell for m in markers):
            return cell
    return ""


def _json_field(txt, name, anchor_key, field):
    """按对象取某个字段，不碰同对象的自由文本。

    **为什么只取字段**：同一段话里提到「作废」，不等于这一条是作废的——
    它可能在说「同批另外几张作废」。按词频判极性，是这条规则首版
    24 命中 23 假阳的成因。
    """
    pat = r'"%s"\s*:\s*"%s"' % (re.escape(anchor_key), re.escape(name))
    for m in re.finditer(pat, txt):
        nxt = txt.find('"%s"' % anchor_key, m.end())
        blk = txt[m.start(): nxt if nxt != -1 else len(txt)]
        r = re.search(r'"%s"\s*:\s*"([^"]*)"' % re.escape(field), blk)
        if r:
            return r.group(1)
    return ""


def _extract(src, txt, name):
    mode = src.get("mode")
    if mode == "table_status_cell":
        rows = [l for l in txt.split("\n") if name in l]
        return " ".join(_table_status_cell(r, src.get("markers", "✅🟡🔴⚪")) for r in rows)
    if mode == "json_field":
        return _json_field(txt, name, src.get("anchor_key", "file"), src.get("field", "status"))
    return ""


# ---------------------------------------------------------------- 实现：同一实体两种定性

def impl_polarity(bind):
    """同一实体，在两份权威源里的**定性**是否打架。

    判据形状（与项目无关）：
      · 实体名：由 entities.regex 从两份文件里各扫一遍，取交集
      · 定性：每份源声明一个「取哪一格/哪个字段」，只认结构化字段
      · 极性：positive / negative 两张词表，两边都取到才算「已标」
      · 违规：同一实体在两份源里的极性不同（正 vs 负，或正 vs 混）

    项目相关的全部参数：源文件两条、实体正则、取字段方式、两张词表。
    """
    base = bind.get("_base", BASE)
    ents = bind["entities"]
    reg = re.compile(ents["regex"])
    pos = re.compile(bind["polarity"]["positive"])
    neg = re.compile(bind["polarity"]["negative"])

    texts = {}
    for src in bind["sources"]:
        texts[src["name"]] = rd(os.path.join(base, src["path"]))

    names = set()
    for t in texts.values():
        names |= set(reg.findall(t))
    if not names:
        return ["两份源里一个实体都没扫到——**这不算通过**，先确认 entities.regex 对不对"]
    out = []
    for name in sorted(names):
        pol, per = {}, {}
        for src in bind["sources"]:
            cell = _extract(src, texts.get(src["name"], ""), name)
            if not cell and not any(name in t for t in texts.values()):
                continue
            without_neg = neg.sub("", cell)
            if neg.search(cell) and pos.search(without_neg):
                p = "混"
            elif neg.search(cell):
                p = "负"
            elif pos.search(without_neg):
                p = "正"
            else:
                p = "未标"
            pol[src["name"]], per[src["name"]] = p, cell.strip()
        marked = {v for v in pol.values() if v != "未标"}
        if len(marked) > 1:
            detail = "／".join("%s「%s」" % (k, pol[k]) for k in pol)
            out.append("%s —— %s" % (name, detail))
    return out


IMPL = {
    "同一实体两种定性": impl_polarity,
}


# ---------------------------------------------------------------- 对外

def run(name, base=None, bind_path=None):
    """返回 (状态, 说明或命中列表)。状态：绿／红／未绑定／无规则。"""
    shape = shape_of(name)
    if not shape:
        return "无规则", ["找不到形状文件 rules/%s.rule.json" % name]
    impl = IMPL.get(shape.get("impl") or name)
    if not impl:
        return "无规则", ["形状文件声明了 impl=%r，但引擎里没有这个实现" % shape.get("impl")]

    bind, bpath = bind_of(name, bind_path)
    if bind is None:
        return "未绑定", ["没有绑定文件 %s" % os.path.relpath(bpath, BASE)]
    miss = missing_params(shape, bind)
    if miss:
        lines = ["参数不齐，**这一项没查成**："]
        for prm in miss:
            lines.append("  · 缺 %s（%s）—— %s" % (prm["key"], prm.get("desc", ""),
                                                   prm.get("fill", "按形状文件填一份")))
        if bpath.endswith(".bind.example.json"):
            tgt = bpath.replace(".bind.example.json", ".bind.json")
            lines.append("  这是空靶。照它复制成 %s，填完再跑。"
                         % os.path.relpath(tgt, BASE))
        else:
            lines.append("  填在 %s；或照 %s 复制一份。" %
                         (os.path.relpath(bpath, BASE),
                          os.path.relpath(bpath.replace(".bind.json", ".bind.example.json"), BASE)))
        return "未绑定", lines

    bind.setdefault("_base", base or BASE)
    hits = impl(bind)
    return ("红" if hits else "绿"), hits


def main():
    args = [a for a in sys.argv[1:]]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if args[0] == "--list":
        files = sorted(f[:-len(".rule.json")] for f in os.listdir(HERE)
                       if f.endswith(".rule.json"))
        if not files:
            print("rules/ 下还没有任何规则形状文件。")
            return 0
        print("规则（%d 条）：" % len(files))
        for n in files:
            sh = shape_of(n) or {}
            has_bind = os.path.isfile(os.path.join(HERE, n + ".bind.json"))
            print("  %-18s %s   绑定：%s" % (n, sh.get("一句话", ""),
                                            "有" if has_bind else "**无（跑起来会报未绑定）**"))
        return 0

    name = args[0]
    bind_path = None
    if "--bind" in args:
        i = args.index("--bind")
        if i + 1 < len(args):
            bind_path = os.path.abspath(args[i + 1])

    status, payload = run(name, bind_path=bind_path)
    print("[rule] %s —— %s" % (name, status))
    if status == "绿":
        print("  ✅ 已绑定，无违规。")
        print("  （只证「这两处说法一致」，不证「说法本身对」——那要看字段背后的事实。）")
        return 0
    if status == "未绑定":
        print("  ⛔ 未绑定**不算绿**：现在这一项什么都没查。")
        for x in payload:
            print("  " + x)
        return 2
    if status == "无规则":
        for x in payload:
            print("  ✗ " + x)
        return 1
    print("  ✗ 命中 %d 处：" % len(payload))
    for x in payload:
        print("    · " + x)
    return 1


if __name__ == "__main__":
    sys.exit(main())
