# 设置界面：自定义标题栏 + 侧边栏导航 + Card 分组布局（Shadcn 风格）
import uuid
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QCheckBox, QSlider, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem,
    QTextEdit, QInputDialog, QMessageBox, QMenu,
    QStackedWidget, QFrame, QScrollArea, QSpinBox,
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices

from version import VERSION
from assets import asset as _asset
from autostart_manager import enable as _autostart_enable, disable as _autostart_disable
from ui.styles import get_settings_stylesheet, ColorPalette
from ui.components.sidebar import SidebarWidget
from ui.components.card import Card
from ui.components.toggle_switch import ToggleSwitch
from ui.components.segmented_control import SegmentedControl


RULE_LABELS = {
    'merge_soft_newline':  ('合并软换行',     'PDF/CAJ 段落内断行合并为一行'),
    'keep_hard_newline':   ('保留段落分隔',   '连续空行视为真正段落分隔，保留不合并'),
    'merge_spaces':        ('合并多余空格',   '多个连续空格合并为单个空格'),
    'smart_punctuation':   ('智能全/半角标点', '中文语境保留全角，英文语境转半角'),
    'pangu_spacing':       ('中英文间距',     '中英文之间自动加空格（Pangu 风格）'),
    'trim_lines':          ('去除行首尾空白', '每行首尾多余空白清除'),
    'protect_code_blocks': ('保护代码块',     '识别代码块，跳过所有清洗'),
    'protect_lists':       ('保护列表结构',   '列表行保留换行，不合并'),
}


class SettingsWindow(QDialog):
    MAX_WHEEL_PROMPTS = 5

    def __init__(self, config, hotkey_manager=None, parent=None):
        super().__init__(parent)
        self._config = config
        self._hotkey_manager = hotkey_manager
        self._pending: dict = {}
        self._theme = config.get('ui.theme', 'light')
        self._drag_pos = None

        # Track themed widgets for propagation
        self._cards: list[Card] = []
        self._toggles: list[ToggleSwitch] = []
        self._segmented_controls: list[SegmentedControl] = []

        # Hotkey recording state
        self._recording_target = None
        self._recording_timer = QTimer()
        self._recording_timer.setSingleShot(True)
        self._recording_timer.timeout.connect(self._on_recording_timeout)
        self._hotkey_buttons = {}  # maps 'clean'/'wheel'/'preview'/'history' -> QPushButton

        # Window setup
        self.setWindowTitle('NeatCopy 设置')
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.resize(780, 580)
        self.setMinimumSize(550, 400)
        self.setWindowIcon(QIcon(_asset('idle.ico')))

        # Build layout
        self._build_layout()

        # Apply theme after all widgets are created
        self._apply_theme()

    # ── Layout construction ─────────────────────────────────────────

    def _build_layout(self):
        """Build the main layout: titlebar + body(sidebar + pages) + footer."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 1. Title bar
        root.addWidget(self._build_titlebar())

        # 2. Body: sidebar + separator + stacked pages
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._sidebar = SidebarWidget(theme=self._theme)
        self._sidebar.currentChanged.connect(self._on_nav_select)
        body.addWidget(self._sidebar)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setObjectName('sidebar_separator')
        body.addWidget(separator)

        self._content_stack = QStackedWidget()
        self._content_stack.addWidget(self._build_general_page())
        self._content_stack.addWidget(self._build_hotkeys_page())
        self._content_stack.addWidget(self._build_rules_page())
        self._content_stack.addWidget(self._build_llm_page())
        self._content_stack.addWidget(self._build_about_page())
        body.addWidget(self._content_stack, 1)

        root.addLayout(body, 1)

        # 3. Footer
        root.addWidget(self._build_footer())

    def _build_titlebar(self) -> QWidget:
        """Build custom title bar (40px) with title and close button."""
        titlebar = QWidget()
        titlebar.setObjectName('titlebar')
        titlebar.setFixedHeight(40)

        layout = QHBoxLayout(titlebar)
        layout.setContentsMargins(16, 0, 8, 0)
        layout.setSpacing(0)

        title_label = QLabel('设置')
        title_label.setObjectName('titlebar_title')
        layout.addWidget(title_label)
        layout.addStretch()

        close_btn = QPushButton('×')
        close_btn.setObjectName('titlebar_close')
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        return titlebar

    def _build_footer(self) -> QWidget:
        """Build footer bar (52px) with status label and save button."""
        footer = QWidget()
        footer.setObjectName('bottom_bar')
        footer.setFixedHeight(52)

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(12)

        self._status_lbl = QLabel('')
        self._status_lbl.setObjectName('status_label')
        layout.addWidget(self._status_lbl)
        layout.addStretch()

        self._btn_save = QPushButton('保存')
        self._btn_save.setObjectName('btn_save')
        self._btn_save.clicked.connect(self._do_save)
        layout.addWidget(self._btn_save)

        return footer

    def _on_nav_select(self, index: int):
        """Sidebar navigation callback: switch stacked page."""
        self._content_stack.setCurrentIndex(index)

    # ── General page (Page 0) ───────────────────────────────────────

    def _build_general_page(self) -> QScrollArea:
        """Build the General settings page with Cards."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName('content_scroll')

        page = QWidget()
        page.setObjectName('content_page')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Card 1: Notifications
        card_notify = Card('通知')
        self._cards.append(card_notify)
        self._toggle_toast = ToggleSwitch(
            parent=self, checked=self._config.get('general.toast_notification', True))
        self._toggles.append(self._toggle_toast)
        self._toggle_toast.toggled.connect(
            lambda v: self._mark('general.toast_notification', v))
        self._make_setting_row(card_notify.content_layout(), '显示清洗完成通知', self._toggle_toast)
        layout.addWidget(card_notify)

        # Card 2: Startup
        card_startup = Card('启动')
        self._cards.append(card_startup)
        self._toggle_startup = ToggleSwitch(
            parent=self, checked=self._config.get('general.startup_with_windows', False))
        self._toggles.append(self._toggle_startup)
        self._toggle_startup.toggled.connect(self._on_startup_changed)
        self._make_setting_row(card_startup.content_layout(), '开机自动启动', self._toggle_startup)
        layout.addWidget(card_startup)

        # Card 3: Appearance
        card_appearance = Card('外观')
        self._cards.append(card_appearance)

        # Row 1: UI theme
        self._seg_theme = SegmentedControl(['浅色', '深色'], parent=self)
        self._segmented_controls.append(self._seg_theme)
        self._seg_theme.setCurrentIndex(0 if self._theme == 'light' else 1)
        self._seg_theme.selectionChanged.connect(self._on_theme_changed)
        self._make_setting_row(card_appearance.content_layout(), '界面主题', self._seg_theme)

        # Row 2: Preview panel theme
        self._seg_preview_theme = SegmentedControl(['深色', '浅色'], parent=self)
        self._segmented_controls.append(self._seg_preview_theme)
        preview_theme_val = self._config.get('preview.theme', 'dark')
        self._seg_preview_theme.setCurrentIndex(0 if preview_theme_val == 'dark' else 1)
        self._seg_preview_theme.selectionChanged.connect(self._on_preview_theme_changed)
        self._make_setting_row(card_appearance.content_layout(), '预览面板主题', self._seg_preview_theme)

        layout.addWidget(card_appearance)

        layout.addStretch()
        scroll.setWidget(page)
        return scroll

    def _make_setting_row(self, parent_layout, label_text, *widgets):
        """Create a horizontal row: label on left (stretch), widgets on right."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 8, 0, 8)
        label = QLabel(label_text)
        label.setStyleSheet(f"color: {ColorPalette.get(self._theme)['fg']};")
        row.addWidget(label)
        row.addStretch()
        for w in widgets:
            row.addWidget(w)
        parent_layout.addLayout(row)

        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(
            f"background: {ColorPalette.get(self._theme)['border']}; "
            f"max-height: 1px; border: none;"
        )
        parent_layout.addWidget(line)
        return row

    # ── Hotkeys page (Page 1) ───────────────────────────────────────

    def _build_hotkeys_page(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName('content_scroll')
        page = QWidget()
        page.setObjectName('content_page')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # ── Card 1: 清洗触发 ──────────────────────────────────────────
        card_clean = Card('清洗触发')
        self._cards.append(card_clean)

        # Row 1: 独立热键 — ToggleSwitch + HotkeyBtn
        self._toggle_clean_hotkey = ToggleSwitch(
            parent=self, checked=self._config.get('general.custom_hotkey.enabled', True))
        self._toggles.append(self._toggle_clean_hotkey)
        self._toggle_clean_hotkey.toggled.connect(
            lambda v: self._mark('general.custom_hotkey.enabled', v))

        self._btn_clean_hotkey = QPushButton(
            self._config.get('general.custom_hotkey.keys', 'ctrl+shift+c'))
        self._btn_clean_hotkey.setObjectName('hotkey_btn')
        self._btn_clean_hotkey.setCheckable(True)
        self._btn_clean_hotkey.clicked.connect(self._on_clean_hotkey_btn)
        self._hotkey_buttons['clean'] = self._btn_clean_hotkey

        self._make_setting_row(card_clean.content_layout(), '独立热键',
                               self._toggle_clean_hotkey, self._btn_clean_hotkey)

        # Row 2: 双击 Ctrl+C — ToggleSwitch
        self._toggle_double_ctrl_c = ToggleSwitch(
            parent=self, checked=self._config.get('general.double_ctrl_c.enabled', False))
        self._toggles.append(self._toggle_double_ctrl_c)
        self._toggle_double_ctrl_c.toggled.connect(self._on_double_click_changed)
        self._make_setting_row(card_clean.content_layout(), '双击 Ctrl+C',
                               self._toggle_double_ctrl_c)

        # Row 3: 间隔阈值 — QSlider + QLabel (indented, disabled when double-click off)
        interval_row = QHBoxLayout()
        interval_row.setContentsMargins(16, 8, 0, 8)

        interval_label = QLabel('间隔阈值')
        c = ColorPalette.get(self._theme)
        interval_label.setStyleSheet(f"color: {c['fg']};")
        interval_row.addWidget(interval_label)
        interval_row.addStretch()

        self._sld_interval = QSlider(Qt.Orientation.Horizontal)
        self._sld_interval.setRange(100, 500)
        self._sld_interval.setSingleStep(50)
        self._sld_interval.setPageStep(50)
        self._sld_interval.setValue(self._config.get('general.double_ctrl_c.interval_ms', 300))
        self._sld_interval.setFixedWidth(140)
        interval_row.addWidget(self._sld_interval)

        self._lbl_interval = QLabel(f"{self._sld_interval.value()} ms")
        self._lbl_interval.setStyleSheet(f"color: {c['muted']};")
        self._lbl_interval.setFixedWidth(50)
        interval_row.addWidget(self._lbl_interval)

        self._sld_interval.valueChanged.connect(self._on_interval_changed)
        card_clean.content_layout().addLayout(interval_row)

        # Separator for interval row
        interval_sep = QFrame()
        interval_sep.setFrameShape(QFrame.Shape.HLine)
        interval_sep.setStyleSheet(
            f"background: {c['border']}; max-height: 1px; border: none;")
        card_clean.content_layout().addWidget(interval_sep)

        # Disable interval row when double-click is off
        double_enabled = self._config.get('general.double_ctrl_c.enabled', False)
        self._sld_interval.setEnabled(double_enabled)
        self._lbl_interval.setEnabled(double_enabled)

        layout.addWidget(card_clean)

        # ── Card 2: 功能快捷键 ────────────────────────────────────────
        card_features = Card('功能快捷键')
        self._cards.append(card_features)

        # Row 1: 轮盘选择器 — ToggleSwitch + HotkeyBtn
        self._toggle_wheel = ToggleSwitch(
            parent=self, checked=self._config.get('wheel.enabled', True))
        self._toggles.append(self._toggle_wheel)
        self._toggle_wheel.toggled.connect(self._on_wheel_enabled_changed)

        self._btn_wheel_hotkey = QPushButton(
            self._config.get('wheel.switch_hotkey', 'ctrl+shift+p'))
        self._btn_wheel_hotkey.setObjectName('hotkey_btn')
        self._btn_wheel_hotkey.setCheckable(True)
        self._btn_wheel_hotkey.clicked.connect(self._on_wheel_hotkey_btn)
        self._hotkey_buttons['wheel'] = self._btn_wheel_hotkey

        self._make_setting_row(card_features.content_layout(), '轮盘选择器',
                               self._toggle_wheel, self._btn_wheel_hotkey)

        # Row 2: QCheckBox — 随清洗热键触发时弹出轮盘 (indented)
        chk_row = QHBoxLayout()
        chk_row.setContentsMargins(16, 8, 0, 8)
        self._chk_wheel_trigger = QCheckBox('随清洗热键触发时弹出轮盘')
        self._chk_wheel_trigger.setChecked(
            self._config.get('wheel.trigger_with_clean', True))
        self._chk_wheel_trigger.toggled.connect(
            lambda v: self._mark('wheel.trigger_with_clean', v))
        wheel_enabled = self._config.get('wheel.enabled', True)
        self._chk_wheel_trigger.setEnabled(wheel_enabled)
        chk_row.addWidget(self._chk_wheel_trigger)
        chk_row.addStretch()
        card_features.content_layout().addLayout(chk_row)

        chk_sep = QFrame()
        chk_sep.setFrameShape(QFrame.Shape.HLine)
        chk_sep.setStyleSheet(
            f"background: {c['border']}; max-height: 1px; border: none;")
        card_features.content_layout().addWidget(chk_sep)

        # Row 3: 预览面板 — ToggleSwitch + HotkeyBtn
        self._toggle_preview = ToggleSwitch(
            parent=self, checked=self._config.get('preview.enabled', True))
        self._toggles.append(self._toggle_preview)
        self._toggle_preview.toggled.connect(
            lambda v: self._mark('preview.enabled', v))

        self._btn_preview_hotkey = QPushButton(
            self._config.get('preview.hotkey', 'ctrl+q'))
        self._btn_preview_hotkey.setObjectName('hotkey_btn')
        self._btn_preview_hotkey.setCheckable(True)
        self._btn_preview_hotkey.clicked.connect(self._on_preview_hotkey_btn)
        self._hotkey_buttons['preview'] = self._btn_preview_hotkey

        self._make_setting_row(card_features.content_layout(), '预览面板',
                               self._toggle_preview, self._btn_preview_hotkey)

        # Row 4: 历史记录 — ToggleSwitch + HotkeyBtn
        self._toggle_history = ToggleSwitch(
            parent=self, checked=self._config.get('history.enabled', True))
        self._toggles.append(self._toggle_history)
        self._toggle_history.toggled.connect(
            lambda v: self._mark('history.enabled', v))

        self._btn_history_hotkey = QPushButton(
            self._config.get('history.hotkey', 'ctrl+h'))
        self._btn_history_hotkey.setObjectName('hotkey_btn')
        self._btn_history_hotkey.setCheckable(True)
        self._btn_history_hotkey.clicked.connect(self._on_history_hotkey_btn)
        self._hotkey_buttons['history'] = self._btn_history_hotkey

        self._make_setting_row(card_features.content_layout(), '历史记录',
                               self._toggle_history, self._btn_history_hotkey)

        layout.addWidget(card_features)

        # ── Card 3: 历史记录 ──────────────────────────────────────────
        card_history = Card('历史记录')
        self._cards.append(card_history)

        # Row: 最大条数 — QSpinBox + "条" label
        spn_max = QSpinBox()
        spn_max.setRange(50, 2000)
        spn_max.setFixedWidth(80)
        spn_max.setValue(self._config.get('history.max_count', 500))
        spn_max.valueChanged.connect(
            lambda v: self._mark('history.max_count', v))
        lbl_suffix = QLabel('条')
        lbl_suffix.setStyleSheet(f"color: {c['muted']};")
        self._make_setting_row(card_history.content_layout(), '最大条数',
                               spn_max, lbl_suffix)

        layout.addWidget(card_history)

        layout.addStretch()
        scroll.setWidget(page)
        return scroll

    # ── Hotkey recording ────────────────────────────────────────────

    def _on_clean_hotkey_btn(self, checked: bool):
        if checked:
            self._cancel_other_recording('clean')
            self._btn_clean_hotkey.setText('请按下快捷键组合...')
            self.grabKeyboard()
            self._recording_target = 'clean'
            self._recording_timer.start(5000)
        else:
            self._release_recording()

    def _on_wheel_hotkey_btn(self, checked: bool):
        if checked:
            self._cancel_other_recording('wheel')
            self._btn_wheel_hotkey.setText('请按下快捷键组合...')
            self.grabKeyboard()
            self._recording_target = 'wheel'
            self._recording_timer.start(5000)
        else:
            self._release_recording()

    def _on_preview_hotkey_btn(self, checked: bool):
        if checked:
            self._cancel_other_recording('preview')
            self._btn_preview_hotkey.setText('请按下快捷键组合...')
            self.grabKeyboard()
            self._recording_target = 'preview'
            self._recording_timer.start(5000)
        else:
            self._release_recording()

    def _on_history_hotkey_btn(self, checked: bool):
        if checked:
            self._cancel_other_recording('history')
            self._btn_history_hotkey.setText('请按下快捷键组合...')
            self.grabKeyboard()
            self._recording_target = 'history'
            self._recording_timer.start(5000)
        else:
            self._release_recording()

    def _cancel_other_recording(self, current: str):
        """Uncheck all hotkey buttons except the one being activated."""
        for name, btn in self._hotkey_buttons.items():
            if name != current:
                btn.setChecked(False)

    def _release_recording(self):
        """Release keyboard and clear recording state."""
        self.releaseKeyboard()
        self._recording_target = None
        self._recording_timer.stop()

    def _on_recording_timeout(self):
        """Cancel hotkey recording after timeout."""
        target = self._recording_target
        if target and target in self._hotkey_buttons:
            config_map = {
                'clean': ('general.custom_hotkey.keys', 'ctrl+shift+c'),
                'wheel': ('wheel.switch_hotkey', 'ctrl+shift+p'),
                'preview': ('preview.hotkey', 'ctrl+q'),
                'history': ('history.hotkey', 'ctrl+h'),
            }
            key, default = config_map[target]
            self._hotkey_buttons[target].setText(self._config.get(key, default))
            self._hotkey_buttons[target].setChecked(False)
        self._release_recording()

    def keyPressEvent(self, event):
        """Capture hotkey recording."""
        target = getattr(self, '_recording_target', None)
        if target is None:
            return super().keyPressEvent(event)

        key = event.key()
        mods = event.modifiers()

        # Ignore pure modifier keys
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift,
                   Qt.Key.Key_Alt, Qt.Key.Key_Meta, Qt.Key.Key_unknown):
            return

        parts = []
        if mods & Qt.KeyboardModifier.ControlModifier:
            parts.append('ctrl')
        if mods & Qt.KeyboardModifier.ShiftModifier:
            parts.append('shift')
        if mods & Qt.KeyboardModifier.AltModifier:
            parts.append('alt')

        try:
            key_name = Qt.Key(key).name.replace('Key_', '').lower()
        except (ValueError, KeyError):
            key_name = ''
        if key_name:
            parts.append(key_name)

        if len(parts) >= 2:
            hotkey_str = '+'.join(parts)
            config_map = {
                'clean': 'general.custom_hotkey.keys',
                'wheel': 'wheel.switch_hotkey',
                'preview': 'preview.hotkey',
                'history': 'history.hotkey',
            }
            self._hotkey_buttons[target].setText(hotkey_str)
            self._mark(config_map[target], hotkey_str)

        self._hotkey_buttons[target].setChecked(False)
        self._release_recording()

    # ── Hotkey page toggles ────────────────────────────────────────

    def _on_wheel_enabled_changed(self, checked: bool):
        self._mark('wheel.enabled', checked)
        self._chk_wheel_trigger.setEnabled(checked)

    def _on_double_click_changed(self, checked: bool):
        self._mark('general.double_ctrl_c.enabled', checked)
        self._sld_interval.setEnabled(checked)
        self._lbl_interval.setEnabled(checked)

    def _on_interval_changed(self, value: int):
        self._lbl_interval.setText(f"{value} ms")
        self._mark('general.double_ctrl_c.interval_ms', value)

    # ── Rules page (Page 2) ──────────────────────────────────────────

    def _build_rules_page(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName('content_scroll')
        page = QWidget()
        page.setObjectName('content_page')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Card 1: 清洗模式
        card_mode = Card('清洗模式')
        self._cards.append(card_mode)
        self._seg_mode = SegmentedControl(
            ['规则模式', '大模型模式'], parent=self, full_width=True)
        self._segmented_controls.append(self._seg_mode)
        current_mode = self._config.get('rules.mode', 'rules')
        self._seg_mode.setCurrentIndex(0 if current_mode == 'rules' else 1)
        self._seg_mode.selectionChanged.connect(self._on_mode_changed)
        card_mode.content_layout().addWidget(self._seg_mode)
        layout.addWidget(card_mode)

        # Card 2: 规则开关
        card_rules = Card('规则开关', description='规则模式下生效')
        self._cards.append(card_rules)
        for key, (label_text, hint_text) in RULE_LABELS.items():
            chk = QCheckBox(label_text)
            chk.setToolTip(hint_text)
            chk.setChecked(self._config.get(f'rules.{key}', True))
            chk.toggled.connect(lambda v, k=key: self._mark(f'rules.{k}', bool(v)))
            card_rules.content_layout().addWidget(chk)
            # Separator between rule checkboxes
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet(
                f"background: {ColorPalette.get(self._theme)['border']}; "
                f"max-height: 1px; border: none;")
            card_rules.content_layout().addWidget(sep)
        layout.addWidget(card_rules)

        layout.addStretch()
        scroll.setWidget(page)
        return scroll

    def _on_mode_changed(self, index: int):
        """Handle cleaning mode segmented control change."""
        mode = 'rules' if index == 0 else 'llm'
        self._mark('rules.mode', mode)
        # If user selected LLM mode, switch to LLM page
        if mode == 'llm':
            self._sidebar.setCurrentIndex(3)  # LLM page

    def _build_llm_page(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName('content_scroll')
        page = QWidget()
        page.setObjectName('content_page')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        label = QLabel('大模型设置（开发中）')
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        layout.addStretch()
        scroll.setWidget(page)
        return scroll

    def _build_about_page(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName('content_scroll')
        page = QWidget()
        page.setObjectName('content_page')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        label = QLabel('关于（开发中）')
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        layout.addStretch()
        scroll.setWidget(page)
        return scroll

    # ── Theme ───────────────────────────────────────────────────────

    def _apply_theme(self):
        """Apply the current theme to the window and all child widgets."""
        c = ColorPalette.get(self._theme)
        self.setStyleSheet(get_settings_stylesheet(self._theme))

        # Title bar styling
        titlebar = self.findChild(QWidget, 'titlebar')
        if titlebar:
            titlebar.setStyleSheet(f"""
                QWidget#titlebar {{
                    background: {c['bg']};
                    border-bottom: 1px solid {c['border']};
                }}
                QLabel#titlebar_title {{
                    color: {c['fg']};
                    font-size: 14px;
                    font-weight: 600;
                }}
                QPushButton#titlebar_close {{
                    background: transparent;
                    border: none;
                    border-radius: 6px;
                    color: {c['muted']};
                    font-size: 16px;
                    padding: 4px;
                }}
                QPushButton#titlebar_close:hover {{
                    background: #ef4444;
                    color: white;
                }}
            """)

        # Sidebar
        if hasattr(self, '_sidebar'):
            self._sidebar.set_theme(self._theme)

        # Cards
        for card in self._cards:
            card.set_theme(self._theme)

        # Toggle switches
        for toggle in self._toggles:
            toggle.set_theme(self._theme)

        # Segmented controls
        for seg in self._segmented_controls:
            seg.set_theme(self._theme)

    def _on_theme_changed(self, index: int):
        """Handle UI theme segmented control change."""
        theme = 'light' if index == 0 else 'dark'
        self._theme = theme
        self._mark('ui.theme', theme)
        self._apply_theme()

    def _on_preview_theme_changed(self, index: int):
        """Handle preview panel theme segmented control change."""
        theme = 'dark' if index == 0 else 'light'
        self._mark('preview.theme', theme)

    # ── Startup ─────────────────────────────────────────────────────

    def _on_startup_changed(self, checked: bool):
        """Handle startup toggle: update registry immediately."""
        self._mark('general.startup_with_windows', checked)
        if checked:
            ok, msg = _autostart_enable()
            if not ok and msg:
                QMessageBox.warning(self, '开机自启动', msg)
        else:
            _autostart_disable()

    # ── Window dragging ─────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and hasattr(self, '_drag_pos') and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # ── Save ────────────────────────────────────────────────────────

    def _mark(self, key: str, value):
        """Mark a config key as pending save."""
        self._pending[key] = value

    def _do_save(self):
        """Save all pending changes to config."""
        for key, value in self._pending.items():
            self._config.set(key, value)
        self._pending.clear()
        if self._hotkey_manager:
            self._hotkey_manager.reload_config(self._config)
        self._status_lbl.setText('已保存 ✓')
        QTimer.singleShot(1500, lambda: self._status_lbl.setText(''))

    # ── Close event ─────────────────────────────────────────────────

    def closeEvent(self, event):
        if self._pending:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle('未保存的修改')
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setText('设置已更改但尚未保存，关闭后修改将丢失。')
            msg_box.setInformativeText('是否保存更改？')
            btn_save = msg_box.addButton('保存', QMessageBox.ButtonRole.AcceptRole)
            btn_discard = msg_box.addButton('不保存', QMessageBox.ButtonRole.DestructiveRole)
            btn_cancel = msg_box.addButton('取消', QMessageBox.ButtonRole.RejectRole)
            msg_box.setDefaultButton(btn_save)
            msg_box.setMinimumWidth(480)
            for btn in (btn_save, btn_discard, btn_cancel):
                btn.setMinimumWidth(90)
            msg_box.exec()
            clicked = msg_box.clickedButton()
            if clicked == btn_save:
                self._do_save()
            elif clicked == btn_cancel:
                event.ignore()
                return
            # btn_discard: just close
        super().closeEvent(event)
