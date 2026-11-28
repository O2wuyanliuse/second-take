# -*- coding: utf-8 -*-
"""代码硬约束机查的回归用例。"""

import ast
import importlib.util
import io
import tokenize
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
        tokens = [t for t in tokenize.generate_tokens(io.StringIO(text).readline) if t.type == tokenize.COMMENT]
        fn = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
        seen[fn.name][style._function_fingerprint(fn)].append(
            (rel, fn.lineno, style._marked_duplicate(fn, tokens), fn)
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
        "```\n"
        "tools/fenced.py:run — 围栏示例不算\n"
        "```\n"
        "~~~\n"
        "tools/tilde.py:run — 波浪围栏示例不算\n"
        "~~~\n"
        "tools/e.py:Outer.run — 已登记的历史原因\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(style, "ROOT", tmp_path)
    assert style._length_exemptions() == {("tools/e.py", "Outer.run")}


def test_length_exemption_long_fence_not_closed_by_shorter_run(tmp_path, monkeypatch):
    baseline = tmp_path / "docs" / "maintain" / "_style基线.md"
    baseline.parent.mkdir(parents=True)
    baseline.write_text(
        "````\n"
        "```\n"
        "tools/inside.py:run — 四反引号块内三反引号不闭合，此豁免不生效\n"
        "````\n"
        "tools/outside.py:run — 块外正常豁免\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(style, "ROOT", tmp_path)
    assert style._length_exemptions() == {("tools/outside.py", "run")}


def test_length_exemption_short_fence_closed_by_longer_run(tmp_path, monkeypatch):
    """B1：三反引号开、四反引号闭——闭合需 leading 串 ≥ 开长度，四 ≥ 三 → 闭合，块外豁免生效。

    与 test_length_exemption_long_fence_not_closed_by_shorter_run（四开三不闭）互为双向钉子。
    变异：把闭合条件 run_len >= fence[1] 改成 == → 四不等于三不闭合，块外豁免丢失，本断言红。
    """
    baseline = tmp_path / "docs" / "maintain" / "_style基线.md"
    baseline.parent.mkdir(parents=True)
    baseline.write_text(
        "```\n"
        "tools/inside.py:run — 三反引号块内不生效\n"
        "````\n"
        "tools/outside.py:run — 四反引号闭合（≥三）后块外正常豁免\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(style, "ROOT", tmp_path)
    assert style._length_exemptions() == {("tools/outside.py", "run")}


def test_length_exemption_uses_qualified_name_for_nested_functions():
    source = (
        "def outer():\n"
        "    def inner():\n" + "        value = 0\n" * 80
        + "    def other():\n" + "        value = 0\n" * 80
    )
    tree = ast.parse(source)
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    functions = {fn.name: fn for fn in ast.walk(tree) if isinstance(fn, ast.FunctionDef)}
    exemptions = {("tools/a.py", "outer.inner")}
    inner = functions["inner"]
    other = functions["other"]
    inner_name = style._qualified_name(inner, parents)
    other_name = style._qualified_name(other, parents)
    assert inner_name == "outer.inner"
    assert style._length_issue("tools/a.py", inner, exemptions, inner_name) is None
    assert "outer.other 81 行 > 80" in style._length_issue("tools/a.py", other, exemptions, other_name)


def test_marked_template_copy_only_exempts_itself():
    issues = duplicates(
        ("templates/checks/a.py", "def run(items):\n    # 故意重复：模板需独立带走\n    return sorted(items)\n"),
        ("tools/b.py", "def run(items):\n    return sorted(items)\n"),
    )
    assert len(issues) == 1
    assert issues[0].startswith("tools/b.py:")
    assert "同名同体函数 run" in issues[0]


def test_main_uses_tokenize_cache_and_marked_exemption(tmp_path, monkeypatch, capsys):
    """F1：走 main() 全流——每文件 tokenize 一次缓存，标 故意重复 的豁免、未标的报。

    钉主流程真用 tokenize 缓存：a.py 标记豁免、b.py 未标 → 只报 b.py 一条。
    变异：main 不按文件缓存 comment_tokens／不认标记 → 报 2 条或 0 条，本断言红。
    """
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    (tools_dir / "a.py").write_text(
        "def run(items):\n    # 故意重复：模板需独立带走\n    return sorted(items)\n", encoding="utf-8")
    (tools_dir / "b.py").write_text(
        "def run(items):\n    return sorted(items)\n", encoding="utf-8")
    monkeypatch.setattr(style, "ROOT", tmp_path)
    monkeypatch.setattr(style, "_load_manifest", lambda: None)
    assert style.main() == 1
    out = capsys.readouterr().out
    assert "同名同体函数 run" in out
    assert "tools/b.py" in out
    assert "违规 1 条" in out


def test_duplicate_marker_must_be_a_comment_with_nonempty_reason():
    def marked(body):
        source = "def run(items):\n" + body + "    return sorted(items)\n"
        fn = ast.parse(source).body[0]
        tokens = [t for t in tokenize.generate_tokens(io.StringIO(source).readline) if t.type == tokenize.COMMENT]
        return style._marked_duplicate(fn, tokens)

    assert marked("    # 故意重复：模板需独立带走\n")
    assert not marked("    # 故意重复：\n")
    assert not marked("    # 故意重复：   \n")
    assert not marked("    note = '# 故意重复：字符串不算'\n")
    assert not marked("    ## 故意重复：标题不算\n")
    assert not marked("    '''\n    # 故意重复：docstring 不算\n    '''\n")


def test_duplicate_marker_only_counts_exclusive_line():
    def marked(source):
        fn = ast.parse(source).body[0]
        tokens = [t for t in tokenize.generate_tokens(io.StringIO(source).readline) if t.type == tokenize.COMMENT]
        return style._marked_duplicate(fn, tokens)

    assert marked("def run(items):\n    # 故意重复：模板需独立带走\n    return sorted(items)\n")
    assert not marked("def run(items):\n    value = items  # 故意重复：行尾不算\n    return sorted(items)\n")
    assert not marked("def run(items):  # 故意重复：def行尾不算\n    return sorted(items)\n")


def test_trailing_comment_marker_does_not_exempt_duplicate():
    issues = duplicates(
        ("tools/a.py", "def run(items):\n    return sorted(items)  # 故意重复：行尾不算\n"),
        ("tools/b.py", "def run(items):\n    return sorted(items)\n"),
    )
    assert len(issues) == 2
    assert all("同名同体函数 run" in issue for issue in issues)


def test_duplicate_marker_tokenize_failure_is_red(tmp_path, monkeypatch, capsys):
    source_dir = tmp_path / "tools"
    source_dir.mkdir()
    (source_dir / "a.py").write_text("def run(items):\n    return sorted(items)\n", encoding="utf-8")

    def broken_tokenize(*args):
        raise tokenize.TokenError("扫描中断", (2, 0))

    monkeypatch.setattr(style, "ROOT", tmp_path)
    # F2：真钉 tokenize 失败（原误钉 _marked_duplicate，名实不符）——main 每文件 tokenize 缓存处抛 TokenError
    monkeypatch.setattr(style.tokenize, "generate_tokens", broken_tokenize)
    monkeypatch.setattr(style, "_load_manifest", lambda: None)
    assert style.main() == 1
    assert "重复标记扫描失败" in capsys.readouterr().out


def swallow_issue(source):
    node = next(node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ExceptHandler))
    return style._bare_except(node, source.splitlines())


def broad_handler(exception, exit_statement):
    return (
        "def f(items):\n"
        "    for item in items:\n"
        "        try:\n"
        "            work()\n"
        f"        except {exception}:\n"
        f"            {exit_statement}\n"
    )


def test_swallow_reason_must_share_pass_line():
    hanging = "try:\n    work()\nexcept Exception:\n    pass\n    # 吞：旧写法\n"
    inline = "try:\n    work()\nexcept Exception:\n    pass  # 吞：新写法\n"
    assert swallow_issue(hanging)
    assert not swallow_issue(inline)


def test_base_exception_and_exception_tuple_silent_exits():
    for exception, exit_statement in (
        ("BaseException", "pass"),
        ("(Exception,)", "continue"),
        ("(BaseException,)", "return None"),
    ):
        assert swallow_issue(broad_handler(exception, exit_statement))
        inline = exit_statement + "  # 吞：已按规则记录理由"
        assert not swallow_issue(broad_handler(exception, inline))


def test_return_none_hanging_reason_is_red_and_inline_is_green():
    hanging = broad_handler("Exception", "return None") + "            # 吞：悬挂不算\n"
    assert swallow_issue(hanging)
    inline = broad_handler("Exception", "return None  # 吞：无结果即无数据")
    assert not swallow_issue(inline)


def test_silent_return_false_requires_inline_reason():
    assert swallow_issue(broad_handler("Exception", "return False"))
    inline = broad_handler("Exception", "return False  # 吞：失败按不可用处理")
    assert not swallow_issue(inline)


def test_empty_containers_and_negative_one_are_silent_exits():
    for expression in ("[]", "{}", "()", "set()", "-1"):
        assert swallow_issue(broad_handler("Exception", "return " + expression))
        inline = "return " + expression + "  # 吞：无结果按空值处理"
        assert not swallow_issue(broad_handler("Exception", inline))


def test_specific_exceptions_and_multi_statement_handlers_are_out_of_scope():
    assert not swallow_issue(broad_handler("(ImportError, ValueError)", "return False"))
    assert not swallow_issue(broad_handler("OSError", "pass"))
    multi = broad_handler("Exception", "report()\n            return False")
    assert not swallow_issue(multi)
