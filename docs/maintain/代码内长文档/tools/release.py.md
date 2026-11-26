# tools/release.py 原始模块文档

来源：`tools/release.py`。本文保存外搬前的完整说明、事故史与表格；代码内只保留运行用法和本页指针。

release.py —— 发版动作的唯一入口：一次写三处（VERSION / latest.json / git tag）。

为什么要有它
------------
版本号散在三处（根目录 `VERSION`、`latest.json`、`git tag`）。手写三处，
第一次就会漂，漂了以后 `latest.json` 与 `tag` 对不上，用户被提醒升级却下到旧包。
这个脚本只做一件事：**三处由一次动作写出，写不完整就整体回滚。**

退出码（与全仓门禁语义一致）
----------------------------
0  写完了，可以打包上传
2  前置校验没过（缺东西 / 工作区脏 / 门禁红 / CHANGELOG 不合格 / 版本号不递增）——**一个字节都没写**
3  写的过程中失败（已回滚到原状）

口径
----
- 版本号唯一真值：本库的 `latest.json["version"]`；若根目录存在 `VERSION` 文件，它必须与之一致（不一致＝退出 2）。
- `CHANGELOG.md` **不由本脚本生成、不改写**：发版说明必须人写（AI 代写的说明等于广告词）。
  本脚本只做机器可判的格式检查：有 `## vX.Y.Z · 日期` 节、「对你有影响」1–3 条、禁词、无 commit hash。
- 本脚本不打包、不上传、不推 tag。推 tag 是人按的。

用法
----
    python tools/release.py --version 0.4.0 --channel stable --severity normal --dry-run
    python tools/release.py --version 0.4.0 --channel stable --severity normal
