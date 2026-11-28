# -*- coding: utf-8 -*-
"""jimeng_bench 本地服务的四道门：来源、类型、体积、参数。

2026-11-24 安全复核 P1–P5 的回归：本地服务开着时，任意网页能跨站 POST 过来，
去掉 dry_run 就是真调 CLI、真花钱。这四条用例钉的就是这个。

**不测 CLI**：`run_cli` 要真装 dreamina，这里只测「门」——请求根本走不到那一步。
"""

import importlib.util
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load_server():
    spec = importlib.util.spec_from_file_location(
        "jimeng_server", REPO / "tools" / "jimeng_bench" / "server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_origin_must_be_loopback():
    mod = load_server()
    assert mod.origin_ok(None) is True, "curl / 同源 GET 没有 Origin，不该拦"
    assert mod.origin_ok("http://127.0.0.1:8765") is True
    assert mod.origin_ok("http://localhost:9999") is True
    assert mod.origin_ok("https://evil.example") is False
    assert mod.origin_ok("http://127.0.0.1.evil.example") is False, "lookalike 域名不算 loopback"


def test_safe_path_blocks_parent_and_sibling_prefix(tmp_path):
    mod = load_server()
    base = tmp_path / "runs"
    base.mkdir()
    (base / "ok.png").write_bytes(b"x")
    sib = tmp_path / "runs2"
    sib.mkdir()
    (sib / "x.png").write_bytes(b"x")

    assert mod.safe_path(base, "ok.png") is not None
    assert mod.safe_path(base, "../runs2/x.png") is None, "前缀兄弟目录必须挡住"
    assert mod.safe_path(base, "../../etc/passwd") is None
    assert mod.safe_path(base, "ok.png", (".md",)) is None, "后缀白名单外要拒"


def test_safe_path_rejects_absolute(tmp_path):
    mod = load_server()
    base = tmp_path / "runs"
    base.mkdir()
    assert mod.safe_path(base, str(tmp_path / "outside.txt")) is None


def test_origin_https_loopback_allowed():
    """TLS 反代套在前面时，Origin 会是 https——回环仍然算本机。

    方案里这条是「可选」：本服务是明文 http.server，眼下没有 https 部署。
    但放着不测，哪天有人遇到反代就顺手改一行、也没人知道被改过。
    """
    mod = load_server()
    assert mod.origin_ok("https://127.0.0.1:8765") is True
    assert mod.origin_ok("https://localhost:8765") is True
    assert mod.origin_ok("http://127.0.0.1:8765") is True
    assert mod.origin_ok("https://evil.example") is False, "https 不等于可信"


def test_validate_bad_num_does_not_raise():
    """P4：`num="x"` 不能让请求断连，要变成一条可读的校验错。"""
    mod = load_server()
    errs = mod.validate({"num": "x", "width": 1024, "height": 1024})
    assert any("数量" in e for e in errs), errs


def serve(mod):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), mod.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def post(port, body=b"{}", ctype="application/json", origin=None, length=None):
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Content-Type": ctype}
    if origin:
        headers["Origin"] = origin
    if length is not None:
        headers["Content-Length"] = str(length)
    try:
        conn.request("POST", "/api/generate", body=body, headers=headers)
        r = conn.getresponse()
        return r.status, r.read()
    except Exception as e:
        # 诊断底线（不 retry 掩盖）：摆出端口与异常原文，便于定位偶发。
        # Windows 回环上服务端早拒（403/415/413）后按 HTTP/1.0 关连接，若请求体
        # 未被读尽，关连接会触发 RST，客户端在 getresponse 处偶发 WinError 10053。
        raise AssertionError(f"POST 127.0.0.1:{port} 失败：{type(e).__name__}: {e}") from e
    finally:
        conn.close()


def get(port, path):
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", path)
        r = conn.getresponse()
        return r.status, r.read()
    finally:
        conn.close()


def test_prompt_traversal_is_400():
    """路由层也必须挡，不能只靠「调用方记得用 safe_path」。

    上面那条测的是函数本身；这条测的是 `/api/prompt` 真的调了它——
    哪天有人图省事把路由改回拼路径，函数还在、门却没了。
    """
    mod = load_server()
    httpd, port = serve(mod)
    try:
        status, _ = get(port, "/api/prompt?file=../../../../README.md")
        assert status == 400, "越界文件名必须 400，不能回 200 空清单"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_post_rejects_non_json_content_type():
    mod = load_server()
    httpd, port = serve(mod)
    try:
        # 空体：ctype 门在读体之前就拒（415），体内容与本断言无关。留实体会让
        # 服务端早拒关连接时因「体未读尽」在 Windows 回环触发 RST（客户端偶发
        # WinError 10053）；空体去掉这个 incidental 触发器，断言口径不变。
        status, _ = post(port, b"", ctype="text/plain")
        assert status == 415, "text/plain 是免预检的简单请求，必须拒"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_post_rejects_cross_site_origin():
    mod = load_server()
    httpd, port = serve(mod)
    try:
        # 空体同理：origin 门（403）也在读体之前拒，去掉未读尽体触发的回环 RST。
        status, _ = post(port, b"", origin="https://evil.example")
        assert status == 403
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_post_rejects_huge_body():
    mod = load_server()
    httpd, port = serve(mod)
    try:
        status, _ = post(port, b"", length=2_000_000)
        assert status == 413, "声明 2 MB 就该在 read 之前拒掉"
    finally:
        httpd.shutdown()
        httpd.server_close()
