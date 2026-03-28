# 轮盘 Prompt 快捷选择器 — 实施计划

**日期**: 2026-03-28
**设计文档**: `docs/superpowers/specs/2026-03-28-wheel-prompt-selector-design.md`

---

## Phase 1: 配置层扩展

**目标**: 扩展 config_manager.py 支持轮盘相关配置

### 1.1 修改 `config_manager.py`

**默认配置新增**:
```python
'wheel': {
    'enabled': True,
    'trigger_with_clean': True,
    'switch_hotkey': 'ctrl+shift+p',
    'last_prompt_id': None,       # 随清洗模式记住上次选择
    'locked_prompt_id': None,     # 锁定模式当前锁定的 Prompt
},
```

**Prompt 对象扩展**: 在 `llm.prompts` 中每个 prompt 新增 `visible_in_wheel: True` 字段。需要在 `_ensure_defaults()` 中处理旧配置兼容（缺少字段时自动补 `True`）。

### 1.2 验证
- 删除本地 config.json，重新启动，确认新字段正确生成
- 手动编辑旧格式 config.json，确认字段自动补全

---

## Phase 2: 轮盘窗口组件

**目标**: 创建 `src/wheel_window.py`，实现扇形轮盘 UI

### 2.1 新建 `src/wheel_window.py`

**类**: `WheelWindow(QWidget)`

**窗口属性**:
- `Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool`
- `Qt.WidgetAttribute.WA_TranslucentBackground`
- 固定尺寸约 300×300px

**核心结构**:
```
WheelWindow
├── prompts: list[dict]         # 当前可见的 prompt 列表
├── hovered_index: int          # 鼠标悬停的选项索引 (-1 = 无)
├── selected_callback: callable # 选择后的回调
├── _animation: QPropertyAnimation  # 展开/关闭动画
│
├── show_at(pos, prompts, callback)  # 在指定位置显示
├── paintEvent()                     # 自绘扇形
├── mouseMoveEvent()                 # 计算悬停扇区
├── mousePressEvent()                # 确认选择
├── keyPressEvent()                  # 数字键 1-5 / ESC
└── _close_wheel()                   # 动画关闭
```

**绘制逻辑** (`paintEvent`):
1. 中心点 = 窗口中心
2. 外圆半径 R=130, 内圆半径 r=40（中心留空）
3. 每个扇区角度 = 360° / n，起始角度 = 90°（正上方开始）
4. 悬停扇区高亮（浅灰），默认扇区深灰色
5. 扇区内绘制 Prompt 名称（沿径向居中）
6. 数字标签 1-5 绘制在扇区内侧

**鼠标检测逻辑** (`mouseMoveEvent`):
1. 计算鼠标相对中心的极坐标 (r, θ)
2. 如果 r < 内半径或 r > 外半径 → hovered = -1
3. 否则 θ 映射到扇区索引

**动画**:
- 展开: `windowOpacity` 0→1 + scale（通过 `QGraphicsOpacityEffect`），150ms
- 关闭: 反向，100ms，动画结束后 `hide()`

**键盘处理** (`keyPressEvent`):
- `Qt.Key.Key_1` ~ `Key_5` → 直接选择对应索引（如果索引有效）
- `Qt.Key.Key_Escape` → `_close_wheel()`

**失焦关闭**: 重写 `focusOutEvent` 或使用 `deactivate` 事件关闭轮盘

**信号**:
- `prompt_selected(str)`: 发射选中的 prompt ID
- `wheel_cancelled()`: 取消（ESC/点击外部）

### 2.2 视觉风格
- 背景: 半透明深灰 `rgba(40, 40, 40, 230)`
- 悬停: `rgba(80, 80, 80, 230)`
- 文字: 白色，字号 12-13px
- 数字标签: 浅灰色，字号 10px
- 边框: 1px `rgba(100, 100, 100, 150)` 圆形外框
- 与现有设置界面的黑灰白配色一致

---

## Phase 3: 热键注册

**目标**: 在 `hotkey_manager.py` 中新增独立切换热键

### 3.1 修改 `hotkey_manager.py`

**新增热键注册**:
- 使用与 custom_hotkey 相同的 `RegisterHotKey` 机制
- 新增 hotkey ID（现有用 id=1，新增用 id=2）
- 在 `_HotkeyFilter.nativeEventFilter` 中区分两个 hotkey ID

**新增信号**:
- `wheel_hotkey_triggered`: 独立切换热键被按下时发射

**修改 `reload_config()`**:
- 读取 `wheel.switch_hotkey` 配置
- 注册/注销独立切换热键
- 仅在 `wheel.enabled` 为 True 时注册

**热键解析**: 复用现有的快捷键字符串解析逻辑（如 `ctrl+shift+p` → MOD_CONTROL | MOD_SHIFT, VK_P）

---

## Phase 4: 处理流程集成

**目标**: 修改 `clip_processor.py` 和 `main.py`，将轮盘集成到处理流程

### 4.1 修改 `clip_processor.py`

**新增方法**:
- `process_with_prompt(prompt_id: str)`: 指定 prompt ID 进行 LLM 处理（供轮盘选择后调用）
- `get_visible_prompts() -> list[dict]`: 获取轮盘可见的 prompt 列表

**修改 `process()` 方法**:
- 当 `rules.mode == 'llm'` 时：
  - 如果 `wheel.locked_prompt_id` 不为 None → 使用锁定的 prompt
  - 否则使用 `llm.active_prompt_id`（现有逻辑不变）
- 当 `rules.mode == 'rules'` 时：不变

### 4.2 修改 `main.py`

**新增 WheelWindow 实例化**:
```python
self.wheel = WheelWindow()
```

**信号连接 — 清洗触发模式**:
```
hotkey_triggered
    → 检查 mode == 'llm' 且 wheel.enabled 且 wheel.trigger_with_clean
        → 获取可见 prompts
        → 如果 > 1 个: wheel.show_at(cursor_pos, prompts, callback)
            → callback: processor.process_with_prompt(selected_id)
                        + 保存 last_prompt_id
        → 如果 == 1 个: 直接 processor.process_with_prompt(only_id)
        → 如果 == 0 个: 不处理
    → 否则: processor.process()（现有逻辑）
```

**信号连接 — 锁定模式**:
```
wheel_hotkey_triggered
    → 获取可见 prompts
    → wheel.show_at(cursor_pos, prompts, lock_callback)
        → lock_callback: config.set('wheel.locked_prompt_id', id)
                         + tray.update_locked_prompt(name)
```

**关键决策**: 在 `main.py` 中编排流程，而非在 `clip_processor.py` 内部判断轮盘，保持 `ClipProcessor` 职责单一。

---

## Phase 5: 托盘菜单集成

**目标**: 在托盘菜单中显示锁定状态

### 5.1 修改 `tray_manager.py`

**新增菜单项**:
- 在"打开设置"和"暂停监听"之间插入分隔线 + "当前锁定: [Prompt名称]" 显示项
- 如果未锁定则显示"当前锁定: 无"
- 点击该项弹出子菜单，列出所有可见 prompt，带 ✓ 标记当前锁定项
- 点击子菜单项可切换锁定（无需弹出轮盘）

**新增方法**:
- `update_locked_prompt(name: str | None)`: 更新菜单显示

**新增信号**:
- `locked_prompt_changed(str)`: 从菜单切换锁定时发射

---

## Phase 6: 设置界面

**目标**: 在 `settings_window.py` 中新增轮盘设置区域

### 6.1 修改 `ui/settings_window.py`

**新增位置**: 在"通用"Tab 的底部新增"轮盘设置"分组框（`QGroupBox`），而非新增 Tab。理由：轮盘设置属于通用交互配置，且配置项不多（4项），不足以单独成 Tab。

**轮盘设置分组** (`QGroupBox("轮盘 Prompt 选择器")`):

| 控件 | 类型 | 配置键 | 说明 |
|------|------|--------|------|
| 启用轮盘 | QCheckBox | `wheel.enabled` | 总开关 |
| 随清洗触发 | QCheckBox | `wheel.trigger_with_clean` | 子选项，仅 enabled=True 时可编辑 |
| 独立切换热键 | QPushButton（录制） | `wheel.switch_hotkey` | 复用现有热键录制逻辑 |
| 可见 Prompt | QListWidget + checkbox | `llm.prompts[].visible_in_wheel` | 列出所有 prompt，勾选最多5个 |

**交互细节**:
- 启用开关关闭时，子项全部置灰
- 可见 Prompt 列表勾选超过 5 个时，阻止勾选并 Toast 提示
- 热键录制复用 Tab1 现有的 `_start_record_hotkey` / `_stop_record_hotkey` 逻辑

### 6.2 保存逻辑
- 使用现有的 `_mark()` + `_do_save()` 机制
- 保存后调用 `hotkey_manager.reload_config()` 以注册新热键

---

## Phase 7: 测试与打磨

### 7.1 手动测试清单
- [ ] 清洗触发模式：LLM 模式 + 轮盘 enabled + trigger_with_clean → 弹出轮盘
- [ ] 清洗触发模式：仅 1 个可见 prompt → 跳过轮盘直接执行
- [ ] 清洗触发模式：0 个可见 prompt → 静默不处理
- [ ] 清洗触发模式：规则模式 → 不弹出轮盘，正常清洗
- [ ] 锁定模式：独立热键 → 弹出轮盘 → 选择后锁定
- [ ] 锁定模式：锁定后清洗使用锁定的 prompt
- [ ] 锁定模式：托盘菜单显示 ✓ 标记
- [ ] 锁定模式：通过托盘菜单切换
- [ ] 轮盘交互：鼠标悬停高亮
- [ ] 轮盘交互：鼠标点击选择
- [ ] 轮盘交互：数字键选择
- [ ] 轮盘交互：ESC 关闭
- [ ] 轮盘交互：点击外部关闭
- [ ] 轮盘交互：弹出/关闭动画流畅
- [ ] 设置界面：所有配置项正确保存和加载
- [ ] 设置界面：可见 prompt 最多勾选 5 个
- [ ] 热键冲突：独立切换热键与清洗热键不冲突
- [ ] 记住上次：随清洗模式记住并默认选中上次 prompt
- [ ] 性能：轮盘弹出 < 100ms

### 7.2 边缘情况
- 轮盘弹出时删除所有 prompt → 轮盘关闭
- 锁定的 prompt 被删除 → 自动解除锁定，回退到 active_prompt_id
- config.json 中无 wheel 字段 → 自动补全默认值

---

## 实施顺序

| 顺序 | Phase | 预计改动 | 依赖 |
|------|-------|----------|------|
| 1 | Phase 1: 配置层 | ~30 行 | 无 |
| 2 | Phase 2: 轮盘窗口 | ~300 行（新文件） | Phase 1 |
| 3 | Phase 3: 热键注册 | ~50 行 | Phase 1 |
| 4 | Phase 4: 流程集成 | ~80 行 | Phase 1-3 |
| 5 | Phase 5: 托盘菜单 | ~40 行 | Phase 4 |
| 6 | Phase 6: 设置界面 | ~100 行 | Phase 1 |
| 7 | Phase 7: 测试打磨 | — | Phase 1-6 |

**Phase 1 → 2/3 可并行 → 4 → 5/6 可并行 → 7**

---

## 关键文件清单

| 文件 | 操作 |
|------|------|
| `src/wheel_window.py` | **新建** |
| `src/config_manager.py` | 修改 |
| `src/hotkey_manager.py` | 修改 |
| `src/clip_processor.py` | 修改 |
| `src/tray_manager.py` | 修改 |
| `src/ui/settings_window.py` | 修改 |
| `src/main.py` | 修改 |
