"""依赖归属图 —— 判「一项检查能不能整项搬走」（2026-11-17，`G-958`）。

完整说明（维护仓，不随包）：docs/maintain/代码内长文档/templates/checks/_depmap.py.md
"""
import argparse
import ast
import io
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
# 通用版：根目录与包目录都可配（缺省取脚本上两级 ＋ `<根>/00_原著/checks`）
PROJ = os.path.abspath(os.environ.get("DEPMAP_ROOT") or os.path.join(HERE, "..", ".."))
PKG = os.path.abspath(os.environ.get("DEPMAP_PKG") or os.path.join(PROJ, "00_原著", "checks"))

# `_core` 里由 `_consist` 注入的东西：见到它们不算「共用」，因为它们本来就是同对象
INJECTED = {"PROJ", "P1", "P2", "rd", "_unset", "_cfg", "SKIP", "LEDGER", "REF_HINT",
            # 跨组共享的项目路径（2026-11-17 起走注入）
            "CASE", "README", "CHANNEL", "FLOW", "DIST"}


def _files():
    out = [os.path.join(PROJ, "00_原著", "_consist.py")]
    if os.path.isdir(PKG):
        out += [os.path.join(PKG, f) for f in sorted(os.listdir(PKG))
                if f.endswith(".py") and f != "__init__.py"]
    return [p for p in out if os.path.exists(p)]


def _toplevel(tree):
    """顶层定义：名字 → 种类。"""
    defs = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs[node.name] = "def"
        elif isinstance(node, ast.ClassDef):
            defs[node.name] = "class"
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name):
                        defs[n.id] = "const"
    return defs


def _locals_of(fn):
    """函数内被绑定的名字：参数、赋值、for、with、except、import、推导式目标。

    宁可多算（把某些自由名字误当局部）也不可少算——少算会把外部依赖漏成「自给自足」。
    """
    names = set()
    args = fn.args
    for a in list(args.args) + list(args.kwonlyargs) + list(args.posonlyargs):
        names.add(a.arg)
    if args.vararg:
        names.add(args.vararg.arg)
    if args.kwarg:
        names.add(args.kwarg.arg)
    for n in ast.walk(fn):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            names.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n is not fn:
            names.add(n.name)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            names.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                names.add((a.asname or a.name).split(".")[0])
    return names


def _free_names(fn):
    """被读、但不是局部变量的名字。"""
    local = _locals_of(fn)
    out = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            if n.id not in local:
                out.add(n.id)
    return out


def build():
    # 故意重复：可单独搬运，见 README
    providers = {}      # 名字 → 提供它的模块
    funcs = {}          # 函数名 → {module, free}
    for path in _files():
        mod = os.path.relpath(path, PROJ).replace("\\", "/")
        tree = ast.parse(io.open(path, encoding="utf-8").read(), path)
        for name in _toplevel(tree):
            providers.setdefault(name, mod)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funcs[node.name] = {"module": mod, "free": _free_names(node)}
    return providers, funcs


def analyze():
    providers, funcs = build()
    checks = {n: v for n, v in funcs.items() if n.startswith("check_")}
    # 每个名字被多少个检查用
    users = defaultdict(set)
    for c, v in checks.items():
        for n in v["free"]:
            users[n].add(c)
    rows = []
    for c, v in sorted(checks.items()):
        own, shared, internal = [], [], []
        for n in sorted(v["free"]):
            if n in INJECTED:
                continue
            src = providers.get(n)
            if not src:
                continue                      # 内置／局部闭包等，不管
            if src != v["module"]:
                internal.append((n, src))     # 已经在包里别的模块，属于正常引用
                continue
            # 同模块内部共用不算障碍：搬的是整个模块，一起走。
            # **只有"名字还住在 _consist 里、却别处也在用"才是真正的坎。**
            if v["module"] != "00_原著/_consist.py":
                internal.append((n, v["module"]))
                continue
            others = users[n] - {c}
            (shared if others else own).append(n)
        rows.append({"check": c, "module": v["module"], "own": own,
                     "shared": shared, "internal": internal})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check")
    ap.add_argument("--md")
    args = ap.parse_args()
    rows = analyze()
    if args.check:
        rows = [r for r in rows if r["check"] == args.check]
        if not rows:
            print("没有这项检查")
            return 2
    lines = ["# 检查器依赖归属（AST 版，2026-11-17）", "",
             "> 由 `scripts/_depmap.py` 生成。判据：**独占为空 ＋ 只依赖 `_core` 注入 = 可整项搬**。", "",
             "| 检查 | 所在模块 | 独占名字 | 共用名字（需注入或降耦） | 跨模块引用 |",
             "|---|---|---|---|---|"]
    ok = 0
    for r in rows:
        verdict_ok = not r["shared"]
        ok += 1 if verdict_ok else 0
        lines.append("| `%s` | %s | %d %s | %s | %d |" % (
            r["check"], r["module"], len(r["own"]),
            ("`" + "` `".join(r["own"]) + "`") if r["own"] else "",
            ("`" + "` `".join(r["shared"]) + "`") if r["shared"] else "—",
            len(r["internal"])))
    lines += ["", "**可整项搬：%d ／ %d**" % (ok, len(rows))]
    text = "\n".join(lines) + "\n"
    if args.md:
        io.open(args.md, "w", encoding="utf-8", newline="\n").write(text)
        print("写好：%s（%d 项，可搬 %d）" % (args.md, len(rows), ok))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
