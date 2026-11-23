# -*- coding: utf-8 -*-
"""体检与清理：dry-run 必须一个字节都不动；input/ output/ 永不入选。

这两条是「清理工具」最容易出事的地方——一次误删比一百次漏删贵得多，
所以这里测的不是「能不能删」，是「不该删的时候真的没删」。
"""

import os
import time
from pathlib import Path

from helpers import copy_into, run

OLD = time.time() - 8 * 86400


def make_tree(root):
    """一份工作区：cache 里一旧一新，output 里放一个同样旧的文件当诱饵。"""
    copy_into(root, "tools/doctor.py")
    for name in ("input", "output", "cache"):
        (Path(root) / "workspace" / name).mkdir(parents=True, exist_ok=True)

    cache_old = Path(root) / "workspace" / "cache" / "old.tmp"
    cache_old.write_text("x" * 1024, encoding="utf-8")
    os.utime(cache_old, (OLD, OLD))

    out_old = Path(root) / "workspace" / "output" / "keep.txt"
    out_old.write_text("别删我", encoding="utf-8")
    os.utime(out_old, (OLD, OLD))

    cache_new = Path(root) / "workspace" / "cache" / "new.tmp"
    cache_new.write_text("刚写的", encoding="utf-8")

    return cache_old, out_old, cache_new


def test_six_lines(sandbox):
    copy_into(sandbox, "tools/doctor.py")
    r = run(sandbox, "tools/doctor.py")
    assert r.returncode == 0, r.stderr
    for i in range(1, 7):
        assert "[%d/6]" % i in r.stdout, r.stdout


def test_dry_run_deletes_nothing(tmp_path):
    cache_old, out_old, cache_new = make_tree(tmp_path)
    before = {p: p.read_bytes() for p in (cache_old, out_old, cache_new)}

    r = run(tmp_path, "tools/doctor.py", "--tidy")
    assert r.returncode == 0, r.stderr
    assert "将清理" in r.stdout
    assert "什么都没删" in r.stdout

    for p, blob in before.items():
        assert p.exists(), "dry-run 把 %s 删了" % p
        assert p.read_bytes() == blob


def test_yes_deletes_cache_only(tmp_path):
    cache_old, out_old, cache_new = make_tree(tmp_path)

    r = run(tmp_path, "tools/doctor.py", "--tidy", "--yes")
    assert r.returncode == 0, r.stderr

    assert not cache_old.exists(), "cache 里超过 7 天的文件应当被删"
    assert cache_new.exists(), "cache 里新文件不该被删"
    assert out_old.exists(), "output 里的文件永不触碰"
