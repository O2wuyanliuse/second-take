import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dependency_graph_computes_names_from_defs():
    path = ROOT / "templates" / "checks" / "_mvchecks.py"
    spec = importlib.util.spec_from_file_location("mvchecks_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tree = ast.parse("BASE = 1\n\ndef f():\n    return BASE\n")
    users, reads = module._dependency_graph(tree, {"BASE", "f"})
    assert isinstance(users, dict) and isinstance(reads, dict)
    assert all(isinstance(value, set) for value in users.values())
    assert all(isinstance(value, set) for value in reads.values())
    assert users["BASE"] == {"f"}
    assert reads["f"] == {"BASE"}
