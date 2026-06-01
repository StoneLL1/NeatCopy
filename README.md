<div align="center">

<img width="275" height="130" src="https://github.com/user-attachments/assets/a09faa5b-7990-47b4-827e-f8574c9ae083" alt="NeatCopy Logo"/>

# NeatCopy

**让复制粘贴更干净，也让 AI 能力触手可及**

[![Release](https://img.shields.io/github/v/release/StoneLL1/NeatCopy?style=flat-square&color=3b82f6)](https://github.com/StoneLL1/NeatCopy/releases/latest)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078d4?style=flat-square)](https://github.com/StoneLL1/NeatCopy/releases/latest)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776ab?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Stars](https://img.shields.io/github/stars/StoneLL1/NeatCopy?style=flat-square&logo=github)](https://github.com/StoneLL1/NeatCopy/stargazers)

NeatCopy 是一款常驻 Windows 系统托盘的剪贴板文本处理工具。复制文本后按下全局快捷键，
即可通过本地规则或大模型完成清洗、翻译、润色与摘要。

查看官网：https://stonell1.github.io/neatcopy-website/

[下载安装](https://github.com/StoneLL1/NeatCopy/releases/latest) ·
[功能概览](#-功能概览) ·
[使用指南](#-使用指南) ·
[开发说明](#-开发说明)

</div>


---

## 为什么需要 NeatCopy？

从 PDF、论文、网页或聊天窗口复制文字时，经常会遇到多余换行、混乱空格和中英文标点不统一的问题：

```text
处理前：
随着人工智能技术的不断发
展，大语言模型在自然语言处
理领域取得了重大突破。

按下 Ctrl+Shift+C 后：
随着人工智能技术的不断发展，大语言模型在自然语言处理领域取得了重大突破。
```

中英文混排也可以一键整理：

```text
处理前：NeatCopy是一款Windows工具,支持LLM模式
处理后：NeatCopy 是一款 Windows 工具，支持 LLM 模式
```

NeatCopy 让这类重复操作变成一个简单流程：

```text
复制文本 -> 按下快捷键 -> 直接粘贴
```

<div align="center">
  <img src="docs/assets/格式清洗功能演示.gif" width="772" alt="NeatCopy 格式清洗功能演示">
</div>

## 🤖 大模型特色

NeatCopy 不只是文本清洗工具。接入 OpenAI 兼容接口后，可以把常用 AI 操作放进复制粘贴流程中，
无需频繁切换网页或对话窗口。

例如，将一段中文翻译为英文：

```text
复制中文 -> 按 Ctrl+Shift+C -> 在轮盘中选择「翻译」
         -> 预览面板查看结果 -> 确认后直接粘贴
```

<div align="center">
  <img src="docs/assets/轮盘翻译功能演示.gif" width="350" alt="NeatCopy Prompt 轮盘翻译功能演示">
</div>

### Prompt 轮盘：在鼠标旁快速选择任务

按下快捷键后，扇形轮盘会在鼠标位置弹出。你可以用鼠标或数字键 `1-5` 选择 Prompt：

| Prompt 示例 | 用途 |
| --- | --- |
| 翻译 | 自动识别中英文并翻译 |
| 格式清洗 | 借助大模型整理复杂段落 |
| 文字润色 | 将口语化表达改写得更自然、专业 |
| 内容摘要 | 从长文本中提炼重点 |
| 随时提问 | 将剪贴板内容作为问题快速获取回答 |

常用 Prompt 也可以通过 `Ctrl+Shift+P` 锁定。锁定后，后续处理会直接使用该模板。

### 预览面板：应用前先看一眼

按 `Ctrl+Q` 打开悬浮预览面板。大模型返回结果后，可以先检查和编辑内容，再应用到剪贴板。
即使预览面板未打开，结果也会正常写入剪贴板，保持快速粘贴体验。

### 自定义 Prompt：把 AI 变成顺手的小工具

Prompt 模板支持自由编辑。除了翻译和润色，还可以用于会议记录整理、Markdown 格式转换、
术语解释、代码注释翻译等场景。

## ✨ 功能概览

### 大模型模式

接入 OpenAI 兼容接口后，可将一次复制粘贴变成轻量 AI 工作流：

- 自定义 Prompt 模板，用于翻译、润色、摘要、格式转换等场景
- 支持 OpenAI、DeepSeek、Moonshot、本地 Ollama 等兼容接口
- 使用 Prompt 轮盘快速选择或锁定常用模板
- 在悬浮预览面板中查看并编辑处理结果
- 请求失败时保留原始剪贴板内容，避免误覆盖

### 本地规则模式

无需联网，也不需要 API Key。内置 8 条按顺序执行的文本清洗规则：

| 规则 | 作用 |
| --- | --- |
| 合并软换行 | 合并 PDF、CAJ 等来源的段落内断行 |
| 保留段落分隔 | 保留真正的空行和段落结构 |
| 合并多余空格 | 将连续空格整理为单个空格 |
| 智能全角 / 半角标点 | 根据中英文语境调整标点 |
| 中英文间距 | 自动补齐 Pangu 风格间距 |
| 清理行首尾空白 | 移除每行两侧的多余空白 |
| 保护代码块 | 跳过 Markdown 代码块，不破坏代码格式 |
| 保护列表结构 | 保留有序列表与无序列表的换行 |

### 桌面体验

| 功能 | 说明 |
| --- | --- |
| 全局快捷键 | 默认使用 `Ctrl+Shift+C` 一键处理剪贴板 |
| 双击复制触发 | 可选开启双击 `Ctrl+C` 自动清洗 |
| Prompt 轮盘 | 在鼠标位置弹出扇形菜单，支持数字键 `1-5` |
| 历史记录 | 自动保存处理记录，支持搜索、复制、删除和清空 |
| 系统托盘 | 后台常驻，不占用任务栏空间 |
| 状态提示 | 托盘图标和 Toast 显示处理中、成功或失败状态 |
| 开机启动 | 可在设置中开启 Windows 自动启动 |

## 🚀 快速开始

### 下载安装

前往 [Releases](https://github.com/StoneLL1/NeatCopy/releases/latest) 下载最新版本：

| 版本 | 适用场景 |
| --- | --- |
| `NeatCopy_Setup_v*.exe` | 推荐。通过安装向导安装，可创建开始菜单和桌面快捷方式 |
| `NeatCopy.exe` | 便携版。无需安装，下载后直接运行 |

首次运行时，Windows 可能显示 SmartScreen 提示。由于当前发布版本未进行代码签名，可点击「更多信息」后选择「仍要运行」。

### 三步使用

1. 选中文字，按 `Ctrl+C` 复制。
2. 按 `Ctrl+Shift+C` 处理剪贴板。
3. 按 `Ctrl+V` 粘贴整理后的内容。

点击托盘图标即可打开设置。在「清洗规则」页面中可切换规则模式或大模型模式。

<div align="center">
  <img src="docs/assets/设置页面.png" width="780" alt="NeatCopy 设置页面">
</div>

## 📖 使用指南

### 快捷键

| 默认快捷键 | 功能 | 备注 |
| --- | --- | --- |
| `Ctrl+Shift+C` | 处理剪贴板 | 支持自定义 |
| 双击 `Ctrl+C` | 复制后自动处理 | 默认关闭，可在设置中开启 |
| `Ctrl+Shift+P` | 打开 Prompt 轮盘 | 仅用于大模型模式 |
| `Ctrl+Q` | 打开 / 关闭预览面板 | 仅用于大模型模式 |
| `Ctrl+H` | 打开历史记录 | 支持全文搜索 |

### Prompt 轮盘

轮盘用于快速切换大模型模式下的 Prompt 模板：

- **随清洗触发**：按下清洗快捷键后先选择 Prompt，再执行处理。
- **锁定模式**：按 `Ctrl+Shift+P` 选择并锁定 Prompt，后续清洗直接使用该模板。
- **快捷选择**：鼠标点击或按数字键 `1-5` 选择，按 `Esc` 取消。

### 大模型配置

进入「设置 -> 大模型」，填写兼容服务提供方的连接信息：

| 字段 | 说明 | 示例 |
| --- | --- | --- |
| Base URL | OpenAI 兼容接口地址 | `https://api.openai.com/v1` |
| Model ID | 模型标识 | `gpt-4o-mini` |
| API Key | 服务提供方分配的密钥 | `sk-...` |
| Temperature | 输出随机性 | 默认 `0.2` |
| Timeout | 请求超时时间 | 默认 `30` 秒 |

> API Key 和设置仅保存在本机 `%APPDATA%\NeatCopy\config.json`。请根据所选服务提供方的文档填写 Base URL 和 Model ID。

### 历史记录

每次处理成功后，NeatCopy 会保存原文、结果、模式和时间戳。默认最多保留最近 `500` 条，可在设置中修改容量或关闭记录功能。

历史记录文件保存在：

```text
%APPDATA%\NeatCopy\history.json
```

<div align="center">
  <img src="docs/assets/历史记录.png" width="780" alt="NeatCopy 历史记录窗口">
</div>

## 🧩 工作方式

```mermaid
flowchart LR
    A["复制文本"] --> B["按下全局快捷键"]
    B --> C{"选择工作模式"}

    subgraph LOCAL["本地规则模式"]
        direction TB
        D["8 条清洗规则"]
        E["离线快速处理"]
        D --> E
    end

    subgraph AI["大模型模式"]
        direction TB
        F["Prompt 轮盘"]
        G["选择或锁定模板"]
        H["OpenAI 兼容接口"]
        I["悬浮预览面板"]
        F --> G --> H
        H -. "预览与编辑" .-> I
    end

    C -->|"规则模式"| D
    C -->|"大模型模式"| F
    E --> J["写回剪贴板"]
    H --> J
    I -. "确认应用" .-> J
    J --> K["直接粘贴"]
    J --> L["保存历史记录"]

    classDef entry fill:#eff6ff,stroke:#3b82f6,color:#1e3a8a,stroke-width:2px;
    classDef decision fill:#fef3c7,stroke:#f59e0b,color:#92400e,stroke-width:2px;
    classDef local fill:#ecfdf5,stroke:#10b981,color:#065f46;
    classDef ai fill:#f5f3ff,stroke:#8b5cf6,color:#5b21b6;
    classDef output fill:#fff7ed,stroke:#f97316,color:#9a3412;

    class A,B entry;
    class C decision;
    class D,E local;
    class F,G,H,I ai;
    class J,K,L output;
```

## 🛠️ 开发说明

### 环境要求

- Windows 10 / 11
- Python 3.11+

### 从源码运行

```bash
git clone https://github.com/StoneLL1/NeatCopy.git
cd NeatCopy

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python src/main.py
```

### 测试与打包

```bash
# 运行自动化测试
python -m pytest tests -v

# 使用仓库内的 PyInstaller 配置打包
pyinstaller NeatCopy.spec
```

### 项目结构

```text
NeatCopy/
├── src/
│   ├── main.py                 # 应用入口与信号编排
│   ├── clip_processor.py       # 剪贴板处理调度
│   ├── rule_engine.py          # 本地规则引擎
│   ├── llm_client.py           # OpenAI 兼容接口客户端
│   ├── hotkey_manager.py       # 全局热键与键盘钩子
│   ├── tray_manager.py         # 系统托盘与 Toast
│   ├── wheel_window.py         # Prompt 轮盘
│   ├── history_manager.py      # 历史记录管理
│   └── ui/                     # 设置、预览与历史记录窗口
├── assets/                     # 图标与资源文件
├── tests/                      # 自动化测试
├── docs/                       # 架构与开发文档
└── installer/                  # Inno Setup 安装脚本
```

更完整的技术细节见 [docs/architecture.md](docs/architecture.md)。

## 📝 更新日志

### v2.0.0

- 重构设置界面，统一视觉风格和交互细节
- 优化托盘菜单、Toast 提示和窗口表现
- 改进 Prompt 模板编辑与轮盘使用体验
- 修复轮盘绘制、动画和 QPainter 生命周期相关问题

### v1.9.x

- 新增历史记录窗口，支持搜索、复制、删除和容量控制
- 优化历史记录刷新和存储性能

### v1.8.0

- 新增 LLM 预览面板
- 支持自定义请求超时时长
- 重构 Prompt 轮盘选择器

完整版本记录请查看 [Releases](https://github.com/StoneLL1/NeatCopy/releases)。

## ❓ 常见问题

### 为什么首次运行会提示风险？

当前发布版本尚未进行代码签名，Windows SmartScreen 可能显示安全提示。建议仅从本仓库的 [Releases](https://github.com/StoneLL1/NeatCopy/releases/latest) 页面下载。

### 为什么快捷键没有响应？

请确认 NeatCopy 正在系统托盘中运行，并检查快捷键是否被其他应用占用。低级键盘钩子在部分系统环境下可能需要管理员权限。

### 大模型请求失败会覆盖剪贴板吗？

不会。只有请求成功后，NeatCopy 才会将结果写入剪贴板；失败时原始内容保持不变。

## 🤝 参与贡献

欢迎提交 [Issue](https://github.com/StoneLL1/NeatCopy/issues) 或 [Pull Request](https://github.com/StoneLL1/NeatCopy/pulls)：

1. Fork 本仓库并创建功能分支。
2. 完成功能开发与必要测试。
3. 使用清晰的提交信息描述改动。
4. 推送分支并创建 Pull Request。

---

<div align="center">

如果 NeatCopy 对你有帮助，欢迎点亮一个 [Star](https://github.com/StoneLL1/NeatCopy)。

Made with care by [StoneLL1](https://github.com/StoneLL1)

</div>
