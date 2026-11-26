# -*- coding: utf-8 -*-
"""_diff.py · 正文层账实核对（E1「二·补」第 4 条判据的机器版）

管什么
    定稿稿相对原件改了什么、改了的是不是都登记了。

三条判据（都能机器判，不靠自己记）
  1 计数：diff 行数必须落在 [条数, 条数×2]。
     替换一处产生 2 行差异（一减一加）；纯新增或纯删除一处产生 1 行。
     低于条数＝有登记却没改；高于条数×2＝有改动没登记。两头都是账实不符。
  2 语义（比计数硬）：每条记录的
     · 「原处」必须在**原件**里命中
     · 「现文」必须在**定稿稿**里命中
     · 「原处」不得残留在**定稿稿**里（否则那一处根本没改）
     计数对得上但语义对不上，说明记录与改动对错了号——这类错计数抓不到。
  3 同构：定稿稿与原件行数必须相同（「二·补」要求同构）。

不管什么
    · 「这一处该不该改」——裁决权归 `定论台账`，本脚本只核对账实是否相符。
    · 引用有没有漂 → `_anchor.py`；作废词有没有回潮 → `_lint.py`；
      真相源 md5 有没有被偷改 → `_collab.py`。
    · 换了行算不算一处改动、该不该合并——人判。

局限（必须写明，免得它变成新的假守护）
    ① 依赖变更记录里的「原处／现文」写的是**足够长的整句**。
      只写半句、或用省略号，会搜不到而误报——这是记录写法的病，不是判据的病。
    ② 同一句在原件里出现多次、只改其中一处时，判据 2 的「原处不得残留」会误报。
      当前两卷无此情况；出现时按提示人工确认，别急着改脚本。
    ③ 判据 1 数的是**非空行**的差异。2026-10-29 之前数全部行，连续多段替换时
      difflib 会把中段空行卷进块，5 段改动算成 22 行，误报「改了没登记」。

用法
    python _diff.py            # 全查
    python _diff.py --quiet    # 只出结论
"""

import difflib
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
        # 吞：输出流不支持 reconfigure 时保留原编码，不让输出配置阻断检查。
# ---------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_cfg():
    # 故意重复：可单独搬运，见 README
    """同目录 checks.config.json 有就用；`--config` 可覆盖（2026-11-16 脱参数）。"""
    p = os.path.join(HERE, "checks.config.json")
    if "--config" in sys.argv:
        p = sys.argv[sys.argv.index("--config") + 1]
    if not os.path.exists(p):
        return {}
    try:
        import json
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return {}


CFG = _load_cfg()
ROOT = os.path.abspath(CFG.get("root") or os.path.join(HERE, "..", ".."))
if "--root" in sys.argv:
    ROOT = os.path.abspath(sys.argv[sys.argv.index("--root") + 1])
# 正文所在目录（相对项目根）——本项目的正文都在一个目录里
BASE = os.path.join(ROOT, CFG.get("diff", {}).get("text_dir", ""))

VOLUMES = CFG.get("diff", {}).get("volumes", [])

P1, P2 = [], []


def read_bytes(rel):
    with open(os.path.join(BASE, rel), "rb") as f:
        return f.read()


def to_lines(text):
    """统一切成行（CRLF 与 LF 都按行切），用于 diff"""
    return text.replace("\r\n", "\n").split("\n")


def clean(cell):
    """表格单元格 → 可比对的纯文本。只去排版标记，不动标点。"""
    s = cell.replace("**", "").replace("`", "").replace("\\|", "|")
    return s.strip()


def parse_log(rel):
    """从变更记录里读「改动清单」表。

    只认表头同时带「#」「原处」「现文」的那张表——避免把「未决事项」等其它表格吃进来。

    返回 (rows, seen_header)：
      · rows 为 None 表示文件不存在；
      · seen_header 为 False 表示**没认出表头**——这不是「0 条改动」，
        而是「本脚本读不懂这份记录了」，两种情况必须分开报，否则格式一改就静默失灵。
    """
    path = os.path.join(BASE, rel)
    if not os.path.exists(path):
        return None, False
    rows = []
    inside = False
    seen_header = False
    for ln in io.open(path, encoding="utf-8").read().replace("\r\n", "\n").split("\n"):
        s = ln.strip()
        if s.startswith("|") and "#" in s and "原处" in s and "现文" in s:
            inside = True
            seen_header = True
            continue
        if inside:
            if not s.startswith("|"):
                inside = False
                continue
            if set(s.replace("|", "").strip()) <= set("-: "):
                continue
            cells = [x for x in s.strip().strip("|").split("|")]
            if len(cells) < 5:
                P2.append("%s 有表格行只切出 %d 列，已跳过：%s"
                          % (rel, len(cells), s[:70]))
                continue
            rows.append({
                "no": cells[0].strip(),
                "where": cells[1].strip(),
                "based": cells[2].strip(),
                "before": clean(cells[3]),
                "after": clean(cells[4]),
            })
    return rows, seen_header


def diff_lines(a, b):
    """数差异行。**空行先剔掉再算**。

    2026-10-29 实测踩到：第十一章开篇连改 5 段，段与段之间都隔着空行。
    difflib 的 SequenceMatcher 把这一整片判成"一块替换"——5 个文字行连中段的
    空行一起标成 `-`／`+`，算出来 22 行；GNU diff 只算 14 行。
    于是判据报「改了没登记」，而实际账实相符。**这是判据误报，不能改数据去凑它。**

    空行本身的增删由判据 3（行数同构）兜底：只要动过空行，总行数必变，那里会拦。
    这里只管"有内容的行"。
    """
    a = [x for x in a if x.strip()]
    b = [x for x in b if x.strip()]
    d = difflib.unified_diff(a, b, n=0, lineterm="")
    return sum(1 for x in d
               if (x.startswith("+") or x.startswith("-"))
               and not x.startswith("+++") and not x.startswith("---"))


def check(vol, quiet):
    name = vol["name"]
    # 文件缺失必须报出来（2026-11-01 补）：原来直接 open()，缺文件就抛栈崩掉，
    # 屏幕上是一堆 Traceback，看不出「这一卷根本没核」。缺件 ≠ 核过没问题。
    for k, label in (("raw", "原文原件"), ("final", "定稿稿")):
        if not os.path.exists(os.path.join(BASE, vol[k])):
            P1.append("%s 缺%s（%s）——**这一卷根本没核**，不是「核过没问题」。"
                      % (name, label, vol[k]))
            return
    raw_b = read_bytes(vol["raw"])
    fin_b = read_bytes(vol["final"])
    raw_t = raw_b.decode("utf-8")
    fin_t = fin_b.decode("utf-8")

    raw_l = to_lines(raw_t)
    fin_l = to_lines(fin_t)

    # ---- 判据 3：同构 ----
    if len(raw_l) != len(fin_l):
        P1.append("%s 行数与原件不同：原件 %d 行，定稿稿 %d 行。\n"
                  "    「二·补」要求同构（只改字、不加删行）。差 %d 行，先查清是漏改还是多改。"
                  % (name, len(raw_l), len(fin_l), len(fin_l) - len(raw_l)))

    # ---- 换行符 / BOM（提示级，见「段落零缩进」那次教训）----
    if (b"\r\n" in raw_b) != (b"\r\n" in fin_b):
        P2.append("%s 换行符与原件不一致（原件 %s，定稿稿 %s）"
                  % (name, "CRLF" if b"\r\n" in raw_b else "LF",
                     "CRLF" if b"\r\n" in fin_b else "LF"))
    if fin_b[:3] == b"\xef\xbb\xbf" and raw_b[:3] != b"\xef\xbb\xbf":
        P2.append("%s 定稿稿带 BOM，原件没有——会把 md5 与首行比对全带偏" % name)

    # ---- 判据 1：计数 ----
    rows, seen_header = parse_log(vol["log"])
    if rows is None:
        P1.append("%s 找不到变更记录（%s）。有定稿稿没变更记录＝改了没人知道。"
                  % (name, vol["log"]))
        return
    if not seen_header:
        P1.append("%s 的变更记录里没认出「改动清单」表（%s）。\n"
                  "    表头需同时含「#」「原处」「现文」三样。认不出来＝本脚本读不懂这份记录，\n"
                  "    不是「0 条改动」——先把表头修回去，别让它静默失灵。"
                  % (name, vol["log"]))
        return
    n = len(rows)
    d = diff_lines(raw_l, fin_l)

    if n == 0 and d != 0:
        P1.append("%s 变更记录 0 条，但定稿稿与原件差 %d 行——有改动没登记。" % (name, d))
    elif n > 0 and not (n <= d <= n * 2):
        P1.append("%s 账实不符：变更记录 %d 条，diff %d 行。\n"
                  "    合法区间是 [%d, %d]（替换一处=2 行，纯增删一处=1 行）。\n"
                  "    少于 %d ＝ 登记了却没改；多于 %d ＝ 改了却没登记。"
                  % (name, n, d, n, n * 2, n, n * 2))

    # ---- 判据 2：语义（必须**计数**，不能只判"搜得到"）----
    # 2026-10-29 反测血案，必须留在这：
    #   本判据第一版写成「现文能不能搜到」，结果两卷里两处改动文本**完全相同**
    #   （同一句报时台词在两次循环重放），把循环 1 偷改成 230、记录不动，
    #   现文照样能在循环 2 那处搜到 → 判据判定「账实相符」，放行了。
    #   而变更记录里本来就写着警告：「不能靠搜到了就算改过」。
    #   所以这里一律数出现次数：残留几处、新增几处，都要与记录条数对得上。
    groups = {}
    for r in rows:
        groups.setdefault((r["before"], r["after"]), []).append(r)

    for (bf, af), items in groups.items():
        cnt = len(items)
        tag = "%s 第 %s 条（%s）" % (name, "／".join(x["no"] for x in items),
                                     items[0]["where"][:38])
        if not bf or not af:
            P2.append("%s 「原处」或「现文」为空，无法核对语义" % tag)
            continue
        if bf == af:
            P2.append("%s 「原处」与「现文」完全相同，这条记录没法核对" % tag)
            continue

        R = raw_t.count(bf)     # 原件里「原处」出现几次
        F = fin_t.count(bf)     # 定稿稿里「原处」还剩几次
        A = fin_t.count(af)     # 定稿稿里「现文」出现几次
        A0 = raw_t.count(af)    # 原件里「现文」本来就有几次（同文互改时会不为 0）

        if R == 0:
            P1.append("%s 「原处」在原件里一次都搜不到。\n"
                      "    原处：%s\n"
                      "    要么记录抄错、要么引的不是原件原句——判据失去依据。"
                      % (tag, bf[:80]))
            continue

        if F != R - cnt:
            P1.append("%s 原处残留数不符：原件里有 %d 处，记录登记 %d 处，"
                      "定稿稿里本应只剩 %d 处，实际剩 %d 处。\n"
                      "    原处：%s\n"
                      "    剩多了＝漏改（或改了别处）；剩少了＝没登记的额外改动。"
                      % (tag, R, cnt, R - cnt, F, bf[:80]))

        if A != A0 + cnt:
            P1.append("%s 现文出现数不符：原件里本来有 %d 处，登记新增 %d 处，"
                      "定稿稿里应有 %d 处，实际 %d 处。\n"
                      "    现文：%s\n"
                      "    少了＝有一处没真改成这个；多了＝改了没登记的同类地方。"
                      % (tag, A0, cnt, A0 + cnt, A, af[:80]))

    if not quiet:
        print("  %s：变更记录 %d 条 ／ diff %d 行 ／ 原件与定稿稿各 %d 行"
              % (name, n, d, len(raw_l)))


def main():
    quiet = "--quiet" in sys.argv
    print("正文层账实核对 · E1「二·补」第 4 条判据")
    print("")
    # ── scope 自报（2026-11-01 立）：先说清要核几卷、每卷三件套齐不齐 ──
    if not VOLUMES:
        print("[scope] 没有配 `diff.volumes`——这一项在你的项目里才有意义（读不到要核的卷，等于没查）")
        return 0
    print("[scope] 核对 %d 卷（每卷三件套：原文原件／定稿稿／变更记录）" % len(VOLUMES))
    for vol in VOLUMES:
        parts = []
        for k, label in (("raw", "原件"), ("final", "定稿稿"), ("log", "变更记录")):
            ok = os.path.exists(os.path.join(BASE, vol[k]))
            parts.append("%s%s" % (label, "✓" if ok else "✗缺"))
        print("[scope]   %s：%s" % (vol["name"], "　".join(parts)))
    print("")
    for vol in VOLUMES:
        check(vol, quiet)
    print("")

    if not P1 and not P2:
        print("✅ 账实相符：每一处改动都登记了，每一条登记都真的落到定稿稿。")
        print("   ⚠ 本脚本只核对「改了的是不是都记了」，不判「该不该改」——那归台账。")
        return 0

    if P1:
        print("✗ 应改（P1）　%d 条" % len(P1))
        for i, x in enumerate(P1, 1):
            print("  %d. %s" % (i, x))
        print("")
    if P2:
        print("提示（P2）　%d 条" % len(P2))
        for i, x in enumerate(P2, 1):
            print("  %d. %s" % (i, x))
        print("")

    print("小结：%d 条应改 ／ %d 条提示" % (len(P1), len(P2)))
    return 1 if P1 else 2


if __name__ == "__main__":
    sys.exit(main())
