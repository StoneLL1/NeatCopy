# 轮盘 Prompt 快捷选择器设计文档

**日期**: 2026-03-28
**项目**: NeatCopy
**功能**: LLM Prompt 快捷选择轮盘

## 功能定位

复用现有 `prompts` 配置，提供扇形轮盘快速选择入口，支持两种使用模式。

## 核心交互

### 模式1：随清洗触发

| 触发方式 | 行为 |
|----------|------|
| Ctrl+C+C | 弹出轮盘 → 选择 Prompt → 执行清洗 |
| Ctrl+Shift+C | 弹出轮盘 → 选择 Prompt → 执行清洗 |

- 记住上次选择的 Prompt，下次默认选中
- 用户可在设置中关闭此模式（仍用默认 Prompt）

### 模式2：锁定模式

| 触发方式 | 行为 |
|----------|------|
| 独立热键（默认 Ctrl+Shift+P，可配置） | 弹出轮盘 → 选择后锁定 → 后续清洗直接使用 |

- 锁定后所有清洗操作使用该 Prompt，直到重新切换
- 锁定状态在托盘菜单中标记（✓ 或高亮）

## 轮盘设计

### 视觉形态

- **扇形/圆形轮盘**：围绕鼠标位置呈扇形展开
- **最多显示 5 个 Prompt**：用户可在设置配置显示哪些
- **动画效果**：弹出/关闭有淡入淡出或展开收起动画

### 交互方式

| 操作 | 行为 |
|------|------|
| 鼠标点击 | 移动到目标选项，点击确认 |
| 数字键 1-5 | 直接选择对应位置的 Prompt |
| ESC 键 | 关闭轮盘，不执行任何操作 |
| 点击外部 | 关闭轮盘，不执行任何操作 |

## 状态显示

| 状态 | 显示方式 |
|------|----------|
| 锁定的 Prompt | 托盘菜单中标记 ✓ 或高亮 |
| 上次选择的 Prompt | 轮盘弹出时默认选中（仅随清洗模式） |

## 设置界面

新增"轮盘设置"区域，包含以下配置项：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| 启用轮盘 | 开关 | true | 整体启用/禁用轮盘功能 |
| 随清洗触发 | 开关 | true | 是否在 Ctrl+C+C 时弹出轮盘 |
| 独立切换热键 | 文本 | Ctrl+Shift+P | 锁定模式的快捷键，可自定义 |
| 可见 Prompt 列表 | 多选 | 全部 | 选择轮盘中显示哪些 Prompt（最多5个） |

### Prompt 可见性配置

- 每个 Prompt 条目新增 `visible_in_wheel` 字段（boolean）
- 设置界面提供多选列表，用户勾选要显示的 Prompt
- readonly Prompt 不可删除但可配置可见性

## 边缘情况处理

| 场景 | 处理方式 |
|------|----------|
| 仅 1 个可见 Prompt | 跳过轮盘，直接执行该 Prompt |
| 没有可见 Prompt | 静默不处理，剪贴板保持原样 |
| 轮盘弹出期间用户操作其他窗口 | 轮盘自动关闭 |

## 配置文件变更

`config.json` 新增字段：

```json
{
  "wheel": {
    "enabled": true,
    "trigger_with_clean": true,
    "switch_hotkey": "ctrl+shift+p",
    "max_visible": 5
  },
  "prompts": [
    {
      "name": "翻译",
      "prompt": "...",
      "readonly": true,
      "visible_in_wheel": true
    }
  ]
}
```

## 模块设计

### 新增模块

```
src/
└── wheel_window.py    # 扇形轮盘窗口（PyQt6 QWidget）
```

### 修改模块

| 模块 | 变更 |
|------|------|
| `config_manager.py` | 新增 `wheel` 配置读写，Prompt 新增 `visible_in_wheel` |
| `hotkey_manager.py` | 新增独立切换热键注册 |
| `clip_processor.py` | 判断轮盘模式，触发轮盘或使用锁定 Prompt |
| `tray_manager.py` | 托盘菜单标记锁定状态，新增轮盘相关菜单项 |
| `ui/settings_window.py` | 新增轮盘设置 Tab 或区域 |

### 数据流

```
用户触发热键
    → HotkeyManager 捕获
    → 判断热键类型：
        [Ctrl+C+C / Ctrl+Shift+C] → 检查 wheel.trigger_with_clean
            → enabled 且有多个可见 Prompt → WheelWindow.show()
            → 选择后 → ClipProcessor.process(prompt_index)
            → disabled 或仅1个 → ClipProcessor.process(default)
        [独立切换热键] → WheelWindow.show()
            → 选择后 → 设置锁定状态 → TrayManager 更新标记
```

## 技术要点

### 扇形轮盘实现

- 使用 PyQt6 `QWidget` 自绘，无边框、透明背景
- 计算扇形角度：每个选项占 360°/n（n ≤ 5）
- 鼠标位置检测：根据角度判断当前悬停选项
- 动画：使用 `QPropertyAnimation` 实现淡入淡出/展开

### 热键冲突处理

- 独立切换热键需要避免与系统/其他应用冲突
- 提供热键输入框，用户可自定义
- 检测热键是否已被占用（keyboard 库支持）

### 性能要求

- 轮盘弹出延迟 < 100ms
- 动画流畅（60fps）
- 不影响原有清洗性能

## 未来扩展（暂不实现）

- 轮盘样式选择（列表/网格）
- 轮盘位置记忆
- Prompt 分组/分类显示