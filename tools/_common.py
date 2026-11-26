#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools 内部共享的小工具。

与同目录脚本一起用，别单独拷：单拷走会报 ModuleNotFoundError。
"""

import hashlib
import importlib.util
import sys


def pytest_available():
    """是否装了 pytest（只查 module，不实际运行）。"""
    try:
        return importlib.util.find_spec("pytest") is not None
    except (ImportError, ValueError):
        return False


def utf8_stdio():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass  # 吞：输出流不支持 reconfigure 时保留原编码，不让输出配置阻断检查。


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()
