# packaging/_sync_check.py 原始模块文档

来源：`packaging/_sync_check.py`。本文保存外搬前的完整说明、事故史与表格；代码内只保留运行用法和本页指针。

_sync_check.py — 私库 → 骨架库的回流检查。

用法：
    python packaging/_sync_check.py                      # 自动找骨架库
    python packaging/_sync_check.py --skeleton <骨架库路径>
    python packaging/_sync_check.py --manifest <清单>

骨架库路径的取法（依次）：`--skeleton` → 环境变量 `SKELETON_ROOT`。**两者都没有就报错，不猜。**

退出码：`0` 全部对齐 ／ `1` 有不一致或该搬没搬 ／ `2` **骨架库路径找不到（未配置，不算通过）**

## 为什么单列一个脚本

2026-11-10 做过一次**一次性搬运**：把 `Agent框架/` 抽成骨架库的子集，搬得很干净。
搬完之后私库继续长（同步防断、`_doctor`、`_triage`、E0 第 9 项……），**骨架库冻结在那一天**。
没有清单与机检，就没人知道差了多少——**这就是「两库」变成两个世界的过程。**

## 它不做什么

**不自动同步。** 回流需要判断（哪些是专名、哪些该改写成通用表述），机器做不了。
它只回答一件事：**清单里这两份，现在是不是同一个东西。**
