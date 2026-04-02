
<div align="center">

<img width="275" height="130" src="https://github.com/user-attachments/assets/a09faa5b-7990-47b4-827e-f8574c9ae083" alt="NeatCopy Logo"/>



**让复制粘贴更智能的AI 剪贴板 让大模型无处不在**

[![Version](https://img.shields.io/badge/version-v1.9.2-blue.svg)](https://github.com/StoneLL1/NeatCopy/releases)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-yellow.svg)]()

一款常驻 Windows 系统托盘的剪贴板文本处理工具
支持规则引擎与大模型两种模式

[功能特性](#-功能特性) • [快速开始](#-快速开始) • [使用指南](#-使用指南) • [安装](#-安装) • [开发](#-从源码运行)

</div>

---



## 💡 它能解决什么问题？

从 PDF、论文、网页复制的文字，总是带着奇怪的换行和格式：

```
❌ 复制后：
随着人工智能技术的不断发
展，大语言模型在自然语言处
理领域取得了重大突破。但
是，模型依然存在幻觉问
题，需要进一步优化。

✅ Ctrl+Shift+C 之后：
随着人工智能技术的不断发展，大语言模型在自然语言处理领域取得了重大突破。但是，模型依然存在幻觉问题，需要进一步优化。
```

或者中英文混排，间距，全半角一团糟：

```
❌ 复制后：NeatCopy是一款Windows工具,支持LLM模式
✅ 之后：  NeatCopy 是一款 Windows 工具，支持 LLM 模式
```

---

## ✨ 功能特性

### 🔧 规则模式（离线，无需网络）

内置 8 条清洗规则，按顺序执行，处理延迟 < 100ms：

| 规则 | 效果 |
|------|------|
| 合并软换行 | PDF/CAJ 段落内断行合并为一行 |
| 保留段落分隔 | 真正的空行段落不被合并 |
| 合并多余空格 | `hello   world` → `hello world` |
| 智能全/半角标点 | 中文语境保留全角，英文语境转半角 |
| 中英文间距 | `AI模型` → `AI 模型`（Pangu 风格）|
| 去除行首尾空白 | 每行首尾多余空白清除 |
| 保护代码块 | ` ``` ` 包裹的代码跳过所有处理 |
| 保护列表结构 | `- item` / `1. item` 保留换行 |

### 🤖 大模型模式（需要 API Key）

接入任意 OpenAI 兼容接口，
**致力于最大限度减小你与AI交互的摩擦成本**
把**复制→粘贴**变成一个**微型 AI工作流**：


- 支持 OpenAI、DeepSeek、月之暗面、本地 Ollama 等
- 自定义 Prompt 模板，一键翻译、润色、摘要
- 扇形轮盘快速切换 Prompt
- 预览面板先看结果再应用

### 🎯 核心功能

| 功能 | 描述 |
|------|------|
| **全局热键** | `Ctrl+Shift+C` 一键清洗，支持自定义 |
| **Prompt 轮盘** | 扇形 UI 快速切换 Prompt，支持数字键 1-5 |
| **LLM 预览面板** | 查看结果、编辑后再应用，毛玻璃悬浮窗 |
| **历史记录** | 自动保存清洗记录，支持搜索、复制、删除 |
| **双击触发** | 快速双击 `Ctrl+C` 触发清洗 |
| **托盘常驻** | 后台运行，不占用任务栏 |
| **主题切换** | 深色/浅色两种主题 |

---

## 🚀 快速开始

### 安装

1. 前往 [Releases](https://github.com/StoneLL1/NeatCopy/releases) 下载最新版
2. 双击直接运行（绿色软件，无需安装）
3. 程序自动启动，系统托盘出现图标

> 首次运行可能弹出 Windows Defender SmartScreen 提示，点击「更多信息」→「仍要运行」即可。

### 基础使用

```
1. 选中文字 → Ctrl+C 复制
2. 按 Ctrl+Shift+C 清洗
3. Ctrl+V 粘贴干净的内容
```

### 选择工作模式

双击托盘图标打开设置：

| 模式 | 适用场景 |
|------|---------|
| **规则模式** | 不需要 AI、追求纯本地处理、快速响应 |
| **大模型模式** | 需要翻译、润色、摘要等 AI 能力 |

---

## 📖 使用指南

### 快捷键一览

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+Shift+C` | 清洗剪贴板（核心功能） |
| `Ctrl+C+C` | 双击 Ctrl+C 触发清洗（需在设置开启） |
| `Ctrl+Shift+P` | 弹出 Prompt 轮盘（大模型模式） |
| `Ctrl+Q` | 打开/关闭预览面板（大模型模式） |
| `Ctrl+H` | 打开历史记录窗口 |

### 托盘图标状态

| 颜色 | 状态 |
|------|------|
| ⚪ 白色 | 空闲，等待触发 |
| 🟡 黄色 | 处理中 |
| 🟢 绿色 | 处理成功 |
| 🔴 红色 | 处理失败（查看 Toast 提示） |

### 大模型配置

**设置 → 大模型** 中填入：

| 字段 | 说明 | 示例 |
|------|------|------|
| Base URL | API 地址 | `https://api.openai.com/v1` |
| Model | 模型 ID | `gpt-4o-mini` / `deepseek-chat` |
| API Key | 密钥 | `sk-...` |

**兼容服务商（仅举例部分辅助说明）：**

| 服务商 | Base URL | Model ID  |
|--------|----------|----------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| Moonshot | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| Qwen | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-flash` |

---

## 🎨 创意玩法

> 在 **设置 → 大模型 → Prompt 模板** 中写好提示词，配合轮盘一键切换。

### 📖 一键翻译
```
Prompt: 将以下中文翻译成流畅自然的英文，保持原文语气。

复制：深度学习模型在图像识别任务上取得了突破性进展。
粘贴：Deep learning models have achieved breakthrough progress in image recognition tasks.
```

### 📝 论文摘要
```
Prompt: 用 3 句话提炼以下内容的核心观点，语言简洁。

复制：[一大段论文引言]
粘贴：本文研究了 XXX 问题。提出了 YYY 方法。实验证明比基线提升 ZZZ%。
```

### ✍️ 文字润色
```
Prompt: 将以下文字改写得更正式、专业。

复制：这个方法挺好用的，比以前快多了
粘贴：该方法显著提升了处理效率，相较于原有方案具有明显优势。
```

### 💡 更多玩法

| 场景 | Prompt 示例 |
|------|------------|
| 代码注释翻译 | `将代码中的英文注释翻译为中文，保持代码不变` |
| 术语解释 | `用通俗易懂的语言解释以下专业术语` |
| 会议笔记整理 | `将杂乱的会议记录整理为结构化条目列表` |
| Markdown 格式化 | `将纯文本转换为格式规范的 Markdown` |

---

## ⚙️ 配置说明

配置文件保存在 `%APPDATA%\NeatCopy\config.json`，仅存在本地。

### 通用设置

| 配置项 | 说明 |
|--------|------|
| 工作模式 | 规则模式 / 大模型模式 |
| 独立热键 | 触发清洗的快捷键 |
| 双击 Ctrl+C | 双击触发清洗（默认关闭） |
| Toast 通知 | 处理完成后弹出通知 |
| Prompt 轮盘 | 启用/禁用、热键配置 |
| 预览面板 | 启用/禁用、主题切换 |
| 历史记录 | 启用/禁用、最大条数 |

### 历史记录

- 自动保存每次清洗的原文和结果
- 支持全文搜索（匹配原文或结果）
- 默认保留最近 500 条
- 快捷键 `Ctrl+H` 快速打开

---

## 🔧 从源码运行

```bash
# 克隆仓库
git clone https://github.com/StoneLL1/NeatCopy.git
cd NeatCopy

# 安装依赖
pip install PyQt6 pywin32 httpx langdetect pyperclip pyinstaller

# 运行
python src/main.py

# 打包
pyinstaller --onefile --windowed --name NeatCopy --add-data "assets;assets" src/main.py
```

### 项目结构

```
NeatCopy/
├── src/
│   ├── main.py              # 入口
│   ├── tray_manager.py      # 托盘管理
│   ├── hotkey_manager.py    # 全局热键
│   ├── clip_processor.py    # 剪贴板处理
│   ├── rule_engine.py       # 规则引擎
│   ├── llm_client.py        # LLM 客户端
│   ├── wheel_window.py      # Prompt 轮盘
│   ├── history_manager.py   # 历史记录
│   └── ui/
│       ├── settings_window.py
│       ├── preview_window.py
│       └── history_window.py
├── assets/                  # 图标资源
├── tests/                   # 单元测试
└── docs/                    # 文档
```

---

## 📋 更新日志

### v1.9.0
- **新增历史记录功能**：
  - 自动保存每次清洗的原文和结果
  - 双栏布局，左侧列表右侧详情
  - 全文搜索，快速复制
  - 快捷键 `Ctrl+H` 打开
- **代码优化**：
  - 修复历史窗口重复刷新问题
  - 优化容量控制算法（O(n²) → O(n)）
  - UI 简化与对齐优化

### v1.8.0
- **新增 LLM 预览面板**：
  - 独立快捷键 `Ctrl+Q` 打开/关闭
  - 预览、编辑后再应用
  - 毛玻璃背景，可拖动调整大小
- **超时时长可配置**
- **轮盘 Prompt 选择器重构**
- **新增三个内置预设模板**

### v1.1.0
- 新增 Prompt 轮盘选择器
- 新增锁定模式
- 托盘菜单显示当前锁定项

### v1.0.0
- 初始版本
- 规则引擎（8 条清洗规则）
- 大模型模式
- 系统托盘常驻

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

---

<div align="center">

**如果觉得有用，请给个 ⭐ Star 支持一下！**

Made with ❤️ by [StoneLL1](https://github.com/StoneLL1)

</div>
