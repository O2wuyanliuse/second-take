#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""资产件判据的机器测法（首用记录）。

为什么有它：『灰底上有没有投影』『占画面几成』『偏冷还是偏暖』这三件事，
肉眼看一次一个说法，而且会看反——首轮我肉眼说「有影子」，量出来背景是平的。
判据要能判，就得先能量。

不进 _gate：它判的是「图」，不是「仓」。手动跑，把数抄进台账。

用法：
    python tools/asset_measure.py <图1> [图2 ...]
"""
import sys
from PIL import Image


def _y(p):
    return 0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2]


def _median(v):
    v = sorted(v)
    return v[len(v) // 2] if v else 0


def measure(path):
    im = Image.open(path).convert("RGB")
    W, H = im.size
    px = im.load()

    # ① 背景：四条边条带取样（避开物体）。左右 1.5%~5.5%，上 0.5%~2%，下 97.5%~99.5%
    def strip(x0, x1, y0, y1, step=2):
        return [_y(px[x, y])
                for y in range(int(y0 * H), int(y1 * H), step)
                for x in range(int(x0 * W), int(x1 * W), step)]

    win = {"left": (0.015, 0.055, 0.15, 0.85), "right": (0.945, 0.985, 0.15, 0.85),
           "top": (0.25, 0.75, 0.005, 0.02), "bottom": (0.25, 0.75, 0.975, 0.995)}
    bg_med = {k: round(_median(strip(*v)), 1) for k, v in win.items()}
    bg = _median(list(bg_med.values()))

    # ② 横向剖面：从左边缘往中心，灰底是否越靠近物体越暗（＝有投影／渐变）
    prof = []
    for f in (0.01, 0.03, 0.05, 0.07, 0.09, 0.11, 0.13):
        x = int(f * W)
        prof.append(round(_median([_y(px[x, y]) for y in range(int(0.3 * H), int(0.7 * H), 4)]), 1))

    # ③ 物体掩膜 → 高度占比、逐层宽度
    rows, widths = [], {}
    for y in range(0, H, 4):
        xs = [x for x in range(0, W, 3) if abs(_y(px[x, y]) - bg) > 14]
        if len(xs) > 3:
            rows.append(y)
            widths[y] = max(xs) - min(xs)
    if not rows:
        return None
    top, bot = min(rows), max(rows)
    hh = bot - top + 4

    def w_at(f):
        y = top + int(f * hh)
        y -= y % 4
        while y not in widths and y > top:
            y -= 4
        return widths.get(y, 0)

    # ④ 色温与饱和（只看物体像素）
    rb, sats = [], []
    for y in range(top, bot, 6):
        for x in range(0, W, 6):
            q = px[x, y]
            if abs(_y(q) - bg) > 20:
                rb.append(q[0] - q[2])
                mx = max(q)
                sats.append((mx - min(q)) / mx if mx else 0)

    return {
        "size": (W, H),
        "bg": bg_med,
        "bg_spread": round(max(bg_med.values()) - min(bg_med.values()), 1),
        "profile": prof,
        "profile_spread": round(max(prof) - min(prof), 1),
        "height_pct": round(hh / H * 100, 1),
        "widths": {k: w_at(k) for k in (0.02, 0.16, 0.40, 0.70, 0.85, 0.95)},
        "warm_rb": _median(rb),
        "sat": round(_median(sats), 3),
    }


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    for p in argv:
        m = measure(p)
        if m is None:
            print(f"{p}\n   量不出物体（背景阈值 14 全域命中或全不命中）")
            continue
        name = p.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        print(f"{name}  {m['size'][0]}x{m['size'][1]}")
        print("   背景四边中位 {} ｜ 极差 {} 级（≤2 视为平）".format(
            m["bg"], m["bg_spread"]))
        print("   横向剖面(y=50%, x=1..13%) {} ｜ 极差 {} 级（≤2 视为无投影）".format(
            m["profile"], m["profile_spread"]))
        print("   物体高占画面 {}% ｜ 逐层宽 {}（02/16/40/70/85/95% 高）".format(
            m["height_pct"], m["widths"]))
        print("   暖冷 R−B 中位 {:+d}（正=偏暖） ｜ 饱和度中位 {}".format(
            m["warm_rb"], m["sat"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
