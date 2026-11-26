#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""release.py —— 发版动作的唯一入口：一次写三处（VERSION / latest.json / git tag）。

为什么要有它
------------
版本号散在三处（根目录 `VERSION`、`latest.json`、`git tag`）。手写三处，
第一次就会漂，漂了以后 `latest.json` 与 `tag` 对不上，用户被提醒升级却下到旧包。
这个脚本只做一件事：**三处由一次动作写出，写不完整就整体回滚。**

退出码（与全仓门禁语义一致）
----------------------------
0  写完了，可以打包上传
2  前置校验没过（缺东西 / 工作区脏 / 门禁红 / CHANGELOG 不合格 / 版本号不递增）——**一个字节都没写**
3  写的过程中失败（已回滚到原状）

口径
----
- 版本号唯一真值：本库的 `latest.json["version"]`；若根目录存在 `VERSION` 文件，它必须与之一致（不一致＝退出 2）。
- `CHANGELOG.md` **不由本脚本生成、不改写**：发版说明必须人写（AI 代写的说明等于广告词）。
  本脚本只做机器可判的格式检查：有 `## vX.Y.Z · 日期` 节、「对你有影响」1–3 条、禁词、无 commit hash。
- 本脚本不打包、不上传、不推 tag。推 tag 是人按的。

用法
----
    python tools/release.py --version 0.4.0 --channel stable --severity normal --dry-run
    python tools/release.py --version 0.4.0 --channel stable --severity normal
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# 中文输出在 GBK 控制台会乱码；统一按 UTF-8 写，乱码也不影响退出码。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
    # 吞：输出流不支持 reconfigure 时保留原编码，不让输出配置阻断检查。

# git 不在 PATH 时，允许用环境变量 GIT 指定绝对路径（不硬编码任何人的机器路径）。
GIT = os.environ.get("GIT") or shutil.which("git") or "git"

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "VERSION"
LATEST = ROOT / "latest.json"
CHANGELOG = ROOT / "CHANGELOG.md"
GATE = ROOT / "gate" / "_gate.py"


_OWNER_REPO = None


def repo_slug():
    """从 origin 推 owner/repo，不写死。仓库改名或搬家之后这里自动跟上。

    读不到就返回空串——**这里不退出**：本文件会被测试与发布判据 import，
    import 时退出等于「解压就能用」的包一解开就炸（0.5.4 的事故）。
    """
    url = subprocess.run([GIT, "remote", "get-url", "origin"],
                         capture_output=True, text=True).stdout.strip()
    m = re.search(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?/?$", url)
    return (m.group(1) + "/" + m.group(2)) if m else ""


def owner_repo():
    """用到才读一次。优先级：环境变量 SECOND_TAKE_OWNER > origin > 空串。"""
    global _OWNER_REPO
    if _OWNER_REPO is None:
        _OWNER_REPO = (os.environ.get("SECOND_TAKE_OWNER") or repo_slug()).strip()
    return _OWNER_REPO

BANNED = [
    "重构", "优化", "修复若干", "底层", "架构", "性能提升",
    "若干问题", "体验更佳", "稳定性增强",
]
MAX_ITEMS = 3
MAX_CHARS_PER_ITEM = 30


class Bad(Exception):
    """前置校验失败（退出 2）。"""


class Broken(Exception):
    """写入过程失败（退出 3，已回滚）。"""


# ---------------------------------------------------------------- helpers

def sh(*args, cwd=ROOT):
    cmd = list(args)
    if cmd and cmd[0] == "git":
        cmd[0] = GIT
    try:
        return subprocess.run(
            cmd, cwd=str(cwd),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    except FileNotFoundError:
        raise Bad("找不到 git（PATH 里没有）。请把 git 加进 PATH，或设环境变量 GIT 指向 git.exe。")


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def vtuple(s: str):
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", s.strip())
    if not m:
        raise Bad("版本号必须是 X.Y.Z 三段数字，给的是 %r" % s)
    return tuple(int(x) for x in m.groups())


def today() -> str:
    return __import__("datetime").date.today().isoformat()


# ---------------------------------------------------------------- checks

def check_git_clean():
    r = sh("git", "status", "--porcelain")
    if r.returncode != 0:
        raise Bad("git status 跑不起来（不是 git 仓库？）：%s" % r.stderr.strip()[:200])
    dirty = [ln for ln in r.stdout.splitlines() if ln.strip()]
    if dirty:
        raise Bad("工作区不干净，先提交或清掉这 %d 项：\n  %s"
                  % (len(dirty), "\n  ".join(dirty[:8])))
    name = sh("git", "config", "user.name").stdout.strip()
    mail = sh("git", "config", "user.email").stdout.strip()
    if not name or not mail:
        raise Bad("没配 git 用户身份（user.name / user.email 为空）——tag 会打不上，先配好再来。")


def check_gate():
    if not GATE.exists():
        # 查不下去不等于通过：找不到门禁就不许发版。
        raise Bad("找不到门禁脚本 %s —— 查不下去按未判处理，不许发版。" % GATE.relative_to(ROOT))
    r = sh(sys.executable, str(GATE))
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode == 0:
        return
    # 2026-11-21：本库是方法仓，17 项门禁里有 15 项的对象按设计不在本库（见
    # `gate_profile.json` 的「不适用」与「结案」），所以总闸永远退出 2。原实现把 2
    # 一律当红，结果是**这个库永远发不了版**——那不是严格，那是把闸焊死了。
    # 这里的规矩只有一条：**阻断必须是 0**。跳过与提示可以有，但必须把覆盖率印出来，
    # 不许让「17% 覆盖」悄悄溜过去。
    if r.returncode == 2 and "阻断 0" in out:
        summ = [l.strip() for l in out.splitlines() if "项" in l and "阻断" in l]
        print("  · 门禁 2：阻断 0，其余为跳过/提示（本库按设计没有那些对象）")
        for l in summ[-1:]:
            print("    %s" % l)
        return
    tail = "\n".join(out.splitlines()[-15:])
    raise Bad("门禁没过（退出码 %d）：\n%s" % (r.returncode, tail))


def load_latest():
    if not LATEST.exists():
        raise Bad("找不到 latest.json：本库不是发版库？")
    try:
        data = json.loads(read_text(LATEST))
    except Exception as e:
        raise Bad("latest.json 不是合法 JSON：%s" % e)
    if not data.get("version"):
        raise Bad("latest.json 里没有 version 字段")
    vtuple(data["version"])
    return data


def check_version_consistency(old: str, new: str):
    if VERSION_FILE.exists():
        cur = read_text(VERSION_FILE).strip().split()[0] if read_text(VERSION_FILE).strip() else ""
        if not cur:
            raise Bad("VERSION 文件是空的")
        if cur != old:
            raise Bad("VERSION(%s) 与 latest.json(%s) 已经不一致 —— 先人工对齐，再发版。" % (cur, old))
    else:
        print("  · 本库无 VERSION 文件，版本真值以 latest.json 为准")
    if vtuple(new) <= vtuple(old):
        raise Bad("新版本 %s 必须大于当前 %s" % (new, old))


def check_changelog(new: str, date: str):
    if not CHANGELOG.exists():
        raise Bad("找不到 CHANGELOG.md")
    lines = read_text(CHANGELOG).splitlines()
    head_pat = re.compile(r"^##\s*v%s\s*(?:·|-|—)?\s*%s" % (re.escape(new), re.escape(date)))
    idx = next((i for i, ln in enumerate(lines) if head_pat.match(ln.strip())), None)
    if idx is None:
        raise Bad("CHANGELOG 里没有本节：`## v%s · %s`（必须先人写发版说明再发版）" % (new, date))
    section = []
    for ln in lines[idx + 1:]:
        if re.match(r"^##\s", ln):
            break
        section.append(ln)
    body = "\n".join(section)

    m = re.search(r"^###\s*对你有影响\s*$", body, re.M)
    if not m:
        raise Bad("CHANGELOG 本节缺 `### 对你有影响` 小节")

    after = body[m.end():]
    stop = re.search(r"^###\s", after, re.M)
    items_block = after[: stop.start()] if stop else after
    items = [re.sub(r"^\s*(?:\d+[.、)]|[-*])\s*", "", ln).strip()
             for ln in items_block.splitlines() if re.match(r"^\s*(?:\d+[.、)]|[-*])\s+", ln)]
    items = [x for x in items if x]

    if not (1 <= len(items) <= MAX_ITEMS):
        raise Bad("`### 对你有影响` 必须是 1–%d 条（现在 %d 条）" % (MAX_ITEMS, len(items)))
    for it in items:
        plain = re.sub(r"[`*]", "", it)
        if len(plain) > MAX_CHARS_PER_ITEM:
            raise Bad("这条超过 %d 字，用户看不下去：%s" % (MAX_CHARS_PER_ITEM, plain[:40]))
        for w in BANNED:
            if w in plain:
                raise Bad("这条里有禁词「%s」：%s" % (w, plain[:40]))
        if re.search(r"\b[0-9a-f]{7,40}\b", plain):
            raise Bad("这条里出现 commit hash，用户不需要看这个：%s" % plain[:40])

    if not re.search(r"^###\s*(没动什么|内部)", body, re.M):
        raise Bad("CHANGELOG 本节缺 `### 没动什么`（或 `### 内部`）——必须交代「什么没碰」")


# ---------------------------------------------------------------- write

def build_latest(old_data: dict, new: str, date: str, channel: str, severity: str) -> dict:
    data = dict(old_data)
    data["version"] = new
    data["date"] = date
    data["channel"] = channel
    data["severity"] = severity
    owner = owner_repo()
    if not owner:
        raise Bad("推断不出 owner/repo：本目录没有 origin。发版时才需要它，二选一——"
                  "①git remote add origin git@github.com:<你>/<仓库>.git；"
                  "②设环境变量 SECOND_TAKE_OWNER=<你>/<仓库>。"
                  "只是想跑测试、或只是想看看这个包，可以什么都不做。")
    data["notes_url"] = "https://github.com/%s/releases/tag/v%s" % (owner, new)
    packs = data.get("pack_urls") or {}
    if isinstance(packs, dict):
        # key 是平台标识（"windows"），**不是资产文件名**：0.3.1 的 key 是 windows、
        # 资产名却是 -win.zip。资产名固定 -win.zip，与本脚本自己的提示、
        # CHANGELOG 的下载主链三处一致；拿 key 拼文件名会写出 -windows.zip，上线即 404。
        data["pack_urls"] = {
            k: "https://github.com/%s/releases/download/v%s/second-take-%s-win.zip"
               % (owner, new, new)
            for k in (packs.keys() or ["windows"])
        }
    return data


def write_all(new: str, date: str, channel: str, severity: str, latest_old: dict, dry: bool):
    plan = []
    tag = "v%s" % new
    if VERSION_FILE.exists():
        plan.append((VERSION_FILE, ("%s · %s\n" % (new, date)), read_text(VERSION_FILE)))
    plan.append((LATEST, json.dumps(build_latest(latest_old, new, date, channel, severity),
                                    ensure_ascii=False, indent=2) + "\n", read_text(LATEST)))

    if dry:
        for p, new_text, _ in plan:
            print("  [dry-run] 将写 %s（%d 字节）" % (p.relative_to(ROOT), len(new_text.encode("utf-8"))))
        print("  [dry-run] 将打 tag %s" % tag)
        return

    done = []
    committed = False
    try:
        for p, new_text, old_text in plan:
            p.write_text(new_text, encoding="utf-8")
            done.append((p, old_text))
            print("  · 写 %s" % p.relative_to(ROOT))
        # 2026-11-20：原来这里**只写文件＋打 tag，从不提交**——tag 落在旧提交上，
        # 「三处同源」是假的（checkout vX.Y.Z 拿到的还是上一版的 VERSION）。
        # 发版说明必须一次提交、且带 SIGNED-BY，这是 `AGENTS.md` 的提交纪律。
        names = [str(p.relative_to(ROOT)) for p, _, _ in plan]
        r = sh("git", "add", *names)
        if r.returncode != 0:
            raise Broken("git add 失败：%s" % (r.stderr.strip()[:200] or ""))
        signed = sh("git", "config", "user.name").stdout.strip()
        msg = "release %s：VERSION 与 latest.json 同步\n\nSIGNED-BY: %s" % (new, signed)
        r = sh("git", "commit", "-m", msg)
        if r.returncode != 0:
            raise Broken("git commit 失败：%s" % (r.stderr.strip()[:200] or ""))
        committed = True
        print("  · 提交 %s" % ", ".join(names))
        r = sh("git", "tag", "-a", tag, "-m", "release %s" % new)
        if r.returncode != 0:
            raise Broken("git tag 失败：%s" % (r.stderr.strip()[:200] or r.stdout.strip()[:200]))
        print("  · 打 tag %s" % tag)
    except Exception as e:
        sh("git", "tag", "-d", tag)
        # 只有**这次**的提交真的成功了，才撤销 HEAD~1。commit 失败时撤 HEAD~1，
        # 撤掉的是上一个与本次无关的提交——2026-11-23 小渊在工作区副本里撞到过
        # （HEAD 从 49435f0 掉到 3bac61a），真实仓库只是恰好没走到这条分支。
        if committed:
            sh("git", "reset", "--soft", "HEAD~1")
        for p, old_text in reversed(done):
            p.write_text(old_text, encoding="utf-8")
        raise Broken("写入失败，已回滚（%s）。原因：%s" % ("VERSION/latest.json/提交/tag", e))


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description="一次写三处：VERSION / latest.json / git tag")
    ap.add_argument("--version", required=True, help="新版本号，X.Y.Z")
    ap.add_argument("--channel", default="stable", choices=["stable", "beta"])
    ap.add_argument("--severity", default="normal", choices=["normal", "security"])
    ap.add_argument("--date", default=None, help="默认今天")
    ap.add_argument("--dry-run", action="store_true", help="只校验与打印，不写盘")
    args = ap.parse_args(argv)

    date = args.date or today()
    print("release %s（%s / %s）%s" % (args.version, args.channel, args.severity,
                                       "  [dry-run]" if args.dry_run else ""))
    try:
        print("前置 1/4 工作区干净 …")
        check_git_clean()
        print("前置 2/4 门禁通过 …")
        check_gate()
        latest_old = load_latest()
        old = latest_old["version"]
        print("  当前版本 %s" % old)
        print("前置 3/4 版本一致且递增 …")
        check_version_consistency(old, args.version)
        print("前置 4/4 CHANGELOG 本节合格 …")
        check_changelog(args.version, date)
    except Bad as e:
        print("\n✗ 前置校验没过（退出 2，未写任何文件）：\n  %s" % e)
        return 2

    try:
        write_all(args.version, date, args.channel, args.severity, latest_old, args.dry_run)
    except Broken as e:
        print("\n✗ %s" % e)
        return 3

    print("\n✓ 三处已同源：VERSION%s / latest.json / tag v%s"
          % ("（如存在）" if VERSION_FILE.exists() else "（本库无此文件）", args.version))
    print("下一步（手工，顺序别换）：")
    print("  0) 判据：python tools/verify_release.py --words <词表> --no-zip")
    print("  1) 打包：python tools/build_public_package.py --out dist/second-take-%s-win.zip --words <词表>" % args.version)
    print("     封条：python tools/seal.py seal dist/second-take-%s-win.zip --words <词表>" % args.version)
    print("  2) 判据全量：python tools/verify_release.py --words <词表> --zip dist/second-take-%s-win.zip" % args.version)
    print("  3) 推 tag：git push origin v%s" % args.version)
    print("  4) 建 release：网页选已存在的 tag，资产名一字不差，正文粘 CHANGELOG 那一节")
    print("  5) 最后推 master：git push origin master")
    return 0


if __name__ == "__main__":
    sys.exit(main())
