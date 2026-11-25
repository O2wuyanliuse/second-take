# -*- coding: utf-8 -*-
"""尺子：白名单与 export-ignore 不许再打架（2026-11-25 外援复审 R5-1）。

来由：0.4.x 的包带了两份本不该带的 `Agent框架/` 文件。当时两条路并存——
`.gitattributes` 里 export-ignore、`publish_manifest.txt` 里不在清单——而没人查两边
是否一致。机器只认清单，注释里那套「兜底」就成了假话：读的人会以为它是第二份清单。

现在定死一条：**包内容只由 `publish_manifest.txt` 决定，`.gitattributes` 不再是第二份
清单**。这条尺子钉三件事：
  1) 清单要发的东西，不许同时在 `.gitattributes` 里带 export-ignore（两边矛盾时，
     谁对没人说得清，只有一条路才不会分叉）；
  2) 曾经被「项目层」说法挡在包外的两份，现在明确在清单里——不许悄悄退出；
  3) 那两份文件的正文里不再出现「不进分发包」「本版不随包」（改了机制，话也得跟着改）。

不测「export-ignore 总条数等于 0」：以后真有正当理由加一条（比如临时压一个不该发的
大件），这条尺子要能继续用，而不必连它一起改。
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "publish_manifest.txt"
ATTRIBUTES = REPO / ".gitattributes"

# 曾被 export-ignore 挡在包外的两份（2026-11-21 中性化 → 11-25 明确留包内）
FORMERLY_EXCLUDED = [
    "Agent框架/13_外部环节接入契约_v0.1.md",
    "Agent框架/同步防断_v1.md",
]

STALE_PHRASES = ["不进分发包", "本版不随包"]


def translate(pat):
    """把清单里的通配写法翻成正则；与 tools/build_public_package.py 同一套语义，
    故意各写一份——尺子跟着被量的东西一起改，就量不出偏差了。"""
    out, i = [], 0
    while i < len(pat):
        c = pat[i]
        if c == "*":
            if i + 1 < len(pat) and pat[i + 1] == "*":
                out.append(".*")
                i += 2
                if i < len(pat) and pat[i] == "/":
                    i += 1
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def manifest_includes():
    """清单里「要发」的那部分（`!` 开头是排除，不算）。"""
    inc = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("!"):
            continue
        if s.endswith("/"):
            s = s + "**"
        inc.append(translate(s))
    return inc


def export_ignore_paths():
    """`.gitattributes` 里带 export-ignore 的路径（按空白切，第一段是路径）。"""
    paths = []
    for line in ATTRIBUTES.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        tokens = s.split()
        if "export-ignore" in tokens[1:]:
            paths.append(tokens[0])
    return paths


def test_manifest_and_export_ignore_do_not_intersect():
    """清单要发的，不许同时被 export-ignore 挡着。"""
    inc = manifest_includes()
    ei = export_ignore_paths()
    overlap = [p for p in ei if any(r.match(p) for r in inc)]
    assert overlap == [], (
        "这些路径既在 publish_manifest.txt 里，又被 .gitattributes export-ignore 挡着："
        + ", ".join(overlap)
    )


def test_formerly_excluded_two_are_in_manifest():
    """被争论过的那两份，现在必须还在清单里（留包内是 11-21 起的裁定）。"""
    inc = manifest_includes()
    missing = [p for p in FORMERLY_EXCLUDED if not any(r.match(p) for r in inc)]
    assert missing == [], "清单里找不到本该随包发的：" + ", ".join(missing)


def test_no_stale_layer_phrases_in_those_files():
    """机制删了，话也得改：这两份不再自称「项目层／不进分发包」。"""
    bad = []
    for rel in FORMERLY_EXCLUDED:
        text = (REPO / rel).read_text(encoding="utf-8")
        for phrase in STALE_PHRASES:
            if phrase in text:
                bad.append("%s：%s" % (rel, phrase))
    assert bad == [], "仍在说旧机制：" + "；".join(bad)
