#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_pack.py — 打分发包：把通用层剥出来，做成一个能独立跑的空工作区。

完整说明：docs/maintain/代码内长文档/packaging/_pack.py.md
"""

import io
import os
import re
import shutil
import subprocess
import sys
import zipfile

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
ROOT = os.path.dirname(HERE)
TPL = os.path.join(HERE, "templates")

# ══════════════════════════════════════════════════════════════
# 〇 · 脱敏：不改源文件，只在复制时做替换
# ══════════════════════════════════════════════════════════════
# **为什么不直接改 `00_原著/_*.py`**
#   那些脚本在项目里是活的判据。清空它们的专名表，`_layer_audit` 和 `_collab`
#   会立刻「查不出任何专名」——项目门禁变成零覆盖假绿，而且没人会发现。
#   所以脱敏只发生在**复制到包里的那一份**上。源文件一个字不动。

# ── 第一步：把三类「专名表」整体清空（按已知格式精确匹配，不做词级替换）──
#   先清表、再替换词。顺序不能反：否则列表里那些词会被替换成 `[专名]`，
#   变成 `PROJECT_NOUNS = ["[专名]", "[专名]", ...]`——一个看起来在跑、
#   实际永远匹配不到的假表，比空表危险得多。
#   ⚠ **每条规则必须绑死文件名**（2026-11-02，G-147）。
#     原来只按内容匹配、不分文件，结果把 `_selftest.py` 里一条**测试夹具**
#     （`'PROJECT_NOUNS = ["测试组"]'`，一个字符串字面量）也当成了真表，
#     换成带换行的多行注释——**字符串被拦腰截断，整份文件语法错**。
#     而包里那个脚本是随包发出去的：用户一跑 `_selftest.py` 就是 SyntaxError。
#     **判据和夹具共用一种写法，改一处就会误伤另一处**——所以限制到「哪个文件」。
LIST_RULES = [
    # _collab.py：多行列表
    ("_collab.py",
     re.compile(r"PROJECT_NOUNS\s*=\s*\[[^\]]*\]", re.S),
     'PROJECT_NOUNS = []   # ← 换成你这个项目的专名，格式：["名1", "名2"]\n'
     '# ↑ 空表＝这项检查不跑。**不是「查过了没问题」，是「还没配」**。'),

    # _layer_audit.py：来源 A 存量黑名单
    ("_layer_audit.py",
     re.compile(r"(?m)^A\s*=\s*\[[^\]]*\]", re.S),
     'A = []   # ← 换成你这个项目的专名。空表＝来源 A 整组不查'),

    # _hollow.py：字典里的行内列表
    ("_hollow.py",
     re.compile(r'"人物"\s*:\s*\[[^\]]*\]'),
     '"人物": [],   # ← 换成你这个项目的人物名'),
]

# ── 第二步：剩下的散落专名 ──
#   **每个词给一个不同的代号**，不能全替换成同一个占位符。
#
#   实测反例（2026-11-01 23:40，第一次脱敏后）：
#       两列并排写「[专名]（零改造人类） | [专名]（高度机械改造）」——读者分不清哪列是哪列；
#       紧接着一句「[专名]那一列是我按品类默认值猜的」——「那一列」指谁，句意直接失效。
#       而那句正是全文最重要的一条警示（"这一列是猜的，别当真"）。
#   **V3 会绿，但文档读不懂。** 这就是"验包通过"和"能用"之间的距离。
#
#   所以：同一个词 → 同一个代号（前后一致），不同的词 → 不同代号（能区分）。
PROJECT_NAME_NOUNS = []   # 项目专名由使用者自行填写；本仓库不内置任何真实项目名
_PROJECT_LABEL = "某项目"

STEMS = "甲乙丙丁戊己庚辛壬癸"


def _load_nouns():
    """词表来源：`packaging/_nounlist.py`（三源合一：专名表＋台账＋补充词）。

    **不在这里另抄一份**。抄一份就又是一对会漂的副本——今天已经在
    `07_视觉提示词规则` 上吃过一次亏（三份、31 条、编号全一致、内容分叉 6 条）。
    """
    sys.path.insert(0, HERE)
    import _nounlist
    return _nounlist.load()


try:
    NOUNS, _FIXED = _load_nouns()
    _NOUN_ERR = None
except Exception as _e:      # 词表缺失／解析失败：**不在导入时死**，交给 main() 说人话
    NOUNS, _FIXED = [], {}
    _NOUN_ERR = _e

# 长的先替。不这么排的话，长专名会先被它的前缀命中，剩下「前缀[项目名]」这种半截东西。
_PROJECT_NAMES = sorted(PROJECT_NAME_NOUNS, key=len, reverse=True)
_OTHER_NOUNS = sorted([n for n in NOUNS if n not in PROJECT_NAME_NOUNS],
                      key=len, reverse=True)
# 代号按词排一次，整个打包过程固定不变——同一个词在任何文件里都是同一个代号。
# 具体编号在 main 里按「在包里出现的频率」定（见 `_build_labels`），
# 这样常见的角色是甲乙丙，罕见的才排到后面。若按字典序固定，一份只出现两个
# 角色的文档会得到「角色辛／角色壬」这种跳号，读者会以为中间还有六个没显示。
_LABEL = {}


def _build_labels(plan):
    """按每个词在包内出现的总次数编号：越常见越靠前（甲、乙、丙…）。"""
    from collections import Counter
    cnt = Counter()
    for src, rel in plan:
        if src.startswith(TPL) or not rel.endswith(TEXT_EXT):
            continue
        txt = io.open(src, encoding="utf-8", errors="replace", newline="").read()
        for n in _OTHER_NOUNS:
            k = txt.count(n)
            if k:
                cnt[n] += k
    ordered = [n for n, _ in cnt.most_common()] + [n for n in _OTHER_NOUNS if n not in cnt]
    for i, n in enumerate(ordered):
        _LABEL[n] = "角色" + (STEMS[i] if i < len(STEMS) else str(i + 1))
    return ordered


def _strip_project_skips(txt):
    """删掉 `_anchor.py` 里指向「本机开发目录」的排除项。

    **为什么**：包是空的——`99_过程稿/备份`、`G1移植测试/样本` 这些目录根本不存在。
    留着排除项，`_anchor` 一启动就报「排除项指向不存在的目录」6 处，
    而它自己的理由写得很清楚：「空转的排除＝替一块不存在的区域放行」。
    **在项目里这是真警报，在包里是假警报**——用户第一眼就以为包坏了（`G-140` 实测报上来）。
    skills 那两条保留：`skills/` 在包里存在，排除是有效的。
    """
    drop = ('"99_过程稿/备份"', '"99_过程稿/已归档"', '"99_过程稿/文笔校准_测试1"',
            '"99_过程稿/文笔校准_测试2"', '"G1移植测试/样本"', '"packaging/templates"')
    out = []
    for line in txt.split("\n"):
        if any(line.strip().startswith(d) for d in drop):
            continue
        out.append(line)
    return "\n".join(out)


def desensitize(txt, rel=""):
    """返回 (脱敏后的文本, 替换次数)。"""
    hits = 0
    fn = os.path.basename(rel)
    for target, pat, rep in LIST_RULES:
        if fn != target:
            continue          # 只改它自己那一份，别碰别处同形的字符串
        txt, n = pat.subn(rep, txt)
        hits += n
    # 指定替换的词先走：组织名／设定词／别名。
    # 它们不能套「角色N」——某个组织名变成「角色甲」读起来是错的，
    # 而某个具体名词变成「角色甲」更是无意义。按类别给词，人才读得懂。
    for k in sorted(_FIXED, key=len, reverse=True):
        c = txt.count(k)
        if c:
            txt = txt.replace(k, _FIXED[k])
            hits += c
    for n in _PROJECT_NAMES:
        c = txt.count(n)
        if c:
            txt = txt.replace(n, _PROJECT_LABEL)
            hits += c
    for n in _OTHER_NOUNS:
        c = txt.count(n)
        if c:
            txt = txt.replace(n, _LABEL[n])
            hits += c
    if rel.endswith("_anchor.py"):
        txt = _strip_project_skips(txt)
    return txt, hits


TEXT_EXT = (".md", ".py", ".txt", ".json", ".yml", ".yaml", ".sh", ".html")

# ══════════════════════════════════════════════════════════════
# 一 · 白名单：要带的，一份一份列
# ══════════════════════════════════════════════════════════════

# ① 通用层规范（Agent框架/）
#    去留由**文件头的层声明**决定（见 `frame_layer()`），不由下面那张字典决定。
INCLUDE_FRAME = True

# ── EXCLUDE_FRAME 已降级为「附注」，不再决定去留 ──
#
# 2026-11-04 之前：这张字典**就是**判定依据，文件头的声明只是给人看的。
# 会漂，而且漂的是最坏的方向——一份文件头上写着「混合层（通用方法＋本项目实例）」，
# 字典没列它，于是整份被打进包发出去（`G-295` 实测）。
#
# 2026-11-04 之后：**声明说了算**。这张字典只回答第二个问题——
# 「这份既然是项目层，还有没有别的处置要说」（例如包里另给一份模板版）。
# 声明通用却被这里排除 → `collect()` 当场报错停打包，不许两处各说各话。
#
# 现状：8 条 vs 8 份声明为项目层，完全对得上。也就是说这张字典现在**只是一份说明**，
# 它之所以还在，是因为有一半条目带着「包里另给模板」这个信息，别处没地方放。
EXCLUDE_FRAME = {
    # ── 三份自报「项目层」的（`_layer_audit` 认可的那三份）──
    # `[台账]跟进通道.md` 原来是整份排除的——**但门禁的「修不动就写进通道」那条出路
    #   指的是这个文件**，包里没有它，那句提示就是一个死链接（`G-140` 实测报上来）。
    #   现在改成带一份空白版（`templates/跟进通道.md`）——**排除项必须留着**：
    #   留着＝跳过真台账、只进模板；删掉＝真台账也被复制一遍（先写后被模板覆盖），
    #   白脱敏十几万字，替换计数也会虚高（2026-11-02 实测 94 → 229）。
    "[台账]跟进通道.md": "项目层：施工日志，全是本项目的事件、编号、缺口；包里由 templates/跟进通道.md 补一份空白版",
    "体检_通用层与纪律冲突_20261028.md": "项目层：存档报告，整份在讲本项目的冲突",
    "脱钩体检_20261027.md": "项目层：存档报告，同上",

    # ── 其余带项目数据的 ──
    "README.md": "含大量本项目实例引用；包里另给一份手写的简短版",
    "[示例]清单输入样本.md": "示例取自本项目文本，未脱敏",
    "待打磨区_方法论台账.md": "每条候选都挂着本项目的实例与编号",
    "新手上手引导.md": "步骤写的是本项目的路径与阶段，包里另给",

    # ── 本脚本自己不需要 ──
    "13_外部环节接入契约_v0.1.md": "讲的是「别人接进来」，不是新用户上手路径；要带可另议",
}

# ② 标准件（通用，含「怎么定」而不含「本项目定成什么」）
INCLUDE_STD = [
    "[标准]分镜双出口_漫剧与AIGC视频_v1.md",
    "[标准]文字转画面转化规则_v1.md",
    "[标准]索引层构建标准_v1.md",
    "[标准]美术定调_v1.md",
    "[标准]视觉锚点包_v1.md",
    "[标准]人物定妆卡提示词_v1.md",
]

# ③ 脚本：全部 22 个都带
#    其中 18 个绑死本项目的表名／专名——它们带过去是**参照物**，不是拿来直接跑的。
#    这一点已写进 `Agent框架/11_分发说明_v1.md` §二，包里沿用它，另在 README 里说明
INCLUDE_SCRIPTS = True

# ③-b 不带的脚本：**依赖正文／设定集才能工作**的那些。
#      包里没有正文，它们本身就是空转；而它们代码里嵌着的是整个世界的词汇表——
#      带出去等于把设定集换个文件名送人。**「工具」和「词汇表」要分开看。**
EXCLUDE_SCRIPTS = {
    "_hollow.py": "专名对账件：TERMS 表就是整套世界词汇（人物／地点／物件／组织／技术／历史事件），"
                  "它干的事只是「数这些词在正文出现几次」。包里没有正文 → 零用处，"
                  "只剩一张词汇表被带出去",
    "_probe_a.py": "A 组探针：直接读正文与设定集做对照，包里没有这些文件；"
                   "代码里还嵌着三个真实组织名的清单",
}

# ④ skill 壳（内部的项目层要剥掉，见 SKILL_STRIP）
INCLUDE_SKILLS = True
SKILL_STRIP = ["references/projects"]   # 项目专属层，含文风红线与设定内核

# ⑤ git 钩子源（不是 .git/hooks 那个安装副本）
INCLUDE_HOOK_SRC = "scripts/git_hooks/pre-commit"

# ══════════════════════════════════════════════════════════════
# 二 · 模板替换：凡是含项目数据的，换成 templates/ 里的空白版
# ══════════════════════════════════════════════════════════════
# 键 = 包里的目标路径（相对包根）；值 = templates/ 下的文件名
TEMPLATES = {
    # 2026-11-02（`G-160`）外部实测：外行拿到包，第一句诉求是「我只想知道怎么装」。
    # 而当时解压后第一眼是 `使用说明.txt`（12.5 KB，讲的是「怎么用」），
    # 该先读的 `安装.md`（20 KB）排在它后面——**新人先读最长的那份，读到的是装完以后的事。**
    # 所以加这一份：两分钟读完、只管一件事（解压→复制→等）。
    "从这里开始.txt": "从这里开始.txt",
    # 给人读的那一份，讲「装完之后怎么用」。**排在入口后面**。
    "使用说明.txt": "使用说明.txt",
    "README.md": "README.md",
    "安装.md": "安装.md",
    "版权与开源红线.md": "版权与开源红线.md",
    "发布前检查清单.md": "发布前检查清单.md",
    # 模板源叫 `gitignore`（无点）——放在 templates/ 里如果带点，很多工具会当隐藏文件跳过。
    # 打包时还原成 `.gitignore`。它必须进包：没有它，用户第一次 `git add .` 会把图和备份全加进去。
    ".gitignore": "gitignore",
    # 原 README 含大量本项目实例引用，不带；这份是手写的精简导航
    "Agent框架/README.md": "框架README.md",
    "00_原著/[台账]常量台账_v1.md": "常量台账.md",
    "Agent框架/[台账]跟进通道.md": "跟进通道.md",
}

# ══════════════════════════════════════════════════════════════
# 三 · 包里必须存在的目录（空目录也要建，用户第一眼看到结构）
# ══════════════════════════════════════════════════════════════
MUST_DIRS = [
    "Agent框架",
    "00_原著",
    "00_原著/_原始归档",     # 门禁里「新项目第一站」指的就是它，空着也要在（G-158）
    "99_过程稿",
    "skills",
]


# ══════════════════════════════════════════════════════════════
# 三·补 · 包名（G-179）
# ══════════════════════════════════════════════════════════════
# 2026-11-02 差点发出去一个「解压出来叫 _pack_new」的包。原因是 `_write_zip` 里
# 顶层目录名原为 `os.path.basename(out)`——**打到哪个临时目录，包就叫那个临时目录的名**。
# 现有硬闸全看不见这件事（V0／V1／V6 只看包内的相对结构），只会在别人解压那一刻暴露，
# 而用户看到的画面是「文件夹名字跟我被要求核的对不上」→ 结论「包是坏的」。
#
# 所以包名进常量，并**两处一起对账**：
#   ① zip 顶层目录名 == PKG_NAME
#   ② 包内 `从这里开始.txt` 正文里提到的包名 == PKG_NAME
# 两处都查，是因为「改版本号只改了一处」和「打到临时目录」是同一个病的两种发作方式。
PKG_NAME = "AI创作工作流_v0.2"
PKG_ENTRY_TXT = "从这里开始.txt"


# ══════════════════════════════════════════════════════════════
# 四 · 清单两份对账（G-150）
# ══════════════════════════════════════════════════════════════
# 2026-11-02 外部实测第 10 轮报绿之后，人肉去核「重复项到底进没进分发包」，
# 才发现两件事：
#
#   ① 项目里的 `发布前检查清单.md` 已经加到 §1.1–1.8，**页脚还写着「七项不许删项」**
#      ——同一个文件里，标题说八项、页脚说七项。
#   ② 包里发出去的那份是 `packaging/templates/发布前检查清单.md`，
#      **它压根没有「文档没有整段连贴两遍」这一项**——规矩在项目里，没跟着包走。
#
# ② 是典型的副本漂移（G-125）：源清单加项，模板是另一份手写的副本，不会自己跟。
# 而 `_verify_package` 只验「这个文件在不在」，**内容对不上它是绿的**。
#
# 所以加这道闸：两份清单的**条目数必须相等**（内容可以按项目/通用两份写，
# 但项数不许各说各话），并且每份自己的「N 项」不许和自己的条目数打架。
# 数字对不上就红——不猜谁对谁错，让人去看。

_CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _cn2int(s):
    """够用就行：一…十、十一…十九、二十。多了用不上。"""
    s = s.strip()
    if s in _CN_NUM:
        return _CN_NUM[s]
    if "十" in s:
        a, _, b = s.partition("十")
        return (_CN_NUM.get(a, 1) if a else 1) * 10 + (_CN_NUM.get(b, 0) if b else 0)
    return None


def _checklist_items(text):
    """两个文档的编号体系不一样，但都是「### + 编号 + 标题」：源用 1.1，模板用 ①。
    只数**动作项**，不数小节。"""
    return len(re.findall(r"(?m)^###\s*(?:\d+\.\d+|[①②③④⑤⑥⑦⑧⑨⑩])\s", text))


def _stated_counts(text):
    """找出文中所有自称的「N 项」，返回 [(原文片段, 数字)]。

    **只认管着 §一 的那两处**：小节标题（「发布前（八项…）」）和页脚那句
    （「§一 的八项不许删项」）。别处的「（三项）」管的是别的节，不是动作项——
    第一版按「（N项」全文抓，当场把 §二 的「发布后（三项）」当成打架，
    闸门绿不了。**判据宽到能误报，人就学会无视它，那比没有更坏。**"""
    out = []
    for m in re.finditer(r"(?m)^##[^\n]*(?:发布前|发之前)[^\n]*?（([一二三四五六七八九十]+)项", text):
        out.append((m.group(0).strip(), _cn2int(m.group(1))))
    for m in re.finditer(r"§一\s*的\s*([一二三四五六七八九十]+)\s*项", text):
        out.append((m.group(0), _cn2int(m.group(1))))
    return [(t, n) for t, n in out if n]


# ── 提示词副本（G-160）：同一段话手抄三处，改一份忘两份就是 G-125 的副本漂移。
# 用**整句**做锚点，不用行号——行号会被前面加两行就错位，而整句改了三份都得改。
PROMPT_HEAD = "我拿到了一套 AI 创作工作流，压缩包在这里："
PROMPT_TAIL = "更不要为了让检查变绿去造假文件。"
PROMPT_COPIES = [
    ("安装.md", os.path.join(TPL, "安装.md")),
    ("使用说明.txt", os.path.join(TPL, "使用说明.txt")),
    ("从这里开始.txt", os.path.join(TPL, "从这里开始.txt")),
]


def _prompt_body(text):
    """从一份文档里抠出提示词正文；首句或尾句不见了就返回 None。"""
    i = text.find(PROMPT_HEAD)
    j = text.find(PROMPT_TAIL, i if i >= 0 else 0)
    if i < 0 or j < 0:
        return None
    return text[i:j + len(PROMPT_TAIL)]


def _prompt_norm(s):
    """抹掉「行尾空白」和「多打一个空行」这两种无害差异，其余一个字都要一样。"""
    out = []
    for line in s.replace("\r\n", "\n").split("\n"):
        line = line.rstrip()
        if not line and (not out or not out[-1]):
            continue
        out.append(line)
    while out and not out[-1]:
        out.pop()
    return "\n".join(out)


def _prompt_carriers():
    """扫 templates 下所有 md／txt，看看**除清单之外还有谁抄了这段话**。

    这一段是 `G-153` 的教训换来的：判据清单本身也可能漏登——
    「我列了三份」和「实际有几份」是两件事，**后者得扫出来，不能靠我记得**。
    """
    out = []
    for fn in sorted(os.listdir(TPL)):
        if not fn.lower().endswith((".md", ".txt")):
            continue
        try:
            txt = io.open(os.path.join(TPL, fn), encoding="utf-8-sig").read()
        except Exception:
            continue  # 吞：单个模板读不到时跳过，其余载体继续对账。
        if PROMPT_HEAD in txt:
            out.append(fn)
    return out


def check_prompts():
    """硬闸：提示词副本必须一份不少、逐字一致。返回 True 表示过。"""
    declared = [n for n, _p in PROMPT_COPIES]
    carriers = _prompt_carriers()
    ok = True
    for fn in carriers:
        if fn not in declared:
            ok = False
            print("✗ %s 里也抄着这段提示词，但没登记进对账清单" % fn)
    for fn in declared:
        if fn not in carriers:
            ok = False
            print("✗ 清单登记了 %s，但那份里找不到提示词（删了？改了首句？）" % fn)
    if not ok:
        print("   PROMPT_COPIES 要跟着正文一起改：多一份就登记，少一份就删登记。")
        print("   判据清单漏登，等于这一份从此没人管。")
        return False

    got = {}
    ok = True
    for label, path in PROMPT_COPIES:
        if not os.path.isfile(path):
            print("✗ 提示词副本缺失：%s" % path)
            return False
        body = _prompt_body(io.open(path, encoding="utf-8-sig").read())
        if body is None:
            ok = False
            print("✗ %s 里抠不到提示词——首句或尾句被改掉了" % label)
            continue
        got[label] = _prompt_norm(body)
    if not ok:
        print("   首句：%s" % PROMPT_HEAD)
        print("   尾句：%s" % PROMPT_TAIL)
        print("   要改措辞就三份一起改；只动一处，另两处就悄悄过期了。")
        return False

    base_label = PROMPT_COPIES[0][0]
    base = got[base_label]
    for label, body in got.items():
        if body == base:
            continue
        ok = False
        a, b = base.split("\n"), body.split("\n")
        print("✗ 提示词副本不一致：%s ↔ %s" % (base_label, label))
        for n, (x, y) in enumerate(zip(a, b), 1):
            if x != y:
                print("     首个不同在第 %d 行：" % n)
                print("       %s：「%s」" % (base_label, x[:70]))
                print("       %s：「%s」" % (label, y[:70]))
                break
        else:
            print("     行数不同：%s %d 行 ／ %s %d 行"
                  % (base_label, len(a), label, len(b)))
        print("   收包的人从哪一份复制都可能，三份不一样就等于三个版本。")
    if ok:
        print("· 提示词副本 %d 处逐字一致（%d 字）"
              % (len(got), len(base)))
    return ok


def check_checklists():
    """硬闸：两处清单条目数对账 + 自称项数自洽。返回 True 表示过。"""
    pairs = [("项目清单", os.path.join(ROOT, "发布前检查清单.md")),
             ("分发包清单", os.path.join(TPL, "发布前检查清单.md"))]
    counts = {}
    ok = True
    for label, path in pairs:
        if not os.path.isfile(path):
            print("✗ %s 缺失：%s" % (label, path))
            return False
        text = io.open(path, encoding="utf-8").read()
        n = _checklist_items(text)
        counts[label] = n
        stated = _stated_counts(text)
        bad = [(t, v) for t, v in stated if v != n]
        if bad:
            ok = False
            print("✗ %s 自己有 %d 条动作项，但文中这么写：" % (label, n))
            for t, v in bad:
                print("     「%s」→ 说了 %d 项" % (t, v))
            print("     同一条清单里的数字打架，读的人只会以为「八项」是笔误。")
        else:
            print("· %s：%d 条动作项，自称项数一致" % (label, n))

    if counts.get("项目清单") != counts.get("分发包清单"):
        ok = False
        print("✗ 两份清单条目数不一致：项目 %d 条 ／ 分发包 %d 条"
              % (counts.get("项目清单", -1), counts.get("分发包清单", -1)))
        print("   源清单加了项、模板没跟——这就是 G-125 说的副本漂移。")
        print("   改哪边都行，但两边得一样多；包里那份是收包的人真正会拿着的。")
    return ok


# ──────────────────────────────────────────────────────────────
def _should_skip(path, name):
    """复制前最后一道人工判断：碰到这些形态一律不带。"""
    if name.startswith("."):
        return "隐藏文件／目录"
    if ".bak_" in name or name.endswith(".bak"):
        return "备份文件"
    if name == "__pycache__":
        return "缓存"
    # 正文与中间稿：只按名字拦不够，但这一层能拦住绝大多数
    for bad in ("定稿_v", "中间稿", "草稿", "勘误", "标注", "抽卡记录",
                "审校", "视图]", "清单]"):
        if bad in name:
            return "疑似含项目数据：文件名命中「%s」" % bad
    return None


# 层声明的唯一格式：`> **层**：<档位>`。只看字段值，不看整行包含什么字
# （`_collab` 2026-11-04 就栽在这：一份通用层文件的声明里写了「项目层放数」，
#  整行包含判定把它判成了项目层）。
LAYER_RE = re.compile(r"^>\s*\*\*层\*\*\s*[：:]\s*\*{0,2}(通用层|项目层|混合)")


def frame_layer(path, head_lines=24):
    """读文件头的层声明。返回 '通用层' / '项目层' / '混合' / None（没声明）。

    **没有默认值。** 没声明就返回 None，由 `collect()` 报错停打包。
    打包侧为什么必须严：进包是往外发，发错了收不回来；本地漏扫一遍只是下次再扫。
    两边代价不对称，所以这里的默认值只能是「不打」。

    与 `00_原著/_layer_audit.py` 的 `declared()` 同一口径——**改一处必须改两处**。
    那边是本地体检（可以兜底、可以重来），这边是出货闸（不能）。
    """
    try:
        head = io.open(path, encoding="utf-8", errors="replace").read().split("\n")[:head_lines]
    except OSError:
        return None
    for ln in head:
        m = LAYER_RE.search(ln)
        if m:
            return m.group(1)
    return None


def _add_to_plan(plan, skipped, src, rel):
    if not os.path.isfile(src):
        skipped.append((rel, "源文件不存在"))
        return
    plan.append((src, rel))


def _report_decl_errors(no_decl, bad_decl, decl_conflict):
    if not (no_decl or bad_decl or decl_conflict):
        return
    print("✗ 层声明有问题，不打这个包：")
    for rel in no_decl:
        print("     缺声明                %s" % rel)
    for rel in bad_decl:
        print("     用了已取消的「混合」    %s" % rel)
    for rel, note in decl_conflict:
        print("     声明是通用层，却在 EXCLUDE_FRAME 里被排除  %s" % rel)
        print("        字典给的理由：%s" % note[:96])
    print()
    print("   判定依据只有一个：文件头的 `> **层**`。")
    print("   通用层写法：`> **层**：**通用层**——整份可搬给别的项目。一句话为什么`")
    print("   项目层写法：`> **层**：**项目层**——**不进分发包**。一句话为什么`")
    print("   **混合层已取消**：要么把项目部分搬到项目层、本文件变通用层；要么整份判项目层。")
    print("   声明通用却被字典排除 → 改声明，或把字典那一条删掉。两处不许各说各话。")
    raise SystemExit(1)


def _collect_frame(plan, skipped):
    no_decl, bad_decl, decl_conflict = [], [], []
    # G-296 的完整来历见 docs/maintain/代码内长文档/packaging/_pack.py.md（维护仓，不随包）。
    if INCLUDE_FRAME:
        d = os.path.join(ROOT, "Agent框架")
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".md"):
                continue
            p = os.path.join(d, fn)
            rel = "Agent框架/" + fn
            lay = frame_layer(p)
            if lay is None:
                no_decl.append(rel)
                continue
            if lay == "混合":
                bad_decl.append(rel)
                continue
            if lay == "项目层":
                skipped.append((rel, EXCLUDE_FRAME.get(fn, "层声明为项目层（不进分发包）")))
                continue
            if fn in EXCLUDE_FRAME:
                decl_conflict.append((rel, EXCLUDE_FRAME[fn]))
                continue
            _add_to_plan(plan, skipped, p, rel)
    _report_decl_errors(no_decl, bad_decl, decl_conflict)


def _collect_std_scripts(plan, skipped):
    for fn in INCLUDE_STD:
        _add_to_plan(plan, skipped, os.path.join(ROOT, "00_原著", fn), "00_原著/" + fn)
    if not INCLUDE_SCRIPTS:
        return
    d = os.path.join(ROOT, "00_原著")
    for fn in sorted(os.listdir(d)):
        if fn.startswith("_") and fn.endswith(".py"):
            if fn in EXCLUDE_SCRIPTS:
                skipped.append(("00_原著/" + fn, EXCLUDE_SCRIPTS[fn]))
                continue
            _add_to_plan(plan, skipped, os.path.join(d, fn), "00_原著/" + fn)


def _collect_skills(plan, skipped):
    if not INCLUDE_SKILLS:
        return
    base = os.path.join(ROOT, "skills")
    if not os.path.isdir(base):
        return
    for skill in sorted(os.listdir(base)):
        sdir = os.path.join(base, skill)
        if not os.path.isdir(sdir):
            continue
        for dirpath, dirnames, filenames in os.walk(sdir):
            rel_dir = os.path.relpath(dirpath, base).replace("\\", "/")
            if any(rel_dir.endswith(s) for s in SKILL_STRIP):
                skipped.append(("skills/" + rel_dir + "/",
                                "skill 的项目专属层（含文风红线与设定内核）"))
                dirnames[:] = []
                continue
            dirnames[:] = [x for x in dirnames if x != "__pycache__"]
            for fn in filenames:
                why = _should_skip(dirpath, fn)
                if why:
                    skipped.append(("skills/%s/%s" % (rel_dir, fn), why))
                    continue
                _add_to_plan(plan, skipped, os.path.join(dirpath, fn),
                             "skills/%s/%s" % (rel_dir, fn))


def _collect_templates(plan, skipped):
    for rel_target, tpl_name in TEMPLATES.items():
        src = os.path.join(TPL, tpl_name)
        if not os.path.isfile(src):
            skipped.append(("模板 " + tpl_name, "模板文件缺失——打包会因此失败"))
            continue
        plan.append((src, rel_target))


def collect(dry=False):
    """返回 [(源绝对路径, 包内相对路径), ...] 和被跳过者的清单。"""
    plan, skipped = [], []
    _collect_frame(plan, skipped)
    _collect_std_scripts(plan, skipped)
    _collect_skills(plan, skipped)
    if INCLUDE_HOOK_SRC:
        _add_to_plan(plan, skipped, os.path.join(ROOT, INCLUDE_HOOK_SRC), INCLUDE_HOOK_SRC)
    plan.append((os.path.join(HERE, "_dupcheck.py"), "00_原著/_dupcheck.py"))
    plan.append((os.path.join(TPL, "项目配置_空模板.json"), "00_原著/_项目配置.json"))
    _collect_templates(plan, skipped)
    return plan, skipped


def _preflight():
    # ── 骨架侧 / 项目侧 ───────────────────────────────────────────────
    # `_pack.py` 做的是「把一个项目打成可分发的包」，它需要那个项目的词表。
    # 骨架库不含任何项目内容 → 没有词表可用。**这是正常的，不是坏了。**
    # 先说清楚，别让人对着一屏 traceback 猜自己是不是装错了。
    if not os.path.isdir(os.path.join(ROOT, "00_原著")):
        print(
            "[packaging] 这里是「骨架侧」，`_pack.py` 不在这里运行。\n"
            "\n"
            "  它做的事：把一个**项目**打成可分发的包，需要那个项目的词表。\n"
            "  本仓库不含任何项目内容 —— 所以没有词表可用。**这是正常的，不是坏了。**\n"
            "\n"
            "  要用它：复制到你自己的项目里（`<项目根>/packaging/_pack.py`），\n"
            "  再照 `packaging/脱敏词表_样例.txt` 填三份词表。\n"
            "  查缺什么：`python packaging/_doctor.py`\n",
            file=sys.stderr)
        return 2

    if _NOUN_ERR is not None:
        print("[packaging] 词表不全，拒绝开工 —— 空词表会让任何包都显示「干净」：\n  %s"
              % str(_NOUN_ERR).replace("\n", "\n  "), file=sys.stderr)
        print("\n[packaging] 查缺什么：`python packaging/_doctor.py`", file=sys.stderr)
        return 1


def _parse_args(argv):
    dry = "--dry-run" in argv
    do_zip = "--zip" in argv
    out = None
    if "--out" in argv:
        i = argv.index("--out")
        if i + 1 < len(argv):
            out = os.path.abspath(argv[i + 1])
    return dry, do_zip, out


def _check_plan(plan, skipped, dry, out):
    print("── 打包计划 ──")
    print("  带出：%d 个文件" % len(plan))
    print("  跳过：%d 个" % len(skipped))
    print()

    missing_tpl = [s for s in skipped if s[1].startswith("模板文件缺失")]
    if missing_tpl:
        print("✗ 有模板缺失，先补齐再打包：")
        for rel, why in missing_tpl:
            print("    %s" % rel)
        print()
        print("  模板在 packaging/templates/ 下。缺模板＝包里有文件没被换成空白版，")
        print("  那一步会直接把项目数据带出去。**不许跳过。**")
        return 1

    if dry:
        print("── 会带出这些 ──")
        for src, rel in plan:
            print("  + %s" % rel)
        print()
        print("── 会跳过这些（前 25 条）──")
        for rel, why in skipped[:25]:
            print("  - %-52s %s" % (rel[:52], why))
        if len(skipped) > 25:
            print("  …… 还有 %d 条" % (len(skipped) - 25))
        return 0

    if not out:
        print("要么加 --dry-run 先看清单，要么加 --out <目录> 真打包。")
        return 2

    if os.path.isdir(out) and os.listdir(out):
        print("✗ 输出目录非空：%s" % out)
        print("  不覆盖——避免半新半旧混在一起。换个目录，或先清空。")
        return 1

    # ── 硬闸 -2：提示词三份副本对账（G-160）。和 -1 同族：手抄多份、
    #    改一份忘两份，错的地方在收包人的对话框里，不在我的屏幕上。
    if not check_prompts():
        print()
        print("✗ 提示词副本对不上，**这包不能发**（输出目录还没建，磁盘上是干净的）")
        return 1

    # ── 硬闸 -1：两处清单对账（G-150）。放最前面——一份「少一条」的清单
    #    打进包里不会报错，只会在收包的人手里静悄悄地少管一件事。
    if not check_checklists():
        print()
        print("✗ 清单对账不过，**这包不能发**（输出目录还没建，磁盘上是干净的）")
        return 1
    print("")


def _write_files(out, plan):
    for rel_dir in MUST_DIRS:
        os.makedirs(os.path.join(out, rel_dir), exist_ok=True)

    # 脚本数**现算**，不让文档手写（2026-11-02，G-143）。
    # 这个数字已经当场过期过两次：`G-132` 22→20，这轮加 `_pname` 又该 20→21。
    # 模板里写 `__NSCRIPTS__`，打包时填真值——**能被算出来的数字，不许手抄。**
    n_scripts = sum(1 for _s, _r in plan
                   if _r.startswith("00_原著/_") and _r.endswith(".py"))
    n_files = len(plan)          # 同一族问题：`安装.md` 里那句「写 74 个文件」已经过期两次

    total_hits = 0
    touched = 0
    for src, rel in plan:
        dst = os.path.join(out, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)

        # 二进制直接搬。
        if not rel.endswith(TEXT_EXT):
            shutil.copy2(src, dst)
            continue

        # 模板本来就干净（不用脱敏），但要填占位符。
        if src.startswith(TPL):
            raw = io.open(src, encoding="utf-8", errors="replace", newline="").read()
            io.open(dst, "w", encoding="utf-8", newline="").write(
                raw.replace("__NSCRIPTS__", str(n_scripts))
                   .replace("__NFILES__", str(n_files)))
            continue

        # newline='' 两头都写：读的时候不把 CRLF 归一成 LF，写的时候也不再转一次。
        # 少了这一对，包里每个 md 的换行都会被悄悄换掉（今天已经踩过一次）。
        raw = io.open(src, encoding="utf-8", errors="replace", newline="").read()
        new, hits = desensitize(raw, rel)
        if hits:
            touched += 1
            total_hits += hits
        io.open(dst, "w", encoding="utf-8", newline="").write(new)

    print("已写入 %d 个文件 → %s" % (len(plan), out))
    print("脱敏：%d 个文件、%d 处替换（源文件未动）" % (touched, total_hits))


def _write_manifest(out, plan):
    # ── 文件清单：版本自报 ＋ 每个文件的 sha256（2026-11-02，G-187②）──────
    # 为什么必须有：包内原先**没有任何文件说自己是哪一版**。版本号只活在 zip 名和
    #   几份文档里，用户手上有两个包、名字记混了就答不出「我装的是哪个」。
    # 一次解决三件事：
    #   ① 版本可查（第一行就是包名）
    #   ② 核「漏装」：清单有、盘上没有 → 解压不完整
    #   ③ 核「残留」：盘上有、清单没有 → 上一版删掉的文件还赖在原地，
    #      而解压只增不删，它会继续被 _gate 扫到，报出「明明删了还在报红」的鬼
    # 清单**不列它自己**（否则算 hash 要递归），表头写明这一点，免得人对数对不上。
    import hashlib
    man = []
    for src, rel in sorted(plan, key=lambda x: x[1]):
        dst = os.path.join(out, rel)
        try:
            with io.open(dst, "rb") as f:
                man.append("%s  %s" % (hashlib.sha256(f.read()).hexdigest()[:16], rel))
        except OSError as e:
            print("✗ 清单算不出 %s 的 hash（%s）" % (rel, e))
            return 1
    head = [
        "%s · 文件清单" % PKG_NAME,
        "",
        "用途三个，别只当装饰：",
        "  ① 确认装的是哪一版——本文件第一行就是版本",
        "  ② 核「漏装」：清单里有、你的盘上没有 → 解压不完整，重新解压",
        "  ③ 核「残留」：你的盘上有、清单里没有 → 那是上一版删掉的文件，"
        "解压只增不删，它会继续被门禁扫到",
        "",
        "格式：sha256 前 16 位 ＋ 两个空格 ＋ 相对包根的路径",
        "共 %d 个文件（本清单自身不计入，否则算 hash 要递归）" % len(man),
        "",
    ]
    man_path = os.path.join(out, "文件清单.txt")
    io.open(man_path, "w", encoding="utf-8", newline="").write(
        "\n".join(head + man) + "\n")
    print("文件清单 → 文件清单.txt（%d 条 sha256，版本 %s）" % (len(man), PKG_NAME))


def _compile_package(out):
    # ── 硬闸 0：包里的脚本必须能编译 ──────────────────────────────
    # 2026-11-02（G-147）：外部实测在包里跑 `_selftest.py`，直接 SyntaxError——
    # 脱敏那三条「清空专名表」的规则当时按内容匹配、不分文件，把一条**测试夹具**
    # 的字符串拦腰换成多行注释，字符串就此没闭合。
    # 而 `_verify_package` 的 V4 只找输出里的「Traceback」——**语法错不打印 Traceback**，
    # 于是「21 个脚本全跑通」和「根本没编译过」在它眼里长得一样，它还报了绿。
    # 编译是确定的：过就是过，没有解释空间。**打完先编译一遍，不过就不许发。**
    py_dir = os.path.join(out, "00_原著")
    py_list = sorted(f for f in os.listdir(py_dir)
                     if f.startswith("_") and f.endswith(".py")) if os.path.isdir(py_dir) else []
    broken = []
    for fn in py_list:
        try:
            compile(io.open(os.path.join(py_dir, fn), encoding="utf-8").read(), fn, "exec")
        except SyntaxError as e:
            broken.append((fn, "%s（第 %s 行）" % (e.msg, e.lineno)))
    if broken:
        print("\n✗ 包里有 %d 个脚本编译不过 —— **这包不能发**：" % len(broken))
        for fn, why in broken:
            print("   %s：%s" % (fn, why))
        print("   多半是脱敏改坏了代码（字符串被截断／缩进被改）。改规则，别改包。")
        return 1
    print("✅ 包内 %d 个脚本全部编译通过" % len(py_list))
    print("")


def _verify_output(out):
    # ── 硬闸 1：正文原句残留 ──
    # V3 查的是专名（名字），查不到「整句原话」。这两件事不一样：
    # 一句原文可以不含任何名字，V3 一律放行。2026-11-02 首测 V3 全绿，
    # 实测却有 14 处、294 字命中原文——**绿的是它查的那一项，不是整件事**。
    qs = os.path.join(HERE, "_quote_scan.py")
    if os.path.isfile(qs):
        print()
        r = subprocess.run([sys.executable, qs, out])
        if r.returncode != 0:
            print()
            print("✗ 正文残留超限或没真扫到文件，正在删除输出目录")
            shutil.rmtree(out, ignore_errors=True)
            return 1
    else:
        print("⚠ 没找到 packaging/_quote_scan.py，**这次打包不检查正文残留**")

    # ── 硬闸 2：验不过就删 ──
    verify = os.path.join(HERE, "_verify_package.py")
    if not os.path.isfile(verify):
        print("⚠ 没找到 packaging/_verify_package.py，跳过验包——**这次打包不可信**")
        return 1

    r = subprocess.run([sys.executable, verify, out])
    if r.returncode != 0:
        print()
        print("✗ 验包没过，正在删除输出目录（防止半成品被发出去）")
        shutil.rmtree(out, ignore_errors=True)
        return 1


def _make_zip(out, do_zip):
    if do_zip:
        # ── 硬闸：包名对账（G-179）。打之前先看目录名，别等写完了才发现 ──
        out_name = os.path.basename(out.rstrip("/\\"))
        if out_name != PKG_NAME:
            print("✗ 输出目录名不对：%s" % out_name)
            print("  最后一级目录名必须是 %s ——它就是 zip 的顶层目录，用户解压后看到的就是它。" % PKG_NAME)
            print("  文档（%s）通篇按这个名字指路，对不上，人只会结论「包是坏的」。" % PKG_ENTRY_TXT)
            print("  换个输出目录：--out .../%s" % PKG_NAME)
            # 和「验包没过就删」同一条规矩：一个连名字都不对的产物，不许留在磁盘上等人手滑发出去。
            shutil.rmtree(out, ignore_errors=True)
            return 1
        zpath = out.rstrip("/\\") + ".zip"
        top, nfiles, ndirs = _write_zip(out, zpath)
        # **自检：文档承诺的目录必须在 zip 里。** 这条是补上「zip 丢空目录」那个洞的守门人——
        # 没有它，同类问题下次换个目录名还会重演，而人只会在解压时才发现。
        import zipfile as _zf
        with _zf.ZipFile(zpath) as _z:
            names = _z.namelist()
            miss = [d for d in MUST_DIRS
                    if not any(n.startswith(top + "/" + d + "/") for n in names)]
            if miss:
                print("✗ zip 里缺目录 %s（文档承诺过它们必须在）" % miss)
                _discard(zpath)
                return 1
            # ── 硬闸的同一条另一半：包内入口文档写的名字，也得是这个包名 ──
            # 只查 zip 顶层不够：版本号改了、目录名跟着改、文档忘了改，顶层照样绿。
            entry = [n for n in names if n == top + "/" + PKG_ENTRY_TXT]
            if not entry:
                print("✗ zip 里没有 %s" % PKG_ENTRY_TXT)
                _discard(zpath)
                return 1
            entry_txt = _z.read(entry[0]).decode("utf-8-sig")
            if PKG_NAME not in entry_txt:
                print("✗ %s 正文里没有出现包名 %s" % (PKG_ENTRY_TXT, PKG_NAME))
                print("  改版本号时这两处必须同一次改——顶层名对了、文档还写着旧名字，")
                print("  用户按文档找不到东西，一样是「包坏了」。")
                _discard(zpath)
                return 1
        print("已打 zip → %s（%.1f MB，%d 个文件 ＋ %d 个目录条目，包名 %s）"
              % (zpath, os.path.getsize(zpath) / 1e6, nfiles, ndirs, PKG_NAME))


def main():
    preflight_rc = _preflight()
    if preflight_rc is not None:
        return preflight_rc

    dry, do_zip, out = _parse_args(sys.argv[1:])

    plan, skipped = collect(dry)
    _build_labels(plan)

    plan_rc = _check_plan(plan, skipped, dry, out)
    if plan_rc is not None:
        return plan_rc

    os.makedirs(out, exist_ok=True)

    _write_files(out, plan)

    manifest_rc = _write_manifest(out, plan)
    if manifest_rc is not None:
        return manifest_rc

    compile_rc = _compile_package(out)
    if compile_rc is not None:
        return compile_rc

    verify_rc = _verify_output(out)
    if verify_rc is not None:
        return verify_rc

    zip_rc = _make_zip(out, do_zip)
    if zip_rc is not None:
        return zip_rc

    return 0


def _discard(path):
    """删掉一个不该留在磁盘上的产物。

    删不掉也**不许假装删掉了**：这台机器上 `os.remove` 被套了回收站钩子，删失败会抛
    OSError，把前面那条真正有用的报错整段冲掉（2026-11-02 实测，G-179 反向测试时撞到）。
    所以这里只报警、不抛——让「为什么拒打」那句话永远是最后一句人话。
    """
    try:
        os.remove(path)
    except OSError as e:
        print("  ⚠ 自动删除失败（%s）：请手动删掉 %s，别让它留在磁盘上被当成成品发出去。"
              % (e.__class__.__name__, path))


def _write_zip(out, zpath):
    """打 zip。两个细节都是给「双击解压的人」准备的，不是给开发者：

    ① **外面套一层同名目录**。原来是把包内容直接铺在 zip 根上——
       用户双击解压到桌面，74 个文件当场铺满一屏，`使用说明.txt` 夹在中间。
    ② **`使用说明.txt` 排第一个**。zip 的条目顺序就是资源管理器的显示顺序，
       排在第一位，人才会先读它再动手。其余按层级排（根目录的在前）。

    这两条都不影响 `_verify_package` 的判定（它验的是解压出来的目录，不是 zip 内部顺序），
    但它们决定「一个不懂技术的人打开压缩包的第一眼看到什么」。
    """
    top = os.path.basename(out.rstrip("/\\"))
    if top != PKG_NAME:
        # main() 已经查过一遍；这里再查，是因为这个函数将来可能被别的入口调，
        # 而「顶层名跟着输出目录走」这件事本身就该在这一层被拦住，不该指望调用方。（G-179）
        raise SystemExit("✗ 顶层目录名 %r ≠ PKG_NAME %r：包名跟着输出目录跑了（见 G-179）"
                         % (top, PKG_NAME))
    files = []
    for dirpath, _, filenames in os.walk(out):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, out).replace("\\", "/")
            files.append((rel, full))
    # zip 条目顺序＝资源管理器里的显示顺序。入口那份必须第一。
    # 但**不能只靠这个**：解压后资源管理器按名字重排，中文按拼音，
    # `安装.md`（an）会跑到 `从这里开始`（cong）前面——所以 §零 那段三步
    # 在 `安装.md` 第一屏也必须能看见，两边都许第一（见 G-160）。
    _head = {"从这里开始.txt": 0, "使用说明.txt": 1}
    files.sort(key=lambda r: (_head.get(r[0], 2), r[0].count("/"), r[0]))

    # **空目录也要写进去**（2026-11-02，G-140）。原来只写文件，`99_过程稿/` 是空目录，
    # 于是 zip 里没有它——用户解压后找不到文档承诺的那个目录，判定「包不完整」。
    # 它是对的：**zip 只存文件，空目录会被静默丢掉**，而文档写着「应该看到这几个文件夹」。
    have = set(rel for rel, _ in files)
    empty_dirs = []
    for dirpath, dirnames, _ in os.walk(out):
        for d in dirnames:
            rel = os.path.relpath(os.path.join(dirpath, d), out).replace("\\", "/")
            if not any(h.startswith(rel + "/") for h in have):
                empty_dirs.append(rel)

    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, full in files:
            z.write(full, top + "/" + rel)
        for d in sorted(empty_dirs):
            zi = zipfile.ZipInfo(top + "/" + d + "/")
            zi.external_attr = (0o40755 << 16) | 0x10      # 目录位，解压器才当目录
            z.writestr(zi, "")
    return top, len(files), len(empty_dirs)
    return top, len(files), len(empty_dirs)


if __name__ == "__main__":
    sys.exit(main())
