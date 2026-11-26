# -*- coding: utf-8 -*-
"""_links.py — 这个仓库自己引用的路径，到底存不存在。

用法：
    python gate/_links.py            # 只看结论
    python gate/_links.py --each     # 逐条列
退出码：`0` 干净 ／ `1` 有断链 ／ `2` 文件都找不到（没查成，不算通过）

完整说明：docs/maintain/代码内长文档/templates/checks/_links.py.md
"""

import io
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass  # 吞：输出流不支持 reconfigure 时保留原编码，不让输出配置阻断检查。

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_cfg():
    # 故意重复：可单独搬运，见 README
    """同目录 `checks.config.json` 有就用，没有就用通用缺省（2026-11-16 脱参数）。"""
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

EXTS = tuple(CFG.get("scan_exts", [".md", ".py", ".json", ".txt", ".html"]))
# **本仓库自己的一级目录**，运行时扫出来——不写死。
# 写死过一次，后果是：这个库里没有 `00_原著/`，于是 `00_原著/xxx` 全被当成
# 「读者项目里的路径」放过；而到了项目库里它恰恰是最该查的那个目录。
# 让目录自己说话：ROOT 下面有什么，什么就是本仓库的（`.git` 之类除外）。
OWN_TOP = tuple(sorted(
    d + "/" for d in os.listdir(ROOT)
    if os.path.isdir(os.path.join(ROOT, d)) and not d.startswith(".") and d != "__pycache__"
))
# 这个目录下的 md 讲的全是「装完之后你的项目长什么样」，里面每个路径都是**目标状态**，
# 不是本仓库路径。查它只会报假断链，而且会把「安装说明写得对不对」和
# 「本仓库引用通不通」搅成一件事。
SKIP_REF = tuple(CFG.get("links", {}).get("skip_ref", []))
# 宿主／工具的记忆与缓存目录（以点开头），不是这个项目的文档——里面指向的东西早年叫别的名字，
# 拿它当引用查，等于拿草稿纸上的涂鸦去对成稿。
SKIP_DIRS = set(CFG.get("skip_dirs", ["__pycache__", "node_modules"]))
# 以点开头的目录一律不扫：那是宿主／工具自己的缓存与记忆，不是这个项目的文档。
# **不写死具体名字**——换宿主就失效的那种写法，正是这套检查存在的理由。
# 文件里出现这几个词，视为「已声明含项目实例」，命中降级为提示
DECLARED = tuple(CFG.get("links", {}).get("declared_phrases", ["项目实例", "带走后不存在"]))

CODE_SPAN = re.compile(r"`([^`\n]{2,120})`")



def load_allow():
    # 故意重复：可单独搬运，见 README
    """读 `gate/links_allow.txt`。没写理由的行不算（与 `leak_allow.txt` 同一条纪律）。"""
    path = CFG.get("links", {}).get("allow_file") or os.path.join(HERE, "links_allow.txt")
    if not os.path.isabs(path):
        path = os.path.join(ROOT, path)
    allow, noreason = {}, []
    if not os.path.isfile(path):
        return allow, noreason
    with io.open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            left, why = s.split("=", 1)
            why = why.strip()
            if "→" not in left:
                continue
            who, where = [x.strip() for x in left.split("→", 1)]
            if not why:
                noreason.append(left.strip())
                continue
            allow[(who, where)] = why
    return allow, noreason


def walk_md():
    # 故意重复：可单独搬运，见 README
    out = []
    for dp, dn, fns in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in fns:
            if fn.lower().endswith(".md"):
                out.append(os.path.join(dp, fn))
    return sorted(out)


def candidates(text):
    # 故意重复：可单独搬运，见 README
    """从一段 md 里取出「看起来是指向本仓库某个文件的路径」。"""
    seen, out = set(), []
    for m in CODE_SPAN.finditer(text):
        s = m.group(1).strip()
        if s in seen:
            continue
        s2 = s.replace("\\", "/")
        if "/" not in s2:
            continue
        if not s2.startswith(OWN_TOP):
            continue
        if not s.lower().endswith(EXTS):
            continue
        if " " in s or "http" in s or "<" in s or ">" in s or "*" in s:
            continue
        if "…" in s or "·" in s:
            continue
        seen.add(s)
        out.append(s.replace("\\", "/"))
    return out


# `[类别]名字` 这种引用不带斜杠，第一遍（只认带斜杠的路径）看不见。
# **窄口径**：只查这些类别前缀。放开到所有裸名，实测 199 个候选里大半是
# 模型名（high_aes_...）、截断的资产名（_06_20261105.jpg）、标签（[scope] [补·画]）——
# 红了就变日常，闸等于死。C8 当年被判「不准进闸」也是这个理由。
CAT = ("[标准]", "[台账]", "[方法]", "[视图]", "[诊断]", "[报告]", "[提案]", "[交接]",
       "[抉择]", "[审计]", "[对比]", "[排查]", "[定形]", "[回执]", "[填表]", "[项目]",
       "[世界]", "[人物]", "[台卡]", "[确认]", "[对接]", "[对账]")
# 明写了「还没建」的不算断链——**声明的欠账不是断链**，把它当红，
# 等于逼人删掉那句「待建」，欠账就从纸上消失了。
DEBT = ("待建", "待立", "待补", "未建", "拟建", "计划建")


def scan_brackets(files, allow):
    # 故意重复：可单独搬运，见 README
    """第二遍：`[类别]xxx` 的落点在不在。返回 (命中, 候选数)。"""
    stems = set()
    for dp, dn, fns in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in fns:
            stems.add(os.path.splitext(fn)[0])

    hits, soft, checked = [], [], 0
    for fp in files:
        rel = os.path.relpath(fp, ROOT).replace("\\", "/")
        if rel.startswith(SKIP_REF):
            continue
        try:
            text = io.open(fp, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        declared = any(k in text for k in DECLARED)
        for m in CODE_SPAN.finditer(text):
            s = m.group(1).strip()
            if "/" in s or "\\" in s:
                continue
            if any(c in s for c in "*?<> …|"):
                continue
            if not s.startswith(CAT):
                continue
            body = s[next(len(c) for c in CAT if s.startswith(c)):]
            if len(body.strip()) < 3:
                continue
            base = re.sub(r"_v\d+(\.\d+)?$", "", os.path.splitext(body)[0]).strip()
            if not base:
                continue
            checked += 1
            if any(base in st for st in stems):
                continue
            around = text[max(0, m.start() - 30):m.end() + 20]
            if any(k in around for k in DEBT):
                continue
            if (rel, s) in allow:
                continue
            # 文件自己写着「这些是项目实例、带走后不存在是正常的」→ 降级为提示。
            # 与第一遍同一条规矩：**声明过的缺席不算断**，没声明的才算。
            (soft if declared else hits).append((rel, s))
    return hits, soft, checked


def main():
    args = sys.argv[1:]
    each = "--each" in args

    files = walk_md()
    if not files:
        print("[links] ⛔ 一个 md 都没找到——**这一项没查成，不算通过。**", file=sys.stderr)
        return 2

    allow, noreason = load_allow()
    hard, soft, checked, pardoned = [], [], 0, 0
    for fp in files:
        rel = os.path.relpath(fp, ROOT).replace("\\", "/")
        if rel.startswith(SKIP_REF):
            continue
        try:
            text = io.open(fp, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        cands = candidates(text)
        if not cands:
            continue
        declared = any(k in text for k in DECLARED)
        for c in cands:
            checked += 1
            if os.path.exists(os.path.join(ROOT, c)):
                continue
            if (rel, c) in allow:
                pardoned += 1
                continue
            (soft if declared else hard).append((rel, c))

    bhard, bsoft, bchecked = scan_brackets(files, allow)
    print("[links] 扫 %d 份 md ｜ 候选路径 %d 条 ｜ 类别名 %d 条 ｜ 豁免 %d 条"
          % (len(files), checked, bchecked, pardoned))
    # 自报范围（本项目的规矩：没 `[scope]` 的绿不认——不懂正则的人唯一能审的维度）。
    print("[scope] 扫 %d 份 md（跳过 %s）｜ 候选 %d 条"
          % (len(files), "／".join(sorted(SKIP_DIRS)), checked))
    print("[scope] 判据：反引号里、以本仓库一级目录开头、带扩展名、无空格无通配的路径，"
          "在仓库里真的存在")
    print("[scope] 第二遍查「类别名」：`[标准]／[台账]／[方法]…` 开头、不带斜杠的引用，"
          "仓库里有没有名字含它的文件")
    print("[scope] **查不了**：引用内容对不对；只写文件名不带目录的（除类别名）；不在反引号里的；"
          "提交信息里的；名字写对了但指错对象的")
    if noreason:
        print("[links] ⚠️ `links_allow.txt` 里这几行没写理由，不算豁免：%s" % "、".join(noreason))
    if soft:
        print("[links] 其中 %d 处落在「已声明含项目实例」的文件里，降级为提示" % len(soft))
    if bsoft:
        print("[links] 类别名：%d 处落在「已声明含项目实例」的文件里，降级为提示" % len(bsoft))
    if bhard:
        print("[links] 类别名找不到落点：%d 处" % len(bhard))
        for rel, s in bhard:
            print("  ✗ %s → %s" % (rel, s))
    if each:
        for rel, c in hard:
            print("  ✗ %s → %s" % (rel, c))
        for rel, c in soft:
            print("  · %s → %s（已声明，提示）" % (rel, c))

    if hard or bhard:
        print("\n✗ 断链 %d 处（另有类别名 %d 处、提示 %d 处）" % (len(hard), len(bhard), len(soft)))
        print("[links] 修法：① 真该存在的 → 补文件；② 只是「名字」的 → 去掉路径前缀；")
        print("        ③ 是项目实例的 → 在文件开头加一句「本文出现的 xxx 是项目实例，带走后不存在是正常的」")
        return 1

    print("\n✅ 干净：%d 条候选路径全部存在（另有 %d 处提示）" % (checked - len(soft), len(soft)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
