<img width="556" height="244" alt="image" src="https://github.com/user-attachments/assets/a09faa5b-7990-47b4-827e-f8574c9ae083" />

# NeatCopy | 让复制粘贴更轻松

**复制文本或图片，按下快捷键，通过轮盘选择粘贴方式。**

NeatCopy 常驻 macOS 菜单栏。按 `Cmd+V` 会弹出粘贴轮盘，你可以在 `历史记录 / 直接粘贴 / 规则清洗 / 大模型处理` 之间选择；按 `Cmd+Option+V` 或快速点击 `Cmd+C+C` 也可以直接走处理流程。复制图片时，NeatCopy 会保留图片并写入历史记录，文本清洗和大模型处理会自动置灰。

---

## 它能解决什么问题？

从 PDF、论文、网页复制的文字，总是带着奇怪的换行和格式：

```
❌ 复制后：
随着人工智能技术的不断发
展，大语言模型在自然语言处
理领域取得了重大突破。但
是，模型依然存在幻觉问
题，需要进一步优化。

✅ Cmd+Option+V 之后：
随着人工智能技术的不断发展，大语言模型在自然语言处理领域取得了重大突破。但是，模型依然存在幻觉问题，需要进一步优化。
```

或者中英文混排，间距一团糟：

```
❌ 复制后：
NeatCopy是一款macOS工具,支持LLM模式

✅ Cmd+Option+V 之后：
NeatCopy 是一款 macOS 工具，支持 LLM 模式
```

---

## 两种工作模式

### 🔧 规则模式（离线，无需网络）

内置 8 条清洗规则，按顺序执行：

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

接入任意 OpenAI 兼容接口（OpenAI、DeepSeek、本地 Ollama……），配合自定义 Prompt，**把复制→粘贴变成一个微型 AI 工作流**。

---

## 大模型模式创意玩法 🎨

> 在设置 → 大模型 → Prompt 模板中写好提示词，之后每次复制文字按 `Cmd+Option+V`，粘贴出来的就是 AI 处理后的结果。

### 📖 一键翻译
**Prompt：** `将以下中文翻译成流畅自然的英文，保持原文语气。`

```
复制：深度学习模型在图像识别任务上取得了突破性进展。
粘贴：Deep learning models have achieved breakthrough progress in image recognition tasks.
```

### 📝 论文摘要
**Prompt：** `用 3 句话提炼以下内容的核心观点，语言简洁。`

```
复制：[一大段论文引言]
粘贴：本文研究了 XXX 问题。提出了 YYY 方法。实验证明比基线提升 ZZZ%。
```

### ✍️ 文字润色
**Prompt：** `将以下文字改写得更正式、专业，适合正式场合使用。`

```
复制：这个方法挺好用的，比以前快多了
粘贴：该方法显著提升了处理效率，相较于原有方案具有明显优势。
```

### 💻 代码注释翻译
**Prompt：** `将以下代码中的英文注释全部翻译为中文，保持代码不变。`

### 🧠 专业术语解释
**Prompt：** `用通俗易懂的语言解释以下专业术语或段落，面向非专业读者。`

### 📋 会议笔记整理
**Prompt：** `将以下杂乱的会议记录整理为结构化的条目列表，突出行动项。`

### 🌐 Markdown 格式化
**Prompt：** `将以下纯文本转换为格式规范的 Markdown，合理使用标题、列表和加粗。`

> 💡 **提示**：可以保存多个 Prompt 模板，在设置界面随时切换。

---

## 安装

1. 前往 Releases 下载 `NeatCopy-macOS.zip`
2. 解压得到 `NeatCopy.app`
3. 拖动到 `/Applications`
4. 首次运行时按系统提示授予权限
5. 在 `系统设置 -> 隐私与安全性` 中为 App 打开：
   - 辅助功能
   - 输入监控（部分系统版本需要）

说明：
- 新版启动时，NeatCopy 会自动检测缺失权限并尝试拉起系统授权或对应设置页。
- macOS 不允许应用自行完成授权勾选，最终仍需你在系统设置中确认。
- 若希望升级后尽量不要反复丢权限，建议始终把同一个 `NeatCopy.app` 放在固定位置，优先使用稳定签名的发布版。

---

## 使用方法

| 操作 | 说明 |
|------|------|
| `Cmd+V` | 弹出粘贴轮盘，可选历史记录、直接粘贴、规则清洗、大模型处理 |
| `Cmd+Option+V` | 选中文字后按下，自动复制并处理，可直接粘贴 |
| 双击 `Cmd+C` | 可选触发方式，默认关闭 |
| 点击菜单栏图标 | 打开菜单，可进入设置或立即处理剪贴板 |
| 菜单栏状态提示 | 空闲 / 处理中 / 成功 / 出错 |

历史记录最多保留 10 条，轮盘中仍只展示 5 个槽位；历史条目支持手动删除。

---

## 配置说明

设置保存在 `~/Library/Application Support/NeatCopy/config.json`，**仅存在本地，不会上传**。

大模型模式需要在 **设置 → 大模型** 中填入：
- Base URL（如 `https://api.openai.com/v1`）
- Model ID（如 `gpt-4o-mini`）
- API Key

---

## 系统要求

- macOS 13+
- Release 版无需 Python 环境，开箱即用

---

## 项目结构

- `src/main.py`：应用入口
- `src/neatcopy/app.py`：应用启动与依赖装配
- `src/neatcopy/application/`：处理流程、历史记录、设置更新
- `src/neatcopy/domain/`：纯规则逻辑
- `src/neatcopy/infrastructure/`：剪贴板、热键、配置、权限、启动项、LLM 接口
- `src/neatcopy/presentation/`：托盘与界面控制器
- `src/neatcopy/presentation/ui/`：PyQt 界面组件
- `tests/`：回归测试
- `assets/`：运行时资源与打包素材

更多结构说明见 `docs/architecture.md`。

---

## 开发与打包

源码运行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python src/main.py
```

构建发布版：

```bash
python -m PyInstaller NeatCopy.spec --clean
```

产物位置：

```text
dist/NeatCopy.app
```

---

## License

MIT
