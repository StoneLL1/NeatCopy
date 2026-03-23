import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from rule_engine import RuleEngine

ALL_ON = {
    'merge_soft_newline': True,
    'keep_hard_newline': True,
    'merge_spaces': True,
    'smart_punctuation': True,
    'pangu_spacing': True,
    'trim_lines': True,
    'protect_code_blocks': True,
    'protect_lists': True,
}


def clean(text, cfg=None):
    return RuleEngine.clean(text, cfg or ALL_ON)


class TestProtectCodeBlocks:
    def test_fenced_code_block_preserved(self):
        text = '前文\n```\ncode line1\ncode line2\n```\n后文'
        result = clean(text)
        assert 'code line1\ncode line2' in result

    def test_indented_code_block_preserved(self):
        text = '段落\n\n    import os\n    os.getcwd()\n\n后段落'
        result = clean(text)
        assert '    import os' in result


class TestProtectLists:
    def test_dash_list_newlines_preserved(self):
        text = '- 项目一\n- 项目二\n- 项目三'
        result = clean(text)
        assert '- 项目一\n- 项目二\n- 项目三' in result

    def test_numbered_list_newlines_preserved(self):
        text = '1. 第一条\n2. 第二条'
        result = clean(text)
        assert '1. 第一条\n2. 第二条' in result

    def test_asterisk_list_preserved(self):
        text = '* 苹果\n* 香蕉'
        result = clean(text)
        assert '* 苹果\n* 香蕉' in result


class TestMergeSoftNewlines:
    def test_single_newline_merged(self):
        result = clean('第一行\n第二行')
        assert '\n' not in result
        assert '第一行' in result and '第二行' in result

    def test_paragraph_break_preserved(self):
        text = '第一段\n\n第二段'
        result = clean(text)
        assert '第一段' in result and '第二段' in result
        assert '\n\n' in result

    def test_list_not_merged(self):
        text = '- item1\n- item2'
        result = clean(text)
        assert '- item1\n- item2' in result

    def test_code_block_not_merged(self):
        text = '```\nline1\nline2\n```'
        result = clean(text)
        assert 'line1\nline2' in result


class TestKeepHardNewlines:
    def test_double_newline_kept(self):
        text = '段落一\n\n段落二'
        result = clean(text)
        assert '\n\n' in result

    def test_triple_newline_collapsed_to_double(self):
        text = '段落一\n\n\n段落二'
        result = clean(text)
        assert result.count('\n\n\n') == 0


class TestMergeSpaces:
    def test_multiple_spaces_merged(self):
        assert clean('hello   world') == 'hello world'

    def test_single_space_unchanged(self):
        assert clean('hello world') == 'hello world'


class TestRuleToggle:
    def test_merge_spaces_off(self):
        cfg = {**ALL_ON, 'merge_spaces': False}
        result = RuleEngine.clean('hello   world', cfg)
        assert '   ' in result

    def test_pangu_spacing_off(self):
        cfg = {**ALL_ON, 'pangu_spacing': False}
        result = RuleEngine.clean('中文English', cfg)
        assert '中文English' in result


class TestPanguSpacing:
    def test_chinese_before_english(self):
        result = clean('中文English')
        assert '中文 English' in result

    def test_english_before_chinese(self):
        result = clean('Hello世界')
        assert 'Hello 世界' in result

    def test_number_beside_chinese(self):
        result = clean('共100个')
        assert '共 100 个' in result


class TestTrimLines:
    def test_leading_whitespace_removed(self):
        result = clean('   前导空格')
        assert not result.startswith(' ')

    def test_trailing_whitespace_removed(self):
        result = clean('尾随空格   ')
        assert not result.endswith(' ')


class TestSmartPunctuation:
    def test_english_context_keeps_half_width_comma(self):
        result = clean('Hello, world')
        assert ',' in result

    def test_chinese_context_keeps_full_width_comma(self):
        result = clean('你好，世界')
        assert '，' in result

    def test_mixed_not_broken(self):
        result = clean('中文，English.')
        assert result is not None


class TestIntegration:
    def test_pdf_typical_copy(self):
        pdf_text = (
            '这是论文的第一段，描述了研究背\n'
            '景和主要贡献。本研究采用了新的\n'
            '方法论。\n\n'
            '第二段开始讨论实验结果，包括：\n'
            '- 实验一的结果\n'
            '- 实验二的结果\n\n'
            '结论部分总结了全文。'
        )
        result = clean(pdf_text)
        # 列表保留换行
        assert '- 实验一的结果\n- 实验二的结果' in result
        # 段落分隔保留
        assert '\n\n' in result
        # 段落内换行被合并（不含研究背\n景这样的断行）
        assert '研究背\n景' not in result
