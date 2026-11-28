#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_verify_package.py — 验一个包能不能发出去。

用法：python packaging/_verify_package.py <包目录>
退出码：0 全过 ／ 1 有阻断 ／ 2 只有提示。
验包项详见 docs/maintain/验包十三项.md（文件名沿用，现十四项）。
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

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

# ── V1 必需文件 ──────────────────────────────────────────────
REQUIRED = [
    # 人读入口必须卡在这个清单里：缺了它，用户又得自己猜先读哪份。
    # 清单本身也会漏登，漏登就等于没人管。
    ("从这里开始.txt", "人读入口第一份。三步、两分钟——缺了它，用户又得自己猜先读哪份"),
    ("使用说明.txt", "装完怎么用。缺了它，装完之后没人告诉他怎么上手"),
    ("README.md", "第一屏。没有它，用户打开看不到从哪下手"),
    ("版权与开源红线.md", "红线原则（空白模板）"),
    ("发布前检查清单.md", "发布前动作清单（空白模板）"),
    ("Agent框架/README.md", "规范的导航"),
    ("Agent框架/[台账]跟进通道.md", "跟进通道。门禁的「修不动就写进通道」指的是这个文件——"
                                   "缺了它，那句提示就是死链接"),
    ("00_原著/_gate.py", "门禁汇总。没有它整套检查跑不起来"),
    ("00_原著/_redline.py", "红线检查"),
    ("00_原著/[台账]常量台账_v1.md", "常量台账（空白模板）"),
    (".gitignore", "媒体与备份排除规则。没有它用户第一次 git add 会把图和备份全加进去"),
]

# ── V2 禁入：文件名命中即拦 ───────────────────────────────────
FORBIDDEN_PATTERNS = [
    (r"定稿_v\d+\.txt$", "正文定稿"),
    (r"^\[中间稿\]", "中间稿"),
    (r"^\[草稿\]", "草稿"),
    (r"^\[勘误\]", "勘误台账"),
    (r"^\[标注\]", "标注件"),
    (r"^\[审校\]", "审校件"),
    (r"^\[清单\]", "项目清单"),
    (r"^\[台账\]抽卡记录", "抽卡记录（含成本与项目数据）"),
    (r"\.bak_", "备份文件"),
    (r"__NSCRIPTS__", "占位符没填（打包时漏了替换，读起来像乱码）"),
    (r"\.pyc$", "字节码缓存"),
    # 2026-11-02 加：视图是**跑出来的生成物**，不是内容。它出现在包里只有一种解释——
    # 这个包被人跑过了。而「跑过」意味着包里的东西已经不是验的那一份了。
    (r"^\[视图\]", "生成物（视图）——包被跑过的证据"),
]

# ── V5 凭据 ─────────────────────────────────────────────────
# ⚠ 正则写成拼接，不要在源码里落完整形态——
#   否则这个脚本扫包时会扫到它自己（`_selftest` 2026-11-01 当场踩过）
CRED_RE = re.compile(r"https?://[^\s/:@]+:" + r"[0-9a-f]{20,}" + r"@")

TEXT_EXT = (".md", ".py", ".txt", ".json", ".yml", ".yaml", ".sh", ".html")


def load_project_nouns():
    """词表来自 `packaging/_nounlist.py`（专名表 ＋ 台账 ＋ 补充词三源合一）。
    读不到就报错——不许静默跳过这一项。

    2026-11-02 换源，原因很具体：原来只读 `_collab.py` 的 14 个词，
    某个组织名、某个角色别名两边都没登记，V3 全绿照样漏。
    **查得少，比查不了更危险——因为它会显示「通过」。**
    """
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    try:
        import _nounlist
    except ImportError as e:
        return None, "导不进 packaging/_nounlist.py（%s）" % e
    try:
        auto, fixed = _nounlist.load()
    except Exception as e:
        return None, "读词表出错（%s）" % e
    nouns = list(auto) + list(fixed)
    if not nouns:
        return None, "词表为空（三个来源都没读到）"
    return nouns, None


def check_v0(root, fails, warns):
    # ── V0 覆盖：先确认真的扫到东西 ──
    # 2026-11-02 血的教训：`_quote_scan` 第一次跑报「0 处残留」，实际 30 处。
    # 原因是目标路径写成 /tmp/...，Git Bash 与 Python 解析成不同位置，
    # 而 os.walk 对不存在的目录**不报错、返回空列表**——「一个文件没扫」
    # 被说成了「没有残留」。**零覆盖假绿，比假红难查得多。**
    print("\nV0 覆盖")
    n_all = sum(len(fs) for _, _, fs in os.walk(root))
    if n_all >= 60:
            print("  ✅ 目录内 %d 个文件，够扫" % n_all)
    else:
            print("  ✗ 目录内只有 %d 个文件（应 ≥60）" % n_all)
            fails.append("V0 只扫到 %d 个文件——路径大概率错了，不是包干净" % n_all)

    return fails, warns



def check_v1(root, fails, warns):
    # ── V1 必需文件 ──
    print("\nV1 必需文件")
    # 人读入口额外卡一条：**存在但内容是空的/半截的，比不存在更糟**——
    # 用户会以为「就这些」，然后自己猜。模板漏贴、编码写挂、写一半存盘，都长这样。
    MIN_BYTES = {"使用说明.txt": 2000}
    for rel, why in REQUIRED:
            p = os.path.join(root, rel.replace("/", os.sep))
            if os.path.isfile(p):
                floor = MIN_BYTES.get(rel)
                size = os.path.getsize(p)
                if floor and size < floor:
                    print("  ✗ %s 只有 %d 字节（应 ≥%d）—— 像是空壳或写了一半" % (rel, size, floor))
                    fails.append("V1 %s 内容过短（%d 字节）" % (rel, size))
                    continue
                print("  ✅ %s" % rel)
            else:
                print("  ✗ 缺 %s —— %s" % (rel, why))
                fails.append("V1 缺 %s（%s）" % (rel, why))

    return fails, warns



def check_v6(root, fails, warns):
    # ── V6 目录结构（先查，V4 要用）──
    print("\nV6 目录结构")
    for d in ["Agent框架", "00_原著", "99_过程稿", "skills"]:
            p = os.path.join(root, d)
            if os.path.isdir(p):
                print("  ✅ %s/" % d)
            else:
                print("  ✗ 缺 %s/ —— 脚本靠「父目录的父目录＝项目根」定位，结构不对就集体推错" % d)
                fails.append("V6 缺目录 %s/" % d)
    # 脚本必须在 00_原著/ 下，这条是硬约束（11_分发说明 §二）
    py_in_root = [f for f in os.listdir(root) if f.startswith("_") and f.endswith(".py")]
    if py_in_root:
            print("  ✗ 包根有脚本 %s —— 它们必须在 00_原著/ 下，否则算出的项目根会高一层"
                  % py_in_root[:3])
            fails.append("V6 脚本跑到了包根")

    return fails, warns



def check_v2(root, fails, warns, all_files):
    # ── V2 禁入文件 ──
    print("\nV2 禁入文件")
    bad = []
    for full in all_files:
            rel = os.path.relpath(full, root).replace("\\", "/")
            base = os.path.basename(full)
            for pat, why in FORBIDDEN_PATTERNS:
                if re.search(pat, base) or re.search(pat, rel):
                    bad.append((rel, why))
                    break
            else:
                if any(p.startswith(".") for p in rel.split("/")[:-1]):
                    bad.append((rel, "内部过程记录"))
    if bad:
            for rel, why in bad:
                print("  ✗ %s —— %s" % (rel, why))
                fails.append("V2 禁入 %s（%s）" % (rel, why))
    else:
            print("  ✅ %d 个文件里没有正文／过程稿／备份／缓存" % len(all_files))

    return fails, warns



def check_v3(root, fails, warns, all_files, nouns, noun_err):
    # ── V3 专名 ──
    print("\nV3 项目专名")
    if noun_err:
            print("  ✗ %s —— 这一项没查成，不许当通过" % noun_err)
            fails.append("V3 查不了（%s）" % noun_err)
    else:
            print("  [scope] 词表来自 packaging/_nounlist.py：专名表 ＋ 专名台账 ＋ 补充词，%d 个词"
                  % len(nouns))
            hits = []
            for full in all_files:
                if not full.endswith(TEXT_EXT):
                    continue
                rel = os.path.relpath(full, root).replace("\\", "/")
                try:
                    txt = open(full, encoding="utf-8").read()
                except (UnicodeDecodeError, OSError):
                    continue
                for n in nouns:
                    if n in txt:
                        hits.append((rel, n, txt.count(n)))
            if hits:
                for rel, n, c in hits[:20]:
                    print("  ✗ %s —— 含「%s」×%d" % (rel, n, c))
                if len(hits) > 20:
                    print("  …… 还有 %d 处" % (len(hits) - 20))
                fails.append("V3 专名泄漏 %d 处" % len(hits))
            else:
                print("  ✅ 全部文本文件里没出现项目专名")

    return fails, warns



def _v4a_compile(scripts, root, fails):
    print("\nV4a 脚本能编译（%d 个）" % len(scripts))
    uncompiled = []
    for script in scripts:
        src_path = os.path.join(root, "00_原著", script)
        try:
            with open(src_path, encoding="utf-8") as f:
                compile(f.read(), script, "exec")
        except SyntaxError as e:
            uncompiled.append((script, "%s（第 %s 行）" % (e.msg, e.lineno)))
        except OSError as e:
            uncompiled.append((script, str(e)))
    for script, why in uncompiled:
        print("  ✗ %s：%s" % (script, why))
        fails.append("V4a %s 编译不过（%s）" % (script, why))
    if not uncompiled:
        print("  ✅ %d 个全部编译通过" % len(scripts))


def _v4_run(scripts, run_root, fails):
    print("\nV4 脚本能跑（包里 %d 个全跑；判的只是「不崩」，不是「判得对」）" % len(scripts))
    print("  [scope] 在临时副本里跑，不在真件上跑——`_mkview`／`_board` 会写 [视图]*.html，"
          "跑在真件上等于往待发的包里塞两个没验过的文件")
    crashed, ok = [], 0
    for script in scripts:
        p = os.path.join(run_root, "00_原著", script)
        try:
            r = subprocess.run([sys.executable, p], cwd=run_root,
                               capture_output=True, text=True, timeout=180,
                               encoding="utf-8", errors="replace")
            out = (r.stdout or "") + (r.stderr or "")
            if "Traceback" in out:
                last = [ln for ln in out.strip().splitlines() if ln.strip()][-1][:90]
                print("  ✗ %-22s 抛异常：%s" % (script, last))
                crashed.append(script)
            else:
                ok += 1
        except subprocess.TimeoutExpired:
            print("  ✗ %-22s 跑超时" % script)
            crashed.append(script)
        except Exception as e:                      # noqa: BLE001
            print("  ✗ %-22s 起不来：%s" % (script, e))
            crashed.append(script)
    if crashed:
        fails.append("V4 %d 个脚本崩溃：%s" % (len(crashed), "／".join(crashed[:5])))
    else:
        print("  ✅ %d 个脚本全部跑通（没有 Traceback 就是没崩；报错是预期内的——"
              "包是空项目，它们当然找不到项目文件）" % ok)


def check_v4(root, fails, warns):
    # G-147 等完整来历见 docs/maintain/验包十三项.md（维护仓，不随包）。
    py_dir = os.path.join(root, "00_原著")
    scripts = sorted(f for f in os.listdir(py_dir)
                     if f.startswith("_") and f.endswith(".py")) if os.path.isdir(py_dir) else []
    sandbox = None
    run_root = root
    if scripts:
        sandbox = tempfile.mkdtemp(prefix="verifypkg_")
        run_root = os.path.join(sandbox, "pkg")
        shutil.copytree(root, run_root)
    _v4a_compile(scripts, root, fails)
    _v4_run(scripts, run_root, fails)
    if sandbox:
        shutil.rmtree(sandbox, ignore_errors=True)
    return fails, warns


def check_v5(root, fails, warns, all_files):
    # ── V5 凭据 ──
    print("\nV5 凭据")
    leaks = []
    for full in all_files:
            if not full.endswith(TEXT_EXT):
                continue
            rel = os.path.relpath(full, root).replace("\\", "/")
            try:
                txt = open(full, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            for m in CRED_RE.finditer(txt):
                raw = m.group(0)
                leaks.append((rel, raw[:raw.index(":") + 1] + "***"))
    if leaks:
            for rel, masked in leaks:
                print("  ✗ %s —— %s" % (rel, masked))
            fails.append("V5 凭据泄漏 %d 处" % len(leaks))
    else:
            print("  ✅ 没有 URL 内嵌凭据")

    return fails, warns



def check_v7(root, fails, warns):
    # ── V7 免责声明 ──
    # 原文照录，一个字都不许改。改措辞会带来两类后果：
    # 「交流学习」被写成「免费使用」；「咨询版权方」这个前置条件被漏掉。
    print("\nV7 免责声明（三处入口）")
    KEY = "严禁对任何已发布的版权作品使用"
    miss = []
    for rel in ("使用说明.txt", "README.md", "版权与开源红线.md"):
            p = os.path.join(root, rel)
            if not os.path.isfile(p):
                miss.append("%s（文件不在）" % rel)
                continue
            try:
                txt = open(p, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                miss.append("%s（读不了）" % rel)
                continue
            if KEY in txt:
                print("  ✅ %s" % rel)
            else:
                print("  ✗ %s —— 没有免责声明原文" % rel)
                miss.append(rel)
    if miss:
            fails.append("V7 免责声明缺失：%s" % "／".join(miss))
    print("  [scope] 查不了：这句话有没有真的贴到用户眼前（那只发生在对话里）")

    return fails, warns



def check_v8(root, fails, warns):
    # ── V8 文档没有整段连贴两遍 ──
    # 判据和实现只在 `packaging/_dupcheck.py` 里一份，这里只调它（2026-11-02，G-151）。
    # 上一版 V8 是内联在本文件里的，于是「打包时跑一次」和「人手工扫一次」会是两套代码——
    # 正是本项目一直在防的「副本必漂」。外部实测还指出：V8 只活在打包脚本里、
    # 检查清单里搜不到，**一个只有写它的人会用的检查，等于不存在**。
    print("\nV8 文档没有整段连贴两遍（判据在 packaging/_dupcheck.py）")
    here8 = os.path.dirname(os.path.abspath(__file__))
    if here8 not in sys.path:
            sys.path.insert(0, here8)
    try:
            import _dupcheck
            dups = _dupcheck.scan(root)
    except Exception as e:                          # noqa: BLE001
            print("  ✗ 跑不了重复检测（%s）——**这一项没查，不算通过**" % e)
            fails.append("V8 起不来（%s）" % e)
            dups = None
    if dups:
            for rel, ln, k, head in dups:
                print("  ✗ %s:%d 起，%d 行紧接着又出现一遍 —— %s" % (rel, ln, k, head))
                fails.append("V8 %s:%d 整段连贴两遍" % (rel, ln))
    elif dups is not None:
            print("  ✅ 没有整段重复")

    return fails, warns



def check_v9(root, fails, warns, all_files):
    # ── V9 版本号全包一致（2026-11-04，G-295）──
    # 原先版本号只有两处硬闸：zip 顶层目录名、`从这里开始.txt` 正文（都在 `_pack.py`）。
    # 包内 `使用说明.txt` 也写着包版本；升版只改 PKG_NAME 与入口时，这里会留下旧号。
    # 后果很具体：闸全绿，用户却照正文去找一个不存在的版本。这和 `G-179` 是同一个病，
    # 区别只是那次翻车的是目录名，这次会翻在文档正文里。
    #
    # 判据只认「包名形式」与「**包**版本 vX」，**不认裸的 `v0.1`**：
    # `框架README.md` 里有 `09_E4到E6_首帧组装契约_v0.1.md`，那个 v0.1 是文件版本后缀、
    # 不是包版本。判据写粗了就会误报，误报的代价是人开始给闸加白名单——闸就废了。
    #
    # 2026-11-05 收窄（这条注释预言的场景真的发生了）：原判据是 `版本\s*v(\d+\.\d+)`，
    # 于是「**当前版本 v2.2**」这种「文件自己的版本」全被当成包版本判红。
    # 加它的人正是同一天立的四·补二十五——**一条讲「一个 vX.Y 必须能分辨是谁的版本」的通则，
    # 在落地当天就撞出了它没覆盖的第四种意思：包的版本。**
    # 现在只认明确指包的三类写法：包名形式／`包版本 vX`／`本包 vX`。
    # 文件自己的版本（`当前版本 vX`）与条目版本（`xxx_v0.1.md`）一律不判。
    print("\nV9 版本号全包一致")
    root_base = os.path.basename(os.path.abspath(root))
    m_ver = re.search(r"_v(\d+\.\d+)$", root_base)
    if not m_ver:
            print("  ⚠ 包名 %r 里没有 `_vX.Y` 后缀，跳过（读不出「应该是什么版本」就不能判）"
                  % root_base)
            warns.append("包名没有版本后缀，V9 未执行")
    else:
            want_ver = m_ver.group(1)
            ver_pats = [
                (re.compile(r"AI创作工作流_v(\d+\.\d+)"), "包名形式"),
                (re.compile(r"包版本\s*v(\d+\.\d+)"), "包版本行"),
                (re.compile(r"本包\s*v(\d+\.\d+)"), "本包行"),
            ]
            mism = []
            for full in all_files:
                if not full.lower().endswith((".md", ".txt")):
                    continue
                rel = os.path.relpath(full, root).replace("\\", "/")
                try:
                    with open(full, encoding="utf-8-sig", errors="replace") as f:
                        txt = f.read()
                except OSError:
                    continue
                for pat, why in ver_pats:
                    for got in set(pat.findall(txt)):
                        if got != want_ver:
                            mism.append((rel, why, got))
            if mism:
                for rel, why, got in sorted(set(mism)):
                    print("  ✗ %s —— %s 写着 v%s，包是 v%s" % (rel, why, got, want_ver))
                    fails.append("V9 %s 版本号 v%s ≠ v%s（%s）" % (rel, got, want_ver, why))
                print("     升版要一次改全：PKG_NAME（`_pack.py`）／`从这里开始.txt`／"
                      "`使用说明.txt`。少改一处，用户就会按旧名字找一个不存在的文件。")
            else:
                print("  ✅ 包名形式与版本行全部 = v%s（%d 个文本文件里没有旧版本号）"
                      % (want_ver, len(all_files)))

    return fails, warns



def check_v10(root, fails, warns):
    # ── V10 包内框架件全是通用层（2026-11-04，`G-296`）──
    #
    # 这是「层声明是唯一真相源」的**出货前最后一道闸**，故意独立于 `_pack.py`。
    #
    # 为什么要独立：`_pack.py` 现在按声明决定去留，但它自己也可能被改坏。而这件事
    # 的失败方式是**不可逆的**——项目内容一旦发出去就收不回来。所以不能只靠一条链路：
    # 打包按声明筛，验包再按声明查一遍，两边都过才算数。
    #
    # 查三件事，每件都能单独致命：
    #   ① 包里有没有漏带进来的项目层文件（声明是项目层，却出现在包内）
    #   ② 包里每个框架件**必须有**层声明（没声明＝没人想过它属于哪层，不该发）
    #   ③ 声明必须是「通用层」（还写着已取消的「混合」＝老档位，要二选一）
    print("\nV10 包内框架件全是通用层")
    lay_re = re.compile(r"^>\s*\*\*层\*\*\s*[：:]\s*\*{0,2}(通用层|项目层|混合)")
    frame_dir = os.path.join(root, "Agent框架")
    # 允许「声明项目层、但包里必须有」的极少数例外。**逐条列名，不许通配**——
    # 通配等于把一整类放开，而这一整类正是最该被拦住的那一类。
    V10_EXEMPT = {
            "Agent框架/[台账]跟进通道.md":
                "包内是空白模板（`templates/跟进通道.md`）。台账这一件**永远是项目层**，"
                "但门禁那句「修不动就写进通道」指的就是它，包里没有它，那句话就是死链接"
                "（`G-140` 实测过）。",
    }
    if not os.path.isdir(frame_dir):
            fails.append("V10 包里没有 Agent框架/ 目录")
            print("  ✗ 包里没有 Agent框架/")
    else:
            bad, exempt = [], []
            n_ok = 0
            for fn in sorted(os.listdir(frame_dir)):
                if not fn.endswith(".md"):
                    continue
                fp = os.path.join(frame_dir, fn)
                try:
                    with open(fp, encoding="utf-8-sig", errors="replace") as f:
                        head = f.read().split("\n")[:24]
                except OSError:
                    continue
                lay = None
                for ln in head:
                    m = lay_re.search(ln)
                    if m:
                        lay = m.group(1)
                        break
                if lay == "通用层":
                    n_ok += 1
                elif lay is None:
                    bad.append((fn, "没写层声明"))
                elif lay == "混合":
                    bad.append((fn, "用的是已取消的「混合」档"))
                elif ("Agent框架/" + fn) in V10_EXEMPT:
                    exempt.append((fn, V10_EXEMPT["Agent框架/" + fn]))
                else:
                    bad.append((fn, "声明是项目层——它不该在包里"))
            if bad:
                for fn, why in bad:
                    print("  ✗ Agent框架/%s —— %s" % (fn, why))
                    fails.append("V10 Agent框架/%s %s" % (fn, why))
                print("     包里的每一份框架件都必须能整份搬走。项目层的东西不进包，")
                print("     混合层那一档已经取消（它等于给项目内容开正式出口）。")
            else:
                print("  ✅ Agent框架/ 下 %d 份 md 全部声明为通用层" % n_ok)
            for fn, why in exempt:
                print("  ◻ 豁免：Agent框架/%s（声明项目层，包里必须留着）" % fn)
                print("       %s" % why)

    return fails, warns



def _v11_patterns():
    exempt = [
        ("从这里开始.txt", "没问题，往下走", "正文里的**示范路径**：告诉用户「正常的路径长这样」"),
        ("从这里开始.txt", "请重新解压到", "**反面示例**：告诉用户「你装到临时目录了，重来」"),
    ]
    user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    # 盘符后必须有真字符，避免把正则字面量误判成路径。
    pats = [
        (re.compile(r"(?<![A-Za-z0-9+.\-])[A-Za-z]:[\\/][A-Za-z0-9_\u4e00-\u9fff.~]"),
         "盘符绝对路径"),
        (re.compile(r"AppData[\\/]|[\\/]AppData"), "AppData 路径"),
        (re.compile(r"Temp[\\/][A-Za-z]|[\\/]Temp[\\/]"), "Temp 路径"),
    ]
    if len(user) >= 3:
        pats.append((re.compile(r"[\\/]" + re.escape(user) + r"[\\/]", re.I), "本机用户名"))
    return pats, exempt


def _v11_scan(root, pats, exempt):
    ext = (".md", ".txt", ".py", ".html", ".json", ".yml", ".yaml", ".sh", ".js", ".css")
    coord, bare, n_scan, exempted = [], [], 0, []
    for dp, dn, fns in os.walk(root):
        dn[:] = [d for d in dn if d != ".git"]
        for fn in fns:
            if not fn.lower().endswith(ext):
                continue
            fp = os.path.join(dp, fn)
            rel = os.path.relpath(fp, root).replace(os.sep, "/")
            try:
                txt = open(fp, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            n_scan += 1
            for i, line in enumerate(txt.splitlines(), 1):
                if "[坐标-ok]" in line:
                    continue
                hit = next(((pat, why) for pat, why in pats if pat.search(line)), None)
                if not hit:
                    if re.search(r"AppData|Temp", line):
                        bare.append((rel, i))
                    continue
                skip = next((w for b, needle, w in exempt
                             if rel.endswith(b) and needle in line), None)
                if skip:
                    exempted.append((rel, i, skip))
                    continue
                coord.append((rel, i, hit[1], line.strip()[:70]))
    return coord, bare, n_scan, exempted


def _v11_report(coord, bare, n_scan, exempted, fails, warns):
    if coord:
        for rel, i, why, snip in coord[:12]:
            print("  ✗ %s:%d（%s）  %s" % (rel, i, why, snip))
        if len(coord) > 12:
            print("     …… 另 %d 处" % (len(coord) - 12))
        fails.append("V11 包里有 %d 处本机坐标（%s）"
                     % (len(coord), "／".join(sorted({h[2] for h in coord}))))
    else:
        print("  ✅ 扫 %d 个文本文件，0 处可解析为本机路径的坐标" % n_scan)
    for rel, i, w in exempted:
        print("  ◻ 豁免：%s:%d —— %s" % (rel, i, w))
    if bare:
        warns.append("V11 有 %d 行提到 AppData／Temp 但不是路径形态（多半是说明书里的警示语，正常；"
                     "只提不拦——判据是「坐标换台机器成不成立」，不是「有没有提这个词」）" % len(bare))


def check_v11(root, fails, warns):
    # G-300/G-302 的完整来历见 docs/maintain/验包十三项.md（维护仓，不随包）。
    print("\nV11 包里没有「这台机器的坐标」")
    pats, exempt = _v11_patterns()
    coord, bare, n_scan, exempted = _v11_scan(root, pats, exempt)
    _v11_report(coord, bare, n_scan, exempted, fails, warns)
    return fails, warns


def check_v12(root, fails, warns):
    # ── V12 人读入口不挂「台账编号」（2026-11-05，`G-303`）──
    # 为什么要有：旧安装入口一度挂着 9 处 `G-xxx`，而**包里那份台账只有一行 `G-01`**。
    # 收包人读到「（2026-11-02 实测，G-157）」，翻台账翻不到，只会得出一个结论：
    # 这个包少给我一份东西。**指向不存在的东西，比不写更坏。**
    #
    # 为什么只查入口、不查全部：规范正文里出现 `G-xx` 多为**教学**——
    # 术语表要拿它当示例（「通道条目号，如 `G-61`」）、反例本身要引用一个号才讲得清。
    # 那些是内容，删了讲不明白。入口页里出现编号则是另一回事：一律是当溯源证据挂的，
    # 而读者手里没有那份台账。**同一个符号，在不同位置承担的功能不一样。**
    print("\nV12 人读入口不挂「台账编号」")
    ENTRIES = ("从这里开始.txt", "使用说明.txt", "README.md",
                   "版权与开源红线.md", "发布前检查清单.md", "Agent框架/README.md")
    GRE = re.compile(r"G-\d{1,3}")
    ent_hits, ent_scan = [], 0
    for rel in ENTRIES:
            fp = os.path.join(root, rel.replace("/", os.sep))
            if not os.path.isfile(fp):
                continue
            try:
                txt = open(fp, encoding="utf-8-sig", errors="replace").read()
            except OSError:
                continue
            ent_scan += 1
            for i, line in enumerate(txt.splitlines(), 1):
                if "[编号-ok]" in line:
                    continue
                for m in GRE.finditer(line):
                    ent_hits.append((rel, i, m.group()))
    if ent_hits:
            for rel, i, g in ent_hits[:10]:
                print("  ✗ %s:%d → %s" % (rel, i, g))
            if len(ent_hits) > 10:
                print("     …… 另 %d 处" % (len(ent_hits) - 10))
            fails.append("V12 人读入口挂着 %d 处台账编号（%s）——包里没有那份台账，收包人查不到"
                         % (len(ent_hits), "／".join(sorted({h[2] for h in ent_hits}))))
    else:
            print("  ✅ 扫 %d 份人读入口，0 处台账编号" % ent_scan)

    return fails, warns

def check_v13(root, fails, warns, all_files):
    # ── V13 包内 MANIFEST.sha256 自洽（2026-11-28，ST1.0.9 A；R1 按包类型分流＋集合相等）──
    # 维护侧对打好的包（解压目录）跑：逐行核 sha256(包内该文件字节)==行值；核清单不含自身；
    # 行数==包内文件数−1；集合相等（missing/extra 都报）；拒绝对路径与含 .. 的路径。
    # 旧实例包（_pack 产物）无清单 → 只 warn 跳过；用户包缺清单／行不符 → 阻断。
    # 包里只放 MANIFEST.sha256 本身，本检查在维护侧（packaging/ 不进用户包）。
    print("\nV13 包内 MANIFEST.sha256 自洽")
    mf = os.path.join(root, "MANIFEST.sha256")
    # R1-A 按包类型分流：旧实例包（_pack 产物，带 从这里开始.txt／00_原著/）本就不带清单 → 只 warn 跳过，不阻断
    old_instance = os.path.isfile(os.path.join(root, "从这里开始.txt")) or os.path.isdir(os.path.join(root, "00_原著"))
    if not os.path.isfile(mf):
        if old_instance:
            print("  ⚠ V13 跳过：旧实例包不带清单")
            warns.append("V13 跳过：旧实例包不带清单")
            return fails, warns
        print("  ✗ 缺 MANIFEST.sha256 —— 包里没有自洽清单")
        fails.append("V13 缺 MANIFEST.sha256")
        return fails, warns
    entries = {}
    bad_lines = []
    bad_paths = []
    with open(mf, encoding="utf-8") as fh:
        for i, line in enumerate(fh.read().splitlines(), 1):
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split("  ", 1)
            if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
                bad_lines.append((i, line[:60]))
                continue
            rel = parts[1].strip()
            # R2-2：非法路径（绝对／含 ..）先判后 continue——不入 entries、不进 sha 循环，杜绝越界读包外
            if os.path.isabs(rel) or ".." in rel.replace("\\", "/").split("/"):
                bad_paths.append((i, rel))
                continue
            entries[rel] = parts[0].strip()
    if "MANIFEST.sha256" in entries:
        print("  ✗ 清单含自身 MANIFEST.sha256 —— 清单不许列自己")
        fails.append("V13 清单含自身")
    for i, rel in bad_paths:
        print("  ✗ 第 %d 行路径非法（绝对路径或含 ..）：%s" % (i, rel))
        fails.append("V13 清单第 %d 行路径非法：%s" % (i, rel))
    # R1-B 集合相等：清单条目集合 == 包内文件集合 − 自身（missing／extra 都报）
    actual = {os.path.relpath(fp, root).replace(os.sep, "/") for fp in all_files}
    actual.discard("MANIFEST.sha256")
    listed = set(entries)
    missing = sorted(listed - actual)
    extra = sorted(actual - listed)
    for rel in missing:
        print("  ✗ 清单列了但包里没有：%s" % rel)
    for rel in extra:
        print("  ✗ 包里有但清单没列：%s" % rel)
    if missing:
        fails.append("V13 清单 %d 项在包内缺失" % len(missing))
    if extra:
        fails.append("V13 包内 %d 个文件未列入清单" % len(extra))
    n_files = len(all_files)
    if len(entries) != n_files - 1:
        print("  ✗ 清单 %d 行 != 包内文件数 %d − 1" % (len(entries), n_files))
        fails.append("V13 清单行数 %d != 包内文件数 %d − 1" % (len(entries), n_files))
    mism = []
    for rel, want in entries.items():
        fp = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.isfile(fp):
            mism.append((rel, "文件不在"))
            continue
        with open(fp, "rb") as fb:
            got = hashlib.sha256(fb.read()).hexdigest()
        if got != want:
            mism.append((rel, "sha256 不符"))
    for i, snip in bad_lines:
        print("  ✗ 第 %d 行格式不对：%s" % (i, snip))
        fails.append("V13 清单第 %d 行格式不对" % i)
    if mism:
        for rel, why in mism[:20]:
            print("  ✗ %s —— %s" % (rel, why))
        fails.append("V13 %d 个文件 sha256 不符或缺失" % len(mism))
    elif not bad_lines and not bad_paths and not missing and not extra and "MANIFEST.sha256" not in entries and len(entries) == n_files - 1:
        print("  ✅ %d 个文件 sha256 全核过，清单不含自身" % len(entries))
    return fails, warns


def main():
    if len(sys.argv) < 2:
        print("用法：python packaging/_verify_package.py <包目录>")
        return 2
    root = os.path.abspath(sys.argv[1])
    if not os.path.isdir(root):
        print("✗ 不是目录：%s" % root)
        return 1
    _script_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if os.path.normcase(root) == os.path.normcase(_script_root):
        print("[verify] 你验的是源码仓库，不是打好的包。", file=sys.stderr)
        return 2
    fails, warns = [], []
    print("── 验包 · %s ──" % root)
    for fn in (check_v0, check_v1, check_v6):
        fn(root, fails, warns)
    nouns, noun_err = load_project_nouns()
    all_files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", ".idea", ".vscode")]
        for fn in filenames:
            all_files.append(os.path.join(dirpath, fn))
    check_v2(root, fails, warns, all_files)
    check_v3(root, fails, warns, all_files, nouns, noun_err)
    check_v4(root, fails, warns)
    check_v5(root, fails, warns, all_files)
    check_v7(root, fails, warns)
    check_v8(root, fails, warns)
    check_v9(root, fails, warns, all_files)
    for fn in (check_v10, check_v11, check_v12):
        fn(root, fails, warns)
    check_v13(root, fails, warns, all_files)
    # ── 汇总 ──
    print()
    if fails:
        print("✗ 不许发：%d 条阻断" % len(fails))
        for f in fails:
            print("    · %s" % f)
        return 1
    print("✅ 可以发。")
    print()
    print("   ⚠ 三个限度，别把绿当「验过了」：")
    print("     ① 它只证「没带出不该带的」，不证「该带的都带了」——白名单漏项它看不见")
    print("     ② 它只证「字面上没有专名」，判不了某句话是不是在讲这个项目")
    print("     ③ 它没装过一遍。装得上不上，得真找个人照 `开工提示词.md` 走一次")
    if warns:
        for w in warns:
            print("     ⚠ %s" % w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
