# -*- coding: utf-8 -*-
"""证据页：结论必须与退出码同源；门禁的「提示档」不能被判成红。

为什么单独给门禁 2 一条用例：方案原文写「三条全 0 才通过」，而本库门禁在骨架库上
**稳定返回 2**（19 项只覆盖 3 项）。照原文实现，干净仓库上这一页永远不通过——
假红比假绿更难发现，因为人会慢慢习惯性忽略那一行红。

第五、六条测「生成的文件」而不是「打印的字」：说跑过不算数，留下的纸才算。
"""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load_evidence():
    spec = importlib.util.spec_from_file_location("evidence_under_test",
                                                  REPO / "tools" / "evidence.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fake_runner(codes):
    """按顺序吐出预设退出码；不管命令内容，只数第几条。"""
    box = {"i": 0}

    def _run(cmd, timeout=900):
        i = box["i"]
        box["i"] = i + 1
        rc = codes[i] if i < len(codes) else 0
        return rc, "第 %d 条输出\n结论行 %d\n" % (i + 1, i + 1), 0.01

    return _run


def test_all_green_passes(monkeypatch):
    mod = load_evidence()
    monkeypatch.setattr(mod, "run_cmd", fake_runner([0, 0, 0]))
    passed, line = mod.verdict(mod.collect())
    assert passed is True
    assert line == "通过（3/3）"


def test_middle_failure_names_that_step(monkeypatch):
    mod = load_evidence()
    monkeypatch.setattr(mod, "run_cmd", fake_runner([0, 1, 0]))
    passed, line = mod.verdict(mod.collect())
    assert passed is False
    assert "第 2 条" in line and "退出码 1" in line
    assert "门禁" in line


def test_all_failure_reports_first(monkeypatch):
    mod = load_evidence()
    monkeypatch.setattr(mod, "run_cmd", fake_runner([1, 1, 1]))
    passed, line = mod.verdict(mod.collect())
    assert passed is False
    assert "第 1 条" in line


def test_gate_rc2_is_hint_not_red(monkeypatch):
    """本库口径：0 绿 / 1 阻断 / 2 提示。门禁的 2 必须算通过。"""
    mod = load_evidence()
    monkeypatch.setattr(mod, "run_cmd", fake_runner([0, 2, 0]))
    passed, line = mod.verdict(mod.collect())
    assert passed is True, line
    assert "提示档" in line


def test_no_tests_runs_two_steps(monkeypatch):
    mod = load_evidence()
    monkeypatch.setattr(mod, "run_cmd", fake_runner([0, 2]))
    rows = mod.collect(skip_tests=True)
    assert len(rows) == 2
    passed, line = mod.verdict(rows)
    assert passed is True
    assert "2/2" in line


def test_report_file_has_exit_code_column(tmp_path, monkeypatch):
    mod = load_evidence()
    monkeypatch.setattr(mod, "run_cmd", fake_runner([0, 0, 0]))
    out = tmp_path / "evidence.md"
    rc = mod.main(["--out", str(out)])
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "退出码" in text
    assert "`python tools/bootstrap.py --check`" in text
    assert "通过（3/3）" in text
    assert "怎么复核" in text


def test_report_file_and_exit_code_agree_on_failure(tmp_path, monkeypatch):
    """纸上的结论与命令行退出码必须是同一件事——这就是这一页存在的理由。"""
    mod = load_evidence()
    monkeypatch.setattr(mod, "run_cmd", fake_runner([0, 1, 0]))
    out = tmp_path / "evidence.md"
    rc = mod.main(["--out", str(out)])
    assert rc == 1
    text = out.read_text(encoding="utf-8")
    assert "未通过" in text
    assert "退出码 1" in text
