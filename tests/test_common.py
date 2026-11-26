import shutil
import subprocess
import sys


def test_tools_directory_can_be_copied_and_run(tmp_path):
    target = tmp_path / "tools"
    shutil.copytree("tools", target, ignore=shutil.ignore_patterns("__pycache__"))
    result = subprocess.run(
        [sys.executable, "tools/bootstrap.py", "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stdout + result.stderr
