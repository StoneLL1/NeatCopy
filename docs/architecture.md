# NeatCopy 技术架构文档

> 版本：v1.9.0 | 日期：2026-03-31

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
│   │    TrayManager      │◄───────►│   Win32 RegisterHotKey│  │
│   │    SettingsWindow   │  信号    └──────────────────────┘  │
│   │    PreviewWindow    │                                    │
│   └────────┬────────────┘                                    │
│            │ Qt Signal                                        │
│            ▼                                                  │
│   ┌─────────────────────┐         ┌──────────────────────┐  │
│   │   ClipProcessor     │────────►│    LLMClient         │  │
│   │   (调度 + 写剪贴板)  │  asyncio│   (httpx 异步请求)   │  │
│   │   + 预览信号发射     │         └──────────────────────┘  │
│   └────────┬────────────┘                                    │
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
| HotkeyManager | Win32 `RegisterHotKey` API + `WM_HOTKEY` 消息过滤 | `pyqtSignal` 发射到主线程 |
| LLM 异步任务 | `asyncio` + `httpx` 网络请求 | `QThread` 包装，完成后 signal 回调 |

> **约束**：剪贴板读写（`win32clipboard`）必须在主线程执行，否则 Windows API 会报错。

---

## 2. 模块详细设计

### 2.1 main.py — 入口

```
职责：
- 创建 QApplication（设置 setQuitOnLastWindowClosed(False) 防止窗口关闭退出）
- 初始化 ConfigManager → TrayManager → HotkeyManager → ClipProcessor → WheelWindow → PreviewWindow
- 连接信号/槽
- 启动 Qt 事件循环

启动流程：
main()
  ├── ConfigManager.load()
  ├── sync_from_config()           # 同步开机自启动注册表状态
  ├── TrayManager.__init__()       # 创建托盘图标
  ├── HotkeyManager.__init__()     # 注册全局热键
  ├── ClipProcessor.__init__()     # 剪贴板处理调度器
  ├── WheelWindow.__init__()       # 轮盘选择器
  ├── PreviewWindow.__init__()     # 预览面板
  ├── 连接信号/槽
  │     ├── hotkey.hotkey_triggered → on_hotkey_triggered (轮盘逻辑)
  │     ├── hotkey.wheel_hotkey_triggered → on_wheel_hotkey_triggered
  │     ├── hotkey.preview_hotkey_triggered → preview.toggle_visibility
  │     ├── processor.process_done → on_process_done
  │     ├── processor.preview_ready → preview.update_result
  │     └── ...
  └── app.exec()                   # 进入事件循环
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
- 使用 Win32 RegisterHotKey API 注册全局热键
- 支持三种热键：清洗热键、轮盘热键、预览热键
- 通过 QAbstractNativeEventFilter 过滤 WM_HOTKEY 消息
- 双击 Ctrl+C 检测通过 WH_KEYBOARD_LL 低级键盘钩子实现
- 热键变更时动态注销/注册

热键 ID 定义：
  HOTKEY_ID_CUSTOM = 1     # 清洗热键（Ctrl+Shift+C）
  HOTKEY_ID_WHEEL = 2      # 轮盘热键（Ctrl+Shift+P）
  HOTKEY_ID_PREVIEW = 3    # 预览热键（Ctrl+Q）

实现逻辑：
  _HotkeyFilter(QAbstractNativeEventFilter):
    nativeEventFilter(eventType, message):
      if eventType == "windows_generic_MSG":
        msg = MSG.from_address(int(message))
        if msg.message == WM_HOTKEY:
          if msg.wParam == HOTKEY_ID_CUSTOM:
            _on_hotkey()  # 注入 Ctrl+C 模拟复制 + 延迟触发
          elif msg.wParam == HOTKEY_ID_WHEEL:
            emit wheel_hotkey_triggered
          elif msg.wParam == HOTKEY_ID_PREVIEW:
            emit preview_hotkey_triggered
          return True, 0
      return False, 0

双击 Ctrl+C（WH_KEYBOARD_LL）：
  - 默认关闭，可在设置中启用
  - 检测两次 Ctrl+C 间隔 ≤ 300ms 触发清洗
  - 跳过注入事件（LLKHF_INJECTED 标志），避免自触发

注意：RegisterHotKey 只支持 Modifier+Key 组合（Ctrl/Shift/Alt + 普通键）。
```

### 2.4 clip_processor.py — 剪贴板处理调度

```
职责：
- 读取剪贴板文本（主线程）
- 根据 config.rules.mode 分派到 RuleEngine 或 LLMClient
- 将结果写回剪贴板（主线程）
- 向 TrayManager 发射结果信号
- [LLM模式] 向 PreviewWindow 发射预览信号

信号定义：
  succeeded = pyqtSignal(str)         # 处理成功，携带结果文本
  failed = pyqtSignal(str)            # 处理失败，携带错误信息
  processing_started = pyqtSignal()   # 开始处理（用于图标变色）
  preview_ready = pyqtSignal(str, str) # LLM结果 + prompt名称
  preview_failed = pyqtSignal(str)    # LLM失败信息

process() 流程：
  1. 读剪贴板 → text（为空则直接返回）
  2. if mode == "rules":
       result = RuleEngine.clean(text, config)   # 同步，< 100ms
       写回剪贴板
       emit succeeded(result)
  3. if mode == "llm":
       emit processing_started
       启动 LLMWorker(QThread)
       LLMWorker 完成后回调：
         if success:
           写回剪贴板
           emit succeeded(result)
           emit preview_ready(result, prompt_name)  # 发送到预览面板
         if failed:
           不写剪贴板（保持原文）
           emit failed(error_msg)
           emit preview_failed(error_msg)

剪贴板读写（win32clipboard 优先）：
  read:  OpenClipboard → GetClipboardData(CF_UNICODETEXT) → CloseClipboard
  write: OpenClipboard → EmptyClipboard → SetClipboardData → CloseClipboard
  备用:  pyperclip.copy() / pyperclip.paste()
```

### 2.5 ui/preview_window.py — LLM 预览面板（新增）

```
职责：
- 显示 LLM 处理结果，支持用户编辑
- 提供"应用到剪贴板"按钮手动确认写入
- 置顶悬浮窗，毛玻璃背景，可拖动可调整大小
- 支持深色/浅色主题切换

窗口属性：
  WindowFlags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
  背景毛玻璃：Windows 11 DWM API (DwmExtendFrameIntoClientArea)

交互实现：
  拖动：整个窗口区域（除文本编辑框）可拖动
  Resize：6px 边框区域检测，支持8方向调整
  关闭：右上角关闭按钮 / 再次按快捷键 toggle

状态指示（顶部状态栏）：
  等待处理：蓝色圆点 ● + "等待处理"
  处理中...：黄色圆点 ● + "处理中..."
  处理完成：绿色圆点 ● + "处理完成"
  处理失败：红色圆点 ● + "处理失败"

信号连接：
  ClipProcessor.preview_ready → _on_preview_ready(text, prompt_name)
  ClipProcessor.preview_failed → _on_preview_failed(error_msg)
  HotkeyManager.preview_hotkey_triggered → toggle 显示/隐藏
```

### 2.6 wheel_window.py — Prompt 轮盘选择器

```
职责：
- 扇形轮盘 UI，围绕鼠标位置弹出
- 支持鼠标点击 + 数字键 1-5 选中
- ESC / 点击外部关闭
- 淡入淡出动画

窗口属性：
  WindowFlags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
  WA_TranslucentBackground: 透明背景
  固定尺寸: 268x268

外部点击检测：
  使用 WH_MOUSE_LL 低级鼠标钩子（不依赖 Qt 焦点）
  点击在轮盘外部 → QTimer.singleShot(0) 延迟关闭

关键实现：
  show_at(pos, prompts, callback, last_prompt_id):
    将轮盘中心放在鼠标位置，确保不超出屏幕
    安装 WH_MOUSE_LL 钩子检测外部点击
    启动淡入动画

  _index_at(x, y) -> int:
    计算鼠标位置落在哪个扇区（角度计算）

  paintEvent():
    绘制扇形区域、悬停高亮、上次使用标记、数字标签、中心圆
```

### 2.7 rule_engine.py — 规则引擎

规则严格按以下顺序执行，顺序不可变：

```python
def clean(text: str, config: dict) -> str:
    # Step 1: 提取代码块（规则7）→ 用占位符替换
    code_blocks = {}
    if config.get('protect_code_blocks', True):
        text = _extract_code_blocks(text, code_blocks)

    lines = text.split('\n')

    # Step 2: 标记列表行（规则8）
    protected = set()
    if config.get('protect_lists', True):
        protected |= _find_list_lines(lines)

    # Step 3: 合并软换行（规则1）—— 跳过 protected 行
    if config.get('merge_soft_newline', True):
        lines = _merge_soft_newlines(lines, protected)

    text = '\n'.join(lines)

    # Step 4: 多余空行折叠为双换行（规则2）
    if config.get('keep_hard_newline', True):
        text = re.sub(r'\n{3,}', '\n\n', text)

    # 按段落分隔后逐段处理
    paragraphs = text.split('\n\n')
    for para in paragraphs:
        # 含占位符的段落跳过所有清洗
        if _PLACEHOLDER_PREFIX in para:
            continue
        # Step 5: 合并多余空格（规则3）
        if config.get('merge_spaces', True):
            para = _merge_spaces(para)
        # Step 6: 智能全/半角标点（规则4）
        if config.get('smart_punctuation', True):
            para = _smart_punctuation(para)
        # Step 7: 中英文间距（规则5）
        if config.get('pangu_spacing', True):
            para = _pangu_spacing(para)
        # Step 8: 去除行首尾空白（规则6）
        if config.get('trim_lines', True):
            para = _trim_lines(para)

    text = '\n\n'.join(paragraphs)

    # 还原代码块
    for placeholder, original in code_blocks.items():
        text = text.replace(placeholder, original)

    return text
```

**规则4 智能全/半角实现：**
```
对每个标点符号，检查其前后各 5 个字符：
  - 若周围字符以中文为主（Unicode range 判断）→ 保留/转为全角
  - 若周围字符以 ASCII 字母/数字为主 → 转为半角
  中文 Unicode 范围：\u4e00-\u9fff，\u3400-\u4dbf 等
  注意：跳过列表编号中的点（如 "1. " 不转换）
```

### 2.8 llm_client.py — 大模型客户端

```python
class LLMClient:
    async def format(self, text: str, prompt: str, config: dict) -> str:
        """
        异步发送请求到 OpenAI 兼容接口（供 test_connection 使用）。
        实际清洗任务由 ClipProcessor._LLMWorker 在 QThread 中同步调用。
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
        timeout = float(config.get('timeout', 30))
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{config['base_url']}/chat/completions",
                json=payload, headers=headers
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

# ClipProcessor._LLMWorker 在 QThread 中使用同步 httpx.Client：
class _LLMWorker(QThread):
    def run(self):
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            self.succeeded.emit(content)

错误分类映射：
  httpx.TimeoutException     → "请求超时，请检查网络"
  httpx.HTTPStatusError 401  → "API Key 无效"
  httpx.HTTPStatusError 429  → "请求频率超限或余额不足"
  httpx.HTTPStatusError 404  → "模型 ID 不存在"
  httpx.ConnectError         → "网络连接失败"
  其他                       → "请求失败：{status_code}"
```

### 2.9 config_manager.py — 配置管理

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

### 2.10 ui/settings_window.py — 设置界面

```
窗口类型：QDialog（非模态，可与托盘共存）
布局：侧边栏导航 + QStackedWidget 内容区 + 底部操作栏

Tab 1 —— 通用：
  ├── 通知：Toast 通知开关
  ├── 启动：开机自启开关
  ├── 界面主题：浅色/深色切换
  ├── 独立热键：QCheckBox + 按键录制 QPushButton
  ├── 双击 Ctrl+C：QCheckBox + QSlider（间隔 100~500ms）
  ├── 轮盘 Prompt 选择器：启用/随清洗触发/切换热键
  └── 预览面板：启用/快捷键/主题切换

Tab 2 —— 清洗规则：
  ├── 模式选择：QCheckBox（规则模式 / 大模型模式，互斥）
  └── 8条规则：QCheckBox × 8（含 QToolTip 说明）

Tab 3 —— 大模型：
  ├── 总开关：QCheckBox
  ├── API 配置：Base URL、Model ID、API Key（密码框）、Temperature 滑块、超时时长 SpinBox
  ├── 测试连接 + 恢复默认按钮
  ├── Prompt 模板列表：QListWidget（右键菜单：新增/编辑/删除/设为默认）
  └── 轮盘 Prompt 选择：左右两栏设计（左栏可用模板勾选，右栏轮盘模板带序号，最多5个）

Tab 4 —— 关于：
  ├── 版本信息 + 检查更新按钮
  ├── 作者
  └── 项目地址（GitHub 链接）

保存逻辑：
  每个控件变化时调用 _mark(key, value) 存入 _pending 字典
  点击"保存"按钮时调用 _do_save() 批量写入 ConfigManager
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

### 4.1 为什么用 Win32 API 而不是 keyboard 库

`RegisterHotKey` 通过 Windows 消息机制在 Qt 主线程接收热键事件，与 PyQt6 事件循环无缝集成，无需额外线程。

**双击 Ctrl+C 检测**：通过 `WH_KEYBOARD_LL` 低级键盘钩子实现时间戳逻辑，默认关闭（可能与部分应用冲突）。

**优势**：
- 不依赖第三方 Python 库
- 与 Qt 事件循环无缝集成
- 热键触发时自动注入 Ctrl+C 模拟复制（解决部分应用复制延迟问题）

**已知限制**：部分安全软件可能阻止低级钩子，需要以管理员身份运行。

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
│   ├── wheel_window.py        # Prompt 轮盘选择器
│   ├── history_manager.py     # 历史记录数据管理
│   ├── autostart_manager.py   # 开机自启动管理
│   ├── assets.py              # 共享资源路径
│   ├── version.py             # 版本号定义
│   ├── config_manager.py
│   └── ui/
│       ├── settings_window.py
│       ├── preview_window.py  # LLM 预览面板
│       ├── history_window.py  # 历史记录窗口
│       ├── styles.py          # 主题样式定义
│       └── components/
│           ├── sidebar.py     # 侧边栏导航组件
│           └── icon_helper.py # 图标辅助工具
├── assets/
│   ├── icon_idle.png / .ico
│   ├── icon_processing.png
│   ├── icon_success.png
│   └── icon_error.png
├── tests/
│   ├── test_rule_engine.py
│   ├── test_config_manager.py
│   └── test_history_manager.py
├── docs/
│   ├── architecture.md     # 本文档
│   └── dev-standards.md
├── PRD.md
├── CLAUDE.md
└── requirements.txt
```

---

## 7. 历史记录模块

### 7.1 history_manager.py — 数据管理

```
职责：
- 管理历史记录的增删查操作
- 读写 history.json 文件
- 容量控制（超出上限时保留最新条目）

数据结构：
  history.json:
    { "entries": [
      {
        "id": "uuid",
        "timestamp": "2026-03-31T12:30:45",
        "mode": "rules" | "llm",
        "prompt_name": "格式清洗" | null,
        "original": "原文内容",
        "result": "清洗结果"
      }, ...
    ] }

关键方法：
  add(original, result, mode, prompt_name) -> bool
    # 添加记录，超出容量时切片保留最新条目

  get_all() -> list[dict]
    # 返回所有记录（按时间倒序）

  delete(entry_id) -> bool
    # 根据 ID 删除指定条目

  clear() -> bool
    # 清空所有历史

  search(keyword) -> list[dict]
    # 全文搜索（匹配原文或结果）

  get_by_id(entry_id) -> dict | None
    # 根据 ID 获取单条记录

性能优化：
  - 容量控制使用切片赋值 O(n) 而非循环 pop(0) O(n²)
```

### 7.2 ui/history_window.py — 历史记录窗口

```
职责：
- 显示历史记录列表和详情（双栏布局）
- 支持搜索、复制原文/结果、删除、清空
- 支持深色/浅色主题切换

窗口属性：
  WindowFlags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
  背景毛玻璃：Windows 11 DWM API (DwmSetWindowAttribute)
  最小尺寸：400x300

UI 结构：
  ┌─────────────────────────────────────────┐
  │ 历史记录                          关闭 │
  ├─────────────────────────────────────────┤
  │ [搜索...]                      [清空] │
  ├──────────────┬──────────────────────────┤
  │ 12:30 [规则] │ 03-31 12:30    规则      │
  │ 原文摘要...  │                          │
  │              │ 原文                      │
  │ 12:25 [LLM]  │ ┌──────────────────────┐ │
  │ 原文摘要...  │ │ 原文内容...          │ │
  │              │ └──────────────────────┘ │
  │              │ 结果                      │
  │              │ ┌──────────────────────┐ │
  │              │ │ 清洗结果...          │ │
  │              │ └──────────────────────┘ │
  │              │ [复制原文] [复制结果] 删除│
  └──────────────┴──────────────────────────┘

关键信号：
  copy_to_clipboard = pyqtSignal(str)  # 请求写入剪贴板

事件处理：
  showEvent(): 刷新主题和列表
  resizeEvent(): 延迟保存窗口尺寸到配置
  mousePressEvent/MoveEvent/ReleaseEvent: 窗口拖动

性能优化：
  - toggle_visibility() 不调用 _refresh_list()，避免与 showEvent 重复刷新
  - datetime 导入放在模块顶部，避免函数内重复导入
```
