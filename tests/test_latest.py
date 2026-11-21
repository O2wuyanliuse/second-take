# -*- coding: utf-8 -*-
"""发版三处同源：VERSION ／ latest.json ／ tag。

这五条不是你项目的判据，是本仓库自己的**发版记录不能自相矛盾**。
它们读的是真实仓库，所以任何一次手改 VERSION 或 latest.json 都会在这里露头。
"""

import json
import re

from helpers import REPO

VERSION_TEXT = (REPO / "VERSION").read_text(encoding="utf-8").strip()
LATEST = json.loads((REPO / "latest.json").read_text(encoding="utf-8"))


def vtuple(s):
    return tuple(int(x) for x in s.split("."))


def test_version_and_latest_agree():
    assert VERSION_TEXT, "VERSION 是空的"
    version = VERSION_TEXT.split()[0]
    assert LATEST["version"] == version, "VERSION 与 latest.json 的 version 不一致"


def test_version_file_carries_release_date():
    parts = VERSION_TEXT.split("·")
    assert len(parts) == 2, "VERSION 应写成 `X.Y.Z · YYYY-MM-DD`"
    assert parts[1].strip() == LATEST["date"]


def test_notes_url_points_at_this_version():
    assert LATEST["notes_url"].endswith("/releases/tag/v%s" % LATEST["version"])


def test_pack_urls_are_versioned_assets():
    packs = LATEST.get("pack_urls") or {}
    assert packs, "pack_urls 不能为空——空对象等于用户点不到下载"
    for key, url in packs.items():
        assert key.strip(), "pack_urls 的 key 不能是空串"
        assert "/v%s/" % LATEST["version"] in url, "%s 指向的不是本版本" % key
        assert url.endswith(".zip"), "%s 不是 zip" % key


def test_min_client_and_channel_are_sane():
    assert LATEST["channel"] in ("stable", "beta", "alpha")
    assert LATEST["severity"] in ("normal", "important", "critical")
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", LATEST["date"])
    assert vtuple(LATEST["min_client"]) <= vtuple(LATEST["version"]), "min_client 不能高于当前版本"
