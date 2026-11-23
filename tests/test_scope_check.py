# -*- coding: utf-8 -*-
"""通用层检查：裸数字要报、区间不报、专名要红。

第二条最重要——规范数字（24–36 格）被扫红的话，这个工具一上线就会被当成噪音忽略，
比不查更坏。所以这里专门钉住「区间不报」。
"""

from helpers import copy_into, run, write


def test_bare_number_flagged(sandbox):
    copy_into(sandbox, "packaging/_scope_check.py")
    write(sandbox, "Agent框架/x.md", "这里写了 23 格，还有 39 秒。\n")
    r = run(sandbox, "packaging/_scope_check.py")
    assert r.returncode == 0, "默认只提示，不拦"
    assert "23 格" in r.stdout
    assert "39 秒" in r.stdout


def test_range_and_limit_not_flagged(sandbox):
    """规范数字：带 –／约／≤ 的一律不报。"""
    copy_into(sandbox, "packaging/_scope_check.py")
    write(sandbox, "Agent框架/x.md",
          "规范是 24–36 格，对应 60–90 秒；约 30 格也行；最多 40 格。\n")
    r = run(sandbox, "packaging/_scope_check.py")
    assert "24–36" not in r.stdout
    assert "60–90" not in r.stdout
    assert "✅" in r.stdout


def test_ok_mark_exempts_line(sandbox):
    copy_into(sandbox, "packaging/_scope_check.py")
    write(sandbox, "Agent框架/x.md", "这是通用阈值 30 秒。  [scope-ok] 非项目样本\n")
    r = run(sandbox, "packaging/_scope_check.py")
    assert "✅" in r.stdout


def test_fen_yi_not_matched_as_time(sandbox):
    """「256 分（积分）」「95 分位」不该被当成时长。"""
    copy_into(sandbox, "packaging/_scope_check.py")
    write(sandbox, "Agent框架/x.md", "一条试跑 256 分（≈24 元）；四角离散度 95 分位。\n")
    r = run(sandbox, "packaging/_scope_check.py")
    assert "✅" in r.stdout


def test_strict_returns_one(sandbox):
    copy_into(sandbox, "packaging/_scope_check.py")
    write(sandbox, "Agent框架/x.md", "23 格。\n")
    r = run(sandbox, "packaging/_scope_check.py", "--strict")
    assert r.returncode == 1


def test_project_name_is_red(sandbox):
    copy_into(sandbox, "packaging/_scope_check.py")
    write(sandbox, ".ci/project_names.txt", "# 一行一个\n某个作品名\n")
    write(sandbox, "Agent框架/x.md", "参见某个作品名的第一章。\n")
    r = run(sandbox, "packaging/_scope_check.py", "--strict")
    assert r.returncode == 1
    assert "专名命中" in r.stdout
