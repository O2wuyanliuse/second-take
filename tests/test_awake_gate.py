# -*- coding: utf-8 -*-
"""尺子：沉睡闸口的位置与唯一真相（1.0.4 默认沉睡）。

来由：1.0.3 及以前，AGENTS.md 的第 0 步是无条件的「打开先做」。
AI 只要被工作台塞了这份文件，就会在任何项目里自己开工——那是污染。
现在定死一条：**醒没醒由用户粘没粘开工提示词决定**，读到文件不等于开工。

这条尺子钉六件事：
  1) 第 0 步在第 1 屏，且在「阅读路线」之前（顺序错了，:14 会把 AI 拉回去）；
  2) 六句骨架在 AGENTS.md 与 开工提示词.md 里逐字相同（两处真相必须一致）；
  3) 没醒时那句话只出现一次、逐字不含糊；
  4) 对外文档不提「放进全局配置」这种装法（具体串，不是关键词同行）；
  5) 装算醒但不自动开工；workspace/ 不作为醒的证据；
  6) 沉睡句与「怎么激活」那句的位置由 AGENTS 决定，不由本文件常量决定。

不测「模型真的会不会照做」：那是判据（第九节），不是测试。
"""
import re

from helpers import REPO

AGENTS = (REPO / 'AGENTS.md').read_text(encoding='utf-8')
PROMPT = (REPO / '开工提示词.md').read_text(encoding='utf-8')

SKELETON = [
    '（second-take · 开工提示词 v1）',
    '它是一个叫 second-take 的开源方法层',
    '请你按这个顺序读，读完先别动手',
    '读完回我三件事',
    '规矩四条',
    '每次只给我三个选项',
]
SLEEP_LINE = 'second-take目前未激活，需要使用请把《开工提示词》第二节整段粘贴到对话窗口'


def _line_no(text, needle):
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return i
    raise AssertionError('没找到：' + needle)


def test_step0_is_first_screen():
    step0 = _line_no(AGENTS, '## 第 0 步')
    route = _line_no(AGENTS, '## 阅读路线')
    assert step0 < route, '第 0 步被挪到了阅读路线后面：:14「只读这三份」会让 AI 把自己叫醒'
    total = len(AGENTS.splitlines())
    assert step0 < total / 3, '第 0 步不在第一屏（行号 %s，总行数 %s）' % (step0, total)


def test_reading_route_does_not_precede_gate():
    step0 = _line_no(AGENTS, '## 第 0 步')
    three = _line_no(AGENTS, '只读这三份，够开工')
    assert three > step0, '「只读这三份」出现在第 0 步之前：AI 会先读开工提示词，等于唤醒信物把自己叫醒'


def test_skeleton_sentences_match_both_files():
    block = re.search(r'```\n(.*?)\n```', PROMPT, re.S)
    assert block, '开工提示词.md 里没找到代码块'
    body = block.group(1)
    for s in SKELETON:
        assert s in AGENTS, '两处骨架不一致：AGENTS.md 缺 ' + s
        assert s in body, '两处骨架不一致：开工提示词.md 代码块缺 ' + s


def test_sleep_line_is_exact_and_unique():
    n = AGENTS.count(SLEEP_LINE)
    assert n == 1, '沉睡那句被改了或写了两份（实际 %s 次）' % n


def test_agents_keeps_english_summary():
    head = AGENTS.splitlines()[:30]
    assert any(l.lstrip('> ').startswith('**English') for l in head), \
        'check_bilingual 会红：英文摘要被挤出前 30 行'


def test_docs_warn_against_global_install():
    cases = [
        ('README.md', ('不要放进全局配置', '全局配置')),
        ('README.en.md', ('Never place this package in a global',)),
        ('开工提示词.md', ('别把这个包放进全局注入位置', '全局注入')),
    ]
    for name, needles in cases:
        text = (REPO / name).read_text(encoding='utf-8')
        for needle in needles:
            assert needle.lower() in text.lower(), \
                '对外文档少了这句：%s / %s' % (name, needle)


def test_install_decline_and_activate_lines_present():
    lines = [
        '装好了。现在要开工吗？',
        '要开工就把《开工提示词》第二节整段粘贴过来；不想现在开工也行，我平时默认不唤醒。',
        '好，那我先睡着（平时默认不唤醒）。要用的时候，把《开工提示词》第二节整段粘贴到对话窗口就行。',
        '要用的时候，把《开工提示词》第二节整段粘贴到对话窗口就行；那段在项目根的 开工提示词.md 里，标题叫「开工提示词」。',
    ]
    for s in lines:
        assert s in AGENTS, 'AGENTS.md 缺这句：' + s


ACTIVATE_LINE = '要用的时候，把《开工提示词》第二节整段粘贴到对话窗口就行；那段在项目根的 开工提示词.md 里，标题叫「开工提示词」。'


def test_activate_answer_differs_from_sleep_line():
    step0 = _line_no(AGENTS, '## 第 0 步')
    half = _line_no(AGENTS, '## 第 0.5 步')
    sleep_block = '\n'.join(AGENTS.splitlines()[step0 - 1:half - 1])
    assert sleep_block.count(SLEEP_LINE) == 1, \
        '沉睡段里 SLEEP_LINE 出现 %s 次' % sleep_block.count(SLEEP_LINE)
    activate_at = _line_no(AGENTS, ACTIVATE_LINE)
    decline_at = _line_no(AGENTS, '好，那我先睡着（平时默认不唤醒）')
    assert activate_at >= half, '「怎么激活」那句跑到了沉睡段里：%s' % activate_at
    assert activate_at > decline_at, '「怎么激活」那句必须在「先不用」那句之后'


def test_install_awake_but_not_auto_start():
    assert '装是另一件事' in AGENTS, '缺「装是另一件事」'
    assert '装完停在问句上' in AGENTS, '缺「装完停在问句上」'
    assert '装完算醒，但不自动开工' in AGENTS, '缺「装完算醒，但不自动开工」'


def test_workspace_is_not_wake_evidence():
    assert 'workspace/ 里有什么不算证据' in AGENTS, 'workspace/ 又被当成醒的证据'
    assert '120 字' not in AGENTS, '120 字阈值还留在 AGENTS 里（R2）'


def test_skeleton_marker_accepts_both_brackets():
    body = 'second-take · 开工提示词 v1'
    for wrap in ['（%s）', '(%s)']:
        marker = wrap % body
        assert body in marker
    assert '（second-take · 开工提示词 v1）' in AGENTS
    assert '括号' in AGENTS or '全半角' in AGENTS or '半角' in AGENTS, 'AGENTS 里应写明括号全半角都算（P4）'


WAKE_RULE = '命中第 1 句哨兵加上任意一句，或命中其中 ≥3 句'


def test_rule_rejects_quoted_skeleton():
    assert '用户转述、引用、复述本文件的骨架句不算命中' in AGENTS, \
        '缺「转述／引用骨架句不算命中」（M1 变异会绿）'


def test_rule_forbids_pasting_step0():
    assert '别贴第 0 步' in AGENTS, '缺「别贴第 0 步」（M2 变异会绿）'


def test_wake_rule_is_exact_and_unique():
    n = AGENTS.count(WAKE_RULE)
    assert n == 1, '判法原句被改或写了多份（实际 %s 次）' % n


def test_no_sleep_reply_when_missing_package_is_unique():
    n = AGENTS.count('不许回沉睡句')
    assert n == 1, '「不许回沉睡句」被删或写了多份（实际 %s 次）' % n



def test_named_start_e0_example_present():
    assert '按 E0 开工' in AGENTS, '缺「按 E0 开工」示例（R2）'



def test_prompt_last_line_explanation_consistent():
    prompt = (REPO / '开工提示词.md').read_text(encoding='utf-8')
    assert '只少了末尾那行仍会醒' in prompt
    assert '「粘全了」的记号' not in prompt
    assert '末尾那行别删' not in prompt


def test_existing_handoff_is_third_wake_entry():
    assert '已存在的 `.md` 交接件路径** → 算醒' in AGENTS
    assert '这是续窗，按交接件的下一步直接做' in AGENTS
    assert '不再跑第 0.5 步' in AGENTS
    assert '三条都不满足 → 没醒' in AGENTS


def test_handoff_scope_covers_deep_package_paths_only():
    for rel in ('00_原著/', 'Agent框架/', 'workspace/'):
        assert '`%s`' % rel in AGENTS
    assert '子目录任意深都算' in AGENTS
    assert '从该 `.md` 所在目录起，逐级向父目录查到盘根' in AGENTS
    assert '找到本包根的 `开工提示词.md` 才算本包' in AGENTS


def test_handoff_deep_subdir_and_ancestor_walk_pinned_together():
    """R3：子目录任意深 ＋ 逐级向父查到盘根，同段钉住。

    保护的场景：00_原著/子/深.md —— 落在 00_原著/ 下任意深，从它所在目录
    逐级向父找，直到本包根的 开工提示词.md 才算本包。A1 是提示词行为，
    这里只证字在；活体验收另走放行条，不拿文本断言冒充。
    """
    bullet = next(l for l in AGENTS.splitlines()
                  if '已存在的 `.md` 交接件路径' in l)
    assert '子目录任意深都算' in bullet, '深处规则不在第三醒法同段里'
    assert '从该 `.md` 所在目录起，逐级向父目录查到盘根' in bullet, \
        '祖先找根规则不在第三醒法同段里'
    assert '找到本包根的 `开工提示词.md` 才算本包' in bullet
    assert '`00_原著/`' in bullet, '00_原著/子/深.md 的第一段不在 scope，深处进不来'
    assert '这是续窗，按交接件的下一步直接做' in bullet


def test_handoff_missing_and_external_paths_do_not_fake_wake():
    assert '这份文件没找到：<路径>' in AGENTS
    assert '路径不存在 → 只报' in AGENTS
    assert '本包外项目的 `.md` → 不算醒' in AGENTS
    assert '不读那份文件' in AGENTS
    assert AGENTS.count(SLEEP_LINE) == 1
