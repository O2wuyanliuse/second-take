**English:** Answer four things — what changed; whether you touched `gate/`／`packaging/`／`tools/`／`.github/` (and that §9 was updated in the same commit, or `[no-procedure-change: reason]` was written); the exit code of `python tools/bootstrap.py --check`; and that no novel text, character names or media are included.

## What changed / 改了什么

<!-- one sentence; link the issue if there is one -->
<!-- 一句话说清；有对应 issue 就挂上 -->

## Did you touch gate / packaging / tools / .github? / 动了这几处吗？

- [ ] No / 没有
- [ ] Yes — I updated §9 of `docs/maintain/维护方法.md` in this same commit
- [ ] Yes — I wrote `[no-procedure-change: reason]` in the commit message
<!-- 勾了 Yes 就必须二选一，否则 CI ⑥ 会红。这不取决于你改得好不好，只看有没有同步。 -->

## Did you run it? / 跑过吗？

```bash
python tools/bootstrap.py --check
```

<!-- paste the exit code. 0 = ready. Non-zero is fine if you explain what it said. -->
<!-- 贴退出码。0 就是合格；非 0 也可以，说清它报了什么。 -->

## No novel text, character names or media / 没有夹带正文、角色名与素材

- [ ] Confirmed / 确认
