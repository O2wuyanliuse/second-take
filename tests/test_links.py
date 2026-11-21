# -*- coding: utf-8 -*-
"""断链检查：反引号里的路径存不存在。它只该答这一个问题。"""

from helpers import copy_into, run, write


def links(sandbox):
    copy_into(sandbox, "gate/_links.py", "gate/_ignore.py")


def test_no_markdown_is_not_pass(sandbox):
    links(sandbox)
    write(sandbox, "README.txt", "这里没有 md\n")
    r = run(sandbox, "gate/_links.py")
    assert r.returncode == 2
    assert "没查成" in r.stderr


def test_existing_path_passes(sandbox):
    links(sandbox)
    write(sandbox, "docs/a.md", "# a\n")
    write(sandbox, "README.md", "见 `docs/a.md`。\n")
    r = run(sandbox, "gate/_links.py")
    assert r.returncode == 0, r.stdout
    assert "干净" in r.stdout


def test_broken_path_blocks(sandbox):
    links(sandbox)
    # `docs/` 必须真实存在：脚本只查「本仓库自己的一级目录」下的引用，
    # 目录都不存在时整条候选会被当成「读者项目里的路径」放过。
    write(sandbox, "docs/keep.md", "# keep\n")
    write(sandbox, "README.md", "见 `docs/missing.md`。\n")
    r = run(sandbox, "gate/_links.py")
    assert r.returncode == 1
    assert "docs/missing.md" in r.stdout


def test_declared_project_instance_is_only_a_hint(sandbox):
    links(sandbox)
    write(sandbox, "docs/keep.md", "# keep\n")
    write(sandbox, "README.md",
          "本文出现的 `docs/x.md` 是项目实例，带走后不存在是正常的。\n")
    r = run(sandbox, "gate/_links.py")
    assert r.returncode == 0, r.stdout
    assert "降级为提示" in r.stdout


def test_ignored_dir_is_not_scanned(sandbox):
    links(sandbox)
    write(sandbox, "README.md", "见 `docs/a.md`。\n")
    write(sandbox, "docs/a.md", "# a\n")
    # 缓存目录里的草稿不算本仓库的引用——扫它只会报假断链
    write(sandbox, "__pycache__/草稿.md", "见 `docs/根本没有.md`。\n")
    r = run(sandbox, "gate/_links.py")
    assert r.returncode == 0, r.stdout
