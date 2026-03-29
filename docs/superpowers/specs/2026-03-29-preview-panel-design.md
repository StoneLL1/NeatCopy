# LLM Preview Panel Design

Date: 2026-03-29

## 1. Overview

为 NeatCopy 新增一个 LLM 结果预览面板，允许用户在 LLM 处理完成后查看、编辑处理结果，再决定是否应用到剪贴板。

核心特性：

- 独立快捷键（默认 `Ctrl+Q`）打开预览面板，toggle 行为（再按一次关闭）
- 预览面板可持久保持，每次 LLM 处理自动刷新内容
- 双写模式：结果照常写入剪贴板，同时发送到预览面板
- 仅 LLM 模式生效，规则模式忽略
- 状态信息显示：上方显示处理状态，下方显示 prompt 名称
- 可编辑结果文本，手动"应用到剪贴板"按钮确认写入

## 2. Data Flow

### 当前流程（不变）

```
热键触发 → 读剪贴板 → LLM处理 → 写入剪贴板 → 托盘提示
```

### 新增预览流（并行追加）

```
LLM处理完成 → 写入剪贴板（原有行为不变）
             → 同时发射 preview_ready 信号（新增）
             → PreviewWindow 接收并刷新显示
```

### 预览面板交互流

```
用户点击"应用到剪贴板" → 编辑后文本写入剪贴板
```

### 关键信号

- `ClipProcessor` 新增信号：
  - `preview_processing()` — LLM 开始处理时发射，面板显示"处理中..."
  - `preview_ready(str result, str prompt_name)` — LLM 处理成功时发射
  - `preview_failed(str error)` — LLM 处理失败时发射
- 仅在 LLM 模式下且预览面板可见时发射，否则零开销
- `PreviewWindow` 监听这些信号，更新状态栏和文本框

## 3. Module Design

### 新增文件

- `src/ui/preview_window.py` — 预览面板窗口组件

### 修改文件

- `src/clip_processor.py` — 新增 `preview_ready` 信号，LLM 成功时发射
- `src/hotkey_manager.py` — 新增预览面板热键注册（第三个 RegisterHotKey ID）
- `src/config_manager.py` — 新增预览相关配置项
- `src/ui/settings_window.py` — 新增预览热键设置区域
- `src/main.py` — 集成预览面板信号连接

### PreviewWindow 组件结构

```
PreviewWindow (QWidget, frameless, always-on-top)
├── 顶部栏
│   ├── QLabel: 状态文字 "等待处理" / "处理中..." / "处理完成" / "处理失败"
│   └── QPushButton: 自定义关闭按钮（X），无边框风格
├── 文本编辑区（中央）
│   └── QTextEdit: 可编辑的结果文本
├── Prompt 名称栏（底部上方）
│   └── QLabel: 显示当前使用的 prompt 名称
└── 应用按钮（底部）
    └── QPushButton: "应用到剪贴板"
```

### 窗口属性

- `WindowFlags`: `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint`
- 背景：Windows 11 毛玻璃效果（DWM API `DwmExtendFrameIntoClientArea`）
- 可拖动：重写 `mousePressEvent` + `mouseMoveEvent` 实现无边框拖动
- 可调整大小：四角/边缘拖动 resize
- 默认尺寸：紧凑（320x200px）
- 记住用户调整的尺寸：保存到 config
- 关闭方式：
  - 点击面板右上角关闭按钮（X）
  - 再次按快捷键 `Ctrl+Q`（toggle 行为）

## 4. Configuration

新增配置项，存储于 `%APPDATA%\NeatCopy\config.json`：

```json
{
  "preview": {
    "enabled": true,
    "hotkey": "ctrl+q",
    "window_width": 320,
    "window_height": 200
  }
}
```

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | bool | `true` | 预览功能开关 |
| `hotkey` | str | `"ctrl+q"` | 打开预览面板的快捷键 |
| `window_width` | int | `320` | 窗口宽度（用户调整后保存） |
| `window_height` | int | `200` | 窗口高度（用户调整后保存） |

### 设置界面

在 General Tab 新增"预览面板"分组：

- 启用复选框
- 热键录制按钮（复用现有 `KeyRecorderButton` 组件）
- 录制完成后调用 `HotkeyManager.register_preview_hotkey()`

## 5. Error Handling & Edge Cases

### LLM 处理失败时

- 预览面板状态栏显示"处理失败" + 错误信息
- 文本框内容保持不变（不覆盖为空或错误文本）
- 剪贴板保持原有行为（不覆盖原文）

### 预览面板未打开时

- `preview_ready` 信号不发射，零开销
- 完全不影响现有流程

### 面板打开但切换到规则模式

- 规则模式下不更新预览面板
- 面板状态栏显示"规则模式，无预览"

### 编辑冲突

- 新 LLM 结果到达时直接覆盖编辑区内容，无需用户确认
