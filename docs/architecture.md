# NeatCopy 技术架构文档

> 版本：v1.0 | 日期：2026-03-23

---

## 1. 整体架构

NeatCopy 采用单进程、事件驱动架构。所有模块在同一 Python 进程内运行，通过 Qt 信号/槽机制跨线程通信。

```
┌──────────────────────────────────────────────────────────────┐
│                        NeatCopy 进程                          │
│                                                              │
│   主线程（Qt Event Loop）          后台线程                   │
│   ┌─────────────────────┐         ┌──────────────────────┐  │
│   │    QApplication     │         │   HotkeyManager      │  │
│   │    TrayManager      │◄───────►│   keyboard 监听线程   │  │
│   │    SettingsWindow   │  信号    └──────────────────────┘  │
│   └────────┬────────────┘                                    │
│            │ Qt Signal                                        │
│            ▼                                                  │
│   ┌─────────────────────┐         ┌──────────────────────┐  │
│   │   ClipProcessor     │────────►│    LLMClient         │  │
│   │   (调度 + 写剪贴板)  │  asyncio│   (httpx 异步请求)   │  │
│   └────────┬────────────┘         └──────────────────────┘  │
│            │                                                  │
│            ▼                                                  │
│   ┌─────────────────────┐   ┌──────────────────────────────┐ │
│   │    RuleEngine       │   │       ConfigManager          │ │
│   │   (纯同步，无IO)    │   │   %APPDATA%\NeatCopy\        │ │
│   └─────────────────────┘   │       config.json            │ │
│                              └──────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### 线程模型

| 线程 | 内容 | 通信方式 |
|------|------|---------|
| 主线程 | Qt 事件循环，UI 渲染，剪贴板读写 | — |
| HotkeyManager 线程 | `keyboard` 库阻塞监听全局按键 | `pyqtSignal` 发射到主线程 |
| LLM 异步任务 | `asyncio` + `httpx` 网络请求 | `QThread` 包装，完成后 signal 回调 |

> **约束**：剪贴板读写（`win32clipboard`）必须在主线程执行，否则 Windows API 会报错。

---

## 2. 模块详细设计

### 2.1 main.py — 入口

```
职责：
- 创建 QApplication（设置 setQuitOnLastWindowClosed(False) 防止窗口关闭退出）
- 初始化 ConfigManager → TrayManager → HotkeyManager
- 启动 Qt 事件循环

启动流程：
main()
  ├── ConfigManager.load()
  ├── TrayManager.__init__()   # 创建托盘图标
  ├── HotkeyManager.__init__() # 注册全局热键
  └── app.exec()               # 进入事件循环
```

### 2.2 tray_manager.py — 托盘管理

```
职责：
- QSystemTrayIcon 生命周期管理
- 右键菜单（打开设置 / 暂停 / 退出）
- 图标三态切换（idle / processing / success / error）
- Windows Toast 通知（QSystemTrayIcon.showMessage）

图标状态机：
idle ──[触发热键]──► processing ──[成功]──► success ──[1.5s]──► idle
                               └──[失败]──► error   ──[1.5s]──► idle

图标文件（嵌入 PyInstaller）：
  assets/icon_idle.png      # 默认灰色
  assets/icon_processing.png # 黄色
  assets/icon_success.png   # 绿色
  assets/icon_error.png     # 红色
```

**关键信号：**
```python
# 接收来自 HotkeyManager 的触发信号
hotkey_triggered = pyqtSignal()

# 接收来自 ClipProcessor 的结果信号
process_done = pyqtSignal(bool, str)  # (success, message)
```

### 2.3 hotkey_manager.py — 全局热键

```
职责：
- 在独立线程中用 keyboard 库监听全局按键事件
- 双击 Ctrl+C 检测（基于时间戳差值）
- 独立热键（默认 Ctrl+Shift+C）检测
- 热键变更时动态注销/注册

双击 Ctrl+C 实现逻辑：
  记录上次 Ctrl+C 时间戳 last_ctrl_c_time
  当前按下 Ctrl+C：
    if now - last_ctrl_c_time <= interval_ms:
        emit hotkey_triggered  # 触发清洗
    else:
        last_ctrl_c_time = now  # 记录为第一次
        正常透传（不拦截）

注意：keyboard 库 suppress=True 会拦截按键，双击方案中
第一次 Ctrl+C 不能拦截（需正常复制），仅第二次触发时拦截。
```

### 2.4 clip_processor.py — 剪贴板处理调度

```
职责：
- 读取剪贴板文本（主线程）
- 根据 config.rules.mode 分派到 RuleEngine 或 LLMClient
- 将结果写回剪贴板（主线程）
- 向 TrayManager 发射结果信号

process() 流程：
  1. 读剪贴板 → text（为空则直接返回）
  2. if mode == "rules":
       result = RuleEngine.clean(text, config)   # 同步，< 100ms
       写回剪贴板
       emit success
  3. if mode == "llm":
       emit processing_started
       启动 LLMWorker(QThread)
       LLMWorker 完成后回调：
         if success: 写回剪贴板，emit success
         if failed:  不写剪贴板，emit error(message)

剪贴板读写（win32clipboard 优先）：
  read:  OpenClipboard → GetClipboardData(CF_UNICODETEXT) → CloseClipboard
  write: OpenClipboard → EmptyClipboard → SetClipboardData → CloseClipboard
  备用:  pyperclip.copy() / pyperclip.paste()
```

### 2.5 rule_engine.py — 规则引擎

规则严格按以下顺序执行，顺序不可变：

```python
def clean(text: str, config: dict) -> str:
    # Step 0: 分割为行列表
    lines = text.split('\n')

    # Step 1: 标记代码块行（规则7）
    code_block_lines = _mark_code_blocks(lines)

    # Step 2: 标记列表行（规则8）
    list_lines = _mark_list_lines(lines)

    protected = code_block_lines | list_lines

    # Step 3: 合并软换行（规则1）—— 跳过 protected 行
    if config['merge_soft_newline']:
        lines = _merge_soft_newlines(lines, protected)

    # Step 4: 段落重组后在段落级处理
    paragraphs = _split_paragraphs(lines)  # 按空行分段

    for para in paragraphs:
        # Step 5: 合并多余空格（规则3）
        if config['merge_spaces']:
            para = _merge_spaces(para)

        # Step 6: 智能全/半角标点（规则4）
        if config['smart_punctuation']:
            para = _smart_punctuation(para)  # 依赖 langdetect

        # Step 7: 中英文间距（规则5）
        if config['pangu_spacing']:
            para = _pangu_spacing(para)

        # Step 8: 去除行首尾空白（规则6）
        if config['trim_lines']:
            para = _trim_lines(para)

    return _join_paragraphs(paragraphs)  # 用 \n\n 重连段落
```

**规则4 智能全/半角实现：**
```
对每个标点符号，检查其前后各 N 个非空字符：
  - 若周围字符以中文为主（langdetect 或 Unicode range 判断）→ 保留/转为全角
  - 若周围字符以 ASCII 字母/数字为主 → 转为半角
  中文 Unicode 范围：\u4e00-\u9fff，\u3400-\u4dbf 等
```

### 2.6 llm_client.py — 大模型客户端

```python
class LLMClient:
    async def format(self, text: str, prompt: str, config: dict) -> str:
        """
        发送请求到 OpenAI 兼容接口。
        失败时抛出异常（由 ClipProcessor 捕获，不覆盖剪贴板）。
        """
        headers = {"Authorization": f"Bearer {config['api_key']}"}
        payload = {
            "model": config['model_id'],
            "temperature": config['temperature'],
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text}
            ]
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{config['base_url']}/chat/completions",
                json=payload, headers=headers
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

错误分类映射：
  httpx.TimeoutException     → "请求超时，请检查网络"
  httpx.HTTPStatusError 401  → "API Key 无效"
  httpx.HTTPStatusError 429  → "请求频率超限或余额不足"
  httpx.HTTPStatusError 404  → "模型 ID 不存在"
  其他                       → "请求失败：{status_code}"
```

### 2.7 config_manager.py — 配置管理

```
配置文件路径：%APPDATA%\NeatCopy\config.json

职责：
- 首次启动时写入默认配置
- 提供 get() / set() 接口，set() 立即写入磁盘
- 配置变更后通知 HotkeyManager 重新注册热键

默认配置结构见 PRD.md §4（config.json Schema）。

Prompt 模板管理：
- readonly=true 的模板不可删除，但 content 可修改
- 新增模板自动生成 UUID 作为 id
```

### 2.8 ui/settings_window.py — 设置界面

```
窗口类型：QDialog（非模态，可与托盘共存）
布局：QTabWidget，三个 Tab

Tab 1 —— 通用：
  ├── 双击 Ctrl+C：QCheckBox + QSlider（间隔 100~500ms）
  ├── 独立热键：QCheckBox + 按键录制 QPushButton（捕获 keyPressEvent）
  ├── 开机自启：QCheckBox（写 HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run）
  └── Toast 通知：QCheckBox

Tab 2 —— 清洗规则：
  ├── 模式选择：QRadioButton（规则模式 / 大模型模式）
  └── 8条规则：QCheckBox × 8（含 QToolTip 说明）

Tab 3 —— 大模型：
  ├── 总开关：QCheckBox
  ├── Base URL：QLineEdit
  ├── API Key：QLineEdit（echoMode=Password）+ 显示切换按钮
  ├── Model ID：QLineEdit
  ├── Temperature：QSlider（0~20，显示除以10的值）
  ├── Prompt 模板列表：QListWidget
  │     右键菜单：新增 / 编辑 / 删除 / 设为默认
  │     双击编辑：QDialog + QTextEdit
  └── Test Connection：QPushButton → 异步发送测试请求 → QMessageBox 结果

保存逻辑：
  每个控件 valueChanged/stateChanged/textChanged 信号连接到 _on_change()
  _on_change() 调用 ConfigManager.set() 实时写入
  底部显示"已保存 ✓"状态标签（1.5s 后消失）
```

---

## 3. 数据流时序图

### 3.1 规则模式触发流程

```
用户按 Ctrl+Shift+C
    │
    ▼
HotkeyManager（后台线程）
    │ emit hotkey_triggered (pyqtSignal)
    ▼
ClipProcessor.process()（主线程）
    │ win32clipboard.GetClipboardData()
    │ text = "乱排版文本..."
    │
    ├── RuleEngine.clean(text, config)
    │     ├── 标记代码块/列表
    │     ├── 合并软换行
    │     ├── 合并空格
    │     ├── 全/半角标点
    │     ├── 中英文间距
    │     └── return cleaned_text
    │
    │ win32clipboard.SetClipboardData(cleaned_text)
    │
    ▼
TrayManager（主线程）
    ├── 图标变绿（1.5s）
    └── showMessage("已清洗，可直接粘贴")  [若开启]
```

### 3.2 大模型模式触发流程

```
用户按 Ctrl+Shift+C
    │
    ▼
ClipProcessor.process()（主线程）
    │ 读剪贴板 → original_text
    │ 保存 original_text（备份）
    │
    ├── emit processing_started
    │     └── TrayManager 图标变黄
    │
    ├── 启动 LLMWorker(QThread)
    │     └── asyncio.run(LLMClient.format(...))
    │           └── httpx POST /chat/completions（最长30s）
    │
    ├── [成功] LLMWorker.finished(result)
    │     ├── win32clipboard.SetClipboardData(result)
    │     └── emit success → 图标变绿 + Toast
    │
    └── [失败] LLMWorker.error(message)
          ├── 剪贴板保持 original_text 不变
          └── emit error → 图标变红 + Toast("请求失败：...")
```

---

## 4. 关键技术决策

### 4.1 为什么用 keyboard 库而不是 Windows RegisterHotKey

`RegisterHotKey` 只支持 Modifier+Key 组合，无法实现双击 Ctrl+C 检测（需要时间戳逻辑）。`keyboard` 库基于底层钩子，可监听任意按键序列，更灵活。

**已知限制**：部分安全软件可能阻止 `keyboard` 库安装全局钩子，需要在文档中说明。

### 4.2 为什么 LLM 请求用 QThread 包装而不是直接 asyncio

PyQt6 的事件循环与 asyncio 事件循环不兼容，直接在主线程跑 asyncio 会阻塞 UI。用 `QThread` 包装后在子线程运行独立的 asyncio event loop，通过 signal 回调主线程，是最简洁的方案。

### 4.3 剪贴板写入时机

LLM 模式下，仅在收到成功结果后才写入剪贴板。网络请求期间剪贴板内容始终是用户复制的原始文本，不会出现"写了一半"的中间状态。

### 4.4 langdetect 的使用范围

`langdetect` 仅在规则4（智能全/半角）中使用，对段落级文本进行语言判断。对于混合中英文段落，按字符级上下文（前后各5个字符）做局部判断，不依赖整段 langdetect 结果。

---

## 5. 打包与发布

```bash
# 打包命令
pyinstaller \
  --onefile \
  --windowed \
  --name NeatCopy \
  --icon assets/icon_idle.ico \
  --add-data "assets;assets" \
  src/main.py

# 输出
dist/NeatCopy.exe  # 单文件，约 40~60MB
```

**已知打包问题：**
- `langdetect` 需要显式加入 `--hidden-import langdetect`
- `win32clipboard` 的 DLL 需要 `--collect-all pywin32`
- PyInstaller 生成的 exe 可能被杀软误报（无代码签名），建议用户添加白名单

---

## 6. 目录结构

```
NeatCopy/
├── src/
│   ├── main.py
│   ├── tray_manager.py
│   ├── hotkey_manager.py
│   ├── clip_processor.py
│   ├── rule_engine.py
│   ├── llm_client.py
│   ├── config_manager.py
│   └── ui/
│       └── settings_window.py
├── assets/
│   ├── icon_idle.png / .ico
│   ├── icon_processing.png
│   ├── icon_success.png
│   └── icon_error.png
├── tests/
│   ├── test_rule_engine.py
│   └── test_config_manager.py
├── docs/
│   ├── architecture.md     # 本文档
│   └── dev-standards.md
├── PRD.md
├── CLAUDE.md
└── requirements.txt
```
