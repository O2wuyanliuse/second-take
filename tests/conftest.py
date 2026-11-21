# -*- coding: utf-8 -*-
import pytest

from helpers import new_repo


@pytest.fixture
def sandbox(tmp_path):
    """一个只有 .git 的空目录——被测脚本会在里面自己长出需要的结构。"""
    return new_repo(tmp_path / "repo")
