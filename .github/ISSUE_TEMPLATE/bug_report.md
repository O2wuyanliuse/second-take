---
name: 用不了 / 报错
title: "[bug] <一句话 / one line>"
about: 卡住了？把下面几项填上，我们就不用来回追问
---

**English:** Paste the full version line, your OS, where it broke, what you expected, what actually happened, and the complete `doctor` output. **Never paste API keys, tokens or passwords.**

> **报错前先自查一次**：同一段提示词，换一个新会话再跑一遍。
> 两次差别很大 → 多半是模型本身的随机性，不是仓库的问题；
> 换了会话还一样错 → 大概率是仓库的问题，带上 `python packaging/_doctor.py` 的输出提 issue。

**Version / 版本**（跑一次 `python 00_原著/_gate.py --first-run`，把第一行整行粘过来）
：

**System / 系统**：Windows 10 / 11

**Where it broke / 卡在哪一步**：（例如：把 zip 拖进对话框、贴上 README 第 1 步那句话之后，它说找不到 `00_原著`）

**Expected / 你期望发生什么**
：

**Actual / 实际发生了什么**（有截图更好）
：

**doctor output / doctor 输出**（`python packaging/_doctor.py`，或包里的 `python 00_原著/_gate.py --first-run`，整段贴，别截断）
：

> 提交前请确认：**不要把 API key、token、账号密码贴进来**。贴了我会删掉并请你立即作废。
> Before submitting: **never paste API keys, tokens or passwords.** If you do, I will delete them and ask you to revoke them immediately.
