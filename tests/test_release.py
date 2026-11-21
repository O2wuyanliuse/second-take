# -*- coding: utf-8 -*-
"""发版脚本的判据：版本号比较、CHANGELOG 两栏、pack_urls 重写。

**不测 git 与 tag**——那要真发一次版。这里只测「它会不会放一个不该发的版本过去」。
"""

import importlib.util

import pytest

from helpers import REPO

_spec = importlib.util.spec_from_file_location("release_mod", REPO / "tools" / "release.py")
release = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release)


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
        "notes_url": "https://github.com/O2wuyanliuse/second-take/releases/tag/v0.5.0",
        "tip": "",
        "pack_urls": {"windows": "https://github.com/O2wuyanliuse/second-take/releases/download/v0.5.0/second-take-0.5.0-win.zip"},
    }
    data = release.build_latest(old, "0.5.1", "2026-11-22", "stable", "normal")
    assert data["version"] == "0.5.1"
    assert set(data["pack_urls"]) == {"windows"}
    assert "/v0.5.1/" in data["pack_urls"]["windows"]
    assert "0.5.1-win.zip" in data["pack_urls"]["windows"]
    assert data["notes_url"].endswith("/v0.5.1")
    assert old["version"] == "0.5.0", "不能就地改掉入参——dry-run 之后还要能回滚"
