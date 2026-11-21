# -*- coding: utf-8 -*-
"""_nounlist.py — 脱敏与查名共用的词表。三个来源，缺一个都会漏。

    A  `00_原著/_collab.py` 的 `PROJECT_NOUNS`   —— 人物与地点（14 个）
    B  `00_原著/专名对账_v1.md` 表格第一列        —— 设定词（去同形异义，16 个）
    C  `packaging/脱敏补充词.txt`               —— 上两处都没登记的：组织名、别名、全名

## 为什么必须有 C（2026-11-02 实测，不是推演）

一类 **组织名** 和一类 **人物别名** 在 A、B 里**都没有**，于是 V3 全绿，包照样带着它们出去了：
    `[标准]文字转画面转化规则_v1.md` 的教学表格里有一句原文引文，含组织真名
    `skills/ai-video-pipeline/SKILL.md` 的两行示例里，有人物真名

**这不是台账写错了。** 台账登记的是「正文里实际用什么名字」，**组织名和别名本来就不在它的范围**。
登记表没覆盖的地方，只能人工列出来，然后由脚本保证它不会再漏。

## 一条纪律

**词表本身不许再复制一份。** `_pack.py` 与 `_verify_package.py` 都从这里取——
两边各抄一份，就又是一对会漂的副本（今天已经在 `07_视觉提示词规则` 上吃过一次）。
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
        pass
# ---------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 与 `_layer_audit.py` 的 HOMONYMS 一致：框架术语与项目专名撞字，不算泄漏。
# 不 import 那个脚本（它有副作用），而是把这两个词抄在这里并注明出处——
# 只有两个词，且 `_layer_audit` 改动时这里不会自动跟，所以写了这条注释。
HOMONYMS = {"门阀", "误读"}

HEADER = {"专名", "依据", "状态", "正文实际用什么"}


class NounlistMissing(RuntimeError):
    """词表缺失 —— **拒绝开工，不返回空表**。

    为什么必须是异常而不是 `return []`（2026-11-11 改）：

      空词表不会报错，它只会让**每一份素材都显示「干净」**。
      2026-11-10 公开仓那次泄露正是这个形态：三组词表读不到 →
      脱敏什么也没删 → 打包流程「全绿」→ 三个真实组织名跟着说明书出去了。
      修正它要重建整条公开历史，因为**公开仓库的泄露不可逆**。

    **宁可红，不许假绿。** 这条比「别中断流程」重要。
    """


SOURCES = (
    ("A 人物与地点", os.path.join("00_原著", "_collab.py")),
    ("B 设定词", os.path.join("00_原著", "专名对账_v1.md")),
    ("C 组织与别名", os.path.join("packaging", "脱敏补充词.txt")),
)


def missing_sources():
    """返回缺失的源清单 `[(标签, 相对路径)]`；空列表＝齐全。"""
    return [(label, rel) for label, rel in SOURCES
            if not os.path.isfile(os.path.join(ROOT, rel))]


def _collab_nouns():
    p = os.path.join(ROOT, "00_原著", "_collab.py")
    raw = io.open(p, encoding="utf-8", errors="ignore").read()
    m = re.search(r"PROJECT_NOUNS\s*=\s*\[(.*?)\]", raw, re.S)
    if not m:
        raise NounlistMissing(
            "A 组解析失败：`00_原著/_collab.py` 里找不到 `PROJECT_NOUNS = [...]`。\n"
            "  文件在、表没有，等于词表是空的 —— 同样会让包显示「干净」。")
    words = re.findall(r'"([^"]+)"', m.group(1))
    if not words:
        raise NounlistMissing("A 组解析出 0 个词：`PROJECT_NOUNS` 是空表。")
    return words


def _ledger_nouns():
    """专名台账表格第一列。解析口径照抄 `_layer_audit.py`，不另发明。"""
    p = os.path.join(ROOT, "00_原著", "专名对账_v1.md")
    out = []
    for ln in io.open(p, encoding="utf-8", errors="ignore").read().split("\n"):
        if not ln.startswith("|"):
            continue
        cols = [c.strip() for c in ln.strip().strip("|").split("|")]
        if not cols:
            continue
        cell = cols[0].replace("*", "").replace("~~", "").strip()
        if not cell or cell in HEADER or len(cell) > 12:
            continue
        if re.fullmatch(r"[\u4e00-\u9fa5A-Za-z0-9]{2,12}", cell):
            out.append(cell)
    result = sorted(set(out) - HOMONYMS)
    if not result:
        raise NounlistMissing(
            "B 组解析出 0 个词：`00_原著/专名对账_v1.md` 的第一列没有可识别的专名。")
    return result


def _supplement():
    """`脱敏补充词.txt`：每行 `原词=替换成`，`#` 开头是注释。

    **C 组允许为空**（新项目可能真的还没有组织名／别名），但**文件必须在**——
    文件不在时由 `missing_sources()` 挡下，走到这里说明文件是存在的。
    """
    p = os.path.join(HERE, "脱敏补充词.txt")
    out = {}
    for ln in io.open(p, encoding="utf-8", errors="ignore").read().split("\n"):
        ln = ln.strip()
        if not ln or ln.startswith("#") or "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        k, v = k.strip(), v.strip()
        if k and v:
            out[k] = v
    return out


def load():
    """返回 (自动编号的词列表, 指定替换的词字典)。

    自动编号：同一个词→同一个「角色N」，按包内出现频率排序编号（常见的是甲乙丙）。
    指定替换：用于「角色N 读起来不对」的词——组织名、设定词、别名。

    **缺源就抛 `NounlistMissing`，一次报全，不逐个中断。**
    """
    miss = missing_sources()
    if miss:
        raise NounlistMissing(
            "词表不全，拒绝开工 —— **空词表会让任何包都显示「干净」**：\n"
            + "\n".join("  · %s —— 缺 `%s`" % (label, rel) for label, rel in miss)
            + "\n补法：A 在 `00_原著/_collab.py` 写 `PROJECT_NOUNS = [...]`；"
              "B 放 `00_原著/专名对账_v1.md`；"
              "C 照 `packaging/脱敏词表_样例.txt` 填一份 `packaging/脱敏补充词.txt`。")

    fixed = _supplement()
    auto = [w for w in (_collab_nouns() + _ledger_nouns()) if w not in fixed]
    # 长的先替，避免长词被它的短后缀先命中，剩下半截
    auto = sorted(set(auto), key=len, reverse=True)
    return auto, fixed
