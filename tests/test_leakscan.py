# -*- coding: utf-8 -*-
"""脱敏扫描：**「没查成」必须和「查干净了」分开**。

这六条对应它最容易退化的六个地方：无词表给绿、词表丢了给绿、
命中不报、干净报错、跳过一半算干净、`--deny` 与 `--words` 不同义。
"""

from helpers import commit, copy_into, run, write


def scanner(sandbox):
    copy_into(sandbox, "packaging/_leakscan.py")


def test_no_wordlist_is_not_pass(sandbox):
    scanner(sandbox)
    write(sandbox, "README.md", "什么也没有\n")
    commit(sandbox, "init")
    r = run(sandbox, "packaging/_leakscan.py")
    assert r.returncode == 2
    assert "没给词表" in r.stderr


def test_missing_wordlist_file_is_not_pass(sandbox, tmp_path):
    scanner(sandbox)
    commit(sandbox, "init", allow_empty=True)
    r = run(sandbox, "packaging/_leakscan.py", "--words", str(tmp_path / "不存在.txt"))
    assert r.returncode == 2
    assert "词表不存在" in r.stderr


def test_hit_in_worktree_blocks(sandbox, tmp_path):
    scanner(sandbox)
    words = tmp_path / "words.txt"
    words.write_text("禁区词\n", encoding="utf-8")
    write(sandbox, "docs/笔记.md", "这里出现了禁区词。\n")
    commit(sandbox, "带词的提交")
    r = run(sandbox, "packaging/_leakscan.py", "--words", str(words), "--no-history")
    assert r.returncode == 1
    assert "禁区词" in r.stdout


def test_clean_tree_passes(sandbox, tmp_path):
    scanner(sandbox)
    words = tmp_path / "words.txt"
    words.write_text("禁区词\n", encoding="utf-8")
    write(sandbox, "docs/笔记.md", "这里什么也没有。\n")
    commit(sandbox, "干净提交")
    r = run(sandbox, "packaging/_leakscan.py", "--words", str(words), "--no-history")
    assert r.returncode == 0
    assert "干净" in r.stdout


def test_no_history_with_strict_is_not_pass(sandbox, tmp_path):
    scanner(sandbox)
    words = tmp_path / "words.txt"
    words.write_text("禁区词\n", encoding="utf-8")
    write(sandbox, "README.md", "干净\n")
    commit(sandbox, "init")
    r = run(sandbox, "packaging/_leakscan.py", "--words", str(words), "--no-history", "--strict")
    assert r.returncode == 1
    assert "不算干净" in r.stdout


def test_deny_is_same_as_words(sandbox, tmp_path):
    scanner(sandbox)
    words = tmp_path / "words.txt"
    words.write_text("禁区词\n", encoding="utf-8")
    write(sandbox, "README.md", "禁区词\n")
    commit(sandbox, "带词的提交")
    r = run(sandbox, "packaging/_leakscan.py", "--deny", str(words), "--no-history")
    assert r.returncode == 1
