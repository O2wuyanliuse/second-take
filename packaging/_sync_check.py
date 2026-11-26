# -*- coding: utf-8 -*-
"""_sync_check.py — 私库 → 骨架库的回流检查。

用法：
    python packaging/_sync_check.py                      # 自动找骨架库
    python packaging/_sync_check.py --skeleton <骨架库路径>
    python packaging/_sync_check.py --manifest <清单>

骨架库路径的取法（依次）：`--skeleton` → 环境变量 `SKELETON_ROOT`。**两者都没有就报错，不猜。**

退出码：`0` 全部对齐 ／ `1` 有不一致或该搬没搬 ／ `2` **骨架库路径找不到（未配置，不算通过）**

## 为什么单列一个脚本

2026-11-10 做过一次**一次性搬运**：把 `Agent框架/` 抽成骨架库的子集，搬得很干净。
搬完之后私库继续长（同步防断、`_doctor`、`_triage`、E0 第 9 项……），**骨架库冻结在那一天**。
没有清单与机检，就没人知道差了多少——**这就是「两库」变成两个世界的过程。**

## 它不做什么

**不自动同步。** 回流需要判断（哪些是专名、哪些该改写成通用表述），机器做不了。
它只回答一件事：**清单里这两份，现在是不是同一个东西。**
"""

import hashlib
import io
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
        # 吞：输出流不支持 reconfigure 时保留原编码，不让输出配置阻断检查。

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

DEFAULT_MANIFEST = os.path.join(HERE, "回流清单.txt")


def rel(path):
    return os.path.relpath(path, ROOT).replace("\\", "/")


def md5(path):
    try:
        return hashlib.md5(open(path, "rb").read()).hexdigest()
    except Exception:
        return None


def read_norm(path):
    """按「内容」读：先把 CRLF 归一成 LF 再比。

    **行尾不是内容。** 2026-11-12 盘点时，6 份文件被字节比较判成「大差异」——
    实际逐行完全一致，只是私库是 CRLF、骨架库是 LF（11-10 搬运时归一过）。
    这种假 diff 比漏报更坏：它把真差异淹在噪音里，人看一眼就懒得看了。
    """
    with open(path, "rb") as f:
        return f.read().replace(b"\r\n", b"\n")


def eol_style(path):
    """这份文件用什么行尾：CRLF ／ LF ／ 混合。只用于提示，不参与判定。"""
    with open(path, "rb") as f:
        d = f.read()
    crlf, lf = d.count(b"\r\n"), d.count(b"\n")
    if crlf and crlf == lf:
        return "CRLF"
    if crlf:
        return "混合"
    return "LF"


def parse_manifest(path):
    """返回 [(私库相对, 骨架库相对, 关系)]。`#` 后是注释。"""
    out = []
    for ln in io.open(path, encoding="utf-8").read().split("\n"):
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        body, _, comment = ln.partition("#")
        if "=" not in body:
            continue
        a, b = body.split("=", 1)
        relation = comment.strip().split("（")[0].split("(")[0].strip() or "同文"
        out.append((a.strip(), b.strip(), relation))
    return out


def leak_hits(path):
    """脱敏件里不许出现**资产文件名**或密钥。

    2026-11-12 立。起因是一次真的复发：`同步防断` 手工脱敏过，
    但为加一条规则从私库重拷，**脱敏成果被整份覆盖回来**——而清单把它标成
    「脱敏，不比对」，所以没有任何东西会发现。**「不比对」等于「不再保护」。**

    只查两类最硬的：带日期戳的资产名、密钥。台账编号不查——
    `README.md` 已声明保留编号作溯源指针，那是设计不是漏洞。
    """
    import re as _re
    FILE_PAT = _re.compile(r"[\w\u4e00-\u9fa5]{2,}_\d{8}_\d{4}")
    SECRET = _re.compile(r"(sk-[A-Za-z0-9]{12,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{12,})")
    out = []
    try:
        for i, ln in enumerate(io.open(path, encoding="utf-8", errors="replace"), 1):
            m = FILE_PAT.search(ln)
            if m and "示例" not in ln:
                out.append((i, "资产文件名", m.group(0)[:40]))
            m = SECRET.search(ln)
            if m:
                out.append((i, "密钥", m.group(0)[:12] + "…"))
    except Exception as e:
        raise RuntimeError("同步检查读取文件失败") from e
    return out


def find_skeleton(argv):
    if "--skeleton" in argv:
        i = argv.index("--skeleton")
        if i + 1 < len(argv):
            return argv[i + 1], "--skeleton"
    env = os.environ.get("SKELETON_ROOT")
    if env:
        return env, "环境变量 SKELETON_ROOT"
    # **不猜「私库父目录下叫什么」**（2026-11-12 清账时删）。
    # 那个名字只在本机成立，而这是要发出去的通用层脚本：
    # 猜对一次是运气，猜错一次是误导——别人看到「没找到」会以为自己路径给错了，
    # 其实是他根本没有这个约定。宁可让他显式给一次。
    return None, "未给（--skeleton 与环境变量 SKELETON_ROOT 都没有）"


def main():
    manifest = DEFAULT_MANIFEST
    if "--manifest" in sys.argv:
        i = sys.argv.index("--manifest")
        if i + 1 < len(sys.argv):
            manifest = sys.argv[i + 1]

    if not os.path.isfile(manifest):
        print("[sync] 清单读不到：%s" % manifest, file=sys.stderr)
        return 2

    skeleton, how = find_skeleton(sys.argv)
    if not skeleton or not os.path.isdir(skeleton):
        print("[sync] ⛔ 骨架库路径没找到（%s）—— **这一项没查成，不算通过。**" % how,
              file=sys.stderr)
        print("       指定法：`--skeleton <路径>` 或设环境变量 `SKELETON_ROOT`", file=sys.stderr)
        return 2

    pairs = parse_manifest(manifest)
    print("[sync] 私库　：%s" % ROOT)
    print("[sync] 骨架库：%s（%s）" % (os.path.abspath(skeleton), how))
    print("[sync] 清单　：%s ／ %d 条" % (os.path.basename(manifest), len(pairs)))

    missing, differ, ok, skipped, leaked = [], [], [], [], {}
    eol_warn = []
    for src, dst, relation in pairs:
        src_p = os.path.join(ROOT, src)
        dst_p = os.path.join(skeleton, dst)
        if not os.path.exists(src_p):
            missing.append((src, "清单失效：私库这边没有这份文件"))
            continue
        if not os.path.exists(dst_p):
            missing.append((dst, "该回流但骨架库还没有（关系=%s）" % relation))
            continue
        if relation.startswith("脱敏") or relation.startswith("生成"):
            hits = leak_hits(dst_p) if relation.startswith("脱敏") else []
            if hits:
                leaked[dst] = hits[:3]
            else:
                skipped.append((dst, relation))
            continue
        if read_norm(src_p) != read_norm(dst_p):
            differ.append(dst)
            continue
        # 内容一致但行尾不同：只提示。两库的行尾策略本来就不统一，
        # 拿它当「不一致」会天天红，红成日常=没人看（同 `_cost` 的「别让红变日常」）。
        if eol_style(src_p) != eol_style(dst_p):
            eol_warn.append((dst, eol_style(src_p), eol_style(dst_p)))
        ok.append(dst)

    print("[sync] 同文一致 %d ／ 脱敏干净 %d ／ 缺 %d ／ 不一致 %d ／ **脱敏件带痕迹 %d**"
          % (len(ok), len(skipped), len(missing), len(differ), len(leaked)))

    for name, why in missing:
        print("  ✗ %s —— %s" % (name, why))
    for name, a, b in eol_warn:
        print("  · %s —— 内容一致，但行尾不同（私库 %s ／ 骨架库 %s），不影响判定" % (name, a, b))
    for name in differ:
        print("  ✗ %s —— 两边内容不一致（私库改了没回流？）" % name)
    for name, hits in leaked.items():
        print("  ✗ %s —— 标着「脱敏」，里面还有真东西：" % name)
        for ln, kind, snip in hits:
            print("      %d 行 [%s] %s" % (ln, kind, snip))
    for name, relation in skipped:
        print("  · %s —— %s，不比对内容（但过泄漏闸）" % (name, relation))

    if missing or differ or leaked:
        print("\n怎么修：该回流的那份，脱敏后复制到骨架库；清单失效的那条，从清单里删掉。")
        return 1

    print("\n✅ 清单里该一致的都一致；脱敏那几份不比对内容，但都过了泄漏闸。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
