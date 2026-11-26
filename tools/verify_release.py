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
    pass  # 吞：输出流不支持 reconfigure 时保留原编码，不让输出配置阻断检查。

GREEN, RED, YELLOW = "绿", "红", "黄"
DENY = "packaging/public_denylist.txt"
WORDS_FILE = DENY
NOISE = (".git/",)
TEXT_EXT = (".md", ".txt", ".py", ".json", ".yml", ".yaml", ".cfg", ".ini", ".toml", ".ps1", ".bat", ".sh", ".html", ".css", ".js")


from _common import sha256_of


def find_git(explicit=None):
    if explicit:
        return explicit
    found = shutil.which("git")
    if found:
        return found
    for candidate in (
        "C:/Program Files/Git/cmd/git.exe",
        "C:/Program Files (x86)/Git/cmd/git.exe",
    ):
        if Path(candidate).exists():
            return candidate
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


def scan_history(repo, words, limit=6, rev="HEAD"):
    rc, revs = repo.run(["rev-list", rev])
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


def check_ref(repo, words, ref):
    """扫一个 ref：树里有没有词表、它自己的全部历史里有没有命中。"""
    deny_here = repo.ok(["cat-file", "-e", ref + ":" + WORDS_FILE])[0]
    n, items = scan_history(repo, words, rev=ref)
    ncommits = len(repo.ok(["rev-list", ref])[1].split())
    return deny_here, n, items, ncommits


def read_push_refs(stream):
    refs = []
    for line in stream:
        parts = line.split()
        if len(parts) >= 4:
            refs.append(parts[:4])
    return refs


def seal_status(zip_path):
    zip_path = Path(zip_path)
    sj = Path(str(zip_path) + ".seal.json")
    if not zip_path.exists():
        return False, "找不到包 " + str(zip_path)
    if not sj.exists():
        return False, "包没有封条 " + str(sj)
    try:
        data = json.loads(sj.read_text(encoding="utf-8").lstrip("\ufeff"))
    except Exception as e:
        return False, "封条读不动：" + str(e)
    sha = sha256_of(zip_path)
    size = zip_path.stat().st_size
    if sha != data.get("sha256") or size != data.get("bytes"):
        return False, ("封条对不上：盘上 " + sha[:8] + " / " + str(size) + " B，封条 "
                       + str(data.get("sha256"))[:8] + " / " + str(data.get("bytes")) + " B")
    return True, "封条对得上 " + sha[:8] + " · " + str(size) + " B · " + str(data.get("files")) + " 个文件"


def _parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("SECOND_TAKE_REPO", "D:/dev/second-take"))
    ap.add_argument("--zip", default="")
    ap.add_argument("--words", default="")
    ap.add_argument("--git", default="")
    ap.add_argument("--no-history", action="store_true")
    ap.add_argument("--no-zip", action="store_true", help="只判树与历史，不判包（CI 打包前用）")
    ap.add_argument("--expect-tag", default="", help="CI 用：tag 名必须与最新 tag 一致")
    ap.add_argument("--push-gate", action="store_true",
                    help="钩子用：从 stdin 读推送清单，逐个 ref 判树/历史/封条")
    ap.add_argument("--scan-ref", default="",
                    help="只核某一个 ref（推分支/推旧历史前用）：扫它的树与它的全部历史")
    a = ap.parse_args()
    return a


def _push_gate(a, repo, rows, row, head):
    # --push-gate：钩子用。读 stdin 上的推送清单，逐个 ref 判——不看工作区 HEAD 就算数。
    if a.push_gate:
        words = []
        if a.words and Path(a.words).exists():
            words = parse_words(Path(a.words).read_text(encoding="utf-8", errors="replace"))
        if not words:
            row("词表", "没给 --words，核不了", RED)
            return report(rows, str(a.repo), head)
        refs = read_push_refs(sys.stdin)
        if not refs:
            row("推送清单", "stdin 上没有 refs，核不了", RED)
            return report(rows, str(a.repo), head)
        bad = False
        seen = []
        for lref, lsha, rref, rsha in refs:
            if lsha.strip("0") == "":
                row("删除", lref + " 是删除 ref，没有内容要核", GREEN)
                continue
            label = lref + " → " + lsha[:7]
            new_sha = lsha not in seen
            if new_sha:
                seen.append(lsha)
                deny_here, n, items, ncommits = check_ref(repo, words, lsha)
                row("树", label + (" 带着词表" if deny_here else " 树里没有词表"), RED if deny_here else GREEN)
                if deny_here:
                    bad = True
                row("历史", label + " 的 " + str(ncommits) + " 个提交 · 命中 " + str(n) + " 处",
                    RED if n else GREEN)
                if n:
                    bad = True
                for path, ln, text, commits in items[:6]:
                    row("", path + ":" + str(ln) + " " + text + " @ " + ",".join(commits[:6]), RED)
            if lref.startswith("refs/tags/v"):
                ver = lref[len("refs/tags/v"):]
                cand = [Path(a.zip)] if a.zip else []
                cand.append(Path(str(a.repo)) / ".." / ("second-take-" + ver + "-win.zip"))
                zpath = next((z for z in cand if z.exists()), cand[-1])
                ok, msg = seal_status(zpath)
                row("封条", label + " · " + msg, GREEN if ok else RED)
                if not ok:
                    bad = True
        return report(rows, str(a.repo), head, RED if bad else GREEN)


def _scan_ref(a, repo, rows, row, head):
    # --scan-ref：钩子用。只看「这次要推上去的那个 ref」，不看 HEAD。
    if a.scan_ref:
        words = []
        if a.words and Path(a.words).exists():
            words = parse_words(Path(a.words).read_text(encoding="utf-8", errors="replace"))
        if not words:
            row("词表", "没给 --words，核不了", YELLOW)
            return report(rows, str(a.repo), head)
        _, sref = repo.ok(["rev-parse", "--short", a.scan_ref])
        deny_here = repo.ok(["cat-file", "-e", a.scan_ref + ":" + WORDS_FILE])[0]
        row("5 词表在库", (WORDS_FILE + " 存在于 " + sref) if deny_here else ("不在 " + sref + " 的树里"),
            RED if deny_here else GREEN)
        n, items = scan_history(repo, words, rev=a.scan_ref)
        ncommits = len(repo.ok(["rev-list", a.scan_ref])[1].split())
        row("9 历史命中", str(n) + " 处（" + sref + " 的 " + str(ncommits) + " 个提交）", GREEN if n == 0 else RED)
        for path, ln, text, commits in items:
            row("", path + ":" + str(ln) + " " + text + " @ " + ",".join(commits), RED)
        return report(rows, str(a.repo), sref)


def _chk_workspace(repo):
    _, st = repo.ok(["status", "--porcelain"])
    dirty = [l for l in st.splitlines() if l.strip() and not l.startswith("??")]
    return [("1 工作区", ("干净" if not dirty else str(len(dirty)) + " 个改动未提交"),
             GREEN if not dirty else RED)]


def _chk_version(repo):
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
    rows = [("2 版本一致", "VERSION " + (ver or "?") + " / latest " + (lver or "?") + " / 最新 tag " + (last_tag or "无"), GREEN if v_ok else RED)]
    return ver, last_tag, rows


def _chk_tag(a, repo, last_tag):
    rows = []
    if last_tag:
        _, ttype = repo.ok(["cat-file", "-t", last_tag])
        _, tcommit = repo.ok(["rev-parse", last_tag + "^{commit}"])
        annotated = ttype.strip() == "tag"
        points_head = tcommit.strip() == repo.ok(["rev-parse", "HEAD"])[1].strip()
        if a.expect_tag:
            ok = annotated and points_head
            detail = ttype.strip() + " / 指向 " + tcommit[:7] + (" = HEAD" if points_head else " ≠ HEAD")
        else:
            anc = repo.run(["merge-base", "--is-ancestor", tcommit.strip(), "HEAD"])[0] == 0
            ok = annotated and anc
            detail = ttype.strip() + " / 指向 " + tcommit[:7] + (" = HEAD" if points_head else "（是 HEAD 的祖先）" if anc else "（既不是 HEAD 也不是它的祖先）")
        rows.append(("3 标记", detail, GREEN if ok else RED))
    else:
        rows.append(("3 标记", "没有任何 tag", YELLOW))
    if a.expect_tag:
        same = a.expect_tag == last_tag
        rows.append(("3b CI tag", "触发 tag " + a.expect_tag + " / 最新 tag " + (last_tag or "无"), GREEN if same else RED))
    return rows


def _chk_words(a, repo):
    words, src, rows = [], "", []
    if a.words:
        p = Path(a.words)
        if p.exists():
            words = parse_words(p.read_text(encoding="utf-8", errors="replace"))
            src = "外部词表 " + str(p)
    if not words:
        rc, deny_text = repo.run(["show", "HEAD:" + WORDS_FILE])
        if rc == 0:
            words = parse_words(deny_text)
            src = "库内词表 " + WORDS_FILE
    if not words:
        rows.append(("4 词表", "没有找到禁用词表（库内没有，也没给 --words）", YELLOW))
    else:
        rows.append(("4 词表", str(len(words)) + " 个词 · 来源 " + src, GREEN))
    deny_exists = repo.ok(["cat-file", "-e", "HEAD:" + WORDS_FILE])[0]
    if deny_exists:
        rows.append(("5 词表在库", WORDS_FILE + " 存在于 HEAD（它必须写出禁用词，所以它自己就带一个）", RED))
    else:
        rows.append(("5 词表在库", "不在库里（这是对的设计）", GREEN))
    return words, rows


def _chk_zip(a, ver, words):
    rows = []
    if a.no_zip:
        return [("6 包形状", "已跳过（CI 打包前，--no-zip）", GREEN)]
    zip_path = Path(a.zip) if a.zip else None
    if zip_path is None and ver:
        cand = Path("D:/dev/second-take-" + ver + "-win.zip")
        if cand.exists():
            zip_path = cand
    if not (zip_path and zip_path.exists()):
        return [("6 包形状", "找不到待发 zip" + ("" if a.zip else "（自动找 D:/dev/second-take-" + (ver or "x") + "-win.zip）"), YELLOW)]
    zsize = zip_path.stat().st_size
    zsha = sha256_of(zip_path)
    nfiles, zhits, has_deny, susp = scan_zip(zip_path, words)
    rows.append(("6 包形状", str(nfiles) + " 个文件 · " + str(zsize) + " B · sha256 " + zsha[:8], GREEN if not susp else RED))
    rows.append(("7 包内禁用词", ("0 处" if not zhits else str(len(zhits)) + " 处"), GREEN if not zhits else RED))
    rows.append(("8 词表进包", ("在包里（不许）" if has_deny else "不在包里"), RED if has_deny else GREEN))
    for fn, ln, text in zhits[:5]:
        rows.append(("", fn + ":" + str(ln) + " " + text, RED))
    for fn in susp[:5]:
        rows.append(("", "不该进包: " + fn, RED))
    return rows


def _chk_history(a, repo, words):
    rows = []
    if words and not a.no_history:
        n, items = scan_history(repo, words)
        rows.append(("9 历史命中", str(n) + " 处（全历史，" + str(len((repo.ok(["rev-list", "HEAD"])[1]).split())) + " 个提交）", GREEN if n == 0 else RED))
        for path, ln, text, commits in items:
            rows.append(("", path + ":" + str(ln) + " " + text + " " + chr(64) + " " + ",".join(commits), RED))
    elif words:
        rows.append(("9 历史命中", "已跳过（--no-history）", YELLOW))
    return rows


def _check_release(a, repo, rows, row, head):
    rows.extend(_chk_workspace(repo))
    ver, last_tag, version_rows = _chk_version(repo)
    rows.extend(version_rows)
    rows.extend(_chk_tag(a, repo, last_tag))
    words, word_rows = _chk_words(a, repo)
    rows.extend(word_rows)
    rows.extend(_chk_zip(a, ver, words))
    rows.extend(_chk_history(a, repo, words))
    verdict = RED if any(r[2] == RED for r in rows) else (YELLOW if any(r[2] == YELLOW for r in rows) else GREEN)
    return report(rows, str(a.repo), head, verdict)


def main():
    a = _parse_args()


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

    if a.push_gate:
        return _push_gate(a, repo, rows, row, head)

    if a.scan_ref:
        return _scan_ref(a, repo, rows, row, head)

    return _check_release(a, repo, rows, row, head)



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
