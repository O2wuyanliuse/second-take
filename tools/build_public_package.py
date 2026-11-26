# -*- coding: utf-8 -*-
"""按白名单打包：清单以外的东西不可能进包。

与 verify_release.py 的分工：
  build_public_package.py 决定「包里能有什么」（白名单，默认不含）；
  verify_release.py       检验「包里实际有什么」（扫描，红了就不许发）。

扫不过时本脚本会**删掉刚打出来的 zip**，让它物理上不存在——不是「报个红请你记得别传」。
"""
import argparse
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from verify_release import find_git, parse_words, scan_zip, sha256_of
except Exception:
    print("找不到 verify_release.py（两者必须放同一目录）")
    sys.exit(3)


def translate(pat):
    out = []
    i = 0
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


def load_manifest(path):
    inc, exc = [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("!"):
            exc.append(translate(s[1:].strip()))
            continue
        if s.endswith("/"):
            s = s + "**"
        inc.append(translate(s))
    return inc, exc


def tracked(git, repo):
    p = subprocess.run([git, "-c", "core.quotepath=false", "ls-tree", "-r", "--name-only", "HEAD"],
                       cwd=str(repo), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise SystemExit("git ls-tree 失败：" + p.stderr.decode("utf-8", "replace"))
    return [l for l in p.stdout.decode("utf-8", "replace").splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("SECOND_TAKE_REPO", "D:/dev/second-take"))
    ap.add_argument("--manifest", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--prefix", default="")
    ap.add_argument("--words", default="")
    ap.add_argument("--git", default="")
    a = ap.parse_args()

    repo = Path(a.repo)
    git = find_git(a.git)
    if not git:
        raise SystemExit("找不到 git")
    man = Path(a.manifest) if a.manifest else (repo / "publish_manifest.txt")
    if not man.exists():
        raise SystemExit("找不到白名单：" + str(man))

    ver = ""
    try:
        ver = (repo / "VERSION").read_text(encoding="utf-8-sig").split("·")[0].strip()
    except Exception:
        pass  # 吞：工作树 VERSION 读不到时，按原逻辑回退到 git HEAD:VERSION。
    if not ver:
        p = subprocess.run([git, "show", "HEAD:VERSION"], cwd=str(repo), stdout=subprocess.PIPE)
        ver = p.stdout.decode("utf-8", "replace").lstrip("\ufeff").split("·")[0].strip()

    prefix = a.prefix or ("second-take-" + ver)
    out = Path(a.out) if a.out else Path("second-take-" + ver + "-win.zip")

    inc, exc = load_manifest(man)
    files = []
    for f in tracked(git, repo):
        posix = f.replace(os.sep, "/")
        if not any(r.match(posix) for r in inc):
            continue
        if any(r.match(posix) for r in exc):
            continue
        files.append(f)
    if not files:
        raise SystemExit("白名单一条都没匹配到——清单写错了")

    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            src = repo / f
            if not src.exists():
                raise SystemExit("白名单里的文件在盘上不存在：" + f)
            z.write(src, prefix + "/" + f.replace(os.sep, "/"))

    size = out.stat().st_size
    sha = sha256_of(out)
    print("打包  " + str(len(files)) + " 个文件 · " + str(size) + " B")
    print("路径  " + str(out))
    print("sha256  " + sha)

    if a.words:
        words = parse_words(Path(a.words).read_text(encoding="utf-8", errors="replace"))
        n, hits, has_deny, susp = scan_zip(out, words)
        if n != len(files):
            print("包内文件数 " + str(n) + " ≠ 打包清单 " + str(len(files)))
        bad = bool(hits) or has_deny or bool(susp)
        if bad:
            for fn, ln, text in hits[:10]:
                print("命中  " + fn + ":" + str(ln) + " " + text)
            if has_deny:
                print("命中  禁用词表进了包")
            for fn in susp[:10]:
                print("不该进包  " + fn)
            out.unlink()
            print("结论  红 · 已删除该 zip（没有扫过的包不存在）")
            return 1
        print("结论  绿 · 包内禁用词 0 处（扫了 " + str(n) + " 个文件）")
    else:
        print("结论  黄 · 没给 --words，这个包没扫过，不许发")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
