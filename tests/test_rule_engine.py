"""规则引擎测试套件：覆盖每条规则的独立功能、开关控制、边界情况和规则组合。"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from rule_engine import RuleEngine

# ── 配置工具 ──────────────────────────────────────────────────────

RULE_KEYS = [
    'merge_soft_newline', 'keep_hard_newline', 'merge_spaces',
    'smart_punctuation', 'pangu_spacing', 'trim_lines',
    'protect_code_blocks', 'protect_lists',
]

ALL_ON = {k: True for k in RULE_KEYS}
ALL_OFF = {k: False for k in RULE_KEYS}


def only(rule):
    """只启用指定规则，其余全部关闭。"""
    return {k: (k == rule) for k in RULE_KEYS}


def without(*rules):
    """启用全部规则，但排除指定的规则。"""
    return {k: (k not in rules) for k in RULE_KEYS}


def clean(text, cfg=None):
    return RuleEngine.clean(text, cfg or ALL_ON)


# ══════════════════════════════════════════════════════════════════
# R7: 代码块保护
# ══════════════════════════════════════════════════════════════════

class TestCodeBlockProtection:
    def test_fenced_backtick(self):
        text = '前文\n```\ncode\n```\n后文'
        result = clean(text)
        assert 'code' in result
        assert '前文' in result and '后文' in result

    def test_fenced_tilde(self):
        text = '前文\n~~~\ncode\n~~~\n后文'
        result = clean(text)
        assert 'code' in result

    def test_language_annotation(self):
        text = '```python\nprint("hi")\n```'
        result = clean(text)
        assert 'print("hi")' in result

    def test_multiple_spaces_preserved(self):
        text = '```\nx  =  1\ny    = 2\n```'
        result = clean(text)
        assert 'x  =  1' in result
        assert 'y    = 2' in result

    def test_cjk_no_pangu_inside(self):
        text = '```\nprint("你好world")\n```'
        result = clean(text)
        assert '你好world' in result

    def test_punctuation_not_converted_inside(self):
        text = '```\n// 注意,这里有逗号\n```'
        result = clean(text)
        assert '注意,这里有逗号' in result

    def test_code_between_paragraphs(self):
        text = '段落一\n\n```\ncode\n```\n\n段落二'
        result = clean(text)
        assert '段落一' in result
        assert 'code' in result
        assert '段落二' in result

    def test_indented_not_protected(self):
        """缩进代码块不保护（4空格缩进在中文排版中太常见）。"""
        text = '段落\n\n    x  =  1\n    y  =  2\n\n后段落'
        result = clean(text)
        # 缩进代码不保护，trim 会清理，空格会被合并
        assert 'x  =  1' not in result

    def test_toggle_off(self):
        cfg = without('protect_code_blocks')
        text = '```\nx  =  1\n```'
        result = RuleEngine.clean(text, cfg)
        assert 'x  =  1' not in result

    def test_toggle_only(self):
        cfg = only('protect_code_blocks')
        text = '前文\n```\ncode\n```\n后文'
        result = RuleEngine.clean(text, cfg)
        assert 'code' in result


# ══════════════════════════════════════════════════════════════════
# R8: 列表保护
# ══════════════════════════════════════════════════════════════════

class TestListProtection:
    def test_dash_list(self):
        result = clean('- 项目一\n- 项目二\n- 项目三')
        assert '- 项目一\n- 项目二\n- 项目三' in result

    def test_numbered_list(self):
        result = clean('1. 第一条\n2. 第二条')
        assert '1. 第一条\n2. 第二条' in result

    def test_asterisk_list(self):
        result = clean('* 苹果\n* 香蕉')
        assert '* 苹果\n* 香蕉' in result

    def test_plus_list(self):
        result = clean('+ one\n+ two')
        assert '+ one\n+ two' in result

    def test_paren_numbered(self):
        result = clean('1) first\n2) second')
        assert '1) first\n2) second' in result

    def test_chinese_numbered_dun(self):
        """中文数字顿号列表：1、2、"""
        result = clean('1、第一点\n2、第二点\n3、第三点')
        assert '1、第一点\n2、第二点' in result

    def test_chinese_ordinal(self):
        """中文序数列表：一、二、"""
        result = clean('一、前言\n二、正文\n三、结论')
        assert '一、前言\n二、正文' in result

    def test_chinese_paren_numbered(self):
        """中文括号编号列表：（1）（2）"""
        result = clean('（1）第一条\n（2）第二条')
        assert '（1）第一条\n（2）第二条' in result

    def test_list_no_pangu(self):
        """列表行不应被盘古间距修改。"""
        result = clean('- 中文English混合')
        assert '中文English' in result

    def test_list_spaces_only_merged(self):
        """列表行仅合并多余空格。"""
        result = clean('- hello   world')
        assert '- hello world' in result

    def test_toggle_off(self):
        cfg = without('protect_lists')
        result = RuleEngine.clean('- item1\n- item2', cfg)
        # 列表不再保护，软换行可能合并
        assert 'item1' in result and 'item2' in result

    def test_toggle_only(self):
        cfg = only('protect_lists')
        text = '- item1\n- item2'
        result = RuleEngine.clean(text, cfg)
        assert '- item1\n- item2' in result


# ══════════════════════════════════════════════════════════════════
# R1: 软换行合并
# ══════════════════════════════════════════════════════════════════

class TestMergeSoftNewlines:
    def test_chinese_merged(self):
        result = clean('第一行\n第二行\n第三行', only('merge_soft_newline'))
        assert result == '第一行第二行第三行'

    def test_english_merged_with_space(self):
        result = clean('line one\nline two', only('merge_soft_newline'))
        assert result == 'line one line two'

    def test_mixed_cjk_english(self):
        result = clean('中文文本\nEnglish text', only('merge_soft_newline'))
        assert '中文文本English text' in result or '中文文本 English text' in result

    def test_paragraph_break_kept(self):
        result = clean('第一段\n\n第二段', only('merge_soft_newline'))
        assert '第一段' in result and '第二段' in result

    def test_empty_line_stops_merge(self):
        result = clean('line1\n\nline2', only('merge_soft_newline'))
        assert 'line1' in result and 'line2' in result

    def test_code_block_not_merged(self):
        result = clean('```\nline1\nline2\n```')
        assert 'line1\nline2' in result

    def test_list_not_merged(self):
        """连续列表项各自保持独立行。"""
        result = clean('- item1\n- item2')
        assert '- item1\n- item2' in result

    def test_list_continuation_merged(self):
        """列表项的续行应合并进列表段落。"""
        result = clean('(1)第一点的内容\n延续到第二行', only('merge_soft_newline'))
        assert result == '(1)第一点的内容延续到第二行'

    def test_list_paragraph_fully_merged(self):
        """(1)...(2)... 格式：每个编号段完整合并。"""
        text = ('(1)石灰石粉库应密封，库顶设置布袋除尘设备，经处理后排放，\n'
                '以防止粉尘对外界的污染。\n\n'
                '(2)煤炭采用密闭皮带机输送，以减少粉尘排放\n'
                '量；设有喷水装置。')
        result = clean(text, only('merge_soft_newline'))
        assert '(1)石灰石粉库应密封，库顶设置布袋除尘设备，经处理后排放，以防止粉尘对外界的污染。' in result
        assert '(2)煤炭采用密闭皮带机输送，以减少粉尘排放量；设有喷水装置。' in result

    def test_list_sentence_end_not_stopping_merge(self):
        """列表段落内句末标点不阻止续行合并（需同时开启列表检测）。"""
        cfg = {**ALL_OFF, 'merge_soft_newline': True, 'protect_lists': True}
        result = RuleEngine.clean('(1)第一句话。\n第二句话。', cfg)
        assert result == '(1)第一句话。第二句话。'

    def test_non_list_sentence_end_still_works(self):
        """非列表文本中句末标点仍然保留换行。"""
        result = clean('普通文本。\n续行', only('merge_soft_newline'))
        assert '普通文本。\n' in result

    def test_toggle_off(self):
        cfg = without('merge_soft_newline')
        result = RuleEngine.clean('第一行\n第二行', cfg)
        assert '第一行\n第二行' in result

    def test_only_rule(self):
        """仅启用软换行合并时，不应执行其他任何清洗。"""
        text = 'hello   world\nsecond line'
        result = clean(text, only('merge_soft_newline'))
        assert result == 'hello   world second line'

    def test_sentence_end_chinese_period(self):
        """中文句末句号后保留换行（CopyPlusPlus 风格）。"""
        result = clean('第一句话。\n第二句话。\n第三句话。', only('merge_soft_newline'))
        assert '第一句话。\n第二句话。\n第三句话。' == result

    def test_sentence_end_chinese_exclamation(self):
        result = clean('太好了！\n继续前进', only('merge_soft_newline'))
        assert '太好了！\n' in result

    def test_sentence_end_chinese_question(self):
        result = clean('为什么呢？\n因为规则如此', only('merge_soft_newline'))
        assert '为什么呢？\n' in result

    def test_sentence_end_english_period(self):
        result = clean('First sentence.\nSecond sentence.', only('merge_soft_newline'))
        assert 'First sentence.\nSecond sentence.' == result

    def test_sentence_end_english_exclamation(self):
        result = clean('Hello!\nWorld', only('merge_soft_newline'))
        assert 'Hello!\n' in result

    def test_non_sentence_end_merged(self):
        """非句末换行仍然合并。"""
        result = clean('这是第一行\n这是第二行', only('merge_soft_newline'))
        assert result == '这是第一行这是第二行'

    def test_mixed_sentence_and_soft_breaks(self):
        """句末保留 + 软换行合并混合场景。"""
        text = '研究背景如下。\n本文提出了\n一种新方法。'
        result = clean(text, only('merge_soft_newline'))
        assert '研究背景如下。\n' in result
        assert '本文提出了一种新方法。' in result


# ══════════════════════════════════════════════════════════════════
# R2: 空行折叠
# ══════════════════════════════════════════════════════════════════

class TestKeepHardNewlines:
    def test_double_newline_kept(self):
        result = clean('段落一\n\n段落二', only('keep_hard_newline'))
        assert result == '段落一\n\n段落二'

    def test_triple_collapsed_to_double(self):
        result = clean('段落一\n\n\n段落二', only('keep_hard_newline'))
        assert '\n\n\n' not in result
        assert '\n\n' in result

    def test_quad_collapsed_to_double(self):
        result = clean('段落一\n\n\n\n段落二', only('keep_hard_newline'))
        assert result.count('\n') == 2

    def test_single_newline_unchanged(self):
        result = clean('第一行\n第二行', only('keep_hard_newline'))
        assert result == '第一行\n第二行'

    def test_toggle_off(self):
        cfg = without('keep_hard_newline')
        text = '段落一\n\n\n\n段落二'
        result = RuleEngine.clean(text, cfg)
        assert '\n\n\n' in result


# ══════════════════════════════════════════════════════════════════
# R3: 空格合并
# ══════════════════════════════════════════════════════════════════

class TestMergeSpaces:
    def test_multi_space_to_single(self):
        result = clean('hello   world', only('merge_spaces'))
        assert result == 'hello world'

    def test_single_space_kept(self):
        result = clean('hello world', only('merge_spaces'))
        assert result == 'hello world'

    def test_cjk_spaces_removed(self):
        """CJK 为主时，移除所有空格。"""
        result = clean('这 是 中 文', only('merge_spaces'))
        assert result == '这是中文'

    def test_cjk_ratio_threshold(self):
        """CJK 占比较高（≥40%）时移除所有空格。"""
        result = clean('使用 Python 编程', only('merge_spaces'))
        # CJK: 使用编程 = 4, ASCII: Python = 6, ratio = 4/10 = 0.4
        assert ' ' not in result

    def test_english_keeps_word_spaces(self):
        """英文为主时保留词间空格。"""
        result = clean('hello   world foo   bar', only('merge_spaces'))
        assert result == 'hello world foo bar'

    def test_cjk_adjacent_spaces_removed(self):
        """英文为主但 CJK 旁空格移除。"""
        result = clean('Hello 世界 Good 夜晚', only('merge_spaces'))
        # 所有 CJK 字符旁的空格都被移除（前后都移除）
        assert result == 'Hello世界Good夜晚'

    def test_list_line_only_merges(self):
        """列表行仅合并多余空格，不改变结构。"""
        result = clean('- hello   world', only('merge_spaces'))
        assert result == '- hello world'

    def test_toggle_off(self):
        cfg = without('merge_spaces')
        result = RuleEngine.clean('hello   world', cfg)
        assert '   ' in result

    def test_only_rule(self):
        result = clean('hello   world', only('merge_spaces'))
        assert result == 'hello world'


# ══════════════════════════════════════════════════════════════════
# R4: 智能标点
# ══════════════════════════════════════════════════════════════════

class TestSmartPunctuation:
    def test_english_keeps_half_width(self):
        result = clean('Hello, world!', only('smart_punctuation'))
        assert ',' in result and '!' in result
        assert '，' not in result

    def test_chinese_gets_full_width(self):
        result = clean('你好,世界!', only('smart_punctuation'))
        assert '，' in result and '！' in result

    def test_list_dot_not_converted(self):
        """列表编号的点（如 1. ）不应被转为全角。"""
        result = clean('1. first item', only('smart_punctuation'))
        assert '1.' in result
        assert '1．' not in result

    def test_semicolon(self):
        result = clean('中文;分号', only('smart_punctuation'))
        assert '；' in result

    def test_colon(self):
        result = clean('English:colon', only('smart_punctuation'))
        assert ':' in result
        assert '：' not in result

    def test_full_to_half_in_english(self):
        result = clean('Hello，world！', only('smart_punctuation'))
        assert ',' in result and '!' in result

    def test_mixed_context(self):
        """混合上下文时，结果应保持合理（不崩溃）。"""
        result = clean('中文，English.', only('smart_punctuation'))
        assert result is not None and len(result) > 0

    def test_toggle_off(self):
        cfg = without('smart_punctuation')
        result = RuleEngine.clean('你好,世界', cfg)
        assert ',' in result

    def test_only_rule(self):
        result = clean('你好,世界!', only('smart_punctuation'))
        assert '，' in result and '！' in result


# ══════════════════════════════════════════════════════════════════
# R5: 盘古间距
# ══════════════════════════════════════════════════════════════════

class TestPanguSpacing:
    def test_cjk_before_english(self):
        result = clean('中文English', only('pangu_spacing'))
        assert '中文 English' in result

    def test_english_before_cjk(self):
        result = clean('Hello世界', only('pangu_spacing'))
        assert 'Hello 世界' in result

    def test_number_after_cjk(self):
        result = clean('共100个', only('pangu_spacing'))
        assert '共 100 个' in result

    def test_already_spaced_normalized(self):
        result = clean('中文  English', only('pangu_spacing'))
        assert '中文 English' in result

    def test_multiple_boundaries(self):
        result = clean('使用Python编程', only('pangu_spacing'))
        assert '使用 Python 编程' in result

    def test_list_line_skipped(self):
        """列表行不应被盘古间距修改。"""
        result = clean('- 中文English', only('pangu_spacing'))
        assert '- 中文English' in result

    def test_pure_english_unchanged(self):
        result = clean('hello world', only('pangu_spacing'))
        assert result == 'hello world'

    def test_pure_cjk_unchanged(self):
        result = clean('你好世界', only('pangu_spacing'))
        assert result == '你好世界'

    def test_toggle_off(self):
        cfg = without('pangu_spacing')
        result = RuleEngine.clean('中文English', cfg)
        assert '中文English' in result

    def test_only_rule(self):
        result = clean('中文English', only('pangu_spacing'))
        assert result == '中文 English'


# ══════════════════════════════════════════════════════════════════
# R6: 行首尾清理
# ══════════════════════════════════════════════════════════════════

class TestTrimLines:
    def test_leading_spaces(self):
        result = clean('   前导空格', only('trim_lines'))
        assert result == '前导空格'

    def test_trailing_spaces(self):
        result = clean('尾随空格   ', only('trim_lines'))
        assert result == '尾随空格'

    def test_both_sides(self):
        result = clean('  hello  ', only('trim_lines'))
        assert result == 'hello'

    def test_multi_line(self):
        result = clean('  line1  \n  line2  ', only('trim_lines'))
        assert result == 'line1\nline2'

    def test_whitespace_only_returned_as_is(self):
        """纯空白文本被 clean() 入口直接返回，不经过任何规则。"""
        result = clean('  \n  \n  ', only('trim_lines'))
        assert result == '  \n  \n  '

    def test_lines_with_content_trimmed(self):
        result = clean('  hello  \n  world  ', only('trim_lines'))
        assert result == 'hello\nworld'

    def test_toggle_off(self):
        cfg = without('trim_lines')
        result = RuleEngine.clean('  hello  ', cfg)
        assert result.startswith(' ') or result.endswith(' ')


# ══════════════════════════════════════════════════════════════════
# 边界情况
# ══════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_empty_string(self):
        assert clean('') == ''

    def test_none_input(self):
        assert RuleEngine.clean(None, ALL_ON) == ''

    def test_whitespace_only(self):
        assert clean('   ') == '   '

    def test_single_char(self):
        assert clean('a') == 'a'

    def test_newlines_only(self):
        result = clean('\n\n\n')
        assert result is not None

    def test_no_rules_enabled(self):
        text = 'hello   world\n\n\n中文English'
        result = RuleEngine.clean(text, ALL_OFF)
        assert result == text

    def test_special_characters(self):
        result = clean('@#$%^&*()')
        assert result is not None

    def test_unicode_emoji(self):
        result = clean('hello 🌍 world')
        assert '🌍' in result

    def test_very_long_text(self):
        text = '这是一段很长的文本。' * 1000
        result = clean(text)
        assert len(result) > 0


# ══════════════════════════════════════════════════════════════════
# 规则独立性（每条规则独立启用时的正确性）
# ══════════════════════════════════════════════════════════════════

class TestRuleIndependence:
    """验证每条规则可以独立工作，不依赖其他规则。"""

    def test_merge_soft_newline_alone(self):
        result = clean('第一行\n第二行', only('merge_soft_newline'))
        assert result == '第一行第二行'

    def test_keep_hard_newline_alone(self):
        result = clean('a\n\n\nb', only('keep_hard_newline'))
        assert result == 'a\n\nb'

    def test_merge_spaces_alone(self):
        result = clean('hello   world', only('merge_spaces'))
        assert result == 'hello world'

    def test_smart_punctuation_alone(self):
        result = clean('你好,世界', only('smart_punctuation'))
        assert '，' in result

    def test_pangu_spacing_alone(self):
        result = clean('中文English', only('pangu_spacing'))
        assert '中文 English' in result

    def test_trim_lines_alone(self):
        result = clean('  hello  ', only('trim_lines'))
        assert result == 'hello'

    def test_protect_code_blocks_alone(self):
        text = '```\ncode\n```'
        result = clean(text, only('protect_code_blocks'))
        assert 'code' in result

    def test_protect_lists_alone(self):
        text = '- item1\n- item2'
        result = clean(text, only('protect_lists'))
        assert '- item1\n- item2' in result


# ══════════════════════════════════════════════════════════════════
# 规则组合 / 集成测试
# ══════════════════════════════════════════════════════════════════

class TestIntegration:
    def test_pdf_typical_copy(self):
        pdf = (
            '这是论文的第一段，描述了研究背\n'
            '景和主要贡献。本研究采用了新的\n'
            '方法论。\n\n'
            '第二段开始讨论实验结果，包括：\n'
            '- 实验一的结果\n'
            '- 实验二的结果\n\n'
            '结论部分总结了全文。'
        )
        result = clean(pdf)
        assert '- 实验一的结果\n- 实验二的结果' in result
        assert '\n\n' in result
        assert '研究背\n景' not in result

    def test_code_block_with_surrounding_text(self):
        text = (
            '这是一段说明文字。\n\n'
            '```python\n'
            'x = 1 + 2\n'
            'print(x)\n'
            '```\n\n'
            '上面的代码输出了3。'
        )
        result = clean(text)
        assert 'x = 1 + 2' in result
        assert 'print(x)' in result
        assert '说明文字' in result

    def test_list_between_paragraphs(self):
        text = '引言段落。\n\n- 要点一\n- 要点二\n\n总结段落。'
        result = clean(text)
        assert '- 要点一\n- 要点二' in result
        assert '引言段落' in result
        assert '总结段落' in result

    def test_mixed_cjk_english_full(self):
        text = '使用Python(3.10)开发的项目'
        result = clean(text)
        assert 'Python' in result
        assert '3.10' in result

    def test_multiple_code_blocks(self):
        text = '前文\n```\ncode1\n```\n中间文字\n```\ncode2\n```\n后文'
        result = clean(text)
        assert 'code1' in result
        assert 'code2' in result

    def test_toggle_combination_r3_r5(self):
        """关闭空格合并和盘古间距，其他保持。"""
        cfg = without('merge_spaces', 'pangu_spacing')
        result = RuleEngine.clean('hello   world  中文English', cfg)
        assert '   ' in result
        assert '中文English' in result

    def test_all_rules_coherent(self):
        """全规则开启时的综合测试。"""
        text = (
            '研究 背景:\n'
            '  本 项目 基于Python(3.10)  \n\n'
            '- 特性一\n'
            '- 特性二\n\n'
            '实验 结果如下:\n'
            '准确率达到95%以上'
        )
        result = clean(text)
        # 段落分隔保留
        assert '\n\n' in result
        # 列表保留
        assert '- 特性一\n- 特性二' in result
        # 空格合理
        assert 'Python' in result
