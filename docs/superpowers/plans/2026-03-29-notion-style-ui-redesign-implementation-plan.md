# NeatCopy Notion 风格 UI 重构 - 实现计划

## 状态：✅ 已完成

所有 Phase 1-6 已实施并通过测试验证。

---

## 目标

将设置窗口从 Tab + GroupBox 布局重构为侧边栏导航布局，参考设计文档 `docs/superpowers/specs/2026-03-29-notion-style-ui-redesign-design.md`。

## 技术栈

- PyQt6（保持不变）
- 在 worktree `ui-refactor` 分支开发

---

## 实现步骤

### Phase 1: 基础架构改造（低风险）

**目标：** 搭建侧边栏 + 内容区骨架，保持功能可用。

#### Step 1.1: 创建侧边栏组件

**文件：** `src/ui/components/sidebar.py`（新建）

**任务：**
1. 创建 `SidebarWidget` 类，继承 `QWidget`
2. 包含应用名称 Label（顶部）
3. 导航按钮列表使用 `QListWidget`
4. 实现 `currentChanged` 信号用于切换页面
5. 实现选中样式（左侧蓝色指示条 + 背景高亮）

**代码要点：**
```python
class SidebarWidget(QWidget):
    currentChanged = pyqtSignal(int)  # 页面索引

    def __init__(self, items: list[str], theme: str = 'light'):
        # items = ['通用', '规则', '大模型', '关于']
        # 使用 QListWidget 作为导航
        # 选中项样式：左侧 3px 蓝条 + 背景变色
```

#### Step 1.2: 更新样式模块

**文件：** `src/ui/styles.py`

**任务：**
1. 新增侧边栏样式函数 `get_sidebar_stylesheet(theme)`
2. 新增内容区样式函数 `get_content_stylesheet(theme)`
3. 新增区块标题样式 `SectionTitleLabel` 的 QSS
4. 更新主样式函数以合并新样式

**关键样式：**
- 侧边栏背景：Light #F7F6F3, Dark #202020
- 导航项高度：36px
- 选中指示条：3px 蓝色 (#2383E2)
- 分隔线：QFrame(HLine) 1px

#### Step 1.3: 更新配置管理器

**文件：** `src/config_manager.py`

**任务：**
1. 新增 `ui.window_width` 默认值 700
2. 新增 `ui.window_height` 默认值 550

**改动：**
```python
DEFAULT_CONFIG = {
    ...
    'ui': {
        'theme': 'light',
        'window_width': 700,
        'window_height': 550,
    },
    ...
}
```

---

### Phase 2: 重构设置窗口主结构

**目标：** 将 QTabWidget 替换为侧边栏 + QStackedWidget。

#### Step 2.1: 重构 SettingsWindow 初始化

**文件：** `src/ui/settings_window.py`

**任务：**
1. 移除 `QTabWidget`，改用 `QHBoxLayout`
2. 左侧放置 `SidebarWidget`（180px 固定宽度）
3. 右侧放置 `QStackedWidget`（自适应宽度）
4. 底部操作栏独立放置在主布局底部
5. 窗口尺寸改为可调整：
   - 默认尺寸从配置读取
   - 最小尺寸 550x400
   - 添加 `resizeEvent` 保存窗口尺寸

**代码骨架：**
```python
def __init__(self, ...):
    # 窗口属性
    width = self._config.get('ui.window_width', 700)
    height = self._config.get('ui.window_height', 550)
    self.resize(width, height)
    self.setMinimumSize(550, 400)

    # 主布局
    main_layout = QVBoxLayout(self)

    # 侧边栏 + 内容区
    content_row = QHBoxLayout()
    self._sidebar = SidebarWidget(['通用', '规则', '大模型', '关于'], self._theme)
    self._sidebar.currentChanged.connect(self._on_page_changed)
    content_row.addWidget(self._sidebar)

    self._stack = QStackedWidget()
    self._stack.addWidget(self._build_general_page())
    self._stack.addWidget(self._build_rules_page())
    self._stack.addWidget(self._build_llm_page())
    self._stack.addWidget(self._build_about_page())
    content_row.addWidget(self._stack)

    main_layout.addLayout(content_row)

    # 底部操作栏（固定高度 48px）
    bottom_bar = self._build_bottom_bar()
    main_layout.addWidget(bottom_bar)
```

#### Step 2.2: 添加页面切换处理

**任务：**
1. 实现 `_on_page_changed(index)` 方法
2. 侧边栏选中项与 QStackedWidget 同步

#### Step 2.3: 添加窗口尺寸持久化

**任务：**
1. 实现 `resizeEvent` 保存窗口尺寸到配置
```python
def resizeEvent(self, event):
    super().resizeEvent(event)
    self._config.set('ui.window_width', self.width())
    self._config.set('ui.window_height', self.height())
```

---

### Phase 3: 重构内容页面布局

**目标：** 去掉 GroupBox 边框，改用分隔线式布局。

#### Step 3.1: 创建区块标题组件

**文件：** `src/ui/components/section_title.py`（新建）

**任务：**
1. 创建 `SectionTitle` 类，继承 `QWidget`
2. 包含标题 Label（"── 标题 ──" 样式）
3. 可选包含分隔线

**样式：**
- 标题文字：12px，灰色 (#787774)
- 分隔线：1px，颜色随主题

#### Step 3.2: 重构通用页面

**文件：** `src/ui/settings_window.py` 的 `_build_general_page()`

**任务：**
1. 方法名从 `_build_general_tab` 改为 `_build_general_page`
2. 返回 `QWidget` 放入 `QScrollArea`
3. 去掉所有 `QGroupBox`
4. 用 `SectionTitle` + 分隔线替代区块分隔
5. 保留所有设置项的信号/槽连接

**区块结构：**
```
页面标题（18px 加粗）
── 通知 ──
☐ 显示清洗完成通知
☐ 开机自动启动
── 界面主题 ──
主题：[浅色] [深色]
── 独立热键 ──
☐ 启用  热键：[ctrl+shift+c]
── 双击 Ctrl+C ──
☐ 启用
间隔阈值滑块
── 轮盘 Prompt 选择器 ──
☐ 启用轮盘...
☐ 随清洗热键触发
切换热键：[ctrl+shift+p]
── 预览面板 ──
☐ 启用预览面板
快捷键：[ctrl+q]
面板主题：[深色] [浅色]
─── 分隔线 ───
[恢复默认]
```

#### Step 3.3: 重构规则页面

**文件：** `src/ui/settings_window.py` 的 `_build_rules_page()`

**任务：**
1. 方法名从 `_build_rules_tab` 改为 `_build_rules_page`
2. 去掉 `QGroupBox`
3. 用分隔线分隔"清洗模式"和"规则开关"区块
4. 保留所有信号/槽连接

#### Step 3.4: 重构大模型页面

**文件：** `src/ui/settings_window.py` 的 `_build_llm_page()`

**任务：**
1. 方法名从 `_build_llm_tab` 改为 `_build_llm_page`
2. 去掉 API 配置和 Prompt 模板的 `QGroupBox`
3. 用分隔线分隔区块
4. 保留所有信号/槽连接（包括测试连接线程）

#### Step 3.5: 重构关于页面

**文件：** `src/ui/settings_window.py` 的 `_build_about_page()`

**任务：**
1. 方法名从 `_build_about_tab` 改为 `_build_about_page`
2. 去掉版本信息、作者、项目地址的 `QGroupBox`
3. 用分隔线分隔区块

---

### Phase 4: 底部操作栏重构

**目标：** 将保存按钮和状态标签移至窗口底部固定位置。

#### Step 4.1: 创建底部操作栏组件

**文件：** `src/ui/settings_window.py`

**任务：**
1. 新增 `_build_bottom_bar()` 方法
2. 返回固定高度 48px 的 `QWidget`
3. 左侧状态标签，右侧保存按钮
4. 与主内容区有 1px 分隔线

**代码：**
```python
def _build_bottom_bar(self) -> QWidget:
    bar = QWidget()
    bar.setFixedHeight(48)
    layout = QHBoxLayout(bar)
    layout.setContentsMargins(16, 8, 16, 8)

    self._status_lbl = QLabel('')
    layout.addWidget(self._status_lbl)
    layout.addStretch()

    save_btn = QPushButton('保存')
    save_btn.setObjectName('btn_save')
    save_btn.clicked.connect(self._do_save)
    layout.addWidget(save_btn)

    return bar
```

---

### Phase 5: 主题切换适配

**目标：** 确保主题切换时侧边栏和内容区同步更新。

#### Step 5.1: 更新主题切换逻辑

**文件：** `src/ui/settings_window.py`

**任务：**
1. 更新 `_apply_theme()` 方法
2. 同时更新侧边栏主题
3. 同时更新内容区样式

```python
def _apply_theme(self):
    self.setStyleSheet(get_settings_stylesheet(self._theme))
    self._sidebar.set_theme(self._theme)
```

#### Step 5.2: 添加侧边栏主题切换方法

**文件：** `src/ui/components/sidebar.py`

**任务：**
1. 新增 `set_theme(theme)` 方法
2. 更新 QListWidget 样式

---

### Phase 6: 测试与验证

**目标：** 确保重构后功能完整，测试通过。

#### Step 6.1: 运行现有测试

**命令：** `pytest tests/`

**预期：** 所有测试通过（52 个测试）

#### Step 6.2: 手动功能验证

**清单：**
1. 侧边栏导航切换正常
2. 所有设置项可正常交互
3. 保存按钮写入配置成功
4. 热键录制功能正常
5. 主题切换实时生效
6. 窗口大小可调整且持久化
7. 滚动区域正常工作（内容超出时）

#### Step 6.3: 性能验证

**清单：**
1. 窗口启动时间 < 1 秒
2. 页面切换无明显延迟
3. 内存占用无明显增加

---

## 文件变更清单

| 文件 | 操作 | 改动说明 |
|------|------|----------|
| `src/ui/components/sidebar.py` | 新建 | 侧边栏导航组件 |
| `src/ui/components/section_title.py` | 新建 | 区块标题组件 |
| `src/ui/components/__init__.py` | 新建 | 组件包初始化 |
| `src/ui/styles.py` | 修改 | 新增侧边栏、内容区样式 |
| `src/ui/settings_window.py` | 重构 | 主窗口布局重构 |
| `src/config_manager.py` | 修改 | 新增窗口尺寸配置 |
| `tests/test_settings_window.py` | 新建 | UI 组件测试（可选） |

---

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 信号/槽连接断开 | 保留所有方法签名，只改 UI 结构 |
| 测试失败 | 在 worktree 开发，逐步验证 |
| 窗口大小持久化失败 | 使用已有 config.set 机制 |
| 主题切换不完整 | _apply_theme 同时更新所有子组件 |

---

## 依赖关系

```
Phase 1 (基础架构) ──┬──> Phase 2 (主结构重构)
                    │
                    └──> Phase 3 (内容页面重构)
                              │
                              └──> Phase 4 (底部操作栏)
                                        │
                                        └──> Phase 5 (主题适配)
                                                  │
                                                  └──> Phase 6 (测试验证)
```

**Phase 1 必须最先完成**，Phase 2 和 Phase 3 可并行开始（但 Phase 2 需要先完成骨架才能放入页面），Phase 4-6 顺序执行。