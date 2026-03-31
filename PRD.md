# NeatCopy PRD — 桌面端剪贴板文本清洗工具

> 文档版本：v1.0 | 日期：2026-03-23 | 平台：Windows 11 | 技术栈：Python 3 + PyQt6

---

## 1. Executive Summary

**Problem Statement**
用户在从 PDF、CAJ、网页等来源复制文本后，常面临段落断行错乱、多余空格、全半角混用等排版问题，需要手动清理后才能使用，效率低下。

**Proposed Solution**
NeatCopy 是一款 Windows 系统托盘工具，通过全局快捷键对剪贴板内容进行即时文本清洗，支持规则引擎与大模型两种模式，清洗后直接覆盖剪贴板，用户 Ctrl+V 即得干净文本。

**Success Criteria**
- 规则模式处理延迟 < 100ms
- 后台内存占用 < 80MB
- 冷启动时间 < 3秒
- 单 `.exe` 无需额外环境，双击即用
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
> As a 用户，I want to 通过双击 Ctrl+C 或独立热键触发文本清洗 so that 复制后无需切换工具即可得到干净文本。

**AC:**
- [ ] 双击 Ctrl+C（默认间隔 ≤ 300ms）触发清洗，第一次正常复制，第二次触发
- [ ] 独立热键（默认 Ctrl+Shift+C）直接处理当前剪贴板内容
- [ ] 两种方式可在设置中独立启用/禁用，热键组合可自定义
- [ ] 清洗完成后剪贴板内容被覆盖，用户 Ctrl+V 得到干净文本

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

**Story 4：系统托盘常驻**
> As a 用户，I want to 程序在后台静默运行 so that 不占用桌面空间，随时可用。

**AC:**
- [ ] 启动后仅显示托盘图标，不弹出主窗口
- [ ] 托盘右键菜单：打开设置 / 暂停监听 / 退出
- [ ] 处理完成后 Toast 通知"已清洗，可直接粘贴"（可在设置关闭）

- [ ] 支持开机自启（可在设置中开关）

**Story 5：设置界面**
> As a 用户，I want to 通过图形界面配置所有参数 so that 无需手动编辑配置文件。

**AC:**
- [ ] 设置界面通过托盘右键"打开设置"唤起，支持再次点击收起
- [ ] 三个 Tab：**通用** / **清洗规则** / **大模型**
- [ ] **通用 Tab**：双击Ctrl+C（开关+间隔滑块）、独立热键（开关+按键录制）、开机自启、Toast通知开关
- [ ] **清洗规则 Tab**：模式切换（规则/大模型）、8条规则独立开关（含规则说明tooltip）
- [ ] **大模型 Tab**：总开关、Base URL输入、API Key（密码框+显示切换）、Model ID输入、Temperature滑块（0~2，步长0.1）、Prompt模板列表（新增/编辑/删除/设为默认）、Test Connection 按钮
- [ ] 所有设置生效，需点击保存按钮，需要“已保存”反馈
- [ ] 配置持久化存储为本地 JSON 文件（路径：`%APPDATA%\NeatCopy\config.json`）

---

### Non-Goals（明确不做）
- 不支持非文本内容（图片、文件路径等）的剪贴板处理
- 不支持 macOS / Linux（Windows 11 专属）
- 不提供云同步配置功能
- 不记录剪贴板历史
- 规则模式不做任何 AI 推断，纯正则/算法处理
- 大模型不做任何内容润色或翻译，仅整理格式

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
│                NeatCopy.exe                  │
│                                              │
│  ┌──────────┐    ┌──────────────────────┐   │
│  │  Tray    │    │   HotkeyManager      │   │
│  │  Manager │    │  - double Ctrl+C     │   │
│  │          │    │  - custom hotkey     │   │
│  └────┬─────┘    └──────────┬───────────┘   │
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
│  ┌──────────────────────────────────────┐   │
│  │         SettingsWindow (PyQt6)        │   │
│  │   Tab: 通用 / 清洗规则 / 大模型        │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

### 核心模块

| 模块 | 职责 | 关键依赖 |
|------|------|---------|
| `TrayManager` | 托盘图标、右键菜单、状态变色、Toast、锁定Prompt显示 | `PyQt6.QSystemTrayIcon` |
| `HotkeyManager` | 全局热键监听（双击Ctrl+C + 独立热键 + 轮盘切换热键） | `keyboard` 库 |
| `ClipProcessor` | 调度规则引擎或 LLM 客户端，写回剪贴板 | `pyperclip` / `win32clipboard` |
| `RuleEngine` | 8条清洗规则的纯 Python 实现 | `re`，`langdetect` |
| `LLMClient` | OpenAI 兼容接口调用，超时/错误处理 | `httpx`（异步） |
| `WheelWindow` | Prompt 轮盘选择器（扇形自绘、动画、键鼠交互） | `PyQt6`，`ctypes`(WH_MOUSE_LL) |
| `ConfigManager` | 读写 config.json，提供全局配置访问 | `json`，`pathlib` |
| `SettingsWindow` | PyQt6 三 Tab 设置界面（含轮盘配置分组） | `PyQt6` |

### 配置文件结构（`config.json`）

```json
{
  "general": {
    "startup_with_windows": false,
    "toast_notification": true,
    "double_ctrl_c": { "enabled": true, "interval_ms": 300 },
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
    "timeout_seconds": 30,
    "active_prompt_id": "default",
    "prompts": [
      {
        "id": "default",
        "name": "格式清洗",
        "content": "你是一个文本格式整理助手。请整理以下文本的段落格式和标点符号，保留原文所有文字内容，不增删任何内容，不修改任何措辞。只修正格式问题：合并不必要的换行，保留真正的段落分隔，修复标点符号使用。直接返回整理后的文本，不要任何解释。",
        "readonly": true,
        "visible_in_wheel": true
      }
    ]
  },
  "wheel": {
    "enabled": false,
    "hotkey": "ctrl+shift+p",
    "trigger_with_clean": false,
    "locked_prompt_id": null,
    "last_prompt_id": null,
    "visible_prompt_ids": ["default"]
  }
}
```

### Security & Privacy
- API Key 明文存储于本地 `config.json`（`%APPDATA%\NeatCopy\`），文件权限仅当前用户可读
- 剪贴板内容仅在内存中处理，不写入磁盘，不上报任何遥测数据
- LLM 模式下文本发送至用户自行配置的第三方 API，软件不中转
- 无网络请求（规则模式完全离线）

---

## 5. Risks & Roadmap

### 技术风险

| 风险 | 概率 | 影响 | 缓解方案 |
|------|------|------|---------|
| 双击 Ctrl+C 与系统/应用冲突 | 中 | 高 | 提供独立热键作为备选；默认仅启用独立热键 |
| 规则1误合并真实换行 | 中 | 中 | 规则2优先（空行保护）；提供规则1开关 |
| PyInstaller 打包后杀软误报 | 高 | 中 | 提供代码签名建议；文档说明白名单操作 |
| LLM 响应超时（>30s） | 低 | 低 | 固定30s超时，Toast提示，剪贴板不变 |
| `keyboard` 库需要管理员权限 | 低 | 高 | 测试验证；如需提权，UAC 启动时说明 |

### Phased Roadmap

**MVP（v1.0）— 核心可用**
- [ ] 系统托盘 + 右键菜单
- [ ] 独立热键触发（Ctrl+Shift+C）
- [ ] 8条规则引擎
- [ ] 基础设置界面（规则开关）
- [ ] 配置持久化
- [ ] PyInstaller 单 exe 打包

**v1.1 — 完整功能**
- [ ] 双击 Ctrl+C 触发
- [ ] Toast 通知 + 托盘变色
- [ ] 大模型模式（LLM Client + Prompt 管理）
- [ ] Test Connection 功能
- [ ] 开机自启

**v2.0 — 体验优化（待定）**
- [ ] 清洗前后 Diff 预览窗口
- [ ] 规则自定义（用户添加正则）
- [ ] 剪贴板历史（最近10条）
- [ ] 更多语言 UI 支持
