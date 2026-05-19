"""规则引擎：8条清洗规则，纯函数，无副作用。

执行顺序（有依赖，不可随意调换）：
  Phase 1 — 保护区域提取：R7 代码块 → R8 列表标记
  Phase 2 — 行级变换：   R1 软换行合并 → R2 空行折叠
  Phase 3 — 段落级变换： R3 空格合并 → R4 智能标点 → R5 盘古间距 → R6 行首尾清理
  Phase 4 — 还原保护区域
"""
import re

# ── Unicode 字符范围 ──────────────────────────────────────────────
# CJK 核心（表意文字 + 假名 + 谚文）：用于盘古间距、标点上下文判断
_CJK_CORE = (
    r'一-鿿'  # CJK Unified Ideographs
    r'㐀-䶿'  # CJK Extension A
    r'぀-ゟ'  # Hiragana
    r'゠-ヿ'  # Katakana
    r'가-힯'  # Hangul Syllables
    r'㇀-㇯'  # CJK Strokes
    r'⺀-⻿'  # CJK Radicals Supplement
)
# CJK 扩展（含全角形式和符号）：用于语言检测、软换行合并
_CJK_EXT = _CJK_CORE + (
    r'＀-￯'  # Fullwidth Forms
    r'　-〿'  # CJK Symbols and Punctuation
)

# ── 预编译正则 ────────────────────────────────────────────────────
_CJK_CORE_RE = re.compile(f'[{_CJK_CORE}]')
_CJK_EXT_RE = re.compile(f'[{_CJK_EXT}]')
_ASCII_ALNUM_RE = re.compile(r'[a-zA-Z0-9]')
_LIST_LINE_RE = re.compile(
    r'^(?:'
    r'\s*[-*+] |'                          # bullet: - * +
    r'\s*\d+[.)] |'                        # numbered: 1. 2)
    r'\d+、\s*|'                           # Chinese numbered: 1、
    r'[一二三四五六七八九十]+[、]\s*|'      # Chinese ordinal: 一、
    r'[（(]\d+[）)]\s*'                   # parenthesized: （1）
    r')')
_MULTI_SPACE_RE = re.compile(r' {2,}')
_MULTI_NL_RE = re.compile(r'\n{3,}')
_FENCED_CODE_RE = re.compile(
    r'(?:^|\n)([ \t]*(?:```|~~~)[^\n]*\n[\s\S]*?\n[ \t]*(?:```|~~~)[ \t]*)')

# 盘古间距：CJK核心 ↔ ASCII 字母数字
_PANGU_C2A = re.compile(f'([{_CJK_CORE}])\\s*([a-zA-Z0-9])')
_PANGU_A2C = re.compile(f'([a-zA-Z0-9])\\s*([{_CJK_CORE}])')

# CJK 旁空格移除（merge_spaces 用）
_CJK_SPACE_AFTER = re.compile(f'([{_CJK_EXT}]) +')
_CJK_SPACE_BEFORE = re.compile(f' +([{_CJK_EXT}])')

# 句末标点（CopyPlusPlus 风格：行尾为句末标点时保留换行）
_SENTENCE_END = frozenset('。！？.!?')

# ── 标点映射表 ────────────────────────────────────────────────────
_FULL_PUNCT = '，。！？；：'  # ，。！？；：
_HALF_PUNCT = ',.!?;:'
_FULL_TO_HALF = str.maketrans(_FULL_PUNCT, _HALF_PUNCT)
_HALF_TO_FULL = str.maketrans(_HALF_PUNCT, _FULL_PUNCT)


class RuleEngine:
    """规则引擎：8条清洗规则，纯静态方法，无实例状态。"""

    _PH = '\x00CB_'  # 占位符前缀

    # ── 主入口 ────────────────────────────────────────────────────

    @staticmethod
    def clean(text: str, config: dict) -> str:
        if not text or not text.strip():
            return text or ''

        # Phase 1: 保护区域提取
        code_blocks: dict[str, str] = {}
        if config.get('protect_code_blocks', True):
            text = RuleEngine._extract_code_blocks(text, code_blocks)

        lines = text.split('\n')
        protected: set[int] = set()
        if config.get('protect_lists', True):
            protected = RuleEngine._mark_list_lines(lines)

        # Phase 2: 行级变换
        if config.get('merge_soft_newline', True):
            lines = RuleEngine._merge_soft_newlines(lines, protected)
        text = '\n'.join(lines)

        if config.get('keep_hard_newline', True):
            text = _MULTI_NL_RE.sub('\n\n', text)

        # Phase 3: 段落级变换（按文档顺序：R3→R4→R5→R6）
        paragraphs = text.split('\n\n')
        processed = []
        for para in paragraphs:
            if RuleEngine._PH in para:
                processed.append(para)
                continue
            if config.get('merge_spaces', True):
                para = RuleEngine._merge_spaces(para)
            if config.get('smart_punctuation', True):
                para = RuleEngine._smart_punctuation(para)
            if config.get('pangu_spacing', True):
                para = RuleEngine._pangu_spacing(para)
            if config.get('trim_lines', True):
                para = RuleEngine._trim_lines(para)
            processed.append(para)
        text = '\n\n'.join(processed)

        # Phase 4: 还原保护区域
        for placeholder, original in code_blocks.items():
            text = text.replace(placeholder, original)

        return text

    # ── R7: 代码块保护 ───────────────────────────────────────────

    @staticmethod
    def _extract_code_blocks(text: str, store: dict) -> str:
        """提取 fenced 代码块（```/~~~），替换为占位符。

        仅保护围栏代码块。4空格/Tab 缩进在中文排版中太常见（段落缩进、引用），
        自动检测会导致正文被误保护。
        """
        counter = 0

        def _replace(m):
            nonlocal counter
            matched = m.group(0)
            has_leading_nl = matched.startswith('\n')
            key = f'{RuleEngine._PH}{counter}\x00'
            store[key] = matched[1:] if has_leading_nl else matched
            counter += 1
            return ('\n' + key) if has_leading_nl else key

        return _FENCED_CODE_RE.sub(_replace, text)

    # ── R8: 列表行标记 ──────────────────────────────────────────

    @staticmethod
    def _mark_list_lines(lines: list) -> set:
        return {i for i, line in enumerate(lines) if _LIST_LINE_RE.match(line)}

    # ── R1: 软换行合并 ──────────────────────────────────────────

    @staticmethod
    def _merge_soft_newlines(lines: list, protected: set) -> list:
        """合并非空行的软换行。

        - 列表行作为段落起点（与前文断开），但其后续行合并进来
        - 非列表段落：句末标点后保留换行（CopyPlusPlus 风格）
        - 列表段落：合并所有续行（列表项应完整合并为一个段落）
        """
        result = []
        i = 0
        while i < len(lines):
            line = lines[i]

            # 跳过空行和占位符行
            if not line.strip() or RuleEngine._PH in line:
                result.append(line)
                i += 1
                continue

            is_list_para = i in protected
            merged = line

            while (i + 1 < len(lines)
                   and lines[i + 1].strip()
                   and (i + 1) not in protected
                   and RuleEngine._PH not in lines[i + 1]):
                # 非列表段落：句末标点后保留换行
                if not is_list_para and _is_sentence_end(merged):
                    break
                i += 1
                next_text = lines[i].strip()
                if (_CJK_EXT_RE.search(merged[-1:])
                        or _CJK_EXT_RE.search(next_text[:1])):
                    merged += next_text
                else:
                    merged += ' ' + next_text

            result.append(merged)
            i += 1
        return result

    # ── R3: 空格合并 ──────────────────────────────────────────

    @staticmethod
    def _merge_spaces(text: str) -> str:
        """智能空格处理。CJK 为主时移除所有空格，英文为主时保留词间空格。"""
        lines = text.split('\n')
        result = []
        for line in lines:
            if _LIST_LINE_RE.match(line):
                result.append(_MULTI_SPACE_RE.sub(' ', line))
                continue

            cjk = len(_CJK_EXT_RE.findall(line))
            asc = len(_ASCII_ALNUM_RE.findall(line))
            total = cjk + asc

            if total == 0:
                result.append(_MULTI_SPACE_RE.sub(' ', line))
                continue

            if cjk / total >= 0.4:
                # CJK 为主：字符间空格几乎总是多余的
                result.append(re.sub(r' +', '', line))
            else:
                # 英文为主：合并多余空格，移除 CJK 字符旁的空格
                processed = _MULTI_SPACE_RE.sub(' ', line)
                processed = _CJK_SPACE_AFTER.sub(r'\1', processed)
                processed = _CJK_SPACE_BEFORE.sub(r'\1', processed)
                result.append(processed)
        return '\n'.join(result)

    # ── R4: 智能标点 ──────────────────────────────────────────

    @staticmethod
    def _smart_punctuation(text: str) -> str:
        """根据上下文智能转换全/半角标点。"""
        chars = list(text)
        for i, ch in enumerate(chars):
            if ch in _FULL_PUNCT:
                ctx = text[max(0, i - 5):i] + text[i + 1:i + 6]
                if _ascii_count(ctx) > _cjk_count(ctx):
                    chars[i] = ch.translate(_FULL_TO_HALF)
            elif ch in _HALF_PUNCT:
                if ch == '.' and i > 0 and text[i - 1].isdigit():
                    continue
                ctx = text[max(0, i - 5):i] + text[i + 1:i + 6]
                if _cjk_count(ctx) > _ascii_count(ctx):
                    chars[i] = ch.translate(_HALF_TO_FULL)
        return ''.join(chars)

    # ── R5: 盘古间距 ──────────────────────────────────────────

    @staticmethod
    def _pangu_spacing(text: str) -> str:
        """在 CJK 字符与 ASCII 字母数字之间添加空格。"""
        lines = text.split('\n')
        result = []
        for line in lines:
            if _LIST_LINE_RE.match(line):
                result.append(line)
                continue
            line = _PANGU_C2A.sub(r'\1 \2', line)
            line = _PANGU_A2C.sub(r'\1 \2', line)
            result.append(line)
        return '\n'.join(result)

    # ── R6: 行首尾清理 ────────────────────────────────────────

    @staticmethod
    def _trim_lines(text: str) -> str:
        return '\n'.join(line.strip() for line in text.split('\n'))


def _cjk_count(s: str) -> int:
    return len(_CJK_CORE_RE.findall(s))


def _ascii_count(s: str) -> int:
    return len(_ASCII_ALNUM_RE.findall(s))


def _is_sentence_end(line: str) -> bool:
    """行尾为句末标点时返回 True，用于保留换行（CopyPlusPlus 风格）。"""
    s = line.rstrip()
    return bool(s) and s[-1] in _SENTENCE_END
