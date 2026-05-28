# 设置界面：自定义标题栏 + 侧边栏导航 + Card 分组布局（Shadcn 风格）
import uuid
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QCheckBox, QSlider, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem,
    QTextEdit, QInputDialog, QMessageBox, QMenu,
    QStackedWidget, QFrame, QScrollArea, QSpinBox,
)
from PyQt6.QtGui import QIcon, QCursor
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices

from version import VERSION
from assets import asset as _asset
from autostart_manager import enable as _autostart_enable, disable as _autostart_disable
from ui.styles import get_settings_stylesheet, ColorPalette, FONT_MONO, FONT_SIZE_XS
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
        self._theme = 'light'
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
        self._titlebar = self._build_titlebar()
        root.addWidget(self._titlebar)

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
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(0)

        title_label = QLabel('设置')
        title_label.setObjectName('titlebar_title')
        layout.addWidget(title_label)
        layout.addStretch()

        close_btn = QPushButton('✕')
        close_btn.setObjectName('titlebar_close')
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        return titlebar

    def _build_footer(self) -> QWidget:
        """Build footer bar (52px) with status label, reset and save buttons."""
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

        self._btn_reset = QPushButton('重置全部')
        self._btn_reset.setObjectName('btn_reset')
        self._btn_reset.clicked.connect(self._on_reset_all)
        layout.addWidget(self._btn_reset)

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
        self._make_setting_row(card_notify.content_layout(), '显示清洗完成通知', self._toggle_toast, separator=False)
        layout.addWidget(card_notify)

        # Card 2: Startup
        card_startup = Card('启动')
        self._cards.append(card_startup)
        self._toggle_startup = ToggleSwitch(
            parent=self, checked=self._config.get('general.startup_with_windows', False))
        self._toggles.append(self._toggle_startup)
        self._toggle_startup.toggled.connect(self._on_startup_changed)
        self._make_setting_row(card_startup.content_layout(), '开机自动启动', self._toggle_startup, separator=False)
        layout.addWidget(card_startup)

        # Card 3: Appearance
        card_appearance = Card('外观')
        self._cards.append(card_appearance)

        self._seg_preview_theme = SegmentedControl(['浅色', '深色'], parent=self)
        self._segmented_controls.append(self._seg_preview_theme)
        preview_theme_val = self._config.get('preview.theme', 'dark')
        self._seg_preview_theme.setCurrentIndex(0 if preview_theme_val == 'light' else 1)
        self._seg_preview_theme.selectionChanged.connect(self._on_preview_theme_changed)
        self._make_setting_row(card_appearance.content_layout(), '预览面板主题', self._seg_preview_theme, separator=False)

        layout.addWidget(card_appearance)

        layout.addStretch()
        scroll.setWidget(page)
        return scroll

    def _make_setting_row(self, parent_layout, label_text, *widgets, separator=True):
        """Create a horizontal row: label on left (stretch), widgets on right."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 12, 0, 12)
        row.setSpacing(16)
        label = QLabel(label_text)
        label.setStyleSheet(f"color: {ColorPalette.get(self._theme)['fg']}; background: transparent;")
        row.addWidget(label)
        row.addStretch()
        for w in widgets:
            row.addWidget(w)
        parent_layout.addLayout(row)

        # Separator line (only between rows, not after the last)
        if separator:
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
                               self._toggle_double_ctrl_c, separator=False)

        # Row 3: 间隔阈值 — QSlider + QLabel (indented, disabled when double-click off)
        interval_row = QHBoxLayout()
        interval_row.setContentsMargins(0, 12, 0, 12)

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
        self._sld_interval.setFixedWidth(200)
        interval_row.addWidget(self._sld_interval)

        self._lbl_interval = QLabel(f"{self._sld_interval.value()} ms")
        self._lbl_interval.setStyleSheet(
            f"color: {c['muted']}; font-family: {FONT_MONO}; font-size: {FONT_SIZE_XS}; background: transparent;")
        self._lbl_interval.setFixedWidth(56)
        self._lbl_interval.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        interval_row.addWidget(self._lbl_interval)

        self._sld_interval.valueChanged.connect(self._on_interval_changed)
        card_clean.content_layout().addLayout(interval_row)

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
        chk_row.setContentsMargins(16, 12, 0, 12)
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
                               self._toggle_history, self._btn_history_hotkey, separator=False)

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
                               spn_max, lbl_suffix, separator=False)

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
            # Hint label below checkbox (visible, per design)
            c = ColorPalette.get(self._theme)
            hint_lbl = QLabel(hint_text)
            hint_lbl.setStyleSheet(f"""
                color: {c['muted']};
                font-size: {FONT_SIZE_XS};
                padding: 0 0 0 22px;
                background: transparent;
                border: none;
            """)
            card_rules.content_layout().addWidget(hint_lbl)
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
        layout.setSpacing(16)

        # ── Page-level: 启用大模型模式 (not in a card) ──
        self._toggle_llm = ToggleSwitch(
            parent=self, checked=self._config.get('rules.mode') == 'llm')
        self._toggles.append(self._toggle_llm)
        self._toggle_llm.toggled.connect(self._on_llm_toggled)

        enable_row = QHBoxLayout()
        enable_row.setContentsMargins(0, 0, 0, 16)
        lbl_enable = QLabel('启用大模型模式')
        c = ColorPalette.get(self._theme)
        lbl_enable.setStyleSheet(f"color: {c['fg']}; font-weight: 600;")
        enable_row.addWidget(lbl_enable)
        enable_row.addStretch()
        enable_row.addWidget(self._toggle_llm)
        layout.addLayout(enable_row)

        # ── Card 1: API配置 ──
        card_api = Card('API配置')
        self._cards.append(card_api)
        cl = card_api.content_layout()

        # Row 1: Base URL (label uses text-xs per design)
        row_url = QHBoxLayout()
        row_url.setContentsMargins(0, 12, 0, 0)
        row_url.setSpacing(24)
        lbl_url = QLabel('Base URL')
        lbl_url.setStyleSheet(f"color: {c['fg']}; font-size: {FONT_SIZE_XS}; background: transparent;")
        lbl_url.setFixedWidth(92)
        lbl_url.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        row_url.addWidget(lbl_url)
        self._le_base_url = QLineEdit(
            str(self._config.get('llm.base_url', 'https://api.openai.com/v1')))
        self._le_base_url.setMinimumWidth(260)
        self._le_base_url.setPlaceholderText('https://api.openai.com/v1')
        self._le_base_url.textChanged.connect(lambda t: self._mark('llm.base_url', t))
        row_url.addWidget(self._le_base_url, 1)
        cl.addLayout(row_url)

        url_sep = QFrame()
        url_sep.setFrameShape(QFrame.Shape.HLine)
        url_sep.setStyleSheet(f"background: {c['border']}; max-height: 1px; border: none;")
        cl.addWidget(url_sep)

        # Row 2: Model ID (label uses text-xs per design)
        row_model = QHBoxLayout()
        row_model.setContentsMargins(0, 12, 0, 0)
        row_model.setSpacing(24)
        lbl_model = QLabel('Model ID')
        lbl_model.setStyleSheet(f"color: {c['fg']}; font-size: {FONT_SIZE_XS}; background: transparent;")
        lbl_model.setFixedWidth(92)
        lbl_model.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        row_model.addWidget(lbl_model)
        self._le_model_id = QLineEdit(
            str(self._config.get('llm.model_id', 'gpt-4o-mini')))
        self._le_model_id.setMinimumWidth(260)
        self._le_model_id.setPlaceholderText('gpt-4o-mini')
        self._le_model_id.textChanged.connect(lambda t: self._mark('llm.model_id', t))
        row_model.addWidget(self._le_model_id, 1)
        cl.addLayout(row_model)

        model_sep = QFrame()
        model_sep.setFrameShape(QFrame.Shape.HLine)
        model_sep.setStyleSheet(f"background: {c['border']}; max-height: 1px; border: none;")
        cl.addWidget(model_sep)

        # Row 3: API Key (password + show/hide toggle)
        key_row = QHBoxLayout()
        key_row.setContentsMargins(0, 8, 0, 8)
        key_row.setSpacing(24)
        lbl_key = QLabel('API Key')
        lbl_key.setStyleSheet(f"color: {c['fg']}; font-size: {FONT_SIZE_XS};")
        lbl_key.setFixedWidth(92)
        lbl_key.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        key_row.addWidget(lbl_key)

        self._le_apikey = QLineEdit(self._config.get('llm.api_key', ''))
        self._le_apikey.setMinimumWidth(260)
        self._le_apikey.setEchoMode(QLineEdit.EchoMode.Password)
        self._le_apikey.setPlaceholderText('sk-...')
        self._le_apikey.textChanged.connect(lambda t: self._mark('llm.api_key', t))
        key_row.addWidget(self._le_apikey, 1)

        self._btn_show_key = QPushButton('显示')
        self._btn_show_key.setCheckable(True)
        self._btn_show_key.setFixedWidth(50)
        self._btn_show_key.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_show_key.setStyleSheet(f"""
            QPushButton {{
                background: none;
                border: none;
                font-size: {FONT_SIZE_XS};
                color: {c['muted']};
            }}
            QPushButton:hover {{
                color: {c['fg']};
            }}
        """)
        self._btn_show_key.toggled.connect(self._on_toggle_apikey_visibility)
        key_row.addWidget(self._btn_show_key)
        cl.addLayout(key_row)

        key_sep = QFrame()
        key_sep.setFrameShape(QFrame.Shape.HLine)
        key_sep.setStyleSheet(f"background: {c['border']}; max-height: 1px; border: none;")
        cl.addWidget(key_sep)

        # Row 4: Temperature slider + label
        temp_row = QHBoxLayout()
        temp_row.setContentsMargins(0, 12, 0, 12)
        temp_row.setSpacing(24)
        lbl_temp = QLabel('Temperature')
        lbl_temp.setStyleSheet(f"color: {c['fg']}; font-size: {FONT_SIZE_XS}; background: transparent;")
        lbl_temp.setFixedWidth(92)
        lbl_temp.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        temp_row.addWidget(lbl_temp)

        self._sld_temp = QSlider(Qt.Orientation.Horizontal)
        self._sld_temp.setRange(0, 20)
        temp_val = self._config.get('llm.temperature', 0.2)
        self._sld_temp.setValue(int(temp_val * 10))
        self._sld_temp.setMinimumWidth(200)
        self._sld_temp.valueChanged.connect(self._on_temp_changed)
        temp_row.addWidget(self._sld_temp, 1)

        self._lbl_temp_val = QLabel(f'{temp_val:.1f}')
        self._lbl_temp_val.setStyleSheet(f"color: {c['muted']}; font-family: {FONT_MONO}; font-size: {FONT_SIZE_XS}; background: transparent;")
        self._lbl_temp_val.setFixedWidth(56)
        self._lbl_temp_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        temp_row.addWidget(self._lbl_temp_val)
        cl.addLayout(temp_row)

        temp_sep = QFrame()
        temp_sep.setFrameShape(QFrame.Shape.HLine)
        temp_sep.setStyleSheet(f"background: {c['border']}; max-height: 1px; border: none;")
        cl.addWidget(temp_sep)

        # Row 5: 超时时长 spinbox
        self._spin_timeout = QSpinBox()
        self._spin_timeout.setRange(10, 300)
        self._spin_timeout.setFixedWidth(72)
        self._spin_timeout.setValue(int(self._config.get('llm.timeout', 30)))
        self._spin_timeout.setToolTip('LLM 请求最大等待时间（10-300 秒）')
        self._spin_timeout.valueChanged.connect(lambda v: self._mark('llm.timeout', v))
        lbl_sec = QLabel('秒')
        lbl_sec.setStyleSheet(f"color: {c['muted']};")
        self._make_setting_row(cl, '超时时长', self._spin_timeout, lbl_sec, separator=False)

        layout.addWidget(card_api)

        # ── Bottom row: 测试连接 + 恢复默认 (outside card) ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self._btn_test = QPushButton('测试连接')
        self._btn_test.clicked.connect(self._on_test_connection)
        btn_row.addWidget(self._btn_test)
        btn_reset_llm = QPushButton('恢复默认')
        btn_reset_llm.setObjectName('btn_reset')
        btn_reset_llm.clicked.connect(self._confirm_and_reset_llm_api)
        btn_row.addWidget(btn_reset_llm)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # ── Card 2: Prompt模板 ──
        card_prompts = Card('Prompt模板')
        self._cards.append(card_prompts)
        pl = card_prompts.content_layout()

        self._prompt_list = QListWidget()
        self._prompt_list.setMinimumHeight(150)
        self._prompt_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._prompt_list.customContextMenuRequested.connect(self._show_prompt_menu)
        self._prompt_list.itemDoubleClicked.connect(
            lambda item: self._edit_prompt_by_id(item.data(Qt.ItemDataRole.UserRole)))
        self._refresh_prompts()
        pl.addWidget(self._prompt_list)

        prompt_btn_row = QHBoxLayout()
        prompt_btn_row.setContentsMargins(0, 12, 0, 0)
        prompt_btn_row.setSpacing(12)
        btn_add = QPushButton('+ 新增模板')
        btn_add.clicked.connect(self._on_add_prompt)
        prompt_btn_row.addWidget(btn_add)
        btn_wheel_mgmt = QPushButton('管理轮盘')
        btn_wheel_mgmt.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                padding: 4px 12px;
                min-height: 24px;
                color: {c['muted']};
                font-size: {FONT_SIZE_XS};
                font-weight: 500;
            }}
            QPushButton:hover {{
                color: {c['fg']};
                background: {c['fg_soft']};
            }}
        """)
        btn_wheel_mgmt.clicked.connect(self._show_wheel_modal)
        prompt_btn_row.addWidget(btn_wheel_mgmt)
        prompt_btn_row.addStretch()
        pl.addLayout(prompt_btn_row)

        layout.addWidget(card_prompts)

        # ── Card 3: 轮盘 Prompt 选择 ──
        card_wheel = Card('轮盘 Prompt 选择')
        self._cards.append(card_wheel)
        wl = card_wheel.content_layout()

        columns = QHBoxLayout()

        # Left column: available templates
        left_lay = QVBoxLayout()
        lbl_left = QLabel('可用模板')
        lbl_left.setStyleSheet(f"color: {c['muted']}; font-size: {FONT_SIZE_XS}; font-weight: 600; background: transparent;")
        left_lay.addWidget(lbl_left)
        self._wheel_all_list = QListWidget()
        self._wheel_all_list.setMinimumHeight(150)
        self._wheel_all_list.itemChanged.connect(self._on_wheel_all_item_changed)
        self._refresh_wheel_all_list()
        left_lay.addWidget(self._wheel_all_list)
        columns.addLayout(left_lay, 1)

        # Right column: selected templates
        right_lay = QVBoxLayout()
        lbl_right = QLabel(f'轮盘模板（最多{self.MAX_WHEEL_PROMPTS}个）')
        lbl_right.setStyleSheet(f"color: {c['muted']}; font-size: {FONT_SIZE_XS}; font-weight: 600; background: transparent;")
        right_lay.addWidget(lbl_right)
        self._wheel_selected_list = QListWidget()
        self._wheel_selected_list.setMinimumHeight(150)
        self._refresh_wheel_selected_list()
        right_lay.addWidget(self._wheel_selected_list)
        columns.addLayout(right_lay, 1)

        wl.addLayout(columns)

        tip = QLabel('提示：勾选左侧模板添加到轮盘')
        tip.setStyleSheet(f"color: {c['muted']}; font-size: {FONT_SIZE_XS}; background: transparent;")
        wl.addWidget(tip)

        layout.addWidget(card_wheel)

        layout.addStretch()
        scroll.setWidget(page)
        return scroll

    # ── LLM page helpers ────────────────────────────────────────────

    def _on_llm_toggled(self, checked: bool):
        mode = 'llm' if checked else 'rules'
        self._mark('rules.mode', mode)
        if hasattr(self, '_seg_mode'):
            self._seg_mode.blockSignals(True)
            self._seg_mode.setCurrentIndex(0 if mode == 'rules' else 1)
            self._seg_mode.blockSignals(False)

    def _on_toggle_apikey_visibility(self, checked: bool):
        if checked:
            self._le_apikey.setEchoMode(QLineEdit.EchoMode.Normal)
            self._btn_show_key.setText('隐藏')
        else:
            self._le_apikey.setEchoMode(QLineEdit.EchoMode.Password)
            self._btn_show_key.setText('显示')

    def _on_temp_changed(self, value: int):
        temp = value / 10.0
        self._lbl_temp_val.setText(f'{temp:.1f}')
        self._mark('llm.temperature', temp)

    def _refresh_prompts(self):
        self._prompt_list.clear()
        prompts = self._config.get('llm.prompts') or []
        active_id = self._config.get('llm.active_prompt_id', 'default')
        for p in prompts:
            tag = '[默认] ' if p['id'] == active_id else ''
            lock = ' 🔒' if p.get('readonly') else ''
            item = QListWidgetItem(f"{tag}{p['name']}{lock}")
            item.setData(Qt.ItemDataRole.UserRole, p['id'])
            self._prompt_list.addItem(item)
        if hasattr(self, '_wheel_all_list'):
            self._refresh_wheel_all_list()
            self._refresh_wheel_selected_list()

    def _show_prompt_menu(self, pos):
        item = self._prompt_list.itemAt(pos)
        if not item:
            return
        pid = item.data(Qt.ItemDataRole.UserRole)
        prompts = self._config.get('llm.prompts') or []
        prompt = next((p for p in prompts if p['id'] == pid), None)
        if not prompt:
            return

        menu = QMenu(self)
        act_default = menu.addAction('设为默认')
        act_edit = menu.addAction('编辑')
        act_del = menu.addAction('删除')
        act_del.setEnabled(not prompt.get('readonly', False))
        action = menu.exec(self._prompt_list.mapToGlobal(pos))

        if action == act_default:
            self._mark('llm.active_prompt_id', pid)
            self._do_save()
            self._refresh_prompts()
        elif action == act_edit:
            self._edit_prompt_by_id(pid)
        elif action == act_del:
            new_prompts = [p for p in prompts if p['id'] != pid]
            self._mark('llm.prompts', new_prompts)
            self._do_save()
            self._refresh_prompts()

    def _edit_prompt_by_id(self, pid: str):
        prompts = list(self._config.get('llm.prompts') or [])
        prompt = next((p for p in prompts if p['id'] == pid), None)
        if not prompt:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f'编辑：{prompt["name"]}')
        dlg.resize(500, 320)
        v = QVBoxLayout(dlg)
        editor = QTextEdit()
        editor.setPlainText(prompt['content'])
        v.addWidget(editor)
        btn_ok = QPushButton('保存')
        btn_ok.clicked.connect(dlg.accept)
        v.addWidget(btn_ok)
        if dlg.exec():
            for p in prompts:
                if p['id'] == pid:
                    p['content'] = editor.toPlainText()
            self._mark('llm.prompts', prompts)
            self._do_save()

    def _on_add_prompt(self):
        name, ok = QInputDialog.getText(self, '新增 Prompt', '模板名称：')
        if not ok or not name.strip():
            return
        new_prompt = {
            'id': str(uuid.uuid4()),
            'name': name.strip(),
            'content': '',
            'readonly': False,
        }
        dlg = QDialog(self)
        dlg.setWindowTitle(f'编辑：{new_prompt["name"]}')
        dlg.resize(500, 320)
        v = QVBoxLayout(dlg)
        editor = QTextEdit()
        editor.setPlaceholderText('在此输入 Prompt 内容...')
        v.addWidget(editor)
        btn_ok = QPushButton('保存')
        btn_ok.clicked.connect(dlg.accept)
        v.addWidget(btn_ok)
        if dlg.exec():
            new_prompt['content'] = editor.toPlainText()
            prompts = list(self._config.get('llm.prompts') or [])
            prompts.append(new_prompt)
            self._mark('llm.prompts', prompts)
            self._do_save()
            self._refresh_prompts()

    def _on_test_connection(self):
        self._do_save()
        llm_cfg = self._config.get('llm') or {}
        self._btn_test.setEnabled(False)
        self._btn_test.setText('测试中...')

        from PyQt6.QtCore import QThread as _QT
        from PyQt6.QtCore import pyqtSignal as _sig

        class _TestWorker(_QT):
            success = _sig(str)
            error = _sig(str)

            def __init__(self, cfg):
                super().__init__()
                self._cfg = cfg

            def run(self):
                try:
                    import httpx
                    headers = {'Authorization': f'Bearer {self._cfg.get("api_key", "")}'}
                    payload = {
                        'model': self._cfg.get('model_id', 'gpt-4o-mini'),
                        'temperature': self._cfg.get('temperature', 0.2),
                        'messages': [
                            {'role': 'system', 'content': '请原样返回我发送给你的文字，不做任何修改。'},
                            {'role': 'user', 'content': '测试文本：hello world'},
                        ],
                    }
                    base_url = self._cfg.get('base_url', 'https://api.openai.com/v1').rstrip('/')
                    timeout = float(self._cfg.get('timeout', 30))
                    with httpx.Client(timeout=timeout) as client:
                        resp = client.post(f'{base_url}/chat/completions',
                                           json=payload, headers=headers)
                        resp.raise_for_status()
                        content = resp.json()['choices'][0]['message']['content']
                        self.success.emit(content)
                except Exception as e:
                    from llm_client import classify_error
                    self.error.emit(classify_error(e, timeout=int(self._cfg.get('timeout', 30))))

        worker = _TestWorker(llm_cfg)

        def _on_success(r):
            QMessageBox.information(self, '连接成功', f'模型回复：{r[:200]}')
            self._btn_test.setEnabled(True)
            self._btn_test.setText('测试连接')

        def _on_error(e):
            QMessageBox.critical(self, '连接失败', e)
            self._btn_test.setEnabled(True)
            self._btn_test.setText('测试连接')

        worker.success.connect(_on_success)
        worker.error.connect(_on_error)
        worker.start()
        self._test_worker = worker

    def _confirm_and_reset_llm_api(self):
        reply = QMessageBox.question(
            self, '确认恢复默认',
            '确定要将 API 配置（Base URL、Model ID、API Key、Temperature、超时时长）恢复为默认值吗？\n'
            'API Key 将被清空，Prompt 模板不受影响。此操作不可撤销。',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        from config_manager import DEFAULT_CONFIG
        llm = DEFAULT_CONFIG['llm']
        self._mark('llm.base_url',    llm['base_url'])
        self._mark('llm.model_id',    llm['model_id'])
        self._mark('llm.api_key',     llm['api_key'])
        self._mark('llm.temperature', llm['temperature'])
        self._mark('llm.timeout',     llm['timeout'])
        # Refresh UI widgets
        self._le_base_url.blockSignals(True)
        self._le_base_url.setText(llm['base_url'])
        self._le_base_url.blockSignals(False)
        self._le_model_id.blockSignals(True)
        self._le_model_id.setText(llm['model_id'])
        self._le_model_id.blockSignals(False)
        self._le_apikey.blockSignals(True)
        self._le_apikey.setText(llm['api_key'])
        self._le_apikey.blockSignals(False)
        self._sld_temp.blockSignals(True)
        self._sld_temp.setValue(int(llm['temperature'] * 10))
        self._sld_temp.blockSignals(False)
        self._lbl_temp_val.setText(f'{llm["temperature"]:.1f}')
        self._spin_timeout.blockSignals(True)
        self._spin_timeout.setValue(llm['timeout'])
        self._spin_timeout.blockSignals(False)
        self._do_save()

    def _refresh_wheel_all_list(self):
        self._wheel_all_list.blockSignals(True)
        self._wheel_all_list.clear()
        prompts = self._config.get('llm.prompts') or []
        for p in prompts:
            item = QListWidgetItem(p['name'])
            item.setData(Qt.ItemDataRole.UserRole, p['id'])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if p.get('visible_in_wheel', True)
                else Qt.CheckState.Unchecked
            )
            self._wheel_all_list.addItem(item)
        self._wheel_all_list.blockSignals(False)

    def _refresh_wheel_selected_list(self):
        self._wheel_selected_list.clear()
        prompts = self._config.get('llm.prompts') or []
        selected = [p for p in prompts if p.get('visible_in_wheel', True)]
        for i, p in enumerate(selected[:self.MAX_WHEEL_PROMPTS], start=1):
            item = QListWidgetItem(f'{i}. {p["name"]}')
            item.setData(Qt.ItemDataRole.UserRole, p['id'])
            self._wheel_selected_list.addItem(item)

    def _on_wheel_all_item_changed(self, item: QListWidgetItem):
        checked_count = sum(
            1 for i in range(self._wheel_all_list.count())
            if self._wheel_all_list.item(i).checkState() == Qt.CheckState.Checked
        )
        if checked_count > self.MAX_WHEEL_PROMPTS:
            self._wheel_all_list.blockSignals(True)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._wheel_all_list.blockSignals(False)
            self._status_lbl.setText(f'轮盘最多显示{self.MAX_WHEEL_PROMPTS}个 Prompt')
            QTimer.singleShot(2000, lambda: self._status_lbl.setText(''))
            return

        prompts = list(self._config.get('llm.prompts') or [])
        for i in range(self._wheel_all_list.count()):
            list_item = self._wheel_all_list.item(i)
            pid = list_item.data(Qt.ItemDataRole.UserRole)
            visible = list_item.checkState() == Qt.CheckState.Checked
            for p in prompts:
                if p['id'] == pid:
                    p['visible_in_wheel'] = visible
        self._mark('llm.prompts', prompts)
        self._refresh_wheel_selected_list()

    def _show_wheel_modal(self):
        dlg = QDialog(self)
        dlg.setWindowTitle('管理轮盘 Prompt')
        dlg.resize(420, 360)
        v = QVBoxLayout(dlg)

        columns = QHBoxLayout()
        c = ColorPalette.get(self._theme)

        # Left: available templates
        left_lay = QVBoxLayout()
        lbl_left = QLabel('可用模板')
        lbl_left.setStyleSheet(f"color: {c['muted']}; font-size: {FONT_SIZE_XS}; font-weight: 600; background: transparent;")
        left_lay.addWidget(lbl_left)
        modal_all = QListWidget()
        modal_all.setMinimumHeight(200)
        prompts = self._config.get('llm.prompts') or []
        for p in prompts:
            mi = QListWidgetItem(p['name'])
            mi.setData(Qt.ItemDataRole.UserRole, p['id'])
            mi.setFlags(mi.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            mi.setCheckState(
                Qt.CheckState.Checked if p.get('visible_in_wheel', True)
                else Qt.CheckState.Unchecked
            )
            modal_all.addItem(mi)
        left_lay.addWidget(modal_all)
        columns.addLayout(left_lay, 1)

        # Right: selected templates
        right_lay = QVBoxLayout()
        lbl_right = QLabel(f'轮盘模板（最多{self.MAX_WHEEL_PROMPTS}个）')
        lbl_right.setStyleSheet(f"color: {c['muted']}; font-size: {FONT_SIZE_XS}; font-weight: 600; background: transparent;")
        right_lay.addWidget(lbl_right)
        modal_selected = QListWidget()
        modal_selected.setMinimumHeight(200)

        def _refresh_modal_selected():
            modal_selected.clear()
            checked = []
            for j in range(modal_all.count()):
                ai = modal_all.item(j)
                if ai.checkState() == Qt.CheckState.Checked:
                    checked.append(ai.text())
            for idx, name in enumerate(checked[:self.MAX_WHEEL_PROMPTS], 1):
                si = QListWidgetItem(f'{idx}. {name}')
                modal_selected.addItem(si)

        modal_all.itemChanged.connect(_refresh_modal_selected)
        _refresh_modal_selected()
        right_lay.addWidget(modal_selected)
        columns.addLayout(right_lay, 1)

        v.addLayout(columns)

        tip = QLabel('提示：勾选左侧模板添加到轮盘')
        tip.setStyleSheet(f"color: {c['muted']}; font-size: {FONT_SIZE_XS}; background: transparent;")
        v.addWidget(tip)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_ok = QPushButton('保存')
        btn_ok.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_ok)
        btn_cancel = QPushButton('取消')
        btn_cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(btn_cancel)
        v.addLayout(btn_row)

        if dlg.exec():
            # Collect check states and sync
            updated_prompts = list(self._config.get('llm.prompts') or [])
            for j in range(modal_all.count()):
                mi = modal_all.item(j)
                pid = mi.data(Qt.ItemDataRole.UserRole)
                visible = mi.checkState() == Qt.CheckState.Checked
                for p in updated_prompts:
                    if p['id'] == pid:
                        p['visible_in_wheel'] = visible
            self._mark('llm.prompts', updated_prompts)
            self._do_save()
            self._refresh_wheel_all_list()
            self._refresh_wheel_selected_list()

    def _build_about_page(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName('content_scroll')

        page = QWidget()
        page.setObjectName('content_page')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 48, 24, 48)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        c = ColorPalette.get(self._theme)
        from ui.styles import FONT_MONO, FONT_SIZE_SM, FONT_SIZE_XS

        # NeatCopy brand name
        name_label = QLabel('NeatCopy')
        name_label.setStyleSheet(f"""
            color: {c['fg']};
            font-size: 28px;
            font-weight: 800;
            letter-spacing: -0.03em;
            background: transparent;
        """)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)

        # Version
        version_label = QLabel(f'v{VERSION}')
        version_label.setStyleSheet(f"""
            color: {c['muted']};
            font-family: {FONT_MONO};
            font-size: {FONT_SIZE_SM};
            background: transparent;
        """)
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

        # Author
        author_label = QLabel('by StoneLL1')
        author_label.setStyleSheet(f"""
            color: {c['muted']};
            font-size: {FONT_SIZE_SM};
            background: transparent;
        """)
        author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(author_label)

        # GitHub link
        github_label = QLabel(
            '<a href="https://github.com/StoneLL1/NeatCopy" '
            f'style="color: {c["fg"]}; text-decoration: underline; font-size: {FONT_SIZE_SM};">'
            'github.com/StoneLL1/NeatCopy</a>')
        github_label.setTextFormat(Qt.TextFormat.RichText)
        github_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        github_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        github_label.linkActivated.connect(self._open_github)
        layout.addWidget(github_label)

        layout.addSpacing(32)

        # Check update button
        self._btn_check_update = QPushButton('检查更新')
        self._btn_check_update.setStyleSheet(f"""
            QPushButton {{
                background: {c['surface_alt']};
                border: 1px solid {c['border']};
                border-radius: 6px;
                padding: 8px 16px;
                color: {c['fg']};
                font-size: {FONT_SIZE_SM};
            }}
            QPushButton:hover {{
                border-color: {c['border_strong']};
                background: {c['fg_soft']};
            }}
        """)
        self._btn_check_update.clicked.connect(self._on_check_update)
        btn_container = QHBoxLayout()
        btn_container.addStretch()
        btn_container.addWidget(self._btn_check_update)
        btn_container.addStretch()
        layout.addLayout(btn_container)

        # Star prompt
        star_label = QLabel('如果觉得有用，欢迎 Star ⭐')
        star_label.setStyleSheet(f"""
            color: {c['muted']};
            font-size: {FONT_SIZE_SM};
            background: transparent;
        """)
        star_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(star_label)

        layout.addStretch()
        scroll.setWidget(page)
        return scroll

    def _open_github(self, url: str):
        QDesktopServices.openUrl(QUrl(url))

    def _on_check_update(self):
        self._btn_check_update.setEnabled(False)
        self._btn_check_update.setText('检查中...')

        from PyQt6.QtCore import QThread, pyqtSignal

        class _UpdateWorker(QThread):
            result = pyqtSignal(str, str)  # latest_version, download_url_or_error

            def run(self):
                try:
                    import httpx
                    with httpx.Client(timeout=10.0) as client:
                        resp = client.get('https://api.github.com/repos/StoneLL1/NeatCopy/releases/latest')
                        resp.raise_for_status()
                        data = resp.json()
                        latest = data.get('tag_name', '').lstrip('v')
                        download_url = data.get('html_url', '')
                        self.result.emit(latest, download_url)
                except Exception as e:
                    self.result.emit('', str(e))

        worker = _UpdateWorker()
        worker.result.connect(self._on_update_result)
        worker.start()
        self._update_worker = worker

    def _on_update_result(self, latest: str, url_or_error: str):
        self._btn_check_update.setEnabled(True)
        self._btn_check_update.setText('检查更新')
        if not latest:
            QMessageBox.warning(self, '检查失败', f'无法获取最新版本信息：{url_or_error}')
            return
        if latest == VERSION:
            QMessageBox.information(self, '已是最新', f'当前版本 v{VERSION} 已是最新版本。')
        else:
            msg = f'发现新版本：v{latest}\n当前版本：v{VERSION}\n\n是否前往下载页面？'
            reply = QMessageBox.question(
                self, '发现新版本', msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl(url_or_error))

    # ── Theme ───────────────────────────────────────────────────────

    def _apply_theme(self):
        """Apply the current theme to the window and all child widgets."""
        c = ColorPalette.get(self._theme)
        card_bg = c.get('card_bg', c['bg'])
        self.setStyleSheet(get_settings_stylesheet(self._theme))

        # Title bar styling
        titlebar = self.findChild(QWidget, 'titlebar')
        if titlebar:
            titlebar.setStyleSheet(f"""
                QWidget#titlebar {{
                    background: {card_bg};
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
                    background: {c['danger_soft']};
                    color: {c['danger']};
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

    def _on_preview_theme_changed(self, index: int):
        """Handle preview panel theme segmented control change."""
        theme = 'light' if index == 0 else 'dark'
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
            pos = event.position().toPoint()
            if self._titlebar.geometry().contains(pos):
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                return
        self._drag_pos = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and hasattr(self, '_drag_pos') and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    # ── Save ────────────────────────────────────────────────────────

    def _on_reset_all(self):
        """Reset all settings to defaults after confirmation."""
        reply = QMessageBox.question(
            self, '确认重置',
            '确定要将所有设置恢复为默认值吗？此操作不可撤销。',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        from config_manager import DEFAULT_CONFIG
        for key, value in DEFAULT_CONFIG.items():
            if not key.startswith('llm.prompts'):
                self._mark(key, value)
        self._do_save()
        self.close()

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
        self._status_lbl.setText('✓ 已保存')
        QTimer.singleShot(2000, lambda: self._status_lbl.setText(''))

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
