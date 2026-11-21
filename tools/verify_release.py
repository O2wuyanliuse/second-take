# -*- coding: utf-8 -*-
"""second-take 发布前核验：只读。不改文件、不推远端、不建 release。

用法：
  卡点核验.py                       # 自动找仓库与待发 zip
  卡点核验.py --repo D:/dev/second-take --zip D:/dev/second-take-0.5.1-win.zip
  卡点核验.py --no-history           # 跳过历史扫描（快）
  卡点核验.py --words 私库词表.txt    # 词表不在库里时从这里读

退出码：0 = 绿（可以按发布按钮）；1 = 红（不许推）；2 = 黄（有未判项，也不许推）。
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import unicodedata
import zipfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

GREEN, RED, YELLOW = "绿", "红", "黄"
DENY = "packaging/public_denylist.txt"
WORDS_FILE = DENY
NOISE = (".git/",)
TEXT_EXT = (".md", ".txt", ".py", ".json", ".yml", ".yaml", ".cfg", ".ini", ".toml", ".ps1", ".bat", ".sh", ".html", ".css", ".js")


def find_git(explicit=None):
    if explicit:
        return explicit
    w = shutil.which("git")
    if w:
        return w
    for c in (
        "C:/Program Files/Git/cmd/git.exe",
        "C:/Program Files (x86)/Git/cmd/git.exe",
    ):
        if Path(c).exists():
            return c
    return None


class Repo:
    def __init__(self, root, git):
        self.root = Path(root)
        self.git = git

    def run(self, args):
        p = subprocess.run(
            [self.git, "-c", "core.quotepath=false"] + list(args),
            cwd=str(self.root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out = p.stdout.decode("utf-8", "replace")
        return p.returncode, out

    def ok(self, args):
        rc, out = self.run(args)
        return rc == 0, out.strip()


def parse_words(text):
    """一行一个词；`#` 注释与 `[类别]` 行跳过。"""
    words = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("[") and s.endswith("]"):
            continue
        words.append(s)
    return words


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_zip(path, words):
    """返回 (文件数, 命中列表, 是否含词表, 可疑项列表)"""
    hits = {}
    suspicious = []
    names = []
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            names.append(info.filename)
            low = info.filename.lower()
            if "config.local.json" in low or low.startswith("workspace/"):
                suspicious.append(info.filename)
            if not low.endswith(TEXT_EXT):
                continue
            try:
                data = z.read(info).decode("utf-8", "replace")
            except Exception:
                continue
            lowdata = data.lower()
            for w in words:
                if w.lower() in lowdata:
                    for i, line in enumerate(data.splitlines(), 1):
                        if w.lower() in line.lower():
                            hits[(info.filename, i)] = line.strip()[:80]
    has_deny = any(n.lower() == DENY.lower() or n.lower().endswith("/" + DENY.lower()) for n in names)
    flat = sorted((k[0], k[1], v) for k, v in hits.items())
    return len(names), flat, has_deny, suspicious


def scan_history(repo, words, limit=6):
    rc, revs = repo.run(["rev-list", "HEAD"])
    revs = revs.split()
    if not revs:
        return 0, []
    hits = {}
    for w in words:
        rc, out = repo.run(["grep", "-n", "-i", "-F", "-e", w] + revs + ["--"])
        if rc not in (0, 1):
            continue
        for line in out.splitlines():
            parts = line.split(":", 3)
            if len(parts) < 4:
                continue
            commit, path, lineno, text = parts
            key = (path, lineno, text.strip()[:60])
            hits.setdefault(key, set()).add(commit[:7])
    items = sorted(hits.items(), key=lambda kv: kv[0][0])
    return len(items), [(k[0], k[1], k[2], sorted(v)) for k, v in items][:limit]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("SECOND_TAKE_REPO", "D:/dev/second-take"))
    ap.add_argument("--zip", default="")
    ap.add_argument("--words", default="")
    ap.add_argument("--git", default="")
    ap.add_argument("--no-history", action="store_true")
    ap.add_argument("--no-zip", action="store_true", help="只判树与历史，不判包（CI 打包前用）")
    ap.add_argument("--expect-tag", default="", help="CI 用：tag 名必须与最新 tag 一致")
    a = ap.parse_args()

    rows = []
    def row(name, detail, verdict):
        rows.append((name, detail, verdict))

    git = find_git(a.git)
    if not git:
        row("git", "找不到 git 命令", YELLOW)
        return report(rows, "D:/dev/second-take", "")

    repo = Repo(a.repo, git)
    exists, _ = repo.ok(["rev-parse", "--git-dir"])
    if not exists:
        row("仓库", str(a.repo) + " 不是 git 仓库", RED)
        return report(rows, a.repo, "")

    _, head = repo.ok(["rev-parse", "--short", "HEAD"])
    rc, _ = repo.run(["rev-parse", "--verify", "HEAD"])

    # 1 工作区
    _, st = repo.ok(["status", "--porcelain"])
    dirty = [l for l in st.splitlines() if l.strip() and not l.startswith("??")]
    row("1 工作区", ("干净" if not dirty else str(len(dirty)) + " 个改动未提交"), GREEN if not dirty else RED)

    # 2 版本三处
    _, ver_raw = repo.ok(["show", "HEAD:VERSION"])
    ver = ver_raw.lstrip("\ufeff").split("·")[0].strip() if ver_raw else ""
    _, latest_raw = repo.ok(["show", "HEAD:latest.json"])
    try:
        latest = json.loads(latest_raw.lstrip("\ufeff"))
        lver = str(latest.get("version", ""))
    except Exception:
        lver = ""
    _, tags_raw = repo.ok(["tag", "-l", "v*"])
    tags = sorted(tags_raw.split(), key=lambda s: [int(x) if x.isdigit() else x for x in s.replace("v", "").replace("-", ".").split(".")])
    last_tag = tags[-1] if tags else ""
    tag_ver = last_tag[1:] if last_tag.startswith("v") else last_tag
    vers = {ver, lver, tag_ver}
    v_ok = ver != "" and len(vers) == 1
    row("2 版本一致", "VERSION " + (ver or "?") + " / latest " + (lver or "?") + " / 最新 tag " + (last_tag or "无"), GREEN if v_ok else RED)

    # 3 标记类型与指向
    if last_tag:
        _, ttype = repo.ok(["cat-file", "-t", last_tag])
        _, tcommit = repo.ok(["rev-parse", last_tag + "^{commit}"])
        annotated = ttype.strip() == "tag"
        points_head = tcommit.strip() == repo.ok(["rev-parse", "HEAD"])[1].strip()
        detail = ttype.strip() + " / 指向 " + tcommit[:7] + (" = HEAD" if points_head else " ≠ HEAD")
        row("3 标记", detail, GREEN if (annotated and points_head) else RED)
    else:
        row("3 标记", "没有任何 tag", YELLOW)

    if a.expect_tag:
        same = a.expect_tag == last_tag
        row("3b CI tag", "触发 tag " + a.expect_tag + " / 最新 tag " + (last_tag or "无"), GREEN if same else RED)

    # 词表
    words = []
    src = ""
    if a.words:
        p = Path(a.words)
        if p.exists():
            words = parse_words(p.read_text(encoding="utf-8", errors="replace"))
            src = "外部词表 " + str(p)
    _, rc_deny = repo.ok(["cat-file", "-e", "HEAD:" + WORDS_FILE])
    if not words:
        rc, deny_text = repo.run(["show", "HEAD:" + WORDS_FILE])
        if rc == 0:
            words = parse_words(deny_text)
            src = "库内词表 " + WORDS_FILE
    if not words:
        row("4 词表", "没有找到禁用词表（库内没有，也没给 --words）", YELLOW)
    else:
        row("4 词表", str(len(words)) + " 个词 · 来源 " + src, GREEN)

    # 5 禁用词表本身是否在库里（它自含词形，一公开就泄一次）
    deny_exists = repo.ok(["cat-file", "-e", "HEAD:" + WORDS_FILE])[0]
    if deny_exists:
        row("5 词表在库", WORDS_FILE + " 存在于 HEAD（它必须写出禁用词，所以它自己就带一个）", RED)
    else:
        row("5 词表在库", "不在库里（这是对的设计）", GREEN)

    # 6 待发 zip
    if a.no_zip:
        row("6 包形状", "已跳过（CI 打包前，--no-zip）", GREEN)
    else:
        zip_path = Path(a.zip) if a.zip else None
        if zip_path is None and ver:
            cand = Path("D:/dev/second-take-" + ver + "-win.zip")
            if cand.exists():
                zip_path = cand
        if zip_path and zip_path.exists():
            zsize = zip_path.stat().st_size
            zsha = sha256_of(zip_path)
            nfiles, zhits, has_deny, susp = scan_zip(zip_path, words)
            row("6 包形状", str(nfiles) + " 个文件 · " + str(zsize) + " B · sha256 " + zsha[:8], GREEN if not susp else RED)
            row("7 包内禁用词", ("0 处" if not zhits else str(len(zhits)) + " 处"), GREEN if not zhits else RED)
            row("8 词表进包", ("在包里（不许）" if has_deny else "不在包里"), RED if has_deny else GREEN)
            for fn, ln, text in zhits[:5]:
                row("", fn + ":" + str(ln) + " " + text, RED)
            for fn in susp[:5]:
                row("", "不该进包: " + fn, RED)
        else:
            row("6 包形状", "找不到待发 zip" + ("" if a.zip else "（自动找 D:/dev/second-take-" + (ver or "x") + "-win.zip）"), YELLOW)

    # 9 历史
    if words and not a.no_history:
        n, items = scan_history(repo, words)
        row("9 历史命中", str(n) + " 处（全历史，" + str(len((repo.ok(["rev-list", "HEAD"])[1]).split())) + " 个提交）", GREEN if n == 0 else RED)
        for path, ln, text, commits in items:
            row("", path + ":" + str(ln) + " " + text + " @ " + ",".join(commits), RED)
    elif words:
        row("9 历史命中", "已跳过（--no-history）", YELLOW)

    verdict = RED if any(r[2] == RED for r in rows) else (YELLOW if any(r[2] == YELLOW for r in rows) else GREEN)
    return report(rows, str(a.repo), head, verdict)


def dwidth(s):
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)


def pad(s, n):
    return s + " " * max(0, n - dwidth(s))


def report(rows, repo_path, head, verdict=None):
    w1 = max((dwidth(r[0]) for r in rows), default=4)
    w2 = max((dwidth(r[1]) for r in rows), default=40)
    w2 = min(max(w2, 40), 68)
    print("")
    print("second-take 发布前核验（只读）")
    print("仓库  " + repo_path)
    print("HEAD  " + (head or "?"))
    print("-" * 60)
    for name, detail, v in rows:
        print("  " + pad(name, w1) + "  " + pad(detail, w2) + "  " + v)
    print("-" * 60)
    final = verdict
    if final is None:
        final = RED if any(r[2] == RED for r in rows) else (YELLOW if any(r[2] == YELLOW for r in rows) else GREEN)
    if final == GREEN:
        print("结论  绿 · 可以按发布按钮")
        return 0
    if final == RED:
        print("结论  红 · 不许推。红了就是错了，不要解释，去改。")
        return 1
    print("结论  黄 · 有未判项（缺件／跳过检查），也不许推。")
    return 2


if __name__ == "__main__":
    sys.exit(main())
