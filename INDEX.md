# INDEX · 我该读哪一份

> **English:** Map of this repository — what to read for which task. The Chinese table is normative. To start working, `开工提示词.md` is enough; the release process is maintainer-only and lives on the repository page.

一张给人和 AI 共用的地图。只有这一页是从头看到尾的，其余按需取。

| 我想… | 读这一份 |
|---|---|
| 让 AI 开工 | `开工提示词.md`——整段复制给它 |
| 知道每一步谁拍板 | `Agent框架/环节主线_人端串行_v1.md` |
| 知道什么叫「过」 | `shapes/01_判据形状.md`、`rules/README.md` |
| 知道怎么交接不丢东西 | `shapes/03_交接形状.md` |
| 知道整条流水线有哪些环节 | `Agent框架/环节表_文字到可视化_v1.md` |
| 装不上 / 卡住 | `README.md` 的「三步开工」→ `python tools/doctor.py` |
| 证明真的跑过 | `python tools/evidence.py`，结果写在 `reports/` 下的 `evidence.md` |
| 升级到新版 / 回到旧版 | `docs/upgrade.md` |
| 我维护仓库，要看代码硬约束与变更记录 | `docs/maintain/维护方法.md` |
| 我要找某段代码搬出去的完整说明 | `docs/maintain/代码内长文档.md` |
| 看历史 | `CHANGELOG.md` |
| 看这个库到底不是什么 | `README.md` 的「边界与免责」 |

「先读什么」不在这张表里——那是 `AGENTS.md` 的「AI 阅读路线」管的事。这里回答的是「想干某件事，该翻哪一份」。

## 三个入口的区别

- **`开工提示词.md`**：给 AI 的一段话。复制走就能开工，不需要你先读懂本库。
- **`AGENTS.md`**：给 AI 的规矩。它读，你不必读。
- **`README.md`**：给你的。装、跑、修，三件事。

## 两个工具

| 命令 | 干什么 | 什么时候用 |
|---|---|---|
| `python tools/status.py` | 三句话：我在哪／能自动查多少／下一步。永远退 0 | 每次开工前看一眼，或不知道接下来干什么 |
| `python tools/doctor.py` | 六行体检：python／git／版本／工作区／配置／上次证据 | 装不上，或不确定现在什么状态 |
| `python tools/evidence.py` | 跑三条检查，把退出码写成一张证据页 | 要证明「真的跑过」，或交差之前 |
