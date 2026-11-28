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
import os
import shutil
import subprocess
import sys
from pathlib import Path
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


def _prepush_stage(sandbox, tmp_path, monkeypatch, with_receipt):
    """真 cmd_check 的舞台：仓库、词表、（可选）回执、空 home（sec 面不在）。"""
    mod = load(sandbox, tmp_path / "review", monkeypatch)
    write(sandbox, "a.py", "print(1)\n")
    head = commit(sandbox, "A")
    write(sandbox, ".ci/denylist.txt", "private-token-not-present\n")
    if with_receipt:
        receipt(tmp_path / "review", head)
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return mod, head


def test_prepush_empty_stdin_without_receipt_reports_both(
        sandbox, tmp_path, monkeypatch, capsys):
    """R2：空 stdin ＋ 无回执 → 两句都在，不被回执缺失误挡。"""
    mod, _ = _prepush_stage(sandbox, tmp_path, monkeypatch, with_receipt=False)
    monkeypatch.setattr(mod.sys, "stdin", io.StringIO("\n"))
    real_run = subprocess.run

    def no_seal(cmd, **kwargs):
        assert "verify_release.py" not in " ".join(map(str, cmd)), \
            "空 refs 不能交给下游假装核过"
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(mod.subprocess, "run", no_seal)
    rc = mod.main(["pre-push"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "没收到推送清单（stdin 空），封条核不了 refs" in out
    assert "还没有复核回执" in out


def test_prepush_empty_stdin_with_receipt_reports_only_stdin(
        sandbox, tmp_path, monkeypatch, capsys):
    """R2：空 stdin ＋ 有回执 → 只报 stdin 句，不再误报缺回执。"""
    mod, _ = _prepush_stage(sandbox, tmp_path, monkeypatch, with_receipt=True)
    monkeypatch.setattr(mod.sys, "stdin", io.StringIO("\n"))
    real_run = subprocess.run

    def no_seal(cmd, **kwargs):
        assert "verify_release.py" not in " ".join(map(str, cmd)), \
            "空 refs 不能交给下游假装核过"
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(mod.subprocess, "run", no_seal)
    rc = mod.main(["pre-push"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "没收到推送清单（stdin 空），封条核不了 refs" in out
    assert "还没有复核回执" not in out


def test_prepush_normal_stdin_with_receipt_passes(sandbox, tmp_path, monkeypatch):
    """R2：正常 refs ＋ 有回执 → rc0，完整清单原样交给封条下游。"""
    mod, head = _prepush_stage(sandbox, tmp_path, monkeypatch, with_receipt=True)
    refs = "refs/heads/main %s refs/heads/main %s\n" % (head, "0" * 40)
    monkeypatch.setattr(mod.sys, "stdin", io.StringIO(refs))
    real_run = subprocess.run
    calls = []

    def fake_seal(cmd, **kwargs):
        if "verify_release.py" in " ".join(map(str, cmd)):
            calls.append((cmd, kwargs))
            return SimpleNamespace(returncode=0)
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(mod.subprocess, "run", fake_seal)
    rc = mod.main(["pre-push"])
    assert rc == 0
    assert len(calls) == 1
    assert calls[0][1]["input"] == refs


def test_install_refreshes_forwarders_and_backs_up_old_hooks(
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
    forwarder = (gate / "review_gate.py").read_text(encoding="utf-8")
    assert "为什么这里只留转发、不留第二份完整拷贝：两份迟早不同步" in forwarder
    assert 'sys.path.insert(0, str(repo / "tools"))' in forwarder
    assert "import review_gate" in forwarder
    assert "sys.exit(review_gate.main(sys.argv[1:]))" in forwarder
    assert "# refreshed gate" not in forwarder
    for name, old in (("pre-push", "# old hook"), ("review_gate.py", "# stale gate")):
        backups = list(gate.glob(name + ".bak-*"))
        assert len(backups) == 1
        assert old in backups[0].read_text(encoding="utf-8")
    hook = (gate / "pre-push").read_text(encoding="utf-8")
    assert 'root="$(git rev-parse --show-toplevel)" || exit 1' in hook
    assert "SECOND_TAKE_PYTHON" in hook
    assert "find_py" in hook
    assert "[blocked] 找不到词表" in hook
    assert 'exec "$PY" -X utf8 "$root/.git/gate/review_gate.py" pre-push "$@"' in hook


def _install_real_gate(sandbox, review_dir, monkeypatch):
    """装真逻辑；只把封条下游换成能报告收到 refs 的探针。"""
    mod = load(sandbox, review_dir, monkeypatch)
    write(sandbox, "tools/review_gate.py",
          (REPO / "tools" / "review_gate.py").read_text(encoding="utf-8"))
    write(sandbox, "tools/verify_release.py",
          "import sys\n"
          "for line in sys.stdin.read().splitlines():\n"
          "    print('[seal] 逐 ref 核验通过：' + line.split()[0])\n")
    write(sandbox, "a.py", "print(1)\n")
    head = commit(sandbox, "A")
    receipt(review_dir, head)
    write(sandbox, ".ci/denylist.txt", "private-token-not-present\n")
    assert mod.main(["install", "--repo", str(sandbox)]) == 0
    return head


def _git_sh():
    shell = shutil.which("sh")
    if shell:
        return shell
    git = shutil.which("git")
    if not git:
        raise AssertionError("本机没有 git，无法验 sh 推送壳")
    git_path = Path(git).resolve()
    candidates = [
        git_path.with_name("sh.exe"),
        git_path.parent.parent / "bin" / "sh.exe",
        git_path.parent.parent / "usr" / "bin" / "sh.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise AssertionError("本机没有 Git sh，无法验 sh 推送壳")


def test_installed_forwarder_check_uses_repo_words_not_git_words(
        sandbox, tmp_path, monkeypatch):
    review_dir = tmp_path / "review"
    _install_real_gate(sandbox, review_dir, monkeypatch)
    monkeypatch.delenv("SECOND_TAKE_REPO", raising=False)
    monkeypatch.delenv("SECOND_TAKE_WORDS", raising=False)
    monkeypatch.setenv("PYTHONIOENCODING", "utf-8")
    gate = sandbox / ".git" / "gate"
    result = subprocess.run(
        [sys.executable, str(gate / "review_gate.py"), "check"],
        cwd=gate, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[leak] 待推内容干净" in result.stdout
    assert "找不到词表" not in result.stdout
    assert ".git\\.ci" not in result.stdout


def test_installed_sh_hook_routes_stdin_through_all_gates(
        sandbox, tmp_path, monkeypatch):
    review_dir = tmp_path / "review"
    head = _install_real_gate(sandbox, review_dir, monkeypatch)
    home = tmp_path / "home"
    write(home, ".second-take/checks/sec_surface.py",
          "for n in range(1, 5):\n"
          "    print('[sec] door %s 绿' % n)\n")
    monkeypatch.delenv("SECOND_TAKE_REPO", raising=False)
    monkeypatch.setenv("SECOND_TAKE_PYTHON", sys.executable)
    monkeypatch.setenv("SECOND_TAKE_WORDS", str(sandbox / ".ci" / "denylist.txt"))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("PYTHONIOENCODING", "utf-8")
    refs = "refs/heads/main %s refs/heads/main %s\n" % (head, "0" * 40)
    result = subprocess.run(
        [_git_sh(), ".git/gate/pre-push", "origin", "https://example.invalid/repo.git"],
        cwd=sandbox, input=refs, capture_output=True, text=True, encoding="utf-8",
        env=os.environ.copy())
    assert result.returncode == 0, result.stdout + result.stderr
    for n in range(1, 5):
        assert "[sec] door %s 绿" % n in result.stdout
    assert "[seal] 逐 ref 核验通过：refs/heads/main" in result.stdout
    assert "can't open file" not in result.stderr


def test_prepush_shell_reports_when_no_usable_python(sandbox, tmp_path, monkeypatch):
    """R1a：候选全是占位壳/坏解释器时，钩子给可读 [blocked]＋试过清单，不静默。"""
    review_dir = tmp_path / "review"
    _install_real_gate(sandbox, review_dir, monkeypatch)
    stub = tmp_path / "stub"
    stub.mkdir()
    for name in ("python3", "python", "py"):
        f = stub / name
        f.write_text("#!/bin/sh\nexit 9\n", encoding="utf-8", newline="\n")
        f.chmod(0o755)
    git = shutil.which("git")
    assert git, "需要 git 才能跑推送壳"
    gitdir = str(Path(git).resolve().parent)
    env = os.environ.copy()
    env["PATH"] = str(stub) + os.pathsep + gitdir
    env.pop("SECOND_TAKE_PYTHON", None)
    env.pop("SECOND_TAKE_REPO", None)
    env["PYTHONIOENCODING"] = "utf-8"
    refs = "refs/heads/main %s refs/heads/main %s\n" % ("a" * 40, "0" * 40)
    result = subprocess.run(
        [_git_sh(), ".git/gate/pre-push", "origin", "https://example.invalid/repo.git"],
        cwd=sandbox, input=refs, capture_output=True, text=True, encoding="utf-8", env=env)
    assert result.returncode == 1, result.stdout + result.stderr
    both = result.stdout + result.stderr
    assert "[blocked] 找不到能用的 python" in both
    assert "试过" in both and "python3" in both
    assert "SECOND_TAKE_PYTHON" in both


def test_install_refuses_when_dotgit_is_a_file(tmp_path, monkeypatch, capsys):
    """R1b：worktree/submodule 的 .git 是文件，install 要明确报错而不是炸栈。"""
    repo = tmp_path / "wt"
    (repo / "tools").mkdir(parents=True)
    (repo / "tools" / "review_gate.py").write_text("# gate\n", encoding="utf-8")
    (repo / ".git").write_text("gitdir: ../real/.git/worktrees/wt\n", encoding="utf-8")
    mod = load(repo, tmp_path / "review", monkeypatch)
    rc = mod.main(["install", "--repo", str(repo)])
    out = capsys.readouterr().out
    assert rc == 1
    assert ".git 不是目录" in out


def test_check_missing_words_fails_closed(sandbox, tmp_path, monkeypatch, capsys):
    """R2：缺词表时 check 必须 fail-closed（rc1），报文不再自相矛盾。"""
    mod = load(sandbox, tmp_path / "review", monkeypatch)
    write(sandbox, "a.py", "print(1)\n")
    head = commit(sandbox, "A")
    receipt(tmp_path / "review", head)        # 有回执，排除「缺回执」干扰
    rc = mod.main(["check"])                  # 沙箱里没有 .ci/denylist.txt
    out = capsys.readouterr().out
    assert rc == 1
    assert "不能算干净，本次不放行" in out
    assert "但闸不因此放行任何东西" not in out
