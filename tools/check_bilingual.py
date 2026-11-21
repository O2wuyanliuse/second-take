#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_bilingual.py — 检查对外文档是否带英文摘要（只查有没有，不查写得好不好）。

判据：清单里每个文件的前 30 行内，必须有一行以 `**English` 开头。
退出码：0 全都有 ／ 1 有文件缺 ／ 2 一个清单文件都不存在（没查成）
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED = (
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "AGENTS.md",
    "docs/maintain/维护方法.md",
    ".github/pull_request_template.md",
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/ISSUE_TEMPLATE/suggestion.md",
)


def has_english(path):
    try:
        with io.open(path, encoding="utf-8", errors="replace") as f:
            head = f.readlines()[:30]
    except OSError:
        return None
    return any(line.lstrip(" >\t").startswith("**English") for line in head)


def main():
    seen, missing, bad = 0, [], []
    for rel in REQUIRED:
        p = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.exists(p):
            missing.append(rel)
            continue
        seen += 1
        if has_english(p) is not True:
            bad.append(rel)
    if seen == 0:
        print("[bilingual] 一个清单文件都不存在，没查成")
        return 2
    if missing:
        print("[bilingual] 清单里有文件不存在（清单过期了，先修清单）：%s" % "、".join(missing))
    if bad:
        print("[bilingual] 这些文件前 30 行里没有英文摘要（以 `**English` 开头那一行）：")
        for rel in bad:
            print("  × %s" % rel)
        print("[bilingual] 怎么改成绿：在标题下方空一行贴一段 `> **English summary:** ...`，见 CONTRIBUTING.md 样板。")
        return 1
    print("[bilingual] %d 份对外文档都有英文摘要" % seen)
    return 0


if __name__ == "__main__":
    sys.exit(main())
