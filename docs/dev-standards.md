# NeatCopy 开发规范文档

> 版本：v1.0 | 日期：2026-03-23

---

## 1. 环境与依赖

### 1.1 Python 版本

要求 Python 3.11+（PyQt6 最低要求，PyInstaller 兼容性最佳）。

### 1.2 依赖安装

```bash
pip install PyQt6 keyboard pywin32 httpx langdetect pyperclip pyinstaller
```

`requirements.txt` 固定版本：

```
PyQt6>=6.6.0
keyboard>=0.13.5
pywin32>=306
httpx>=0.27.0
langdetect>=1.0.9
pyperclip>=1.8.2
pyinstaller>=6.0.0
```

### 1.3 开发命令

```bash
# 运行
python src/main.py

# 运行测试
python -m pytest tests/ -v

# 打包
pyinstaller --onefile --windowed --name NeatCopy --icon assets/icon_idle.ico --add-data "assets;assets" --hidden-import langdetect --collect-all pywin32 src/main.py
```

---

## 2. 代码风格

### 2.1 基本规范

- 遵循 PEP 8，行宽上限 **100** 字符
- 缩进：4空格，不用 Tab
- 字符串：优先单引号 `'`，含引号内容用双引号 `"`
- 文件编码：UTF-8，文件头无需显式声明

### 2.2 命名约定

| 类型 | 风格 | 示例 |
|------|------|------|
| 类名 | PascalCase | `RuleEngine`, `TrayManager` |
| 函数/方法 | snake_case | `clean_text()`, `on_hotkey_triggered()` |
| 私有方法 | `_snake_case` | `_merge_soft_newlines()` |
| 常量 | UPPER_SNAKE | `DEFAULT_INTERVAL_MS = 300` |
| Qt 信号 | snake_case | `hotkey_triggered = pyqtSignal()` |
| 配置键名 | snake_case | `merge_soft_newline`, `api_key` |

### 2.3 类型注解

所有公开方法必须有类型注解，私有方法建议加：

```python
# 正确
def clean(self, text: str, config: dict) -> str:
    ...

# 可接受（私有方法）
def _merge_spaces(self, text):
    ...
```

### 2.4 注释规范

- 模块顶部写单行功能说明
- 复杂算法逻辑（如规则4的上下文判断）必须注释说明思路
- Qt 信号连接处注释说明信号来源和处理目标
- 不写无意义注释（`i += 1  # i 加 1`）

---

## 3. 模块开发规范

### 3.1 ConfigManager 使用规范

**所有模块通过 ConfigManager 读写配置，禁止直接操作 config.json：**

```python
# 正确
from config_manager import ConfigManager
config = ConfigManager.instance()
value = config.get('general.toast_notification')
config.set('general.toast_notification', False)

# 禁止
import json
with open('config.json') as f:
    data = json.load(f)
```

配置键路径用点号分隔，支持嵌套访问：`'llm.prompts'`、`'rules.mode'`。

### 3.2 Qt 线程安全规范

**UI 操作（包括剪贴板读写）必须在主线程执行：**

```python
# 正确：从子线程 emit 信号，主线程的 slot 处理 UI
class LLMWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def run(self):
        try:
            result = asyncio.run(self._fetch())
            self.finished.emit(result)   # 由主线程 slot 写剪贴板
        except Exception as e:
            self.error.emit(str(e))

# 禁止：在子线程直接操作剪贴板
class LLMWorker(QThread):
    def run(self):
        result = asyncio.run(self._fetch())
        win32clipboard.SetClipboardData(...)  # 会崩溃
```

### 3.3 RuleEngine 规范

- `RuleEngine` 的所有方法必须是**纯函数**（无副作用，不读写外部状态）
- 规则函数签名统一为 `_rule_name(text: str) -> str`
- 执行顺序在 `clean()` 主函数中集中管理，各规则函数不互相调用
- 每条规则函数对应一个单元测试

### 3.4 LLMClient 规范

- `format()` 方法只抛出异常，不返回错误信息（由调用方处理）
- 不在 LLMClient 内部 catch 异常后静默失败
- 超时统一设 30s，不允许各处自行设置不同超时值

```python
# 正确：抛出异常
async def format(self, text: str, prompt: str, config: dict) -> str:
    resp = await client.post(...)
    resp.raise_for_status()   # 非200状态直接抛出
    return resp.json()['choices'][0]['message']['content']

# 禁止：吞掉异常
async def format(self, text: str, prompt: str, config: dict) -> str | None:
    try:
        ...
    except Exception:
        return None  # 调用方无法区分失败原因
```

### 3.5 设置界面规范

- 每个控件的信号连接到统一的 `_on_setting_changed(key, value)` 方法
- 不在各控件 handler 中直接调用 `ConfigManager.set()`，统一入口便于调试
- Prompt 编辑 Dialog 在 `SettingsWindow` 内部作为内嵌类定义，不单独建文件

---

## 4. 错误处理规范

### 4.1 分层原则

| 层级 | 处理方式 |
|------|---------|
| `RuleEngine` | 不抛出异常，输入异常时返回原文 |
| `LLMClient` | 只抛出，不处理 |
| `ClipProcessor` | 捕获所有异常，emit error signal |
| `TrayManager` | 接收 error signal，显示 Toast |

### 4.2 LLM 失败保护（最高优先级）

ClipProcessor 在进入 LLM 流程前必须保存原始文本，失败时确保不覆盖：

```python
def process(self):
    original_text = self._read_clipboard()
    if not original_text:
        return

    if self.config.get('rules.mode') == 'llm':
        # 保存原文，失败时不覆盖
        self._original_text = original_text
        worker = LLMWorker(original_text, ...)
        worker.error.connect(self._on_llm_error)
        worker.start()
        # 注意：此处不写剪贴板，由 _on_llm_success 写

def _on_llm_error(self, message: str):
    # 剪贴板内容保持不变（self._original_text 不写回）
    self.process_done.emit(False, message)
```

### 4.3 Toast 错误消息规范

错误消息使用用户可理解的中文，附加操作建议：

```python
ERROR_MESSAGES = {
    401: 'API Key 无效，请在设置中检查',
    429: '请求频率超限或余额不足',
    404: '模型 ID 不存在，请检查设置',
    'timeout': '请求超时（30s），请检查网络连接',
    'network': '网络连接失败，请检查代理设置',
}
```

---

## 5. 测试规范

### 5.1 测试范围

| 模块 | 测试类型 | 优先级 |
|------|---------|--------|
| `RuleEngine` | 单元测试（每条规则） | P0，必须 |
| `ConfigManager` | 单元测试（读写/默认值） | P0，必须 |
| `LLMClient` | 单元测试（Mock httpx） | P1，建议 |
| `HotkeyManager` | 手动测试 | P2，不自动化 |
| `TrayManager` | 手动测试 | P2，不自动化 |

### 5.2 RuleEngine 测试用例规范

每条规则至少覆盖以下场景：

```python
# 示例：规则1 合并软换行
class TestMergeSoftNewlines:
    def test_basic_merge(self):
        """PDF 典型断行场景"""
        input_text = "这是第一段\n文字继续"
        assert clean(input_text) == "这是第一段文字继续"

    def test_preserve_paragraph(self):
        """空行分隔的段落不合并"""
        input_text = "第一段\n\n第二段"
        assert clean(input_text) == "第一段\n\n第二段"

    def test_skip_code_block(self):
        """代码块内换行保留"""
        input_text = "```\ncode line1\ncode line2\n```"
        assert clean(input_text) == input_text

    def test_skip_list(self):
        """列表行保留换行"""
        input_text = "- item1\n- item2"
        assert clean(input_text) == "- item1\n- item2"
```

### 5.3 测试文件位置

```
tests/
├── test_rule_engine.py     # RuleEngine 全部8条规则
├── test_config_manager.py  # 读写、默认值、嵌套键
└── test_llm_client.py      # Mock httpx，测试错误分类
```

---

## 6. Git 提交规范

使用 Conventional Commits 格式：

```
<type>(<scope>): <subject>

type:
  feat     新功能
  fix      Bug 修复
  refactor 重构（不改变行为）
  test     测试相关
  docs     文档
  chore    构建/依赖/配置

scope（可选）：
  rule-engine / llm / hotkey / tray / settings / config

示例：
  feat(rule-engine): 实现规则4智能全半角标点转换
  fix(llm): 修复 LLM 失败时覆盖剪贴板的问题
  feat(hotkey): 支持双击 Ctrl+C 触发清洗
```

---

## 7. Roadmap 开发顺序建议

按 PRD Phased Roadmap，建议严格按以下顺序开发，每步可独立测试：

```
Step 1: ConfigManager + 默认配置文件读写
Step 2: RuleEngine（全部8条规则 + 单元测试）
Step 3: TrayManager（托盘图标 + 右键菜单，热键触发先用按钮模拟）
Step 4: HotkeyManager（独立热键 Ctrl+Shift+C）
Step 5: ClipProcessor（规则模式完整链路打通）
Step 6: SettingsWindow（规则 Tab + 通用 Tab）
Step 7: LLMClient + ClipProcessor LLM 分支
Step 8: SettingsWindow 大模型 Tab + Prompt 管理
Step 9: 双击 Ctrl+C + 热键自定义
Step 10: PyInstaller 打包验证
```
