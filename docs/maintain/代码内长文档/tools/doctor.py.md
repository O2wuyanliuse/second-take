# tools/doctor.py 原始模块文档

来源：`tools/doctor.py`。本文保存外搬前的完整说明、事故史与表格；代码内只保留运行用法和本页指针。

仓库体检：六行看完，不用翻目录。

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
