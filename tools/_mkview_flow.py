# -*- coding: utf-8 -*-
"""_mkview_flow.py — 镜表 → 环节视图（通用层）

## 它跟 `_mkview.py` 的分工

    清单（问题／依据／选项） → 可填件、要人逐条裁定  → `_mkview.py`
    镜表（一格一行、每格带参数） → 状态板、供人核参数  → **这个**

两类东西长得很像，判法完全不同：前者问「你选哪个」，后者问「这格对不对」。
**别用一个脚本干两件事**——那会让两边都变成参数堆。

## 输入

一份 md，里面可以有多张同构表（分段用），每张表一条镜头一行：

| 格 | 景别 | 呈现 | 节奏 | 本格唯一信息 | 资产 | 动不动 | 变化 | 生产方式 | 机位建议 |
|---|---|---|---|---|---|---|---|---|---|
| S-01 | 中景 | 清晰 | 慢 | 这一格要说的事 | 某资产❌ | 微动 | 光变 | AI 图+后期 | 〔参〕距 X |

**按表头名取值，不认列序号。** 表头名用模糊匹配（见 `ROLE`），差几个字也认。
多出来的列不报错、原样保留在单格页里——**它认不出好歹，只负责摆出来**。

必需列只有一个：**格**。其余缺了就是缺，不猜。

## 输出

一张 html，三个页签：

    ① 总表     —— 一行一格，横向扫一眼看出哪格不对劲
    ② 分派     —— 「本格唯一信息」× 「资产」：这格要说的事有没有主人
    ③ 单格     —— 选一格，全参数摊开（含它没认出来的列）

**没有「整体结论」这一页。** 它给的是观察面，判断在人。

## 三条边界

① **它不判合格。** 不写「✅ 通过」这种字——参数齐不齐是一回事，对不对是另一回事。
② **它不改数据源。** 只读 md，产物是一次性的视图；md 改了要重跑，别手改 html。
③ **机位那类「参考值」不进判据。** 表里标了 `〔参〕` 的原样带过来，脚本不认它的语义。

用法：
    python tools/_mkview_flow.py <镜表.md> -o "[视图]环节.html"
    python tools/_mkview_flow.py <镜表.md> -o out.html --title "预告片 · 23 格"
    python tools/_mkview_flow.py <镜表.md> -o out.html --pick T-04    # 单格页默认打开哪格
"""

import io
import os
import re
import sys
import html
import hashlib

# 表头名 → 角色。值是这个角色认可的几种写法（模糊匹配：包含即算）。
# 加新角色就在这里加一行——**别在渲染代码里写 `if "景别" in h`**。
ROLE = [
    ("格",       ["格", "镜号", "镜头号", "编号"]),
    ("原文行",   ["原文行", "出处", "原文"]),
    ("信息层",   ["信息层", "层的", "类别"]),
    ("镜头方案", ["镜头方案", "方案", "拍法"]),
    ("景别",     ["景别"]),
    ("呈现",     ["呈现"]),
    ("节奏",     ["节奏", "时长"]),
    ("空间",     ["空间", "层位"]),
    ("尺寸参照", ["尺寸"]),
    ("光",       ["光"]),
    ("资产",     ["资产", "素材"]),
    ("信息",     ["本格唯一信息", "唯一信息", "信息"]),
    ("动不动",   ["动不动", "动幅"]),
    ("变化",     ["变化"]),
    ("起止帧",   ["可借作起止帧", "起止帧"]),
    ("生产方式", ["生产方式", "制作方式"]),
    ("机位",     ["机位"]),
]

# 总表默认显示的角色（顺序即列序）。想换列改这里，别改渲染函数。
WIDE = ["格", "景别", "呈现", "节奏", "动不动", "变化", "生产方式", "信息", "资产"]

# 落盘时的键名。中文表头是给人读的，json 键给程序读——**别混着用**，
# 混了之后调用方要写 `row["本格唯一信息"]`，等于把中文当 API。
KEY = {
    "格": "shot_id", "原文行": "source", "信息层": "info_layer",
    "镜头方案": "shot_plan", "景别": "framing", "呈现": "present",
    "节奏": "pace", "空间": "space", "尺寸参照": "scale_ref", "光": "light",
    "资产": "asset", "信息": "info", "动不动": "motion", "变化": "change",
    "起止帧": "borrowable", "生产方式": "production", "机位": "camera",
}

SCHEMA_VERSION = 1


def die(msg, code=2):
    print("[flow] ⛔ " + msg, file=sys.stderr)
    sys.exit(code)


# ── 解析 ──────────────────────────────────────────────────────────────────

def split_row(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def is_sep(line):
    return bool(re.match(r"^\|[\s:\-|]+\|?\s*$", line.strip())) and "-" in line


def match_role(name):
    """把一个表头名归到角色上。认不出返回 None——**不许兜底成第一列**。

    「格」只做精确匹配：`主格`、`格数`、`格子` 都会被模糊匹配抓进来，
    而镜表旁边最常见的配角表恰好就叫「必须传达的信息 ｜ 主格 ｜ 谁来兜」——
    那一张被抓进来，23 格会变成 46 格，而且不报错。**宁可漏认一列，不许认错一张表。**
    """
    n = name.strip().strip("*").strip()
    for role, alts in ROLE:
        for a in alts:
            if a == n:
                return role
    for role, alts in ROLE:
        if role == "格":
            continue
        for a in alts:
            if a in n:
                return role
    return None


def parse_tables(text):
    """返回 (rows, dropped)。rows 里每条是 {角色: 值}，键就是 ROLE 里那个角色名。
    同构表可以有多张，合并成一份；**顺序按文件出现顺序**，不排序——
    镜表的播放序是人排的，脚本不替他重排。

    认一张表要同时满足两条：有「格」列 ＋ 至少两个**强特征列**（景别／镜头方案／呈现／
    节奏／资产／动不动／变化）。只看「格」不够——镜表旁边常贴一张
    「必须传达的信息 ｜ 主格 ｜ 谁来兜」的映射表，只按「格」判，那张表会被当成镜表，
    23 格变 46 格，**而且一句错都不报**（2026-11-12 实测踩到）。
    """
    lines = text.split("\n")
    i, rows, dropped = 0, [], 0
    strong = {"景别", "镜头方案", "呈现", "节奏", "资产", "动不动", "变化"}
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("|") and i + 1 < len(lines) and is_sep(lines[i + 1]):
            roles = [match_role(h) for h in split_row(ln)]
            if "格" not in roles or len(set(roles) & strong) < 2:
                # 不是镜表（可能是说明表／映射表），跳过整段
                i += 2
                continue
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                if is_sep(lines[i]):
                    i += 1
                    continue
                cells = split_row(lines[i])
                rec = {}
                for k, val in enumerate(cells):
                    if k < len(roles) and roles[k]:
                        rec[roles[k]] = val
                if rec.get("格"):
                    rows.append(rec)
                else:
                    dropped += 1
                i += 1
            continue
        i += 1
    return rows, dropped


def strip_md(s):
    """去掉 markdown 行内标记，留下可读文本。表格里塞加粗是常事。"""
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s or "")
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"~~(.+?)~~", r"\1", s)
    return s.strip()


def esc(s):
    return html.escape(strip_md(s), quote=True)


def short(s, n=42):
    """长文本截断，只用于总表；单格页给全文。"""
    t = strip_md(s)
    return t if len(t) <= n else t[:n] + "…"


# ── 渲染 ──────────────────────────────────────────────────────────────────

CSS = """
:root{--bg:#12151a;--fg:#dfe4ea;--dim:#8b95a3;--line:#252b34;--card:#191d24;
--acc:#c8a24a;--warn:#d9843a;--ok:#5a9e6f}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:14px/1.6 "Sarasa Mono SC","Microsoft YaHei",system-ui,sans-serif}
header{padding:18px 24px 12px;border-bottom:1px solid var(--line)}
h1{margin:0 0 4px;font-size:17px;font-weight:600}
.meta{color:var(--dim);font-size:12px}
.tabs{display:flex;gap:2px;padding:0 24px;border-bottom:1px solid var(--line);
background:#141820;position:sticky;top:0;z-index:5}
.tab{padding:9px 16px;cursor:pointer;color:var(--dim);font-size:13px;
border-bottom:2px solid transparent;user-select:none}
.tab:hover{color:var(--fg)}
.tab.on{color:var(--acc);border-bottom-color:var(--acc)}
.panel{display:none;padding:20px 24px 60px}
.panel.on{display:block}
.water{display:flex;gap:18px;flex-wrap:wrap;margin-bottom:16px;
padding:10px 14px;background:var(--card);border:1px solid var(--line);border-radius:6px;
font-size:12px;color:var(--dim)}
.water b{color:var(--fg);font-weight:600}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:left;
vertical-align:top}
th{color:var(--dim);font-weight:500;font-size:12px;white-space:nowrap;
position:sticky;top:44px;background:var(--bg)}
td.id{font-family:ui-monospace,monospace;color:var(--acc);white-space:nowrap}
tr:hover td{background:#1b2028}
.tag{display:inline-block;padding:0 6px;border-radius:3px;font-size:11.5px;
background:#232a34;color:var(--dim);white-space:nowrap}
.tag.warn{background:#3a2a18;color:var(--warn)}
.tag.ok{background:#1b2f22;color:var(--ok)}
.dim{color:var(--dim)}
.none{color:#5a626e}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:12px 14px}
.card h3{margin:0 0 8px;font-size:13px;color:var(--acc);font-weight:600}
.kv{display:grid;grid-template-columns:88px 1fr;gap:4px 10px;font-size:12.5px}
.kv dt{color:var(--dim)}
.kv dd{margin:0}
.pick{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}
.pick .b{padding:4px 10px;border:1px solid var(--line);border-radius:4px;
cursor:pointer;font-family:ui-monospace,monospace;font-size:12px;color:var(--dim)}
.pick .b:hover{border-color:var(--acc);color:var(--fg)}
.pick .b.on{background:#2a2415;border-color:var(--acc);color:var(--acc)}
.sheet{display:none}
.sheet.on{display:block}
.note{margin-top:22px;padding:10px 14px;border-left:3px solid var(--warn);
background:#1d1a14;color:var(--dim);font-size:12px;border-radius:0 4px 4px 0}
"""

JS = """
function tab(el){var k=el.dataset.p;
document.querySelectorAll('.tab').forEach(function(t){t.classList.toggle('on',t===el)});
document.querySelectorAll('.panel').forEach(function(p){p.classList.toggle('on',p.id===k)});}
function pick(el){var k=el.dataset.k;
document.querySelectorAll('#pickbar .b').forEach(function(b){b.classList.toggle('on',b===el)});
document.querySelectorAll('.sheet').forEach(function(s){s.classList.toggle('on',s.id==='s-'+k)});}
"""


def render_water(rows):
    """顶部水位：只数得出来的东西，不写「合格」。"""
    n = len(rows)
    noinfo = sum(1 for r in rows if not strip_md(r.get("信息")))
    noasset = sum(1 for r in rows if not strip_md(r.get("资产")))
    pending = sum(1 for r in rows if "待定" in r.get("生产方式", "") or "待定" in r.get("动不动", ""))
    parts = ['<b>%d</b> 格' % n]
    parts.append('缺「本格唯一信息」<b>%d</b>' % noinfo)
    parts.append('缺「资产」<b>%d</b>' % noasset)
    parts.append('含「待定」<b>%d</b>' % pending)
    return '<div class="water">%s<span class="dim">· 只数得出来的，不判合格</span></div>' % " ｜ ".join(parts)


def render_wide(rows):
    """① 总表：一行一格，横向扫。"""
    head = "".join("<th>%s</th>" % h for h in WIDE)
    body = []
    for r in rows:
        tds = ['<td class="id">%s</td>' % esc(r.get("格", ""))]
        for role in WIDE[1:]:
            v = strip_md(r.get(role, ""))
            if not v or v == "—":
                tds.append('<td class="none">—</td>')
                continue
            cls = ""
            if "待定" in v:
                cls = ' class="tag warn"'
            elif role == "资产" and "❌" in v:
                cls = ' class="tag warn"'
            tds.append("<td><span%s>%s</span></td>" % (cls, esc(short(v))) if cls
                       else "<td>%s</td>" % esc(short(v)))
        body.append("<tr>%s</tr>" % "".join(tds))
    return ('<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>'
            % (head, "".join(body)))


def render_dispatch(rows):
    """② 分派：这格要说的事，有没有主人。"""
    cards = []
    for r in rows:
        info = strip_md(r.get("信息", "")) or "（未写）"
        asset = strip_md(r.get("资产", "")) or "（未写）"
        miss = "❌" in asset or not strip_md(r.get("资产", ""))
        cls = "tag warn" if miss else "tag ok"
        cards.append(
            '<div class="card"><h3>%s</h3><dl class="kv">'
            '<dt>要说的事</dt><dd>%s</dd>'
            '<dt>谁拍它</dt><dd><span class="%s">%s</span></dd>'
            '<dt>景别·节奏</dt><dd>%s ｜ %s</dd>'
            "</dl></div>"
            % (esc(r.get("格", "")), esc(info), cls, esc(asset),
               esc(r.get("景别", "—")), esc(r.get("节奏", "—"))))
    return '<div class="cards">%s</div>' % "".join(cards)


def render_one(r, title):
    """③ 单格：全参数摊开，含没认出来的列。"""
    order = [k for k, _ in ROLE]
    kv = []
    for role in order:
        if role == "格":
            continue
        v = strip_md(r.get(role, ""))
        if not v:
            continue
        kv.append('<dt>%s</dt><dd>%s</dd>' % (role, esc(v)))
    return ('<div class="sheet" id="s-%s"><div class="card" style="max-width:820px">'
            "<h3>%s ｜ %s</h3><dl class=\"kv\">%s</dl></div></div>"
            % (esc(r.get("格", "")), esc(r.get("格", "")), esc(title), "".join(kv)))


def build(rows, title, pick=""):
    if not rows:
        die("没解析出任何一格。检查：表头里有没有「格」这一列？")
    keys = [r.get("格", "") for r in rows]
    if pick and pick not in keys:
        die("`--pick %s` 不在这份表里。有的是：%s" % (pick, "、".join(keys)))

    pickbar = "".join(
        '<div class="b%s" data-k="%s" onclick="pick(this)">%s</div>'
        % (" on" if (k == (pick or keys[0])) else "", esc(k), esc(k)) for k in keys)
    sheets = "".join(render_one(r, title) for r in rows)

    return """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s</title><style>%s</style></head><body>
<header><h1>%s</h1>
<div class="meta">%d 格 ｜ 由 `_mkview_flow.py` 从镜表生成 ｜ <b>脚本不判合格，只摆参数</b></div></header>
<div class="tabs">
<div class="tab on" data-p="p1" onclick="tab(this)">总表</div>
<div class="tab" data-p="p2" onclick="tab(this)">分派</div>
<div class="tab" data-p="p3" onclick="tab(this)">单格</div>
</div>
<div class="panel on" id="p1">%s%s</div>
<div class="panel" id="p2">%s</div>
<div class="panel" id="p3"><div class="pick" id="pickbar">%s</div>%s</div>
<div class="note">三件事它做不到：<b>不判合格</b>（参数齐不等于对）／<b>不改数据源</b>（md 改了要重跑）／
<b>不认参考值的语义</b>（标了〔参〕的原样带过来，它不知道那是不是判据）。</div>
<script>%s</script></body></html>""" % (
        esc(title), CSS, esc(title), len(rows),
        render_water(rows), render_wide(rows),
        render_dispatch(rows), pickbar, sheets, JS)


def parse_camera(raw):
    """把 `〔参〕距 2.5 ／ 高 1.2 ／ 偏 28°` 拆成数。

    **拆不出来就留 None，不猜、不拿默认值补。** 有的格写的是区间（`距 5.0→2.5`），
    那不是一个数——硬取左边会把「起止两个机位」压成一个，比空着更坏。
    `raw` 永远原样保留，结构化字段只是方便程序读；**读不到就去读 raw**。
    """
    out = {"raw": strip_md(raw), "ref": "〔参〕" in (raw or "")}
    if not raw:
        return out
    for key, pat in (("distance", r"距\s*([\d.]+)"),
                     ("height", r"高\s*([\d.]+)"),
                     ("yaw", r"偏\s*([\d.]+)")):
        m = re.search(pat, raw)
        out[key] = float(m.group(1)) if m else None
    # 区间值（`5.0→2.5`）不拆：单值语义不成立，宁可空着
    if re.search(r"距\s*[\d.]+\s*→", raw) or re.search(r"高\s*[\d.]+\s*→", raw):
        out["distance"] = None
        out["height"] = None
    return out


def to_shot(r, order, src_label, src_md5v):
    """一格 → 一份落盘件。**17 栏全进**，宁可冗余也不让下游回读 md。

    五组：身份 ／ 拍什么 ／ 怎么拍 ／ 素材 ／ 参考。元信息单列在最后。
    """
    info = strip_md(r.get("信息", ""))
    plan = strip_md(r.get("镜头方案", ""))
    asset = strip_md(r.get("资产", ""))
    # `desc` 是**派生**的，不是源字段：回执第四条已定「一句话描述」来源就是
    # 「本格唯一信息」（＋「镜头方案」补充），不另造一列同名不同义的东西。
    desc = info or (plan[:40] + "…" if len(plan) > 40 else plan)
    return {
        "schema_version": SCHEMA_VERSION,
        "shot_id": strip_md(r.get("格", "")),
        "order": order,
        "source": strip_md(r.get("原文行", "")),
        "brief": {
            "desc": desc,
            "desc_from": "info" if info else "shot_plan",
            "info": info,
            "info_layer": strip_md(r.get("信息层", "")),
            "shot_plan": plan,
        },
        "shot": {
            "framing": strip_md(r.get("景别", "")),
            "present": strip_md(r.get("呈现", "")),
            "pace": strip_md(r.get("节奏", "")),
            "light": strip_md(r.get("光", "")),
            "space": strip_md(r.get("空间", "")),
            "scale_ref": strip_md(r.get("尺寸参照", "")),
            "motion": strip_md(r.get("动不动", "")),
            "change": strip_md(r.get("变化", "")),
        },
        "material": {
            "asset": asset,
            "asset_missing": "❌" in asset,
            "borrowable": strip_md(r.get("起止帧", "")),
            "production": strip_md(r.get("生产方式", "")),
        },
        "camera": parse_camera(r.get("机位", "")),
        "meta": {
            "generated_from": src_label,
            "generated_md5": src_md5v,
        },
    }


def emit_shots(rows, outdir, src_label, src_md5v):
    """逐格写 `<格号>.json`。返回 (写成几个, 跳过哪些)。

    同名文件直接覆盖——**落盘件是一次性的产物，不许手改**；
    手改过的版本在下次生成时会被无声抹掉，这跟「别手改生成的 html」是同一条纪律。
    """
    import json
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    wrote, skipped = [], []
    for i, r in enumerate(rows, 1):
        sid = strip_md(r.get("格", "")).strip("*").strip()
        if not sid or "/" in sid or "\\" in sid:
            skipped.append(sid or "(空格号)")
            continue
        doc = to_shot(r, i, src_label, src_md5v)
        path = os.path.join(outdir, sid + ".json")
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
        wrote.append(sid)
    return wrote, skipped


def main():
    args = sys.argv[1:]
    if not args or "-h" in args or "--help" in args:
        print(__doc__)
        return 0
    src, out, title, pick, emit = "", "", "", "", ""
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-o", "--out"):
            i += 1
            out = args[i] if i < len(args) else ""
        elif a in ("--title",):
            i += 1
            title = args[i] if i < len(args) else ""
        elif a in ("--pick",):
            i += 1
            pick = args[i] if i < len(args) else ""
        elif a in ("--emit",):
            i += 1
            emit = args[i] if i < len(args) else ""
        elif not src:
            src = a
        else:
            die("多余的参数：%s" % a)
        i += 1

    if not src:
        die("要给一份镜表 md。用法见 `--help`。")
    if not os.path.isfile(src):
        die("找不到：%s" % src)
    if not out and not emit:
        out = os.path.splitext(os.path.basename(src))[0] + "_flow.html"

    with io.open(src, encoding="utf-8", errors="replace") as f:
        text = f.read()
    rows, dropped = parse_tables(text)
    if dropped:
        print("[flow] 有 %d 行没有格号，已跳过——**别当它们不存在**" % dropped,
              file=sys.stderr)

    title = title or os.path.basename(src)
    if out:
        with io.open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(build(rows, title, pick))
        print("[flow] %d 格 → %s" % (len(rows), out))
        print("[flow] 认出来的列：%s" % "、".join(
            [k for k, _ in ROLE if any(k in r for r in rows)]))

    if emit:
        # 存**相对当前目录的路径**：能指到那份 md，检查器才验得了。
        # 绝对路径会带盘符，等于把本机目录结构写进每一格。
        # 不在当前目录下（以 `..` 开头）就退回文件名——宁可溯源弱一点，不写盘符。
        try:
            label = os.path.relpath(src).replace("\\", "/")
            if label.startswith(".."):
                label = os.path.basename(src)
        except ValueError:
            label = os.path.basename(src)
        md5 = hashlib.md5(text.encode("utf-8")).hexdigest()[:12]
        wrote, skipped = emit_shots(rows, emit, label, md5)
        print("[flow] 落盘 %d 份 → %s（源 %s@%s）" % (len(wrote), emit, label, md5))
        if skipped:
            print("[flow] ⚠ 跳过 %d 格（格号为空／含路径分隔符）：%s"
                  % (len(skipped), "、".join(skipped)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
