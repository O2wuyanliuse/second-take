# -*- coding: utf-8 -*-
"""复核闸的判据：回执覆盖到哪一步算数。

2026-11-24 的缺口：`release.py` 的提交永远在回执之后产生，而闸要求
`head == HEAD`，于是每次发版都推不动，只能靠人看出来再补签一次。
放行口径定成「祖先 ＋ 差异只含 VERSION/latest.json」——但**多一个文件就不行**。
这条必须有用例：放宽的那天如果没人钉住，就等于敞开。
"""

import importlib.util
import json

from helpers import REPO, commit, write


def load(sandbox, review_dir, monkeypatch):
    monkeypatch.setenv("SECOND_TAKE_REPO", str(sandbox))
    monkeypatch.setenv("SECOND_TAKE_REVIEW_DIR", str(review_dir))
    spec = importlib.util.spec_from_file_location(
        "rg_under_test", REPO / "tools" / "review_gate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def receipt(review_dir, head, verdict="通过"):
    review_dir.mkdir(parents=True, exist_ok=True)
    data = {"head": head, "verdict": verdict,
            "implementer": "WB", "reviewer": "小渊"}
    (review_dir / (head + ".json")).write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def test_receipt_on_head_passes(sandbox, tmp_path, monkeypatch):
    mod = load(sandbox, tmp_path / "review", monkeypatch)
    write(sandbox, "a.py", "print(1)\n")
    h = commit(sandbox, "A")
    ok, why = mod.receipt_covers(receipt(tmp_path / "review", h), h)
    assert ok, why


def test_ancestor_with_only_version_files_passes(sandbox, tmp_path, monkeypatch):
    """发版提交是机械产物：回执签在它前面也应该算数。"""
    mod = load(sandbox, tmp_path / "review", monkeypatch)
    write(sandbox, "a.py", "print(1)\n")
    base = commit(sandbox, "A")
    write(sandbox, "VERSION", "1.0.0\n")
    write(sandbox, "latest.json", '{"version": "1.0.0"}\n')
    head = commit(sandbox, "release")
    ok, why = mod.receipt_covers(receipt(tmp_path / "review", base), head)
    assert ok, why


def test_ancestor_with_third_file_is_rejected(sandbox, tmp_path, monkeypatch):
    """小渊点名要的那条：往发版提交里塞第三个文件，必须被拒。"""
    mod = load(sandbox, tmp_path / "review", monkeypatch)
    write(sandbox, "a.py", "print(1)\n")
    base = commit(sandbox, "A")
    write(sandbox, "VERSION", "1.0.0\n")
    commit(sandbox, "release")
    write(sandbox, "backdoor.py", "print('x')\n")     # ← 第三个文件
    head = commit(sandbox, "夹带")
    ok, why = mod.receipt_covers(receipt(tmp_path / "review", base), head)
    assert not ok, "塞了第三个文件还放行，闸就成摆设了"
    assert "backdoor.py" in why


def test_ancestor_with_changelog_is_rejected(sandbox, tmp_path, monkeypatch):
    """CHANGELOG 是内容，不是版本文件——照规矩要签。"""
    mod = load(sandbox, tmp_path / "review", monkeypatch)
    write(sandbox, "a.py", "print(1)\n")
    base = commit(sandbox, "A")
    write(sandbox, "CHANGELOG.md", "# 变了\n")
    head = commit(sandbox, "文档")
    ok, why = mod.receipt_covers(receipt(tmp_path / "review", base), head)
    assert not ok
    assert "CHANGELOG.md" in why


def test_no_receipt_is_rejected(sandbox, tmp_path, monkeypatch):
    mod = load(sandbox, tmp_path / "review", monkeypatch)
    write(sandbox, "a.py", "print(1)\n")
    h = commit(sandbox, "A")
    ok, if_no = mod.receipt_covers(None, h)
    assert not ok
    assert "没有" in if_no


def test_wrong_verdict_is_rejected(sandbox, tmp_path, monkeypatch):
    mod = load(sandbox, tmp_path / "review", monkeypatch)
    write(sandbox, "a.py", "print(1)\n")
    h = commit(sandbox, "A")
    ok, why = mod.receipt_covers(receipt(tmp_path / "review", h, verdict="不通过"), h)
    assert not ok
    assert "不通过" in why


def test_sign_refuses_same_person(sandbox, tmp_path, monkeypatch):
    mod = load(sandbox, tmp_path / "review", monkeypatch)
    write(sandbox, "a.py", "print(1)\n")
    commit(sandbox, "A")
    rc = mod.main(["sign", "--implementer", "WB", "--reviewer", "wb"])
    assert rc == 1, "同名（大小写不同也算）必须拒签"
    assert not (tmp_path / "review").exists() or not list(
        (tmp_path / "review").glob("*.json"))
