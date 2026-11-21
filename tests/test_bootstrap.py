# -*- coding: utf-8 -*-
"""启动自检：它说「可以开工」的时候，是真的可以开工。"""

from helpers import copy_into, run


def bootstrap(sandbox):
    copy_into(sandbox, "tools/bootstrap.py", "config.example.json")


def test_empty_repo_is_not_ready(sandbox):
    bootstrap(sandbox)
    r = run(sandbox, "tools/bootstrap.py", "--check")
    assert r.returncode == 1
    assert "缺少目录" in r.stdout
    assert "环境未合格" in r.stdout


def test_init_creates_workspace_and_config(sandbox):
    bootstrap(sandbox)
    r = run(sandbox, "tools/bootstrap.py")
    assert r.returncode == 0, r.stdout + r.stderr
    for sub in ("input", "output", "cache"):
        assert (sandbox / "workspace" / sub).is_dir()
    assert (sandbox / "config.local.json").is_file()
    assert "环境就绪" in r.stdout


def test_init_is_idempotent(sandbox):
    bootstrap(sandbox)
    run(sandbox, "tools/bootstrap.py")
    first = (sandbox / "config.local.json").read_bytes()
    r = run(sandbox, "tools/bootstrap.py")
    assert r.returncode == 0
    assert (sandbox / "config.local.json").read_bytes() == first
    assert "已存在, 不动" in r.stdout


def test_check_passes_after_init(sandbox):
    bootstrap(sandbox)
    run(sandbox, "tools/bootstrap.py")
    r = run(sandbox, "tools/bootstrap.py", "--check")
    assert r.returncode == 0, r.stdout
    assert "可以开工" in r.stdout


def test_root_flag_wins_over_repo_workspace(sandbox, tmp_path):
    bootstrap(sandbox)
    other = tmp_path / "elsewhere" / "ws"
    r = run(sandbox, "tools/bootstrap.py", "--root", str(other))
    assert r.returncode == 0, r.stdout
    assert (other / "output").is_dir()
    assert not (sandbox / "workspace").exists()
    # 工作区在别处，--check 也要认这个 --root，否则「建好了却说不合格」
    r2 = run(sandbox, "tools/bootstrap.py", "--check", "--root", str(other))
    assert r2.returncode == 0, r2.stdout
