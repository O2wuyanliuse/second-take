# -*- coding: utf-8 -*-
"""_orphan.py · 孤儿件检查（谁都没引用）

定位
    2026-11-03 23:35 建。起因：`00_原著/_index.md` 立起来之后，**索引本身
    也没人查**——新件建完补不补那一行，全靠记性。作者要求收工做孤儿检查。

判定
    一个 .md 文件是孤儿，当且仅当：**除了它自己，没有任何文件提到它的名字。**

    两级：
      全孤儿   谁都没提，连索引都没有        → 基本等于白建
      半孤儿   只有索引提了，正文／台账没引用 → 索引里挂着，但流程不走它

排除
    _原始归档 / 备份 / node_modules / 视图件（html、js 由别的机制管）

用法
    python _orphan.py            # 只报全孤儿与半孤儿
    python _orphan.py --all      # 连引用数一起列，便于抽查
    python _orphan.py --py       # 只看脚本：零引用的 .py（不判红）
"""

# ---- 输出编码兜底（2026-11-05）--------------------------------------------
# 某些 AI 运行环境会注入 PYTHONUTF8／PYTHONIOENCODING，会把这条崩溃遮住；
# 换台机器（gbk 默认）跑到 print 带 ✅ 的那一行就 UnicodeEncodeError。
# 探针必须在 `env -u PYTHONUTF8 -u PYTHONIOENCODING` 下跑，否则整类 bug 测不出。
import sys as _encsys
if hasattr(_encsys.stdout, "reconfigure"):
    _encsys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _encsys.stderr.reconfigure(encoding="utf-8", errors="replace")


import io
import os
import sys

from _ignore import ignored_dirs, is_ignored
from _links import walk_md as _walk_md

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 扫 md 时跳过的目录（名字按配置，见 `gate/_ignore.py`）——不再写死某个项目的归档目录名
SKIP_DIRS = ignored_dirs()
# README 是入口：**不作为被检查对象**，但**必须作为引用源**参与扫描
# （2026-11-03 23:40 修：首版把 README 整份跳过，导致「README 里写了路径」不算引用，
#   于是刚接好的入口仍被判半孤儿——排除粒度搞错了，排除的是"被引用"，不是"能引用"）
SKIP_AS_TARGET = {"README.md"}
INDEX_NAMES = {"_index.md"}         # 索引本身不算"流程引用"


# ---- 脚本孤儿（2026-11-13 加）-----------------------------------------------
# 为什么单开一个模式：这个检查原来只查 .md，于是「这脚本还有没有用」
# 只能靠人 grep——不敢删，就一直留着。2026-11-13 实测：93 个脚本里有一批
# 谁也说不清在不在用。**不敢删的垃圾比垃圾本身更贵。**
PY_SKIP = tuple(sorted(ignored_dirs())) + ("attic",)


def scan_py():
    """扫脚本：既没被任何 md 提到、也没被别的脚本 import 的，报出来。

    判据同 md 那条：**它下次还会被打开吗？** 会→留着；不会→归档。
    **这个模式不判红**（退出码恒 0）——历史脚本是过程，不是问题；
    它只回答「哪些是我不敢删的」，删不删由人定。
    """
    import glob as _g
    import re as _re

    pys = []
    for p in _g.glob(os.path.join(ROOT, "**", "*.py"), recursive=True):
        rel_p = os.path.relpath(p, ROOT).replace("\\", "/")
        if any(rel_p.startswith(d) for d in PY_SKIP):
            continue
        pys.append(rel_p)

    blob = []
    for p in _g.glob(os.path.join(ROOT, "**", "*.md"), recursive=True):
        rel_p = os.path.relpath(p, ROOT).replace("\\", "/")
        if is_ignored(rel_p):
            continue
        try:
            blob.append(open(p, encoding="utf-8", errors="replace").read())
        except OSError:
            pass
    blob = "\n".join(blob)

    imported = set()
    for rel_p in pys:
        try:
            t = open(os.path.join(ROOT, rel_p), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for m in _re.finditer(r"^\s*(?:from|import)\s+([A-Za-z_][\w.]*)", t, _re.M):
            imported.add(m.group(1).split(".")[0])

    orphan = []
    for rel_p in pys:
        stem = os.path.basename(rel_p)[:-3]
        if stem in imported or stem in blob:
            continue
        orphan.append(rel_p)

    print("脚本孤儿检查：扫 %d 个 .py（跳过 %s）" % (len(pys), "／".join(PY_SKIP)))
    if not orphan:
        print("\n✅ 没有零引用脚本——每个都至少被一份 md 提到或被别的脚本 import。")
        return 0
    print("\n零引用的 %d 个（没被 md 提到、也没被 import）：" % len(orphan))
    for rel_p in orphan:
        print("   %s" % rel_p)
    print("\n小字：")
    print("  ① 「零引用」不等于「没用」——一次性补丁、外部项目件正常就该零引用。")
    print("  ② 真正要问的是：**它下次还会被打开吗？** 不会就归档，别留着当包袱。")
    print("  ③ 归档目录已排除：%s" % "／".join(PY_SKIP))
    print("  ④ 这个模式不判红（退出码恒 0）——历史脚本是过程，不是问题。")
    return 0


def main():
    if "--py" in sys.argv:
        return scan_py()
    show_all = "--all" in sys.argv
    # `--only a.md b.md`：只判这几个文件（pre-commit 传「这次新加的 md」）。
    # **为什么需要这个模式**（2026-11-08 00:1x，`G-492`）：
    #   全库模式报 38 份全孤儿，其中绝大多数是**历史阶段的过程稿**
    #   （第二卷改写稿／草稿／竖切片测试／零基线测试）——它们当时有用，现在没人打开，
    #   **这不是问题，是过程**（工具自己的小字②就写着这句话）。
    #   而闸真正要防的是另一件事：**新建一份件，忘了在索引里补那一行**。
    #   那件事只在「新增」这一瞬间可判，一旦攒了两个月就变成 38 份噪音。
    #   所以：全库模式留给人看（`python _orphan.py`），闸里只跑 `--only`。
    has_only = "--only" in sys.argv
    only = []
    if has_only:
        _i = sys.argv.index("--only")
        only = [x for x in sys.argv[_i + 1:] if not x.startswith("--")]
        if not only:
            # 写了 `--only` 但这次没有新增 md → 不是「全库判一遍」，是「没事做」。
            # 不特判的话它会掉回全库模式、报 38 份历史孤儿、退出码 1 ——
            # **一个每天都在红的闸，第三次就被人关掉。**
            print("孤儿检查（--only）：这次没有新增 md，跳过。")
            return 0
    all_md = _walk_md(ROOT, SKIP_DIRS, include_hidden=False, sort=False)  # 全部：作为引用源
    files = [p for p in all_md if os.path.basename(p) not in SKIP_AS_TARGET]
    # ⚠ `only` 只收窄「被判的对象」，**引用源仍是全部 md**——
    #   不然新建的件永远找不到「谁提到它」，因为可能提到它的是份老文件。
    if only:
        want = {os.path.normcase(os.path.normpath(os.path.join(ROOT, o.replace("/", os.sep))))
                for o in only}
        files = [p for p in files if os.path.normcase(os.path.normpath(p)) in want]
        if not files:
            print("孤儿检查（--only）：给的 %d 个文件里没有 md，或都不在扫描范围内。" % len(only))
            return 0

    texts = {}
    for p in all_md:
        try:
            texts[p] = io.open(p, encoding="utf-8").read()
        except (UnicodeDecodeError, IOError):
            texts[p] = ""

    stems = {}
    for p in files:
        stems[p] = os.path.splitext(os.path.basename(p))[0]

    rows = []
    for p in files:
        stem = stems[p]
        hits_all, hits_flow = [], []
        for q in all_md:
            if q == p:
                continue
            if stem in texts[q]:
                hits_all.append(q)
                if os.path.basename(q) not in INDEX_NAMES:
                    hits_flow.append(q)
        rows.append((p, len(hits_all), len(hits_flow), hits_all))

    full = [r for r in rows if r[1] == 0]
    half = [r for r in rows if r[1] > 0 and r[2] == 0]

    rel = lambda p: os.path.relpath(p, ROOT).replace(os.sep, "/")

    print("=" * 70)
    if only:
        print("孤儿检查（只判新增）   %d 份 ｜ 引用源 %d 份 md" % (len(files), len(all_md)))
    else:
        print("孤儿件检查   共 %d 份 md（全库模式，供人看，不进闸）" % len(files))
    # 自报范围（项目规矩：没有 `[scope]` 的绿不认）
    print("[scope] 判对象 %d 份 ｜ 引用源 %d 份 md ｜ 跳过目录 %d 个（%s）｜ 跳过目标 %d 种（%s）"
          % (len(files), len(all_md), len(SKIP_DIRS), "、".join(sorted(SKIP_DIRS)),
             len(SKIP_AS_TARGET), "、".join(sorted(SKIP_AS_TARGET))))
    print("[scope] 判据：文件名（去扩展名）在**别的任何一份 md** 里出现过 = 有引用。"
          "全孤儿＝连索引都没提。")
    print("[scope] **查不了**：提了但提错；同名不同路径的算不算；只在 git 提交信息里提到的不算引用；"
          "「这份件还该不该存在」只能人判（判据：下次还会被打开吗）")
    print("=" * 70)

    if full:
        print("\n全孤儿（谁都没提，连索引都没有）  %d 份" % len(full))
        for p, a, f, _ in full:
            print("  ✗ %s" % rel(p))
    else:
        print("\n全孤儿  0 份  OK")

    if half:
        print("\n半孤儿（只有索引提了，流程不走它）  %d 份" % len(half))
        for p, a, f, _ in half:
            print("  ~ %s" % rel(p))
    else:
        print("\n半孤儿  0 份  OK")

    if show_all:
        print("\n全部引用数（降序）")
        for p, a, f, _ in sorted(rows, key=lambda x: (-x[2], x[0])):
            print("  %3d / %3d  %s" % (f, a, rel(p)))

    print("\n小字：")
    print("  ① 只查「名字有没有被提到」，查不了「提了但提错」。")
    print("  ② **任务专用件在别的阶段必然是孤儿，那不是白建。**")
    print("     例：`Agent框架/环节推进表_大纲建模_v1.md` 只管「建模/验证」那条线，")
    print("     做预告片时它就该是孤儿；判它死没死，要看它对应的任务还会不会发生。")
    print("  ③ 判据：**这份东西下次还会被打开吗？** 会→留着；不会→归档或删。")
    # **全库模式永远不红**（2026-11-08 00:1x，`G-492`）：
    #   它列的是「谁都没被提」，而 38 份里绝大多数是历史过程稿——那是过程，不是问题。
    #   把「全库有孤儿」当红，等于每次提交都红，第三次就被人关掉。
    #   判红只发生在 `--only`：**这次新加的件，有没有人提它**。
    if not has_only:
        return 0
    return 1 if full else 0


if __name__ == "__main__":
    sys.exit(main())
