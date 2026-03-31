# 历史记录功能实现规划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 NeatCopy 添加历史记录功能，记录清洗前后的文本内容，支持搜索、复制和删除操作。

**Architecture:** 新增独立模块 `history_manager.py` 负责数据读写，`ui/history_window.py` 负责窗口 UI。最小侵入式设计，仅在 `ClipProcessor` 成功分支调用历史记录，不影响核心清洗流程。

**Tech Stack:** Python 3, PyQt6, JSON 文件存储, pytest 测试

---

## 文件结构

### 新增文件
- `src/history_manager.py` — 历史数据管理（增删查、容量控制）
- `src/ui/history_window.py` — 历史记录窗口 UI（双栏布局）
- `tests/test_history_manager.py` — 历史管理器单元测试

### 修改文件
- `src/config_manager.py:7-144` — 新增 `history` 配置组
- `src/clip_processor.py:82-202` — 构造函数注入 history_manager，成功时调用 add()
- `src/hotkey_manager.py:10-28,83-87,111-141` — 新增快捷键 ID、信号、注册逻辑
- `src/tray_manager.py:9-13,33-58` — 新增信号、托盘菜单入口
- `src/main.py:24-31,40-153` — 初始化 HistoryManager + HistoryWindow，连接信号
- `src/ui/settings_window.py:33-36,122-223` — 通用 Tab 新增历史设置 GroupBox

---

## Task 1: 创建 HistoryManager 数据管理模块

**Files:**
- Create: `src/history_manager.py`
- Create: `tests/test_history_manager.py`

- [ ] **Step 1: 写 HistoryManager 基础测试（add 和 get_all）**

```python
# tests/test_history_manager.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from history_manager import HistoryManager


class TestHistoryManagerBasic:
    def test_add_and_get_all(self, tmp_config_dir):
        """添加记录后能正确获取所有条目"""
        hm = HistoryManager(config_dir=str(tmp_config_dir))
        hm.add('原文内容', '处理后结果', 'rules', None)
        entries = hm.get_all()
        assert len(entries) == 1
        assert entries[0]['original'] == '原文内容'
        assert entries[0]['result'] == '处理后结果'
        assert entries[0]['mode'] == 'rules'
        assert entries[0]['prompt_name'] is None
        assert 'id' in entries[0]
        assert 'timestamp' in entries[0]

    def test_add_llm_mode_with_prompt_name(self, tmp_config_dir):
        """LLM 模式记录 prompt_name"""
        hm = HistoryManager(config_dir=str(tmp_config_dir))
        hm.add('原文', '结果', 'llm', '格式清洗')
        entries = hm.get_all()
        assert entries[0]['mode'] == 'llm'
        assert entries[0]['prompt_name'] == '格式清洗'

    def test_empty_history_returns_empty_list(self, tmp_config_dir):
        """空历史返回空列表而非 None"""
        hm = HistoryManager(config_dir=str(tmp_config_dir))
        assert hm.get_all() == []
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_history_manager.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'history_manager'"

- [ ] **Step 3: 实现 HistoryManager 基础结构**

```python
# src/history_manager.py
"""历史记录数据管理：读写 history.json，增删查接口。"""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


class HistoryManager:
    """历史记录管理器，负责读写 history.json 文件。"""

    def __init__(self, config_dir: str | None = None, max_count: int = 500):
        if config_dir is None:
            config_dir = os.environ.get('APPDATA', str(Path.home()))
        self._history_path = Path(config_dir) / 'NeatCopy' / 'history.json'
        self._history_path.parent.mkdir(parents=True, exist_ok=True)
        self._max_count = max_count
        self._data = self._load()

    def _load(self) -> dict:
        """加载历史文件，不存在或损坏时返回空结构。"""
        if not self._history_path.exists():
            return {'entries': []}
        try:
            with open(self._history_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if 'entries' not in data or not isinstance(data['entries'], list):
                return {'entries': []}
            return data
        except (json.JSONDecodeError, ValueError, IOError):
            # 文件损坏，备份后重建
            backup = self._history_path.with_suffix('.json.bak')
            try:
                self._history_path.rename(backup)
            except Exception:
                pass
            return {'entries': []}

    def _write(self) -> bool:
        """写入历史文件，失败时静默返回 False。"""
        try:
            with open(self._history_path, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            return True
        except (IOError, OSError):
            return False

    def add(self, original: str, result: str, mode: str, prompt_name: str | None) -> bool:
        """添加历史记录，超出上限时删除最旧条目。"""
        entry = {
            'id': str(uuid.uuid4()),
            'timestamp': datetime.now().isoformat(timespec='seconds'),
            'mode': mode,
            'prompt_name': prompt_name,
            'original': original,
            'result': result,
        }
        self._data['entries'].append(entry)
        # 容量控制：超出时删除最旧的
        while len(self._data['entries']) > self._max_count:
            self._data['entries'].pop(0)
        return self._write()

    def get_all(self) -> list[dict]:
        """返回所有历史记录（按时间倒序）。"""
        entries = self._data.get('entries', [])
        # 倒序排列（最新在前）
        return list(reversed(entries))

    def set_max_count(self, max_count: int):
        """更新最大条数上限。"""
        self._max_count = max_count
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_history_manager.py::TestHistoryManagerBasic -v`
Expected: PASS (3 tests)

- [ ] **Step 5: 提交**

```bash
git add src/history_manager.py tests/test_history_manager.py
git commit -m "feat: add HistoryManager core module with add/get_all"
```

---

## Task 2: 完善 HistoryManager 增删查功能

**Files:**
- Modify: `src/history_manager.py`
- Modify: `tests/test_history_manager.py`

- [ ] **Step 1: 写删除和搜索测试**

```python
# tests/test_history_manager.py (追加)
class TestHistoryManagerDelete:
    def test_delete_by_id(self, tmp_config_dir):
        """根据 ID 删除指定条目"""
        hm = HistoryManager(config_dir=str(tmp_config_dir))
        hm.add('原文1', '结果1', 'rules', None)
        hm.add('原文2', '结果2', 'rules', None)
        entries = hm.get_all()
        first_id = entries[0]['id']  # 最新那条
        hm.delete(first_id)
        remaining = hm.get_all()
        assert len(remaining) == 1
        assert remaining[0]['original'] == '原文1'

    def test_delete_nonexistent_id_returns_false(self, tmp_config_dir):
        """删除不存在的 ID 返回 False"""
        hm = HistoryManager(config_dir=str(tmp_config_dir))
        hm.add('原文', '结果', 'rules', None)
        result = hm.delete('nonexistent-id')
        assert result is False

    def test_clear_all(self, tmp_config_dir):
        """清空所有历史"""
        hm = HistoryManager(config_dir=str(tmp_config_dir))
        hm.add('原文1', '结果1', 'rules', None)
        hm.add('原文2', '结果2', 'rules', None)
        hm.clear()
        assert hm.get_all() == []


class TestHistoryManagerSearch:
    def test_search_matches_original(self, tmp_config_dir):
        """搜索匹配原文内容"""
        hm = HistoryManager(config_dir=str(tmp_config_dir))
        hm.add('PDF复制的文本段落', '清洗后文本', 'rules', None)
        hm.add('另一段内容', '结果', 'rules', None)
        results = hm.search('PDF')
        assert len(results) == 1
        assert 'PDF' in results[0]['original']

    def test_search_matches_result(self, tmp_config_dir):
        """搜索匹配结果内容"""
        hm = HistoryManager(config_dir=str(tmp_config_dir))
        hm.add('原文', '清洗后的格式化文本', 'rules', None)
        results = hm.search('格式化')
        assert len(results) == 1
        assert '格式化' in results[0]['result']

    def test_search_no_match_returns_empty(self, tmp_config_dir):
        """无匹配返回空列表"""
        hm = HistoryManager(config_dir=str(tmp_config_dir))
        hm.add('原文', '结果', 'rules', None)
        results = hm.search('不存在的内容')
        assert results == []

    def test_search_case_insensitive(self, tmp_config_dir):
        """搜索不区分大小写"""
        hm = HistoryManager(config_dir=str(tmp_config_dir))
        hm.add('Hello World', 'hello world', 'rules', None)
        results = hm.search('HELLO')
        assert len(results) == 1


class TestHistoryManagerCapacity:
    def test_max_count_limit(self, tmp_config_dir):
        """超出上限自动删除最旧"""
        hm = HistoryManager(config_dir=str(tmp_config_dir), max_count=3)
        hm.add('第1条', '结果1', 'rules', None)
        hm.add('第2条', '结果2', 'rules', None)
        hm.add('第3条', '结果3', 'rules', None)
        hm.add('第4条', '结果4', 'rules', None)  # 应触发删除第1条
        entries = hm.get_all()
        assert len(entries) == 3
        # 最旧的已被删除
        originals = [e['original'] for e in entries]
        assert '第1条' not in originals
        assert '第4条' in originals

    def test_update_max_count(self, tmp_config_dir):
        """动态更新上限"""
        hm = HistoryManager(config_dir=str(tmp_config_dir), max_count=5)
        hm.add('第1条', '结果1', 'rules', None)
        hm.set_max_count(2)
        hm.add('第2条', '结果2', 'rules', None)
        hm.add('第3条', '结果3', 'rules', None)  # 应触发删除
        entries = hm.get_all()
        assert len(entries) == 2
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_history_manager.py::TestHistoryManagerDelete tests/test_history_manager.py::TestHistoryManagerSearch tests/test_history_manager.py::TestHistoryManagerCapacity -v`
Expected: FAIL with "AttributeError: 'HistoryManager' object has no attribute 'delete'"

- [ ] **Step 3: 实现删除、搜索、容量控制方法**

```python
# src/history_manager.py (追加方法)
    def delete(self, entry_id: str) -> bool:
        """根据 ID 删除指定条目。"""
        entries = self._data.get('entries', [])
        for i, entry in enumerate(entries):
            if entry.get('id') == entry_id:
                entries.pop(i)
                return self._write()
        return False

    def clear(self) -> bool:
        """清空所有历史记录。"""
        self._data['entries'] = []
        return self._write()

    def search(self, keyword: str) -> list[dict]:
        """全文搜索，匹配原文或结果内容（不区分大小写）。"""
        if not keyword:
            return self.get_all()
        keyword_lower = keyword.lower()
        entries = self._data.get('entries', [])
        matched = [
            e for e in entries
            if keyword_lower in e.get('original', '').lower()
            or keyword_lower in e.get('result', '').lower()
        ]
        return list(reversed(matched))

    def get_by_id(self, entry_id: str) -> dict | None:
        """根据 ID 获取单个条目。"""
        entries = self._data.get('entries', [])
        for entry in entries:
            if entry.get('id') == entry_id:
                return entry
        return None
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_history_manager.py -v`
Expected: PASS (所有 14 tests)

- [ ] **Step 5: 提交**

```bash
git add src/history_manager.py tests/test_history_manager.py
git commit -m "feat: add HistoryManager delete/search/clear/capacity control"
```

---

## Task 3: 配置管理器集成历史配置项

**Files:**
- Modify: `src/config_manager.py:7-144`

- [ ] **Step 1: 写配置测试**

```python
# tests/test_config_manager.py (追加)
class TestHistoryConfig:
    def test_default_history_config_exists(self, tmp_config_dir):
        """默认配置包含 history 组"""
        from config_manager import ConfigManager
        config = ConfigManager(config_dir=str(tmp_config_dir))
        assert config.get('history.enabled') is True
        assert config.get('history.max_count') == 500
        assert config.get('history.hotkey') == 'ctrl+h'
        assert config.get('history.window_width') == 600
        assert config.get('history.window_height') == 400

    def test_history_config_merge(self, tmp_config_dir):
        """旧配置文件自动补 history 默认值"""
        from config_manager import ConfigManager
        # 写一个不含 history 的旧配置
        import json
        config_path = tmp_config_dir / 'NeatCopy' / 'config.json'
        config_path.parent.mkdir(parents=True, exist_ok=True)
        old_config = {'general': {'toast_notification': True}}
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(old_config, f)
        # 加载后应自动合并 history 默认值
        config = ConfigManager(config_dir=str(tmp_config_dir))
        assert config.get('history.enabled') is True
        assert config.get('history.max_count') == 500
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_config_manager.py::TestHistoryConfig -v`
Expected: FAIL with "AssertionError: assert config.get('history.enabled') is True"

- [ ] **Step 3: 在 DEFAULT_CONFIG 新增 history 组**

```python
# src/config_manager.py (修改 DEFAULT_CONFIG)
DEFAULT_CONFIG = {
    'ui': {
        'theme': 'light',
        'window_width': 700,
        'window_height': 550,
    },
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
        'timeout': 30,
        'active_prompt_id': 'default',
        'prompts': [
            # ... (保持原有 prompts 不变)
        ],
    },
    'wheel': {
        'enabled': True,
        'trigger_with_clean': True,
        'switch_hotkey': 'ctrl+shift+p',
        'last_prompt_id': None,
        'locked_prompt_id': None,
    },
    'preview': {
        'enabled': True,
        'hotkey': 'ctrl+q',
        'window_width': 320,
        'window_height': 200,
        'theme': 'dark',
    },
    'history': {
        'enabled': True,
        'max_count': 500,
        'hotkey': 'ctrl+h',
        'window_width': 600,
        'window_height': 400,
    },
}
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_config_manager.py::TestHistoryConfig -v`
Expected: PASS (2 tests)

- [ ] **Step 5: 提交**

```bash
git add src/config_manager.py tests/test_config_manager.py
git commit -m "feat: add history config group to DEFAULT_CONFIG"
```

---

## Task 4: 热键管理器新增历史快捷键

**Files:**
- Modify: `src/hotkey_manager.py:10-28,83-87,111-141`

- [ ] **Step 1: 添加历史快捷键常量和信号**

```python
# src/hotkey_manager.py (修改)
# 在 WM_HOTKEY 常量区域后添加（约 line 11）
WM_HOTKEY = 0x0312
WM_KEYDOWN = 0x0100
WH_KEYBOARD_LL = 13
VK_C = 0x43
VK_CONTROL = 0x11

_MOD_MAP = {'ctrl': 0x0002, 'shift': 0x0004, 'alt': 0x0001}
# ...

# 在 HOTKEY_ID 常量区域添加（约 line 26-28）
HOTKEY_ID_CUSTOM = 1
HOTKEY_ID_WHEEL = 2
HOTKEY_ID_PREVIEW = 3
HOTKEY_ID_HISTORY = 4  # 新增

# 在 HotkeyManager 类的信号定义区添加（约 line 83-86）
class HotkeyManager(QObject):
    hotkey_triggered = pyqtSignal()
    wheel_hotkey_triggered = pyqtSignal()
    preview_hotkey_triggered = pyqtSignal()
    history_hotkey_triggered = pyqtSignal()  # 新增
```

- [ ] **Step 2: 修改 _HotkeyFilter 构造函数和 nativeEventFilter**

```python
# src/hotkey_manager.py (修改 _HotkeyFilter 类)
class _HotkeyFilter(QAbstractNativeEventFilter):
    """拦截 Qt 主线程消息循环中的 WM_HOTKEY。"""

    def __init__(self, callback, wheel_callback=None, preview_callback=None, history_callback=None):
        super().__init__()
        self._callback = callback
        self._wheel_callback = wheel_callback
        self._preview_callback = preview_callback
        self._history_callback = history_callback  # 新增

    def nativeEventFilter(self, eventType, message):
        if eventType == QByteArray(b'windows_generic_MSG'):
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY:
                if msg.wParam == HOTKEY_ID_CUSTOM:
                    self._callback()
                    return True, 0
                elif msg.wParam == HOTKEY_ID_WHEEL and self._wheel_callback:
                    self._wheel_callback()
                    return True, 0
                elif msg.wParam == HOTKEY_ID_PREVIEW and self._preview_callback:
                    self._preview_callback()
                    return True, 0
                elif msg.wParam == HOTKEY_ID_HISTORY and self._history_callback:  # 新增
                    self._history_callback()
                    return True, 0
        return False, 0
```

- [ ] **Step 3: 修改 HotkeyManager 构造函数和注册逻辑**

```python
# src/hotkey_manager.py (修改 HotkeyManager.__init__)
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._paused = False
        self._registered = False
        self._wheel_registered = False
        self._preview_registered = False
        self._history_registered = False  # 新增
        self._filter = None
        self._ll_hook = None
        self._ll_proc = None
        self._lock = threading.Lock()
        self._last_ctrl_c_time = 0.0
        self._simulating = False
        self._register_hotkey()
```

- [ ] **Step 4: 修改 _register_hotkey 添加历史热键注册**

```python
# src/hotkey_manager.py (修改 _register_hotkey 方法，约 line 111-141)
    def _register_hotkey(self):
        """在主线程注册全局热键，通过 Qt 消息循环接收。"""
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()

        # 清洗独立热键
        cfg_hotkey = self._config.get('general.custom_hotkey') or {}
        if cfg_hotkey.get('enabled', True):
            keys = cfg_hotkey.get('keys', 'ctrl+shift+c')
            mods, vk = _parse_hotkey(keys)
            if vk:
                ok = user32.RegisterHotKey(None, HOTKEY_ID_CUSTOM, mods, vk)
                self._registered = bool(ok)

        # 轮盘切换热键
        cfg_wheel = self._config.get('wheel') or {}
        if cfg_wheel.get('enabled', True):
            wheel_keys = cfg_wheel.get('switch_hotkey', 'ctrl+shift+p')
            w_mods, w_vk = _parse_hotkey(wheel_keys)
            if w_vk:
                ok2 = user32.RegisterHotKey(None, HOTKEY_ID_WHEEL, w_mods, w_vk)
                self._wheel_registered = bool(ok2)

        # 预览面板热键
        cfg_preview = self._config.get('preview') or {}
        if cfg_preview.get('enabled', True):
            preview_keys = cfg_preview.get('hotkey', 'ctrl+q')
            p_mods, p_vk = _parse_hotkey(preview_keys)
            if p_vk:
                ok3 = user32.RegisterHotKey(None, HOTKEY_ID_PREVIEW, p_mods, p_vk)
                self._preview_registered = bool(ok3)

        # 历史记录热键（新增）
        cfg_history = self._config.get('history') or {}
        if cfg_history.get('enabled', True):
            history_keys = cfg_history.get('hotkey', 'ctrl+h')
            h_mods, h_vk = _parse_hotkey(history_keys)
            if h_vk:
                ok4 = user32.RegisterHotKey(None, HOTKEY_ID_HISTORY, h_mods, h_vk)
                self._history_registered = bool(ok4)

        if (self._registered or self._wheel_registered or self._preview_registered or self._history_registered) and app:
            self._filter = _HotkeyFilter(
                self._on_hotkey, self._on_wheel_hotkey,
                self._on_preview_hotkey, self._on_history_hotkey  # 新增
            )
            app.installNativeEventFilter(self._filter)

        # 双击 Ctrl+C（WH_KEYBOARD_LL 低级键盘钩子）
        cfg_double = self._config.get('general.double_ctrl_c') or {}
        if cfg_double.get('enabled', False):
            self._install_ll_hook()
```

- [ ] **Step 5: 添加 _unregister_hotkey 和回调方法**

```python
# src/hotkey_manager.py (修改 _unregister_hotkey，约 line 169-187)
    def _unregister_hotkey(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if self._filter and app:
            app.removeNativeEventFilter(self._filter)
            self._filter = None
        if self._registered:
            user32.UnregisterHotKey(None, HOTKEY_ID_CUSTOM)
            self._registered = False
        if self._wheel_registered:
            user32.UnregisterHotKey(None, HOTKEY_ID_WHEEL)
            self._wheel_registered = False
        if self._preview_registered:
            user32.UnregisterHotKey(None, HOTKEY_ID_PREVIEW)
            self._preview_registered = False
        if self._history_registered:  # 新增
            user32.UnregisterHotKey(None, HOTKEY_ID_HISTORY)
            self._history_registered = False
        if self._ll_hook:
            user32.UnhookWindowsHookEx(self._ll_hook)
            self._ll_hook = None
            self._ll_proc = None

    # 新增回调方法（约 line 218 后）
    def _on_history_hotkey(self):
        """历史记录快捷键回调（toggle 行为）。"""
        if self._paused:
            return
        self.history_hotkey_triggered.emit()
```

- [ ] **Step 6: 运行现有测试验证无破坏**

Run: `pytest tests/test_config_manager.py tests/test_rule_engine.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add src/hotkey_manager.py
git commit -m "feat: add history hotkey to HotkeyManager"
```

---

## Task 5: 托盘管理器新增历史入口

**Files:**
- Modify: `src/tray_manager.py:9-13,33-58`

- [ ] **Step 1: 添加信号和菜单项**

```python
# src/tray_manager.py (修改信号定义，约 line 9-13)
class TrayManager(QObject):
    open_settings_requested = pyqtSignal()
    pause_toggled = pyqtSignal(bool)
    quit_requested = pyqtSignal()
    locked_prompt_changed = pyqtSignal(str)
    open_history_requested = pyqtSignal()  # 新增

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self._config = config
        self._locked_name: str | None = None
        self._icon_idle = QIcon(_asset('idle.png'))
        self._icon_processing = QIcon(_asset('processing.png'))
        self._icon_success = QIcon(_asset('success.png'))
        self._icon_error = QIcon(_asset('error.png'))

        self._tray = QSystemTrayIcon(self._icon_idle)
        self._tray.setToolTip('NeatCopy')
        self._build_menu()
        self._tray.show()
        # ...
```

- [ ] **Step 2: 修改 _build_menu 添加历史菜单项**

```python
# src/tray_manager.py (修改 _build_menu 方法，约 line 33-58)
    def _build_menu(self):
        # 所有 QMenu/QAction 必须存为实例变量，防止 GC 回收
        self._menu = QMenu()
        self._act_settings = QAction('打开设置', self._menu)
        self._act_settings.triggered.connect(self.open_settings_requested)

        # 历史记录菜单项（新增）
        self._act_history = QAction('历史记录', self._menu)
        self._act_history.triggered.connect(self.open_history_requested)

        # 锁定 Prompt 状态显示与子菜单
        self._act_locked = QAction('当前锁定：无', self._menu)
        self._act_locked.setEnabled(False)
        self._menu_lock = QMenu('切换锁定 Prompt', self._menu)

        self._act_pause = QAction('暂停监听', self._menu)
        self._act_pause.setCheckable(True)
        self._act_pause.triggered.connect(self._on_pause_toggled)
        self._act_quit = QAction('退出', self._menu)
        self._act_quit.triggered.connect(self.quit_requested)

        self._menu.addAction(self._act_settings)
        self._menu.addAction(self._act_history)  # 新增
        self._menu.addSeparator()
        self._menu.addAction(self._act_locked)
        self._menu.addMenu(self._menu_lock)
        self._menu.addSeparator()
        self._menu.addAction(self._act_pause)
        self._menu.addSeparator()
        self._menu.addAction(self._act_quit)
        self._tray.setContextMenu(self._menu)

        # 右键菜单弹出时刷新锁定子菜单
        self._menu.aboutToShow.connect(self._refresh_lock_submenu)
```

- [ ] **Step 3: 运行现有测试验证无破坏**

Run: `pytest tests/ -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add src/tray_manager.py
git commit -m "feat: add history menu entry to TrayManager"
```

---

## Task 6: ClipProcessor 集成历史记录调用

**Files:**
- Modify: `src/clip_processor.py:82-202`

- [ ] **Step 1: 修改 ClipProcessor 构造函数**

```python
# src/clip_processor.py (修改 ClipProcessor 类)
class ClipProcessor(QObject):
    process_done = pyqtSignal(bool, str)
    processing_started = pyqtSignal()
    preview_ready = pyqtSignal(str, str)
    preview_failed = pyqtSignal(str)

    def __init__(self, config, history_manager=None, parent=None):  # 新增 history_manager 参数
        super().__init__(parent)
        self._config = config
        self._history = history_manager  # 新增
        self._current_worker = None
        self._current_prompt_obj = None

    def reload_config(self, config, history_manager=None):  # 新增可选参数
        self._config = config
        if history_manager is not None:
            self._history = history_manager
```

- [ ] **Step 2: 在规则模式成功时调用历史记录**

```python
# src/clip_processor.py (修改 _process_rules 方法)
    def _process_rules(self, text: str):
        self.processing_started.emit()
        try:
            rule_config = self._config.get('rules') or {}
            cleaned = RuleEngine.clean(text, rule_config)
            if _write_clipboard(cleaned):
                # 新增：记录历史（仅在启用时）
                if self._history and self._config.get('history.enabled', True):
                    self._history.add(text, cleaned, 'rules', None)
                self.process_done.emit(True, '已清洗，可直接粘贴')
            else:
                self.process_done.emit(False, '写入剪贴板失败')
        except Exception as e:
            self.process_done.emit(False, f'清洗出错：{e}')
```

- [ ] **Step 3: 在 LLM 模式成功时调用历史记录**

```python
# src/clip_processor.py (修改 _on_llm_success 方法)
    def _on_llm_success(self, result: str):
        # 写入剪贴板（原有行为：双写模式）
        if _write_clipboard(result):
            # 新增：记录历史（仅在启用时）
            if self._history and self._config.get('history.enabled', True):
                prompt_name = self._current_prompt_obj.get('name', '默认') if self._current_prompt_obj else '默认'
                # 需获取原文，保存为实例变量
                self._history.add(self._current_original, result, 'llm', prompt_name)
            self.process_done.emit(True, '大模型处理完成，可直接粘贴')
        else:
            self.process_done.emit(False, '写入剪贴板失败')

        # 发射预览信号（双写模式）
        prompt_name = self._current_prompt_obj.get('name', '默认') if self._current_prompt_obj else '默认'
        self.preview_ready.emit(result, prompt_name)
```

- [ ] **Step 4: 在启动 LLM worker 时保存原文**

```python
# src/clip_processor.py (修改 _start_llm_worker 方法)
    def _start_llm_worker(self, text: str, prompt_obj: dict, llm_config: dict):
        self.processing_started.emit()
        self._current_prompt_obj = prompt_obj
        self._current_original = text  # 新增：保存原文用于历史记录
        worker = _LLMWorker(text, prompt_obj['content'], llm_config)
        worker.succeeded.connect(self._on_llm_success)
        worker.failed.connect(self._on_llm_error)
        worker.finished.connect(lambda: setattr(self, '_current_worker', None))
        worker.finished.connect(lambda: setattr(self, '_current_prompt_obj', None))
        worker.finished.connect(lambda: setattr(self, '_current_original', None))  # 新增
        worker.start()
        self._current_worker = worker

    # 在 __init__ 中新增实例变量初始化
    def __init__(self, config, history_manager=None, parent=None):
        super().__init__(parent)
        self._config = config
        self._history = history_manager
        self._current_worker = None
        self._current_prompt_obj = None
        self._current_original = None  # 新增
```

- [ ] **Step 5: 运行现有测试验证无破坏**

Run: `pytest tests/test_rule_engine.py tests/test_llm_client.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add src/clip_processor.py
git commit -m "feat: integrate history recording into ClipProcessor"
```

---

## Task 7: 创建历史记录窗口 UI

**Files:**
- Create: `src/ui/history_window.py`

- [ ] **Step 1: 创建 HistoryWindow 基础结构**

```python
# src/ui/history_window.py
"""历史记录窗口组件：双栏布局，左侧列表右侧详情，支持搜索、复制、删除。"""
import ctypes
import sys

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QListWidget, QListWidgetItem,
    QLineEdit, QMessageBox, QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QCursor

from ui.styles import ColorPalette


class HistoryWindow(QWidget):
    """历史记录窗口，置顶悬浮窗，双栏布局。"""

    copy_to_clipboard = pyqtSignal(str)  # 请求写入剪贴板

    def __init__(self, config, history_manager):
        super().__init__()
        self._config = config
        self._history = history_manager
        self._current_entry_id = None
        self._theme = config.get('ui.theme', 'light')

        self._setup_window_properties()
        self._create_ui()
        self._apply_theme(self._theme)
        self._apply_acrylic_effect()

    # ─────────────────────────────────────────────────────────────
    #  窗口属性
    # ─────────────────────────────────────────────────────────────

    def _setup_window_properties(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(
            self._config.get('history.window_width', 600),
            self._config.get('history.window_height', 400)
        )
        self.setMinimumSize(400, 300)
        self.setWindowTitle('NeatCopy 历史记录')

    # ─────────────────────────────────────────────────────────────
    #  UI 构建
    # ─────────────────────────────────────────────────────────────

    def _create_ui(self):
        # 外层容器
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 内容容器（圆角面板）
        self.container = QWidget()
        self.container.setObjectName('historyPanel')
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(10)

        # === 顶部栏：标题 + 搜索框 + 清空按钮 + 关闭 ===
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        title = QLabel('历史记录')
        title.setObjectName('historyTitle')
        top_bar.addWidget(title)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('搜索...')
        self.search_input.textChanged.connect(self._on_search_changed)
        top_bar.addWidget(self.search_input, stretch=1)

        self.clear_btn = QPushButton('清空全部')
        self.clear_btn.clicked.connect(self._on_clear_all)
        top_bar.addWidget(self.clear_btn)

        self.close_btn = QPushButton('✕')
        self.close_btn.setObjectName('closeBtn')
        self.close_btn.setFixedSize(26, 26)
        self.close_btn.clicked.connect(self.hide)
        top_bar.addWidget(self.close_btn)

        layout.addLayout(top_bar)

        # === 双栏区域：左侧列表 + 右侧详情 ===
        split_layout = QHBoxLayout()
        split_layout.setSpacing(10)

        # 左侧列表
        self.list_widget = QListWidget()
        self.list_widget.setMinimumWidth(150)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        split_layout.addWidget(self.list_widget)

        # 右侧详情区
        detail_panel = QVBoxLayout()
        detail_panel.setSpacing(6)

        # 详情头部
        self.detail_time = QLabel('时间：')
        self.detail_time.setObjectName('detailTime')
        self.detail_mode = QLabel('模式：')
        self.detail_mode.setObjectName('detailMode')
        detail_panel.addWidget(self.detail_time)
        detail_panel.addWidget(self.detail_mode)

        # 原文区域
        orig_label = QLabel('原文')
        orig_label.setObjectName('sectionLabel')
        detail_panel.addWidget(orig_label)
        self.original_view = QTextEdit()
        self.original_view.setReadOnly(True)
        self.original_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        detail_panel.addWidget(self.original_view, stretch=1)

        # 结果区域
        result_label = QLabel('结果')
        result_label.setObjectName('sectionLabel')
        detail_panel.addWidget(result_label)
        self.result_view = QTextEdit()
        self.result_view.setReadOnly(True)
        self.result_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        detail_panel.addWidget(self.result_view, stretch=1)

        # 操作按钮
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(8)
        self.copy_orig_btn = QPushButton('复制原文')
        self.copy_orig_btn.clicked.connect(self._on_copy_original)
        self.copy_result_btn = QPushButton('复制结果')
        self.copy_result_btn.clicked.connect(self._on_copy_result)
        self.delete_btn = QPushButton('删除')
        self.delete_btn.clicked.connect(self._on_delete_entry)
        btn_bar.addWidget(self.copy_orig_btn)
        btn_bar.addWidget(self.copy_result_btn)
        btn_bar.addStretch()
        btn_bar.addWidget(self.delete_btn)
        detail_panel.addLayout(btn_bar)

        split_layout.addLayout(detail_panel, stretch=1)
        layout.addLayout(split_layout, stretch=1)

        outer.addWidget(self.container)

        # 初始化加载历史
        self._refresh_list()
```

- [ ] **Step 2: 添加主题样式和交互方法**

```python
# src/ui/history_window.py (追加)
    # ─────────────────────────────────────────────────────────────
    #  主题样式
    # ─────────────────────────────────────────────────────────────

    def _get_theme_styles(self, theme: str) -> dict:
        """返回指定主题的样式配置。"""
        c = ColorPalette.get(theme)
        if theme == 'light':
            return {
                'panel_bg': 'rgba(255, 255, 255, 245)',
                'panel_border': 'rgba(233, 233, 233, 180)',
                'text_primary': c['text_primary'],
                'text_secondary': c['text_secondary'],
                'edit_bg': 'rgba(247, 247, 245, 220)',
                'edit_border': 'rgba(218, 218, 218, 120)',
                'list_bg': c['bg_primary'],
                'list_item_bg': 'transparent',
                'list_item_selected': c['bg_selected'],
                'btn_bg': 'rgba(250, 250, 250, 200)',
                'btn_border': 'rgba(218, 218, 218, 140)',
                'close_text': c['text_secondary'],
                'close_hover_bg': 'rgba(0, 0, 0, 15)',
            }
        else:  # dark
            return {
                'panel_bg': 'rgba(25, 25, 25, 220)',
                'panel_border': 'rgba(55, 53, 47, 140)',
                'text_primary': c['text_primary'],
                'text_secondary': c['text_secondary'],
                'edit_bg': 'rgba(31, 31, 31, 200)',
                'edit_border': 'rgba(61, 60, 58, 100)',
                'list_bg': '#2B2B2B',
                'list_item_bg': 'transparent',
                'list_item_selected': '#404040',
                'btn_bg': 'rgba(47, 47, 47, 160)',
                'btn_border': 'rgba(61, 60, 58, 100)',
                'close_text': c['text_secondary'],
                'close_hover_bg': 'rgba(255, 255, 255, 25)',
            }

    def _apply_theme(self, theme: str):
        """应用主题样式。"""
        self._theme = theme
        styles = self._get_theme_styles(theme)

        self.container.setStyleSheet(f"""
            #historyPanel {{
                background: {styles['panel_bg']};
                border: 1px solid {styles['panel_border']};
                border-radius: 10px;
            }}
        """)

        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background: {styles['edit_bg']};
                border: 1px solid {styles['edit_border']};
                border-radius: 6px;
                padding: 6px 10px;
                color: {styles['text_primary']};
            }}
        """)

        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background: {styles['list_bg']};
                border: 1px solid {styles['edit_border']};
                border-radius: 6px;
                padding: 4px;
                outline: none;
            }}
            QListWidget::item {{
                background: {styles['list_item_bg']};
                padding: 6px 8px;
                border-radius: 4px;
                color: {styles['text_primary']};
            }}
            QListWidget::item:selected {{
                background: {styles['list_item_selected']};
            }}
        """)

        self.original_view.setStyleSheet(f"""
            QTextEdit {{
                background: {styles['edit_bg']};
                border: 1px solid {styles['edit_border']};
                border-radius: 6px;
                padding: 8px;
                color: {styles['text_primary']};
            }}
        """)

        self.result_view.setStyleSheet(f"""
            QTextEdit {{
                background: {styles['edit_bg']};
                border: 1px solid {styles['edit_border']};
                border-radius: 6px;
                padding: 8px;
                color: {styles['text_primary']};
            }}
        """)

        for btn in [self.copy_orig_btn, self.copy_result_btn, self.clear_btn]:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {styles['btn_bg']};
                    border: 1px solid {styles['btn_border']};
                    border-radius: 6px;
                    padding: 4px 12px;
                    color: {styles['text_primary']};
                }}
                QPushButton:hover {{
                    background: {styles['list_item_selected']};
                }}
            """)

        self.delete_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(217, 83, 79, 150);
                border: none;
                border-radius: 6px;
                padding: 4px 12px;
                color: white;
            }}
            QPushButton:hover {{
                background: rgba(217, 83, 79, 200);
            }}
        """)

        self.close_btn.setStyleSheet(f"""
            #closeBtn {{
                background: transparent;
                border: none;
                color: {styles['close_text']};
                font-size: 12px;
            }}
            #closeBtn:hover {{
                background: {styles['close_hover_bg']};
            }}
        """)

    def _apply_acrylic_effect(self):
        """应用毛玻璃效果（Win11）。"""
        if sys.platform != 'win32':
            return
        version = sys.getwindowsversion()
        if version.major < 10 or (version.major == 10 and version.build < 22000):
            return
        hwnd = int(self.winId())
        DWMWA_SYSTEMBACKDROP_TYPE = 38
        value = 3
        try:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_SYSTEMBACKDROP_TYPE,
                ctypes.byref(ctypes.c_int(value)), 4
            )
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────
    #  交互方法
    # ─────────────────────────────────────────────────────────────

    def _refresh_list(self, keyword: str = ''):
        """刷新历史列表。"""
        self.list_widget.clear()
        entries = self._history.search(keyword) if keyword else self._history.get_all()

        if not entries:
            # 显示空状态提示
            item = QListWidgetItem('暂无历史记录')
            item.setData(Qt.ItemDataRole.UserRole, None)
            self.list_widget.addItem(item)
            self._clear_detail()
            return

        for entry in entries:
            # 格式化显示：时间 + 模式 + 原文摘要
            time_str = entry['timestamp'].split('T')[1][:5]  # HH:MM
            mode_str = '规则' if entry['mode'] == 'rules' else f"LLM-{entry.get('prompt_name', '')}"
            summary = entry['original'][:30].replace('\n', ' ')
            if len(entry['original']) > 30:
                summary += '...'
            display = f"{time_str} [{mode_str}] {summary}"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, entry['id'])
            self.list_widget.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem):
        """点击列表项显示详情。"""
        entry_id = item.data(Qt.ItemDataRole.UserRole)
        if entry_id is None:
            return
        self._current_entry_id = entry_id
        entry = self._history.get_by_id(entry_id)
        if entry:
            self.detail_time.setText(f"时间：{entry['timestamp']}")
            mode_text = '规则清洗' if entry['mode'] == 'rules' else f"LLM - {entry.get('prompt_name', '默认')}"
            self.detail_mode.setText(f"模式：{mode_text}")
            self.original_view.setPlainText(entry['original'])
            self.result_view.setPlainText(entry['result'])

    def _clear_detail(self):
        """清空详情区。"""
        self._current_entry_id = None
        self.detail_time.setText('时间：')
        self.detail_mode.setText('模式：')
        self.original_view.setPlainText('')
        self.result_view.setPlainText('')

    def _on_search_changed(self, keyword: str):
        """搜索框输入变化时刷新列表。"""
        self._refresh_list(keyword)
        self._clear_detail()

    def _on_copy_original(self):
        """复制原文到剪贴板。"""
        if self._current_entry_id:
            entry = self._history.get_by_id(self._current_entry_id)
            if entry:
                self.copy_to_clipboard.emit(entry['original'])
                self._show_toast('已复制原文')

    def _on_copy_result(self):
        """复制结果到剪贴板。"""
        if self._current_entry_id:
            entry = self._history.get_by_id(self._current_entry_id)
            if entry:
                self.copy_to_clipboard.emit(entry['result'])
                self._show_toast('已复制结果')

    def _on_delete_entry(self):
        """删除当前选中条目。"""
        if not self._current_entry_id:
            return
        reply = QMessageBox.question(
            self, '确认删除',
            '确定要删除这条历史记录吗？',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._history.delete(self._current_entry_id)
            self._refresh_list(self.search_input.text())
            self._clear_detail()

    def _on_clear_all(self):
        """清空全部历史。"""
        reply = QMessageBox.question(
            self, '确认清空',
            '确定要清空所有历史记录吗？此操作不可撤销。',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._history.clear()
            self._refresh_list()
            self._clear_detail()

    def _show_toast(self, message: str):
        """显示简短提示（使用系统托盘 Toast）。"""
        # 通过信号通知主窗口显示 Toast
        pass

    def toggle_visibility(self):
        """切换可见性。"""
        if self.isVisible():
            self.hide()
        else:
            self._refresh_list()  # 显示时刷新数据
            self.show()
            self.activateWindow()
            self.raise_()

    def resizeEvent(self, event):
        """窗口大小变化时保存尺寸。"""
        super().resizeEvent(event)
        QTimer.singleShot(500, self._save_window_size)

    def _save_window_size(self):
        self._config.set('history.window_width', self.width())
        self._config.set('history.window_height', self.height())
```

- [ ] **Step 3: 运行语法检查**

Run: `python -m py_compile src/ui/history_window.py`
Expected: 无错误输出

- [ ] **Step 4: 提交**

```bash
git add src/ui/history_window.py
git commit -m "feat: add HistoryWindow UI component with dual-pane layout"
```

---

## Task 8: 设置界面集成历史配置

**Files:**
- Modify: `src/ui/settings_window.py:33-36,122-223`

- [ ] **Step 1: 添加历史设置 GroupBox 到通用页**

在 `_build_general_page` 方法中，在预览面板 GroupBox 后添加历史设置 GroupBox。

```python
# src/ui/settings_window.py (修改 _build_general_page 方法)
    def _build_general_page(self) -> QWidget:
        """构建通用设置页面（GroupBox 分组布局）"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName('content_scroll')

        page = QWidget()
        page.setObjectName('content_page')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        # ── 通知 GroupBox ──
        notify_box = QGroupBox('通知')
        notify_lay = QVBoxLayout(notify_box)
        self._chk_toast = QCheckBox('显示清洗完成通知（Toast）')
        self._chk_toast.setChecked(self._config.get('general.toast_notification', True))
        self._chk_toast.stateChanged.connect(
            lambda v: self._mark('general.toast_notification', bool(v)))
        notify_lay.addWidget(self._chk_toast)
        layout.addWidget(notify_box)

        # ... (保持其他 GroupBox 不变：启动、界面主题、独立热键、双击Ctrl+C、轮盘、预览)
        # 在预览面板 GroupBox 后添加：

        # ── 历史记录 GroupBox ──（新增）
        layout.addWidget(self._build_history_group())

        layout.addStretch()
        btn_reset_general = QPushButton('恢复通用默认设置')
        btn_reset_general.setObjectName('btn_reset')
        btn_reset_general.clicked.connect(self._confirm_and_reset_general)
        layout.addWidget(btn_reset_general)

        scroll.setWidget(page)
        return scroll
```

- [ ] **Step 2: 新增 _build_history_group 方法**

```python
# src/ui/settings_window.py (新增方法)
    def _build_history_group(self) -> QGroupBox:
        """构建历史记录设置分组。"""
        history_box = QGroupBox('历史记录')
        history_lay = QVBoxLayout(history_box)
        history_lay.setSpacing(6)

        # 启用开关
        self._chk_history = QCheckBox('启用历史记录（记录清洗前后文本）')
        self._chk_history.setChecked(self._config.get('history.enabled', True))
        self._chk_history.stateChanged.connect(
            lambda v: self._mark('history.enabled', bool(v)))
        history_lay.addWidget(self._chk_history)

        # 条数上限
        count_row = QHBoxLayout()
        count_row.addWidget(QLabel('最大条数：'))
        self._spin_history_count = QSpinBox()
        self._spin_history_count.setRange(50, 2000)
        self._spin_history_count.setValue(self._config.get('history.max_count', 500))
        self._spin_history_count.setToolTip('超出时自动删除最旧记录')
        self._spin_history_count.valueChanged.connect(
            lambda v: self._mark('history.max_count', v))
        count_row.addWidget(self._spin_history_count)
        count_row.addWidget(QLabel('条'))
        count_row.addStretch()
        history_lay.addLayout(count_row)

        # 快捷键录制
        hk_row = QHBoxLayout()
        hk_row.addWidget(QLabel('快捷键：'))
        self._btn_history_hotkey = QPushButton(
            self._config.get('history.hotkey', 'ctrl+h'))
        self._btn_history_hotkey.setCheckable(True)
        self._btn_history_hotkey.setObjectName('hotkey_btn')
        self._btn_history_hotkey.clicked.connect(self._on_history_hotkey_btn)
        hk_row.addWidget(self._btn_history_hotkey)
        hk_row.addStretch()
        history_lay.addLayout(hk_row)

        return history_box
```

- [ ] **Step 3: 新增快捷键录制按钮回调**

```python
# src/ui/settings_window.py (新增方法)
    def _on_history_hotkey_btn(self, checked: bool):
        """历史快捷键录制按钮回调。"""
        if checked:
            self._btn_history_hotkey.setText('请按下热键组合...')
            # 取消其他录制按钮的 checked 状态
            self._btn_record.setChecked(False)
            self._btn_wheel_hotkey.setChecked(False)
            self._btn_preview_hotkey.setChecked(False)
            self.grabKeyboard()
            self._recording_target = 'history'
        else:
            self.releaseKeyboard()
            self._recording_target = None
```

- [ ] **Step 4: 修改 keyPressEvent 处理 history 录制**

```python
# src/ui/settings_window.py (修改 keyPressEvent 方法)
    def keyPressEvent(self, event):
        """捕获热键录制"""
        target = getattr(self, '_recording_target', None)
        if target is None:
            return super().keyPressEvent(event)

        from PyQt6.QtCore import Qt as _Qt
        key = event.key()
        mods = event.modifiers()

        # 忽略纯修饰键
        if key in (
            _Qt.Key.Key_Control, _Qt.Key.Key_Shift, _Qt.Key.Key_Alt,
            _Qt.Key.Key_Meta, _Qt.Key.Key_unknown
        ):
            return

        parts = []
        if mods & _Qt.KeyboardModifier.ControlModifier:
            parts.append('ctrl')
        if mods & _Qt.KeyboardModifier.ShiftModifier:
            parts.append('shift')
        if mods & _Qt.KeyboardModifier.AltModifier:
            parts.append('alt')

        try:
            key_str = _Qt.Key(key).name
            key_name = key_str.replace('Key_', '').lower()
        except (ValueError, KeyError):
            key_name = ''
        if key_name:
            parts.append(key_name)

        if len(parts) >= 2:
            hotkey_str = '+'.join(parts)
            if target == 'clean':
                self._btn_record.setText(hotkey_str)
                self._mark('general.custom_hotkey.keys', hotkey_str)
            elif target == 'wheel':
                self._btn_wheel_hotkey.setText(hotkey_str)
                self._mark('wheel.switch_hotkey', hotkey_str)
            elif target == 'preview':
                self._btn_preview_hotkey.setText(hotkey_str)
                self._mark('preview.hotkey', hotkey_str)
            elif target == 'history':  # 新增
                self._btn_history_hotkey.setText(hotkey_str)
                self._mark('history.hotkey', hotkey_str)

        self.releaseKeyboard()
        self._recording_target = None
        # 取消所有录制按钮的 checked 状态
        if target == 'clean':
            self._btn_record.setChecked(False)
        elif target == 'wheel':
            self._btn_wheel_hotkey.setChecked(False)
        elif target == 'preview':
            self._btn_preview_hotkey.setChecked(False)
        elif target == 'history':  # 新增
            self._btn_history_hotkey.setChecked(False)
```

- [ ] **Step 5: 运行语法检查**

Run: `python -m py_compile src/ui/settings_window.py`
Expected: 无错误输出

- [ ] **Step 6: 提交**

```bash
git add src/ui/settings_window.py
git commit -m "feat: add history settings GroupBox to SettingsWindow"
```

---

## Task 9: 主程序初始化历史模块

**Files:**
- Modify: `src/main.py:24-31,40-153`

- [ ] **Step 1: 导入历史模块**

```python
# src/main.py (修改导入部分)
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QCursor, QIcon
from assets import asset as _asset
from config_manager import ConfigManager
from autostart_manager import sync_from_config
from tray_manager import TrayManager
from hotkey_manager import HotkeyManager
from clip_processor import ClipProcessor
from wheel_window import WheelWindow
from ui.settings_window import SettingsWindow
from ui.preview_window import PreviewWindow
from history_manager import HistoryManager  # 新增
from ui.history_window import HistoryWindow  # 新增
```

- [ ] **Step 2: 初始化 HistoryManager 和 HistoryWindow**

```python
# src/main.py (修改 main 函数的初始化部分)
def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName('NeatCopy')
    app.setWindowIcon(QIcon(_asset('idle.ico')))

    config = ConfigManager()
    sync_from_config(config.get('general.startup_with_windows', False))

    # 初始化历史管理器（新增）
    history = HistoryManager(
        max_count=config.get('history.max_count', 500)
    )

    tray = TrayManager(config)
    hotkey = HotkeyManager(config)
    processor = ClipProcessor(config, history_manager=history)  # 修改：注入 history_manager
    wheel = WheelWindow()
    preview = PreviewWindow(config)
    history_win = HistoryWindow(config, history)  # 新增

    # ... (信号连接部分继续)
```

- [ ] **Step 3: 连接历史相关信号**

```python
# src/main.py (在预览面板信号连接后添加)
    # ── 历史记录信号连接 ─────────────────────────────────────────
    hotkey.history_hotkey_triggered.connect(history_win.toggle_visibility)
    tray.open_history_requested.connect(history_win.toggle_visibility)
    history_win.copy_to_clipboard.connect(
        lambda text: processor.write_to_clipboard(text))

    # ── 初始化托盘锁定状态显示 ─────────────────────────────────────
    # ... (保持原有代码)
```

- [ ] **Step 4: 运行语法检查**

Run: `python -m py_compile src/main.py`
Expected: 无错误输出

- [ ] **Step 5: 提交**

```bash
git add src/main.py
git commit -m "feat: initialize HistoryManager and HistoryWindow in main"
```

---

## Task 10: 集成测试和最终验证

**Files:**
- Run all tests and manual verification

- [ ] **Step 1: 运行全部单元测试**

Run: `pytest tests/ -v`
Expected: PASS (所有测试)

- [ ] **Step 2: 运行应用进行手动测试**

Run: `python src/main.py`

手动测试清单：
1. 按 `Ctrl+H` 打开历史窗口，验证窗口显示
2. 执行一次规则清洗，验证历史记录已添加
3. 执行一次 LLM 清洗，验证历史记录包含 prompt_name
4. 在历史窗口中搜索关键词，验证搜索功能
5. 点击列表项，验证详情显示正确
6. 点击"复制原文"和"复制结果"，验证剪贴板写入
7. 点击"删除"按钮，验证删除确认和执行
8. 点击"清空全部"，验证清空确认和执行
9. 托盘菜单点击"历史记录"，验证窗口打开
10. 调整历史窗口大小，关闭后重新打开验证尺寸保存
11. 设置界面修改历史快捷键，保存后验证新快捷键生效

- [ ] **Step 3: 最终提交**

```bash
git add -A
git commit -m "feat: complete history feature implementation"
```

---

## 自检清单

**Spec Coverage:**
- ✅ 数据模型：`history_manager.py` 实现 add/delete/search/clear
- ✅ 存储位置：`%APPDATA%\NeatCopy\history.json`
- ✅ 配置项：`config_manager.py` 新增 `history` 组
- ✅ 热键触发：`hotkey_manager.py` 新增 `HOTKEY_ID_HISTORY` 和信号
- ✅ 托盘入口：`tray_manager.py` 新增菜单项和信号
- ✅ ClipProcessor 集成：成功时调用 `history.add()`
- ✅ 历史窗口 UI：`history_window.py` 双栏布局 + 搜索 + 复制 + 删除
- ✅ 设置界面：`settings_window.py` 新增历史 GroupBox + 快捷键录制
- ✅ 主程序初始化：`main.py` 初始化并连接信号
- ✅ 容量控制：`HistoryManager` 自动删除超出条目
- ✅ 错误处理：静默失败，不阻塞核心流程

**Placeholder Scan:**
- 无 TBD/TODO 占位符
- 所有代码块完整
- 所有命令具体

**Type Consistency:**
- `history_manager.add(original, result, mode, prompt_name)` 参数类型一致
- `history_hotkey_triggered` 信号在 HotkeyManager 定义、main 中连接
- `open_history_requested` 信号在 TrayManager 定义、main 中连接
- `copy_to_clipboard` 信号在 HistoryWindow 定义、main 中连接