# -*- coding: utf-8 -*-
"""发版脚本的判据：版本号比较、CHANGELOG 两栏、pack_urls 重写。

**不测 git 与 tag**——那要真发一次版。这里只测「它会不会放一个不该发的版本过去」。
"""

import importlib.util
import json
import os
from pathlib import Path

import pytest

from helpers import REPO, commit, copy_into, git, write

_spec = importlib.util.spec_from_file_location("release_mod", REPO / "tools" / "release.py")
release = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release)


@pytest.fixture(autouse=True)
def _fixed_owner(monkeypatch):
    """测 URL 重写不需要真仓库：把 owner 钉死，测试与任何人的 origin 无关。"""
    monkeypatch.setattr(release, "_OWNER_REPO", "example/second-take")


GOOD = """# CHANGELOG

## v0.5.1 · 2026-11-22

### 对你有影响

- 新增三份治理文件

### 没动什么

- 发版工具与门禁逻辑
"""


def test_vtuple_orders_numerically():
    assert release.vtuple("0.10.0") > release.vtuple("0.9.9")
    assert release.vtuple("0.5.1") > release.vtuple("0.5.0")


def test_changelog_good_section_passes(tmp_path, monkeypatch):
    f = tmp_path / "CHANGELOG.md"
    f.write_text(GOOD, encoding="utf-8")
    monkeypatch.setattr(release, "CHANGELOG", f)
    release.check_changelog("0.5.1", "2026-11-22")  # 不抛就是通过


def test_changelog_banned_word_rejected(tmp_path, monkeypatch):
    f = tmp_path / "CHANGELOG.md"
    f.write_text(GOOD.replace("新增三份治理文件", "优化 加载速度"), encoding="utf-8")
    monkeypatch.setattr(release, "CHANGELOG", f)
    with pytest.raises(release.Bad) as e:
        release.check_changelog("0.5.1", "2026-11-22")
    assert "禁词" in str(e.value)


def test_build_latest_keeps_keys_and_moves_urls():
    old = {
        "version": "0.5.0",
        "date": "2026-11-21",
        "channel": "stable",
        "severity": "normal",
        "min_client": "0.2.0",
        "notes_url": "https://example.com/second-take/releases/tag/v0.5.0",
        "tip": "",
        "pack_urls": {"windows": "https://example.com/second-take/releases/download/v0.5.0/second-take-0.5.0-win.zip"},
    }
    data = release.build_latest(old, "0.5.1", "2026-11-22", "stable", "normal")
    assert data["version"] == "0.5.1"
    assert set(data["pack_urls"]) == {"windows"}
    assert "/v0.5.1/" in data["pack_urls"]["windows"]
    assert "0.5.1-win.zip" in data["pack_urls"]["windows"]
    assert data["notes_url"].endswith("/v0.5.1")
    assert old["version"] == "0.5.0", "不能就地改掉入参——dry-run 之后还要能回滚"


def test_repo_slug_returns_empty_without_origin(monkeypatch):
    """没有 origin 时返回空串，不是退出——解压就能用的包不能被 import 炸掉。"""
    monkeypatch.setattr(release, "GIT", "git")
    monkeypatch.setattr(release.subprocess, "run",
                        lambda *a, **k: type("R", (), {"stdout": ""})())
    assert release.repo_slug() == ""


def test_owner_repo_empty_when_nothing_available(monkeypatch):
    monkeypatch.setattr(release, "_OWNER_REPO", None)
    monkeypatch.setattr(release, "repo_slug", lambda: "")
    monkeypatch.delenv("SECOND_TAKE_OWNER", raising=False)
    assert release.owner_repo() == ""


def test_owner_repo_prefers_env(monkeypatch):
    monkeypatch.setattr(release, "_OWNER_REPO", None)
    monkeypatch.setenv("SECOND_TAKE_OWNER", "someone/else")
    assert release.owner_repo() == "someone/else"


def load_release_in(root):
    """按临时仓库的路径重新加载一次——ROOT 是模块级常量，不能复用真实仓库那份。"""
    spec = importlib.util.spec_from_file_location(
        "release_sandbox", Path(root) / "tools" / "release.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._OWNER_REPO = "example/second-take"
    return mod


def test_commit_failure_does_not_drop_previous_commit(sandbox):
    """commit 失败时只还原文件字节，不许 reset 掉**上一个**提交。

    2026-11-23 小渊在工作区副本里撞到过：钩子一红，HEAD 从 49435f0 掉到 3bac61a，
    撤掉的是一个与本次发版无关的提交。真实仓库那次只是恰好没走这条分支。
    """
    copy_into(sandbox, "tools/release.py")
    write(sandbox, "README.md", "# 起点\n")
    commit(sandbox, "起点")

    latest_old = json.loads((REPO / "latest.json").read_text(encoding="utf-8"))
    latest_old["version"] = "0.5.0"
    write(sandbox, "VERSION", "0.5.0 · 2026-11-22\n")
    write(sandbox, "latest.json", json.dumps(latest_old, ensure_ascii=False, indent=2))
    commit(sandbox, "0.5.0")
    head_protected = git(sandbox, "rev-parse", "HEAD").stdout.strip()

    # 让 commit 必然失败：一条 exit 1 的 pre-commit 钩子。
    hook = Path(sandbox) / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    os.chmod(hook, 0o755)

    mod = load_release_in(sandbox)
    with pytest.raises(mod.Broken):
        mod.write_all("0.6.0", "2026-11-23", "stable", "normal", latest_old, False)

    assert git(sandbox, "rev-parse", "HEAD").stdout.strip() == head_protected, \
        "上一个提交被 reset 掉了——这正是要防的那个 bug"
    assert (Path(sandbox) / "VERSION").read_text(encoding="utf-8").startswith("0.5.0"), \
        "文件字节没还原"
    assert git(sandbox, "tag").stdout.strip() == "", "不该留下半个 tag"
