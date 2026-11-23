# -*- coding: utf-8 -*-
"""状态页：只出人话，不出内部读数。

这条边界是产品决定的，不是风格偏好：用户要的是「覆盖率、风险、下一步」，
不是「绿 3／跳过 15／阻断 0」。所以这里钉三件事——
① 内部词一个都不许漏到用户面；② 不论检查结果如何都退 0（镜子不是门）；
③ 没有 gate 也不能崩、不能说成「全通过」。
"""

from pathlib import Path

from helpers import copy_into, run, write

BANNED = ("绿", "跳过", "阻断", "门禁", "提示档", "全绿", "退出码 2")

SUMMARY = "⚠ 部分通过：19 项 ｜ 绿 3 ／ **跳过 15** ／ 提示 1 ／ 阻断 0\n"


def fake_gate(root, text=SUMMARY):
    write(root, "gate/_gate.py", (
        "# -*- coding: utf-8 -*-\n"
        "import sys\n"
        "sys.stdout.reconfigure(encoding='utf-8')\n"
        "print(%r)\n" % text.strip()
    ))


def status_output(root):
    copy_into(root, "tools/status.py")
    r = run(root, "tools/status.py")
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_only_human_words(sandbox):
    fake_gate(sandbox)
    out = status_output(sandbox)
    for w in BANNED:
        assert w not in out, "内部用词漏到用户面: %s\n%s" % (w, out)


def test_coverage_is_percentage(sandbox):
    fake_gate(sandbox)
    out = status_output(sandbox)
    assert "能自动检查的：3/19（16%）" in out, out
    assert "还有 15 项现在查不了" in out, out


def test_always_exit_zero_even_when_blocked(sandbox):
    fake_gate(sandbox, "⚠ 部分通过：19 项 ｜ 绿 0 ／ **跳过 3** ／ 提示 0 ／ 阻断 16")
    copy_into(sandbox, "tools/status.py")
    r = run(sandbox, "tools/status.py")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "16 处会直接过不去" in r.stdout, r.stdout


def test_no_gate_does_not_crash(sandbox):
    copy_into(sandbox, "tools/status.py")
    r = run(sandbox, "tools/status.py")
    assert r.returncode == 0, r.stderr
    assert "我在哪：" in r.stdout
    assert "0/0" in r.stdout
    # 没有 gate 时不许把「没查成」说成通过
    assert "通过" not in r.stdout


def test_risks_name_the_next_action(sandbox):
    fake_gate(sandbox)
    out = status_output(sandbox)
    assert "workspace/input/" in out           # 缺前置 → 指到具体目录
    assert "建状态卡" in out                    # 缺 STATE.md → 给一句能说的话
    assert "tools/evidence.py" in out          # 缺证据 → 给命令


def test_report_written(sandbox):
    fake_gate(sandbox)
    copy_into(sandbox, "tools/status.py")
    r = run(sandbox, "tools/status.py", "--report")
    assert r.returncode == 0, r.stderr
    p = Path(sandbox) / "workspace" / "开工报告.md"
    assert p.exists(), r.stdout
    body = p.read_text(encoding="utf-8")
    assert body.startswith("# 开工报告"), body[:80]
    for w in BANNED:
        assert w not in body, w
