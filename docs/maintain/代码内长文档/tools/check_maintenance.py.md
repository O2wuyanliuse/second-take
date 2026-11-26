# tools/check_maintenance.py 原始模块文档

来源：`tools/check_maintenance.py`。本文保存外搬前的完整说明、事故史与表格；代码内只保留运行用法和本页指针。

维护方法双写检查。

规则：一个**提交**若触及流程相关目录，必须同时改 docs/maintain/维护方法.md；
      否则那个提交的信息里要带 [no-procedure-change: 理由]。

2026-11-21 · v1.8：从「只看最后一个提交」改成**逐提交判**。
原实现 diff 看 `base...HEAD` 整个范围、message 只读 HEAD，于是这一串能混过去：
  · 提交 A：改 `gate/`，没同步维护方法
  · 提交 B：只改 README，信息里写 `[no-procedure-change: 排版]`
检查读的是 B 的消息、看的是 A+B 的文件，判「有免责标签」→ 通过。
**范围按整个区间取、消息只取一条，这两个口径一旦错配，标签就能替别人免责。**
经过写在 docs/maintain/维护方法.md §9 v1.8。

用法：
    python tools/check_maintenance.py                        # 只查 HEAD 这一个提交
    python tools/check_maintenance.py --base HEAD~1           # 查刚做完的那一个提交
    python tools/check_maintenance.py --base origin/master    # 查整段（两者之间没有提交时退 2，不是通过）
    python tools/check_maintenance.py --staged --message-file .git/COMMIT_EDITMSG

退出码：0 通过 ／ 1 有提交触犯 ／ 2 没查成（空范围、git 失败）——**2 不是通过**
