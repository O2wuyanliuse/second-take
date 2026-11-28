from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_backup_download_is_source_snapshot():
    text = read("CHANGELOG.md")
    assert "备链是**源码快照**" in text
    assert "发布成品仍用主链" in text
    assert "下下来自己跑 `packaging/_pack.py` 打包" not in text


def test_changelog_scope_rule_in_maintenance_doc():
    text = read("docs/maintain/维护方法.md")
    assert "CHANGELOG 只写用户能感知的变化" in text
    assert "内部改动写维护方法，不进 CHANGELOG" in text


def test_pack_entry_marked_deprecated():
    text = read("packaging/_pack.py")
    assert "[已停用] 私库整包入口 _pack.py 不再维护；用户包请用 tools/build_public_package.py + publish_manifest.txt" in text


def test_pack_entry_shows_deprecation_banner_on_first_screen():
    import subprocess
    import sys
    result = subprocess.run(
        [sys.executable, "packaging/_pack.py", "--dry-run"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    output = result.stdout + result.stderr
    assert result.returncode == 2
    assert "[已停用] 私库整包入口 _pack.py 不再维护" in output


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


def test_handoff_template_contains_full_skeleton_and_continuation():
    text = read("shapes/03_交接形状.md").split("## 七、续窗开工块", 1)[1]
    for sentence in (
        "它是一个叫 second-take 的开源方法层",
        "请你按这个顺序读，读完先别动手",
        "读完回我三件事",
        "规矩四条",
        "每次只给我三个选项",
        "（second-take · 开工提示词 v1）",
    ):
        assert sentence in text
    assert "0) <上面那份交接件的完整路径>" in text
    assert "这是续窗，按交接件的下一步直接做" in text
    assert "第一屏" in text


def test_flow_doc_has_same_continuation_hardline():
    text = read("Agent框架/02_流程层_交接防错.md")
    assert "续窗硬线" in text
    assert "这是续窗，按交接件的下一步直接做" in text
    assert "shapes/03_交接形状.md` 第七节" in text
    assert "第 0 条写交接件自己的路径" in text
    assert "不重跑 bootstrap" in text
    assert "外项目的 `.md` 不醒" in text
