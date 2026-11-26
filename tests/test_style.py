# -*- coding: utf-8 -*-
"""代码硬约束机查的回归用例。"""

import ast
import importlib.util
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("repo_style", ROOT / "packaging" / "_style.py")
style = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(style)


def duplicates(*sources):
    seen = defaultdict(lambda: defaultdict(list))
    for rel, text in sources:
        tree = ast.parse(text)
        fn = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
        seen[fn.name][style._function_fingerprint(fn)].append(
            (rel, fn.lineno, style._marked_duplicate(fn, text.splitlines()), fn)
        )
    return style._duplicate_issues(seen)


def test_same_name_different_body_is_not_a_copy():
    issues = duplicates(
        ("tools/a.py", "def run(items):\n    return len(items)\n"),
        ("tools/b.py", "def run(items):\n    return [str(x) for x in items]\n"),
    )
    assert issues == []


def test_same_name_and_ast_body_is_a_copy():
    issues = duplicates(
        ("tools/a.py", "def run(items):\n    '''甲说明'''\n    return sorted(items)\n"),
        ("tools/b.py", "def run(items):\n    '''乙说明'''\n    return sorted(items)\n"),
    )
    assert len(issues) == 2
    assert all("同名同体函数 run" in issue for issue in issues)


def test_marked_template_copy_does_not_implicate_other_file():
    issues = duplicates(
        ("templates/checks/a.py", "def run(items):\n    # 故意重复：模板需独立带走\n    return sorted(items)\n"),
        ("tools/b.py", "def run(items):\n    return sorted(items)\n"),
    )
    assert issues == []


def test_swallow_reason_must_share_pass_line():
    hanging = "try:\n    work()\nexcept Exception:\n    pass\n    # 吞：旧写法\n"
    inline = "try:\n    work()\nexcept Exception:\n    pass  # 吞：新写法\n"
    hanging_node = next(node for node in ast.walk(ast.parse(hanging)) if isinstance(node, ast.ExceptHandler))
    inline_node = next(node for node in ast.walk(ast.parse(inline)) if isinstance(node, ast.ExceptHandler))
    assert style._bare_except(hanging_node, hanging.splitlines())
    assert not style._bare_except(inline_node, inline.splitlines())
