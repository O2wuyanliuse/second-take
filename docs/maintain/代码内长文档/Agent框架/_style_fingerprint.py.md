# Agent框架/_style_fingerprint.py 原始模块文档

来源：`Agent框架/_style_fingerprint.py`。本文保存外搬前的完整说明、事故史与表格；代码内只保留运行用法和本页指针。

_style_fingerprint.py · 文笔结构指纹（通用层工具）

它干什么
    把「人机味」拆成几项**结构指标**，拿某个作者自己的原文当基线，再拿新稿去比。
    只测结构，不测好坏——**指标全绿也可能写得烂**。

它为什么存在
    作者 2026-10-29 02:20 点破：续写最难的不是逻辑（框架会填），是文笔统一——
    「为了自洽，你写的东西过于方便自己通过；但读者容易一眼人机」。

    "像不像"不能靠 AI 自评（自评必然给自己放水）。所以把判断挪到可数的东西上。
    完整方法论见 `06_数据采集与迭代规范.md` → `四·补一 文笔校准`（**待验**）。

一条硬规矩
    **阈值不许写死。** 每个作者基线不同（实测一位作者「四字整句」0.47，AI 稿普遍 1.8–3.8 倍）。
    所以必须 `--base` 先算这个人的基线，再比。拿固定阈值套所有人，是在制造新的"人机味"。

用法
    python _style_fingerprint.py --base 原文.txt
    python _style_fingerprint.py --base 原文目录/ --check 新稿.md
    python _style_fingerprint.py --base a.txt --base b.txt --check 新稿.md    # 多文件累加
    python _style_fingerprint.py --base 原文.txt --check 新稿.md --json       # 机器可读
