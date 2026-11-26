"""一次性搬运器：把一批顶层函数及其**独占依赖**从 `_consist.py` 切到指定模块。

为什么写这支：手搬四批，每批都踩「切函数带走夹在中间的常量」「正则漏判模块级」
两类坑。判「谁属于谁」是语法问题，就交给 `ast`。

它做四件事：
1. 算闭包：目标函数 ＋ 只被它们用到的顶层定义（反复迭代到不动点）；
2. 按 `ast` 行号整块切除（**不会误伤夹在函数之间的常量**——常量有独立节点）；
3. 剩下的外部依赖，凡是清单里的「可注入名」→ `_core.NAME`；
4. 主脚本补 `from checks.X import ...`。

用法（在项目根跑）：
    python scripts/_mvchecks.py --to checks/yinyong.py --names check_a,check_b --inject CASE,README
"""
import argparse
import ast
import io
import os
import sys

# 通用版：根目录可配；主脚本与目标包都相对它算
PROJ = os.path.abspath(os.environ.get("MV_ROOT") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SRC = os.path.join(PROJ, "00_原著", "_consist.py")


def load():
    # 故意重复：可单独搬运，见 README
    text = io.open(SRC, encoding="utf-8").read()
    return text, ast.parse(text)


def top_defs(tree):
    """名字 → 节点（函数／类／赋值）。赋值按行号范围整体算。"""
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[node.name] = node
        elif isinstance(node, ast.ClassDef):
            out[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            tgt = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in tgt:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name):
                        out[n.id] = node
    return out


def free_names(fn, module_names):
    """函数里被读、但不是局部变量的名字（只保留本模块顶层定义过的）。"""
    local = set()
    a = fn.args
    for x in list(a.args) + list(a.kwonlyargs) + list(a.posonlyargs):
        local.add(x.arg)
    if a.vararg:
        local.add(a.vararg.arg)
    if a.kwarg:
        local.add(a.kwarg.arg)
    for n in ast.walk(fn):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            local.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n is not fn:
            local.add(n.name)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            local.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for al in n.names:
                local.add((al.asname or al.name).split(".")[0])
    return {n.id for n in ast.walk(fn)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
            and n.id not in local and n.id in module_names}



def rewrite_names(src, mapping):
    """按 AST 的 **Name 节点位置**改写标识符——只改代码，不动字符串与注释。

    2026-11-17 的教训：先按正则把 `README` 换成 `_core.README`，
    结果消息字符串里的 `"Agent框架/" + README + ".md"` 被改成字面量 `_core.README`，
    检查器报「Agent框架 里没有 _core.README.md」。**正则分不清代码和字面量。**
    """
    tree = ast.parse(src)
    edits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in mapping:
            edits.append((node.lineno, node.col_offset, node.end_lineno,
                          node.end_col_offset, mapping[node.id]))
    if not edits:
        return src
    lines = src.split("\n")
    # `ast` 的 col_offset 是 **UTF-8 字节偏移**，不是字符偏移——
    #   中文行（本项目全是中文）按字符切会错位，切出 `PTR_MANIFEST +_core.PTR_MANIFEST**——` 这种残句。
    #   所以按字节切，再解码回来。
    for ln, col, end_ln, end_col, new in sorted(edits, reverse=True):
        if ln != end_ln:
            continue
        raw = lines[ln - 1].encode("utf-8")
        lines[ln - 1] = (raw[:col] + new.encode("utf-8") + raw[end_col:]).decode("utf-8", "replace")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", required=True)
    ap.add_argument("--names", required=True)
    ap.add_argument("--inject", default="")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    text, tree = load()
    defs = top_defs(tree)
    names_all = set(defs)

    # 每个顶层定义分别被谁用到：函数看自由名字，常量看右值里读了谁。
    #   2026-11-17 修：首版只算了函数→名字，漏掉「常量读常量」（如 `RETIRED_SKIP = SKIP + …`），
    #   于是闭包算不出来，搬到一半 `NameError`。**常量也是使用者。**
    users = {}
    reads = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nm = node.name
            f = free_names(node, names_all)
            reads[nm] = f
            for d in f:
                users.setdefault(d, set()).add(nm)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets_n = node.targets if isinstance(node, ast.Assign) else [node.target]
            tnames = {n.id for t in targets_n for n in ast.walk(t) if isinstance(n, ast.Name)}
            value = node.value
            f = {n.id for n in ast.walk(value) if isinstance(n, ast.Name)
                 and isinstance(n.ctx, ast.Load) and n.id in names_all} - tnames
            for t in tnames:
                reads["const:" + t] = f
                for d in f:
                    users.setdefault(d, set()).add("const:" + t)

    targets = [x.strip() for x in args.names.split(",") if x.strip()]
    missing = [t for t in targets if t not in defs]
    if missing:
        print("找不到：", missing)
        return 2

    moved = set(targets)
    def _u(n):
        # 使用者的名字里带 `const:` 前缀的要还原成常量名
        return {x[6:] if x.startswith("const:") else x for x in users.get(n, set())}
    changed = True
    while changed:
        changed = False
        for n in list(moved):
            for dep in reads.get(n, set()):
                if dep in moved or dep not in defs:
                    continue
                if _u(dep) - moved == set():
                    moved.add(dep)
                    changed = True

    # 注入点：除了命令行给的，永远加上 `_core` 里的固定几样
    #   （2026-11-17 修：首版只按命令行改写，搬到 `P2.append` 当场 NameError）
    inject = {x.strip() for x in args.inject.split(",") if x.strip()}
    inject |= {"PROJ", "P1", "P2", "rd", "_unset", "_cfg", "SKIP", "LEDGER"}

    # 收集要搬的源码块（按行号，从大到小切）
    # **同一个节点可能被多个名字共享**（`A = B = ...` 或 `a, b = ...`）。
    #   首版按名字建行区间，于是同一段被切两次，切出来的源码错位——`G-959` 踩到 SyntaxError。
    #   现在按节点去重，一个节点只切一次。
    nodes, seen = [], set()
    for n in sorted(moved):
        node = defs[n]
        if id(node) in seen:
            continue
        seen.add(id(node))
        nodes.append((node.lineno, node.end_lineno, n))
    spans = sorted(nodes, reverse=True)

    lines = text.split("\n")
    chunks = []
    for start, end, n in spans:
        chunk = "\n".join(lines[start - 1:end])
        chunks.append((n, chunk))
        del lines[start - 1:end]
    new_main = "\n".join(lines)

    # 外部依赖 → _core.X（只处理注入清单里的）
    out_chunks = []
    for n, chunk in chunks:
        # 按 AST 位置改写，不用正则（正则会改到字符串里，`G-959` 踩过）
        try:
            chunk = rewrite_names(chunk, {k: "_core." + k for k in inject})
        except SyntaxError:
            pass
        out_chunks.append(chunk)

    print("将搬 %d 个顶层定义：%s" % (len(moved), ", ".join(sorted(moved))))
    if not args.apply:
        print("（dry-run，加 --apply 才写盘）")
        return 0

    io.open(SRC, "w", encoding="utf-8", newline="").write(new_main)
    mod = os.path.join(PROJ, "00_原著", args.to)
    header = ('"""由 `_mvchecks.py` 于 2026-11-17 生成：%s\n\n'
              '搬运动机见 `G-959`：手搬四批每次都在「切函数带走常量」上翻车，'
              '交给 ast 之后按节点切，不再碰夹在中间的常量。\n"""\n'
              'import io\nimport json\nimport os\nimport re\n\nfrom . import _core\n\n'
              % ", ".join(targets))
    io.open(mod, "w", encoding="utf-8", newline="\n").write(header + "\n\n".join(out_chunks) + "\n")
    print("写入：", mod)
    print("下一步：在 `_consist.py` 补 import —— %s" % ", ".join(targets))
    return 0


if __name__ == "__main__":
    sys.exit(main())
