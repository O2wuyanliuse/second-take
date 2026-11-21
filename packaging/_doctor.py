# -*- coding: utf-8 -*-
"""_doctor.py — 这套东西的环境自检。形状照 `flutter doctor`：**先查，再告诉你缺什么。**

用法：
    python packaging/_doctor.py

回答三个问题：
    ① 我在哪一侧？——**骨架侧**（本仓库，不含任何项目内容）／**项目侧**（有 `00_原著/`）
    ② 三组词表齐不齐？
    ③ 不齐的话，是「正常」还是「该修」？

退出码：`0` 齐 ／ `2` 骨架侧（缺是正常的）／ `1` 项目侧缺（该修）

## 为什么要有这个

`_nounlist.py` 缺词表时会**拒绝开工**（`NounlistMissing`）——那是有意的：
空词表会让每一份素材都显示「干净」，2026-11-10 那次公开仓泄露正是这个形态。

但「拒绝」和「报错」是两件事。新人 clone 下来一跑就是一屏 traceback，
会以为仓库坏了。**该说的是「这里不该跑」和「去你的项目里跑」，不是一段堆栈。**

同类的做法里，这一层叫 doctor：`flutter doctor`、`brew doctor`、`npx react-native doctor`。
它不替你修，只**把「缺什么、缺得对不对、下一步去哪」一次说清**。
"""

import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)


def main():
    has_project = os.path.isdir(os.path.join(ROOT, "00_原著"))
    side = "项目侧" if has_project else "骨架侧"

    print("[doctor] 当前：%s（%s）" % (side, "有 00_原著/" if has_project else "没有 00_原著/"))

    try:
        import _nounlist
    except Exception as e:
        print("[doctor] ⛔ 无法 import `_nounlist.py`：%s" % e)
        return 1

    miss = _nounlist.missing_sources()
    miss_labels = {label for label, _ in miss}

    # ---- 逐组报状态 ----
    detail = []
    if "A 人物与地点" in miss_labels:
        detail.append("A 人物与地点 …… 缺")
    else:
        try:
            n = len(_nounlist._collab_nouns())
            detail.append("A 人物与地点 …… 齐（%d 词）" % n)
        except Exception as e:
            detail.append("A 人物与地点 …… **解析失败**：%s" % str(e).split("\n")[0])
    if "B 设定词" in miss_labels:
        detail.append("B 设定词 ……… 缺")
    else:
        try:
            n = len(_nounlist._ledger_nouns())
            detail.append("B 设定词 ……… 齐（%d 词）" % n)
        except Exception as e:
            detail.append("B 设定词 ……… **解析失败**：%s" % str(e).split("\n")[0])
    if "C 组织与别名" in miss_labels:
        detail.append("C 组织与别名 …… 缺")
    else:
        n = len(_nounlist._supplement())
        detail.append("C 组织与别名 …… %s（%d 词）" % ("空（允许）" if n == 0 else "齐", n))

    print("[doctor] 三组词表：")
    for d in detail:
        print("           " + d)

    # ---- 结论 ----
    if not has_project:
        print("[doctor] 结论：**正常。** 本仓库不含任何项目内容，本来就没有词表。")
        print("[doctor] 下一步：把 `packaging/` 复制到你自己的项目里（`<项目根>/packaging/`），")
        print("           再照 `packaging/脱敏词表_样例.txt` 填三份词表。")
        print("[doctor] 想在这里看它怎么工作：读 `packaging/脱敏词表_样例.txt`")
        print("           和 README 的「这个仓库怎么自证不含项目内容」一节。")
        return 2

    if miss or any("解析失败" in d for d in detail):
        print("[doctor] 结论：**该修。** 缺词表时打包会拒绝开工——这是有意的，不是 bug。")
        print("[doctor] 补法：")
        for label, rel in miss:
            print("           · %s → `%s`" % (label, rel))
        print("           · C 组可照 `packaging/脱敏词表_样例.txt` 复制一份再填")
        return 1

    print("[doctor] 结论：**齐全，可以打包。**")
    print("[doctor] 自检一格：`python packaging/_triage.py <文件>` 会给 A／B／C 候选等级。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
