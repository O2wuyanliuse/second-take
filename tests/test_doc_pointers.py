from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_backup_download_is_source_snapshot():
    text = read("CHANGELOG.md")
    assert "备链是**源码快照**" in text
    assert "发布成品仍用主链" in text
    assert "下下来自己跑 `packaging/_pack.py` 打包" not in text


def test_package_verifier_has_no_deleted_install_entry():
    text = read("packaging/_verify_package.py")
    assert "安装.md" not in text
    assert "V7 免责声明（三处入口）" in text


def test_jimeng_missing_cli_gives_real_setup_commands():
    text = read("tools/jimeng_bench/server.py")
    assert "pip install dreamina，再 dreamina login" in text
    assert "README 的安装步骤" not in text


def test_instance_manifest_is_not_user_package_manifest():
    text = read("Agent框架/11_分发说明_v1.md")
    assert "这是**私库实例包**的结构" in text
    assert "对外用户包的文件清单以 `publish_manifest.txt` 为准" in text
