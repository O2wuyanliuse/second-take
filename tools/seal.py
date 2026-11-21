# -*- coding: utf-8 -*-
"""封条：给一个包写上「它是谁」，之后任何人（包括上传之后）都能对。

用法：
  seal.py seal  <zip>  --repo D:/dev/second-take [--words 词表]   # 打完包立刻封
  seal.py check <zip>  --seal <zip>.seal.json                       # 对封条
  seal.py check <zip>  --from-release v0.5.1 --asset second-take-0.5.1-win.zip

封条内容（json，随边上放 <zip>.seal.json）：
  sha256 / bytes / files / head / version / manifest_sha / words_sha256 / words_count / created

封条会随 release 一起公开发出去——所以**只记词表的指纹，不记词表的路径**。
（2026-11-21 修：原来写 words_source 全路径，等于把私库目录名贴到公开资产里。）

退出码：0 = 对得上；1 = 对不上（红）；2 = 缺封条或缺件（黄，也不许发）。
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from verify_release import find_git  # 同目录，复用同一套 git 探测
except Exception:
    def find_git(explicit=None):
        return explicit or "git"


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def count_files(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        return len([i for i in z.infolist() if not i.is_dir()])


def git_out(git, repo, args):
    p = subprocess.run([git, "-c", "core.quotepath=false"] + args, cwd=str(repo),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode, p.stdout.decode("utf-8", "replace").strip()


def cmd_seal(a):
    zip_path = Path(a.zip)
    if not zip_path.exists():
        print("找不到包：" + str(zip_path))
        return 2
    repo = Path(a.repo)
    git = find_git(a.git)
    head = ""
    version = ""
    if repo.exists() and git:
        rc, head = git_out(git, repo, ["rev-parse", "HEAD"])
        rc2, version = git_out(git, repo, ["show", "HEAD:VERSION"])
        version = version.lstrip("\ufeff").split("·")[0].strip() if version else ""
    man = repo / "publish_manifest.txt"
    man_sha = sha256_of(man) if man.exists() else ""
    words = []
    if a.words and Path(a.words).exists():
        raw = Path(a.words).read_text(encoding="utf-8", errors="replace")
        for line in raw.splitlines():
            s = line.strip()
            if not s or s.startswith("#") or (s.startswith("[") and s.endswith("]")):
                continue
            words.append(s)
    data = {
        "sha256": sha256_of(zip_path),
        "bytes": zip_path.stat().st_size,
        "files": count_files(zip_path),
        "head": head,
        "version": version,
        "manifest_sha": man_sha,
        "words_sha256": hashlib.sha256("\n".join(words).encode("utf-8")).hexdigest() if words else "",
        "words_count": len(words),
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    out = Path(str(zip_path) + ".seal.json")
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("封条  " + str(out))
    print("      sha256 " + data["sha256"][:16] + "… · " + str(data["bytes"]) + " B · " + str(data["files"]) + " 个文件 · HEAD " + data["head"][:7])
    if len(words) == 0:
        print("结论  黄 · 没扫过的包不许封（要给 --words）")
        out.unlink()
        return 2
    print("结论  绿 · 已封")
    return 0


def cmd_check(a):
    zip_path = Path(a.zip)
    if not zip_path.exists():
        if a.from_release:
            print("本地没有包；请先 gh release download " + a.from_release + " -p " + a.asset)
        else:
            print("找不到包：" + str(zip_path))
        return 2
    if a.from_release and a.asset:
        tmp = Path(a.tmp or (str(zip_path) + ".downloaded"))
        r = subprocess.run(["gh", "release", "download", a.from_release, "-p", a.asset, "-D", str(tmp.parent), "--clobber"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if r.returncode != 0:
            print("gh 下载失败：" + r.stderr.decode("utf-8", "replace")[:300])
            return 2
        cand = tmp.parent / a.asset
        if cand.exists():
            zip_path = cand
    seal_path = Path(a.seal) if a.seal else Path(str(zip_path) + ".seal.json")
    if not seal_path.exists():
        print("没有封条：" + str(seal_path))
        print("结论  黄 · 无封条的包不许发")
        return 2
    seal = json.loads(seal_path.read_text(encoding="utf-8").lstrip("\ufeff"))
    sha = sha256_of(zip_path)
    size = zip_path.stat().st_size
    files = count_files(zip_path)
    bad = []
    if sha != seal.get("sha256"):
        bad.append("sha256 " + sha[:16] + "… ≠ 封条 " + str(seal.get("sha256"))[:16] + "…")
    if size != seal.get("bytes"):
        bad.append("字节 " + str(size) + " ≠ 封条 " + str(seal.get("bytes")))
    if files != seal.get("files"):
        bad.append("文件数 " + str(files) + " ≠ 封条 " + str(seal.get("files")))
    print("包    " + str(zip_path))
    print("封条  " + str(seal_path) + "（" + str(seal.get("created", "")) + "，HEAD " + str(seal.get("head", ""))[:7] + "，版本 " + str(seal.get("version", "")) + "）")
    print("sha256  " + sha[:16] + "… · " + str(size) + " B · " + str(files) + " 个文件")
    if bad:
        for b in bad:
            print("不对  " + b)
        print("结论  红 · 这个包不是那个包")
        return 1
    print("结论  绿 · 与封条一致")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    s = sub.add_parser("seal")
    s.add_argument("zip")
    s.add_argument("--repo", default=os.environ.get("SECOND_TAKE_REPO", "D:/dev/second-take"))
    s.add_argument("--words", default="")
    s.add_argument("--git", default="")
    c = sub.add_parser("check")
    c.add_argument("zip")
    c.add_argument("--seal", default="")
    c.add_argument("--from-release", default="")
    c.add_argument("--asset", default="")
    c.add_argument("--tmp", default="")
    a = ap.parse_args()
    return cmd_seal(a) if a.mode == "seal" else cmd_check(a)


if __name__ == "__main__":
    sys.exit(main())
