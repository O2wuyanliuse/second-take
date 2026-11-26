# -*- coding: utf-8 -*-
"""_pname.py — 项目名只认一个来源，其余脚本都来这里取。

    NAME = _pname.NAME                     # 展示用（报告标题）
    _pname.setting()                       # 设定集全路径
    _pname.setting("世界观总览表")          # 总览表全路径

## 为什么要有这个文件

2026-11-02，一个外部 agent 在分发测试里报上来一件事：**同一个项目名，有 30 处写死在代码里**。
主标题走了新的解析逻辑（能显示用户填的名字），子标题和真相源文件名还是硬编码的
「某项目_世界观设定集_v1.0.md」。后果很直接：

    用户把自己的设定集命名成「<自己的项目名>_世界观设定集_v1.0.md」
    → 脚本只认「某项目_世界观设定集_v1.0.md」
    → 「真相源守门」永远红，而红的原因是**用户按文档做了对的事**。

它的原话是「这和『项目名不再写死』的说法对不上，需要你定夺」——
**不需要定夺，这是漏了。** 一个名字散落在 6 个脚本里，就是 6 份会各自漂的副本，
而项目自己立过规矩：副本一定会漂（`G-125`）。

## 解析顺序（前一条成立就不看后一条）

1. 环境变量 `GATE_PROJECT`——换机器、做测试、想临时改口径时用，不改文件
2. `README.md` 里的 `> 项目：xxx` 标记——分发版靠这条，`安装.md` 第 3 步让人填
3. **同目录下 `*_世界观设定集_v*.md` 的文件名前缀**——项目里没有 README 也照样拿得到
4. 都没有 → `某项目`

第 3 条是关键：**它让「名字」这个东西有了一个物证**。
项目里那份设定集叫什么，项目就叫什么——不用人再抄一遍到别处。
"""

import io
import os
import re
import sys

# ---- 输出编码兜底（2026-11-04，G-299）------------------------------------
# 为什么必须有这几行：Windows 上 stdout 被重定向到文件（`python x.py > out.txt`）
# 或接管道时，Python 走 locale 编码（中文机是 cp936），打印 ✅ ✗ ⚠ 这类符号会抛
# UnicodeEncodeError —— 退出码变成 1，看起来像"脚本坏了"。而在控制台里跑是好的，
# 因为 WriteConsoleW 绕过了编码，**所以本机永远测不出来**。
# 这里按 utf-8 重设，errors="replace" 兜底：宁可打问号，不许整篇不出。
for _std_stream in (sys.stdout, sys.stderr):
    try:
        _std_stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
        # 吞：输出流不支持 reconfigure 时保留原编码，不让输出配置阻断检查。
# ---------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

DEFAULT = "某项目"


def _from_env():
    return os.environ.get("GATE_PROJECT", "").strip() or None


def _from_readme():
    """`> 项目：xxx` 标记。尖括号开头的是模板占位符，**不能当名字用**——
    否则报告标题会变成那个占位符，比显示「某项目」更莫名其妙。"""
    try:
        with io.open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            m = re.search(r"(?m)^>\s*项目：\s*(\S.*?)\s*$", f.read())
        if m and not m.group(1).startswith("<"):
            return m.group(1)[:24]
    except (OSError, UnicodeDecodeError):
        pass
    return None


def _from_setting_file():
    """同目录下的设定集文件名，去掉 `_世界观设定集_vX.Y.md` 后缀就是项目名。"""
    try:
        for fn in sorted(os.listdir(HERE)):
            m = re.match(r"^(.+?)_世界观设定集_v\d+\.\d+\.md$", fn)
            if m:
                return m.group(1)
    except OSError:
        pass
    return None


def resolve():
    return _from_env() or _from_readme() or _from_setting_file() or DEFAULT


NAME = resolve()

# 分发版会在这里被写死成一个默认名——**不要**，那就又回到「30 处写死」的老路。
# 名字只由上面前三条决定，这里只负责拼路径。
SETTING_SUFFIX = "_世界观设定集_v1.0.md"
OVERVIEW_SUFFIX = "_世界观总览表_v1.0.md"


def setting(prefix="世界观设定集", ver="v1.0"):
    return os.path.join(HERE, "%s_%s_%s.md" % (NAME, prefix, ver))


# ── `--check`：名字有没有又被写回代码里 ────────────────────────────
# 2026-11-02，同一个病根被外部实测抓到两次：`G-140` 报了 6 处，我改完 6 处，
# `G-143` 又报出 `_board.py`／`_view.py` 各一处。**两次都是靠人眼扫出来的。**
# 这个开关把那次「扫」固定下来：一条命令，列出所有还写着名字的地方。
#
# 白名单里的文件是**故意的**，别往里加：
#   `_pname.py`        —— 兜底值 DEFAULT 本身
#   `_collab.py`       —— 项目专名表（脱敏时整表替换，进包后是占位符）
#   `_layer_audit.py`  —— 同上，专名表 A（进包后清空成 []）
#   `_selftest.py`     —— 夹具，见该文件 CASES 上方的说明：夹具不许动态取名
#   `_probe_a.py`／`_hollow.py` —— 项目词表与探测稿，本就不进分发包
_ALLOWED = {
    "_pname.py": "兜底值 DEFAULT 本身就是这个字面量",
    "_collab.py": "项目专名表：脱敏时整表换掉，进包后是占位符",
    "_layer_audit.py": "专名表 A：同样由脱敏处理，包里清成空表",
    "_selftest.py": "夹具：见该文件用例表上方，夹具不许动态取名",
    "_probe_a.py": "项目词表；本就不进分发包",
    "_hollow.py": "项目词表；本就不进分发包",
}


def scan_one(name):
    """扫一个名字，返回 [(文件名, 行号, 原行)]。"""
    hits = []
    for fn in sorted(os.listdir(HERE)):
        if not (fn.startswith("_") and fn.endswith(".py")):
            continue
        try:
            txt = io.open(os.path.join(HERE, fn), encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        for i, ln in enumerate(txt.split("\n"), 1):
            if name in ln:
                hits.append((fn, i, ln.strip()[:90]))
    return hits


if __name__ == "__main__":
    if "--check" in sys.argv:
        # **要扫两个名字，不是一个**（2026-11-02，G-144）。
        #   项目里：名字被写死的痕迹是「真名」，扫 NAME 就够。
        #   包里：真名已被脱敏抹掉，同一个病根残留下来是**兜底名**。
        #   只扫 NAME，在包里等于什么都没扫到——而它还会报「0 处」，比不查更糟。
        #
        # **只报数字也是不够的**：外部实测拿到「白名单内 1 处」时没法核对那是哪一处，
        #   只能信我。所以这里**逐条列位置**，不给只读数字。
        names = [(NAME, "当前项目名")]
        if NAME != DEFAULT:
            names.append((DEFAULT, "兜底名（用户没填名字时才会用到）"))

        print("扫描范围：`00_原著/_*.py`（共 %d 个脚本）"
              % len([f for f in os.listdir(HERE) if f.startswith("_") and f.endswith(".py")]))
        # 只列**本目录里真的存在**的文件（2026-11-02，G-145）。
        # 原来六个全列，而 `_hollow.py`／`_probe_a.py` 在分发包里根本不在——
        # 一个不存在的文件占着白名单一行，永远不可能命中，**属于空转条目**：
        # 读的人会以为包里还有这两个脚本（跟 `_anchor` 那条「空转的排除」同型）。
        present = set(f for f in os.listdir(HERE)
                      if f.startswith("_") and f.endswith(".py"))
        print("白名单（这些位置写死名字是对的，**别往里加**）：")
        for fn in sorted(_ALLOWED):
            if fn in present:
                print("    %s —— %s" % (fn, _ALLOWED[fn]))
        gone = [fn for fn in sorted(_ALLOWED) if fn not in present]
        if gone:
            print("    （另有 %s 本目录没有，无从命中，已略去）" % "、".join(gone))
        print("")
        print("注：**注释里为了解释而引用名字，也会被算作残留**——扫描器分不清")
        print("    「硬编码」和「解释硬编码」。改写措辞（说「占位字符」而不是照抄），")
        print("    比往白名单里加文件安全。（2026-11-02 外部实测撞到，`G-161`）")

        bad_total = 0
        for name, label in names:
            hits = scan_one(name)
            inside = [h for h in hits if h[0] in _ALLOWED]
            outside = [h for h in hits if h[0] not in _ALLOWED]
            print("「%s」——%s：命中 %d 处（白名单 %d ／ 白名单外 %d）"
                  % (name, label, len(hits), len(inside), len(outside)))
            for fn, i, s in inside:
                print("    白名单  %s:%d  %s" % (fn, i, s))
            for fn, i, s in outside:
                print("    ✗ 外面  %s:%d  %s" % (fn, i, s))
            if not hits:
                print("    （一处都没有——说明这个名字没被写进任何脚本）")
            bad_total += len(outside)

        print("")
        if bad_total:
            print("✗ 白名单外共 %d 处：名字又被写回代码了，改用 _pname.NAME／_pname.setting()"
                  % bad_total)
            sys.exit(1)
        print("✅ 白名单外 0 处（上面两个名字都逐条列过，可自己核）")
        sys.exit(0)

    print("项目名：%s" % NAME)
    print("来源：%s" % ("环境变量 GATE_PROJECT" if _from_env()
                       else "README 的「项目：」标记" if _from_readme()
                       else "设定集文件名" if _from_setting_file()
                       else "默认值（以上三处都没读到）"))
    print("设定集：%s" % setting())
    print("总览表：%s" % setting("世界观总览表"))
