# -*- coding: utf-8 -*-
"""状态页：把内部检查翻成人话。

用户不需要知道「绿几项、跳过几项、阻断几项」。他要知道三件事：
  1. 现在能自动检查到什么程度（覆盖率，以及没覆盖的那部分没有保护）；
  2. 哪一步会绊他（错位、缺前置、会卡住）；
  3. 下一步做什么。

内部口径只留在 gate 里；本文件一个字都不印。
用法:
    python tools/status.py             # 四到八行
    python tools/status.py --report    # 另写 workspace/开工报告.md
    python tools/status.py --root DIR
退出码永远是 0：这是镜子，不是门。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# 打印黑名单：这些词属于内部运行，不许出现在用户面。
BANNED = ("绿", "跳过", "阻断", "门禁", "提示档", "全绿", "退出码 2", "项有提示")

NUM = re.compile(r"\d+")


def utf8_stdio() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def run_gate(root: Path) -> str:
    gate = root / "gate" / "_gate.py"
    if not gate.exists():
        return ""
    try:
        r = subprocess.run(
            [sys.executable, str(gate), "--quiet"],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=300,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return r.stdout or ""
    except Exception:
        return ""


def parse(out: str) -> dict:
    """只读汇总行：逐项明细是给维护者的，状态页不搬。"""
    zero = {"total": 0, "ok": 0, "uncovered": 0, "decide": 0, "stuck": 0}
    for line in out.splitlines():
        if "项" not in line or "／" not in line:
            continue
        parts = re.split(r"[／/]", line)
        if len(parts) < 4:
            continue
        head = NUM.findall(parts[0])      # 19 项 ｜ 绿 3
        tail = [NUM.findall(x) for x in parts[1:4]]   # 跳过 15 / 提示 1 / 阻断 0
        if len(head) < 2 or any(not t for t in tail):
            continue
        return {"total": int(head[0]), "ok": int(head[-1]),
                "uncovered": int(tail[0][-1]), "decide": int(tail[1][-1]),
                "stuck": int(tail[2][-1])}
    return zero


def where(root: Path) -> str:
    ws = root / "workspace"
    if not ws.exists():
        return "还没建工作区——这一步由 AI 跑 bootstrap 时完成"
    inp = ws / "input"
    try:
        n = len([p for p in inp.iterdir() if p.name != ".gitkeep"]) if inp.exists() else 0
    except Exception:
        n = 0
    if n == 0:
        return "工作区已建好，但 input/ 里还没有原文"
    return "工作区已就位，input/ 里有 %d 份材料" % n


def has_state(root: Path) -> bool:
    return (root / "workspace" / "STATE.md").exists() or (root / "STATE.md").exists()


def risks(root: Path, d: dict) -> list:
    """错位与风险：每条都给「怎么办」，不给术语。"""
    out = []
    ws = root / "workspace"
    inp = ws / "input"
    try:
        n = len([p for p in inp.iterdir() if p.name != ".gitkeep"]) if inp.exists() else 0
    except Exception:
        n = 0
    if n == 0:
        out.append(("还没到能开工的地方", "先有原文，才谈分镜",
                    "把要改的长文放进 workspace/input/，然后对 AI 说「按 E0 开工」"))
    if not has_state(root):
        out.append(("换个窗口就断片", "没有状态卡，AI 每轮都要重新问你到哪一步",
                    "对 AI 说「建状态卡」，之后它自己读"))
    if not (root / "reports" / "evidence.md").exists():
        out.append(("没人能证明它真的跑过", "所有结论现在都只是转述",
                    "跑一次 python tools/evidence.py，它会写一份带命令与结论的证据页"))
    if d["stuck"]:
        out.append(("%d 处会直接过不去" % d["stuck"], "这些位置现在过不了检查",
                    "让 AI 逐条说明「改哪里、改完怎么验」，改不动的先放一放"))
    if d["decide"]:
        out.append(("%d 处等你拍板" % d["decide"], "AI 不该替你决定，所以停在这里",
                    "看 AI 给的两个选项与代价，选一个；不选它会一直空着"))
    return out


def coverage(d: dict) -> str:
    t = d["total"] or 1
    return "%d/%d（%d%%）" % (d["ok"], d["total"], round(100.0 * d["ok"] / t))


def render(root: Path) -> list:
    d = parse(run_gate(root))
    lines = ["我在哪：" + where(root), "能自动检查的：" + coverage(d)]
    if d["uncovered"]:
        lines.append("　　还有 %d 项现在查不了——这段路上没有保护，只能靠人眼。" % d["uncovered"])
    rs = risks(root, d)
    if rs:
        lines.append("要注意：")
        for i, (title, why, how) in enumerate(rs, 1):
            lines.append("　%d. %s（%s）→ %s" % (i, title, why, how))
    else:
        lines.append("要注意：暂时没有发现错位或缺前置。")
    lines.append("下一步：① 放原文进 workspace/input/ ② 对 AI 说「按 E0 开工」 ③ 只想看看就说「跑一段样例」")
    lines.append("证据：python tools/evidence.py（结果在 reports/evidence.md）")
    return lines


def write_report(root: Path, lines: list) -> Path:
    ws = root / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    p = ws / "开工报告.md"
    body = ["# 开工报告（自动生成，别手改）", "",
            "生成时间：%s" % datetime.now().strftime("%Y-%m-%d %H:%M"), ""]
    body += [ln.replace("　", "  ") for ln in lines]
    p.write_text("\n".join(body) + "\n", encoding="utf-8")
    return p


def main() -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(description="状态页：人话版进度与风险")
    ap.add_argument("--report", action="store_true", help="同时写 workspace/开工报告.md")
    ap.add_argument("--root", default=None)
    ap.add_argument("--json", action="store_true", help="给机器读")
    args = ap.parse_args()
    root = Path(args.root).resolve() if args.root else REPO
    lines = render(root)
    for ln in lines:
        print(ln)
    if args.report:
        print("")
        print("已写：%s" % write_report(root, lines))
    if args.json:
        print(json.dumps({"lines": lines}, ensure_ascii=False))
    bad = [w for w in BANNED if any(w in ln for ln in lines)]
    if bad:
        print("[内部] 状态页里出现了不该给用户看的词: %s" % "、".join(bad), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())