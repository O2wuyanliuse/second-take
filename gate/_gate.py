# -*- coding: utf-8 -*-
"""_gate.py · 汇总报告（原「收工总闸」）

用法：python gate/_gate.py [--quiet|--each|--verbose] [--full] [--brief]
  --quiet  默认两行结论；--each 逐项结论；--verbose 全量输出。
  --full   加跑判据自检；--brief 汇总正文但缩短跟进通道。
退出码：0 通过；1 有阻断；2 有提示；3 安装未完成。

完整说明（维护仓，不随包）：docs/maintain/代码内长文档/gate/_gate.py.md
"""

import io
import json
import os
import re
import subprocess
import sys

# `_pname.py` 是**模块，不是检查项**——它提供 `NAME`／`setting()` 给别的脚本 import。
# 它不在下面 CHECKS 的列表里，也不该在：那张表列的是「跑起来能判红绿的东西」，
# 而它没有判定能力。同理，`_gate.py` 自己这个文件是调度器，也不在列表里。
# 2026-11-12 清账时记下这一句：`gate/` 目录里出现「跑不出一行结论」的文件时，
# 读的人第一反应是「它坏了」——**说明它是什么，比让人猜便宜**。
import _pname  # 项目名唯一来源（2026-11-02，G-142）；模块，非检查项

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
        pass  # 吞：输出流不支持 reconfigure 时保留原编码，不让输出配置阻断检查。
# ---------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 脚本父目录的父目录＝项目根（与其余脚本同一口径）

STEPS = [
    # 顺序与 `.git/hooks/pre-commit` 逐字一致（2026-11-01 补齐：原只跑 3 个，
    # 而必经路径跑 7 个——「一次看全」这件事以前做不到，得自己 for 循环）
    ("真相源守门", "_collab.py", []),
    ("正文账实核对", "_diff.py", []),
    ("作废词残留", "_lint.py", []),
    ("引用锚点", "_anchor.py", []),
    ("判据参照物", "_basis.py", []),   # 2026-11-04 入：判据不许拿生成图当尺子／不许并列基准／不许裸像素
    ("开工入口卡", "_state.py", ["--check"]),  # 2026-11-04 入：卡不在／过期／超行数 → 红。它查不了「读没读」，但能查「有没有生成过」
    ("副本一致性", "_consist.py", []),
    ("层级纯度", "_layer_audit.py", []),
    # 2026-11-09 02:1x（`G-561`）：专名对账接通。它一直在磁盘上，但只靠人想起来才跑——
    # 「不报错、不提醒、没人跑等于不存在」。耗时 0.2 s，够便宜，直接进必经路径。
    ("专名对账", "_hollow.py", []),
    ("旧常量残留", "_const.py", []),      # 2026-11-01 新入：措辞有台账，数字也得有
    ("索引层校准", "_world.py", ["--scan"]),
    ("版权红线", "_redline.py", []),   # 2026-11-01 新入：查这道墙还在不在
    ("skill 同步", "_skill_sync.py", []),  # 2026-11-01 新入：源与安装副本
    # 2026-11-07 23:4x 补：昨晚把 _cost 加进 pre-commit 时**忘了这里**，
    # 于是「逐字一致」这句话当天就变成假的。**改一处漏一处，是这套东西最常见的死法。**
    ("抽卡成本", "_cost.py", []),   # rc=2=提示（词表越界／责任层空），不阻断
    # 2026-11-08 00:2x（`G-492`）：两个资产检查器接通。
    ("资产用途", "_asset.py", ["--gate"]),   # 只把 [A] 越界引用当红；[B]／[C] 是提示
    ("孤儿件", "_orphan.py", []),            # 全库模式供人看（列清单，不判红）
    # 2026-11-11 16:2x：同步防断接通（`G-679`／`G-680`）。它一直在方法件里写着「人肉跑」，
    # 而人肉跑的东西等于没有——这条闸挡的是「状态只写在一个入口，新窗口读到旧的那一份」。
    ("同步防断", "_drift.py", []),   # C1／C5 阻断，C4 只提示
    # 2026-11-12：通用层自己的引用通不通。`_anchor` 留在项目侧（它要项目台账当基线），
    # 于是骨架库文档里写 `00_原著/_mkview.py` 这种路径一个字都不报——`11_分发说明` §四
    # 立的「名字不带位置」，在通用层内部反而是无闸的。这个脚本只查本仓库顶层目录，
    # 别的路径一律当「读者项目里该有的」（2026-11-12 实测：不设这条，106 条候选里 37 条假）。
    ("仓库内断链", "_links.py", []),
    # 2026-11-20 冷启动实测（`G-1201`）：`AGENTS.md` 那句「不跳步」只是话，门禁里没人查。
    # 实测窗口拿到一段正文，直接出 E2-2 定调 + S01 镜表 + E3-0 判格，E0 登记一条没做，
    # 而门禁报绿。它只判三样事实在不在（原文在哪／文体／与原著的关系），判形状不判内容。
    # 没有 `00_原著/` 时给 2（提示）不判红——本库是方法仓，这里判红就是假红。
    ("投喂登记", "_e0.py", ["--gate"]),
]

VERDICT = ("✅", "✗", "⚠", "共 ", "· ", "P0")

CHANNEL = os.path.join(os.path.dirname(HERE), "Agent框架", "[台账]跟进通道.md")


def channel_banner(brief=False):
    """跟进通道状态。

    定位：**不参与判定**，只保证它出现在视野里。
    理由：四·补十一 的教训——没有检查者的条件等于没写。
    这里不做硬拦截：通道 OPEN 是正常工作状态，不是错误。
    """
    import re

    if not os.path.exists(CHANNEL):
        print("📋 跟进通道：**文件不存在** ｜ 期望位置 %s" % CHANNEL)
        print("   → 机制没接上。见 02_流程层 四·补十二。")
        print("")
        return

    try:
        txt = io.open(CHANNEL, encoding="utf-8").read()
    except Exception as exc:  # noqa: BLE001
        print("📋 跟进通道：读不出（%s）" % exc)
        print("")
        return

    m = re.search(r"\*\*状态\*\*[：:]\s*([^\n]*)", txt)
    state = "OPEN" if (m and "OPEN" in m.group(1)) else ("CLOSED" if m else "未知")

    pkg = re.search(r"\*\*当前包\*\*[：:]\s*`?([^`\n｜|]+)", txt)
    pkg = pkg.group(1).strip() if pkg else "—"

    rows = [l for l in txt.split("\n") if re.match(r"^\| G-\d+ ", l)]
    opens = []
    for line in rows:
        cells = [c.strip() for c in line.split("|")]
        if len(cells) > 6 and "🔴" in cells[6]:
            short = re.sub(r"[`*]", "", cells[4])
            if len(short) > 46:
                short = short[:46] + "…"
            opens.append((cells[1], short))

    print("📋 跟进通道：%s ｜ 包 %s ｜ 条目共 %d ｜ 开着 %d" % (state, pkg, len(rows), len(opens)))

    # 2026-11-05 加：一眼看出「卡在谁手上」。
    # 起因是作者那句「不然给人感觉就是永远有东西没做完」——30 条共用一个 🔴，
    # 读起来就是 30 件事没做完；实际 0 条要动手、13 条等他一句话、15 条等出图。
    # **三种性质印成一个数，读的人只能取最坏的那个解释。**
    buckets = []
    bs = re.search(r"^## 一之二.*?(?=^## )", txt, re.S | re.M)
    if bs:
        for line in bs.group(0).split("\n"):
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.split("|")]
            if len(cells) < 5 or not re.search(r"[甲乙丙丁]·", cells[1]):
                continue
            n = len(re.findall(r"`G-\d+`", cells[-2]))
            buckets.append((re.sub(r"[`*]", "", cells[1]), n))
    if buckets:
        print("   📊 卡在谁手上：" + " ｜ ".join("%s %d" % (nm, n) for nm, n in buckets))

    if brief:
        print("")
        return

    if state == "OPEN":
        for gid, brieftxt in opens[:6]:
            print("   · %s %s" % (gid, brieftxt))
        if len(opens) > 6:
            print("   · …… 另 %d 条（看文件）" % (len(opens) - 6))
        if not opens:
            print("   → 开着的条目为 0，可以过封包清单了（见通道 §三）")
    elif state == "CLOSED":
        print("   → 已封包。要维护框架，口令：进入框架debug模式")
    else:
        print("   ⚠ 认不出状态行，检查头部格式是否被改坏")
    print("")


def run(script, args):
    path = os.path.join(HERE, script)
    if not os.path.exists(path):
        return None, "脚本不存在：%s" % script
    try:
        p = subprocess.run(
            [sys.executable, path] + args,
            cwd=HERE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        return p.returncode, p.stdout.decode("utf-8", "replace")
    except Exception as e:
        return None, "执行失败：%s" % e


def project_name():
    """项目名唯一来源是 `_pname.py`——这里只保留旧函数名，不再自己解析一遍。

    2026-11-02（`G-142`）：本函数原先自己解析，而 `_collab`／`_anchor`／`_lint` 各自又写死
    一份文件名。同一个名字四份实现，第一份改了、后三份没改，于是出现「主标题已经是用户填的名字、
    子标题还是兜底名」——外部实测一眼看出来的那种分裂。**一个名字只认一处来源。**
    
    注：这段注释原先直接引了那句兜底名，于是 `_pname.py --check` 在分发包里把它当事主报出来——
    **判据自己踩进判据里**。改成描述，不再复述那个字面量。
    """
    return _pname.NAME


def is_fresh_project():
    """这是「还没开始」还是「在还债」？两种状态用同一套语气，就是在骂新人。

    2026-11-02 外部实测（`G-158`）第一句话就说中了：一个**还没开工**的人看到
    「退出码 1 ＝ 硬失败」「处理二选一：① 修掉 ② 修不动 → 写进跟进通道」，
    读到的是「你还没动手就已经挂了」「你欠了东西要还」——而他此刻两手空空，
    「修」这个字对不上他脑子里的任何东西，**他还没做错什么，哪来的修**。

    判据只看三样东西在不在：设定集、定论台账、正文归档。三样都没有＝空项目。
    宁可判成「还没开始」多给一句指引，也别把新人当欠债的骂——**骂错了没人会告诉你**。
    """
    g = os.path.join(ROOT, "00_原著")
    if not os.path.isdir(g):
        return True
    names = os.listdir(g)
    has_setting = any(re.search(r"_世界观设定集_v\d+\.\d+\.md$", f) for f in names)
    has_ledger = any("定论台账" in f for f in names)
    arch = os.path.join(g, "_原始归档")
    has_text = os.path.isdir(arch) and any(
        f.lower().endswith((".txt", ".md")) for f in os.listdir(arch))
    return not (has_setting or has_ledger or has_text)


def install_state():
    """这套东西是「装完了」，还是只把压缩包解开了？（2026-11-02，`G-188`）

    为什么要单立一个状态：外部实测的三种真实入口里，最坏那种是「解压了＝能用了 →
    直接贴开工话术」。那条路上没人做安装步骤，于是 `.git` 没 init、钩子没复制，
    **而本页照样把十项跑完、报一堆红，和「装好了但内容还没建」长得一模一样**——
    用户和 AI 都分不出来，只能各自猜，猜错的方向还相反（一个以为包坏了，一个以为没事）。

    判据只查「安装步骤有没有做过」这种确定性事实，不查内容：
      · `.git/`                        ← 步骤 1 做没做
      · `core.hooksPath` ＝ scripts/hooks 且文件在  ← 步骤 2 做没做（没有它，整套门禁等于没通电）

    **2026-11-11 改判法**（外部回执《省字节进仓库》§二）：原来是查
    `.git/hooks/pre-commit` 那个**副本**。副本本身就是病——改一份忘一份，
    而且 `.git/hooks` 不在版本库里，clone 下来永远没有。现在 hook 只活在库里
    `scripts/hooks/pre-commit`，用 `core.hooksPath` 指过去；装一次，之后改脚本不用重装。

    所以不会误伤「装好了但一个字没写」的新人——那种人这两样都有。
    返回 [(缺什么, 第几步, 补救命令), ...]，空列表＝装完了。
    """
    miss = []
    if not os.path.isdir(os.path.join(ROOT, ".git")):
        miss.append(("git 没初始化", "步骤 1", "git init"))
    hook = os.path.join(ROOT, "scripts", "hooks", "pre-commit")
    hp = ""
    try:
        hp = subprocess.run(["git", "-C", ROOT, "config", "core.hooksPath"],
                            capture_output=True, text=True).stdout.strip()
    except OSError:
        pass
    if not os.path.isfile(hook):
        miss.append(("门禁钩子源文件不见了", "步骤 2",
                     "从版本库把 `scripts/hooks/pre-commit` 取回来（git checkout -- scripts/hooks/）"))
    elif hp.replace("\\", "/").strip("/") != "scripts/hooks":
        miss.append(("门禁钩子没装（core.hooksPath 没指向库内）", "步骤 2",
                     "git config core.hooksPath scripts/hooks"))
    return miss


def load_profile():
    """读 `gate_profile.json`：本库里哪几项适用、其余为什么不适用。

    **为什么要有这一层**：同一套检查，在项目库里 17 项都有对象可判；
    在只装方法论的那个库里，11 项要的正文／台账／锚定表**根本不存在**——
    它们跑起来只会吐一堆假红（实测：`_anchor` 报 35 条断链，全是「子集里没有」）。

    **跳过不算通过**：调用方必须把跳过项从「绿」里扣掉，并在结论里印出覆盖率。
    """
    path = None
    if "--profile" in sys.argv:
        i = sys.argv.index("--profile")
        if i + 1 < len(sys.argv):
            path = sys.argv[i + 1]
    else:
        cand = os.path.join(ROOT, "gate_profile.json")
        path = cand if os.path.isfile(cand) else None
    if not path:
        return None, {}, {}
    if not os.path.isfile(path):
        print("✗ 指定的 profile 不存在：%s" % path)
        return None, {}, {}
    try:
        d = json.load(io.open(path, encoding="utf-8"))
    except Exception as e:
        print("✗ gate_profile.json 解析失败：%s" % e)
        print("   解析失败时**不退回「全跑」**——那会把假红当结论。先修 JSON。")
        return None, {}, {}
    allow = set(d.get("适用", []))
    why = d.get("不适用", {}) or {}
    return allow, why, d


def _check_install(raw):
    # ---------- 装没装完，先判这一步（`G-188`） ----------
    # 放在十项之前：装没装完和内容坏不坏是两个问题，混在一起报就等于两个都没报。
    if raw.get("跳过安装检查"):
        print("⏭ 安装态检查：跳过——本库是公开的方法仓，不是项目工作副本。")
        print("   钩子不装是对的：这里没有「提交前必须拦住」的内容改动。")
        print("")
    else:
        miss = install_state()
        if miss:
            print("✗ 这套东西还没装完（退出码 3）——下面十项一项都没跑。")
            print("")
            for what, step, fix in miss:
                print("   缺：%s（%s）" % (what, step))
                print("       补救：%s" % fix)
            print("")
            print("   这不是「内容还没建」，是「安装步骤还没做」。两件事处置完全相反：")
            print("     · 只是把压缩包解开了 → 照包根 `README.md` 的「三步开工」第 1 步做一遍")
            print("     · 以为自己装好了 → 你少的就是上面这几步，补上就好，**不用重装**")
            print("")
            print("   为什么不能先凑合：钩子不在，门禁就不会在提交那一刻跑，")
            print("   于是「有守卫」只是文档里的一句话，实际拦你的什么都没有。")
            print("")
            print("   补齐后重跑本页；在那之前，先别开工、先别出图。")
            print("")
            print("   （装法只有一条：`git config core.hooksPath scripts/hooks`——hook 在库内，不拷副本。）")
            return 3


def _collect_results(allow, why):
    results = []
    for title, script, args in STEPS:
        base = script[:-3] if script.endswith(".py") else script
        if allow is not None and base not in allow:
            results.append((title, script, "SKIP",
                            why.get(base, "未在 gate_profile.json 的「适用」里")))
            continue
        code, out = run(script, args)
        results.append((title, script, code, out))

    # 2026-11-09 02:1x（`G-561`）：判据自检怎么接。
    # 它 28 秒——压在每次跑门禁上，人早晚被逼去绕开。所以：
    #   · 默认**不跑**，但**必须印出来**（静默跳过等于没有这个检查，`G-492` 的教训）；
    #   · 加 `--full` 才跑；
    #   · 提交那一刻由 pre-commit 条件触发（只要 `00_原著/_*.py` 有暂存改动就跑）。
    if "--full" in sys.argv:
        code, out = run("_selftest.py", [])
        results.append(("判据自检", "_selftest.py", code, out))
    else:
        print("⚠ 判据自检（_selftest.py）— 未跑：它约 28 秒，默认不压在门禁上。")
        print("   要现在跑：`python _gate.py --full`；改过检查器的提交，pre-commit 会自动跑它。")
        print("")
    return results


def _report_results(results, brief):
    _nm = project_name()
    print("《%s》· 汇总报告（必经路径是本仓库的 pre-commit 钩子，本页只汇总）" % _nm)
    if _nm == _pname.DEFAULT:
        # 2026-11-02 外部实测（`G-158`）：README 没填名字的人第一眼看到的是一串占位字符，
        # 会怀疑拿到的是别人的旧工程。回退是预期行为，但**没解释就等于没设计**。
        # （注释里别把那串字符照抄进来——`_pname.py --check` 会把所有字面量都算作残留，
        #  它分不清「硬编码」和「解释硬编码」。见 `G-161`。）
        print("   （「%s」是占位符，不是别人的工程——在 `README.md` 顶部写一行 `> 项目：你的名字` 就换掉）" % _nm)
    print("=" * 46)
    print("")

    blocking = []
    warning = []
    no_scope = []
    skipped = []

    for title, script, code, out in results:
        if code == "SKIP":
            print("⏭ %s（%s）— **跳过**：%s" % (title, script, out))
            print("")
            skipped.append(title)
            continue

        if code is None:
            # 「没装」和「坏了」是两件事。
            # `_links` 是骨架库专有的检查（通用层引用通不通），项目库没有这个脚本；
            # 把它当阻断，两个库就永远不可能共用同一份 `_gate.py`——而共用本身比
            # 多一个检查值钱。**没有这个检查 ≠ 这个检查挂了**，所以跳过并印出来，
            # 覆盖率里会少一项，看得见。
            if "脚本不存在" in out:
                print("⏭ %s（%s）— **跳过**：本库没装这个脚本" % (title, script))
                skipped.append(title)
                continue
            print("✗ %s（%s）" % (title, script))
            print("   %s" % out.strip())
            blocking.append(title)
            continue

        if code == 0:
            mark, state = "✅", "通过"
        elif code == 1:
            mark, state = "✗", "阻断（P0）"
            blocking.append(title)
        else:
            mark, state = "⚠", "有提示"
            warning.append(title)

        # 范围自报检查（2026-11-01 立）：没自报范围的「绿」＝不知道盖住了多少，不当通过。
        # 这是外行唯一能审的维度——不懂正则，但看得懂「它说自己扫了多少」。
        if "[scope]" not in out:
            state += " ／ ⚠未自报范围"
            no_scope.append(title)

        print("%s %s（%s）— %s" % (mark, title, script, state))
        if not brief:
            for ln in out.split("\n"):
                if any(v in ln for v in VERDICT) and ln.strip():
                    print("   %s" % ln.rstrip())
        print("")

    print("=" * 46)
    channel_banner(brief)

    total = len(results)
    ok = total - len(blocking) - len(warning) - len(skipped)
    if skipped:
        print("小结：共 %d 项 ｜ 绿 %d ／ **跳过 %d** ／ 提示 %d ／ 阻断 %d"
              % (total, ok, len(skipped), len(warning), len(blocking)))
    else:
        print("小结：共 %d 项 ｜ 绿 %d ／ 提示 %d ／ 阻断 %d" % (total, ok, len(warning), len(blocking)))
    fresh = is_fresh_project() and bool(blocking)
    if fresh:
        print("")
        # 数字现算，不写死（`G-161`）：装没装 skill 会让红项数差一，
        # 而「九项」这个手写数字上一版就在包里印错过。
        print("→ **新项目第一站**：把正文放进 `00_原著/_原始归档/`，其余 %d 项会跟着松动——"
              % len(blocking))
        print("   **现在一项都不用修**。（那 %d 项红，是因为还没有东西可核，不是因为做错了）"
              % len(blocking))
    print("")

    if no_scope:
        print("⚠ %d 项未自报 [scope] 范围：%s" % (len(no_scope), "、".join(no_scope)))
        print("   没有范围自报的「绿」，等于不知道它盖住了多少——**不当通过**。")
        print("   补法：在该脚本开头打一行 `[scope] 扫了什么／跳过了什么／认不出什么`。")
        print("")

    if blocking:
        print("✗ %d 项阻断：%s" % (len(blocking), "、".join(blocking)))
        if fresh:
            print("   退出码 1 ＝ 这次提交会被 pre-commit 拦下。**空项目本来就该被拦**——")
            print("   它拦的是「还没有东西可核」，不是「你做错了」。")
            print("   处理二选一（都不叫「修」）：")
            print("     ① 建 → 把缺的那一份建出来（正文／设定集／台账，按第一站那句先建一样）；")
            print("     ② 现在建不了 → 写进跟进通道记一句「空壳基线，什么时候补」，")
            print("        再提交；别用 `--no-verify` 绕钩子——绕过去它就再也不会提醒你。")
        else:
            print("   退出码 1 ＝ 硬失败，**提交会被 pre-commit 拦下来**。")
            print("   处理二选一：")
            print("     ① 修掉 → 重跑本页确认变绿；")
            print("     ② 修不动 → 写进跟进通道，写清「欠什么、何时清」。")
            print("   红没有去向，就是今天这场账：一个漏数挂了整晚，没人知道它红着。")
        return 1
    if warning:
        print("⚠ %d 项有提示：%s" % (len(warning), "、".join(warning)))
        print("   退出码 2 ＝ **不阻断**提交，但也不等于通过，别当已定用。")
        print("   典型是待拍板队列（如 _world 的待裁冲突）——它等作者裁决，改代码消不掉。")
        return 2
    if skipped:
        print("✅ 本库适用的 %d 项都过；另有 **%d 项不适用**（逐条理由见上，未计入绿）。"
              % (ok, len(skipped)))
        print("   ⚠ **跳过不算绿**：本页只覆盖 %d/%d 项（%.0f%%）——没覆盖的那部分，没有在保护你。"
              % (ok, total, (100.0 * ok / total) if total else 0))
        return 0
    print("✅ 全绿：%d 项都过。" % total)
    print("   ⚠ 只代表「机器能判的都过了」——该不该改、写得好不好，本页判不了。")
    return 0


def main():
    brief = "--brief" in sys.argv
    allow, why, raw = load_profile()

    install_rc = _check_install(raw)
    if install_rc:
        return install_rc

    results = _collect_results(allow, why)

    return _report_results(results, brief)



if __name__ == "__main__":
    # 默认只印两行（作者 11-11 10:3x 定；起因：一份外部回执指出「第一次 clone 的人
    #   第一轮就被 5KB 输出吓跑，烧的是积分」）。
    #     ✅ 通过：16 项 ｜ 绿 14 ／ 提示 2 ／ 阻断 0
    #     　逐项：python <本脚本> --verbose
    #   **不省成“藏”**：一定要印「查了多少项、各多少」——不印数字，用户会怀疑根本没过检。
    #   三档：无参数（＝--quiet）＝两行结论 ／ --each（＝--detail）＝逐项结论＋红项名单 ／ --verbose＝全量。
    #   2026-11-11 11:1x 改名（外部回执 §二）：原来「逐项」那档叫 `--quiet`，而它比默认**大五倍**——
    #   全项目其它脚本的 `--quiet` 都是「只报结论」，唯独这里反着。人想省字节第一反应是加 `--quiet`，
    #   正好加反，而没人先读 help。现在 `--quiet` 归位成"最短那档"（等同不加参数），明细叫 `--each`。
    if "--verbose" in sys.argv:
        MODE = "verbose"
    elif "--each" in sys.argv or "--detail" in sys.argv:
        MODE = "each"
    else:
        MODE = "brief"          # 含 --quiet：它是最短那档的名字，不是明细

    import io as _io
    import contextlib as _ctx
    import re as _re
    _self = os.path.relpath(os.path.abspath(__file__), os.getcwd()).replace("\\", "/")

    _buf = _io.StringIO()
    with _ctx.redirect_stdout(_buf):
        _rc = main()
    _all = _buf.getvalue()
    _lines = _all.split("\n")

    if MODE == "verbose":
        print(_all.rstrip("\n"))
        sys.exit(_rc)

    # 顶格结论行（缩进的 ✗ 是明细——比如孤儿件名单 36 行，不是红，不能当结论用）
    # 2026-11-20 冷启动实测（`G-1202`）：这个正则原先没有 `⚠`，于是 `--each` 里
    # 「提示 1」这个计数孤零零挂着、逐项里却找不到是哪一项——读的人只会以为全绿。
    # 提示本身就是「还没建」，藏起来它，就等于帮它冒充通过。
    _item = _re.compile(r"^(✅|🟡|⚠|✗|❌|⏭)\s")
    _red = _re.compile(r"^✗ (\d+) 项阻断")
    _items = [l for l in _lines if _item.match(l)]
    _summ = [l for l in _lines if l.strip().startswith("小结：共")]
    _summ = _summ[0].strip() if _summ else ""
    _m = _re.search(r"共\s*(\d+)\s*项.*?绿\s*(\d+).*?(?:跳过\s*(\d+).*?)?提示\s*(\d+).*?阻断\s*(\d+)", _summ)
    if not _m:
        print(_all.rstrip("\n"))      # 读不出小结就别装省：宁可全给，也不给一句假结论
        sys.exit(_rc)
    _tot, _g, _sk, _w, _b = (int(x or 0) for x in _m.groups())
    _kv = "%d 项 ｜ 绿 %d" % (_tot, _g)
    if _sk:
        _kv += " ／ **跳过 %d**" % _sk
    _kv += " ／ 提示 %d ／ 阻断 %d" % (_w, _b)

    # 判「过没过」用**阻断数**，不用退出码：本套约定里 0=全绿、1=有阻断、2=有提示，
    #   而「14 绿／2 提示／0 阻断」是常态（退出码 2）。拿 _rc 判会把常态显示成红。
    if _b == 0 and _sk:
        print("⚠ 部分通过：" + _kv)
        if MODE == "each":
            for l in _items:
                print(l)
            if _summ:
                print(_summ)
        else:
            print("   跳过 %d 项**不算绿**：本页只覆盖 %d/%d 项（%.0f%%）。逐项理由：--each"
                  % (_sk, _g, _tot, (100.0 * _g / _tot) if _tot else 0))
        sys.exit(_rc)
    if _b == 0:
        print("✅ 通过：" + _kv)
        if MODE == "brief":
            print("   逐项：python %s --each ｜ 全量：--verbose" % _self)
        else:                      # each：逐项结论 + 小结，一条不少（约 800 字节）
            for l in _items:
                print(l)
            if _summ:
                print(_summ)
    else:
        if MODE == "brief":
            # 红路径：三行摘要在前，再展开红项。作者 11-11 10:0x 定：红了要能展开，
            #   但先给「哪项红、卡在哪、下一步」，别又灌 5KB。
            # 红路径：三行摘要 ＋ 只列**红**的那几条。
            #   绿项一条不印——红了还刷 14 行 ✅，等于把「哪里坏了」埋在一片好消息里。
            print("🔴 " + _kv)
            _names = []
            for l in _items:
                if not l.startswith("✗"):
                    continue
                _nm = l[2:].split("—")[0].strip()
                if _nm and "项阻断" not in _nm and not _nm[:1].isdigit() and _nm not in _names:
                    _names.append(_nm)
            print("   哪项红：" + ("、".join(_names) or "（见下）"))
            print("   卡在哪＋下一步：下面每条 ✗ 就是；单跑 `cd 00_原著 && python <脚本名>.py` 看全部")
            for l in _items:
                if l.startswith("✗"):
                    print("   " + l)
        else:
            for l in _items:
                print(l)
            if _summ:
                print(_summ)
    sys.exit(_rc)
