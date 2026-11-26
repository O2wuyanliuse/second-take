# -*- coding: utf-8 -*-
"""_links.py — 这个仓库自己引用的路径，到底存不存在。

## 为什么要有它

`_anchor.py` 留在项目侧，查的是「项目文档引用的路径在不在」。**这个仓库没有它**，
于是通用层文档里写着 `00_原著/_mkview.py` 这种路径，一个字都不会报——
可它在骨架库里根本不存在。`11_分发说明` §四 立的「名字不带位置」，
在通用层内部反而是无闸的。

## 它查什么

md 里用反引号包住、**同时满足下面四条**的才算候选：

1. 含 `/`（不带路径分隔符的一律当「名字」，不管）
2. 以 `.md` / `.py` / `.json` / `.txt` / `.html` 结尾
3. 不含空格（含空格的多半是命令，`python gate/_gate.py` 这种）
4. 不含 `http` / `<` / `>` / `*` / `…` / `·`（URL、占位、通配、省略号）

候选里，`os.path.exists` 为假的报出来。

## 它故意不做什么

- **不判断引用内容对不对**，只判断文件在不在。
- **不认识「项目实例」**。有些文档开头写着「本文出现的 `00_原著/xxx` 是项目实例，带走后不存在是正常的」——
  这种声明是合法的，脚本不猜。**带这类声明的文件，命中降级成提示**，由人看。
- **不查图片、不查链接语法**（`[文字](路径)`），那要解析 md，代价不成比例。

用法：
    python gate/_links.py            # 只看结论
    python gate/_links.py --each     # 逐条列
退出码：`0` 干净 ／ `1` 有断链 ／ `2` 文件都找不到（没查成，不算通过）
"""

import fnmatch
import io
import json
import os
import re
import sys

from _ignore import ignored_dirs

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

EXTS = (".md", ".py", ".json", ".txt", ".html")
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
SKIP_REF = ("packaging/templates/",)
# 缓存目录（名字按配置，见 `gate/_ignore.py`）不是这个项目的文档——里面指向的东西
# 早年叫别的名字，拿它当引用查，等于拿草稿纸上的涂鸦去对成稿。
SKIP_DIRS = ignored_dirs()
# 文件里出现这几个词，视为「已声明含项目实例」，命中降级为提示
DECLARED = ("项目实例", "带走后不存在")
# 按**路径**声明「这属于项目实例」：骨架包不带、用户自建，存在与否都不判断链。
# 只在 `links_scope.json` 里改，不许为了消红改这个脚本（见维护方法 §9 v3.9）。
SCOPE_FILE = os.path.join(ROOT, "links_scope.json")

CODE_SPAN = re.compile(r"`([^`\n]{2,120})`")

# 裸文件名（不带斜杠）默认**不查**——项目层到处是「交接_当前进度.md」这种引用，放开会红成一片。
# 但通用层的入口件不一样：`安装.md` 被删之后，「打开包里的 `安装.md`」就成了一条死路，
# 而第一遍（只认带斜杠的路径）看不见它。2026-11-23 就是这么漏的。
# 所以这里列一份**很窄**的清单：库自身的入口件 ＋ v1.0.0 删掉的三份。
# 新名字要进这份清单，得先问一句：它是「谁都不该凭空发明」的入口件吗？
BARE_NAMES = (
    "README.md", "README.en.md", "AGENTS.md", "INDEX.md", "CHANGELOG.md",
    "CONTRIBUTING.md", "SECURITY.md", "CODE_OF_CONDUCT.md",
    "开工提示词.md", "发布前检查清单.md", "版权与开源红线.md", "剪辑引导.md",
    "安装.md", "从这里开始.txt", "使用说明.txt",
)


def bare_candidates(text):
    """反引号里、不带斜杠、且落在 `BARE_NAMES` 里的文件名。"""
    out = []
    for m in CODE_SPAN.finditer(text):
        s = m.group(1).strip()
        if "/" in s.replace("\\", "/"):
            continue
        if s in BARE_NAMES and s not in out:
            out.append(s)
    return out


def all_basenames():
    """仓库里所有文件名（跳过缓存目录）。用于判断裸名有没有落点。"""
    names = set()
    for dp, dn, fns in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        names.update(fns)
    return names



def load_scope():
    """读 `links_scope.json`：哪些路径属于「项目实例」——骨架包不带、用户自建。

    它们存在与否都不判断链，只降级为提示。判据没放宽：承认的是「这棵树本来就不带项目实例」这个事实。
    """
    try:
        with io.open(SCOPE_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return (), ()
    dirs = tuple(x for x in (data.get("instance_dirs") or []) if x)
    pats = tuple(x for x in (data.get("instance_files") or []) if x)
    return dirs, pats


def in_scope(c, dirs, pats):
    c = c.replace("\\", "/")
    if any(c.startswith(d) for d in dirs):
        return True
    return any(fnmatch.fnmatch(c, p) for p in pats)


def load_allow():
    """读 `gate/links_allow.txt`。没写理由的行不算（与 `leak_allow.txt` 同一条纪律）。"""
    path = os.path.join(HERE, "links_allow.txt")
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


def walk_md(root=ROOT, skip_dirs=SKIP_DIRS, include_hidden=True, sort=True):
    out = []
    for dp, dn, fns in os.walk(root):
        dn[:] = [d for d in dn if d not in skip_dirs and (include_hidden or not d.startswith("."))]
        for fn in fns:
            if fn.lower().endswith(".md"):
                out.append(os.path.join(dp, fn))
    return sorted(out) if sort else out


def candidates(text):
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
    """第二遍：`[类别]xxx` 的落点在不在。返回 (命中, 候选数)。"""
    stems = set()
    for dp, dn, fns in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
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
    scope_dirs, scope_pats = load_scope()
    hard, soft, checked, pardoned, scoped = [], [], 0, 0, 0
    bare_hard, bare_checked = [], 0
    basenames = all_basenames()
    for fp in files:
        rel = os.path.relpath(fp, ROOT).replace("\\", "/")
        if rel.startswith(SKIP_REF):
            continue
        try:
            text = io.open(fp, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        # 裸文件名先查：它不带斜杠，下面 candidates() 的 `"/" not in s2` 会整条放过。
        for s in bare_candidates(text):
            bare_checked += 1
            if s in basenames:
                continue
            if (rel, s) in allow:
                pardoned += 1
                continue
            bare_hard.append((rel, s))
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
            if in_scope(c, scope_dirs, scope_pats):
                scoped += 1
                soft.append((rel, c))
                continue
            (soft if declared else hard).append((rel, c))

    bhard, bsoft, bchecked = scan_brackets(files, allow)
    print("[links] 扫 %d 份 md ｜ 候选路径 %d 条 ｜ 裸文件名 %d 条 ｜ 类别名 %d 条 ｜ 豁免 %d 条"
          % (len(files), checked, bare_checked, bchecked, pardoned))
    # 自报范围（本项目的规矩：没 `[scope]` 的绿不认——不懂正则的人唯一能审的维度）。
    print("[scope] 扫 %d 份 md（跳过 %s）｜ 候选 %d 条"
          % (len(files), "／".join(sorted(SKIP_DIRS)), checked))
    print("[scope] 判据：反引号里、以本仓库一级目录开头、带扩展名、无空格无通配的路径，"
          "在仓库里真的存在")
    print("[scope] 第二遍查「裸文件名」：`安装.md` 这种不带斜杠的，只认 BARE_NAMES 里那几份"
          "（库入口件＋已删文档），仓库里没有同名文件就报")
    print("[scope] 第三遍查「类别名」：`[标准]／[台账]／[方法]…` 开头、不带斜杠的引用，"
          "仓库里有没有名字含它的文件")
    print("[scope] **查不了**：引用内容对不对；不在 `BARE_NAMES` 里的裸文件名；"
          "不在反引号里的；提交信息里的；名字写对了但指错对象的")
    if noreason:
        print("[links] ⚠️ `links_allow.txt` 里这几行没写理由，不算豁免：%s" % "、".join(noreason))
    if soft:
        print("[links] 其中 %d 处落在「已声明含项目实例」的文件里，降级为提示" % len(soft))
    if scoped:
        print("[links] 其中 %d 处属于「项目实例」（links_scope.json），降级为提示" % scoped)
    if bsoft:
        print("[links] 类别名：%d 处落在「已声明含项目实例」的文件里，降级为提示" % len(bsoft))
    if bare_hard:
        print("[links] 裸文件名找不到：%d 处" % len(bare_hard))
        for rel, s in bare_hard:
            print("  ✗ %s → %s" % (rel, s))
    if bhard:
        print("[links] 类别名找不到落点：%d 处" % len(bhard))
        for rel, s in bhard:
            print("  ✗ %s → %s" % (rel, s))
    # 阻断项**永远指名**：原来只在 `--each` 时打印，于是默认模式下报「断链 1 处」
    # 却不说哪一条——报了红却点不出位置，等于让人自己去 grep 全库。
    # 提示项（`soft`）仍然只在 `--each` 时展开，免得刷屏。
    if hard:
        print("[links] 断链：%d 处" % len(hard))
        for rel, c in hard:
            print("  ✗ %s → %s" % (rel, c))
    if each:
        for rel, c in soft:
            print("  · %s → %s（已声明，提示）" % (rel, c))

    if hard or bhard or bare_hard:
        print("\n✗ 断链 %d 处（另有裸文件名 %d 处、类别名 %d 处、提示 %d 处）"
              % (len(hard), len(bare_hard), len(bhard), len(soft)))
        print("[links] 修法：① 真该存在的 → 补文件；② 只是「名字」的 → 去掉路径前缀；")
        print("        ③ 是项目实例的 → 在文件开头加一句「本文出现的 xxx 是项目实例，带走后不存在是正常的」")
        return 1

    print("\n✅ 干净：%d 条候选路径全部存在（裸文件名 %d 条已核；另有 %d 处提示）"
          % (checked - len(soft), bare_checked, len(soft)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
