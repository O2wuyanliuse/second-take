#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""证据页：把「真的跑过」钉成一张纸。

为什么要有它：门禁的判据是真的，但输出是一屏终端文字。AI 转述时会说成「全部通过」，
人无法核。0.5.2 那次「首跑红脸」就是「文档说过了、机器没跑」的变种——这一页把
命令原文 / 退出码 / 耗时 / 关键行 落在磁盘上，谁都能打开复核。

**门禁的「通过」是 {0, 2}，不是 {0}。** 本库约定 0 绿 ／ 1 阻断 ／ 2 提示；
骨架库的门禁本来就返回 2（19 项只覆盖 3 项，跳过 15）。把它当红，干净仓库上
这一页永远不通过——那是另一种假红，比假绿更难发现，因为大家会慢慢习惯性忽略它。

**「用例」没装 pytest 时记「跳过」，不记红。** 解压就用的用户手上可能根本没有
pytest；让这一页在他那儿第一眼就红，等于把一个可选依赖写成了必装项。
跳过会写进结论（`通过（2/3，用例未跑：未安装 pytest）`），不会混成「全过了」。

用法：
    python tools/evidence.py                       # 三条都跑
    python tools/evidence.py --no-tests            # 跳过 pytest（快速迭代）
    python tools/evidence.py --out reports/x.md    # 换个落盘位置

退出码：0 通过 ／ 1 未通过（与报告结论一致，可直接进 CI）
"""

import argparse
import datetime
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

# 中文输出在 GBK 控制台会乱码；本库 2026-11-06 在门禁的 ✅ 上踩过。
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
DEFAULT_OUT = "reports/evidence.md"

# 通过判据写死在表里，不靠人记：门禁的 2 是提示档，本库口径，不是红。
STEPS = (
    ("环境自检", ("tools/bootstrap.py", "--check"), (0,)),
    ("门禁", ("gate/_gate.py",), (0, 2)),
    ("用例", ("-m", "pytest", "-q"), (0,)),
)

RED_MARKS = ("❌", "🔴", "✗", "⛔", "FAILED", "ERROR", "Traceback")


def pytest_available():
    """当前解释器里能不能找到 pytest。

    用它而不是跑 `-m pytest --version`：不启子进程，也不为一次探测多等半秒。
    **找不到不等于环境坏了**——zip 用户手上本来就可能没有 pytest，那不是他的错。
    """
    try:
        return importlib.util.find_spec("pytest") is not None
    except (ImportError, ValueError):
        return False


def run_cmd(cmd, timeout=900):
    """跑一条命令，返回 (退出码, 合并输出, 秒数)。

    跑不起来也算一条结果（127），不抛——「没跑成」本身就是要被记下来的证据，
    不能因为异常让整页断在中间。
    """
    t0 = time.time()
    try:
        r = subprocess.run(
            cmd, cwd=str(REPO), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        out = r.stdout or ""
        if r.stderr:
            out += ("\n" if out else "") + r.stderr
        return r.returncode, out, time.time() - t0
    except subprocess.TimeoutExpired:
        return 124, "（超时：%d 秒）" % timeout, time.time() - t0
    except OSError as e:
        return 127, "（跑不起来：%s）" % e, time.time() - t0


def key_line(rc, text, ok):
    """表格里的「关键行」：失败摘第一条红，通过摘最后一行。"""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return "（无输出）"
    if rc not in ok:
        for ln in lines:
            if any(m in ln for m in RED_MARKS):
                return ln[:160]
        return lines[-1][:160]
    return lines[-1][:120]


def collect(skip_tests=False):
    """顺序跑三条，逐条记录。返回行列表（顺序即执行顺序）。

    「用例」有两级降级，语义不同，别混：
    - `--no-tests`：用户主动要求不跑，这条**不进表**（分母变 2），结论里注明。
    - 没装 pytest：本来该跑、只是跑不了——**进表、记跳过**，分母仍是 3。
      两种都按提示档处理：解压就用的用户手上可能根本没有 pytest，
      让它第一眼看见一张红纸，正是这个功能最该避免的事。
    """
    rows, idx = [], 0
    for label, argv, ok in STEPS:
        if skip_tests and label == "用例":
            continue
        idx += 1

        if label == "用例" and not pytest_available():
            rows.append({
                "idx": idx, "label": label, "cmd": "python " + " ".join(argv),
                "rc": None, "ok": ok, "secs": 0.0, "skipped": True,
                "why": "未安装 pytest", "out": "",
                "key": "未跑：未安装 pytest（pip install pytest 后可跑）",
            })
            continue

        # 脚本不在，就别交给解释器：Python 找不到文件时**也退 2**，而 2 在本库是
        # 「提示档」，会被当成通过。那正是「故意改名必须判红」要抓的那种假绿。
        script = next((a for a in argv if a.endswith(".py")), None)
        if script and not (REPO / script).exists():
            rows.append({
                "idx": idx, "label": label, "cmd": "python " + " ".join(argv),
                "rc": 127, "ok": ok, "secs": 0.0,
                "out": "脚本不存在：%s" % script,
                "key": "脚本不存在：%s" % script,
            })
            continue

        # 解释器用 sys.executable：Windows 上 `python` 可能是另一个装法。
        cmd = [sys.executable]
        for a in argv:
            cmd.append(str(REPO / a) if a.endswith(".py") else a)
        rc, out, secs = run_cmd(cmd)
        rows.append({
            "idx": idx, "label": label, "cmd": "python " + " ".join(argv),
            "rc": rc, "ok": ok, "secs": secs, "out": out,
            "key": key_line(rc, out, ok),
        })
    return rows


def verdict(rows, no_tests=False):
    """结论 = 结论文字 + 是否通过。两者出自同一处，避免打印与退出码打架。

    **跳过不是通过**：没跑的那一项必须写进结论，不能让它混在「3/3」里蒙过去。
    """
    bad = [r for r in rows if not r.get("skipped") and r["rc"] not in r["ok"]]
    if bad:
        f = bad[0]
        return False, "未通过：第 %d 条「%s」· 退出码 %d" % (f["idx"], f["label"], f["rc"])

    skipped = [r for r in rows if r.get("skipped")]
    ran = len(rows) - len(skipped)

    notes = []
    hint = [r["label"] for r in rows if not r.get("skipped") and r["rc"] == 2]
    if hint:
        notes.append("其中「%s」为提示档" % "、".join(hint))
    if no_tests:
        notes.append("用例按 --no-tests 跳过")
    for r in skipped:
        notes.append("%s未跑：%s" % (r["label"], r["why"]))

    tail = "，" + "；".join(notes) if notes else ""
    return True, "通过（%d/%d%s）" % (ran, len(rows), tail)


def _git(*args):
    try:
        r = subprocess.run(["git", "-C", str(REPO)] + list(args),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        return r.stdout.strip() if r.returncode == 0 else ""
    except OSError:
        return ""


def version_of():
    try:
        return (REPO / "VERSION").read_text(encoding="utf-8").split("·")[0].strip()
    except OSError:
        return "?"


def latest_version():
    try:
        data = json.loads((REPO / "latest.json").read_text(encoding="utf-8"))
        return data.get("version", "?")
    except (OSError, ValueError):
        return "?"


def now_text():
    t = datetime.datetime.now().astimezone()
    off = t.utcoffset()
    hours = int(off.total_seconds() // 3600) if off else 0
    return t.strftime("%Y-%m-%d %H:%M") + " (UTC%+d)" % hours


def dirty_text():
    n = len([x for x in _git("status", "--porcelain").splitlines() if x.strip()])
    return "干净" if n == 0 else "脏 %d 个文件" % n


def render(rows, line, meta):
    out = [
        "# 证据 · v%s · %s · %s" % (meta["version"], meta["head"] or "（无 git）", meta["time"]),
        "",
        "- 结论：**%s**" % line,
        "- 解释器：%s" % meta["python"],
        "- 工作区：%s" % meta["dirty"],
        "- 版本：VERSION %s ｜ latest.json %s" % (meta["version"], meta["latest"]),
        "",
        "| 命令 | 退出码 | 耗时 | 关键行 |",
        "|---|---|---|---|",
    ]
    for r in rows:
        if r.get("skipped"):
            out.append("| `%s` | — | — | %s |" % (
                r["cmd"], r["key"].replace("|", "\\|")))
            continue
        mark = "" if r["rc"] in r["ok"] else " ❌"
        out.append("| `%s` | %d%s | %.2fs | %s |" % (
            r["cmd"], r["rc"], mark, r["secs"], r["key"].replace("|", "\\|")))
    out += [
        "",
        "## 怎么复核",
        "",
        "把这一页整段贴给提问的人。表里每一条的退出码都能自己再跑一次：",
        "复制「命令」列，在本仓库根目录执行，看退出码是否一致。",
        "",
        "口径：**0 绿 ／ 1 阻断 ／ 2 提示**。门禁那一行的 2 是「部分通过：覆盖率不足」，",
        "不是红；出现 1 才是真停。",
        "",
        "「用例」写「未跑：未安装 pytest」时，先 `pip install pytest` 再跑一次。",
        "不装也能开工，只是这一项没被覆盖——**没跑的事从来不写成通过**。",
        "",
    ]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT, help="落盘位置，默认 reports/evidence.md")
    ap.add_argument("--no-tests", action="store_true", help="跳过 pytest")
    args = ap.parse_args(argv)

    rows = collect(args.no_tests)
    passed, line = verdict(rows, no_tests=args.no_tests)
    meta = {
        "version": version_of(),
        "head": _git("rev-parse", "--short", "HEAD"),
        "time": now_text(),
        "python": "%d.%d.%d (%s)" % (
            sys.version_info[0], sys.version_info[1], sys.version_info[2],
            sys.implementation.name),
        "dirty": dirty_text(),
        "latest": latest_version(),
    }
    text = render(rows, line, meta)

    out = Path(args.out)
    if not out.is_absolute():
        out = REPO / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")

    print("[evidence] " + line)
    for r in rows:
        if r.get("skipped"):
            print("  %-6s 跳过      %s" % (r["label"], r["key"][:70]))
            continue
        print("  %-6s rc=%-3d %6.2fs  %s" % (r["label"], r["rc"], r["secs"], r["key"][:80]))
    print("[evidence] 落盘：%s" % out)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
