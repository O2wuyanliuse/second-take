# packaging/_pr_guard.py 原始模块文档

来源：`packaging/_pr_guard.py`。本文保存外搬前的完整说明、事故史与表格；代码内只保留运行用法和本页指针。

_pr_guard.py — 给**不懂代码的维护者**看 PR 的第一遍。

用法：
    python packaging/_pr_guard.py --range origin/master..HEAD   # 看本地领先远端的提交
    python packaging/_pr_guard.py --range HEAD~1..HEAD          # 看最近一次提交
    git diff xxx | python packaging/_pr_guard.py                # 读 stdin
    python packaging/_pr_guard.py --file pr.diff                # 读文件

输出：动了几个文件、有没有新增、哪些是脚本、**可疑点在哪一行**。
退出码：`0` 没发现可疑点 ／ `1` 有可疑点（不是错，是"这里要人看"）

## 它不做什么——这一条比功能重要

**它不判断对错，也不代替你看。** 它只做一件事：**把「人该看哪里」从几百行里圈出来。**

为什么需要它：维护者可能不是工程师。要求「看懂每一行 diff」是不现实的，
而放弃审查更危险——那等于把仓库交给任何提交 PR 的人。

所以正确的做法不是让人变专家，而是**把要看的面积缩小到三五行**。

## 可疑点的判据（按"藏东西的常见手法"排）

1. **新增文件** —— 新文件可以藏任何东西，比改旧文件危险
2. **网络请求**（`urllib`／`requests`／`http`）—— 可以把数据带出去
3. **子进程／执行**（`subprocess`／`os.system`／`eval`／`exec`）—— 可以跑任意命令
4. **编码与压缩**（`base64`／`zlib`／`marshal`）—— 可以把东西藏成看不懂的样子
5. **删除文件** —— 删掉证据比加上东西更难发现
6. **写文件到仓库外**（绝对路径、`..`）—— 可以改到别处
7. **`.py` 改动超过 50 行** —— 超过这个量，人看不完
