# 规则引擎：8条清洗规则，纯函数，无副作用，执行顺序在 clean() 中集中管理。
import re

# 扩展CJK字符范围，包含日韩文字
_CJK_PATTERN = re.compile(
    r'[\u4e00-\u9fff\u3400-\u4dbf\uff00-\uffef\u3000-\u303f'  # 中日韩统一表意文字、符号
    r'\u3040-\u309f\u30a0-\u30ff'  # 日文假名
    r'\uac00-\ud7af'  # 韩文谚文
    r'\u31c0-\u31ef\u2e80-\u2eff]'  # 其他CJK符号
)
_ASCII_ALPHA = re.compile(r'[a-zA-Z0-9]')

_FULL_TO_HALF = str.maketrans('\uff0c\u3002\uff01\uff1f\uff1b\uff1a', ',.!?;:')
_HALF_TO_FULL = str.maketrans(',.!?;:', '\uff0c\u3002\uff01\uff1f\uff1b\uff1a')


class RuleEngine:

    _PLACEHOLDER_PREFIX = '\x00CODEBLOCK_'

    @staticmethod
    def clean(text: str, config: dict) -> str:
        """
        清洗文本的主入口

        Args:
            text: 待清洗的文本
            config: 配置字典，包含各规则的开关

        Returns:
            清洗后的文本
        """
        # 输入验证
        if text is None:
            return ''
        if not isinstance(text, str):
            text = str(text)
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

        # 规则1: 合并软换行（跳过受保护行和代码块占位符）
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
            if config.get('pangu_spacing', True):
                para = RuleEngine._pangu_spacing(para)
            if config.get('smart_punctuation', True):
                para = RuleEngine._smart_punctuation(para)
            if config.get('trim_lines', True):
                para = RuleEngine._trim_lines(para)
            processed.append(para)

        text = '\n\n'.join(processed)

        # 还原代码块 (修复：处理新的元组格式)
        for placeholder, (prefix_marker, content) in code_blocks.items():
            # prefix_marker 是 'LEADING_NL' 或 ''
            # 占位符替换时保留其前导换行（如果有）
            text = text.replace(placeholder, content)

        return text

    @staticmethod
    def _extract_code_blocks(text: str, store: dict) -> str:
        """
        将 fenced 代码块（``` 或 ~~~）替换为占位符，原文存入 store。

        注意：仅保护围栏代码块，不再自动检测缩进代码块。
        原因：4空格/Tab缩进在中文排版中广泛使用（段落缩进、引用等），
        自动检测会导致中文正文被误保护而跳过清洗。
        围栏代码块有明确的 ```/~~~ 标记，零误判。
        """
        counter = 0

        def _replace_fenced(m):
            nonlocal counter
            matched = m.group(0)
            content = matched[1:] if matched.startswith('\n') else matched
            key = f'{RuleEngine._PLACEHOLDER_PREFIX}{counter}\x00'
            store[key] = ('LEADING_NL' if matched.startswith('\n') else '', content)
            counter += 1
            return '\n' + key if matched.startswith('\n') else key

        text = re.sub(
            r'(?:^|\n)([ \t]*(?:```|~~~)[^\n]*\n[\s\S]*?\n[ \t]*(?:```|~~~)[ \t]*)',
            _replace_fenced,
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
        """
        合并非空行的软换行

        修复：跳过包含代码块占位符的行，避免破坏代码块结构
        """
        result = []
        i = 0
        while i < len(lines):
            line = lines[i]

            # 跳过空行
            if not line.strip():
                result.append(line)
                i += 1
                continue

            # 跳过保护的行（列表等）
            if i in protected:
                result.append(line)
                i += 1
                continue

            # 修复：跳过包含代码块占位符的行
            if RuleEngine._PLACEHOLDER_PREFIX in line:
                result.append(line)
                i += 1
                continue

            # 合并连续的非空、非保护行
            merged = line
            while (i + 1 < len(lines)
                   and lines[i + 1].strip()
                   and (i + 1) not in protected
                   and RuleEngine._PLACEHOLDER_PREFIX not in lines[i + 1]):  # 修复：检查占位符
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
        """
        智能空格处理。

        核心原则：CJK字符之间的空格在任何情况下都应移除。
        中日韩文本中，字符之间不需要空格分隔，空格几乎总是多余的。

        策略：
        - 列表行：仅合并多余空格，保留列表结构
        - 中文为主（≥40% CJK）：移除所有空格
        - 英文为主或混合：保留词间空格，但始终移除CJK字符之间的空格
        """
        lines = text.split('\n')
        result = []

        # CJK字符范围（用于空格移除的正则）
        _CJK_CHAR_CLASS = r'\u4e00-\u9fff\u3400-\u4dbf\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af\u31c0-\u31ef\u2e80-\u2eff\uff00-\uffef\u3000-\u303f'
        # 列表模式
        list_pattern = re.compile(r'^(\s*[-*+]|\s*\d+[.)]) ')

        for line in lines:
            # 列表行：仅合并多余空格，保留列表结构
            if list_pattern.match(line):
                result.append(re.sub(r' {2,}', ' ', line))
                continue

            # 分析语言组成
            cjk_count = len(_CJK_PATTERN.findall(line))
            ascii_count = len(_ASCII_ALPHA.findall(line))
            total_chars = cjk_count + ascii_count

            if total_chars == 0:
                result.append(re.sub(r' {2,}', ' ', line))
                continue

            cjk_ratio = cjk_count / total_chars

            if cjk_ratio >= 0.4:
                # 中文为主：移除所有空格（CJK文本中空格几乎总是多余的）
                processed = re.sub(r' +', '', line)
            else:
                # 英文为主或混合：先合并多余空格，再移除CJK字符间的空格
                processed = re.sub(r' {2,}', ' ', line)
                # 移除CJK字符后的空格：本 项目 → 本项目
                processed = re.sub(
                    f'([{_CJK_CHAR_CLASS}]) +', r'\1', processed)
                # 移除CJK字符前的空格：项目 本 → 项目本
                processed = re.sub(
                    f' +([{_CJK_CHAR_CLASS}])', r'\1', processed)

            result.append(processed)

        return '\n'.join(result)

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
        """
        Pangu间距：在中英文之间添加空格
        智能模式：避免破坏技术术语的紧凑排版

        策略：
        - 跳过列表行
        - 检测技术术语模式（如Python 3、TensorFlow 2）
        - 对已有空格的边界，标准化为单个空格
        - 对紧密连接的中英文，添加空格
        """
        lines = text.split('\n')
        result = []

        # 列表模式检测
        list_pattern = re.compile(r'^(\s*[-*+]|\s*\d+[.)]) ')
        # 技术术语模式：英文单词后跟数字/符号（如 Python 3、OpenAI API）
        tech_pattern = re.compile(r'[a-zA-Z]+\s*[0-9.(){}[\]]+')

        for line in lines:
            # 跳过列表行
            if list_pattern.match(line):
                result.append(line)
                continue

            # 检测是否包含大量技术术语
            tech_matches = len(tech_pattern.findall(line))
            if tech_matches > 0:
                # 技术文档：保守处理，只标准化现有空格
                processed = re.sub(r'([\u4e00-\u9fff\u3400-\u4dbf\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af])\s+([a-zA-Z0-9])', r'\1 \2', line)
                processed = re.sub(r'([a-zA-Z0-9])\s+([\u4e00-\u9fff\u3400-\u4dbf\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af])', r'\1 \2', processed)
            else:
                # 普通文本：添加中英文间距
                processed = re.sub(r'([\u4e00-\u9fff\u3400-\u4dbf\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af])\s*([a-zA-Z0-9])', r'\1 \2', line)
                processed = re.sub(r'([a-zA-Z0-9])\s*([\u4e00-\u9fff\u3400-\u4dbf\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af])', r'\1 \2', processed)

            result.append(processed)

        return '\n'.join(result)

    @staticmethod
    def _trim_lines(text: str) -> str:
        return '\n'.join(line.strip() for line in text.split('\n'))
