<!-- 这个模板只问三件事。答不清的 PR 会被直接关——不是不信任，是看不完就等于没看。 -->

## 改了什么

<!-- 一句话：动了哪几个文件，为什么。 -->

## 对用户可见的变化

<!-- 没有就写「无」。用户看不见的内部重构，不值得单独发一版。 -->

## 流程改动

改到 `gate/`／`packaging/`／`scripts/`／`tools/`／`.github/` 的话，二选一：

- [ ] 同一个 commit 里改了 `docs/maintain/维护方法.md`，并在 §9 追加了一条变更记录
- [ ] 提交信息里写了 `[no-procedure-change: 为什么这次改了代码但流程没变]`

> 这不是礼貌，是机器检查：CI 第 ⑥ 步逐个提交判，**下一条提交的免责标签不能替上一条免责**。
> 只改代码不改文档，下一个人照着旧步骤做，会踩同一个坑。

## 自查

- [ ] `python tools/bootstrap.py --check` 退出 0
- [ ] `python packaging/_pr_guard.py --range origin/master..HEAD` 的输出我读过，没有说不清的行
- [ ] 改 `packaging/*.py` 的话，这个 PR 不超过 50 行（超过请拆开，见 `CONTRIBUTING.md`）
