# NeatCopy UI Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite NeatCopy's PyQt6 UI from Notion-style to Shadcn-style, matching the HTML/CSS design mockups in NeatCopy-ui/.

**Architecture:** Replace the ColorPalette and stylesheet system, build 3 custom QWidget subclasses (ToggleSwitch, SegmentedControl, Card), then rewrite settings_window (4→5 pages), history_window, and update styles for preview/wheel/tray. Each task produces a runnable state.

**Tech Stack:** Python 3, PyQt6, QtSvg (for sidebar icons)

**Spec:** `docs/superpowers/specs/2026-05-27-ui-rewrite-design.md`
**Design reference:** `D:\Users\Aletta\Desktop\Works\NeatCopy\NeatCopy-ui\` (HTML/CSS mockups)

---

## File Structure

| File | Responsibility | Status |
|------|---------------|--------|
| `src/ui/styles.py` | ColorPalette + all QSS generators | REWRITE |
| `src/ui/components/icon_helper.py` | SVG icon generator for sidebar | MODIFY |
| `src/ui/components/sidebar.py` | 5-item sidebar navigation | REWRITE |
| `src/ui/components/__init__.py` | Component exports | MODIFY |
| `src/ui/components/toggle_switch.py` | ToggleSwitch custom widget | CREATE |
| `src/ui/components/segmented_control.py` | SegmentedControl custom widget | CREATE |
| `src/ui/components/card.py` | Card container widget | CREATE |
| `src/ui/settings_window.py` | Settings dialog with 5 pages | REWRITE |
| `src/ui/history_window.py` | History window with toolbar + dual-pane | REWRITE |
| `src/ui/preview_window.py` | Preview panel style alignment | MODIFY |
| `src/wheel_window.py` | Wheel sector style tweaks | MODIFY |
| `src/tray_manager.py` | Tray menu + Toast style | MODIFY |

---

### Task 1: Design System — styles.py rewrite

**Files:**
- REWRITE: `src/ui/styles.py`

This task replaces the entire Notion-style palette and stylesheet system with the Shadcn design tokens from the spec.

- [ ] **Step 1: Write the new ColorPalette class**

Replace the entire `styles.py` content. The new file must contain:

1. `FONT_FAMILY` — `"Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI", sans-serif`
2. `FONT_MONO` — `"Cascadia Code", "Fira Code", Consolas, monospace`
3. `ColorPalette` class with `LIGHT` and `DARK` dicts containing all tokens from the spec (bg, surface_alt, fg, fg_2, muted, fg_soft, border, border_strong, accent, accent_on, accent_hover, accent_soft, success, success_soft, warn, warn_soft, danger, danger_soft, info, info_soft, focus_ring)
4. `ColorPalette.get(theme)` classmethod
5. `get_settings_stylesheet(theme)` — main QSS for settings window, covering: QDialog, QScrollArea, QLabel, QCheckBox, QSlider, QLineEdit, QTextEdit, QSpinBox, QPushButton (btn-primary, btn-secondary, btn-ghost, btn-danger, btn-sm variants), QScrollBar, QMenu, QToolTip
6. `get_sidebar_stylesheet(theme)` — sidebar QSS
7. `get_history_stylesheet(theme)` — history window QSS
8. `get_checkbox_image_path(theme)` — keep existing pattern, update paths

Key style rules for the QSS:
- All colors must use `rgba()` notation (Qt doesn't support `color-mix()` or `oklch`)
- Button primary: accent bg + accent_on text
- Button secondary: border + fg text, hover border_strong + fg_soft bg
- Button ghost: muted text, hover fg text + fg_soft bg
- Button danger: danger text, hover danger_soft bg
- Input fields: border + radius_sm, focus accent border + accent_soft shadow ring
- Slider groove: 4px height, border color; handle: 16x16, bg + 2px accent border; sub-page: accent color
- Scrollbar: 6px wide for content areas, 4px for history list, border-colored thumb with radius
- Segmented container background (for items not using custom widget): surface_alt

- [ ] **Step 2: Verify styles.py loads without error**

Run: `cd src && python -c "from ui.styles import ColorPalette; print(ColorPalette.LIGHT['accent']); print(ColorPalette.DARK['accent'])"`
Expected: `#000000` then `#fafafa`

- [ ] **Step 3: Commit**

```bash
git add src/ui/styles.py
git commit -m "refactor: rewrite styles.py with Shadcn design tokens"
```

---

### Task 2: ToggleSwitch custom widget

**Files:**
- CREATE: `src/ui/components/toggle_switch.py`
- MODIFY: `src/ui/components/__init__.py`

- [ ] **Step 1: Create toggle_switch.py**

Build a custom QWidget subclass:

```python
# Key structure:
class ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, parent=None, checked=False):
        # Track: 36x20px
        # Thumb: 16x16px circle
        # Uses QPropertyAnimation for smooth thumb slide (150ms)
        # Uses QPainter in paintEvent to draw track (rounded rect) and thumb (ellipse)

    @pyqtProperty(bool)
    def checked(self): ...

    @checked.setter
    def checked(self, value): ...

    def paintEvent(self, event):
        # Track: rounded rect, border_strong when off, accent when on
        # Thumb: white ellipse with shadow, position based on checked state
        # Use palette colors from self._theme_colors (call set_theme method)

    def mousePressEvent(self, event):
        # Toggle checked, emit toggled signal

    def set_theme(self, theme: str):
        # Update internal color cache from ColorPalette.get(theme)
        # Trigger update()
```

The paintEvent must draw:
- Off state: `border_strong` track, white thumb at x=2
- On state: `accent` track, white thumb at x=18 (translateX 16px)
- Thumb shadow: `0 1px 2px rgba(0,0,0,0.15)`

Use `QPainter.setRenderHint(QPainter.RenderHint.Antialiasing)`.

- [ ] **Step 2: Update __init__.py exports**

Add `from ui.components.toggle_switch import ToggleSwitch` to `src/ui/components/__init__.py`.

- [ ] **Step 3: Verify widget renders**

Run: `cd src && python -c "from ui.components.toggle_switch import ToggleSwitch; print('ToggleSwitch OK')"`
Expected: `ToggleSwitch OK`

- [ ] **Step 4: Commit**

```bash
git add src/ui/components/toggle_switch.py src/ui/components/__init__.py
git commit -m "feat: add ToggleSwitch custom widget with Shadcn style"
```

---

### Task 3: SegmentedControl custom widget

**Files:**
- CREATE: `src/ui/components/segmented_control.py`
- MODIFY: `src/ui/components/__init__.py`

- [ ] **Step 1: Create segmented_control.py**

```python
class SegmentedControl(QWidget):
    selectionChanged = pyqtSignal(int)

    def __init__(self, options: list[str], parent=None, full_width=False):
        # Container: surface_alt bg, padding 3px, gap 2px, radius_sm
        # Layout: QHBoxLayout with buttons
        # Each option is a QPushButton with:
        #   - Unselected: muted text, no background
        #   - Selected: bg bg + shadow_sm + fg text
        #   - Hover: fg text
        # full_width: buttons use stretch factor for equal width

    def setCurrentIndex(self, index: int): ...
    def currentIndex(self) -> int: ...
    def set_theme(self, theme: str): ...
```

Implementation approach:
- Use QButtonGroup with exclusive toggle
- Apply QSS to the container and buttons
- Selected button gets a special stylesheet class or objectName
- `full_width` sets all buttons to stretch=1 in the QHBoxLayout

- [ ] **Step 2: Update __init__.py**

Add `from ui.components.segmented_control import SegmentedControl`.

- [ ] **Step 3: Verify**

Run: `cd src && python -c "from ui.components.segmented_control import SegmentedControl; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/ui/components/segmented_control.py src/ui/components/__init__.py
git commit -m "feat: add SegmentedControl custom widget"
```

---

### Task 4: Card widget + icon_helper update

**Files:**
- CREATE: `src/ui/components/card.py`
- MODIFY: `src/ui/components/__init__.py`
- MODIFY: `src/ui/components/icon_helper.py`

- [ ] **Step 1: Create card.py**

```python
class Card(QFrame):
    """Shadcn-style card container replacing QGroupBox."""

    def __init__(self, title: str = '', description: str = '', parent=None):
        # QFrame with:
        #   - objectName: "card"
        #   - Layout: QVBoxLayout, padding sp_5, spacing 0
        #   - Title label (if provided): sm font, font-weight 600, margin-bottom sp_4
        #   - Description label (if provided): xs font, muted color, margin-bottom sp_3
        #   - Content area: QVBoxLayout for child widgets
        #   - QSS: bg + 1px border + radius_md + margin-bottom sp_4

    def content_layout(self) -> QVBoxLayout:
        # Returns the layout where setting rows are added

    def set_theme(self, theme: str): ...
```

- [ ] **Step 2: Update icon_helper.py**

Update `NAV_ICON_MAP` to add the new "快捷键" entry with a keyboard SVG icon. Update SVG_ICONS to add a new `keyboard` key with an appropriate keyboard SVG (from the design reference: rect with keys pattern).

Update the icon color source to use the new `ColorPalette.get(theme)['fg']` instead of `text_primary`.

- [ ] **Step 3: Update __init__.py**

Add both new imports.

- [ ] **Step 4: Verify**

Run: `cd src && python -c "from ui.components.card import Card; from ui.components.icon_helper import get_nav_icon; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/ui/components/card.py src/ui/components/icon_helper.py src/ui/components/__init__.py
git commit -m "feat: add Card widget and update icon_helper for 5 nav items"
```

---

### Task 5: Sidebar rewrite

**Files:**
- REWRITE: `src/ui/components/sidebar.py`

- [ ] **Step 1: Rewrite sidebar.py**

Rewrite `SidebarWidget` for 5 navigation items with Shadcn style:

```python
class SidebarWidget(QWidget):
    currentChanged = pyqtSignal(int)

    NAV_ITEMS = ['通用', '快捷键', '清洗规则', '大模型', '关于']

    def __init__(self, theme='light', parent=None):
        # Fixed width: 160px
        # Layout: QVBoxLayout
        # Brand label: "NeatCopy", font-weight 700, base size, padding sp_2 sp_4 sp_4
        # QListWidget: 5 items with icons from icon_helper
        # Each item: padding sp_2 sp_4, 3px transparent left border
        # Selected: accent_soft bg + accent left border + font-weight 500
        # Hover: fg_soft bg

    def set_theme(self, theme): ...
    def setCurrentIndex(self, index): ...
```

Key changes from current:
- 4 items → 5 items (add "快捷键")
- Blue indicator → black/accent indicator
- Notion sidebar colors → Shadcn sidebar colors
- Width 150 → 160

- [ ] **Step 2: Verify sidebar renders in isolation**

Run: `cd src && python -c "from ui.components.sidebar import SidebarWidget; s = SidebarWidget(); print(f'Items: {s._list.count()}'); assert s._list.count() == 5; print('OK')"`
Expected: `Items: 5` then `OK`

- [ ] **Step 3: Commit**

```bash
git add src/ui/components/sidebar.py
git commit -m "refactor: rewrite sidebar with 5 nav items and Shadcn style"
```

---

### Task 6: Settings window shell + General page

**Files:**
- REWRITE: `src/ui/settings_window.py`

This is the largest task. The settings window is rewritten from scratch with the new layout. This task creates the shell (titlebar, sidebar, stacked widget, footer) and the General page. Subsequent tasks add the other pages.

- [ ] **Step 1: Write the SettingsWindow class shell**

```python
class SettingsWindow(QDialog):
    def __init__(self, config, hotkey_manager=None, parent=None):
        # Window: 780x580, min 550x400
        # Layout: QVBoxLayout (margins 0)
        #   - Title bar (custom, 40px): title "设置" + close button
        #   - Body (QHBoxLayout): sidebar + QStackedWidget
        #   - Footer (52px): stretch + "保存" button (btn-primary)
        # Pages (in order): General, Hotkeys, Rules, LLM, About

    def _build_titlebar(self) -> QWidget: ...
    def _build_footer(self) -> QWidget: ...
    def _build_general_page(self) -> QScrollArea: ...
    def _build_hotkeys_page(self) -> QScrollArea: ...
    def _build_rules_page(self) -> QScrollArea: ...
    def _build_llm_page(self) -> QScrollArea: ...
    def _build_about_page(self) -> QScrollArea: ...
```

- [ ] **Step 2: Implement _build_general_page()**

3 Card widgets:
1. **通知** Card: one SettingRow with "显示清洗完成通知" label + ToggleSwitch
2. **启动** Card: one SettingRow with "开机自动启动" label + ToggleSwitch
3. **外观** Card:
   - SettingRow: "界面主题" + SegmentedControl(["浅色", "深色"])
   - SettingRow: "预览面板主题" + SegmentedControl(["深色", "浅色"])

Each SettingRow is a QHBoxLayout: label on left (stretch), control on right (fixed), separated by border-top between rows.

- [ ] **Step 3: Implement stub pages (return empty scroll area with label placeholder)**

Create minimal stubs for Hotkeys, Rules, LLM, About pages so the window is navigable.

- [ ] **Step 4: Implement _mark(), _do_save(), _apply_theme(), hotkey recording**

Port these methods from the existing code. The `_mark`/`_do_save`/pending system stays the same. Hotkey recording (`keyPressEvent`, grab/release keyboard) stays the same. `_apply_theme()` applies `get_settings_stylesheet(theme)` and propagates to sidebar.

- [ ] **Step 5: Implement closeEvent with unsaved changes dialog**

Port from existing code.

- [ ] **Step 6: Verify window opens and sidebar navigates**

Run: `cd src && python -c "
from PyQt6.QtWidgets import QApplication
import sys
app = QApplication(sys.argv)
from config_manager import ConfigManager
from ui.settings_window import SettingsWindow
w = SettingsWindow(ConfigManager())
w.show()
print('Settings window OK')
"`
Expected: Window opens at 780x580, sidebar has 5 items, clicking navigates between pages. General page shows 3 cards with toggles and segmented controls.

- [ ] **Step 7: Commit**

```bash
git add src/ui/settings_window.py
git commit -m "feat: rewrite settings window shell + general page with Shadcn style"
```

---

### Task 7: Settings window — Hotkeys page

**Files:**
- MODIFY: `src/ui/settings_window.py`

- [ ] **Step 1: Implement _build_hotkeys_page()**

3 Card widgets:

**清洗触发 Card:**
- SettingRow: "独立热键" + ToggleSwitch(checked=config hotkey enabled) + HotkeyBtn(config hotkey keys)
- SettingRow: "双击 Ctrl+C" + ToggleSwitch
- SettingRow (indented, opacity controlled by double-click toggle): "间隔阈值" + Slider(100-500, step 50) + value label

**功能快捷键 Card:**
- SettingRow: "轮盘选择器" + ToggleSwitch + HotkeyBtn
- Indented QCheckBox: "随清洗热键触发时弹出轮盘"
- SettingRow: "预览面板" + ToggleSwitch + HotkeyBtn
- SettingRow: "历史记录" + ToggleSwitch + HotkeyBtn

**历史记录 Card:**
- SettingRow: "最大条数" + QSpinBox(50-5000, width 80px) + "条" label

HotkeyBtn pattern: QPushButton with objectName "hotkey_btn", checkable. On click: set checked, grab keyboard, change text to "请按下快捷键组合...". In keyPressEvent: capture combo, set text, release keyboard. 5 second timeout to cancel.

Slider pattern: QSlider + QLabel showing value. Temperature maps 0-20 → 0.0-2.0. Interval maps 100-500 directly.

Port the existing hotkey recording logic (`_on_clean_hotkey_btn`, `_on_wheel_hotkey_btn`, `_on_preview_hotkey_btn`, `_on_history_hotkey_btn`, `keyPressEvent`) adapting to the new widget references.

- [ ] **Step 2: Verify hotkeys page works**

Run the app, navigate to Hotkeys page, verify toggles work, sliders adjust, hotkey buttons enter recording mode.

- [ ] **Step 3: Commit**

```bash
git add src/ui/settings_window.py
git commit -m "feat: add hotkeys page to settings window"
```

---

### Task 8: Settings window — Rules page

**Files:**
- MODIFY: `src/ui/settings_window.py`

- [ ] **Step 1: Implement _build_rules_page()**

**清洗模式 Card:**
- SegmentedControl(full_width=True, options=["规则模式", "大模型模式"])
- When "大模型模式" selected: switch sidebar to LLM tab and switch stacked widget

**规则开关 Card:**
- Title + description "规则模式下生效" (xs, muted)
- 8 QCheckBox items with title + hint text, using RULE_LABELS dict (keep existing)
- Each checkbox: when toggled, calls `_mark(f'rules.{key}', checked)`

Keep the existing `_on_mode_checkbox_changed` logic, adapted for SegmentedControl instead of QCheckBox pair.

- [ ] **Step 2: Verify**

Run app, navigate to Rules page, verify segmented control toggles, checkboxes work, switching to "大模型模式" navigates to LLM tab.

- [ ] **Step 3: Commit**

```bash
git add src/ui/settings_window.py
git commit -m "feat: add rules page to settings window"
```

---

### Task 9: Settings window — LLM page

**Files:**
- MODIFY: `src/ui/settings_window.py`

- [ ] **Step 1: Implement _build_llm_page()**

Page-level items (not in a card):
- SettingRow: "启用大模型模式" (font-weight 600) + ToggleSwitch

**API配置 Card:**
- Base URL: QLineEdit with placeholder
- Model ID: QLineEdit with placeholder
- API Key: QLineEdit(password) + "显示"/"隐藏" toggle button (inline right)
- Temperature: QSlider(0-20) + value label
- 超时时长: QSpinBox(10-300) + "秒"
- Bottom row: "测试连接" button + "恢复默认" button + connection status label (inline, below card)

**Prompt模板 Card:**
- QListWidget for templates (right-click menu: set default/edit/delete, double-click: edit)
- Template item display: name + [默认] tag + [只读] Badge
- Bottom: "+ 新增模板" button + "管理轮盘" button

**轮盘管理 Modal** (triggered by "管理轮盘" button):
- QDialog, 420px wide
- Two-column layout: left "可用模板" (checkable list) + right "轮盘模板" (numbered list)
- Max 5 items
- "确定" button

**模板编辑 Modal** (triggered by double-click/edit menu):
- QDialog, 420px wide
- Title: "编辑：{name}"
- QTextEdit (8 rows)
- "保存" button

Port existing logic: `_refresh_prompts`, `_show_prompt_menu`, `_edit_prompt_by_id`, `_on_add_prompt`, `_on_test_connection`, `_confirm_and_reset_llm_api`, wheel selector logic.

- [ ] **Step 2: Verify**

Run app, navigate to LLM page, verify all fields populate from config, test connection works, template CRUD works, wheel management modal opens.

- [ ] **Step 3: Commit**

```bash
git add src/ui/settings_window.py
git commit -m "feat: add LLM page with API config, prompts, and wheel management"
```

---

### Task 10: Settings window — About page

**Files:**
- MODIFY: `src/ui/settings_window.py`

- [ ] **Step 1: Implement _build_about_page()**

Centered layout (no cards):
- QVBoxLayout, alignment AlignCenter, padding sp_12 sp_6
- "NeatCopy" label: xl font-size (24px), font-weight 800, letter-spacing -0.03em, fg color
- Version label: mono font, sm size, muted color ("v{VERSION}")
- Author label: sm size, muted color ("by StoneLL1")
- GitHub link: sm size, fg color, clickable (`<a>` tag with QDesktopServices)
- "检查更新" button (secondary style)
- "如果觉得有用，欢迎 Star ⭐" label: sm size, muted color

Port `_on_check_update` and `_on_update_result` from existing code.

- [ ] **Step 2: Verify**

Run app, navigate to About page, verify layout is centered, link opens browser, update check works.

- [ ] **Step 3: Commit**

```bash
git add src/ui/settings_window.py
git commit -m "feat: add centered about page"
```

---

### Task 11: History window rewrite

**Files:**
- REWRITE: `src/ui/history_window.py`

- [ ] **Step 1: Rewrite HistoryWindow**

Key changes from current:
- **Remove** frameless window flag — use standard system window frame
- **Remove** acrylic effect (standard window doesn't need it)
- **Add** custom titlebar (36px): "历史记录" title + close button
- **Add** toolbar: "历史记录" label (font-weight 600) + search input (flex 1, max 280px, placeholder "搜索原文或结果...") + "清空" button (ghost style)
- **Keep** dual-pane layout (QSplitter) with left 240px list + right detail
- **Update** all styles to use new ColorPalette

Layout structure:
```
QVBoxLayout (margins 0)
├── TitleBar (36px, border-bottom)
├── Toolbar (padding sp_3 sp_4, border-bottom)
└── QSplitter (horizontal)
    ├── QListWidget (240px, border-right)
    └── Detail pane (flex 1)
        ├── Empty state OR
        ├── Detail content
        │   ├── Header: time + mode badge
        │   ├── "原文" section label + text display
        │   ├── "结果" section label + text display
        │   └── Actions: 复制原文 + 复制结果 + stretch + 删除
```

Style details:
- List items: padding sp_3 sp_4, border-bottom 1px, hover fg_soft, selected accent_soft
- List item content: time (mono, 11px, muted) + mode badge (xs, pill) on top, summary (xs, truncate 30 chars) below
- Detail text: surface_alt bg + border + radius_sm, sm font, line-height 1.6
- Section labels: xs, font-weight 600, muted
- Action buttons: secondary style, delete button danger style
- Scrollbars: 4px width, border color thumb

Keep all existing data logic: `_refresh_list`, `_on_item_clicked`, `_clear_detail`, search, copy, delete, clear all. The list item rendering needs updating to use the two-line format (time+mode on top, summary below).

Window size: 720x520, min 400x300. Keep drag (only via titlebar area). Keep resize event saving.

- [ ] **Step 2: Verify**

Run the app, open history window via tray menu or Ctrl+H. Verify:
- Standard window frame with title bar
- Toolbar with search and clear
- Dual-pane layout
- List items show time, mode badge, summary
- Clicking shows detail with original/result
- Search filters, copy/delete works

- [ ] **Step 3: Commit**

```bash
git add src/ui/history_window.py
git commit -m "refactor: rewrite history window with Shadcn style and titlebar"
```

---

### Task 12: Preview window style update

**Files:**
- MODIFY: `src/ui/preview_window.py`

- [ ] **Step 1: Update _get_theme_styles() to use new ColorPalette**

Replace the hardcoded color dicts with colors derived from `ColorPalette.get(theme)`.

Dark theme (default):
- Panel bg: `rgba(30,30,46,0.92)` — keep this specific dark blue-gray for the frosted glass look
- Panel border: `rgba(255,255,255,0.08)`
- Text: `#e2e2e8`
- Status colors: use semantic colors from palette (success, warn, danger, info)
- Apply button: white bg + dark text (matching design)
- Close button: `rgba(255,255,255,0.4)` → hover `rgba(255,255,255,0.8)` + bg `rgba(255,255,255,0.08)`

Light theme:
- Panel bg: `rgba(255,255,255,0.92)`
- Panel border: `rgba(0,0,0,0.08)`
- Text: use fg from palette
- Apply button: accent bg + accent_on text
- Close button: muted → hover fg

Update all `setStyleSheet()` calls to use the new colors. Keep the acrylic effect code. Keep all resize/drag logic unchanged.

- [ ] **Step 2: Verify**

Run app, trigger LLM mode preview (Ctrl+Q), verify dark theme frosted glass panel. Change preview theme to light in settings, verify light theme works.

- [ ] **Step 3: Commit**

```bash
git add src/ui/preview_window.py
git commit -m "style: update preview window with Shadcn-style colors"
```

---

### Task 13: Wheel window style tweaks

**Files:**
- MODIFY: `src/wheel_window.py`

- [ ] **Step 1: Update sector colors**

Find the sector fill/hover/selected colors in `wheel_window.py` and update to match the design spec:
- Normal: `rgba(255,255,255,0.06)` (was slightly different)
- Hover: `rgba(255,255,255,0.14)`
- Selected: `rgba(255,255,255,0.2)`
- Last-used: `rgba(255,255,255,0.1)`
- Label text: `rgba(255,255,255,0.7)`, 12px
- Number text: `rgba(255,255,255,0.3)`, 10px
- Center circle: `rgba(30,30,46,0.95)` fill + `rgba(255,255,255,0.1)` stroke
- ESC text: `rgba(255,255,255,0.4)`

These are likely defined as constants or in the `_build_sectors`/painting methods. Find and update the color values.

- [ ] **Step 2: Verify**

Run app, trigger wheel (Ctrl+Shift+P with LLM prompts configured), verify sector colors match design.

- [ ] **Step 3: Commit**

```bash
git add src/wheel_window.py
git commit -m "style: update wheel sector colors to match design spec"
```

---

### Task 14: Tray menu + Toast style updates

**Files:**
- MODIFY: `src/tray_manager.py`

- [ ] **Step 1: Update tray context menu styles**

Find the QMenu stylesheet in `tray_manager.py` and update to Shadcn style:
- Background: bg color from ColorPalette
- Border: 1px border + radius_md
- Padding: sp_1 0
- Item padding: sp_2 sp_3
- Item hover: accent_soft bg
- Separator: 1px border
- Disabled items: muted color
- "退出" item: danger color text

- [ ] **Step 2: Update Toast notification styles**

Find the Toast widget/styles in `tray_manager.py` and update:
- save: accent(bg) + accent_on(text) — "✓ 已保存"
- success: success bg + white text — "✓ 清洗完成"
- error: danger bg + white text — "✕ 处理失败"
- info: fg bg + bg text — "→ 已应用到剪贴板"
- warn: warn bg + white text — "! 连接超时"
- Padding: sp_2 sp_4, radius_sm, font-weight 500, xs font
- Duration: 2 seconds
- Animation: fade in/out (if current code supports it)

- [ ] **Step 3: Verify**

Run app, trigger a clean operation, verify toast appears with new colors. Right-click tray icon, verify menu styling.

- [ ] **Step 4: Commit**

```bash
git add src/tray_manager.py
git commit -m "style: update tray menu and toast notification styles"
```

---

### Task 15: Final integration and smoke test

**Files:**
- None (verification only)

- [ ] **Step 1: Full application smoke test**

Run `python src/main.py` and verify:

1. App starts, tray icon appears
2. Right-click tray → "打开设置" → Settings window opens at 780x580
3. Sidebar has 5 items with correct icons
4. **通用** page: 3 cards (通知/启动/外观), toggles work, segmented controls work
5. **快捷键** page: 3 cards, all toggles/sliders/hotkey buttons work
6. **清洗规则** page: mode segmented control, 8 checkboxes
7. **大模型** page: enable toggle, API fields, template list, wheel management modal
8. **关于** page: centered layout, version, link opens browser
9. Footer has "保存" button, clicking saves and shows toast
10. Theme switch (浅色/深色) applies correctly across all pages
11. Close with unsaved changes shows dialog
12. History window (Ctrl+H or tray menu): titlebar, toolbar, dual-pane, search works
13. Preview panel (Ctrl+Q): dark theme frosted glass, status colors
14. Wheel selector: sector colors match spec
15. Tray menu: Shadcn styled, all items work
16. Toast: correct colors per type

- [ ] **Step 2: Fix any issues found**

Address any visual glitches, broken signals, or missing functionality.

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "fix: final integration fixes for UI rewrite"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- [x] Design system (tokens, palette) → Task 1
- [x] ToggleSwitch → Task 2
- [x] SegmentedControl → Task 3
- [x] Card + icon_helper → Task 4
- [x] Sidebar (5 items) → Task 5
- [x] Settings window General page → Task 6
- [x] Settings window Hotkeys page → Task 7
- [x] Settings window Rules page → Task 8
- [x] Settings window LLM page → Task 9
- [x] Settings window About page → Task 10
- [x] History window → Task 11
- [x] Preview window → Task 12
- [x] Wheel window → Task 13
- [x] Tray menu + Toast → Task 14
- [x] Final integration → Task 15

**2. Placeholder scan:** No TBD/TODO/fill-in-later patterns found. All tasks have specific implementation instructions.

**3. Type consistency:** All widget class names, method names, and signals are consistent across tasks. ColorPalette.get(theme) is used uniformly.
