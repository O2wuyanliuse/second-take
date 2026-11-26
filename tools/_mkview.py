# -*- coding: utf-8 -*-
"""清单 → 可填视图生成器（通用层）

用法：
    python _mkview.py 清单.md -o "[视图]XXX.html"
    python _mkview.py 清单.md -o out.html --title "E0·6 对齐扫雷" --mode t2
    python _mkview.py 清单.md -o out.html --options "采纳/覆盖/作废"

完整说明：docs/maintain/代码内长文档/tools/_mkview.py.md
"""
import io
import os
import re
import sys
import html
import hashlib

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


def src_md5(text):
    """源清单的内容指纹。

    **换行符先归一再算**——不归一的话，git checkout 把 LF 转成 CRLF，
    指纹就变了，探针会误报「视图过期」。而那是换行符的事，不是内容的事。
    两边（这里与 `_consist.check_viz_pair`）必须用同一个算法，否则比了个寂寞。
    """
    flat = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.md5(flat.encode("utf-8")).hexdigest()[:12]

# ---------------------------------------------------------------- 表头识别
# 模糊匹配：表头单元格**包含**这些词就算命中。不认列序号。
COLS = {
    "id":   ("编号", "id", "序", "no", "#"),
    "q":    ("问题", "条目", "事项", "内容", "标题"),
    "why":  ("依据", "出处", "理由", "锚点", "原文"),
    "opt":  ("选项", "选择", "方案"),
    "hint": ("建议", "倾向", "备注", "说明"),
    # 「裁决」不是「选项」的同义词：选项是候选，裁决是结果。
    # 原先把它并进 opt，清单一旦两列并存，裁完的件会被重新渲染成可填的。
    "verdict": ("裁决", "结论", "结果"),
}

MODES = {
    "t1": ["采纳", "覆盖", "作废"],
    "t2": ["已定", "未定"],
}


def split_row(line):
    """切一行 md 表格。处理 `\\|` 转义，不去掉内容里的竖线。"""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    parts = re.split(r"(?<!\\)\|", s)
    return [p.strip().replace("\\|", "|") for p in parts]


def is_sep(line):
    """分隔行：| --- | :---: |"""
    s = line.strip()
    if not s.startswith("|"):
        return False
    return bool(re.fullmatch(r"\|?[\s:\-|]+\|?", s)) and "-" in s


def map_headers(cells):
    """表头单元格 → 角色名。认不出返回 None。"""
    got = {}
    for i, c in enumerate(cells):
        low = c.strip().lower()
        for role, keys in COLS.items():
            if role in got:
                continue
            if any(k.lower() in low for k in keys):
                got[role] = i
                break
    return got if "q" in got else None


def parse_table(text):
    """从 md 里找第一张能认出来的表，返回 (rows, headers)。"""
    lines = text.split("\n")
    for i in range(len(lines) - 1):
        if not lines[i].strip().startswith("|"):
            continue
        if not is_sep(lines[i + 1]):
            continue
        headers = split_row(lines[i])
        idx = map_headers(headers)
        if not idx:
            continue
        rows = []
        for j in range(i + 2, len(lines)):
            ln = lines[j]
            if not ln.strip().startswith("|"):
                break
            cells = split_row(ln)

            def pick(role):
                k = idx.get(role)
                if k is None or k >= len(cells):
                    return ""
                return cells[k].strip()

            q = pick("q")
            if not q:
                continue
            rows.append({
                "id": pick("id") or ("Q%d" % (len(rows) + 1)),
                "q": q,
                "why": pick("why"),
                "opt": pick("opt"),
                "hint": pick("hint"),
                "verdict": pick("verdict"),
            })
        return rows, headers
    return [], []


# ---------------------------------------------------------------- 内联格式
def md_inline(s):
    """把 `**粗**` / `~~删~~` / `` `代码` `` 转成 HTML，其余转义。够用就好。"""
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    # 删除线：作废的旧建议要用它划掉，否则读的人分不清哪句还算数。
    s = re.sub(r"~~([^~]+)~~", r"<s>\1</s>", s)
    return s


def esc_attr(s):
    return html.escape(s, quote=True)


# ---------------------------------------------------------------- 生成
def build(rows, title, subtitle, opts, stage, src_name="", src_md5v=""):
    n = len(rows)
    # 每条一组的 radio name
    body = []
    done_n = 0
    for i, r in enumerate(rows):
        # 已裁的行不再渲染控件——裁完还能改，等于让人以为判决可以随手推翻。
        if r["verdict"]:
            done_n += 1
            why = ('<div class="why">%s</div>' % md_inline(r["why"])) if r["why"] else ""
            hint = ('<div class="hintline">原建议：%s</div>' % md_inline(r["hint"])) if r["hint"] else ""
            body.append(
                '<div class="item closed" data-i="%d" data-no="%s">\n'
                '  <div class="head"><span class="no">%s</span><span class="qt">%s</span>'
                '<span class="tag">已裁</span></div>\n'
                '  %s\n'
                '  <div class="verdict">%s</div>\n'
                '  %s\n'
                '</div>' % (i, esc_attr(r["id"]), md_inline(r["id"]), md_inline(r["q"]),
                            why, md_inline(r["verdict"]), hint)
            )
            continue

        o = r["opt"] or ""
        choices = [c.strip() for c in re.split(r"[/／、]", o) if c.strip()] or opts
        name = "q%d" % i
        chips = []
        for k, c in enumerate(choices):
            cid = "%s_%d" % (name, k)
            chips.append(
                '<label class="ch"><input type="radio" name="%s" id="%s" value="%s">'
                '<span>%s</span></label>' % (name, cid, esc_attr(c), md_inline(c))
            )
        why = ('<div class="why">%s</div>' % md_inline(r["why"])) if r["why"] else ""
        hint = ('<div class="hintline">%s</div>' % md_inline(r["hint"])) if r["hint"] else ""
        body.append(
            '<div class="item" data-i="%d">\n'
            '  <div class="head"><span class="no">%s</span><span class="qt">%s</span></div>\n'
            '  %s\n'
            '  <div class="chips">%s</div>\n'
            '  <textarea class="note" rows="1" placeholder="补充说明（可留空）：改了哪儿、为什么"></textarea>\n'
            '  %s\n'
            '</div>' % (i, md_inline(r["id"]), md_inline(r["q"]), why, "".join(chips), hint)
        )

    return TEMPLATE % {
        "title": esc_attr(title),
        "title_html": md_inline(title),
        "subtitle": esc_attr(subtitle),
        "subtitle_html": md_inline(subtitle),
        "n": n,
        "done_n": done_n,
        "all_done": "1" if (n and done_n == n) else "0",
        "items": "\n".join(body),
        "stage_attr": "1" if stage else "fill",
        "stage_js": "true" if stage else "false",
        "src_name": esc_attr(src_name),
        "src_md5": esc_attr(src_md5v),
    }


TEMPLATE = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="generator" content="mkview">
<title>%(title)s</title><style>
  :root{--bg:#0e1014;--card:#171b22;--card2:#1d222b;--line:#2a3140;--txt:#dfe4ec;
        --dim:#8b95a6;--faint:#5d6675;--accent:#5b9cf5;--ok:#43c08a;--warn:#e2a33c;--bad:#e06a6a}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--txt);padding:26px 20px 70px;
       font:14px/1.7 -apple-system,"Segoe UI","Microsoft YaHei",system-ui,sans-serif}
  .wrap{max-width:900px;margin:0 auto}
  header{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin-bottom:6px}
  h1{font-size:19px;font-weight:600;margin:0 0 4px}
  .sub{color:var(--dim);font-size:12px;font-family:ui-monospace,Consolas,monospace}
  #badge{flex:none;font-size:11.5px;padding:4px 11px;border-radius:20px;
         font-family:ui-monospace,Consolas,monospace;white-space:nowrap;
         background:#12301f;border:1px solid #2c6a46;color:#7fd8a8}
  #badge.dirty{background:#3a2a10;border-color:#7a5a1c;color:#e8c073}
  .bar{display:flex;gap:8px;align-items:center;margin:16px 0 14px;padding:10px 14px;
       background:var(--card);border:1px solid var(--line);border-radius:9px;font-size:12.5px;color:var(--dim)}
  .bar b{color:var(--txt)}
  .bar .grow{flex:1}
  button{font-family:inherit;cursor:pointer;font-size:12.5px;border-radius:6px;
         padding:6px 13px;border:1px solid var(--line);background:var(--card2);color:#b7c0cd;transition:.12s}
  button:hover{border-color:#3d4a5e;color:var(--txt)}
  button.primary{background:#1b3a5e;border-color:var(--accent);color:#bcd8fb;font-weight:500}
  button.primary:hover{background:#22476f}
  button:disabled{opacity:.4;cursor:not-allowed}
  .item{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:13px 15px;margin-bottom:10px}
  .item.done{border-color:#2c4a34}
  .head{display:flex;gap:10px;align-items:baseline;margin-bottom:5px}
  .no{flex:none;font-family:ui-monospace,Consolas,monospace;font-size:11.5px;color:var(--faint);
      background:var(--card2);border-radius:4px;padding:1px 7px}
  .qt{font-size:13.5px;font-weight:500;line-height:1.6}
  .why{font-size:12px;color:var(--dim);line-height:1.65;padding:5px 0 3px;border-left:2px solid #2f3a4a;padding-left:10px;margin:5px 0 7px}
  .why code,.qt code{background:#0a0c10;border-radius:3px;padding:1px 5px;font-size:11.5px;
                     font-family:ui-monospace,Consolas,monospace;color:#9fb6d4}
  .chips{display:flex;flex-wrap:wrap;gap:6px;margin:7px 0}
  .ch{display:inline-flex;align-items:center;cursor:pointer}
  .ch input{position:absolute;opacity:0;width:0;height:0}
  .ch span{display:inline-block;padding:5px 13px;border-radius:6px;font-size:12.5px;
           background:var(--card2);border:1px solid var(--line);color:#b7c0cd;transition:.12s}
  .ch:hover span{border-color:#3d4a5e;color:var(--txt)}
  .ch input:checked + span{background:#1b3a5e;border-color:var(--accent);color:#bcd8fb;font-weight:500}
  .ch input:focus-visible + span{outline:2px solid var(--accent);outline-offset:1px}
  .ch input:disabled + span{opacity:.45;cursor:not-allowed}
  textarea.note{width:100%%;background:#0a0c10;border:1px solid var(--line);border-radius:6px;
                color:var(--txt);font:12.5px/1.6 inherit;padding:7px 9px;resize:vertical;min-height:32px}
  textarea.note:disabled{opacity:.45}
  .hintline{font-size:11.5px;color:var(--faint);margin-top:6px;line-height:1.6}
  .out{margin-top:18px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:15px}
  .out h2{font-size:12px;font-weight:600;margin:0 0 10px;color:var(--dim);
          font-family:ui-monospace,Consolas,monospace;letter-spacing:.4px;display:flex;
          justify-content:space-between;align-items:center;gap:10px}
  pre#txt{margin:0;white-space:pre-wrap;word-break:break-word;font-size:12.5px;line-height:1.9;
          color:#cfd6e0;font-family:ui-monospace,Consolas,"Microsoft YaHei",monospace;min-height:2em}
  .miss{margin-top:11px;padding-top:10px;border-top:1px dashed var(--line);
        font-size:12px;color:var(--warn);line-height:1.7}
  .miss:empty{display:none}
  .copytip{display:none}
  .copytip.show{display:block;margin-top:10px;padding:8px 11px;background:#3a2a10;
                border:1px solid #7a5a1c;border-radius:6px;color:#e8c073;
                font-size:12.5px;line-height:1.65}
  pre#txt{cursor:text}
  .note-btm{margin-top:18px;color:var(--faint);font-size:11.5px;line-height:1.8;
            border-top:1px solid var(--line);padding-top:12px}
  .locked-tip{font-size:12px;color:var(--warn);margin:0 0 12px}
  body[data-stage="fill"] .locked-tip{display:none}
  /* 已裁行：不给控件。裁完还能改，等于让人以为判决可以随手推翻。
     类名用 closed 不用 done —— done 已被「本行已填写」占用（见上方 .item.done）。 */
  .item.closed{opacity:.78}
  .item.closed .tag{flex:none;font-size:10.5px;padding:2px 8px;border-radius:10px;
        background:rgba(67,192,138,.14);color:var(--ok);
        font-family:ui-monospace,Consolas,monospace;margin-left:8px}
  .item.closed .verdict{margin-top:9px;padding:9px 12px;border-radius:7px;
        background:rgba(67,192,138,.07);border-left:2px solid var(--ok);
        font-size:13px;line-height:1.75;color:#cfe3d8}
  .item.closed .verdict b{color:var(--ok)}
  body[data-all-done="1"] #unlock{display:none}
  body[data-all-done="1"] .locked-tip{display:none}
  .all-done-tip{display:none;font-size:12.5px;color:var(--ok);margin:0 0 12px}
  body[data-all-done="1"] .all-done-tip{display:block}
  body[data-all-done="1"] #reset{display:none}
  body[data-all-done="1"] #copy{display:none}
</style></head><body data-view-init="1" data-stage="%(stage_attr)s" data-all-done="%(all_done)s" data-mkview="1" data-src="%(src_name)s" data-src-md5="%(src_md5)s"><div class="wrap">

<header>
  <div>
    <h1>%(title_html)s</h1>
    <div class="sub">%(subtitle_html)s</div>
  </div>
  <span id="badge">初始态 · 未填写</span>
</header>

<div class="bar">
  <span>共 <b>%(n)s</b> 条</span>
  <span class="grow"></span>
  <button id="unlock" class="primary">我已读完，解锁作答</button>
  <button id="reset">复位</button>
</div>
<p class="locked-tip">现在是<b>只读阶段</b>：开关是锁的。先从头看一遍问题，看完再点「解锁作答」。——没读完就勾，勾的是印象不是判断。</p>
<p class="all-done-tip"><b>这一批已经全部裁完。</b>此件自此是裁决记录，不再接受作答；要改结论，改清单再重生成。</p>

%(items)s

<div class="out">
  <h2><span>回执（整段复制走）</span>
    <span><button id="copy">复制</button></span>
  </h2>
  <pre id="txt" title="点一下可全选，再按 Ctrl+C"></pre>
  <div class="copytip" id="copytip"></div>
  <div class="miss" id="miss"></div>
</div>

<div class="note-btm">
  刷新即归零，不往浏览器里存任何东西。回执是纯文本，直接粘贴即可，不必复述「我选了第几个」。<br>
  本页由清单生成，请勿手改——要改就改源清单再重生成，否则下次重生成会覆盖你手改的部分。
</div>

<script>
(function(){
  var body = document.body;
  var STAGED = %(stage_js)s;
  var items = Array.prototype.slice.call(document.querySelectorAll('.item'));
  var badge = document.getElementById('badge');
  var txt = document.getElementById('txt');
  var miss = document.getElementById('miss');
  var btnUnlock = document.getElementById('unlock');

  // 复位基线只有一个来源：HTML 声明值（checked / 默认文本）。不拿加载时快照当基线。
  function baseline(){
    document.querySelectorAll('input[type=radio],input[type=checkbox]').forEach(function(el){
      el.checked = el.defaultChecked;
    });
    document.querySelectorAll('textarea').forEach(function(el){
      el.value = el.defaultValue;
    });
  }

  function lockAll(){
    document.querySelectorAll('input,textarea').forEach(function(el){ el.disabled = true; });
  }
  function unlockAll(){
    document.querySelectorAll('input,textarea').forEach(function(el){ el.disabled = false; });
  }

  function stageTo(s){
    body.dataset.stage = s;
    if (s === 'fill') { unlockAll(); btnUnlock.disabled = true; btnUnlock.textContent = '已解锁'; }
    else { lockAll(); btnUnlock.disabled = false; btnUnlock.textContent = '我已读完，解锁作答'; }
  }

  // closed 行没有 input 也没有 textarea，取值必须逐个防 null，否则整页脚本直接崩。
  function collect(){
    return items.map(function(it, i){
      var closed = it.classList.contains('closed');
      var checked = it.querySelector('input:checked');
      var ta = it.querySelector('textarea');
      var noEl = it.querySelector('.no');
      var qtEl = it.querySelector('.qt');
      return {
        i: i,
        no: noEl ? noEl.textContent.trim() : (it.dataset.no || ''),
        q: qtEl ? qtEl.textContent.trim() : '',
        closed: closed,
        ans: checked ? checked.value : '',
        note: (ta && ta.value ? ta.value : '').trim()
      };
    });
  }

  function render(){
    var all = collect();
    // 已裁行不参与作答统计——它们本来就没有控件，算进 missing 会永远差几条。
    var rows = all.filter(function(r){ return !r.closed; });
    var missing = rows.filter(function(r){ return !r.ans; }).map(function(r){ return r.no; });
    var filled = rows.filter(function(r){ return r.ans; }).length;

    var lines = rows.filter(function(r){ return r.ans; }).map(function(r){
      return r.no + '｜' + r.ans + (r.note ? '｜备注：' + r.note : '');
    });
    txt.textContent = lines.length
      ? lines.join('\\n')
      : (rows.length ? '（还没作答。选完会在这里生成，整段复制走。）'
                     : '（这一批已全部裁完，没有待作答项。结论在各表与清单的「裁决」列里。）');

    if (missing.length) {
      // 用 innerHTML 而不是 textContent：这里要出粗体，而 textContent 会把 ** 原样显示
      // （2026-11-01 实测截图里就写着「回执**不完整**」）。拼进去的只有编号，是生成的，安全。
      miss.innerHTML = '还差 <b>' + missing.length + '</b> 条没答：' + missing.join('、')
        + '。现在这份回执<b>不完整</b>，别拿去当结论。';
    } else {
      miss.textContent = '';
    }

    all.forEach(function(r){ if (!r.closed) items[r.i].classList.toggle('done', !!r.ans); });

    if (body.dataset.allDone === '1') {
      badge.textContent = '全部已裁 · 记录';
      badge.className = '';
      return;
    }

    var stage = body.dataset.stage;
    if (stage === 'read') {
      badge.textContent = '只读 · 未填写';
      badge.className = '';
    } else if (!filled) {
      badge.textContent = '已解锁 · 未填写';
      badge.className = 'dirty';
    } else {
      badge.textContent = '已改动 ' + filled + ' 项';
      badge.className = 'dirty';
    }

    // 没答任何一条时，复制按钮是假的——它会复制那句占位提示，
    // 用户粘出来不是回执（2026-11-01 作者实测踩到，而且没报错）。
    var btnCopy = document.getElementById('copy');
    btnCopy.disabled = !filled;
    btnCopy.textContent = filled ? '复制' : '先作答';
    btnCopy.title = filled ? '' : '还没答任何一条，没有可复制的回执';
  }

  function hardReset(){
    baseline();
    if (STAGED) {
      stageTo('read');
    } else {
      body.dataset.stage = 'fill';
      unlockAll();
      btnUnlock.style.display = 'none';
    }
    render();
  }

  btnUnlock.addEventListener('click', function(){ stageTo('fill'); render(); });
  document.getElementById('reset').addEventListener('click', hardReset);
  document.addEventListener('input', render);
  document.addEventListener('change', render);

  document.getElementById('copy').addEventListener('click', function(){
    var t = txt.textContent;
    var b = document.getElementById('copy');
    var tip = document.getElementById('copytip');

    function ok(){ tip.className = 'copytip'; b.textContent = '已复制';
      setTimeout(function(){ b.textContent = '复制'; }, 1600); }

    function selectAll(){
      var r = document.createRange(); r.selectNodeContents(txt);
      var s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
    }

    function fail(){
      // 走到这里说明两套 API 都被拒了（预览面板的 iframe 常这样）。
      // 这时**不能只闪一下提示就完事**——用户会以为复制成功了，直接去粘贴，
      // 粘出来的是上一次剪贴板里的东西（2026-11-01 作者实测，粘出的是测试数据）。
      selectAll();
      tip.className = 'copytip show';
      tip.textContent = '浏览器拦了自动复制（预览面板里常见）。上面的回执已经全选好了 —— 按 Ctrl+C 即可。';
      b.textContent = '按 Ctrl+C';
    }

    function legacy(){
      var done = false;
      try {
        var ta = document.createElement('textarea');
        ta.value = t;
        ta.style.position = 'fixed';
        ta.style.top = '-1000px';
        ta.setAttribute('readonly', '');
        document.body.appendChild(ta);
        ta.select();
        ta.setSelectionRange(0, t.length);
        done = document.execCommand('copy');
        document.body.removeChild(ta);
      } catch (e) { done = false; }
      if (done) { ok(); } else { fail(); }
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(t).then(ok).catch(legacy);
    } else {
      legacy();
    }
  });

  // 点回执区就全选——给「自动复制被拦」留一条不用动脑的路：
  // 点一下、按 Ctrl+C，两步，不需要知道哪里有按钮。
  txt.addEventListener('click', function(){
    var r = document.createRange(); r.selectNodeContents(txt);
    var s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
  });

  // 三处归位：首次解析、资源加载完、从 bfcache 前进/后退回来
  document.addEventListener('DOMContentLoaded', hardReset);
  window.addEventListener('load', hardReset);
  window.addEventListener('pageshow', hardReset);
})();
</script>
</body></html>
"""


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    src = args[0]
    out = None
    title = None
    mode = "t1"
    custom_opts = None
    stage = True

    i = 1
    while i < len(args):
        a = args[i]
        if a in ("-o", "--out"):
            i += 1
            out = args[i]
        elif a == "--title":
            i += 1
            title = args[i]
        elif a == "--mode":
            i += 1
            mode = args[i].lower()
        elif a == "--options":
            i += 1
            custom_opts = [c.strip() for c in re.split(r"[/／、]", args[i]) if c.strip()]
        elif a == "--no-stage":
            stage = False
        i += 1

    if not os.path.exists(src):
        print("✗ 找不到输入文件：%s" % src)
        return 2
    text = io.open(src, encoding="utf-8", errors="replace").read()
    rows, headers = parse_table(text)

    if not rows:
        print("✗ 这份文件里没有能认出来的清单表格。")
        print("  需要的是一张 md 表格，且表头里必须有「问题」或「条目」列。")
        print("  认出来的表头：%s" % (headers or "（没有表）"))
        print("  这不是「清单是空的」，是「判据没对上」——两者要分开看。")
        return 2

    opts = custom_opts or MODES.get(mode, MODES["t1"])
    if title is None:
        title = os.path.splitext(os.path.basename(src))[0]
    # 副标题只在真有条目用缺省选项时才提缺省——逐条都写了选项还提，是噪音。
    done = sum(1 for r in rows if r["verdict"])
    subtitle = "由清单生成 ｜ %d 条" % len(rows)
    if done:
        subtitle += " ｜ 已裁 %d" % done
    if any((not r["opt"]) and (not r["verdict"]) for r in rows):
        subtitle += " ｜ 缺省选项 %s" % "／".join(opts)

    if out is None:
        d = os.path.dirname(os.path.abspath(src))
        out = os.path.join(d, "[视图]%s.html" % os.path.splitext(os.path.basename(src))[0])

    html_text = build(rows, title, subtitle, opts, stage,
                      src_name=os.path.basename(src), src_md5v=src_md5(text))
    with io.open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(html_text)

    print("✅ 生成：%s" % out)
    n_own = sum(1 for r in rows if r["opt"])
    if n_own == len(rows):
        opt_desc = "逐条自定"
    elif n_own == 0:
        opt_desc = "／".join(opts)
    else:
        opt_desc = "%s（另有 %d 条自定）" % ("／".join(opts), n_own)
    print("   条数 %d ｜ 选项 %s ｜ 两阶段 %s" % (len(rows), opt_desc, "开" if stage else "关"))
    print("   源指纹 %s —— 清单再改而没重生成，视图就停在改之前的版本上。"
          "（本项目有 `_consist` 会报过期；新项目没有它，只能靠这条提醒。）" % src_md5(text))
    print("   [scope] 只生成了形态；内容对不对、选项合不合适，它不判。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
