# -*- coding: utf-8 -*-
"""两份「起点台账」与私库原件必须逐字节相同。

`templates/start/` 是用户包里的起点模板；源仍在 `packaging/templates/`（私库整包链在用）。
同一件事存两份，就必须有尺子量——不然改一份、忘了另一份，包里发的就是旧口径。
"""

import hashlib

from helpers import REPO

PAIRS = [
    ("templates/start/跟进通道.md", "packaging/templates/跟进通道.md"),
    ("templates/start/常量台账.md", "packaging/templates/常量台账.md"),
]


def _sha(rel):
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def test_start_templates_copy_originals():
    for start, src in PAIRS:
        assert (REPO / start).is_file(), "缺少起点模板: %s" % start
        assert (REPO / src).is_file(), "缺少私库原件: %s" % src
        assert _sha(start) == _sha(src), (
            "%s 与 %s 不再逐字节相同——改一份就要同改另一份" % (start, src)
        )
