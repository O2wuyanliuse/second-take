**English:** Answer five things — what changed; what a user would notice (write "none" for internal-only work); whether you touched `gate/`／`packaging/`／`tools/`／`.github/` (and that §9 was updated in the same commit, or `[no-procedure-change: reason]` was written); the exit codes you actually got, and that you read `_pr_guard.py`'s output; and that no novel text, character names or media are included. A PR that changes `packaging/*.py` must stay **≤50 lines** — split it instead.

## What changed / 改了什么

<!-- one sentence: which files, why. Link the issue if there is one. -->
<!-- 一句话说清：动了哪几个文件、为什么。有对应 issue 就挂上。 -->

## User-visible change / 对用户可见的变化

<!-- If none, write "none". Internal refactors users cannot see are not worth a release on their own. -->
<!-- 没有就写「无」。用户看不见的内部重构，不值得单独发一版。 -->

## Did you touch gate / packaging / tools / .github? / 动了这几处吗？

- [ ] No / 没有
- [ ] Yes — I updated §9 of `docs/maintain/维护方法.md` in this same commit / 同一提交里改了 §9
- [ ] Yes — I wrote `[no-procedure-change: reason]` in the commit message / 提交信息里写了免责标签

<!-- 勾了 Yes 必须二选一，否则 CI ⑥ 会红。机器逐个提交判：下一条提交的免责标签替不了上一条。 -->

## Did you run it? / 跑过吗？

```bash
python tools/bootstrap.py --check
python packaging/_pr_guard.py --range origin/master..HEAD
```

<!-- Paste the exit code of the first command (0 = ready), and say you read the second one's output. -->
<!-- 贴第一条的退出码（0 就合格）；第二条的输出要读过再说。 -->

- [ ] Changing `packaging/*.py`? This PR is **≤50 lines**, or I split it. / 改的是 `packaging/*.py` 的话，这个 PR 不超过 50 行，超了就拆

## No novel text, character names or media / 没有夹带正文、角色名与素材

- [ ] Confirmed / 确认
