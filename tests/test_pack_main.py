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


def test_main_passes_real_argv_to_parse_args(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "packaging" / "_pack.py"
    spec = importlib.util.spec_from_file_location("pack_main_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []

    def recorder(argv):
        calls.append(argv)
        return True, False, None

    monkeypatch.setattr(module, "_preflight", lambda: None)
    monkeypatch.setattr(module, "_parse_args", recorder)
    monkeypatch.setattr(sys, "argv", ["_pack.py", "--dry-run"])
    try:
        module.main()
    except NameError:
        raise
    except Exception:
        pass  # 吞：只吞下游 collect；调参那一段与断言都不吞。
    except SystemExit:
        pass  # 吞：只吞下游 collect 的 SystemExit；调参与断言仍在外面。
    assert calls == [["--dry-run"]]
