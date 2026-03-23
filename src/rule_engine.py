# 规则引擎：8条清洗规则，纯函数，无副作用，执行顺序在 clean() 中集中管理。
import re

_CJK_PATTERN = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uff00-\uffef\u3000-\u303f]')
_ASCII_ALPHA = re.compile(r'[a-zA-Z0-9]')

_FULL_TO_HALF = str.maketrans('\uff0c\u3002\uff01\uff1f\uff1b\uff1a', ',.!?;:')
_HALF_TO_FULL = str.maketrans(',.!?;:', '\uff0c\u3002\uff01\uff1f\uff1b\uff1a')


class RuleEngine:

    _PLACEHOLDER_PREFIX = '\x00CODEBLOCK_'

    @staticmethod
    def clean(text: str, config: dict) -> str:
        if not text or not text.strip():
            return text

        # 规则7: 提取代码块，用占位符替换，保护其不受后续规则影响
        code_blocks: dict[str, str] = {}
        if config.get('protect_code_blocks', True):
            text = RuleEngine._extract_code_blocks(text, code_blocks)

        lines = text.split('\n')

        # 规则8: 标记列表行
        protected: set[int] = set()
        if config.get('protect_lists', True):
            protected |= RuleEngine._find_list_lines(lines)

        # 规则1: 合并软换行（跳过受保护行）
        if config.get('merge_soft_newline', True):
            lines = RuleEngine._merge_soft_newlines(lines, protected)

        text = '\n'.join(lines)

        # 规则2: 多余空行折叠为双换行
        if config.get('keep_hard_newline', True):
            text = re.sub(r'\n{3,}', '\n\n', text)

        # 按段落分隔后逐段处理
        paragraphs = text.split('\n\n')
        processed = []
        for para in paragraphs:
            # 含占位符的段落跳过所有清洗
            if RuleEngine._PLACEHOLDER_PREFIX in para:
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

        # 还原代码块
        for placeholder, original in code_blocks.items():
            text = text.replace(placeholder, original)

        return text

    @staticmethod
    def _extract_code_blocks(text: str, store: dict) -> str:
        """将 fenced 代码块和连续缩进代码块替换为占位符，原文存入 store。"""
        counter = 0

        # 1) fenced code blocks (``` or ~~~)
        def _replace_fenced(m):
            nonlocal counter
            key = f'{RuleEngine._PLACEHOLDER_PREFIX}{counter}\x00'
            store[key] = m.group(0)
            counter += 1
            return key

        text = re.sub(
            r'(?:^|\n)([ \t]*(?:```|~~~)[^\n]*\n[\s\S]*?\n[ \t]*(?:```|~~~))',
            lambda m: ('\n' if m.group(0).startswith('\n') else '') + _replace_fenced(m),
            text,
        )

        # 2) indented code blocks: 连续的 ≥4空格/Tab 开头的非空行
        def _replace_indented(m):
            nonlocal counter
            key = f'{RuleEngine._PLACEHOLDER_PREFIX}{counter}\x00'
            store[key] = m.group(0)
            counter += 1
            return key

        text = re.sub(
            r'((?:^|\n)(?:(?:    |\t)[^\n]*\n?){2,})',
            lambda m: ('\n' if m.group(0).startswith('\n') else '') + _replace_indented(m),
            text,
        )

        return text

    @staticmethod
    def _find_list_lines(lines: list) -> set:
        protected: set[int] = set()
        list_pattern = re.compile(r'^(\s*[-*+]|\s*\d+[.)]) ')
        for i, line in enumerate(lines):
            if list_pattern.match(line):
                protected.add(i)
        return protected

    @staticmethod
    def _merge_soft_newlines(lines: list, protected: set) -> list:
        result = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                result.append(line)
                i += 1
                continue
            if i in protected:
                result.append(line)
                i += 1
                continue
            merged = line
            while (i + 1 < len(lines)
                   and lines[i + 1].strip()
                   and (i + 1) not in protected):
                i += 1
                next_line = lines[i].strip()
                # 中文行合并不加空格，纯英文行加空格
                if (_CJK_PATTERN.search(merged[-1:])
                        or _CJK_PATTERN.search(next_line[:1])):
                    merged += next_line
                else:
                    merged += ' ' + next_line
            result.append(merged)
            i += 1
        return result

    @staticmethod
    def _merge_spaces(text: str) -> str:
        return re.sub(r' {2,}', ' ', text)

    @staticmethod
    def _smart_punctuation(text: str) -> str:
        result = list(text)
        for i, ch in enumerate(result):
            if ch in '\uff0c\u3002\uff01\uff1f\uff1b\uff1a':
                context = text[max(0, i - 5):i] + text[i + 1:i + 6]
                cjk = len(_CJK_PATTERN.findall(context))
                asc = len(_ASCII_ALPHA.findall(context))
                if asc > cjk and asc > 0:
                    result[i] = ch.translate(_FULL_TO_HALF)
            elif ch in ',.!?;:':
                # 跳过列表编号的点（如 "1. " "2. "）
                if ch == '.' and i > 0 and text[i - 1].isdigit():
                    continue
                context = text[max(0, i - 5):i] + text[i + 1:i + 6]
                cjk = len(_CJK_PATTERN.findall(context))
                asc = len(_ASCII_ALPHA.findall(context))
                if cjk > asc and cjk > 0:
                    result[i] = ch.translate(_HALF_TO_FULL)
        return ''.join(result)

    @staticmethod
    def _pangu_spacing(text: str) -> str:
        text = re.sub(r'([\u4e00-\u9fff\u3400-\u4dbf])([a-zA-Z0-9])', r'\1 \2', text)
        text = re.sub(r'([a-zA-Z0-9])([\u4e00-\u9fff\u3400-\u4dbf])', r'\1 \2', text)
        return text

    @staticmethod
    def _trim_lines(text: str) -> str:
        return '\n'.join(line.strip() for line in text.split('\n'))
