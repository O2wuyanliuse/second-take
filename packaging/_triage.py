# -*- coding: utf-8 -*-
"""_triage.py — 投喂分级提示器。挂 **E0·1**，不是打包时。

用法：
    python packaging/_triage.py <文件或目录> [--nouns-file 词表.txt]

输出：建议等级（A / B / C）＋ 依据（命中哪些专名、是否疑似叙事、有无硬问题）。
退出码：`0` 已给建议 ／ `1` 有硬问题（密钥、本机路径）—— 硬问题不看等级，先修。

## 三条纪律

① **它不判定，只提示。** 等级由人写进 E0 登记第 9 项。脚本给的是候选。
② **词表不全就报错，不许静默给 A。** 一份空词表会让任何素材都显示“干净”——
   这正是 2026-11-10 那次泄露的形态：打包全绿，词表其实是空的。
③ **结构类信号不依赖词表**（密钥、本机路径、疑似叙事），任何时候都能查。

## 为什么在 E0 而不是打包时

脱敏需要的信息在投喂那一刻最全：作者知道“这个词是组织名还是普通词”。
到了打包阶段只剩 grep，而 grep 只知道出现过，不知道是什么。
"""

import io
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
        # 吞：输出流不支持 reconfigure 时保留原编码，不让输出配置阻断检查。

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

TEXT_EXT = {".md", ".txt", ".py", ".json", ".yaml", ".yml", ".toml", ".sh", ".tsv", ".csv", ".html"}

SECRET_PAT = re.compile(
    r"(sk-[A-Za-z0-9]{12,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{12,}"
    r"|Bearer\s+[A-Za-z0-9\-\._]{20,}|password\s*[:=]|api[_-]?key\s*[:=])", re.I)

# 盘符前不许是字母数字——否则 `http://` 的 `p:/`、`file://` 的 `e:/` 全被当成路径。
# 首版没加这个 lookbehind，8 命中 8 误报（2026-11-11 实测）。**同一族毛病见 C8：共现判不出意图。**
# 这里只认**结构特征**（盘符、家目录）。裸目录名属于词表范畴，走 `--nouns-file`，
# 不写死在本机——写死一个，等于把某台机器的目录结构钉进了通用层。
# 2026-11-21：原来还硬编码了一个「工具目录」，那是同一毛病的变体，已删。
LOCALPATH_PAT = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]"
    r"|/Users/[A-Za-z0-9._-]{2,}")

# 讲"路径这件事"的说明文字、占位示例、正则字面量——都不算泄露。
NOISE_PAT = re.compile(
    r"(\.\.\.|…|某人|某某|我的创作|我的项目|Programs[\\/]Python|"
    r"[\\/]tmp|127\.0\.0\.1|localhost|https?://|r\"|正则|示例|示范|例如)")

NARRATIVE_PAT = re.compile(r"[「“\"][^」”\"]{4,}[」”\"]")

# ── 项目痕迹（2026-11-12 加，起因是一次真的漏）──────────────────────────────
# 2026-11-11 夜：公开仓查出 85 处 `G-号`、19 处「定论台账」、2 个带日期戳的资产文件名。
# **专名表一条都查不出来**——因为它只收人物与地点，不收编号。
# 而编号恰恰是最容易漏的：它不像人名那样扎眼，却把「有 75 个批次、663 条通道」说漏了。
# 分两类，别混成一条：
#   ① **资产文件名**（`名字_日期戳_时分` 这种）→ 真名，硬问题。它指向磁盘上一张真图。
#   ② **台账编号**（`G-630`／`K-75`）→ 只提示，不阻断。
#      依据：`README.md` 第 41 行声明「保留编号作溯源指针，本仓库不含那份台账」。
#      **不把设计当漏洞改**——2026-11-12 凌晨我第一版就是这么误判的（97 处全报红）。
TRACE_FILE_PAT = re.compile(r"[\w\u4e00-\u9fa5]{2,}_\d{8}_\d{4}")
TRACE_ID_PAT = re.compile(r"(?<![A-Za-z0-9])[GK]-?\d{2,3}(?![0-9])")

# 模板里的占位号（`G-001` 这种）与讲规则的示例，不算痕迹。
TRACE_NOISE = re.compile(r"(示例|示范|例如|占位|模板|G-001|G-000)")


def load_nouns(nouns_file=None):
    """返回 (词表, 来源说明, 缺失说明)。**词表不全时缺失说明非空。**"""
    if nouns_file:
        if not os.path.exists(nouns_file):
            return [], "", "指定的词表不存在：%s" % nouns_file
        words = []
        for ln in io.open(nouns_file, encoding="utf-8", errors="ignore").read().split("\n"):
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            if ln.startswith("[") and ln.endswith("]"):
                continue      # `[类别]` 是分段头，不是词——当词收进去就是一个永假命中
            words.append(ln.split("=")[0].strip())
        return [w for w in words if w], "外部词表 %s" % os.path.basename(nouns_file), ""

    try:
        import _nounlist
        auto, fixed = _nounlist.load()
        words = sorted(set(auto) | set(fixed))
        if not words:
            return [], "", "词表解析结果为空"
        return words, "内置三组（A/B/C）", ""
    except Exception as e:
        # `_nounlist.load()` 缺源时抛 NounlistMissing 并一次报全；
        # 这里只把它转成「缺什么」，**不吞掉、不降级成空表**。
        return [], "", str(e).replace("\n", " ").replace("\r", " ")


def iter_files(target):
    if os.path.isfile(target):
        yield target
        return
    for dp, dn, fns in os.walk(target):
        dn[:] = [d for d in dn if d not in (".git", "node_modules", "__pycache__")]
        for fn in fns:
            if os.path.splitext(fn)[1].lower() in TEXT_EXT:
                yield os.path.join(dp, fn)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 0
    target = args[0]
    nouns_file = None
    if "--nouns-file" in sys.argv:
        i = sys.argv.index("--nouns-file")
        if i + 1 < len(sys.argv):
            nouns_file = sys.argv[i + 1]

    words, src, missing = load_nouns(nouns_file)
    print("[triage] 词表：%s ｜ %d 个词" % (src, len(words)))
    if missing:
        # 2026-11-20（冷启动实测·问题 3）：否决必须在数字前面。
        # 原来 ⛔ 夹在中间、后面紧跟「专名命中 0 处」——人眼只抓住那个 0，看不见「不许判 A」。
        print("[triage] ⛔ **词表不全 → 本次结论：未判定。** 下面「专名」那一栏是「未查」，不是 0。")
        print("[triage]    原因：%s" % missing)
        print("[triage]    结构类信号（密钥／本机路径／疑似叙事）照常给。")

    noun_hits, hard, soft, narr, nfiles, ids = {}, [], [], 0, 0, 0
    for fp in iter_files(target):
        nfiles += 1
        rel = os.path.relpath(fp, ROOT).replace("\\", "/")
        try:
            lines = io.open(fp, encoding="utf-8", errors="replace").read().split("\n")
        except Exception:
            continue
        for i, ln in enumerate(lines, 1):
            for w in words:
                if w in ln:
                    noun_hits.setdefault(w, []).append("%s:%d" % (rel, i))
            m = SECRET_PAT.search(ln)
            if m:
                hard.append(("密钥", rel, i, m.group(0)[:24]))
            if LOCALPATH_PAT.search(ln) and not NOISE_PAT.search(ln):
                soft.append(("本机路径", rel, i, ln.strip()[:80]))
            if TRACE_FILE_PAT.search(ln):
                hard.append(("资产文件名", rel, i, TRACE_FILE_PAT.search(ln).group(0)[:40]))
            if TRACE_ID_PAT.search(ln) and not TRACE_NOISE.search(ln):
                ids += 1
            if NARRATIVE_PAT.search(ln):
                narr += 1

    total = sum(len(v) for v in noun_hits.values())
    # 词表不全时不能报「0 处」——0 是「查过且没有」，未查是「没查」。两个意思混在一格里，
    # 就是「查不下去 ＝ 通过」在输出层的同型错误（2026-11-20 冷启动实测·问题 3）。
    noun_cell = "**未查**（无词表）" if missing else "%d 处（%d 个词）" % (total, len(noun_hits))
    print("[triage] 扫描 %d 个文件 ｜ 专名命中 %s ｜ 疑似叙事行 %d ｜ 硬问题 %d ｜ 提示 %d"
          % (nfiles, noun_cell, narr, len(hard), len(soft)))
    if ids:
        print("[triage] 台账编号 %d 处——**按 README 声明保留作溯源指针，不计入硬问题**；"
              "换一个项目用这份东西，先想清楚要不要留。" % ids)

    for w, locs in sorted(noun_hits.items(), key=lambda kv: -len(kv[1])):
        print("    · %-12s %d 处  %s" % (w, len(locs), "、".join(locs[:3])))
    for kind, rel, i, snip in hard:
        print("    ✗ [%s] %s:%d  %s" % (kind, rel, i, snip))
    for kind, rel, i, snip in soft[:15]:
        print("    ⚠ [%s·提示] %s:%d  %s" % (kind, rel, i, snip))
    if len(soft) > 15:
        print("    ... 路径提示另 %d 处（多半是示例；真泄露请人看）" % (len(soft) - 15))

    # ---- 建议等级（提示，不是判定）----
    if hard:
        level, why = "—", "有硬问题（密钥／项目痕迹），先修再谈等级"
    elif missing:
        level, why = "?", "词表不全，无法给候选；按三问答一次"
    elif total >= 5 or (narr >= 3 and total >= 1):
        level, why = "C", "专名 %d 处＋叙事行 %d，疑似项目内容本体" % (total, narr)
    elif total >= 1:
        level, why = "B", "专名 %d 处，方法可迁移但举例带专名" % total
    else:
        level, why = "A", "0 专名（叙事行 %d 不构成内容本体）" % narr

    print("\n[triage] 建议等级：%s —— %s" % (level, why))
    print("[triage] **这是提示不是判定。** 等级写进 E0 登记第 9 项，由人定。")
    print("[triage] ⚠ 边界：**词表之外的专名，本工具查不出。** 只查得出已知的词——"
          "这正是 2026-11-10 那次泄露的形态（三个组织名三组词表都没收）。"
          "词表外的，只能靠 E0·1 那三问由人判。")
    if level == "C":
        print("[triage] C 级不进打包范围；**不许打码后再发**。")
    # 2026-11-20（冷启动实测·问题 1）：原来词表不全也 exit 0，等于把「没查成」说成「通过」。
    # 任何拿它写 CI、或让 AI 判「过没过」的人，都会拿到 0 当真。与 `_leakscan.py` 对齐：退出码 2。
    code = 1 if hard else (2 if missing else 0)
    if missing:
        print("[triage] ⛔ 结论：**%s**——退出码 %d，**这不是通过**。"
              % ("有硬问题，先修硬问题" if hard else "未判定（词表不全）", code))
    return code


if __name__ == "__main__":
    sys.exit(main())
