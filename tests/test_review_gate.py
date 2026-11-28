# -*- coding: utf-8 -*-
"""复核闸的判据：回执覆盖到哪一步算数。

2026-11-24 的缺口：`release.py` 的提交永远在回执之后产生，而闸要求
`head == HEAD`，于是每次发版都推不动，只能靠人看出来再补签一次。
放行口径定成「祖先 ＋ 差异只含 VERSION/latest.json」——但**多一个文件就不行**。
这条必须有用例：放宽的那天如果没人钉住，就等于敞开。
"""

import importlib.util
import io
import json
from types import SimpleNamespace

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


def test_prepush_forwards_the_same_stdin_to_seal(sandbox, tmp_path, monkeypatch):
    """回执检查之后，verify_release 仍须收到完整非空 refs。"""
    mod = load(sandbox, tmp_path / "review", monkeypatch)
    refs = "refs/heads/main abc123 refs/heads/main def456\n"
    monkeypatch.setattr(mod.sys, "stdin", io.StringIO(refs))
    monkeypatch.setattr(mod, "cmd_check", lambda args: 0)
    monkeypatch.setattr(mod, "_run_security_surface", lambda: 0)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    rc = mod.main(["pre-push", "origin", "https://example.invalid/repo.git"])
    assert rc == 0
    assert len(calls) == 1
    cmd, kwargs = calls[0]
    assert cmd[1:] == ["tools/verify_release.py", "--push-gate", "--words",
                       str(sandbox / ".ci" / "denylist.txt"), "--repo", str(sandbox)]
    assert kwargs["input"] == refs


def test_prepush_empty_stdin_is_red(sandbox, tmp_path, monkeypatch, capsys):
    mod = load(sandbox, tmp_path / "review", monkeypatch)
    monkeypatch.setattr(mod.sys, "stdin", io.StringIO("\n"))
    monkeypatch.setattr(mod, "cmd_check", lambda args: 0)

    def must_not_run(*args, **kwargs):
        raise AssertionError("空 refs 不能交给下游假装核过")

    monkeypatch.setattr(mod.subprocess, "run", must_not_run)
    rc = mod.main(["pre-push"])
    assert rc == 1
    assert "没收到推送清单（stdin 空），封条核不了 refs" in capsys.readouterr().out


def test_install_refreshes_copy_and_backs_up_old_hook(
        sandbox, tmp_path, monkeypatch):
    mod = load(sandbox, tmp_path / "review", monkeypatch)
    write(sandbox, "tools/review_gate.py", "# refreshed gate\n")
    write(sandbox, ".git/gate/pre-push", "#!/bin/sh\n# old hook\n")
    write(sandbox, ".git/gate/review_gate.py", "# stale gate\n")
    monkeypatch.setattr(mod, "sh", lambda *args, **kwargs: SimpleNamespace(
        returncode=0, stderr=""))
    rc = mod.main(["install", "--repo", str(sandbox)])
    assert rc == 0
    gate = sandbox / ".git" / "gate"
    assert (gate / "review_gate.py").read_text(encoding="utf-8") == "# refreshed gate\n"
    backups = list(gate.glob("pre-push.bak-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "#!/bin/sh\n# old hook\n"
    hook = (gate / "pre-push").read_text(encoding="utf-8")
    assert 'cd "$(git rev-parse --git-path gate)"' in hook
    assert 'python review_gate.py pre-push "$@"' in hook
