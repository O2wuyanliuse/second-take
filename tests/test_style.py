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


def test_all_functions_over_80_are_reported():
    source = "def run(items):\n" + "    value = items\n" * 80
    fn = ast.parse(source).body[0]
    assert "81 行 > 80" in style._length_issue("tools/a.py", fn, set())
    assert style._length_issue("tools/a.py", fn, {("tools/a.py", "run")}) is None
    main_fn = ast.parse(source.replace("def run", "def main")).body[0]
    assert "main 81 行 > 80" in style._length_issue("tools/a.py", main_fn, set())


def test_length_exemptions_require_exact_path_function_and_reason(tmp_path, monkeypatch):
    baseline = tmp_path / "docs" / "maintain" / "_style基线.md"
    baseline.parent.mkdir(parents=True)
    baseline.write_text(
        "tools/a.py:run —\n"
        "tools/b.py:run —   \n"
        "# tools/c.py:run — 注释不算\n"
        "tools/d.py:not-a-name — 函数名无效\n"
        "tools/e.py:run — 已登记的历史原因\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(style, "ROOT", tmp_path)
    assert style._length_exemptions() == {("tools/e.py", "run")}


def test_marked_template_copy_only_exempts_itself():
    issues = duplicates(
        ("templates/checks/a.py", "def run(items):\n    # 故意重复：模板需独立带走\n    return sorted(items)\n"),
        ("tools/b.py", "def run(items):\n    return sorted(items)\n"),
    )
    assert len(issues) == 1
    assert issues[0].startswith("tools/b.py:")
    assert "同名同体函数 run" in issues[0]


def test_duplicate_marker_must_be_a_comment_with_nonempty_reason():
    def marked(body):
        source = "def run(items):\n" + body + "    return sorted(items)\n"
        fn = ast.parse(source).body[0]
        return style._marked_duplicate(fn, source.splitlines())

    assert marked("    # 故意重复：模板需独立带走\n")
    assert not marked("    # 故意重复：\n")
    assert not marked("    # 故意重复：   \n")
    assert not marked("    note = '# 故意重复：字符串不算'\n")
    assert not marked("    ## 故意重复：标题不算\n")


def test_swallow_reason_must_share_pass_line():
    hanging = "try:\n    work()\nexcept Exception:\n    pass\n    # 吞：旧写法\n"
    inline = "try:\n    work()\nexcept Exception:\n    pass  # 吞：新写法\n"
    hanging_node = next(node for node in ast.walk(ast.parse(hanging)) if isinstance(node, ast.ExceptHandler))
    inline_node = next(node for node in ast.walk(ast.parse(inline)) if isinstance(node, ast.ExceptHandler))
    assert style._bare_except(hanging_node, hanging.splitlines())
    assert not style._bare_except(inline_node, inline.splitlines())
