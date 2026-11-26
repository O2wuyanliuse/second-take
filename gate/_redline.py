# -*- coding: utf-8 -*-
"""_redline.py · 版权与开源红线守门

定位
    2026-11-01 22:00 建。起因：作者说「定在清单里吧，不然不能指望你每次新窗口
    都记得这个」——但**清单本身也会被忘**。所以这份东西不给人读，给必经路径读。

    挂进 pre-commit。绕不过去。

为什么是这几项（不是别的）
    只查**能离线判的、且判错代价高的**。三条原则：

      ① 不查"要不要发布"——发布是人的决定，机器不知道
      ② 只查**前兆**——开源和公开都有可观测的前兆动作（加 LICENSE、
         放掉媒体排除、把 token 拼进 URL）
      ③ 正常状态下**必须全绿**——会定期吵的检查等于没有检查

    ⚠ 本脚本查不了的事，比查得了的重要：
       · 平台协议说了什么（看不到）
       · 这一句引用算不算"关键信息点"（要人判）
       · 声明到底贴没贴到三个位置（要看成品）
      这些在 `发布前检查清单.md` §一，**靠人，别指望这台机器**。

检查项（4 项）
    R1 红线文件与清单在场         缺 → 阻断（新窗口能不能知道这事，全靠这两份）
    R2 没有 LICENSE 类文件        有 → 提示（加了就是在授予权利，当前状态不该有）
    R3 .gitignore 媒体排除规则完整 被删 → 提示（媒体入库不是版权问题，但是打包前兆）
    R4 无凭据泄漏                 有 → 阻断（token 进了文件或 remote，直接有害）

退出码
    1 = 阻断 ｜ 2 = 只剩提示 ｜ 0 = 全绿

用法
    python _redline.py
"""

from __future__ import print_function

import io
import json
import os
import re
import sys

from _ignore import ignored_dirs

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
ROOT = os.path.dirname(HERE)

# ── 配置：这个仓库是「私库」还是「公开库」 ──
# R2 的期望值两头相反，而它属于**项目绑定**，不属于判据形状：
#   私库：不该有 LICENSE（授权方不止作者一人，默认保留所有权利）
#   公开库：必须有 LICENSE（不加就等于没授权，别人不能用）
# 所以用一份配置切，而不是把规则改成「随便」。
DEFAULTEDGE = os.path.join(ROOT, "redline.json")


def is_public():
    try:
        d = json.load(io.open(DEFAULTEDGE, encoding="utf-8"))
        return bool(d.get("公开库"))
    except Exception:
        return False


# ── R1 必在场的两份 ──
REQUIRED = [
    ("版权与开源红线.md", "原则：什么能公开、什么永远不能"),
    ("发布前检查清单.md", "动作：发布前逐项打勾"),
]

# ── R2 出现即提示的文件名 ──
LICENSE_NAMES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "NOTICE")
LICENSE_NAMES += tuple(n + ".md" for n in ("LICENSE", "COPYING", "NOTICE"))

# ── R3 .gitignore 里必须保留的媒体排除规则（抽样，不要求全对）──
GITIGNORE_MUST = ["*.mp4", "*.png", "*.jpg", "*.psd", "*.zip"]

# ── R4 凭据形态 ──
# URL 里夹带口令： https://user:token@gitee.com/...  或  https://user:token@github.com/...
CRED_IN_URL = re.compile(r"://[^/:\s@]+:[0-9A-Za-z_\-]{16,}@")
# 扫描的工作区文件后缀
SCAN_EXT = (".md", ".txt", ".json", ".yml", ".yaml", ".py", ".cfg", ".ini")
# 不扫的目录（名字按配置，见 `gate/_ignore.py`）
SKIP_DIRS = ignored_dirs()

VERBOSE = "-v" in sys.argv or "--verbose" in sys.argv


def read(path):
    with io.open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def check_r1(results):
    """红线文件与清单在场。"""
    missing = []
    for name, why in REQUIRED:
        p = os.path.join(ROOT, name)
        if not os.path.isfile(p):
            missing.append((name, why))
        elif os.path.getsize(p) < 500:
            missing.append((name + "（内容少于 500 字节，疑似被清空）", why))

    if missing:
        results.append((
            "R1", "红线文件在场", 1,
            "缺 %d 份：%s" % (len(missing), "、".join(n for n, _ in missing)),
            "这两份是新窗口知道「不能开源」的唯一入口。缺了就等于没立过这条规矩。",
        ))
    else:
        results.append(("R1", "红线文件在场", 0, "2 份齐全", None))


def check_r2(results):
    """没有 LICENSE 类文件。

    注意：这不是"不许有"，是"有了要你确认"。
    当前项目的正确状态是**不加**——默认「保留所有权利」。
    加了 LICENSE 就是在授予权利，而授权方本来就不是作者一个人。
    """
    found = []
    for d in (ROOT, os.path.join(ROOT, "00_原著"), os.path.join(ROOT, "Agent框架")):
        if not os.path.isdir(d):
            continue
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for n in names:
            if n.upper() in {"LICENSE", "COPYING", "NOTICE"} or \
               n.upper().startswith(("LICENSE.", "COPYING.", "NOTICE.")):
                found.append(os.path.relpath(os.path.join(d, n), ROOT))

    if is_public():
        if found:
            results.append(("R2", "有 LICENSE 类文件", 0,
                            "有（公开库应该有的）：%s" % "、".join(found), None))
        else:
            results.append((
                "R2", "有 LICENSE 类文件", 1,
                "公开库没有 LICENSE",
                "没有许可＝默认保留所有权利，别人**不能合法使用**——"
                "那就不是开源仓库，只是公开了源码。补一份 LICENSE。",
            ))
        return

    if found:
        results.append((
            "R2", "无 LICENSE 类文件", 2,
            "发现 %d 份：%s" % (len(found), "、".join(found)),
            "加了 LICENSE 就是在授予权利。原著版权不全在你手上，"
            "默认「保留所有权利」才是当前要的状态。"
            "**请先读 `版权与开源红线.md` §2.3，确认这是有意为之再提交。**",
        ))
    else:
        results.append(("R2", "无 LICENSE 类文件", 0, "无（正确状态）", None))


def check_r3(results):
    """媒体排除规则仍在。"""
    p = os.path.join(ROOT, ".gitignore")
    if not os.path.isfile(p):
        results.append((
            "R3", "媒体排除规则完整", 2,
            ".gitignore 不存在",
            "没有排除表，媒体会全部入库。不是版权问题，但会让仓库从 3.6MB 涨到 100MB+。",
        ))
        return

    txt = read(p)
    missing = [r for r in GITIGNORE_MUST if r not in txt]
    if missing:
        results.append((
            "R3", "媒体排除规则完整", 2,
            "缺 %d 条：%s" % (len(missing), "、".join(missing)),
            "排除表被改动过。若不是有意的，改回去；若是有意的，写进跟进通道说明理由。",
        ))
    else:
        results.append(("R3", "媒体排除规则完整", 0, "%d 条抽样全在" % len(GITIGNORE_MUST), None))


def check_r4(results):
    """凭据泄漏：URL 里夹带 token，写进了文件或 remote。"""
    hits = []

    # 4a .git/config 的 remote
    cfg = os.path.join(ROOT, ".git", "config")
    if os.path.isfile(cfg):
        for i, line in enumerate(read(cfg).split("\n"), 1):
            if CRED_IN_URL.search(line):
                hits.append((".git/config:%d" % i, "remote 地址里夹带了凭据"))
            elif "url = http" in line and "@" in line and "://" in line:
                # 形如 https://user@host/... （只有用户名，无害，跳过）
                pass

    # 4b 工作区文件
    nscan = 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.lower().endswith(SCAN_EXT):
                continue
            fp = os.path.join(dirpath, fn)
            try:
                if os.path.getsize(fp) > 2 * 1024 * 1024:
                    continue
                txt = read(fp)
            except (OSError, IOError):
                continue
            nscan += 1
            for i, line in enumerate(txt.split("\n"), 1):
                m = CRED_IN_URL.search(line)
                if m:
                    # 打码，别把凭据本身打印出来——但**保留用户名**，否则定位不到是哪个账号
                    raw = m.group(0)          # 形如  ://user:token@
                    head, _, _tail = raw.rpartition(":")
                    masked = head + ":***@"
                    hits.append((os.path.relpath(fp, ROOT) + ":%d" % i,
                                 "疑似凭据 %s" % masked))

    if hits:
        detail = "；".join("%s（%s）" % h for h in hits[:5])
        if len(hits) > 5:
            detail += "；…另 %d 处" % (len(hits) - 5)
        results.append((
            "R4", "无凭据泄漏", 1, detail,
            "把 token 从文件里删掉，改用 SSH（已配：`git@gitee.com:...`）。"
            "**若这个 token 已经提交过历史，删文件不算数——必须去平台吊销重发。**",
        ))
    else:
        results.append((
            "R4", "无凭据泄漏", 0,
            "扫 %d 个文件 ＋ .git/config，0 处" % nscan, None,
        ))


def main():
    print("── _redline · 版权与开源红线 ──")
    print("[scope] 模式：%s" % ("公开库（R2 反转为「必须有 LICENSE」）" if is_public() else "私库（R2：不该有 LICENSE）"))
    print("[scope] 查 4 项：R1 红线文件在场 ／ R2 %s ／ "
          % ("有 LICENSE 类文件" if is_public() else "无 LICENSE 类文件") +
          "R3 媒体排除规则 ／ R4 无凭据泄漏")
    print("[scope] 扫项目根 ＋ .git/config ＋ 全部 .md/.txt/.json/.py（跳过 .git/缓存目录/__pycache__）")
    print("[scope] **查不了**：平台协议内容、引用算不算关键信息点、声明贴没贴到三处——"
          "这三项在 `发布前检查清单.md` §一，靠人")
    print("")

    results = []
    for fn in (check_r1, check_r2, check_r3, check_r4):
        try:
            fn(results)
        except Exception as e:  # 单检查项崩了不该带走整页
            results.append(("??", fn.__name__, 2, "检查器异常：%s" % e, None))

    blocking = 0
    warning = 0
    for code, name, level, detail, advice in results:
        mark = {0: "✅", 1: "✗", 2: "⚠"}[level] if level in (0, 1, 2) else "⚠"
        print("%s %s %s：%s" % (mark, code, name, detail))
        if level == 1:
            blocking += 1
        elif level == 2:
            warning += 1
        if advice and (level > 0 or VERBOSE):
            print("    → %s" % advice)

    print("")
    if blocking:
        print("✗ %d 项阻断。红没有去向，就是没清。" % blocking)
        return 1
    if warning:
        print("⚠ %d 项提示——不阻断，但别当没看见。" % warning)
        return 2
    print("✅ 4 项全绿。**红线本身没被动过**——不代表这次发布合规，合规看清单。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
