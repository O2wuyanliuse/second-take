# -*- coding: utf-8 -*-
"""即梦出图工作台 · 甲档

完整说明（维护仓，不随包）：docs/maintain/代码内长文档/tools/jimeng_bench/server.py.md
"""

import json
import re
import shutil
import statistics
import subprocess
import sys
import threading
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent.parent          # 项目根（本工具置于 <项目根>/tools/jimeng_bench/）
RUNS = ROOT / "runs"
RUNS.mkdir(exist_ok=True)

HOST = "127.0.0.1"
PORT = 8765

# 只接受**本机来源**。端口不写死（可以换端口跑，测试也起在 0 端口），但 host 必须是 loopback。
# 不加这一条，任何网页都能跨站 POST 过来——本地服务开着的时候等于开了个后门，
# 去掉 dry_run 就是真调 CLI、真花钱（2026-11-24 安全复核 P1）。
ALLOWED_HOSTS = ("127.0.0.1", "localhost")
MAX_BODY = 1_000_000          # 1 MB；再大一律 413，不给它吃内存的机会
PROMPT_EXTS = (".md", ".txt")


def origin_ok(origin):
    """同源请求没有 Origin（curl、GET），放行；有 Origin 就必须是 loopback。"""
    if not origin:
        return True
    try:
        o = urlparse(origin)
    except ValueError:
        return False
    return o.scheme in ("http", "https") and o.hostname in ALLOWED_HOSTS


def safe_path(base, name, exts=None):
    """把用户给的文件名解析到 base 下；越界或后缀不对返回 None。

    用 `resolve() + is_relative_to()`，**不用 startswith**：`runs` 与 `runs2` 前缀相同，
    startswith 会把兄弟目录一起放进来（2026-11-24 复核实测：`<runs>/../runs2/x.png` 能过）。
    """
    try:
        base = Path(base).resolve()
        p = (base / name).resolve()
    except (OSError, ValueError):
        return None
    if not p.is_relative_to(base):
        return None
    if exts and p.suffix.lower() not in exts:
        return None
    return p

# 允许的模型档（写死：默认 5.0，不显式写会静默降档，这是 2026-11-09 实测的坑）
MODELS = ["5.0Pro", "5.0", "4.7", "4.6", "4.5", "4.1", "4.0"]

# 每个档一句话。界面要铺开给人看，不是一个裸名字——名字不带信息，人就没法判断该选哪个。
MODEL_META = {
    "5.0Pro": {"tag": "基准", "desc": "项目侧指定为画风基准的那一档；换档会断同源", "ok": True},
    "5.0":    {"tag": "默认", "desc": "CLI 不显式指定就落到这一档，会断同源", "ok": False},
    "4.7":    {"tag": "非基准", "desc": "旧档，无基准对照", "ok": False},
    "4.6":    {"tag": "非基准", "desc": "旧档，无基准对照", "ok": False},
    "4.5":    {"tag": "非基准", "desc": "旧档，无基准对照", "ok": False},
    "4.1":    {"tag": "非基准", "desc": "旧档，无基准对照", "ok": False},
    "4.0":    {"tag": "非基准", "desc": "旧档，无基准对照", "ok": False},
}

# 单价。两个数字都来自实测留痕，不是查来的公开报价。
# 界面把「预估」和「实扣」并排放——差距本身就是信息，藏起来才是黑箱。
PRICE = {
    "est": 5,
    "note": "CLI 实扣读 list_task.credit_count；2026-11-09 两次实测：0（权益额度）与 5（真扣），同档同尺寸",
    "web": 12,
}

# 分辨率档的像素边界（来自 dreamina text2image -h，逐字抄的）
LIMITS = {
    "1k":   {"side": (512, 2016),  "total": 1763584},
    "1.5k": {"side": (972, 2268),  "total": 2359296},
    "2k":   {"side": (768, 3072),  "total": 4194304},
    "4k":   {"side": (1536, 6240), "total": 16777216},
}
# 各模型档允许哪些分辨率
RESO_BY_MODEL = {
    "5.0Pro": ["1.5k", "2k", "4k"],
    "5.0": ["2k", "4k"], "4.7": ["2k", "4k"], "4.6": ["2k", "4k"],
    "4.5": ["2k", "4k"], "4.1": ["2k", "4k"], "4.0": ["2k", "4k"],
}

# 批次预设：**留空**。这是项目数据，不属于通用工具。
#
# 你自己的用法：把「已经在过程表里填过 A 段」的批次按下面格式补进来。
# 每条对应你项目过程表里的一个批次块；改参数要两边一起改，否则一处改了另一处不认。
#
# 格式示例（占位值，照抄后替换）：
#   {
#       "id": "K-01", "label": "K-01 · 这一批要判什么（一句话）",
#       "note": "只判什么、不判什么——边界写不清，一次出图会连不该对的也一起对",
#       "w": 1536, "h": 2048, "reso": "2k", "num": 1, "model": "5.0Pro",
#       "file": "<你的提示词文件>.md", "block": 0,
#       "refs": [],
#   },
BATCHES = []

LOCK = threading.Lock()   # 同一时刻只允许一个任务（CLI 并发上限 3，但这里不冒险）


# ────────────────────────────── CLI ──────────────────────────────

def find_cli():
    """找 dreamina。先 PATH，再 ~/bin 兜底（Windows 安装脚本就装在那）。"""
    hit = shutil.which("dreamina") or shutil.which("dreamina.exe")
    if hit:
        return hit
    cand = Path.home() / "bin" / "dreamina.exe"
    if cand.exists():
        return str(cand)
    return None


def run_cli(args, timeout=300):
    """调 CLI，返回 (ok, dict_or_text)。统一 UTF-8 解码，Windows 上不猜 GBK。"""
    exe = find_cli()
    if not exe:
        return False, {"error": "找不到 dreamina。先 pip install dreamina，再 dreamina login。"}
    try:
        p = subprocess.run(
            [exe] + args,
            capture_output=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        return False, {"error": f"超时（{timeout}s）。任务可能还在跑，去 CLI 用 list_task 查。"}
    out = (p.stdout or "").strip()
    err = (p.stderr or "").strip()
    if p.returncode != 0:
        return False, {"error": err or out or f"退出码 {p.returncode}"}
    try:
        return True, json.loads(out)
    except json.JSONDecodeError:
        return True, {"raw": out}


def get_credit():
    ok, data = run_cli(["user_credit"], timeout=60)
    if ok and isinstance(data, dict):
        return data
    return {"error": data}


# ─────────────────────────── 提示词读取 ───────────────────────────

def list_prompt_files():
    """列出 99_过程稿/预告片 下带提示词块的件。"""
    d = PROJECT / "99_过程稿" / "预告片"
    out = []
    if not d.exists():
        return out
    for f in sorted(d.glob("*.md")):
        try:
            txt = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue  # 吞：单个提示词文件读不到时跳过，继续列其余文件。
        if "赛璐璐硬边动画风格" in txt:
            blocks = [b for b in re.findall(r"```\n(.*?)\n```", txt, re.S)
                      if "赛璐璐硬边动画风格" in b]
            out.append({"file": f.name, "blocks": len(blocks)})
    return out


def read_prompt_blocks(name):
    """读一个件里的全部提示词块，按出现顺序编号。越界或后缀不对返回 []。"""
    f = safe_path(PROJECT / "99_过程稿" / "预告片", name, PROMPT_EXTS)
    if f is None or not f.exists():
        return []
    txt = f.read_text(encoding="utf-8", errors="replace")
    blocks = [b.strip() for b in re.findall(r"```\n(.*?)\n```", txt, re.S)
              if "赛璐璐硬边动画风格" in b]
    # 抓每块前面最近的一个标题，当标签用
    labels = []
    for m in re.finditer(r"```\n(.*?)\n```", txt, re.S):
        blk = m.group(1)
        if "赛璐璐硬边动画风格" not in blk:
            continue
        head = txt[:m.start()]
        hs2 = re.findall(r"^##\s+(.+)$", head, re.M)      # 优先二级标题
        hs = re.findall(r"^#{2,4}\s*(.+)$", head, re.M)   # 回退
        pick = hs2[-1] if hs2 else (hs[-1] if hs else None)
        labels.append(pick.strip() if pick else f"块 {len(labels)+1}")
    return [{"label": labels[i] if i < len(labels) else f"块 {i+1}", "text": b}
            for i, b in enumerate(blocks)]


# ─────────────────────────── 图片体检 ───────────────────────────

def inspect_image(path: Path):
    """尺寸 / 四角 / 右下角近白占比 —— 净版判定的那套，和项目里用的同一口径。"""
    info = {"path": str(path), "size_bytes": path.stat().st_size}
    try:
        from PIL import Image
    except ImportError:
        info["note"] = "无 Pillow，跳过统计"
        return info
    im = Image.open(path).convert("RGB")
    w, h = im.size
    info["width"], info["height"] = w, h

    def stats(box):
        reg = im.crop(box)
        px = list(reg.getdata())
        lum = [(r * 299 + g * 587 + b * 114) // 1000 for r, g, b in px]
        return {
            "mean": round(statistics.mean(lum), 1),
            "std": round(statistics.pstdev(lum), 1),
            "near_white_pct": round(sum(1 for v in lum if v > 235) / len(lum) * 100, 3),
        }

    info["corners"] = {
        "左上": stats((0, 0, 120, 80)),
        "右上": stats((w - 120, 0, w, 80)),
        "左下": stats((0, h - 80, 120, h)),
        "右下": stats((w - 200, h - 120, w, h)),
    }
    rb = info["corners"]["右下"]
    # 净版判据：右下角近白 0，且与其它角同量级（防角标）
    others = [info["corners"][k]["mean"] for k in ("左上", "右上", "左下")]
    same_scale = abs(rb["mean"] - statistics.mean(others)) < 40
    info["clean"] = bool(rb["near_white_pct"] < 0.05 and same_scale)
    info["clean_reason"] = ("右下角近白 %.3f%%，与其它角同量级 → 净版"
                            % rb["near_white_pct"]) if info["clean"] else \
                           ("右下角近白 %.3f%% 或与其它角不同量级 → 疑似角标，人工复核"
                            % rb["near_white_pct"])
    return info


# ─────────────────────────── 生成 ───────────────────────────

def validate(req):
    """参数校验。这里每一条都对应一个真踩过的坑，不是形式主义。"""
    errs = []
    model = req.get("model", "")
    reso = req.get("resolution_type", "")
    w = req.get("width")
    h = req.get("height")
    num = req.get("num", 1)

    if model not in MODELS:
        errs.append(f"模型档必须是 {MODELS} 之一")
    if reso not in LIMITS:
        errs.append(f"分辨率档必须是 {list(LIMITS)} 之一")
    if model in RESO_BY_MODEL and reso not in RESO_BY_MODEL.get(model, []):
        errs.append(f"{model} 不支持 {reso}（支持 {RESO_BY_MODEL[model]}）")

    try:
        w, h = int(w), int(h)
    except (TypeError, ValueError):
        errs.append("宽高必须是整数")
        return errs

    try:
        num_i = int(num)
    except (TypeError, ValueError):
        errs.append("数量必须是整数")
    else:
        if not (1 <= num_i <= 10):
            errs.append("数量 1–10")

    if reso in LIMITS:
        lo, hi = LIMITS[reso]["side"]
        cap = LIMITS[reso]["total"]
        if not (lo <= w <= hi):
            errs.append(f"{reso} 每边像素须在 {lo}–{hi}，当前宽 {w}")
        if not (lo <= h <= hi):
            errs.append(f"{reso} 每边像素须在 {lo}–{hi}，当前高 {h}")
        if w * h > cap:
            errs.append(f"{reso} 总像素上限 {cap}，当前 {w*h} 超了 {w*h-cap}（换更高分辨率档，或缩小画幅）")

    if not (req.get("prompt") or "").strip():
        errs.append("提示词为空")

    refs = [r for r in (req.get("refs") or []) if r.strip()]
    if len(refs) > 10:
        errs.append("参考图上限 10 张")
    for r in refs:
        if not Path(r).exists():
            errs.append(f"参考图不存在：{r}")

    return errs


def _build_generate_args(req):
    model = req["model"]
    reso = req["resolution_type"]
    w, h = int(req["width"]), int(req["height"])
    num = int(req["num"])
    prompt = req["prompt"]
    refs = [r for r in (req.get("refs") or []) if r.strip()]
    cmd = "image2image" if refs else "text2image"   # 必须是 str，不是 list（2026-11-09 修）
    args = [cmd, "--prompt", prompt,
            f"--model_version={model}",
            f"--width={w}", f"--height={h}",
            f"--resolution_type={reso}",
            f"--generate_num={num}",
            "--poll=180"]
    if refs:
        args.append("--images")
        args.extend(refs)
    return args, (w, h, num, refs)


def _collect_results(submit_id, outdir):
    results = []
    if submit_id:
        ok2, q = run_cli(["query_result", f"--submit_id={submit_id}",
                          f"--download_dir={outdir}"], timeout=180)
        if ok2 and isinstance(q, dict):
            for item in (q.get("result_json") or {}).get("images", []):
                rel = item.get("path") or ""
                p = Path(rel) if rel else None
                if p and p.exists():
                    results.append(inspect_image(p))
    if not results:
        for p in sorted(outdir.glob("*.png")) + sorted(outdir.glob("*.jpg")):
            results.append(inspect_image(p))
    return results


def _query_real_cost(submit_id):
    # 真正扣了多少只能看 list_task；user_credit 在权益通道下不可靠。
    ok3, lt = run_cli(["list_task"], timeout=90)
    if ok3 and isinstance(lt, list):
        for t in lt:
            if t.get("submit_id") == submit_id:
                return (t.get("commerce_info") or {}).get("credit_count")
    return None


def do_generate(req):
    args, (w, h, num, refs) = _build_generate_args(req)
    started = datetime.now()
    batch = started.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    outdir = RUNS / batch
    outdir.mkdir(parents=True, exist_ok=True)
    credit_before = get_credit()
    ok, data = run_cli(args, timeout=420)
    if not ok:
        return {"ok": False, "batch": batch, "error": data,
                "cmd": " ".join(args[:1] + ["..."]), "credit_before": credit_before}
    submit_id = data.get("submit_id")
    results = _collect_results(submit_id, outdir)
    credit_after = get_credit()
    real_cost = _query_real_cost(submit_id)
    queue_name = ""
    try:
        dbg = (data.get("queue_info") or {}).get("debug_info") or ""
        m = re.search(r'"queue_name":"([^"]+)"', dbg)
        if m:
            queue_name = m.group(1)
    except Exception:
        pass  # 吞：queue_name 只是可选调试字段，解析失败仍返回空串。
    return {
        "ok": True, "batch": batch, "submit_id": submit_id,
        "queue_name": queue_name,
        "requested": {"width": w, "height": h, "model": req["model"], "reso": req["resolution_type"], "num": num,
                      "refs": refs},
        "images": results,
        "credit_before": credit_before, "credit_after": credit_after,
        "real_cost": real_cost,
        "credit_count_present": real_cost is not None,
        "outdir": str(outdir),
        "raw": data,
    }


# ─────────────────────────── HTTP ───────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a):
        pass  # 不往控制台刷日志

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        raw = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
            return self._send(200, html, "text/html; charset=utf-8")
        if u.path == "/api/env":
            return self._send(200, {
                "cli": find_cli(),
                "credit": get_credit(),
                "files": list_prompt_files(),
                "models": MODELS,
                "model_meta": MODEL_META,
                "price": PRICE,
                "batches": BATCHES,
                "limits": {k: {"side": v["side"], "total": v["total"]} for k, v in LIMITS.items()},
                "reso_by_model": RESO_BY_MODEL,
                "project": str(PROJECT),
            })
        if u.path == "/api/image":
            from urllib.parse import unquote
            q = parse_qs(u.query)
            raw = unquote((q.get("path") or [""])[0])
            p = Path(raw)
            try:
                p = p.resolve()
            except Exception:
                return self._send(400, {"error": "路径不合法"})
            # 只放行两个目录，防目录穿越。用 is_relative_to，不用 startswith——
            # `runs` 与 `runs2` 前缀相同，startswith 会把兄弟目录一起放进来。
            allowed = [RUNS.resolve(), (PROJECT / "99_过程稿").resolve()]
            if not any(p.is_relative_to(a) for a in allowed):
                return self._send(403, {"error": "只能读 runs/ 与 99_过程稿/ 下的图"})
            if not p.exists():
                return self._send(404, {"error": "图不存在"})
            ctype = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
            return self._send(200, p.read_bytes(), ctype)
        if u.path == "/api/prompt":
            q = parse_qs(u.query)
            name = (q.get("file") or [""])[0]
            if safe_path(PROJECT / "99_过程稿" / "预告片", name, PROMPT_EXTS) is None:
                return self._send(400, {"error": "文件名不合法（只收该目录下的 .md/.txt）"})
            return self._send(200, {"blocks": read_prompt_blocks(name)})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        # 兜底：没被下面的分支挡住的异常，回一个 JSON 500，
        # 别让客户端只看到「网络错误」（2026-11-24 复核 P4）。
        try:
            self._handle_post()
        except Exception as e:
            self._send(500, {"error": f"服务端内部错误：{e}"})

    def _handle_post(self):
        # 来源与类型：挡跨站，也挡掉 text/plain 这种「免预检的简单请求」。
        if not origin_ok(self.headers.get("Origin")):
            return self._send(403, {"error": "只接受本机页面发来的请求"})
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            return self._send(415, {"error": "只接受 application/json"})

        u = urlparse(self.path)
        if u.path != "/api/generate":
            return self._send(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._send(400, {"error": "Content-Length 不合法"})
        if n > MAX_BODY:
            return self._send(413, {"error": "请求体过大（上限 1 MB）"})
        try:
            req = json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception as e:
            return self._send(400, {"error": f"请求体不是 JSON：{e}"})

        errs = validate(req)
        if errs:
            return self._send(400, {"error": "参数没通过校验（这一步不花钱）", "details": errs})

        # 只校验不执行：公示阶段先跑这个，确认参数合法且 0 花费
        if req.get("dry_run"):
            cmd = "image2image" if [r for r in (req.get("refs") or []) if r.strip()] else "text2image"
            return self._send(200, {
                "ok": True, "dry_run": True, "cmd": cmd,
                "would_run": {
                    "model": req["model"], "width": int(req["width"]),
                    "height": int(req["height"]), "reso": req["resolution_type"],
                    "num": int(req["num"]),
                    "refs": [r for r in (req.get("refs") or []) if r.strip()],
                    "prompt_chars": len(req["prompt"]),
                },
                "note": "参数通过校验。这一步没有调用 CLI，一分未花。",
            })

        if not LOCK.acquire(blocking=False):
            return self._send(429, {"error": "上一个任务还在跑，等它结束"})
        try:
            res = do_generate(req)
        finally:
            LOCK.release()
        return self._send(200, res)


def main():
    if not (ROOT / "ui" / "index.html").exists():
        print("缺 ui/index.html")
        return 1
    cli = find_cli()
    print(f"dreamina : {cli or '未找到（界面会提示）'}")
    print(f"项目根   : {PROJECT}")
    if cli:
        c = get_credit()
        print(f"账号     : {c.get('vip_level','?')} ／ 余额 {c.get('total_credit','?')}")
    print(f"\n→ http://{HOST}:{PORT}   （Ctrl+C 停）\n")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
