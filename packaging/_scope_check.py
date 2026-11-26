#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用层实例残留检查（提示档，**不进 gate**）。

判据只有一条：**「换一部小说、换一个平台，这句话还成立吗？」**
不成立的（某个项目的格数、镜数、秒数、专有细节）就不该待在通用层。

但这条判据机器判不全，所以这里只做两件**低误报**的事：

1. **裸数字**：`23 格`、`103 镜`、`39 秒` 这种既没区间也没「约」的数字 → 提示。
   规范数字（`24–36 格`、`60–90 秒`）整行带 `–`／`~`／`约`／`到`／`至`，直接跳过。
   带 `≤`／`最多`／`上限` 的也跳过——那是平台限制，不是项目样本。
2. **专名表**：`.ci/project_names.txt` 一行一个词，命中 → 红。
   词表与脱敏词表一样**不进库**（它写的就是要防的名字）。

退出码：**默认 0**（只打印，不拦）；`--strict` 时有命中退 1。
为什么默认不拦：清单稳定之前硬拦，人会开始忽略它——那比不查更坏。
行内写 `[scope-ok]` 可单条豁免（理由写在行尾）。

用法：
    python packaging/_scope_check.py
    python packaging/_scope_check.py --strict
"""

import argparse
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
        # 吞：输出流不支持 reconfigure 时保留原编码，不让输出配置阻断检查。

ROOT = Path(__file__).resolve().parent.parent

# 通用层清单：换项目时这几处该整份带走
TARGETS = (
    ("Agent框架", (".md",)),
    ("skills", (".md",)),
    ("tools", (".py",)),
)

# 案例文件就是放样本的地方；CHANGELOG 记的是历史，不适用通用层判据
SKIP_PARTS = ("references/projects/",)
SKIP_FILES = ("CHANGELOG.md",)

NUM_GELIN = re.compile(r"(?<![\d.\-/])(\d{2,3})\s*(格|镜)")
# 「分」不单独查：积分、分位、分镜全在里面，误报会比真报多。只认「分钟」与「秒」。
NUM_SEC = re.compile(r"(?<![\d.\-/])(\d{2,3})\s*(秒|分钟)")
RANGE_MARKS = ("–", "~", "约", "到", "至")
LIMIT_MARKS = ("≤", "最多", "上限", "至少")
OK_MARK = "[scope-ok]"


def iter_files():
    for top, exts in TARGETS:
        base = ROOT / top
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file() or p.suffix not in exts:
                continue
            rel = p.relative_to(ROOT).as_posix()
            if any(s in rel for s in SKIP_PARTS):
                continue
            if p.name in SKIP_FILES:
                continue
            yield p, rel


def load_names():
    p = ROOT / ".ci" / "project_names.txt"
    if not p.exists():
        return []
    words = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        w = line.strip()
        if w and not w.startswith("#"):
            words.append(w)
    return words


def scan(names):
    """返回 (裸数字清单, 专名命中)。代码块内的行不看——那是示例代码，不是正文。"""
    hits, red = [], []
    for p, rel in iter_files():
        in_code = False
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if line.strip().startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            if OK_MARK in line:
                continue
            for w in names:
                if w in line:
                    red.append((rel, i, w))
            if any(m in line for m in RANGE_MARKS) or any(m in line for m in LIMIT_MARKS):
                continue
            for m in NUM_GELIN.finditer(line):
                hits.append((rel, i, m.group(0)))
            for m in NUM_SEC.finditer(line):
                hits.append((rel, i, m.group(0)))
    return hits, red


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="有命中就退 1；默认只打印")
    args = ap.parse_args(argv)

    names = load_names()
    hits, red = scan(names)

    if red:
        print("[scope] ❌ 专名命中（这些词不该出现在通用层）：")
        for rel, i, w in red[:20]:
            print("  %s:%d  %s" % (rel, i, w))
        if len(red) > 20:
            print("  …还有 %d 处" % (len(red) - 20))

    if hits:
        print("[scope] ⚠ 通用层需人工过一遍：裸数字 %d 处" % len(hits))
        for rel, i, tok in hits[:30]:
            print("  %s:%d  %s" % (rel, i, tok))
        if len(hits) > 30:
            print("  …还有 %d 处" % (len(hits) - 30))
        print("[scope] 判据：换一部小说还成立吗？样本请移进 references/projects/；")
        print("[scope]       确属规范的，行尾写 `[scope-ok]` 并说明理由。")

    if not names:
        print("[scope] 提示：没有 .ci/project_names.txt，专名一项**没查**（不是干净）。")

    if not red and not hits:
        print("[scope] ✅ 通用层没有裸数字，也没有专名命中。")
        return 0

    if not args.strict:
        print("[scope] 提示档：不影响退出码。要阻断加 --strict。")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
