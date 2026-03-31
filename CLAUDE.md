# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

NeatCopy 是一款 Windows 11 桌面端剪贴板文本清洗工具，常驻系统托盘，通过全局快捷键触发清洗，支持规则引擎与大模型两种模式（二选一）。

## 技术栈

- **语言**：Python 3
- **UI**：PyQt6（`QSystemTrayIcon` 托盘，`QTabWidget` 设置界面）
- **全局热键**：Win32 `RegisterHotKey` API + `WH_KEYBOARD_LL` 低级键盘钩子
- **剪贴板**：`win32clipboard`（优先）/ `pyperclip`（备用）
- **LLM 请求**：`httpx`（异步，OpenAI 兼容接口）
- **语言检测**：`langdetect`（规则4智能全/半角判断）
- **打包**：PyInstaller → 单 `.exe`

## 模块结构

```
src/
├── main.py              # 入口，初始化 QApplication + TrayManager + PreviewWindow + HistoryWindow，轮盘编排
├── tray_manager.py      # QSystemTrayIcon，托盘菜单，图标三态变色，Toast，锁定Prompt显示
├── hotkey_manager.py    # 全局热键（双击Ctrl+C + 独立热键 + 轮盘切换热键 + 预览热键 + 历史记录热键），Win32 API
├── clip_processor.py    # 调度入口：读剪贴板 → 规则或LLM → 写回剪贴板 + 发射预览信号 + 记录历史
├── rule_engine.py       # 8条清洗规则，纯正则/算法，无网络
├── llm_client.py        # OpenAI 兼容接口，httpx 异步，可配置超时
├── wheel_window.py      # Prompt 轮盘选择器（扇形自绘、动画、键鼠交互、WH_MOUSE_LL钩子）
├── history_manager.py   # 历史记录数据管理：读写 history.json，增删查接口
├── autostart_manager.py # Windows 开机自启动管理（HKCU Run 注册表）
├── assets.py            # 共享 assets 路径模块（图标等资源）
├── version.py           # 版本号定义
├── config_manager.py    # 读写 %APPDATA%\NeatCopy\config.json，含轮盘配置
└── ui/
    ├── settings_window.py  # PyQt6 四Tab设置界面（通用/规则/大模型/关于），含轮盘配置分组
    ├── preview_window.py   # LLM 预览面板（置顶悬浮窗，毛玻璃，可编辑）
    ├── history_window.py   # 历史记录窗口（双栏布局，搜索，复制，删除）
    ├── styles.py           # 主题样式定义（ColorPalette、get_settings_stylesheet）
    └── components/
        ├── sidebar.py      # 侧边栏导航组件
        └── icon_helper.py  # 图标辅助工具
```

## 核心数据流

```
用户触发热键
    → HotkeyManager 捕获
    → ClipProcessor.process()
        → 读剪贴板文本
        → 按 config.rules.mode 分派：
            rules  → RuleEngine.clean(text, config)
            llm    → LLMClient.format(text, prompt, config)
        → 写回剪贴板
        → [LLM模式] emit preview_ready(result, prompt_name)
        → HistoryManager.add(original, result, mode, prompt_name)  # 记录历史
    → TrayManager 显示状态（成功/失败）+ Toast（若开启）
    → [预览面板可见] PreviewWindow 接收并刷新显示
```

## LLM 预览面板

**触发方式**：独立快捷键（默认 `Ctrl+Q`）打开，可持久保持，再次按快捷键关闭。

**核心特性**：
- 仅 LLM 模式生效，规则模式忽略
- 双写模式：结果照常写入剪贴板，同时发送到预览面板
- 状态信息：上方显示处理状态（等待/处理中/完成/失败），下方显示 prompt 名称
- 文本编辑：结果可编辑，手动点击"应用到剪贴板"按钮确认
- 窗口外观：置顶悬浮窗，可拖动，可调整大小，毛玻璃材质
- 主题切换：深色/浅色两种主题，在设置界面配置

**关键信号**：
```python
# ClipProcessor
preview_ready = pyqtSignal(str, str)  # (result, prompt_name)
preview_failed = pyqtSignal(str)      # (error_message)

# HotkeyManager
preview_hotkey_triggered = pyqtSignal()  # 预览面板快捷键触发
```

**关闭方式**：
- 点击面板右上角关闭按钮（X）
- 再次按快捷键 `Ctrl+Q`（toggle 行为）

**配置项**（`config.preview`）：
- `enabled`: 预览功能开关
- `hotkey`: 打开预览面板的快捷键
- `window_width`: 窗口宽度（用户调整后保存）
- `window_height`: 窗口高度（用户调整后保存）
- `theme`: 主题（dark/light）

## Prompt 轮盘选择器

**功能定位**：LLM 模式下的 Prompt 快速切换 UI，复用现有 prompts 配置，扇形轮盘围绕鼠标位置展开。

**两种触发模式**：
1. **随清洗触发**（`trigger_with_clean`）：按清洗热键时先弹轮盘选 Prompt → 再执行清洗
2. **锁定模式**：独立热键（默认 `Ctrl+Shift+P`）弹轮盘选 Prompt 并锁定 → 后续清洗直接使用

**轮盘交互**：
- 鼠标点击 / 数字键 1-5 选中，ESC / 点击外部关闭
- 仅 1 个可见 Prompt 时跳过轮盘直接执行，无可见 Prompt 时静默不处理
- 弹出/关闭有淡入淡出动画

**窗口技术细节**（`wheel_window.py`）：
- `Qt.WindowType.FramelessWindowHint | WindowStaysOnTopHint`
- 关闭检测用 `WH_MOUSE_LL` 低级鼠标钩子（不依赖 Qt 焦点，后台热键 App 可靠）
- `_anim` 的 `finished` 信号管理需注意：`show_at()` 时必须先 disconnect 残留的 `hide` 连接
- 扇区坐标计算使用 QCursor.pos()（逻辑坐标），不能用 Win32 物理坐标（HiDPI 不匹配）

**配置项**（`config.wheel`）：
```json
{
  "enabled": true,
  "switch_hotkey": "ctrl+shift+p",
  "trigger_with_clean": true,
  "locked_prompt_id": null,
  "last_prompt_id": null
}
```

**设置界面**：
- 通用 Tab 底部：启用/禁用开关、随清洗触发开关、独立切换热键（可录制）
- 大模型 Tab 底部：轮盘 Prompt 选择器（左右两栏设计，左栏可用模板勾选，右栏轮盘模板带序号，最多5个）

## 历史记录

**功能定位**：自动记录每次清洗的原文和结果，支持搜索、查看、复制、删除。

**触发方式**：
- 独立快捷键（默认 `Ctrl+H`）打开历史记录窗口
- 托盘菜单"历史记录"选项

**核心特性**：
- 自动记录：每次清洗成功后自动保存（原文、结果、模式、时间戳）
- 双栏布局：左侧列表显示时间+模式+摘要，右侧显示完整详情
- 全文搜索：匹配原文或结果内容（不区分大小写）
- 快速复制：一键复制原文或结果到剪贴板
- 容量控制：默认保留最近 500 条，可在设置中调整

**关键信号**：
```python
# HotkeyManager
history_hotkey_triggered = pyqtSignal()  # 历史记录快捷键触发

# TrayManager
open_history_requested = pyqtSignal()    # 托盘菜单打开历史记录

# HistoryWindow
copy_to_clipboard = pyqtSignal(str)      # 请求写入剪贴板
```

**数据存储**：
- 路径：`%APPDATA%\NeatCopy\history.json`
- 结构：`{ "entries": [{id, timestamp, mode, prompt_name, original, result}, ...] }`

**配置项**（`config.history`）：
```json
{
  "enabled": true,
  "max_count": 500,
  "hotkey": "ctrl+h",
  "window_width": 600,
  "window_height": 400
}
```

**设置界面**：
- 通用 Tab 底部：启用/禁用开关、最大条数、快捷键录制

## 关键设计约定

**规则引擎执行顺序**（顺序有依赖，不可随意调换）：
1. 识别并提取代码块（规则7）→ 跳过后续处理
2. 识别列表行（规则8）→ 标记保护
3. 合并软换行（规则1），但跳过受保护行
4. 保留空行段落分隔（规则2）
5. 合并多余空格（规则3）
6. 智能全/半角标点（规则4，需 langdetect）
7. 中英文间距（规则5，Pangu 风格）
8. 去除行首尾空白（规则6）

**配置文件**：`%APPDATA%\NeatCopy\config.json`，结构见 `PRD.md §4`。设置界面点击保存按钮后写入，并显示"已保存"反馈。

**LLM 模式**：调用失败时剪贴板内容必须保持不变，不得覆盖原文。`prompts` 列表中 `"readonly": true` 的条目不可删除但可编辑。

**双击 Ctrl+C**：默认关闭（避免热键冲突），独立热键 `Ctrl+Shift+C` 默认开启。

## 开发命令

```bash
# 安装依赖
pip install PyQt6 keyboard pywin32 httpx langdetect pyperclip pyinstaller

# 运行
python src/main.py

# 打包为单 exe
pyinstaller --onefile --windowed --name NeatCopy --add-data "assets;assets" src/main.py
```

## 性能约束

- 规则模式处理延迟 < 100ms（10,000字以内）
- 后台内存占用 < 80MB
- 冷启动 < 3秒
