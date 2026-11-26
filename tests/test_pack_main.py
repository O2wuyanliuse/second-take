import importlib.util
import subprocess
import sys
from pathlib import Path


def test_pack_main_dry_run_has_no_traceback():
    result = subprocess.run(
        [sys.executable, "packaging/_pack.py", "--dry-run"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    output = result.stdout + result.stderr
    assert result.returncode == 2
    assert "[packaging]" in output
    assert "本仓库不含任何项目内容" in output
    assert "can't open file" not in output
    assert "Traceback" not in result.stdout + result.stderr
    assert "NameError" not in result.stdout + result.stderr


def test_pack_main_out_has_no_traceback(tmp_path):
    result = subprocess.run(
        [sys.executable, "packaging/_pack.py", "--out", str(tmp_path / "out")],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    output = result.stdout + result.stderr
    assert result.returncode == 2
    assert "[packaging]" in output
    assert "本仓库不含任何项目内容" in output
    assert "can't open file" not in output
    assert "Traceback" not in result.stdout + result.stderr
    assert "NameError" not in result.stdout + result.stderr


def test_parse_args_uses_passed_argv():
    path = Path(__file__).resolve().parent.parent / "packaging" / "_pack.py"
    spec = importlib.util.spec_from_file_location("pack_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module._parse_args(["--dry-run", "--out", "x"]) == (True, False, str(Path("x").resolve()))
