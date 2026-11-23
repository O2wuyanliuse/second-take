#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仓库体检：六行看完，不用翻目录。

与 `packaging/_doctor.py` 的区别——那个查**分发包里的环境**（词表在不在、包在哪一侧）；
这个查**仓库与工作区**。两者不合并：合并后每加一个参数，两边都要为对方让路。

`--tidy` 只碰 `workspace/cache/` 里超过 7 天没改的文件：
- 默认 dry-run，只打印清单，**一个字节都不动**；加 `--yes` 才真删。
- `workspace/input/` 与 `workspace/output/` **永不触碰**——这条写死在代码里，不做成参数。
  用户的原稿和产出比任何磁盘空间都贵，给个开关就等于迟早有人开错。

用法：
    python tools/doctor.py
    python tools/doctor.py --tidy
    python tools/doctor.py --tidy --yes

退出码：0（体检不拦人；真正拦人的是 `gate/_gate.py`）
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
MIN_PY = (3, 10)
SEVEN_DAYS = 7 * 86400
TIDY_SHOW = 20


def git(*args):
    try:
        r = subprocess.run(
            ["git", "-C", str(ROOT)] + list(args),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except OSError:
        return ""


def dir_stats(path):
    """(文件数, MB)。目录不在就是 0，不算错——干净仓库里 workspace 本来可以先空着。"""
    if not path.exists():
        return 0, 0.0
    n, size = 0, 0
    for f in path.rglob("*"):
        if f.is_file():
            n += 1
            try:
                size += f.stat().st_size
            except OSError:
                pass
    return n, size / 1048576.0


def read_version(root):
    try:
        return (root / "VERSION").read_text(encoding="utf-8").split("·")[0].strip()
    except OSError:
        return ""


def read_latest(root):
    try:
        return json.loads((root / "latest.json").read_text(encoding="utf-8")).get("version", "")
    except (OSError, ValueError):
        return ""


def six_lines(root):
    out = []

    v = "%d.%d.%d" % sys.version_info[:3]
    ok_py = sys.version_info[:2] >= MIN_PY
    out.append("[1/6] python   %s %s %d.%d%s" % (
        v, "≥" if ok_py else "<", MIN_PY[0], MIN_PY[1], "" if ok_py else "  ⚠ 低于 bootstrap 要求"))

    head = git("rev-parse", "--short", "HEAD")
    if not head:
        out.append("[2/6] git      不是 git 仓库（解压包就是这样，正常）")
    else:
        branch = git("branch", "--show-current") or "（分离 HEAD）"
        dirty = len([x for x in git("status", "--porcelain").splitlines() if x.strip()])
        out.append("[2/6] git      %s · %s · %s" % (
            branch, head, "干净" if dirty == 0 else "脏 %d 个文件" % dirty))

    ver, lat = read_version(root), read_latest(root)
    if ver and lat:
        same = ver == lat
        out.append("[3/6] 版本      VERSION %s %s latest.json %s%s" % (
            ver, "=" if same else "≠", lat, "" if same else "  ⚠ 发版前必须同源"))
    else:
        out.append("[3/6] 版本      读不到（VERSION %s ／ latest.json %s）" % (
            ver or "缺", lat or "缺"))

    stats = {}
    for name in ("input", "output", "cache"):
        stats[name] = dir_stats(root / "workspace" / name)
    total = sum(s[1] for s in stats.values())
    biggest = max(stats, key=lambda k: stats[k][1]) if total > 0 else "无"
    out.append("[4/6] 工作区    input %d ｜ output %d ｜ cache %d ｜ 合计 %.2f MB（最大 %s）" % (
        stats["input"][0], stats["output"][0], stats["cache"][0], total, biggest))

    cfg = root / "config.local.json"
    if cfg.exists():
        try:
            wr = json.loads(cfg.read_text(encoding="utf-8")).get("workspace_root", "（未写）")
        except ValueError:
            wr = "（解析失败）"
        out.append("[5/6] 配置      config.local.json 在 ｜ workspace_root=%s" % wr)
    else:
        out.append("[5/6] 配置      config.local.json 不在（跑一次 tools/bootstrap.py 会建）")

    ev = root / "reports" / "evidence.md"
    concl = ""
    if ev.exists():
        for ln in ev.read_text(encoding="utf-8", errors="replace").splitlines():
            if ln.startswith("- 结论："):
                concl = ln.split("**")[1] if "**" in ln else ln[len("- 结论："):]
                break
    out.append("[6/6] 门禁      %s" % (concl or "未跑过（先跑 python tools/evidence.py）"))

    return out


def tidy_targets(root):
    """workspace/cache 下超过 7 天未改的文件。input/ 与 output/ 不在搜索范围内。"""
    cache = root / "workspace" / "cache"
    if not cache.exists():
        return []
    base = cache.resolve()
    cutoff = time.time() - SEVEN_DAYS
    found = []
    for f in cache.rglob("*"):
        if not f.is_file():
            continue
        try:
            # 符号链接指到 cache 外面的一律不收——清理工具最容易被这样坑。
            f.resolve().relative_to(base)
            st = f.stat()
        except (OSError, ValueError):
            continue
        if st.st_mtime < cutoff:
            found.append((f, st.st_size, st.st_mtime))
    found.sort(key=lambda x: x[1], reverse=True)
    return found


def tidy(root, yes):
    targets = tidy_targets(root)
    if not targets:
        print("[tidy] workspace/cache 里没有超过 7 天未改动的文件。什么都没删。")
        return 0

    total_mb = sum(t[1] for t in targets) / 1048576.0
    verb = "已清理" if yes else "将清理"
    print("[tidy] %s %d 个文件 / 共 %.2f MB（workspace/cache 下超过 7 天未改动）%s" % (
        verb, len(targets), total_mb, "" if yes else "——dry-run"))

    for f, size, mt in targets[:TIDY_SHOW]:
        try:
            rel = f.relative_to(root)
        except ValueError:
            rel = f
        print("  %-48s %8.2f MB  %s" % (
            str(rel), size / 1048576.0, time.strftime("%Y-%m-%d", time.localtime(mt))))
    if len(targets) > TIDY_SHOW:
        print("  …还有 %d 个未列出" % (len(targets) - TIDY_SHOW))

    if not yes:
        print("[tidy] 什么都没删。加 --yes 才真删；input/ 与 output/ 永不触碰。")
        return 0

    done = 0
    for f, _size, _mt in targets:
        try:
            f.unlink()
            done += 1
        except OSError as e:
            print("  ⚠ 删不掉：%s（%s）" % (f, e))
    print("[tidy] 已删 %d 个文件 / 共 %.2f MB。" % (done, total_mb))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tidy", action="store_true", help="清理 workspace/cache 的旧文件（默认 dry-run）")
    ap.add_argument("--yes", action="store_true", help="与 --tidy 同用：真的删")
    ap.add_argument("--root", default=str(ROOT), help="换一个仓库根（用例用，平时不用给）")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    if args.tidy:
        return tidy(root, args.yes)

    for ln in six_lines(root):
        print(ln)
    return 0


if __name__ == "__main__":
    sys.exit(main())
