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
_PACK_TIMEOUT = 120


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


def _length_exemptions():
    path = ROOT / "docs/maintain/_style基线.md"
    if not path.exists():
        return set()
    exemptions = set()
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "`")):
            continue
        location, sep, reason = line.partition(" — ")
        if not sep or not reason.strip() or ":" not in location:
            continue
        rel, name = location.rsplit(":", 1)
        if rel.endswith(".py") and name.isidentifier():
            exemptions.add((rel, name))
    return exemptions


def _length_issue(rel, fn, exemptions):
    n = _fn_len(fn)
    if n <= 80 or (rel, fn.name) in exemptions:
        return None
    return f"{rel}:{fn.lineno}: {fn.name} {n} 行 > 80"


def _marked_duplicate(fn, lines):
    body = lines[fn.lineno - 1:getattr(fn, "end_lineno", fn.lineno)]
    prefix = "# 故意重复："
    for line in body[:4]:
        comment = line.strip()
        if comment.startswith(prefix) and comment[len(prefix):].strip():
            return True
    return False


def _broad_exception(node):
    if isinstance(node, ast.Name):
        return node.id in ("Exception", "BaseException")
    if isinstance(node, ast.Tuple):
        return any(_broad_exception(elt) for elt in node.elts)
    return False


def _silent_exit(node):
    if isinstance(node, (ast.Pass, ast.Continue)):
        return True
    if not isinstance(node, ast.Return):
        return False
    value = node.value
    if value is None or isinstance(value, ast.Constant):
        return True
    if isinstance(value, (ast.List, ast.Dict, ast.Tuple, ast.Set)):
        return not getattr(value, "elts", getattr(value, "keys", []))
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
        return value.func.id == "set" and not value.args and not value.keywords
    return isinstance(value, ast.UnaryOp) and isinstance(value.op, ast.USub) and isinstance(value.operand, ast.Constant)


def _bare_except(fn, lines):
    if not isinstance(fn, ast.ExceptHandler):
        return False
    if fn.type is None:
        return True
    if not _broad_exception(fn.type) or len(fn.body) != 1:
        return False
    exit_node = fn.body[0]
    if not _silent_exit(exit_node):
        return False
    _, marker, reason = lines[exit_node.lineno - 1].partition("# 吞：")
    return not marker or not reason.strip()


def _function_fingerprint(fn):
    """同名之外再比 AST：参数、返回标注与剥掉 docstring 的函数体。"""
    body = list(fn.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    return (
        ast.dump(fn.args, include_attributes=False),
        ast.dump(fn.returns, include_attributes=False) if fn.returns else "",
        ast.dump(ast.Module(body=body, type_ignores=[]), include_attributes=False),
    )


def _duplicate_issues(seen):
    issues = []
    for name, variants in seen.items():
        if name == "main":
            continue
        for locs in variants.values():
            if len({rel for rel, _, _, _ in locs}) < 2:
                continue
            for rel, ln, marked, _ in locs:
                if not marked:
                    issues.append(f"{rel}:{ln}: 同名同体函数 {name} 跨文件重复，未标 故意重复")
    return issues


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


def _check_package_count(root, count):
    # 打包计数检查不依赖 .ci 词表（词表归 _leakscan）。
    # rc2＝缺词表黄档，包仍打出，计数照核。
    # subprocess 起不来／超时是真红，不当「查不了」。
    try:
        import zipfile, tempfile, subprocess
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "pkg.zip"
            r = subprocess.run(
                [sys.executable, "tools/build_public_package.py", "--repo", str(root), "--out", str(out)],
                cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=_PACK_TIMEOUT,
            )
            if r.returncode not in (0, 2):
                return f"打包失败：{r.stdout + r.stderr}"
            with zipfile.ZipFile(out) as z:
                files = [n for n in z.namelist() if not n.endswith("/")]
            if len(files) != count:
                return f"打包计数 {len(files)} != 清单有效项 {count}"
    except Exception as e:
        return f"打包失败：{type(e).__name__}: {e}"
    return None


def main():
    issues = []
    exemptions = _length_exemptions()
    seen = defaultdict(lambda: defaultdict(list))
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
                issue = _length_issue(rel, fn, exemptions)
                if issue:
                    issues.append(issue)
                if not fn.name.startswith("test") and fn.name != "__init__":
                    seen[fn.name][_function_fingerprint(fn)].append((rel, fn.lineno, _marked_duplicate(fn, lines), fn))
        for node in ast.walk(tree):
            if _bare_except(node, lines):
                issues.append(f"{rel}:{node.lineno}: 宽异常静默出口未在出口行写吞的理由")
    issues.extend(_duplicate_issues(seen))
    count = _load_manifest()
    if count is not None:
        issue = _check_package_count(ROOT, count)
        if issue:
            issues.append(issue)
    for i in issues:
        print(i)
    print(f"违规 {len(issues)} 条")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
