import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("repo_style_package", ROOT / "packaging" / "_style.py")
style = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(style)


@pytest.mark.skipif(shutil.which("git") is None, reason="需要本地 git 才能构造无 .ci 的干净树")
def test_style_main_is_green_in_clean_clone_without_ci(tmp_path):
    clone = tmp_path / "repo"
    subprocess.run(["git", "clone", "-q", str(ROOT), str(clone)], check=True)
    assert not (clone / ".ci").exists()
    env = dict(os.environ, PYTHONUTF8="1")
    result = subprocess.run(
        [sys.executable, "packaging/_style.py"],
        cwd=clone, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_package_count_mismatch_is_red():
    expected = style._load_manifest()
    issue = style._check_package_count(ROOT, expected + 1)
    assert issue == f"打包计数 {expected} != 清单有效项 {expected + 1}"


def test_package_builder_failure_is_red(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="boom"),
    )
    issue = style._check_package_count(ROOT, 113)
    assert "打包失败" in issue
    assert "boom" in issue


def test_package_builder_timeout_is_red(monkeypatch):
    seen = {}

    def slow_pack(*args, **kwargs):
        seen["timeout"] = kwargs.get("timeout")
        raise subprocess.TimeoutExpired(args[0], kwargs.get("timeout"))

    monkeypatch.setattr(subprocess, "run", slow_pack)
    issue = style._check_package_count(ROOT, 113)
    assert seen["timeout"] == 120
    assert "打包失败" in issue
    assert "TimeoutExpired" in issue
