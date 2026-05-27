# NeatCopy UI 重写设计规格

## 概述

将 NeatCopy 的 PyQt6 UI 从 Notion 暖灰风格重写为 Shadcn 锌灰+黑色 CTA 风格，基于 `NeatCopy-ui/` 目录中的 HTML/CSS 设计稿。

设计稿参考路径：`D:\Users\Aletta\Desktop\Works\NeatCopy\NeatCopy-ui\`

## 设计系统

### 调色板 (ColorPalette)

浅色主题 (LIGHT):

| Token | 值 | 用途 |
|-------|------|------|
| bg | #ffffff | 主背景、卡片背景 |
| surface_alt | #f9fafb | Segmented背景、次要表面 |
| fg | #111827 | 主文字色 |
| fg_2 | #334155 | 次要文字 |
| muted | #64748b | 辅助/禁用文字 |
| fg_soft | rgba(17,24,39,0.05) | 悬停背景 |
| border | #e5e7eb | 主边框 |
| border_strong | #cbd5e1 | 强边框、Toggle关闭色 |
| accent | #000000 | CTA按钮、选中指示 |
| accent_on | #ffffff | CTA按钮文字 |
| accent_hover | #1a1a1a | CTA悬停 |
| accent_soft | rgba(0,0,0,0.08) | 选中背景 |
| success | #16a34a | 成功状态 |
| success_soft | rgba(22,163,74,0.10) | 成功背景 |
| warn | #d97706 | 处理中/警告 |
| warn_soft | rgba(217,119,6,0.10) | 警告背景 |
| danger | #dc2626 | 错误/删除 |
| danger_soft | rgba(220,38,38,0.10) | 危险背景 |
| info | #3b82f6 | 已应用/信息 |
| info_soft | rgba(59,130,246,0.10) | 信息背景 |
| focus_ring | `0 0 0 2px bg, 0 0 0 4px accent` | 焦点环 |

深色主题 (DARK):

| Token | 值 |
|-------|------|
| bg | #18181b |
| surface_alt | #27272a |
| fg | #fafafa |
| fg_2 | #d4d4d8 |
| muted | #a1a1aa |
| fg_soft | rgba(250,250,250,0.05) |
| border | #3f3f46 |
| border_strong | #52525b |
| accent | #fafafa |
| accent_on | #18181b |
| accent_hover | #e4e4e7 |
| accent_soft | rgba(250,250,250,0.08) |
| success | #4ade80 |
| success_soft | rgba(74,222,128,0.10) |
| warn | #fbbf24 |
| warn_soft | rgba(251,191,36,0.10) |
| danger | #f87171 |
| danger_soft | rgba(248,113,113,0.10) |
| info | #60a5fa |
| info_soft | rgba(96,165,250,0.10) |
| focus_ring | `0 0 0 2px bg, 0 0 0 4px accent` |

### 字体

```python
FONT_FAMILY = '"Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI", -apple-system, sans-serif'
FONT_MONO = '"Cascadia Code", "Fira Code", Consolas, monospace'
```

字号：xs=12px, sm=14px, base=16px, lg=20px, xl=24px

### 间距

4px 网格：sp_1=4, sp_2=8, sp_3=12, sp_4=16, sp_5=20, sp_6=24, sp_8=32, sp_12=48

### 圆角

radius_sm=6px, radius_md=8px, radius_lg=12px, radius_pill=9999px

### 阴影

- shadow_sm: `0 1px 2px 0 rgba(0,0,0,0.05)`
- shadow_md: `0 2px 8px 0 rgba(0,0,0,0.08), 0 1px 2px 0 rgba(0,0,0,0.05)`
- shadow_lg: `0 4px 24px 0 rgba(0,0,0,0.12)`

### 动画

- motion_fast: 150ms
- motion_base: 200ms
- ease: `cubic-bezier(0.2, 0, 0, 1)` (Qt: QEasingCurve.OutCubic 近似)

### 深色主题策略

设计稿仅提供浅色主题的 HTML 参考。深色主题通过浅色 token 的逻辑反色推导得出。原则：
- 背景从白色→深灰(#18181b)，表面从浅灰→中灰(#27272a)
- 文字从深色→浅色，accent 从黑色→白色
- 边框从浅灰→深灰，保持对比度
- 语义色(success/warn/danger/info)使用更亮的变体以确保在深色背景上的可读性

## 自定义组件

### 1. SegmentedControl(QWidget)

分段选择器，替代主题切换等二选一/多选一场景。

- 属性：`options: list[str]`, `current_index: int`
- 信号：`selectionChanged(int)`
- 容器：surface_alt 背景，padding 3px，gap 2px，radius_sm
- 选中项：bg 背景 + shadow_sm + fg 文字色
- 未选中项：muted 文字色，悬停变 fg
- 支持 fullWidth 模式（按钮等分宽度，使用 stretch factor）
- 过渡动画：motion_fast + ease

### 2. ToggleSwitch(QWidget)

开关控件，替代 QCheckBox 在开关场景下的使用。

- 属性：`checked: bool`
- 信号：`toggled(bool)`
- 尺寸：36x20px 轨道，16x16px 圆形滑块
- 关闭色：border_strong 轨道 + 白色滑块
- 开启色：accent 轨道 + 白色滑块 translateX(16px)
- 滑块阴影：`0 1px 2px rgba(0,0,0,0.15)`
- 过渡动画：motion_fast + ease (QPropertyAnimation)
- 使用 QPainter 在 paintEvent 中绘制

### 3. Card(QFrame)

卡片容器，替代 QGroupBox。

- 样式：bg 背景 + 1px border + radius_md 圆角
- 内边距：sp_5 (20px)
- 卡片间距：margin-bottom sp_4 (16px)
- 卡片标题：sm 字号 + font-weight:600 + margin-bottom sp_4
- 卡片描述文字：xs 字号 + muted 色 + margin-top -sp_4

### 4. HotkeyBtn(QWidget)

热键录制按钮。

- 默认态：surface_alt 背景 + border 边框 + muted 文字 + mono字体
- 录制态：accent 边框 + accent 文字 + accent_soft 背景 + 脉冲动画
- 最小宽度：100px，居中文字
- 点击进入录制模式，5秒超时自动取消
- 录制中捕获按键组合，显示为 "Ctrl+Shift+C" 格式

### 5. Badge(QLabel)

标签/徽章。

- 通用：pill圆角 + xs字号 + font-weight:500
- 变体：default(surface_alt+fg), muted(surface_alt+muted), success, warn, danger
- padding: 2px sp_2

### 6. SettingRow

设置行布局模式（非独立组件，用 QHBoxLayout 实现）。

- flex 布局：左侧 label + 右侧 controls，space-between
- 行间距：padding sp_3 0
- 相邻行：border-top 1px border 分隔线
- 缩进行：padding-left sp_4
- controls 区：flex row，gap sp_3

### 7. Modal(QDialog)

模态对话框（模板编辑、轮盘管理等）。

- 遮罩层：rgba(0,0,0,0.4)
- 对话框：bg 背景 + border + radius_lg + shadow_lg
- 宽度：420px，最大高度 80vh
- 头部：sp_4 sp_5 padding + border-bottom + font-weight:600
- 内容：sp_5 padding，可滚动
- 底部：sp_3 sp_5 padding + border-top + 右对齐按钮

## 设置窗口 (SettingsWindow)

### 窗口属性

- 尺寸：780x580，可调整大小，最小 550x400
- 布局：标题栏(40px) + 主体(侧边栏+内容) + 底部栏(52px)

### 标题栏

- 高度 40px
- 左侧：标题"设置"（sm字号，font-weight:600）
- 右侧：关闭按钮 28x28px，hover 时红色背景

### 侧边栏

- 宽度：160px
- 顶部：NeatCopy 品牌名（font-weight:700，base字号）
- 5个导航项，每项带 SVG 图标 + 文字：
  1. 通用（齿轮图标）
  2. 快捷键（键盘图标）
  3. 清洗规则（文档图标）
  4. 大模型（用户图标）
  5. 关于（信息图标）
- 导航项：padding sp_2 sp_4，左侧 3px 透明边框
- 选中态：accent_soft 背景 + accent 左边框 + font-weight:500 + fg 色
- 悬停态：fg_soft 背景 + fg 色

### 页面内容

所有页面使用 QScrollArea 包裹，内容 padding sp_6。

#### 通用页

3个卡片：

**通知卡片**
- 显示清洗完成通知：SettingRow(ToggleSwitch)

**启动卡片**
- 开机自动启动：SettingRow(ToggleSwitch)

**外观卡片**
- 界面主题：SettingRow(SegmentedControl [浅色/深色])
- 预览面板主题：SettingRow(SegmentedControl [深色/浅色])

#### 快捷键页

3个卡片：

**清洗触发卡片**
- 独立热键：SettingRow(ToggleSwitch + HotkeyBtn)
- 双击 Ctrl+C：SettingRow(ToggleSwitch)
- 间隔阈值：SettingRow(Slider + 数值标签) — 缩进，双击开启时可用(opacity 0.4 + disabled)，关闭时不可交互

**功能快捷键卡片**
- 轮盘选择器：SettingRow(ToggleSwitch + HotkeyBtn)
- 随清洗热键触发时弹出轮盘：QCheckBox（缩进 sp_4）
- 预览面板：SettingRow(ToggleSwitch + HotkeyBtn)
- 历史记录：SettingRow(ToggleSwitch + HotkeyBtn)

**历史记录卡片**
- 最大条数：SettingRow(QSpinBox width=80px + "条" 单位标签)

#### 清洗规则页

2个卡片：

**清洗模式卡片**
- SegmentedControl(fullWidth) [规则模式/大模型模式]
- 选择"大模型模式"时自动跳转到"大模型"页

**规则开关卡片**
- 标题 + 描述文字("规则模式下生效")
- 8个 QCheckBox，每个带标题 + 说明文字(hint)，垂直排列

#### 大模型页

- 启用大模型模式：ToggleSwitch（页面顶部 SettingRow，font-weight:600）
- API配置卡片：
  - Base URL: 输入框(placeholder "https://api.openai.com/v1")
  - Model ID: 输入框(placeholder "gpt-4o-mini")
  - API Key: 密码框 + 显示/隐藏按钮(右侧 suffix)
  - Temperature: Slider(0-20 → 0.0-2.0) + 数值标签
  - 超时时长: QSpinBox(10-300, width=72px) + "秒"
  - 底部行: "测试连接"按钮 + "恢复默认"按钮 + 连接状态文字(内联，loading/ok/fail)
- Prompt模板卡片：
  - 模板列表：点击选中，双击编辑，右键菜单(设为默认/编辑/删除)
  - 列表项：名称 + [默认] 标签(可选) + 只读 Badge(可选)
  - 选中项：accent_soft 背景
  - 底部："+ 新增模板"按钮 + "管理轮盘"按钮
- 轮盘管理弹窗(Modal 420px)：
  - 双栏布局：左栏"可用模板"(带勾选的列表) + 右栏"轮盘模板"(带序号的列表)
  - 最多5个
  - 底部提示文字："勾选左侧模板添加到轮盘"
- 模板编辑弹窗(Modal 420px)：
  - 标题："编辑：{名称}"
  - QTextEdit (8行高)
  - 保存按钮

#### 关于页

居中布局(vertical, padding sp_12 sp_6)：
- NeatCopy 大字（xl字号, font-weight:800, letter-spacing:-0.03em）
- 版本号（mono字体, sm字号, muted色）
- 作者（sm字号, muted色）
- GitHub 链接（sm字号, fg色, hover accent, underline）
- 检查更新按钮（secondary样式）
- "如果觉得有用，欢迎 Star"（sm字号, muted色）

### 底部栏

- 高度：52px
- 内容：右对齐"保存"按钮（btn-primary 样式）
- 上边框：1px border

### 保存反馈

点击保存后，底部栏上方弹出 toast："✓ 已保存"，黑底白字，2秒消失，从下方淡入。

## 历史记录窗口 (HistoryWindow)

### 窗口属性

- 标准窗口（保留系统边框），尺寸 720x520，最小 400x300
- 可拖动、可调整大小，尺寸保存到 config

### 布局

**标题栏(36px)**：标题"历史记录" + 关闭按钮(28x28)

**工具栏**：标题"历史记录"(font-weight:600) + 搜索框(flex:1, max-width 280px, 带搜索图标) + "清空"按钮(ghost)

**双栏主体**：
- 左栏 240px：QListWidget，border-right 1px
  - 列表项：padding sp_3 sp_4，border-bottom 1px
  - 顶部：时间(mono字体, 11px, muted色) + 模式 Badge(右对齐)
  - 底部：摘要(xs字号, 30字截断)
  - 选中项：accent_soft 背景
  - 悬停：fg_soft 背景
  - 滚动条：4px 宽，border 色圆角 thumb
- 右栏(flex:1)：详情区
  - 空状态：居中图标 + "选择左侧条目查看详情"
  - 详情内容：
    - 头部：时间 + 模式 Badge
    - "原文" 标签(xs, font-weight:600, muted) + 文本框(surface_alt背景 + border + radius_sm)
    - "结果" 标签 + 文本框
    - 操作按钮行(border-top)：复制原文 + 复制结果 + stretch + 删除(危险色)

## 预览面板 (PreviewWindow)

### 窗口属性

- 无边框置顶悬浮窗，毛玻璃效果 (Windows 11 Acrylic, Win10 降级为不透明)
- 尺寸：480px 宽，最小 240x180

### 布局

**标题栏(36px)**：状态点 + 状态文字(xs, font-weight:500) + 关闭按钮(24x24, hover 白色)

**内容区(padding sp_4)**：QTextEdit，透明背景，无边框，可编辑，min-height 180px

**底部栏**：
- 左：Prompt名称(xs, muted色, "Prompt: **名称**")
- 右："应用到剪贴板"按钮(白色背景+深色文字, xs, font-weight:500, disabled 时 opacity 0.4)

### 深色主题背景

`rgba(30,30,46,0.92)` + backdrop-filter blur(16px)，边框 `rgba(255,255,255,0.08)`

### 浅色主题背景

`rgba(255,255,255,0.92)` + backdrop-filter，边框 `rgba(0,0,0,0.08)`

### 状态色

| 状态 | 点色 | 文字 |
|------|-------|------|
| 等待处理 | #64748b | 等待处理 |
| 处理中 | #d97706 (QPropertyAnimation 闪烁) | 处理中... |
| 处理完成 | #16a34a | 处理完成 |
| 处理失败 | #dc2626 | 处理失败 |
| 已应用 | #3b82f6 | 已应用 |

## 轮盘选择器 (WheelWindow)

轮盘始终为深色主题（与系统主题无关）。

样式微调对齐设计稿：
- 扇区背景：`rgba(255,255,255,0.06)`
- 悬停：`rgba(255,255,255,0.14)`
- 选中：`rgba(255,255,255,0.2)`
- 上次使用标记：`rgba(255,255,255,0.1)`
- 标签文字：`rgba(255,255,255,0.7)`，12px
- 数字：`rgba(255,255,255,0.3)`，10px
- 中心圆 ESC 文字：`rgba(255,255,255,0.4)`

## Toast 通知

5种类型，底部居中弹出（相对于触发窗口），2秒消失：
- save: accent(bg) + accent_on(文字) ✓ 已保存
- success: success(bg) + white(文字) ✓ 清洗完成
- error: danger(bg) + white(文字) ✕ 处理失败
- info: fg(bg) + bg(文字) → 已应用到剪贴板
- warn: warn(bg) + white(文字) ! 连接超时

样式：padding sp_2 sp_4，radius_sm，shadow_md，font-weight:500

动画：淡入 0.25s ease（从下方8px滑入+缩放0.96→1），淡出 0.2s

## 托盘菜单

上下文菜单样式对齐设计稿：
- 背景：bg 色
- 圆角：radius_md
- padding: sp_1 0
- 菜单项：padding sp_2 sp_3，sm字号，hover accent_soft
- 分隔线：1px border，margin sp_1 0
- 红色退出项：danger 色
- 子菜单（锁定 Prompt）：级联展开

### 菜单项

- 打开设置
- 历史记录
- 分隔线
- 当前锁定：{名称}（禁用态，muted色）
- 切换锁定 Prompt → 子菜单（✓ 无/解除锁定 + 分隔线 + 各 Prompt 名称）
- 分隔线
- 暂停/继续监听（切换项）
- 分隔线
- 退出（danger色）

## 不实现的部分

- 本地模型模块（设计稿中 model-source 的 "本地模型" 选项及相关面板）
- 底部"重置全部"按钮

## 文件变更范围

| 文件 | 变更类型 |
|------|----------|
| `src/ui/styles.py` | 重写：新调色板 + 新样式函数 |
| `src/ui/components/sidebar.py` | 重写：5项导航 + Shadcn 样式 |
| `src/ui/components/toggle_switch.py` | 新增：自定义开关控件 |
| `src/ui/components/segmented_control.py` | 新增：分段选择器控件 |
| `src/ui/components/card.py` | 新增：卡片容器控件 |
| `src/ui/settings_window.py` | 重写：5页布局 + Card/ToggleSwitch/SegmentedControl |
| `src/ui/preview_window.py` | 修改：样式对齐设计稿 + 浅色主题支持 |
| `src/ui/history_window.py` | 重写：标准窗口 + 标题栏 + 工具栏 + 双栏布局 |
| `src/wheel_window.py` | 修改：扇区样式微调 |
| `src/tray_manager.py` | 修改：托盘菜单样式 + Toast 样式 |
