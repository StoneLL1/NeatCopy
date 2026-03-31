# NeatCopy 历史记录功能设计文档

## 概述

为 NeatCopy 剪贴板清洗工具添加历史记录功能，记录清洗前后的文本内容，支持搜索、复制和删除操作。

## 功能需求

### 核心功能
- **记录内容**：原文 + 处理结果 + 处理模式（规则/LLM） + Prompt 名称（LLM 模式）
- **存储方式**：JSON 文件，位于 `%APPDATA%\NeatCopy\history.json`
- **触发方式**：快捷键 + 托盘菜单入口（两者并存）
- **保留策略**：可配置条数上限，超出自动删除最旧记录

### UI 功能
- **窗口类型**：独立弹出窗口（类似预览面板）
- **布局**：双栏设计（左侧列表 + 右侧详情）
- **功能**：全文搜索、一键复制、删除/清空

## 模块结构

新增文件：
```
src/
├── history_manager.py      # 历史数据管理
├── ui/
│   └── history_window.py   # 历史记录窗口
```

修改文件：
```
src/
├── clip_processor.py       # 新增历史记录调用
├── hotkey_manager.py       # 新增快捷键信号
├── tray_manager.py         # 托盘菜单新增入口
├── main.py                 # 初始化和信号连接
├── config_manager.py       # 新增配置项
├── ui/settings_window.py   # 通用 Tab 新增历史设置
```

## 数据模型

### history.json 结构

```json
{
  "entries": [
    {
      "id": "uuid-string",
      "timestamp": "2026-03-31T14:30:00",
      "mode": "rules",
      "prompt_name": null,
      "original": "原始剪贴板文本...",
      "result": "处理后的文本..."
    },
    {
      "id": "uuid-string",
      "timestamp": "2026-03-31T14:25:00",
      "mode": "llm",
      "prompt_name": "格式清洗",
      "original": "另一段原文...",
      "result": "处理后文本..."
    }
  ]
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | UUID，唯一标识条目 |
| `timestamp` | string | ISO 格式时间戳 |
| `mode` | string | `rules` 或 `llm` |
| `prompt_name` | string | LLM 模式记录 Prompt 名称，规则模式为 null |
| `original` | string | 清洗前原文 |
| `result` | string | 清洗后结果 |

### 容量控制

新增条目时检查 `entries.length >= max_count`，超出则移除 timestamp 最旧的条目。

## 核心流程

### 记录时机

仅清洗成功时记录历史，失败不记录（保持原文不变）。

```
用户触发热键
    → ClipProcessor.process()
        → 读取剪贴板原文
        → 规则/LLM 处理
        → 成功写入剪贴板
        → 【新增】HistoryManager.add(original, result, mode, prompt_name)
            → 检查条数上限
            → 写入 history.json
    → TrayManager 显示成功状态
```

### ClipProcessor 改动

ClipProcessor 构造函数新增 `history_manager` 参数：

```python
def __init__(self, config, history_manager=None, parent=None):
    super().__init__(parent)
    self._config = config
    self._history = history_manager
    ...
```

在 `_process_rules` 和 `_on_llm_success` 成功分支调用 `self._history.add()`。

## 历史窗口 UI

### 窗口布局

```
┌─────────────────────────────────────────────────────────┐
│  历史记录                                    [× 关闭]    │
├─────────────────────────────────────────────────────────┤
│  [🔍 搜索框________________________]        [清空全部]   │
├───────────────────────┬─────────────────────────────────┤
│  【列表区】           │  【详情区】                      │
│  ┌─────────────────┐  │                                 │
│  │ 14:30 [规则]    │  │  时间：2026-03-31 14:30:00      │
│  │ PDF复制的一段.. │  │  模式：规则清洗                  │
│  ├─────────────────┤  │                                 │
│  │ 14:25 [LLM-格式]│  │  ┌─ 原文 ─────────────────────┐│
│  │ 另一段原文...   │  │  │ （可滚动查看完整内容）      ││
│  ├─────────────────┤  │  └────────────────────────────┘│
│  │ ...             │  │                                 │
│  └─────────────────┘  │  ┌─ 结果 ─────────────────────┐│
│                       │  │ （可滚动查看完整内容）      ││
│                       │  └────────────────────────────┘│
│                       │                                 │
│                       │  [复制原文] [复制结果] [删除]   │
└───────────────────────┴─────────────────────────────────┘
```

### 交互设计

| 操作 | 行为 |
|------|------|
| 点击列表项 | 右侧详情区显示完整原文和结果 |
| 搜索输入 | 实时过滤列表（匹配原文或结果内容） |
| 复制原文 | 将原文写入剪贴板，显示 Toast 提示 |
| 复制结果 | 将结果写入剪贴板，显示 Toast 提示 |
| 删除 | 确认对话框，确认后删除该条目 |
| 清空全部 | 确认对话框，确认后删除全部历史 |
| 关闭窗口 | 点击关闭按钮或再次按快捷键（toggle） |

### 窗口属性

- `Qt.WindowType.WindowStaysOnTopHint`：置顶
- 可调整大小，退出时保存宽高到配置
- 主题跟随设置（深色/浅色），复用现有 `ui/styles.py`

### 列表项显示

每条记录显示：
- 时间（HH:MM 格式）
- 模式标签（规则/LLM）
- Prompt 名称（仅 LLM 模式）
- 原文摘要（前 30 字符，超出显示省略号）

## 配置集成

### 新增配置项

```python
'history': {
    'enabled': True,           # 历史功能开关
    'max_count': 500,          # 最大条数上限
    'hotkey': 'ctrl+h',        # 打开历史窗口快捷键
    'window_width': 600,       # 窗口宽度
    'window_height': 400,      # 窗口高度
},
```

### 设置界面改动

通用 Tab 新增"历史记录" GroupBox：
- **启用开关**：禁用时不记录历史，窗口显示"历史功能已禁用"
- **条数上限**：SpinBox，范围 50-2000，默认 500
- **快捷键录制**：复用现有热键录制逻辑

### 配置生效时机

- 启用/禁用：立即生效
- 条数上限：下次写入时检查新上限
- 快捷键：保存后重新注册热键

## 错误处理

### 原则

历史功能是辅助功能，**失败时绝不阻塞核心清洗流程**。

### 异常处理策略

| 场景 | 处理方式 |
|------|----------|
| history.json 损坏/不存在 | 自动重建空文件 |
| 写入失败（磁盘满/权限） | 静默失败，不阻塞清洗 |
| 读取失败 | 窗口显示空列表 + 提示 |
| 历史为空 | 窗口显示"暂无历史记录"占位提示 |
| 搜索无结果 | 显示"无匹配记录" |
| 功能禁用 | 窗口显示"历史功能已禁用" |

## 信号设计

### HotkeyManager 新增信号

```python
history_hotkey_triggered = pyqtSignal()
```

### TrayManager 新增信号

```python
open_history_requested = pyqtSignal()
```

### HistoryWindow 信号

```python
copy_to_clipboard = pyqtSignal(str)  # 请求写入剪贴板
```

## 实现优先级

1. `history_manager.py`：核心数据读写逻辑
2. `ui/history_window.py`：窗口 UI 和交互
3. `clip_processor.py`：集成历史记录调用
4. `hotkey_manager.py` + `tray_manager.py`：触发入口
5. `main.py`：初始化和信号连接
6. `config_manager.py` + `settings_window.py`：配置和设置界面