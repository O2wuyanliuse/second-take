#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools 内部共享的小工具。

与同目录脚本一起用，别单独拷：单拷走会报 ModuleNotFoundError。
"""

import importlib.util
import sys


def pytest_available():
    """是否装了 pytest（只查 module，不实际运行）。"""
    try:
        return importlib.util.find_spec("pytest") is not None
    except Exception:
        return False


def utf8_stdio():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
