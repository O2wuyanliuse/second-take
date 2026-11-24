#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复核闸（逻辑层）。

入口壳在 `.git/gate/review_gate.py`，回执在 `~/.second-take/review/`；
两者都不进仓库、不进包。逻辑放在这里，是为了让 `tests/` 测得到它——
2026-11-24 之前它只有壳里一份，壳一改，闸就变成 `AttributeError` 而没人发现。

判据三条，按顺序：
1. **这次要推的内容**里词表一个都不许出现（含提交信息）。只报位置和词序号，
   不把词本身打出来——报出来就等于又泄漏一次。
2. 有一次「通过」的回执，且 **head 就是当前 HEAD**。
3. 或者回执的 head 是 HEAD 的**祖先**，且从它到 HEAD 的差异**只含**
   `VERSION` / `latest.json`——发版提交是机械产物，不该每次多签一次；
   但只要多一个文件（CHANGELOG、维护方法、代码）就退回到第 2 条。

性质说明：回执是明文 JSON，谁都能手写。它防的是「忘了核」，不是「想绕过」。
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(os.environ.get("SECOND_TAKE_REPO") or
            Path(__file__).resolve().parent.parent)

# 只放这两个：发版提交由 release.py 机械生成，人没什么可核的。
# 多加一个等于把「内容」也塞进免签白名单——小渊 2026-11-24 明确不许。
VERSION_FILES = ("VERSION", "latest.json")


def receipt_dir():
    env = os.environ.get("SECOND_TAKE_REVIEW_DIR")
    return Path(env) if env else Path.home() / ".second-take" / "review"


def sh(*args, cwd=None):
    return subprocess.run(list(args), cwd=str(cwd or ROOT), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def head_sha():
    r = sh("git", "rev-parse", "HEAD")
    return r.stdout.strip()


def read_receipt(head):
    p = receipt_dir() / (head + ".json")
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def all_receipts():
    """回执目录里的全部回执。按 head 精确找不够用——祖先的那份文件名是祖先的 sha。"""
    d = receipt_dir()
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.glob("*.json")):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    # 按签署时间倒序：拒绝时要报「最近那份为什么不作数」，报最老的那份等于误导。
    out.sort(key=lambda r: str(r.get("at") or ""), reverse=True)
    return out


def find_covering(head):
    """找一份能覆盖 HEAD 的回执。返回 (receipt 或 None, 说明)。

    先找 head 精确相等的那份（它最该被信任），再退到「祖先 ＋ 只改版本文件」。
    两步都看 verdict，宁可报「没有」也不拿一份不通过的回执凑数。
    """
    cands = all_receipts()
    if not cands:
        return None, "还没有复核回执"
    for r in cands:
        if str(r.get("head") or "") == head:
            ok, why = receipt_covers(r, head)
            return (r if ok else None), why
    nearest = []
    for r in cands:
        ok, why = receipt_covers(r, head)
        if ok:
            return r, why
        nearest.append(why)
    return None, (nearest[0] if nearest else "没有一份回执覆盖当前 HEAD")


def changed_files(base, head):
    # quotepath=false：否则中文路径会变成 \347\273\264 这种转义，报给人看等于没说。
    r = sh("git", "-c", "core.quotepath=false", "diff", "--name-only", base, head)
    if r.returncode != 0:
        return None
    return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]


def receipt_covers(receipt, head):
    """回执是否覆盖当前 HEAD。返回 (ok, 说明)。"""
    if not receipt:
        return False, "还没有复核回执"
    rhead = str(receipt.get("head") or "")
    if receipt.get("verdict") != "通过":
        return False, "回执结论是「%s」，不是「通过」" % receipt.get("verdict")
    if rhead == head:
        return True, "回执对的就是 HEAD"
    if not rhead:
        return False, "回执里没有 head 字段"
    anc = sh("git", "merge-base", "--is-ancestor", rhead, head)
    if anc.returncode != 0:
        return False, "回执对的是 %s，既不是 HEAD 也不是它的祖先" % rhead[:7]
    files = changed_files(rhead, head)
    if files is None:
        return False, "算不出 %s..%s 的差异" % (rhead[:7], head[:7])
    extra = [f for f in files if f not in VERSION_FILES]
    if extra:
        return False, ("回执对的是祖先 %s，但它之后还改了 %s——只放行 VERSION / latest.json"
                       % (rhead[:7], "、".join(extra[:3])))
    return True, "回执是祖先 %s，其后只改了版本文件" % rhead[:7]


def load_words(path):
    p = Path(path)
    if not p.is_file():
        return None
    words = []
    for ln in p.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        w = ln.strip()
        if not w or w.startswith("#") or w.startswith("["):
            continue
        words.append(w)
    return words or None


def scan_leaks(words):
    """扫「这次要推出去的东西」：待推对象的内容 ＋ 待推提交的提交信息。

    `HEAD --not --remotes` 是口径：远端已经有的不重扫（它们早被扫过了），
    这样 push 前只需为新增部分付时间。
    """
    r = sh("git", "rev-list", "--objects", "HEAD", "--not", "--remotes")
    if r.returncode != 0:
        return None
    hits, n = [], 0
    for line in r.stdout.splitlines():
        parts = line.split(maxsplit=1)
        if not parts:
            continue
        sha = parts[0]
        path = parts[1] if len(parts) > 1 else ""
        typ = sh("git", "cat-file", "-t", sha).stdout.strip()
        if typ not in ("blob", "commit"):
            continue
        body = sh("git", "cat-file", "-p", sha).stdout
        if not body:
            continue
        if typ == "blob" and "\x00" in body[:2048]:
            continue                     # 二进制，不扫
        low = body.lower()
        for i, w in enumerate(words, 1):
            if w.lower() not in low:
                continue
            n += 1
            if typ == "commit":
                hits.append(("提交信息 " + sha[:7], 0, i, len(w)))
                continue
            for ln, text in enumerate(body.splitlines(), 1):
                if w.lower() in text.lower():
                    hits.append((path or sha[:7], ln, i, len(w)))
                    break
    return hits


def cmd_sign(args):
    head = head_sha()
    if not head:
        print("[拒签] 读不到 HEAD。")
        return 1
    if args.implementer.strip().lower() == args.reviewer.strip().lower():
        print("[拒签] 实施人和复核人不能是同一个人——自己写的东西不能自己签。")
        return 1
    d = receipt_dir()
    d.mkdir(parents=True, exist_ok=True)
    data = {
        "head": head,
        "implementer": args.implementer,
        "reviewer": args.reviewer,
        "verdict": "通过",
        "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "note": args.note or "",
        "repo": str(ROOT),
    }
    (d / (head + ".json")).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[签了] %s · 实施 %s · 复核 %s" % (head[:7], args.implementer, args.reviewer))
    return 0


def cmd_check(args):
    words_path = Path(args.words) if args.words else ROOT / ".ci" / "denylist.txt"
    words = load_words(words_path)
    if words is None:
        print("[leak] 找不到词表：" + str(words_path)
              + " —— 这一项没查（不算干净），但闸不因此放行任何东西。")
    else:
        hits = scan_leaks(words)
        if hits is None:
            print("[停一下] 算不出「这次要推的东西」，没法扫。")
            return 1
        if hits:
            print("[leak] 这次要推的内容里有 %d 处命中（只报位置，不报词）：" % len(hits))
            for path, ln, idx, n in hits[:20]:
                print("  %s:%s · 词 #%d（%d 字）" % (path, ln, idx, n))
            print("  推之前先改内容。改写历史是最贵的修法，别用它。")
            return 1
        print("[leak] 待推内容干净（%d 个词）。" % len(words))

    head = head_sha()
    r, why = find_covering(head)
    if r is None:
        print("")
        print("[停一下] " + why + "。")
        print("  这次的改动得先让人核过，由核的人签字，你才推得出去。")
        print("  怎么签：python .git/gate/review_gate.py sign "
              "--implementer <实施人> --reviewer <复核人>")
        print("  （实施人和复核人必须是两个人：自己写的东西不能自己签。）")
        return 1
    print("[gate] 复核回执对得上：" + head[:7] + " · 实施 " + str(r.get("implementer"))
          + " · 复核 " + str(r.get("reviewer")) + "（" + why + "）")
    return 0


def cmd_install(args):
    """把 core.hooksPath 指到 `.git/gate`，并确认壳在。"""
    repo = Path(args.repo).resolve() if args.repo else ROOT
    r = sh("git", "config", "core.hooksPath", ".git/gate", cwd=repo)
    if r.returncode != 0:
        print("[失败] 设不上 core.hooksPath：" + r.stderr.strip()[:160])
        return 1
    gate = repo / ".git" / "gate"
    if not (gate / "review_gate.py").is_file():
        print("[提醒] " + str(gate) + " 里没有 review_gate.py 壳——钩子会缺入口。")
    print("[ok] core.hooksPath = .git/gate（" + str(repo) + "）")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="推送前的复核闸：回执与脱敏")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("sign", help="签一次回执（写 ~/.second-take/review/<head>.json）")
    p.add_argument("--implementer", required=True)
    p.add_argument("--reviewer", required=True)
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_sign)

    p = sub.add_parser("check", help="推送前检查（pre-push 调它）")
    p.add_argument("--words", default=None)
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("install", help="把 hooksPath 指到 .git/gate")
    p.add_argument("--repo", default=None)
    p.set_defaults(func=cmd_install)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
