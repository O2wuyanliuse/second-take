from helpers import REPO

INTERFACE = (REPO / 'Agent框架/00_人机接口层_交付形态与提问纪律.md').read_text(encoding='utf-8')
STORYBOARD = (REPO / 'Agent框架/04_分镜标注规范.md').read_text(encoding='utf-8')
E0 = (REPO / 'Agent框架/环节E0_对齐扫雷操作清单_v1.md').read_text(encoding='utf-8')
E1 = (REPO / 'Agent框架/环节E1_判据表_v1.md').read_text(encoding='utf-8')
TABLE = (REPO / 'Agent框架/环节表_文字到可视化_v1.md').read_text(encoding='utf-8')
AGENTS = (REPO / 'AGENTS.md').read_text(encoding='utf-8')

LINE1 = '你先自己看；手感想复核，就把片段直接拖进这个对话框，或者告诉我原件放在哪个路径，我来做复盘解析。'
LINE2 = '要是觉得不用复核，回我一句「这条过了」，我记下你的原话就往下走。'


def test_handover_script_verbatim():
    assert LINE1 in INTERFACE, '缺第一句通报话术'
    assert LINE2 in INTERFACE, '缺第二句通报话术'


def test_q3_section_title_present():
    assert '### Q3 · 收口必须通报（沉默不算通过）' in INTERFACE


def test_storyboard_six_columns_and_evidence():
    assert '一行一场、六列' in STORYBOARD
    assert '收口凭据（复盘／人过，机判只作辅助；写法见 00_人机接口层 Q3）' in STORYBOARD


def test_table_exit_two_levels():
    assert '一·补二 出口两级' in TABLE
    e0_row = [l for l in TABLE.splitlines() if l.startswith('| **E0**（含 E0·1–E0·7）')]
    e8_row = [l for l in TABLE.splitlines() if l.startswith('| **E8**（成片）')]
    assert e0_row and '**不许**' in e0_row[0]
    assert e8_row and '**可跳**' in e8_row[0]


def test_e0_e1_daily_reminder_once():
    assert E0.count('每天开工时提醒一次') == 1
    assert E1.count('每天开工时提醒一次') == 1


def test_agents_install_scope_limited_to_this_package():
    line = [l for l in AGENTS.splitlines() if '或者用户明确在装' in l]
    assert line, 'AGENTS 里找不到安装分支'
    assert '**只有本包才算**' in line[0]
    assert '开工提示词.md' in line[0]



def test_equivalent_reply_phrase_present():
    assert '「没问题下一条」' in INTERFACE


def test_e0_reminder_once_only():
    assert E0.count('同一天不许提醒第二遍') == 1


def test_agents_other_packages_not_awake():
    assert '别的包、别的项目路径说的话不算醒' in AGENTS



def test_q3_e0_e1_exception_present():
    assert 'E0／E1 不发这两句，也不认这两句' in INTERFACE


def test_e1_reminder_once_only():
    assert E1.count('同一天不许提醒第二遍') == 1


def test_e1_uses_step3_example():
    assert 'E1 的第 ③ 步' in E1



AXIS = (REPO / 'Agent框架/00_主轴_按环节读_v1.md').read_text(encoding='utf-8')


def test_storyboard_silence_is_unclosed():
    assert '沉默一律算未收口' in STORYBOARD


def test_interface_no_silence_closed():
    assert '沉默之后不许把状态改成已收口' in INTERFACE


def test_interface_quote_verbatim():
    assert '凭据里抄他的原话，不改写' in INTERFACE


def test_interface_same_scene_once():
    assert '同一场最多问一次' in INTERFACE


def test_interface_no_mixed_questions():
    assert '收口那条消息不要夹别的问题' in INTERFACE


def test_axis_e8_evidence():
    assert '各场成片齐、全场已收口' in AXIS


def test_e0_step_example():
    assert 'E0·3 这类' in E0



def test_interface_no_skip_scene_to_e8():
    assert '也不许把这一场当过了往 E8 走' in INTERFACE


def test_storyboard_status_has_unclosed():
    assert '状态（未开／进行中／未收口／已收口）' in STORYBOARD
