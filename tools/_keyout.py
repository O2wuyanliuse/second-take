#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""色键抠图 —— 把「人物独立成层」这件事做成一条命令。

用法：
    python tools/_keyout.py 原图.jpg -o 抠图.png
    python tools/_keyout.py 原图.jpg -o 抠图.png --tol 30 --soft 20

完整说明：docs/maintain/代码内长文档/tools/_keyout.py.md
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass  # 吞：输出流不支持 reconfigure 时保留原编码，不让输出配置阻断检查。

try:
    from PIL import Image
    import numpy as np
except ImportError:
    print("缺 Pillow / numpy：pip install pillow numpy")
    sys.exit(2)


def main():
    ap = argparse.ArgumentParser(description="纯色背景的色键抠图")
    ap.add_argument("src")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--tol", type=float, default=25.0, help="背景判定距离（低于此值算背景）")
    ap.add_argument("--soft", type=float, default=20.0, help="过渡带宽度（tol 到 tol+soft 之间做羽化）")
    ap.add_argument("--edge", type=int, default=40, help="四角采样边长")
    args = ap.parse_args()

    im = Image.open(args.src).convert("RGB")
    a = np.asarray(im).astype(np.int16)
    h, w, _ = a.shape
    e = max(4, min(args.edge, h // 4, w // 4))
    corners = np.concatenate([
        a[:e, :e].reshape(-1, 3), a[:e, -e:].reshape(-1, 3),
        a[-e:, :e].reshape(-1, 3), a[-e:, -e:].reshape(-1, 3),
    ])
    bg = np.median(corners, axis=0)
    d = np.sqrt(((a - bg) ** 2).sum(axis=2))

    # 背景均匀度：四角像素到中位色的 95 分位
    spread = float(np.percentile(
        np.sqrt(((corners - bg) ** 2).sum(axis=1)), 95))
    fg = d > args.tol
    fg_ratio = float(fg.mean() * 100)

    alpha = np.clip((d - args.tol) / max(args.soft, 1e-6), 0, 1)
    soft_ratio = float(((alpha > 0.05) & (alpha < 0.95)).mean() * 100)

    print("背景色 RGB = %s ｜ 离散度 %.1f ｜ 前景 %.1f%% ｜ 边缘过渡 %.2f%%"
          % (bg.astype(int).tolist(), spread, fg_ratio, soft_ratio))

    bad = False
    if spread > 8:
        print("  ⚠ 背景不够均匀（离散度 %.1f > 8）：四角可能不全是背景，或背景有渐变/纹理。" % spread)
        print("     抠出来边缘会有残留——先确认这张图的背景是不是纯色，或者调大 --tol 试试。")
        bad = True
    if fg_ratio < 5:
        print("  ⚠ 前景只有 %.1f%%：背景色可能采错了（四角不是背景，或主体占满画面）。" % fg_ratio)
        bad = True
    if fg_ratio > 60:
        print("  ⚠ 前景 %.1f%% 过大：背景色被当成了主体，或这图是满幅无背景的。" % fg_ratio)
        bad = True

    out = np.dstack([a.astype(np.uint8), (alpha * 255).astype(np.uint8)])
    Image.fromarray(out, "RGBA").save(args.out)
    print("✅ 已存：%s%s" % (args.out, "（有警告，先看图再决定用不用）" if bad else ""))
    print("   [scope] 只做「纯色背景 → alpha」。人物内部的洞（比如手臂与身体之间的背景）会一起抠掉——这是对的。")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
