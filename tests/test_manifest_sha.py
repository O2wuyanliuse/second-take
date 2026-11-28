# -*- coding: utf-8 -*-
"""尺子：包内 MANIFEST.sha256 自洽（ST1.0.9 A）。

build_public_package.py 打出的包带一份 MANIFEST.sha256（逐文件 sha256，不含自身）。
这里钉：自洽（每行 sha256 == 包内该文件字节）、不含自身、行数＝包内文件数−1、
维护侧 check_v13 对包跑绿；tamper 一个文件／删清单 → check_v13 必红。
V13 在维护侧（packaging/ 不进用户包），包里只放 MANIFEST.sha256 本身。
"""
import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="需要本地 git 才能打包")

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verify_pkg_under_test", ROOT / "packaging" / "_verify_package.py")
vp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vp)


def _build_and_extract(base):
    out = base / "pkg.zip"
    r = subprocess.run(
        [sys.executable, "tools/build_public_package.py", "--repo", str(ROOT), "--out", str(out)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    assert r.returncode in (0, 2), r.stdout + r.stderr
    ext = base / "ext"
    with zipfile.ZipFile(out) as z:
        z.extractall(ext)
    tops = [p for p in ext.iterdir() if p.is_dir()]
    assert len(tops) == 1, "包顶层应只有一个 second-take-<ver>/ 目录"
    return tops[0]


def _all_files(root):
    files = []
    for dp, dn, fns in os.walk(root):
        dn[:] = [d for d in dn if d not in (".git", "__pycache__", ".idea", ".vscode")]
        for fn in fns:
            files.append(os.path.join(dp, fn))
    return files


def _manifest_entries(root):
    entries = {}
    for line in (root / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        digest, rel = line.split("  ", 1)
        entries[rel.strip()] = digest.strip()
    return entries


@pytest.fixture(scope="module")
def built_pkg(tmp_path_factory):
    return _build_and_extract(tmp_path_factory.mktemp("built"))


@pytest.fixture()
def pkg(built_pkg, tmp_path):
    dest = tmp_path / "pkg"
    shutil.copytree(built_pkg, dest)
    return dest


def test_manifest_self_consistent(pkg):
    entries = _manifest_entries(pkg)
    assert entries, "MANIFEST.sha256 不该为空"
    for rel, want in entries.items():
        got = hashlib.sha256((pkg / rel).read_bytes()).hexdigest()
        assert got == want, f"{rel} sha256 不符"


def test_manifest_excludes_itself(pkg):
    entries = _manifest_entries(pkg)
    assert "MANIFEST.sha256" not in entries
    assert (pkg / "MANIFEST.sha256").is_file()


def test_manifest_line_count_is_files_minus_one(pkg):
    entries = _manifest_entries(pkg)
    n_files = len(_all_files(pkg))
    assert len(entries) == n_files - 1


def test_check_v13_green_on_built_package(pkg):
    fails, warns = [], []
    vp.check_v13(str(pkg), fails, warns, _all_files(pkg))
    assert fails == [], fails


def test_check_v13_tamper_is_red(pkg):
    entries = _manifest_entries(pkg)
    victim = next(iter(entries))
    fp = pkg / victim
    fp.write_bytes(fp.read_bytes() + b"\n# tampered\n")
    fails, warns = [], []
    vp.check_v13(str(pkg), fails, warns, _all_files(pkg))
    assert any("V13" in f for f in fails), fails


def test_check_v13_missing_manifest_is_red(pkg):
    (pkg / "MANIFEST.sha256").unlink()
    fails, warns = [], []
    vp.check_v13(str(pkg), fails, warns, _all_files(pkg))
    assert any("缺 MANIFEST.sha256" in f for f in fails), fails


def test_check_v13_old_instance_without_manifest_skips(tmp_path):
    """R1-A：旧实例包（_pack 产物，带 从这里开始.txt／00_原著/）无清单 → 只 warn 跳过，不阻断。

    变异：去掉 check_v13 的包类型分流 → 旧包缺清单也 fail，本断言红。
    """
    root = tmp_path / "oldpkg"
    root.mkdir()
    (root / "从这里开始.txt").write_text("旧实例包入口", encoding="utf-8")
    (root / "00_原著").mkdir()
    fails, warns = [], []
    vp.check_v13(str(root), fails, warns, _all_files(root))
    assert fails == [], fails
    assert any("V13 跳过：旧实例包不带清单" in w for w in warns), warns


def test_check_v13_subprocess_on_built_package(pkg):
    """R1-A：维护侧真能跑——子进程对真打的用户包跑验包器，V13 那一行绿。

    用户包跑验器整体 rc 必为 1（V1/V6/V3/V7 查项目内容），只看 V13 行判清单自洽。
    """
    r = subprocess.run(
        [sys.executable, "packaging/_verify_package.py", str(pkg)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
    )
    out = r.stdout + r.stderr
    assert "V13" in out, out
    assert "112 个文件 sha256 全核过" in out, out


def test_check_v13_path_traversal_is_red(pkg):
    """R1-B：清单行换成 ../outside.md（outside 放改坏内容）→ 拒含 .. 路径，必红。"""
    outside = pkg.parent / "outside.md"
    outside.write_text("改坏内容", encoding="utf-8")
    digest = hashlib.sha256(outside.read_bytes()).hexdigest()
    mf = pkg / "MANIFEST.sha256"
    new, replaced = [], False
    for ln in mf.read_text(encoding="utf-8").splitlines():
        if not replaced and ln.strip() and not ln.startswith("#"):
            new.append(digest + "  ../outside.md")
            replaced = True
        else:
            new.append(ln)
    mf.write_text("\n".join(new) + "\n", encoding="utf-8")
    fails, warns = [], []
    vp.check_v13(str(pkg), fails, warns, _all_files(pkg))
    assert any("路径非法" in f for f in fails), fails


def test_check_v13_deleted_file_kept_line_is_red(pkg):
    """R1-B：删一个包内文件、不删清单行 → 集合不等（missing），必红。"""
    victim = next(iter(_manifest_entries(pkg)))
    (pkg / victim).unlink()
    fails, warns = [], []
    vp.check_v13(str(pkg), fails, warns, _all_files(pkg))
    assert any("V13" in f for f in fails), fails
    assert any("缺失" in f for f in fails), fails


def test_check_v13_extra_file_not_listed_is_red(pkg):
    """R1-B：包里多一个清单没列的文件 → 集合不等（extra），必红。"""
    (pkg / "stowaway.txt").write_text("包里有但清单没列", encoding="utf-8")
    fails, warns = [], []
    vp.check_v13(str(pkg), fails, warns, _all_files(pkg))
    assert any("未列入清单" in f for f in fails), fails


def test_build_count_mismatch_is_red(tmp_path, monkeypatch):
    """R2-1：scan_zip 报的包内文件数 != 打包清单 → 并进 bad，rc1 且 zip 被删。

    变异：去掉 bad 里的 or n != len(files) + 1 → 计数不符只打印不判红，本断言红。
    """
    spec = importlib.util.spec_from_file_location("bpp_under_test", ROOT / "tools" / "build_public_package.py")
    bpp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bpp)
    out = tmp_path / "pkg.zip"
    words = ROOT / ".ci" / "denylist.txt"
    monkeypatch.setattr(sys, "argv", [
        "build_public_package.py", "--repo", str(ROOT), "--out", str(out), "--words", str(words)])
    monkeypatch.setattr(bpp, "scan_zip", lambda *a, **k: (0, [], False, []))
    rc = bpp.main()
    assert rc == 1, rc
    assert not out.exists(), "计数不符应删 zip"
