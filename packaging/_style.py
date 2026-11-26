#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_style.py — 代码硬约束机查器（不进包）。

查：单函数行数、模块 docstring 行数、裸 except Exception: pass、
跨文件重复 helper（故意重复需标注）、打包计数 == 清单有效项。
退出码：0 无违规 ／ 1 有违规。
"""
import ast
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent


def _iter_files():
    for p in sorted(ROOT.rglob("*.py")):
        if any(part in (".git", "__pycache__", "node_modules", "workspace") for part in p.parts):
            continue
        yield p


def _fn_len(fn):
    return getattr(fn, "end_lineno", fn.lineno) - fn.lineno + 1


def _docstring_lines(tree):
    ds = ast.get_docstring(tree, clean=False)
    return len(ds.splitlines()) if ds else 0


def _marked_duplicate(fn, lines):
    body = lines[fn.lineno - 1:getattr(fn, "end_lineno", fn.lineno)]
    return any("故意重复" in l for l in body[:4])


def _bare_except(fn, lines):
    if not isinstance(fn, ast.ExceptHandler):
        return False
    if fn.type is None:
        return True
    if isinstance(fn.type, ast.Name) and fn.type.id == "Exception":
        if len(fn.body) == 1 and isinstance(fn.body[0], ast.Pass):
            following = lines[fn.end_lineno:fn.end_lineno + 1]
            return not any("# 吞：" in l for l in following)
    return False


def _load_manifest():
    mf = ROOT / "publish_manifest.txt"
    if not mf.exists():
        return None
    n = 0
    for line in mf.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#") and not s.startswith("!"):
            n += 1
    return n


def main():
    issues = []
    seen = defaultdict(list)
    for p in _iter_files():
        rel = p.relative_to(ROOT).as_posix()
        text = p.read_text(encoding="utf-8")
        lines = text.splitlines()
        try:
            tree = ast.parse(text)
        except SyntaxError as e:
            issues.append(f"{rel}: 语法错误 {e}")
            continue
        d = _docstring_lines(tree)
        if d > 15:
            issues.append(f"{rel}: 模块 docstring {d} 行 > 15")
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                n = _fn_len(fn)
                if fn.name == "main" and n > 80:
                    issues.append(f"{rel}:{fn.lineno}: main {n} 行 > 80")
                elif fn.name != "main" and n > 300:
                    issues.append(f"{rel}:{fn.lineno}: {fn.name} {n} 行 > 300")
                if not fn.name.startswith("test") and fn.name != "__init__":
                    seen[fn.name].append((rel, fn.lineno, _marked_duplicate(fn, lines)))
        for node in ast.walk(tree):
            if _bare_except(node, lines):
                issues.append(f"{rel}:{node.lineno}: 裸 except Exception: pass 未写吞的理由")
    for name, locs in seen.items():
        if len(locs) < 2 or name == "main":
            continue
        for rel, ln, marked in locs:
            if not marked:
                issues.append(f"{rel}:{ln}: 同名函数 {name} 跨文件重复，未标 故意重复")
    count = _load_manifest()
    if count is not None:
        try:
            import zipfile, tempfile, subprocess
            with tempfile.TemporaryDirectory() as td:
                out = Path(td) / "pkg.zip"
                r = subprocess.run([sys.executable, "tools/build_public_package.py", "--repo", str(ROOT), "--out", str(out), "--words", str(ROOT / ".ci" / "denylist.txt")], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
                if r.returncode != 0:
                    issues.append(f"打包失败：{r.stdout + r.stderr}")
                else:
                    with zipfile.ZipFile(out) as z:
                        files = [n for n in z.namelist() if not n.endswith("/")]
                    if len(files) != count:
                        issues.append(f"打包计数 {len(files)} != 清单有效项 {count}")
        except Exception as e:
            issues.append(f"打包计数检查失败：{e}")
    for i in issues:
        print(i)
    print(f"违规 {len(issues)} 条")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
