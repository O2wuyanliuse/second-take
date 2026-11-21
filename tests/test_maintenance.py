# -*- coding: utf-8 -*-
"""双写检查：文件、消息、提交必须来自**同一个提交**。

第四条是 2026-11-21 那个洞的回归用例——改前它必然是绿的，
所以它在这里红一次，比在发布那天红一次便宜得多。
"""

from helpers import commit, copy_into, git, run, write

DOC = "docs/maintain/维护方法.md"


def checker(sandbox):
    copy_into(sandbox, "tools/check_maintenance.py")
    write(sandbox, "README.md", "# 起点\n")
    return commit(sandbox, "起点")


def test_single_commit_without_doc_blocks(sandbox):
    checker(sandbox)
    write(sandbox, "gate/_gate.py", "# 改了流程，没写文档\n")
    commit(sandbox, "改门禁")
    r = run(sandbox, "tools/check_maintenance.py")
    assert r.returncode == 1
    assert "gate/_gate.py" in r.stdout


def test_doc_in_same_commit_passes(sandbox):
    checker(sandbox)
    write(sandbox, "gate/_gate.py", "# 改了流程\n")
    write(sandbox, DOC, "# 维护方法\n\n## §9\n\n- 记一条\n")
    commit(sandbox, "改门禁并同步维护方法")
    r = run(sandbox, "tools/check_maintenance.py")
    assert r.returncode == 0, r.stdout


def test_disclaimer_tag_passes(sandbox):
    checker(sandbox)
    write(sandbox, "tools/x.py", "# 只改实现\n")
    commit(sandbox, "改实现\n\n[no-procedure-change: 命令与步骤都没变]")
    r = run(sandbox, "tools/check_maintenance.py")
    assert r.returncode == 0, r.stdout


def test_next_commit_cannot_excuse_previous(sandbox):
    """洞一：A 改 gate/ 不带文档，B 只改 README 带免责标签 → 仍然红。"""
    base = checker(sandbox)
    write(sandbox, "gate/_gate.py", "# 偷偷改流程\n")
    commit(sandbox, "改门禁（没写文档）")
    write(sandbox, "README.md", "# 起点\n\n排版\n")
    commit(sandbox, "只改 README\n\n[no-procedure-change: 排版]")

    r = run(sandbox, "tools/check_maintenance.py", "--base", base)
    assert r.returncode == 1, r.stdout
    assert "gate/_gate.py" in r.stdout


def test_staged_mode_reads_message_file(sandbox):
    checker(sandbox)
    write(sandbox, "tools/y.py", "# 暂存\n")
    git(sandbox, "add", "-A")

    msg = sandbox / "msg.txt"
    msg.write_text("改工具\n", encoding="utf-8")
    r = run(sandbox, "tools/check_maintenance.py", "--staged", "--message-file", str(msg))
    assert r.returncode == 1

    msg.write_text("改工具\n\n[no-procedure-change: 只改实现]\n", encoding="utf-8")
    r2 = run(sandbox, "tools/check_maintenance.py", "--staged", "--message-file", str(msg))
    assert r2.returncode == 0, r2.stdout


def test_empty_range_is_not_a_pass(sandbox):
    """空范围＝没查成，不是通过：--base HEAD 必须退 2。"""
    checker(sandbox)
    write(sandbox, "gate/_gate.py", "# 改流程\n")
    commit(sandbox, "改门禁（没写文档）")
    r = run(sandbox, "tools/check_maintenance.py", "--base", "HEAD")
    assert r.returncode == 2, r.stdout
    assert "没查成" in r.stderr


def test_empty_range_is_not_a_pass(sandbox):
    """空范围＝没查成，不是通过：--base HEAD 必须退 2。"""
    checker(sandbox)
    write(sandbox, "gate/_gate.py", "# 改流程\n")
    commit(sandbox, "改门禁（没写文档）")
    r = run(sandbox, "tools/check_maintenance.py", "--base", "HEAD")
    assert r.returncode == 2, r.stdout
    assert "没查成" in r.stderr
