# NeatCopy PRD — 桌面端剪贴板文本清洗工具

> 文档版本：v2.0.5 | 日期：2026-07-21 | 平台：Windows 10/11 + macOS 11+（当前发布包为 Apple Silicon） | 技术栈：Python 3 + PyQt6

---

## 1. Executive Summary

**Problem Statement**
用户在从 PDF、CAJ、网页等来源复制文本后，常面临段落断行错乱、多余空格、全半角混用等排版问题，需要手动清理后才能使用，效率低下。

**Proposed Solution**
NeatCopy 是一款 Windows 系统托盘 / macOS 菜单栏工具，通过平台原生全局快捷键对剪贴板内容进行即时文本清洗，支持规则引擎与大模型两种模式。清洗后直接覆盖剪贴板，用户可用 `Ctrl+V`（Windows）或 `⌘V`（macOS）粘贴干净文本。

**Success Criteria**
- 规则模式处理延迟 < 100ms
- 后台内存占用 < 80MB
- 冷启动时间 < 3秒
- Windows 提供单 `.exe` 与安装程序，macOS 提供 `.dmg` 安装包，均无需额外 Python 环境
- 8条清洗规则独立可控，零误触率（保护代码块/列表结构）

---

## 2. User Experience & Functionality

### User Personas

**Persona A — 学术研究者（主要用户）**
从 PDF/CAJ 大量复制文献内容，深受换行断句困扰，需要快速整理段落。

**Persona B — 内容创作者 / 编辑**
跨平台复制文本后全半角混用、间距混乱，需要统一排版风格。

**Persona C — 开发者 / 技术写作者**
复制技术文档时需要保护代码块和列表，不能破坏原有结构。

---

### User Stories & Acceptance Criteria

**Story 1：快速触发清洗**
> As a 用户，I want to 通过双击系统复制键或独立热键触发文本清洗 so that 复制后无需切换工具即可得到干净文本。

**AC:**
- [ ] 双击 `Ctrl+C`（Windows）或 `⌘C`（macOS，默认间隔 ≤ 300ms）触发清洗，第一次正常复制，第二次触发
- [ ] 独立热键直接处理当前剪贴板内容；Windows 默认 `Ctrl+Shift+C`，macOS 默认 `⌘⇧C`
- [ ] 两种方式可在设置中独立启用/禁用，热键组合可自定义
- [ ] 清洗完成后剪贴板内容被覆盖，用户使用平台粘贴键得到干净文本

**Story 2：规则模式清洗**
> As a 用户，I want to 通过预设规则自动清洗文本格式 so that 段落结构保留，乱码换行和空格被清除。

**AC:**
- [ ] 规则1：合并段落内软换行（行末非空行的单换行合并）
- [ ] 规则2：连续两个换行（空行）视为段落分隔，保留不合并
- [ ] 规则3：多个连续空格合并为单个空格
- [ ] 规则4：中文语境保留全角标点（。，），英文语境转为半角（.,）；通过相邻字符语言检测判断语境
- [ ] 规则5：中文字符与英文字母/数字相邻处自动插入空格（Pangu 风格）
- [ ] 规则6：每行首尾空白字符清除
- [ ] 规则7：识别缩进代码块（≥4空格/1 Tab）和 ``` 包裹内容，整块跳过所有清洗
- [ ] 规则8：`-`、`*`、`1.` 等列表标记开头的行保留换行，不合并
- [ ] 每条规则均可在设置中单独开关，默认全部开启
- [ ] 处理延迟 < 100ms（本地文本，10,000 字以内）

**Story 3：大模型模式清洗**
> As a 用户，I want to 调用大模型 API 对复杂文本进行格式整理 so that 规则难以覆盖的边界情况也能处理正确。

**AC:**
- [ ] 支持 OpenAI 兼容接口（Base URL + API Key + Model ID 可配置）
- [ ] 内置默认 Prompt 模板（不可删除，可编辑），专注格式整理，不修改文字内容
- [ ] 支持新增/编辑/删除/切换 Prompt 模板
- [ ] 大模型模式与规则模式互斥（二选一），通过设置切换
- [ ] 大模型模式有总开关（默认关闭）
- [ ] 处理期间托盘图标显示"处理中"状态
- [ ] 结果一次性写入剪贴板（无流式输出）
- [ ] 调用失败时：Toast 通知错误信息，剪贴板内容保持不变

**Story 3.5：Prompt 轮盘选择器**
> As a LLM 模式用户，I want to 通过扇形轮盘快速切换 Prompt so that 无需每次打开设置界面手动切换。

**AC:**
- [ ] 轮盘围绕鼠标位置弹出，扇形布局，最多显示 5 个 Prompt
- [ ] 两种触发模式：① 随清洗触发（每次清洗前选 Prompt）② 锁定模式（独立热键锁定 Prompt）
- [ ] 支持鼠标点击 + 数字键 1-5 选中，ESC / 点击外部关闭
- [ ] 仅 1 个可见 Prompt 时跳过轮盘直接执行，无可见 Prompt 时静默不处理
- [ ] 托盘菜单显示当前锁定的 Prompt（带 ✓）
- [ ] 轮盘弹出/关闭有淡入淡出动画
- [ ] 可在设置中配置：启用开关、随清洗触发开关、独立热键（可录制）、可见 Prompt 勾选

**Story 4：托盘 / 菜单栏常驻**
> As a 用户，I want to 程序在后台静默运行 so that 不占用桌面空间，随时可用。

**AC:**
- [ ] 启动后仅显示 Windows 托盘图标或 macOS 菜单栏图标，不弹出主窗口、不占用 Dock
- [ ] 图标菜单：打开设置 / 暂停监听 / 退出
- [ ] 处理完成后显示"已清洗，可直接粘贴"通知（可在设置关闭）

- [ ] 支持开机自启（可在设置中开关）

**Story 5：设置界面**
> As a 用户，I want to 通过图形界面配置所有参数 so that 无需手动编辑配置文件。

**AC:**
- [ ] 设置界面通过托盘 / 菜单栏的“打开设置”唤起，支持再次点击收起
- [ ] 四个 Tab：**通用** / **清洗规则** / **大模型** / **关于**
- [ ] **通用 Tab**：双击复制键（开关+间隔滑块）、独立热键（开关+按键录制）、开机自启、通知开关、界面主题、轮盘基本设置、预览面板设置
- [ ] **清洗规则 Tab**：模式切换（规则/大模型）、8条规则独立开关（含规则说明tooltip）
- [ ] **大模型 Tab**：总开关、Base URL输入、API Key（密码框+显示切换）、Model ID输入、Temperature滑块（0~2，步长0.1）、超时时长配置、Prompt模板列表（新增/编辑/删除/设为默认）、Test Connection 按钮、轮盘 Prompt 选择器
- [ ] **关于 Tab**：版本信息、检查更新、作者、项目地址
- [ ] 所有设置生效，需点击保存按钮，需要”已保存”反馈
- [ ] 配置持久化存储为本地 JSON 文件（Windows：`%APPDATA%\NeatCopy\config.json`；macOS：`~/Library/Application Support/NeatCopy/config.json`）

---

### Non-Goals（明确不做）
- 不支持非文本内容（图片、文件路径等）的剪贴板处理
- 暂不支持 Linux
- 当前 macOS Release 仅提供 Apple Silicon 安装包，不提供 Intel 安装包
- 不提供云同步配置功能
- 规则模式不做任何 AI 推断，纯正则/算法处理


---

## 3. AI System Requirements

### 接入规格

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| Base URL | OpenAI 兼容接口地址 | `https://api.openai.com/v1` |
| API Key | Bearer Token | 空（必填） |
| Model ID | 模型名称 | `gpt-4o-mini` |
| Temperature | 0~2 | `0.2`（格式任务低随机性） |
| Timeout | 请求超时 | 30s |

### 内置默认 Prompt

```
你是一个文本格式整理助手。请整理以下文本的段落格式和标点符号，
保留原文所有文字内容，不增删任何内容，不修改任何措辞。
只修正格式问题：合并不必要的换行，保留真正的段落分隔，
修复标点符号使用。直接返回整理后的文本，不要任何解释。
```

### 兼容模型清单（开箱即用，仅需修改 Base URL + Model ID）

| 服务商 | Base URL | 示例 Model ID |
|--------|----------|--------------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| Moonshot | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| Qwen | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-turbo` |

### Evaluation Strategy
- Test Connection 功能：发送固定测试文本，验证接口可达+返回非空结果
- 失败分类：网络错误 / 认证失败（401）/ 余额不足（402/429）/ 模型不存在（404）
- 每种错误在 Toast 中显示对应中文提示

---

## 4. Technical Specifications

### Architecture Overview

```
┌─────────────────────────────────────────────┐
│          NeatCopy.exe / NeatCopy.app         │
│                                              │
│  ┌──────────┐    ┌──────────────────────┐   │
│  │  Tray    │    │   HotkeyManager      │   │
│  │  Manager │    │  - double copy       │   │
│  │          │    │  - custom hotkey     │   │
│  └────┬─────┘    │  - wheel hotkey     │   │
│       │          │  - preview hotkey   │   │
│       │          └──────────┬───────────┘   │
│       │                     │               │
│       └──────────┬──────────┘               │
│                  ▼                           │
│          ┌───────────────┐                  │
│          │ ClipProcessor │                  │
│          │  ┌──────────┐ │                  │
│          │  │RuleEngine│ │ ← 规则模式        │
│          │  └──────────┘ │                  │
│          │  ┌──────────┐ │                  │
│          │  │LLMClient │ │ ← 大模型模式      │
│          │  └──────────┘ │                  │
│          └───────┬───────┘                  │
│                  │                          │
│          ┌───────▼───────┐                  │
│          │  ConfigManager│                  │
│          │  config.json  │                  │
│          └───────────────┘                  │
│                                              │
│  ┌──────────────┐  ┌────────────────────┐   │
│  │ WheelWindow  │  │  PreviewWindow     │   │
│  │ (轮盘选择器) │  │  (LLM预览面板)     │   │
│  └──────────────┘  └────────────────────┘   │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │         SettingsWindow (PyQt6)        │   │
│  │   Tab: 通用/清洗规则/大模型/关于      │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

### 核心模块

| 模块 | 职责 | 关键依赖 |
|------|------|---------|
| `TrayManager` | Windows 托盘 / macOS 菜单栏、状态变色、通知、锁定 Prompt 显示 | `PyQt6.QSystemTrayIcon` |
| `HotkeyManager` | 全局热键监听（双击复制 + 清洗 / 轮盘 / 预览 / 历史热键） | Windows：`RegisterHotKey` + `WH_KEYBOARD_LL`；macOS：Carbon + Quartz |
| `macos_input.py` | macOS 原生快捷键、复制模拟、双击复制监控与权限检测 | PyObjC、ApplicationServices、Quartz |
| `ClipProcessor` | 调度规则引擎或 LLM 客户端，读写剪贴板，发射预览信号 | Windows：`win32clipboard`；macOS：Qt Clipboard |
| `RuleEngine` | 8条清洗规则的纯 Python 实现 | `re`，`langdetect` |
| `LLMClient` | OpenAI 兼容接口调用，超时/错误处理 | `httpx`（同步） |
| `WheelWindow` | Prompt 轮盘选择器（扇形自绘、动画、键鼠交互） | `PyQt6`；Windows 使用 `WH_MOUSE_LL`，macOS 使用原生前台激活与焦点恢复 |
| `PreviewWindow` | LLM 预览面板（置顶悬浮、可编辑） | `PyQt6`；Windows 可使用 DWM 效果 |
| `ConfigManager` | 读写 config.json，提供全局配置访问 | `json`，`pathlib` |
| `PlatformPaths` | 解析不同系统的应用数据目录 | `pathlib` |
| `AutostartManager` | 跨平台开机启动 | Windows HKCU Run；macOS LaunchAgent |
| `SettingsWindow` | PyQt6 四 Tab 设置界面（含轮盘配置分组） | `PyQt6` |

### 配置文件结构（`config.json`）

```json
{
  "ui": {
    "theme": "light",
    "window_width": 700,
    "window_height": 550
  },
  "general": {
    "startup_with_windows": false,
    "toast_notification": true,
    "double_ctrl_c": { "enabled": false, "interval_ms": 300 },
    "custom_hotkey": { "enabled": true, "keys": "ctrl+shift+c" }
  },
  "rules": {
    "mode": "rules",
    "merge_soft_newline": true,
    "keep_hard_newline": true,
    "merge_spaces": true,
    "smart_punctuation": true,
    "pangu_spacing": true,
    "trim_lines": true,
    "protect_code_blocks": true,
    "protect_lists": true
  },
  "llm": {
    "enabled": false,
    "base_url": "https://api.openai.com/v1",
    "api_key": "",
    "model_id": "gpt-4o-mini",
    "temperature": 0.2,
    "timeout": 30,
    "active_prompt_id": "default",
    "prompts": [
      {
        "id": "default",
        "name": "格式清洗",
        "content": "你是一个文本格式整理助手...",
        "readonly": true,
        "visible_in_wheel": true
      },
      {
        "id": "preset-prompt-master",
        "name": "PromptMaster",
        "content": "...",
        "readonly": false,
        "visible_in_wheel": true
      },
      {
        "id": "preset-translate",
        "name": "翻译",
        "content": "...",
        "readonly": false,
        "visible_in_wheel": true
      },
      {
        "id": "preset-ask",
        "name": "随时提问",
        "content": "根据我的提问提供简短的回答...",
        "readonly": false,
        "visible_in_wheel": true
      }
    ]
  },
  "wheel": {
    "enabled": true,
    "switch_hotkey": "ctrl+shift+p",
    "trigger_with_clean": true,
    "locked_prompt_id": null,
    "last_prompt_id": null
  },
  "preview": {
    "enabled": true,
    "hotkey": "ctrl+q",
    "window_width": 320,
    "window_height": 200,
    "theme": "dark"
  },
  "history": {
    "enabled": true,
    "max_count": 500,
    "hotkey": "ctrl+h",
    "window_width": 600,
    "window_height": 400
  }
}
```

> 配置键名为兼容历史版本继续保留 `startup_with_windows` 和 `double_ctrl_c`。首次生成配置时，快捷键默认值由平台决定：Windows 使用 `ctrl`，macOS 清洗与轮盘使用 `cmd`；macOS 预览和历史使用 `ctrl`，避免占用系统的 `⌘Q` / `⌘H`。

### Security & Privacy
- API Key 明文存储于本地 `config.json`（Windows：`%APPDATA%\NeatCopy\`；macOS：`~/Library/Application Support/NeatCopy/`），文件权限限制为当前用户
- 剪贴板内容仅在内存中处理，不写入磁盘，不上报任何遥测数据
- LLM 模式下文本发送至用户自行配置的第三方 API，软件不中转
- 无网络请求（规则模式完全离线）

---

## 5. Risks & Roadmap

### 技术风险

| 风险 | 概率 | 影响 | 缓解方案 |
|------|------|------|---------|
| 双击复制键与系统/应用冲突 | 中 | 高 | 提供独立热键作为备选；默认仅启用独立热键 |
| macOS 未授予辅助功能 / 输入监控权限 | 中 | 高 | 设置页解释权限边界；普通面板热键不要求权限；授权后自动重试或提示重启 |
| 规则1误合并真实换行 | 中 | 中 | 规则2优先（空行保护）；提供规则1开关 |
| PyInstaller 打包后杀软误报 | 高 | 中 | 提供代码签名建议；文档说明白名单操作 |
| LLM 响应超时（>30s） | 低 | 低 | 固定30s超时，Toast提示，剪贴板不变 |
| Windows 低级键盘钩子被安全软件拦截 | 低 | 高 | 独立热键仍使用 `RegisterHotKey`；文档提供冲突与权限排查 |

### Phased Roadmap

**MVP（v1.0）— Windows 核心可用（历史里程碑）**
- [x] Windows 系统托盘 + 右键菜单
- [x] Windows 独立热键触发（`Ctrl+Shift+C`）
- [x] 8条规则引擎
- [x] 基础设置界面（规则开关）
- [x] 配置持久化
- [x] PyInstaller 单 exe 打包

**v1.1 — 完整功能**
- [x] 双击 `Ctrl+C` 触发
- [x] Toast 通知 + 托盘变色
- [x] 大模型模式（LLM Client + Prompt 管理）
- [x] Test Connection 功能
- [x] 开机自启

**v1.2 — 体验增强**
- [x] Prompt 轮盘选择器
- [x] LLM 预览面板
- [x] 历史记录功能

**v2.0.5 — 跨平台支持**
- [x] macOS Apple Silicon 支持（菜单栏、原生全局热键、双击 `⌘C`、DMG）
- [x] Windows / macOS 平台默认快捷键与用户数据目录
- [x] Windows HKCU Run / macOS LaunchAgent 开机启动
- [x] Windows 与 macOS 双平台 CI

**未来规划**
- [ ] 清洗前后 Diff 预览窗口
- [ ] 规则自定义（用户添加正则）
- [ ] 更多语言 UI 支持
