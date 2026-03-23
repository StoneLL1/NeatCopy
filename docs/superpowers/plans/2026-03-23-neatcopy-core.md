# NeatCopy Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 NeatCopy 完整核心功能——系统托盘常驻、全局热键触发、规则引擎+大模型两种模式清洗剪贴板文本，并打包为单 exe。

**Architecture:** 单 Python 进程，Qt 事件循环为主线程，`keyboard` 库在后台线程监听全局热键，通过 `pyqtSignal` 回调主线程处理剪贴板；LLM 请求用 `QThread` 包装 asyncio，防止阻塞 UI。配置统一由 `ConfigManager` 单例读写 `%APPDATA%\NeatCopy\config.json`。

**Tech Stack:** Python 3.11+, PyQt6, keyboard, pywin32, httpx, langdetect, pyperclip, PyInstaller

---

## 文件结构总览

```
NeatCopy/
├── src/
│   ├── main.py                   # 入口，QApplication + 初始化链
│   ├── config_manager.py         # 单例配置读写
│   ├── rule_engine.py            # 8条规则，纯函数，无副作用
│   ├── tray_manager.py           # 托盘图标、菜单、Toast、图标变色
│   ├── hotkey_manager.py         # 全局热键（独立热键 + 双击Ctrl+C）
│   ├── clip_processor.py         # 调度：读剪贴板→规则/LLM→写剪贴板
│   ├── llm_client.py             # OpenAI兼容接口，httpx异步
│   └── ui/
│       ├── __init__.py
│       └── settings_window.py    # QDialog，三Tab设置界面
├── assets/
│   ├── icon_idle.png             # 16x16 灰色图标
│   ├── icon_processing.png       # 16x16 黄色图标
│   ├── icon_success.png          # 16x16 绿色图标
│   └── icon_error.png            # 16x16 红色图标
├── tests/
│   ├── conftest.py               # 共享 fixtures（tmp config dir）
│   ├── test_config_manager.py    # ConfigManager 单元测试
│   ├── test_rule_engine.py       # 8条规则单元测试
│   └── test_llm_client.py        # LLMClient Mock测试
├── requirements.txt
└── NeatCopy.spec                 # PyInstaller 配置（Task 10生成）
```

---

## Task 1: ConfigManager — 配置读写单例

**Files:**
- Create: `src/config_manager.py`
- Create: `tests/conftest.py`
- Create: `tests/test_config_manager.py`
- Create: `requirements.txt`

### 前置：安装依赖

- [ ] **Step 1.1: 创建 requirements.txt**

```
PyQt6>=6.6.0
keyboard>=0.13.5
pywin32>=306
httpx>=0.27.0
langdetect>=1.0.9
pyperclip>=1.8.2
pyinstaller>=6.0.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

- [ ] **Step 1.2: 安装依赖**

```bash
pip install -r requirements.txt
```

Expected: 所有包安装成功，无报错。

### TDD: ConfigManager

- [ ] **Step 1.3: 创建 tests/conftest.py（共享 tmp 目录 fixture）**

```python
import pytest
import tempfile
import os

@pytest.fixture
def tmp_config_dir(tmp_path, monkeypatch):
    """将 APPDATA 重定向到临时目录，避免污染真实配置。"""
    monkeypatch.setenv('APPDATA', str(tmp_path))
    return tmp_path
```

- [ ] **Step 1.4: 写失败测试**

创建 `tests/test_config_manager.py`：

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config_manager import ConfigManager

class TestConfigManagerDefaults:
    def test_creates_config_file_on_first_load(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        config_path = tmp_config_dir / 'NeatCopy' / 'config.json'
        assert config_path.exists()

    def test_default_toast_notification_is_true(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        assert cm.get('general.toast_notification') is True

    def test_default_mode_is_rules(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        assert cm.get('rules.mode') == 'rules'

    def test_default_llm_enabled_is_false(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        assert cm.get('llm.enabled') is False

class TestConfigManagerGetSet:
    def test_set_persists_to_disk(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        cm.set('general.toast_notification', False)
        # 重新实例化，模拟重启
        cm2 = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        assert cm2.get('general.toast_notification') is False

    def test_get_nested_key(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        val = cm.get('general.double_ctrl_c.interval_ms')
        assert val == 300

    def test_set_nested_key(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        cm.set('general.double_ctrl_c.interval_ms', 500)
        assert cm.get('general.double_ctrl_c.interval_ms') == 500

    def test_get_nonexistent_key_returns_none(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        assert cm.get('nonexistent.key') is None

    def test_get_nonexistent_key_returns_default(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        assert cm.get('nonexistent.key', default='fallback') == 'fallback'

class TestConfigManagerPrompts:
    def test_default_prompt_exists(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        prompts = cm.get('llm.prompts')
        assert len(prompts) >= 1
        assert prompts[0]['id'] == 'default'

    def test_default_prompt_is_readonly(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        prompts = cm.get('llm.prompts')
        assert prompts[0]['readonly'] is True
```

- [ ] **Step 1.5: 运行测试，确认全部失败**

```bash
python -m pytest tests/test_config_manager.py -v
```

Expected: `ModuleNotFoundError: No module named 'config_manager'`（正确失败）

- [ ] **Step 1.6: 实现 src/config_manager.py**

```python
import json
import os
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = {
    'general': {
        'startup_with_windows': False,
        'toast_notification': True,
        'double_ctrl_c': {'enabled': False, 'interval_ms': 300},
        'custom_hotkey': {'enabled': True, 'keys': 'ctrl+shift+c'},
    },
    'rules': {
        'mode': 'rules',
        'merge_soft_newline': True,
        'keep_hard_newline': True,
        'merge_spaces': True,
        'smart_punctuation': True,
        'pangu_spacing': True,
        'trim_lines': True,
        'protect_code_blocks': True,
        'protect_lists': True,
    },
    'llm': {
        'enabled': False,
        'base_url': 'https://api.openai.com/v1',
        'api_key': '',
        'model_id': 'gpt-4o-mini',
        'temperature': 0.2,
        'active_prompt_id': 'default',
        'prompts': [
            {
                'id': 'default',
                'name': '默认格式整理',
                'content': (
                    '你是一个文本格式整理助手。请整理以下文本的段落格式和标点符号，'
                    '保留原文所有文字内容，不增删任何内容，不修改任何措辞。'
                    '只修正格式问题：合并不必要的换行，保留真正的段落分隔，'
                    '修复标点符号使用。直接返回整理后的文本，不要任何解释。'
                ),
                'readonly': True,
            }
        ],
    },
}


class ConfigManager:
    def __init__(self, config_dir: str | None = None):
        if config_dir is None:
            appdata = os.environ.get('APPDATA', str(Path.home()))
            config_dir = os.path.join(appdata, 'NeatCopy')
        self._config_path = Path(config_dir) / 'config.json'
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        if not self._config_path.exists():
            self._write(DEFAULT_CONFIG)
            return dict(DEFAULT_CONFIG)
        with open(self._config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # 合并缺失的默认键（升级兼容）
        return self._merge_defaults(data, DEFAULT_CONFIG)

    def _merge_defaults(self, data: dict, defaults: dict) -> dict:
        result = dict(defaults)
        for k, v in data.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = self._merge_defaults(v, result[k])
            else:
                result[k] = v
        return result

    def _write(self, data: dict) -> None:
        with open(self._config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """点号分隔的嵌套键访问，如 'general.toast_notification'。"""
        parts = key.split('.')
        node = self._data
        for part in parts:
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, key: str, value: Any) -> None:
        """设置值并立即写入磁盘。"""
        parts = key.split('.')
        node = self._data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
        self._write(self._data)

    def all(self) -> dict:
        return self._data
```

- [ ] **Step 1.7: 运行测试，确认全部通过**

```bash
python -m pytest tests/test_config_manager.py -v
```

Expected: 所有测试 PASS。

- [ ] **Step 1.8: Commit**

```bash
git add requirements.txt tests/conftest.py tests/test_config_manager.py src/config_manager.py
git commit -m "feat(config): 实现 ConfigManager 单例，支持嵌套键读写和默认配置"
```

---

## Task 2: RuleEngine — 8条清洗规则

**Files:**
- Create: `src/rule_engine.py`
- Create: `tests/test_rule_engine.py`

> 所有规则函数为纯函数，无副作用。执行顺序在 `clean()` 中集中管理。

- [ ] **Step 2.1: 写失败测试**

创建 `tests/test_rule_engine.py`：

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from rule_engine import RuleEngine

# 全规则开启的默认配置
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


# ── 规则7：保护代码块 ─────────────────────────────────────────
class TestProtectCodeBlocks:
    def test_fenced_code_block_preserved(self):
        text = '前文\n```\ncode line1\ncode line2\n```\n后文'
        result = clean(text)
        assert '```\ncode line1\ncode line2\n```' in result

    def test_indented_code_block_preserved(self):
        text = '段落\n\n    import os\n    os.getcwd()\n\n后段落'
        result = clean(text)
        assert '    import os' in result


# ── 规则8：保护列表行 ─────────────────────────────────────────
class TestProtectLists:
    def test_dash_list_newlines_preserved(self):
        text = '- 项目一\n- 项目二\n- 项目三'
        result = clean(text)
        assert result == '- 项目一\n- 项目二\n- 项目三'

    def test_numbered_list_newlines_preserved(self):
        text = '1. 第一条\n2. 第二条'
        result = clean(text)
        assert '1. 第一条\n2. 第二条' in result

    def test_asterisk_list_preserved(self):
        text = '* 苹果\n* 香蕉'
        result = clean(text)
        assert '* 苹果\n* 香蕉' in result


# ── 规则1：合并软换行 ─────────────────────────────────────────
class TestMergeSoftNewlines:
    def test_single_newline_merged(self):
        assert clean('第一行\n第二行') == '第一行第二行'

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


# ── 规则2：保留空行段落 ───────────────────────────────────────
class TestKeepHardNewlines:
    def test_double_newline_kept(self):
        text = '段落一\n\n段落二'
        result = clean(text)
        assert '\n\n' in result

    def test_triple_newline_collapsed_to_double(self):
        text = '段落一\n\n\n段落二'
        result = clean(text)
        # 多余空行折叠为单个段落分隔
        assert result.count('\n\n\n') == 0


# ── 规则3：合并多余空格 ───────────────────────────────────────
class TestMergeSpaces:
    def test_multiple_spaces_merged(self):
        assert clean('hello   world') == 'hello world'

    def test_single_space_unchanged(self):
        assert clean('hello world') == 'hello world'

    def test_tabs_converted(self):
        result = clean('a\t\tb')
        assert '  ' not in result or '\t' not in result


# ── 规则3关闭 ─────────────────────────────────────────────────
class TestRuleToggle:
    def test_merge_spaces_off(self):
        cfg = {**ALL_ON, 'merge_spaces': False}
        result = RuleEngine.clean('hello   world', cfg)
        assert '   ' in result

    def test_pangu_spacing_off(self):
        cfg = {**ALL_ON, 'pangu_spacing': False}
        result = RuleEngine.clean('中文English', cfg)
        # 关闭后不加空格
        assert 'English' in result


# ── 规则5：中英文间距 ─────────────────────────────────────────
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


# ── 规则6：行首尾空白 ─────────────────────────────────────────
class TestTrimLines:
    def test_leading_whitespace_removed(self):
        result = clean('   前导空格')
        assert not result.startswith(' ')

    def test_trailing_whitespace_removed(self):
        result = clean('尾随空格   ')
        assert not result.endswith(' ')


# ── 规则4：智能全/半角标点 ───────────────────────────────────
class TestSmartPunctuation:
    def test_english_context_uses_half_width_comma(self):
        result = clean('Hello, world')
        assert ',' in result

    def test_chinese_context_keeps_full_width_comma(self):
        result = clean('你好，世界')
        assert '，' in result

    def test_mixed_not_broken(self):
        # 不应崩溃
        result = clean('中文，English.')
        assert result is not None


# ── 综合场景 ──────────────────────────────────────────────────
class TestIntegration:
    def test_pdf_typical_copy(self):
        """模拟 PDF 典型复制场景"""
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
        # 段落内换行合并
        assert '研究背景' not in result.split('\n\n')[0] or \
               '研究背\n景' not in result
        # 列表保留
        assert '- 实验一的结果\n- 实验二的结果' in result
        # 段落分隔保留
        assert '\n\n' in result
```

- [ ] **Step 2.2: 运行测试，确认失败**

```bash
python -m pytest tests/test_rule_engine.py -v
```

Expected: `ImportError: cannot import name 'RuleEngine'`

- [ ] **Step 2.3: 实现 src/rule_engine.py**

```python
import re
from typing import Union

try:
    from langdetect import detect, LangDetectException
    _LANGDETECT_AVAILABLE = True
except ImportError:
    _LANGDETECT_AVAILABLE = False

# 中文字符 Unicode 范围
_CJK_PATTERN = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uff00-\uffef\u3000-\u303f]')
_ASCII_ALPHA = re.compile(r'[a-zA-Z0-9]')

# 全角→半角标点映射
_FULL_TO_HALF = str.maketrans('，。！？；：""''（）【】', ',.!?;:""\'\'()[]')
# 半角→全角标点映射
_HALF_TO_FULL = str.maketrans(',.!?;:', '，。！？；：')


class RuleEngine:

    @staticmethod
    def clean(text: str, config: dict) -> str:
        if not text or not text.strip():
            return text

        # Step 1: 识别代码块行索引（规则7）
        lines = text.split('\n')
        protected_lines: set[int] = set()

        if config.get('protect_code_blocks', True):
            protected_lines |= RuleEngine._find_code_block_lines(lines)

        if config.get('protect_lists', True):
            protected_lines |= RuleEngine._find_list_lines(lines)

        # Step 2: 合并软换行（规则1）
        if config.get('merge_soft_newline', True):
            lines = RuleEngine._merge_soft_newlines(lines, protected_lines)

        # Step 3: 重建文本，按空行分段（规则2）
        text = '\n'.join(lines)
        if config.get('keep_hard_newline', True):
            # 多余空行（3+换行）折叠为双换行
            text = re.sub(r'\n{3,}', '\n\n', text)

        # Step 4: 段落内逐行处理
        paragraphs = text.split('\n\n')
        processed = []
        for para in paragraphs:
            if config.get('merge_spaces', True):
                para = RuleEngine._merge_spaces(para)
            if config.get('smart_punctuation', True):
                para = RuleEngine._smart_punctuation(para)
            if config.get('pangu_spacing', True):
                para = RuleEngine._pangu_spacing(para)
            if config.get('trim_lines', True):
                para = RuleEngine._trim_lines(para)
            processed.append(para)

        return '\n\n'.join(processed)

    # ── 辅助：标记代码块行 ────────────────────────────────────

    @staticmethod
    def _find_code_block_lines(lines: list[str]) -> set[int]:
        protected: set[int] = set()
        in_fence = False
        fence_start = 0
        for i, line in enumerate(lines):
            if line.startswith('```') or line.startswith('~~~'):
                if not in_fence:
                    in_fence = True
                    fence_start = i
                else:
                    in_fence = False
                    for j in range(fence_start, i + 1):
                        protected.add(j)
            elif in_fence:
                protected.add(i)
            elif line.startswith('    ') or line.startswith('\t'):
                protected.add(i)
        return protected

    @staticmethod
    def _find_list_lines(lines: list[str]) -> set[int]:
        protected: set[int] = set()
        list_pattern = re.compile(r'^(\s*[-*+]|\s*\d+[.)]) ')
        for i, line in enumerate(lines):
            if list_pattern.match(line):
                protected.add(i)
        return protected

    # ── 规则1：合并软换行 ────────────────────────────────────

    @staticmethod
    def _merge_soft_newlines(lines: list[str], protected: set[int]) -> list[str]:
        result: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            # 空行直接保留（段落分隔）
            if not line.strip():
                result.append(line)
                i += 1
                continue
            # 受保护行直接保留
            if i in protected:
                result.append(line)
                i += 1
                continue
            # 尝试合并后续行
            merged = line
            while (i + 1 < len(lines)
                   and lines[i + 1].strip()        # 下一行非空
                   and (i + 1) not in protected):  # 下一行非保护
                i += 1
                # 中文行合并不加空格，英文行合并加空格
                next_line = lines[i]
                if _CJK_PATTERN.search(merged[-1:]) or _CJK_PATTERN.search(next_line[:1]):
                    merged += next_line.strip()
                else:
                    merged += ' ' + next_line.strip()
            result.append(merged)
            i += 1
        return result

    # ── 规则3：合并多余空格 ──────────────────────────────────

    @staticmethod
    def _merge_spaces(text: str) -> str:
        # Tab 转空格，多空格合并
        text = text.replace('\t', ' ')
        text = re.sub(r' {2,}', ' ', text)
        return text

    # ── 规则4：智能全/半角标点 ──────────────────────────────

    @staticmethod
    def _smart_punctuation(text: str) -> str:
        result = list(text)
        for i, ch in enumerate(result):
            if ch in '，。！？；：':
                # 检查前后各5字符，判断是否处于英文语境
                context = text[max(0, i-5):i] + text[i+1:min(len(text), i+6)]
                cjk_count = len(_CJK_PATTERN.findall(context))
                ascii_count = len(_ASCII_ALPHA.findall(context))
                if ascii_count > cjk_count and ascii_count > 0:
                    result[i] = ch.translate(_FULL_TO_HALF)
            elif ch in ',.!?;:':
                context = text[max(0, i-5):i] + text[i+1:min(len(text), i+6)]
                cjk_count = len(_CJK_PATTERN.findall(context))
                ascii_count = len(_ASCII_ALPHA.findall(context))
                if cjk_count > ascii_count and cjk_count > 0:
                    result[i] = ch.translate(_HALF_TO_FULL)
        return ''.join(result)

    # ── 规则5：中英文间距（Pangu） ───────────────────────────

    @staticmethod
    def _pangu_spacing(text: str) -> str:
        # 中文后接英文/数字，加空格
        text = re.sub(r'([\u4e00-\u9fff])([a-zA-Z0-9])', r'\1 \2', text)
        # 英文/数字后接中文，加空格
        text = re.sub(r'([a-zA-Z0-9])([\u4e00-\u9fff])', r'\1 \2', text)
        return text

    # ── 规则6：去除行首尾空白 ────────────────────────────────

    @staticmethod
    def _trim_lines(text: str) -> str:
        return '\n'.join(line.strip() for line in text.split('\n'))
```

- [ ] **Step 2.4: 运行测试，确认通过**

```bash
python -m pytest tests/test_rule_engine.py -v
```

Expected: 所有测试 PASS（允许规则4相关测试有少量调整，因语言检测有概率性）。

- [ ] **Step 2.5: Commit**

```bash
git add src/rule_engine.py tests/test_rule_engine.py
git commit -m "feat(rule-engine): 实现8条清洗规则，含代码块/列表保护和软换行合并"
```

---

## Task 3: TrayManager + main.py — 托盘图标与基础框架

**Files:**
- Create: `src/main.py`
- Create: `src/tray_manager.py`
- Create: `assets/icon_idle.png`（占位图，16x16）
- Create: `src/ui/__init__.py`

> 此 Task 无自动化测试，以手动运行验证。

- [ ] **Step 3.1: 生成占位图标（用 Python 生成最小 PNG）**

```bash
python -c "
from PyQt6.QtGui import QPixmap, QColor, QPainter
from PyQt6.QtWidgets import QApplication
import sys

app = QApplication(sys.argv)
colors = {'idle': '#9E9E9E', 'processing': '#FFC107', 'success': '#4CAF50', 'error': '#F44336'}
for name, color in colors.items():
    px = QPixmap(16, 16)
    px.fill(QColor(color))
    px.save(f'assets/{name}.png')
    print(f'assets/{name}.png created')
"
```

- [ ] **Step 3.2: 创建 src/ui/__init__.py（空文件）**

```bash
touch src/ui/__init__.py
```

- [ ] **Step 3.3: 实现 src/tray_manager.py**

```python
import os
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QTimer, pyqtSignal, QObject


def _asset_path(filename: str) -> str:
    base = os.path.join(os.path.dirname(__file__), '..', 'assets')
    return os.path.normpath(os.path.join(base, filename))


class TrayManager(QObject):
    open_settings_requested = pyqtSignal()
    pause_toggled = pyqtSignal(bool)        # True=暂停
    quit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._paused = False
        self._icon_idle = QIcon(_asset_path('idle.png'))
        self._icon_processing = QIcon(_asset_path('processing.png'))
        self._icon_success = QIcon(_asset_path('success.png'))
        self._icon_error = QIcon(_asset_path('error.png'))

        self._tray = QSystemTrayIcon(self._icon_idle)
        self._tray.setToolTip('NeatCopy')
        self._build_menu()
        self._tray.show()

        self._restore_timer = QTimer(self)
        self._restore_timer.setSingleShot(True)
        self._restore_timer.timeout.connect(self._restore_idle_icon)

    def _build_menu(self):
        menu = QMenu()
        self._act_settings = QAction('打开设置')
        self._act_settings.triggered.connect(self.open_settings_requested)
        self._act_pause = QAction('暂停监听')
        self._act_pause.setCheckable(True)
        self._act_pause.triggered.connect(self._on_pause_toggled)
        self._act_quit = QAction('退出')
        self._act_quit.triggered.connect(self.quit_requested)

        menu.addAction(self._act_settings)
        menu.addAction(self._act_pause)
        menu.addSeparator()
        menu.addAction(self._act_quit)
        self._tray.setContextMenu(menu)

    def _on_pause_toggled(self, checked: bool):
        self._paused = checked
        self._act_pause.setText('继续监听' if checked else '暂停监听')
        self.pause_toggled.emit(checked)

    def set_processing(self):
        self._tray.setIcon(self._icon_processing)
        self._tray.setToolTip('NeatCopy — 处理中...')

    def set_success(self, toast_enabled: bool = True, message: str = '已清洗，可直接粘贴'):
        self._tray.setIcon(self._icon_success)
        self._tray.setToolTip('NeatCopy — 成功')
        if toast_enabled:
            self._tray.showMessage('NeatCopy', message, QSystemTrayIcon.MessageIcon.Information, 2000)
        self._restore_timer.start(1500)

    def set_error(self, message: str, toast_enabled: bool = True):
        self._tray.setIcon(self._icon_error)
        self._tray.setToolTip(f'NeatCopy — 错误')
        if toast_enabled:
            self._tray.showMessage('NeatCopy', message, QSystemTrayIcon.MessageIcon.Critical, 3000)
        self._restore_timer.start(1500)

    def _restore_idle_icon(self):
        self._tray.setIcon(self._icon_idle)
        self._tray.setToolTip('NeatCopy')
```

- [ ] **Step 3.4: 实现 src/main.py**

```python
import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# 确保 src/ 在路径中
sys.path.insert(0, os.path.dirname(__file__))

from config_manager import ConfigManager
from tray_manager import TrayManager


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName('NeatCopy')

    config = ConfigManager()
    tray = TrayManager()

    # 退出处理
    tray.quit_requested.connect(app.quit)

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
```

- [ ] **Step 3.5: 手动测试：运行程序，验证托盘图标出现**

```bash
python src/main.py
```

验收：
- 系统托盘出现灰色图标
- 右键菜单显示「打开设置 / 暂停监听 / 退出」
- 点击「退出」程序正常退出

- [ ] **Step 3.6: Commit**

```bash
git add src/main.py src/tray_manager.py src/ui/__init__.py assets/
git commit -m "feat(tray): 实现系统托盘图标、右键菜单和三态图标变色"
```

---

## Task 4: HotkeyManager — 独立热键触发

**Files:**
- Create: `src/hotkey_manager.py`
- Modify: `src/main.py`（连接热键信号）

- [ ] **Step 4.1: 实现 src/hotkey_manager.py**

```python
import threading
import time
import keyboard
from PyQt6.QtCore import QObject, pyqtSignal


class HotkeyManager(QObject):
    hotkey_triggered = pyqtSignal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._paused = False
        self._last_ctrl_c_time = 0.0
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def set_paused(self, paused: bool):
        self._paused = paused

    def reload_config(self, config):
        """热键配置变更时调用，重新注册。"""
        keyboard.unhook_all()
        self._config = config
        # 重启监听（daemon thread 不可重启，改为重新 hook）
        self._register_hooks()

    def _listen(self):
        self._register_hooks()
        keyboard.wait()  # 阻塞，保持监听

    def _register_hooks(self):
        cfg_hotkey = self._config.get('general.custom_hotkey', {})
        if cfg_hotkey.get('enabled', True):
            keys = cfg_hotkey.get('keys', 'ctrl+shift+c')
            try:
                keyboard.add_hotkey(keys, self._on_custom_hotkey, suppress=True)
            except Exception:
                pass  # 热键冲突时静默跳过

        cfg_double = self._config.get('general.double_ctrl_c', {})
        if cfg_double.get('enabled', False):
            keyboard.on_press_key('c', self._on_c_pressed)

    def _on_custom_hotkey(self):
        if not self._paused:
            self.hotkey_triggered.emit()

    def _on_c_pressed(self, event):
        if not keyboard.is_pressed('ctrl'):
            return
        if self._paused:
            return
        cfg = self._config.get('general.double_ctrl_c', {})
        interval_ms = cfg.get('interval_ms', 300)
        now = time.time()
        if (now - self._last_ctrl_c_time) * 1000 <= interval_ms:
            self._last_ctrl_c_time = 0  # 重置，防止三击触发两次
            self.hotkey_triggered.emit()
        else:
            self._last_ctrl_c_time = now
```

- [ ] **Step 4.2: 更新 src/main.py，连接热键信号**

在 `main()` 中添加：

```python
from hotkey_manager import HotkeyManager

# 在 tray 初始化后添加：
hotkey = HotkeyManager(config)
tray.pause_toggled.connect(hotkey.set_paused)

# 暂时用 print 验证信号（后续 Task 5 替换为 ClipProcessor）
hotkey.hotkey_triggered.connect(lambda: print('热键触发！'))
```

- [ ] **Step 4.3: 手动测试：运行并按 Ctrl+Shift+C**

```bash
python src/main.py
```

验收：
- 按 Ctrl+Shift+C，终端输出「热键触发！」
- 按托盘「暂停监听」后，热键不再触发

- [ ] **Step 4.4: Commit**

```bash
git add src/hotkey_manager.py src/main.py
git commit -m "feat(hotkey): 实现独立热键 Ctrl+Shift+C 全局监听，支持暂停"
```

---

## Task 5: ClipProcessor — 规则模式完整链路

**Files:**
- Create: `src/clip_processor.py`
- Modify: `src/main.py`（接入 ClipProcessor）

- [ ] **Step 5.1: 实现 src/clip_processor.py（规则模式）**

```python
import win32clipboard
import win32con
from PyQt6.QtCore import QObject, pyqtSignal

from rule_engine import RuleEngine


def _read_clipboard() -> str | None:
    try:
        win32clipboard.OpenClipboard()
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            return text
        return None
    except Exception:
        return None
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass


def _write_clipboard(text: str) -> bool:
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
        return True
    except Exception:
        return False
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass


class ClipProcessor(QObject):
    process_done = pyqtSignal(bool, str)  # (success, message)
    processing_started = pyqtSignal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config

    def reload_config(self, config):
        self._config = config

    def process(self):
        text = _read_clipboard()
        if not text or not text.strip():
            return

        mode = self._config.get('rules.mode', 'rules')

        if mode == 'rules':
            self._process_rules(text)
        elif mode == 'llm':
            self._process_llm(text)

    def _process_rules(self, text: str):
        try:
            rule_config = self._config.get('rules') or {}
            cleaned = RuleEngine.clean(text, rule_config)
            if _write_clipboard(cleaned):
                self.process_done.emit(True, '已清洗，可直接粘贴')
            else:
                self.process_done.emit(False, '写入剪贴板失败')
        except Exception as e:
            self.process_done.emit(False, f'清洗出错：{e}')

    def _process_llm(self, text: str):
        # LLM 分支在 Task 7 实现，此处占位
        self.process_done.emit(False, '大模型模式尚未启用')
```

- [ ] **Step 5.2: 更新 src/main.py，完整链路接入**

```python
from clip_processor import ClipProcessor

# 替换原有 lambda print：
processor = ClipProcessor(config)

def on_process_done(success: bool, message: str):
    toast_enabled = config.get('general.toast_notification', True)
    if success:
        tray.set_success(toast_enabled=toast_enabled, message=message)
    else:
        tray.set_error(message=message, toast_enabled=toast_enabled)

hotkey.hotkey_triggered.connect(processor.process)
processor.process_done.connect(on_process_done)
processor.processing_started.connect(tray.set_processing)
```

- [ ] **Step 5.3: 手动测试：完整规则模式流程**

```bash
python src/main.py
```

验收：
1. 打开记事本，输入「这是第一行\n续接行」（含换行）
2. 全选复制（Ctrl+A → Ctrl+C）
3. 按 Ctrl+Shift+C
4. 托盘图标变绿，Toast 弹出「已清洗，可直接粘贴」
5. 粘贴到记事本，换行已合并

- [ ] **Step 5.4: Commit**

```bash
git add src/clip_processor.py src/main.py
git commit -m "feat(clip): 接入规则模式完整链路，热键→清洗→写回剪贴板→Toast"
```

---

## Task 6: SettingsWindow — 通用Tab + 规则Tab

**Files:**
- Create: `src/ui/settings_window.py`
- Modify: `src/main.py`（连接设置窗口）
- Modify: `src/tray_manager.py`（暴露 open_settings 接口）

- [ ] **Step 6.1: 实现 src/ui/settings_window.py（通用Tab + 规则Tab）**

```python
from PyQt6.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QCheckBox, QSlider, QPushButton, QGroupBox,
    QRadioButton, QButtonGroup, QLineEdit, QSizePolicy,
    QStatusBar
)
from PyQt6.QtCore import Qt, QTimer


RULE_LABELS = {
    'merge_soft_newline': ('合并软换行', 'PDF/CAJ 段落内断行合并为一行'),
    'keep_hard_newline': ('保留段落分隔', '连续空行视为真正段落分隔'),
    'merge_spaces': ('合并多余空格', '多个连续空格合并为单个'),
    'smart_punctuation': ('智能全/半角标点', '中文语境全角，英文语境半角'),
    'pangu_spacing': ('中英文间距', '中英文之间自动加空格（Pangu 风格）'),
    'trim_lines': ('去除行首尾空白', '每行首尾多余空白清除'),
    'protect_code_blocks': ('保护代码块', '识别代码块，跳过清洗'),
    'protect_lists': ('保护列表结构', '列表行保留换行不合并'),
}


class SettingsWindow(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._do_save)
        self._pending_changes: dict = {}

        self.setWindowTitle('NeatCopy 设置')
        self.setMinimumWidth(460)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)

        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_general_tab(), '通用')
        self._tabs.addTab(self._build_rules_tab(), '清洗规则')
        layout.addWidget(self._tabs)

        # 状态栏
        self._status_label = QLabel('')
        self._status_label.setStyleSheet('color: #4CAF50;')
        layout.addWidget(self._status_label)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        save_btn = QPushButton('保存')
        save_btn.clicked.connect(self._do_save)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    # ── 通用 Tab ──────────────────────────────────────────────

    def _build_general_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # Toast 通知
        self._chk_toast = QCheckBox('显示清洗完成通知（Toast）')
        self._chk_toast.setChecked(self._config.get('general.toast_notification', True))
        self._chk_toast.stateChanged.connect(
            lambda v: self._mark_change('general.toast_notification', bool(v)))
        layout.addWidget(self._chk_toast)

        # 开机自启
        self._chk_startup = QCheckBox('开机自动启动')
        self._chk_startup.setChecked(self._config.get('general.startup_with_windows', False))
        self._chk_startup.stateChanged.connect(
            lambda v: self._mark_change('general.startup_with_windows', bool(v)))
        layout.addWidget(self._chk_startup)

        # 独立热键
        hk_group = QGroupBox('独立热键')
        hk_layout = QHBoxLayout(hk_group)
        self._chk_hotkey = QCheckBox('启用')
        self._chk_hotkey.setChecked(self._config.get('general.custom_hotkey.enabled', True))
        self._chk_hotkey.stateChanged.connect(
            lambda v: self._mark_change('general.custom_hotkey.enabled', bool(v)))
        self._lbl_hotkey = QLabel(self._config.get('general.custom_hotkey.keys', 'ctrl+shift+c'))
        hk_layout.addWidget(self._chk_hotkey)
        hk_layout.addWidget(QLabel('当前：'))
        hk_layout.addWidget(self._lbl_hotkey)
        layout.addWidget(hk_group)

        # 双击 Ctrl+C
        dbl_group = QGroupBox('双击 Ctrl+C')
        dbl_layout = QVBoxLayout(dbl_group)
        self._chk_dbl = QCheckBox('启用（注意：可能与部分应用冲突）')
        self._chk_dbl.setChecked(self._config.get('general.double_ctrl_c.enabled', False))
        self._chk_dbl.stateChanged.connect(
            lambda v: self._mark_change('general.double_ctrl_c.enabled', bool(v)))
        interval = self._config.get('general.double_ctrl_c.interval_ms', 300)
        self._lbl_interval = QLabel(f'间隔阈值：{interval} ms')
        self._sld_interval = QSlider(Qt.Orientation.Horizontal)
        self._sld_interval.setRange(100, 500)
        self._sld_interval.setValue(interval)
        self._sld_interval.setTickInterval(50)
        self._sld_interval.valueChanged.connect(self._on_interval_changed)
        dbl_layout.addWidget(self._chk_dbl)
        dbl_layout.addWidget(self._lbl_interval)
        dbl_layout.addWidget(self._sld_interval)
        layout.addWidget(dbl_group)

        layout.addStretch()
        return w

    def _on_interval_changed(self, value: int):
        self._lbl_interval.setText(f'间隔阈值：{value} ms')
        self._mark_change('general.double_ctrl_c.interval_ms', value)

    # ── 规则 Tab ──────────────────────────────────────────────

    def _build_rules_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # 模式选择
        mode_group = QGroupBox('清洗模式')
        mode_layout = QHBoxLayout(mode_group)
        self._rb_rules = QRadioButton('规则模式')
        self._rb_llm = QRadioButton('大模型模式')
        current_mode = self._config.get('rules.mode', 'rules')
        self._rb_rules.setChecked(current_mode == 'rules')
        self._rb_llm.setChecked(current_mode == 'llm')
        self._rb_rules.toggled.connect(
            lambda checked: self._mark_change('rules.mode', 'rules') if checked else None)
        self._rb_llm.toggled.connect(
            lambda checked: self._mark_change('rules.mode', 'llm') if checked else None)
        mode_layout.addWidget(self._rb_rules)
        mode_layout.addWidget(self._rb_llm)
        layout.addWidget(mode_group)

        # 8条规则开关
        rules_group = QGroupBox('规则开关（规则模式下生效）')
        rules_layout = QVBoxLayout(rules_group)
        self._rule_checkboxes: dict[str, QCheckBox] = {}
        for key, (label, tooltip) in RULE_LABELS.items():
            chk = QCheckBox(label)
            chk.setToolTip(tooltip)
            chk.setChecked(self._config.get(f'rules.{key}', True))
            chk.stateChanged.connect(
                lambda v, k=key: self._mark_change(f'rules.{k}', bool(v)))
            self._rule_checkboxes[key] = chk
            rules_layout.addWidget(chk)
        layout.addWidget(rules_group)

        layout.addStretch()
        return w

    # ── 保存逻辑 ──────────────────────────────────────────────

    def _mark_change(self, key: str, value):
        self._pending_changes[key] = value

    def _do_save(self):
        for key, value in self._pending_changes.items():
            self._config.set(key, value)
        self._pending_changes.clear()
        self._status_label.setText('已保存 ✓')
        QTimer.singleShot(1500, lambda: self._status_label.setText(''))
```

- [ ] **Step 6.2: 更新 src/main.py，连接设置窗口**

```python
from ui.settings_window import SettingsWindow

settings_win = SettingsWindow(config)

def on_open_settings():
    if settings_win.isVisible():
        settings_win.hide()
    else:
        settings_win.show()
        settings_win.raise_()

tray.open_settings_requested.connect(on_open_settings)
```

- [ ] **Step 6.3: 手动测试：打开设置界面**

```bash
python src/main.py
```

验收：
- 右键「打开设置」，弹出设置窗口
- 修改规则开关后点「保存」，显示「已保存 ✓」
- 重启程序，设置保持不变

- [ ] **Step 6.4: Commit**

```bash
git add src/ui/settings_window.py src/main.py
git commit -m "feat(settings): 实现通用Tab+规则Tab设置界面，点击保存持久化配置"
```

---

## Task 7: LLMClient + ClipProcessor LLM 分支

**Files:**
- Create: `src/llm_client.py`
- Create: `tests/test_llm_client.py`
- Modify: `src/clip_processor.py`（补充 LLM 分支）

- [ ] **Step 7.1: 写 LLMClient 失败测试**

创建 `tests/test_llm_client.py`：

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from llm_client import LLMClient, classify_error

class TestClassifyError:
    def test_timeout_error(self):
        err = httpx.TimeoutException('timeout')
        assert '超时' in classify_error(err)

    def test_401_error(self):
        req = MagicMock()
        resp = httpx.Response(401, request=req)
        err = httpx.HTTPStatusError('', request=req, response=resp)
        assert 'Key' in classify_error(err) or '无效' in classify_error(err)

    def test_429_error(self):
        req = MagicMock()
        resp = httpx.Response(429, request=req)
        err = httpx.HTTPStatusError('', request=req, response=resp)
        assert '频率' in classify_error(err) or '余额' in classify_error(err)

    def test_404_error(self):
        req = MagicMock()
        resp = httpx.Response(404, request=req)
        err = httpx.HTTPStatusError('', request=req, response=resp)
        assert '模型' in classify_error(err) or '不存在' in classify_error(err)


@pytest.mark.asyncio
class TestLLMClientFormat:
    async def test_success_returns_content(self):
        mock_response = {
            'choices': [{'message': {'content': '整理后的文本'}}]
        }
        config = {
            'base_url': 'https://api.openai.com/v1',
            'api_key': 'test-key',
            'model_id': 'gpt-4o-mini',
            'temperature': 0.2,
        }
        with patch('httpx.AsyncClient') as MockClient:
            mock_resp = AsyncMock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = MagicMock()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value.post = AsyncMock(return_value=mock_resp)

            client = LLMClient()
            result = await client.format('原始文本', '系统prompt', config)
            assert result == '整理后的文本'

    async def test_failure_raises_exception(self):
        config = {
            'base_url': 'https://api.openai.com/v1',
            'api_key': 'bad-key',
            'model_id': 'gpt-4o-mini',
            'temperature': 0.2,
        }
        with patch('httpx.AsyncClient') as MockClient:
            req = MagicMock()
            resp = httpx.Response(401, request=req)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value.post = AsyncMock(
                side_effect=httpx.HTTPStatusError('', request=req, response=resp))

            client = LLMClient()
            with pytest.raises(Exception):
                await client.format('文本', 'prompt', config)
```

- [ ] **Step 7.2: 运行测试，确认失败**

```bash
python -m pytest tests/test_llm_client.py -v
```

- [ ] **Step 7.3: 实现 src/llm_client.py**

```python
import httpx
from typing import Any


ERROR_MESSAGES = {
    401: 'API Key 无效，请在设置中检查',
    402: '账户余额不足',
    429: '请求频率超限或余额不足',
    404: '模型 ID 不存在，请检查设置',
}


def classify_error(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return '请求超时（30s），请检查网络连接'
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return ERROR_MESSAGES.get(code, f'请求失败（HTTP {code}）')
    if isinstance(exc, httpx.ConnectError):
        return '网络连接失败，请检查代理或网络设置'
    return f'未知错误：{exc}'


class LLMClient:
    async def format(self, text: str, prompt: str, config: dict) -> str:
        """
        调用 OpenAI 兼容接口整理文本格式。
        失败时抛出异常，由调用方处理，不在此处静默。
        """
        headers = {'Authorization': f'Bearer {config["api_key"]}'}
        payload = {
            'model': config['model_id'],
            'temperature': config.get('temperature', 0.2),
            'messages': [
                {'role': 'system', 'content': prompt},
                {'role': 'user', 'content': text},
            ],
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f'{config["base_url"].rstrip("/")}/chat/completions',
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()['choices'][0]['message']['content']

    async def test_connection(self, config: dict) -> str:
        """发送固定测试文本验证连接，返回模型回复（供 UI 展示）。"""
        return await self.format(
            '测试文本：hello world',
            '请原样返回我发送给你的文字，不做任何修改。',
            config,
        )
```

- [ ] **Step 7.4: 补充 clip_processor.py 的 LLM 分支**

在 `ClipProcessor` 中添加：

```python
import asyncio
from PyQt6.QtCore import QThread
from llm_client import LLMClient, classify_error


class _LLMWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, text: str, prompt: str, config: dict, parent=None):
        super().__init__(parent)
        self._text = text
        self._prompt = prompt
        self._config = config

    def run(self):
        try:
            client = LLMClient()
            result = asyncio.run(client.format(self._text, self._prompt, self._config))
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(classify_error(e))


# 在 ClipProcessor._process_llm 中：
def _process_llm(self, text: str):
    llm_config = self._config.get('llm') or {}
    if not llm_config.get('enabled', False):
        self.process_done.emit(False, '请先在设置中启用大模型模式')
        return

    # 获取当前激活 prompt
    active_id = llm_config.get('active_prompt_id', 'default')
    prompts = llm_config.get('prompts', [])
    prompt_obj = next((p for p in prompts if p['id'] == active_id), prompts[0] if prompts else None)
    if not prompt_obj:
        self.process_done.emit(False, '未找到有效的 Prompt 模板')
        return

    self.processing_started.emit()
    worker = _LLMWorker(text, prompt_obj['content'], llm_config, parent=self)
    worker.finished.connect(self._on_llm_success)
    worker.error.connect(self._on_llm_error)
    worker.start()
    self._current_worker = worker  # 防止 GC

def _on_llm_success(self, result: str):
    if _write_clipboard(result):
        self.process_done.emit(True, '大模型处理完成，可直接粘贴')
    else:
        self.process_done.emit(False, '写入剪贴板失败')

def _on_llm_error(self, message: str):
    # 不写剪贴板，原文保持不变
    self.process_done.emit(False, message)
```

- [ ] **Step 7.5: 运行测试，确认通过**

```bash
python -m pytest tests/test_llm_client.py -v
```

- [ ] **Step 7.6: Commit**

```bash
git add src/llm_client.py src/clip_processor.py tests/test_llm_client.py
git commit -m "feat(llm): 实现 LLMClient OpenAI兼容接口，ClipProcessor接入LLM分支"
```

---

## Task 8: SettingsWindow — 大模型Tab + Prompt管理

**Files:**
- Modify: `src/ui/settings_window.py`（添加大模型Tab）

- [ ] **Step 8.1: 在 SettingsWindow 添加大模型Tab**

在 `__init__` 中的 `self._tabs.addTab` 后追加：

```python
self._tabs.addTab(self._build_llm_tab(), '大模型')
```

新增方法：

```python
import uuid
from PyQt6.QtWidgets import (
    QListWidget, QListWidgetItem, QTextEdit, QInputDialog,
    QMessageBox, QMenu
)

def _build_llm_tab(self) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)

    # 总开关
    self._chk_llm = QCheckBox('启用大模型模式（与规则模式互斥）')
    self._chk_llm.setChecked(self._config.get('llm.enabled', False))
    self._chk_llm.stateChanged.connect(
        lambda v: self._mark_change('llm.enabled', bool(v)))
    layout.addWidget(self._chk_llm)

    # API 配置
    api_group = QGroupBox('API 配置')
    api_layout = QVBoxLayout(api_group)

    for label, key, placeholder in [
        ('Base URL', 'llm.base_url', 'https://api.openai.com/v1'),
        ('Model ID', 'llm.model_id', 'gpt-4o-mini'),
    ]:
        row = QHBoxLayout()
        row.addWidget(QLabel(f'{label}：'))
        le = QLineEdit(self._config.get(key, placeholder))
        le.setPlaceholderText(placeholder)
        le.textChanged.connect(lambda t, k=key: self._mark_change(k, t))
        row.addWidget(le)
        api_layout.addLayout(row)

    # API Key 行
    key_row = QHBoxLayout()
    key_row.addWidget(QLabel('API Key：'))
    self._le_apikey = QLineEdit(self._config.get('llm.api_key', ''))
    self._le_apikey.setEchoMode(QLineEdit.EchoMode.Password)
    self._le_apikey.textChanged.connect(lambda t: self._mark_change('llm.api_key', t))
    btn_show = QPushButton('显示')
    btn_show.setCheckable(True)
    btn_show.toggled.connect(
        lambda on: self._le_apikey.setEchoMode(
            QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
    key_row.addWidget(self._le_apikey)
    key_row.addWidget(btn_show)
    api_layout.addLayout(key_row)

    # Temperature
    temp_row = QHBoxLayout()
    temp_val = self._config.get('llm.temperature', 0.2)
    self._lbl_temp = QLabel(f'Temperature：{temp_val:.1f}')
    self._sld_temp = QSlider(Qt.Orientation.Horizontal)
    self._sld_temp.setRange(0, 20)
    self._sld_temp.setValue(int(temp_val * 10))
    self._sld_temp.valueChanged.connect(self._on_temp_changed)
    temp_row.addWidget(self._lbl_temp)
    temp_row.addWidget(self._sld_temp)
    api_layout.addLayout(temp_row)

    layout.addWidget(api_group)

    # Test Connection
    btn_test = QPushButton('测试连接')
    btn_test.clicked.connect(self._on_test_connection)
    layout.addWidget(btn_test)

    # Prompt 模板管理
    prompt_group = QGroupBox('Prompt 模板')
    prompt_layout = QVBoxLayout(prompt_group)
    self._prompt_list = QListWidget()
    self._prompt_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    self._prompt_list.customContextMenuRequested.connect(self._show_prompt_menu)
    self._refresh_prompt_list()
    prompt_layout.addWidget(self._prompt_list)

    btn_row = QHBoxLayout()
    btn_add = QPushButton('新增')
    btn_add.clicked.connect(self._on_add_prompt)
    btn_row.addWidget(btn_add)
    btn_row.addStretch()
    prompt_layout.addLayout(btn_row)
    layout.addWidget(prompt_group)

    layout.addStretch()
    return w

def _on_temp_changed(self, value: int):
    temp = value / 10.0
    self._lbl_temp.setText(f'Temperature：{temp:.1f}')
    self._mark_change('llm.temperature', temp)

def _refresh_prompt_list(self):
    self._prompt_list.clear()
    prompts = self._config.get('llm.prompts') or []
    active_id = self._config.get('llm.active_prompt_id', 'default')
    for p in prompts:
        label = f"{'[默认] ' if p['id'] == active_id else ''}{p['name']}"
        if p.get('readonly'):
            label += ' 🔒'
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, p['id'])
        self._prompt_list.addItem(item)

def _show_prompt_menu(self, pos):
    item = self._prompt_list.itemAt(pos)
    if not item:
        return
    prompt_id = item.data(Qt.ItemDataRole.UserRole)
    prompts = self._config.get('llm.prompts') or []
    prompt = next((p for p in prompts if p['id'] == prompt_id), None)
    if not prompt:
        return

    menu = QMenu(self)
    act_default = menu.addAction('设为默认')
    act_edit = menu.addAction('编辑')
    act_del = menu.addAction('删除')
    act_del.setEnabled(not prompt.get('readonly', False))

    action = menu.exec(self._prompt_list.mapToGlobal(pos))
    if action == act_default:
        self._mark_change('llm.active_prompt_id', prompt_id)
        self._refresh_prompt_list()
    elif action == act_edit:
        self._edit_prompt(prompt)
    elif action == act_del:
        prompts = [p for p in prompts if p['id'] != prompt_id]
        self._mark_change('llm.prompts', prompts)
        self._refresh_prompt_list()

def _edit_prompt(self, prompt: dict):
    dialog = QDialog(self)
    dialog.setWindowTitle(f'编辑：{prompt["name"]}')
    dialog.resize(500, 300)
    vlayout = QVBoxLayout(dialog)
    editor = QTextEdit()
    editor.setPlainText(prompt['content'])
    vlayout.addWidget(editor)
    btn_ok = QPushButton('保存')
    btn_ok.clicked.connect(dialog.accept)
    vlayout.addWidget(btn_ok)
    if dialog.exec():
        prompts = list(self._config.get('llm.prompts') or [])
        for p in prompts:
            if p['id'] == prompt['id']:
                p['content'] = editor.toPlainText()
        self._mark_change('llm.prompts', prompts)

def _on_add_prompt(self):
    name, ok = QInputDialog.getText(self, '新增 Prompt', '模板名称：')
    if ok and name.strip():
        new_prompt = {
            'id': str(uuid.uuid4()),
            'name': name.strip(),
            'content': '',
            'readonly': False,
        }
        self._edit_prompt(new_prompt)
        prompts = list(self._config.get('llm.prompts') or [])
        prompts.append(new_prompt)
        self._mark_change('llm.prompts', prompts)
        self._refresh_prompt_list()

def _on_test_connection(self):
    import asyncio
    from llm_client import LLMClient, classify_error
    # 先保存当前待改变配置
    self._do_save()
    config = self._config.get('llm') or {}
    try:
        client = LLMClient()
        result = asyncio.run(client.test_connection(config))
        QMessageBox.information(self, '连接成功', f'模型回复：{result[:100]}')
    except Exception as e:
        QMessageBox.critical(self, '连接失败', classify_error(e))
```

- [ ] **Step 8.2: 手动测试：大模型Tab**

```bash
python src/main.py
```

验收：
- 大模型Tab显示所有配置项
- 填写真实 API Key + Model ID，点「测试连接」收到成功提示
- 新增/编辑/删除 Prompt 模板正常
- 「设为默认」改变 active_prompt_id，保存后重启保持

- [ ] **Step 8.3: Commit**

```bash
git add src/ui/settings_window.py
git commit -m "feat(settings): 添加大模型Tab，支持API配置、Prompt模板管理和连接测试"
```

---

## Task 9: 双击 Ctrl+C + 热键自定义

**Files:**
- Modify: `src/hotkey_manager.py`（双击逻辑已在Task4实现，此Task验证完整性）
- Modify: `src/ui/settings_window.py`（热键录制功能）

- [ ] **Step 9.1: 验证双击 Ctrl+C 功能**

在设置界面「通用Tab」→ 启用「双击Ctrl+C」，设置间隔 300ms：

```bash
python src/main.py
```

验收：
- 勾选后，快速双击 Ctrl+C（在文本编辑器中），触发清洗
- 单击 Ctrl+C 正常复制，不触发清洗
- 调整间隔滑块，行为随之变化

- [ ] **Step 9.2: 实现热键录制（按键捕获）**

在 `settings_window.py` 的 `_build_general_tab` 中替换热键显示为可录制按钮：

```python
# 替换 self._lbl_hotkey 为录制按钮
self._btn_record = QPushButton(self._config.get('general.custom_hotkey.keys', 'ctrl+shift+c'))
self._btn_record.setCheckable(True)
self._btn_record.toggled.connect(self._on_record_toggle)
self._recording_keys: list[str] = []
hk_layout.addWidget(self._chk_hotkey)
hk_layout.addWidget(QLabel('热键：'))
hk_layout.addWidget(self._btn_record)

def _on_record_toggle(self, recording: bool):
    if recording:
        self._btn_record.setText('按下组合键...')
        self._recording_keys = []
    else:
        if self._recording_keys:
            combo = '+'.join(self._recording_keys)
            self._btn_record.setText(combo)
            self._mark_change('general.custom_hotkey.keys', combo)

def keyPressEvent(self, event):
    if not self._btn_record.isChecked():
        return super().keyPressEvent(event)
    from PyQt6.QtCore import Qt
    mods = []
    if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
        mods.append('ctrl')
    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
        mods.append('shift')
    if event.modifiers() & Qt.KeyboardModifier.AltModifier:
        mods.append('alt')
    key_name = event.text().lower() or ''
    if key_name and key_name not in ('', ' '):
        self._recording_keys = mods + [key_name]
        self._btn_record.setChecked(False)
        self._btn_record.toggle()  # 触发 toggled(False)
```

- [ ] **Step 9.3: HotkeyManager 热键更新接口验证**

修改热键配置保存后，`ClipProcessor` 通过 `config` 引用自动获取最新值（因 `ConfigManager.set()` 直接写盘且内存同步）。HotkeyManager 需重新注册：

在 `main.py` 中，设置窗口保存时通知 HotkeyManager：

```python
# 在 SettingsWindow._do_save 后，发出信号或直接调用
# 最简方案：SettingsWindow 保存后 HotkeyManager.reload_config(config)
```

- [ ] **Step 9.4: Commit**

```bash
git add src/hotkey_manager.py src/ui/settings_window.py src/main.py
git commit -m "feat(hotkey): 完善双击Ctrl+C和热键自定义录制功能"
```

---

## Task 10: PyInstaller 打包验证

**Files:**
- Create: `NeatCopy.spec`

- [ ] **Step 10.1: 生成 spec 文件**

```bash
pyi-makespec --onefile --windowed --name NeatCopy \
  --icon assets/icon_idle.ico \
  src/main.py
```

- [ ] **Step 10.2: 编辑 NeatCopy.spec，添加 assets 和隐式导入**

在生成的 `.spec` 文件中找到 `Analysis(...)` 块，修改：

```python
a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[('assets', 'assets')],          # 打包资源目录
    hiddenimports=[
        'langdetect',
        'langdetect.utils',
        'win32clipboard',
        'win32con',
        'pywintypes',
    ],
    ...
)
```

- [ ] **Step 10.3: 执行打包**

```bash
pyinstaller NeatCopy.spec
```

Expected: `dist/NeatCopy.exe` 生成，约 40~70MB。

- [ ] **Step 10.4: 验证打包产物**

```bash
dist/NeatCopy.exe
```

验收（在无 Python 环境的路径下运行）：
- 程序启动，托盘图标出现，冷启动 < 3秒
- 热键触发正常，规则清洗正常
- 大模型模式可配置并调用
- 关闭程序后无残留进程

- [ ] **Step 10.5: 最终全量测试**

```bash
python -m pytest tests/ -v
```

Expected: 所有自动化测试 PASS。

- [ ] **Step 10.6: 最终 Commit**

```bash
git add NeatCopy.spec
git commit -m "chore(build): 添加 PyInstaller spec，完成单 exe 打包配置"
git tag v1.0.0
```

---

## 测试命令速查

```bash
# 全量测试
python -m pytest tests/ -v

# 单模块测试
python -m pytest tests/test_rule_engine.py -v
python -m pytest tests/test_config_manager.py -v
python -m pytest tests/test_llm_client.py -v

# 运行程序
python src/main.py

# 打包
pyinstaller NeatCopy.spec
```

## 已知风险提示

| 风险 | 处理方式 |
|------|---------|
| `keyboard` 库在某些环境需管理员权限 | 以管理员身份运行；或改用 `pynput` |
| PyInstaller 打包后杀软误报 | 添加白名单；可选代码签名 |
| 双击 Ctrl+C 与 IDE/应用冲突 | 默认关闭，仅在用户主动启用时生效 |
| `langdetect` 打包时 profile 缺失 | `--hidden-import langdetect.utils` |
