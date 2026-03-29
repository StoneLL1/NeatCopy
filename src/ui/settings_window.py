# 设置界面：侧边栏导航 + 分隔线式布局（Notion风格）
import sys
import os
import uuid
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QCheckBox, QSlider, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem,
    QTextEdit, QInputDialog, QMessageBox, QMenu, QSizePolicy,
    QStackedWidget, QFrame, QScrollArea,
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices

from version import VERSION
from assets import asset as _asset
from ui.styles import (
    get_settings_stylesheet, get_sidebar_stylesheet,
    get_content_stylesheet, ColorPalette,
)
from ui.components.sidebar import Sidebar
from ui.components.section_title import SectionTitle


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
    # 导航项定义
    NAV_ITEMS = ['通用', '清洗规则', '大模型', '关于']

    def __init__(self, config, hotkey_manager=None, parent=None):
        super().__init__(parent)
        self._config = config
        self._hotkey_manager = hotkey_manager
        self._pending: dict = {}
        self._theme = config.get('ui.theme', 'light')

        self.setWindowTitle('NeatCopy 设置')
        # 可调整大小的窗口
        self.resize(700, 550)
        self.setMinimumSize(550, 400)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
        self.setWindowIcon(QIcon(_asset('idle.ico')))

        # 应用主题样式
        self._apply_theme()

        # 主布局：侧边栏 + 内容区
        self._build_main_layout()

    def _build_main_layout(self):
        """构建主布局：左侧导航栏 + 右侧内容区 + 底部操作栏"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 上部区域：侧边栏 + 内容区
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)

        # 侧边栏
        self._sidebar = Sidebar(
            items=self.NAV_ITEMS,
            theme=self._theme,
        )
        self._sidebar.setFixedWidth(180)
        self._sidebar.currentChanged.connect(self._on_nav_select)
        top_layout.addWidget(self._sidebar)

        # 侧边栏与内容区的分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setObjectName('sidebar_separator')
        top_layout.addWidget(separator)

        # 内容区（使用 QStackedWidget）
        self._content_stack = QStackedWidget()
        self._content_stack.addWidget(self._build_general_page())
        self._content_stack.addWidget(self._build_rules_page())
        self._content_stack.addWidget(self._build_llm_page())
        self._content_stack.addWidget(self._build_about_page())
        top_layout.addWidget(self._content_stack, 1)

        main_layout.addLayout(top_layout, 1)

        # 底部操作栏
        self._build_bottom_bar(main_layout)

    def _build_bottom_bar(self, parent_layout: QVBoxLayout):
        """构建底部操作栏：状态文字 + 保存按钮"""
        bottom_bar = QWidget()
        bottom_bar.setObjectName('bottom_bar')
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(24, 12, 24, 12)
        bottom_layout.setSpacing(12)

        self._status_lbl = QLabel('')
        self._status_lbl.setObjectName('status_label')
        bottom_layout.addWidget(self._status_lbl)
        bottom_layout.addStretch()

        save_btn = QPushButton('保存')
        save_btn.setObjectName('btn_save')
        save_btn.clicked.connect(self._do_save)
        bottom_layout.addWidget(save_btn)

        parent_layout.addWidget(bottom_bar)

    def _on_nav_select(self, index: int):
        """导航项选择回调"""
        self._content_stack.setCurrentIndex(index)

    # ── 通用页面 ──────────────────────────────────────────────

    def _build_general_page(self) -> QWidget:
        """构建通用设置页面（分隔线式布局）"""
        # 使用滚动区域包装内容
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName('content_scroll')

        page = QWidget()
        page.setObjectName('content_page')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 页面标题
        title = QLabel('通用设置')
        title.setObjectName('page_title')
        layout.addWidget(title)

        # ── 通知区块 ──
        layout.addWidget(SectionTitle('通知'))
        self._chk_toast = QCheckBox('显示清洗完成通知（Toast）')
        self._chk_toast.setChecked(self._config.get('general.toast_notification', True))
        self._chk_toast.stateChanged.connect(
            lambda v: self._mark('general.toast_notification', bool(v)))
        layout.addWidget(self._chk_toast)
        layout.addWidget(self._separator())

        # ── 启动区块 ──
        layout.addWidget(SectionTitle('启动'))
        self._chk_startup = QCheckBox('开机自动启动')
        self._chk_startup.setChecked(self._config.get('general.startup_with_windows', False))
        self._chk_startup.stateChanged.connect(
            lambda v: self._mark('general.startup_with_windows', bool(v)))
        layout.addWidget(self._chk_startup)
        layout.addWidget(self._separator())

        # ── 界面主题区块 ──
        layout.addWidget(SectionTitle('界面主题'))
        theme_row = QHBoxLayout()
        self._btn_theme_light = QPushButton('浅色')
        self._btn_theme_light.setCheckable(True)
        self._btn_theme_light.setObjectName('theme_btn')
        self._btn_theme_dark = QPushButton('深色')
        self._btn_theme_dark.setCheckable(True)
        self._btn_theme_dark.setObjectName('theme_btn')
        self._btn_theme_light.setChecked(self._theme == 'light')
        self._btn_theme_dark.setChecked(self._theme == 'dark')
        self._btn_theme_light.clicked.connect(self._on_theme_light_clicked)
        self._btn_theme_dark.clicked.connect(self._on_theme_dark_clicked)
        theme_row.addWidget(self._btn_theme_light)
        theme_row.addWidget(self._btn_theme_dark)
        theme_row.addStretch()
        layout.addLayout(theme_row)
        layout.addWidget(self._separator())

        # ── 独立热键区块 ──
        layout.addWidget(SectionTitle('独立热键'))
        hk_row = QHBoxLayout()
        self._chk_hotkey = QCheckBox('启用')
        self._chk_hotkey.setChecked(self._config.get('general.custom_hotkey.enabled', True))
        self._chk_hotkey.stateChanged.connect(
            lambda v: self._mark('general.custom_hotkey.enabled', bool(v)))
        hk_row.addWidget(self._chk_hotkey)
        hk_row.addSpacing(16)
        hk_row.addWidget(QLabel('热键：'))
        self._btn_record = QPushButton(
            self._config.get('general.custom_hotkey.keys', 'ctrl+shift+c'))
        self._btn_record.setCheckable(True)
        self._btn_record.setObjectName('hotkey_btn')
        self._btn_record.clicked.connect(self._on_clean_hotkey_btn)
        hk_row.addWidget(self._btn_record)
        hk_row.addStretch()
        layout.addLayout(hk_row)
        layout.addWidget(self._separator())

        # ── 双击 Ctrl+C 区块 ──
        layout.addWidget(SectionTitle('双击 Ctrl+C'))
        self._chk_dbl = QCheckBox('启用（注意：可能与部分应用冲突）')
        self._chk_dbl.setChecked(self._config.get('general.double_ctrl_c.enabled', False))
        self._chk_dbl.stateChanged.connect(
            lambda v: self._mark('general.double_ctrl_c.enabled', bool(v)))
        layout.addWidget(self._chk_dbl)

        interval = self._config.get('general.double_ctrl_c.interval_ms', 300)
        self._lbl_interval = QLabel(f'间隔阈值：{interval} ms')
        self._lbl_interval.setObjectName('sub_label')
        layout.addWidget(self._lbl_interval)

        self._sld_interval = QSlider(Qt.Orientation.Horizontal)
        self._sld_interval.setRange(100, 500)
        self._sld_interval.setValue(interval)
        self._sld_interval.setTickInterval(50)
        self._sld_interval.valueChanged.connect(self._on_interval_changed)
        layout.addWidget(self._sld_interval)
        layout.addWidget(self._separator())

        # ── 轮盘 Prompt 选择器区块 ──
        self._build_wheel_section(layout)
        layout.addWidget(self._separator())

        # ── 预览面板区块 ──
        self._build_preview_section(layout)
        layout.addWidget(self._separator())

        # ── 底部恢复按钮 ──
        layout.addStretch()
        btn_reset_general = QPushButton('恢复通用默认设置')
        btn_reset_general.setObjectName('btn_reset')
        btn_reset_general.clicked.connect(self._confirm_and_reset_general)
        layout.addWidget(btn_reset_general)

        scroll.setWidget(page)
        return scroll

    def _build_wheel_section(self, layout: QVBoxLayout):
        """构建轮盘 Prompt 选择器设置区块。"""
        layout.addWidget(SectionTitle('轮盘 Prompt 选择器'))

        # 启用开关
        self._chk_wheel = QCheckBox('启用轮盘 Prompt 选择器')
        self._chk_wheel.setChecked(self._config.get('wheel.enabled', True))
        self._chk_wheel.stateChanged.connect(self._on_wheel_enabled_changed)
        layout.addWidget(self._chk_wheel)

        # 随清洗触发
        self._chk_wheel_trigger = QCheckBox('随清洗热键触发（弹出轮盘后执行清洗）')
        self._chk_wheel_trigger.setChecked(self._config.get('wheel.trigger_with_clean', True))
        self._chk_wheel_trigger.stateChanged.connect(
            lambda v: self._mark('wheel.trigger_with_clean', bool(v)))
        layout.addWidget(self._chk_wheel_trigger)

        # 独立切换热键
        sw_hk_lay = QHBoxLayout()
        sw_hk_lay.addWidget(QLabel('切换热键：'))
        self._btn_wheel_hotkey = QPushButton(
            self._config.get('wheel.switch_hotkey', 'ctrl+shift+p'))
        self._btn_wheel_hotkey.setCheckable(True)
        self._btn_wheel_hotkey.setObjectName('hotkey_btn')
        self._btn_wheel_hotkey.clicked.connect(self._on_wheel_hotkey_btn)
        sw_hk_lay.addWidget(self._btn_wheel_hotkey)
        sw_hk_lay.addStretch()
        layout.addLayout(sw_hk_lay)

        # 可见 Prompt 配置
        layout.addWidget(QLabel('轮盘显示的 Prompt（最多5个）：'))
        self._wheel_prompt_list = QListWidget()
        self._wheel_prompt_list.setMaximumHeight(100)
        self._wheel_prompt_list.itemChanged.connect(self._on_wheel_prompt_item_changed)
        self._refresh_wheel_prompts()
        layout.addWidget(self._wheel_prompt_list)

        # 根据启用状态更新子控件可用性
        self._update_wheel_subwidgets()

    def _build_preview_section(self, layout: QVBoxLayout):
        """构建预览面板设置区块。"""
        layout.addWidget(SectionTitle('预览面板'))

        # 启用开关
        self._chk_preview = QCheckBox('启用预览面板（LLM 处理后查看结果）')
        self._chk_preview.setChecked(self._config.get('preview.enabled', True))
        self._chk_preview.stateChanged.connect(
            lambda v: self._mark('preview.enabled', bool(v)))
        layout.addWidget(self._chk_preview)

        # 快捷键录制
        hk_lay = QHBoxLayout()
        hk_lay.addWidget(QLabel('快捷键：'))
        self._btn_preview_hotkey = QPushButton(
            self._config.get('preview.hotkey', 'ctrl+q'))
        self._btn_preview_hotkey.setCheckable(True)
        self._btn_preview_hotkey.setObjectName('hotkey_btn')
        self._btn_preview_hotkey.clicked.connect(self._on_preview_hotkey_btn)
        hk_lay.addWidget(self._btn_preview_hotkey)
        hk_lay.addStretch()
        layout.addLayout(hk_lay)

        # 主题切换按钮
        theme_lay = QHBoxLayout()
        theme_lay.addWidget(QLabel('面板主题：'))
        self._btn_preview_theme_dark = QPushButton('深色')
        self._btn_preview_theme_dark.setCheckable(True)
        self._btn_preview_theme_dark.setObjectName('theme_btn')
        self._btn_preview_theme_light = QPushButton('浅色')
        self._btn_preview_theme_light.setCheckable(True)
        self._btn_preview_theme_light.setObjectName('theme_btn')
        current_theme = self._config.get('preview.theme', 'dark')
        self._btn_preview_theme_dark.setChecked(current_theme == 'dark')
        self._btn_preview_theme_light.setChecked(current_theme == 'light')
        self._btn_preview_theme_dark.clicked.connect(self._on_preview_theme_dark_clicked)
        self._btn_preview_theme_light.clicked.connect(self._on_preview_theme_light_clicked)
        theme_lay.addWidget(self._btn_preview_theme_dark)
        theme_lay.addWidget(self._btn_preview_theme_light)
        theme_lay.addStretch()
        layout.addLayout(theme_lay)

    def _separator(self) -> QFrame:
        """创建水平分隔线"""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName('section_separator')
        return line

    def _confirm_and_reset_general(self):
        reply = QMessageBox.question(
            self, '确认恢复默认',
            '确定要将通用设置（热键、双击 Ctrl+C、Toast 通知等）恢复为默认值吗？\n此操作不可撤销。',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        from config_manager import DEFAULT_CONFIG
        g = DEFAULT_CONFIG['general']
        # 写入待保存列表
        self._mark('general.toast_notification',         g['toast_notification'])
        self._mark('general.startup_with_windows',       g['startup_with_windows'])
        self._mark('general.double_ctrl_c.enabled',      g['double_ctrl_c']['enabled'])
        self._mark('general.double_ctrl_c.interval_ms',  g['double_ctrl_c']['interval_ms'])
        self._mark('general.custom_hotkey.enabled',      g['custom_hotkey']['enabled'])
        self._mark('general.custom_hotkey.keys',         g['custom_hotkey']['keys'])
        # 刷新 UI（阻断信号，避免触发二次 _mark）
        for widget, value in [
            (self._chk_toast,    g['toast_notification']),
            (self._chk_startup,  g['startup_with_windows']),
            (self._chk_hotkey,   g['custom_hotkey']['enabled']),
            (self._chk_dbl,      g['double_ctrl_c']['enabled']),
        ]:
            widget.blockSignals(True)
            widget.setChecked(value)
            widget.blockSignals(False)
        self._btn_record.blockSignals(True)
        self._btn_record.setText(g['custom_hotkey']['keys'])
        self._btn_record.blockSignals(False)
        self._sld_interval.blockSignals(True)
        self._sld_interval.setValue(g['double_ctrl_c']['interval_ms'])
        self._sld_interval.blockSignals(False)
        self._lbl_interval.setText(f'间隔阈值：{g["double_ctrl_c"]["interval_ms"]} ms')
        self._do_save()

    # ── 规则页面 ──────────────────────────────────────────────

    def _build_rules_page(self) -> QWidget:
        """构建规则设置页面"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName('content_scroll')

        page = QWidget()
        page.setObjectName('content_page')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 页面标题
        title = QLabel('清洗规则')
        title.setObjectName('page_title')
        layout.addWidget(title)

        # ── 清洗模式区块 ──
        layout.addWidget(SectionTitle('清洗模式'))
        mode_row = QHBoxLayout()
        current = self._config.get('rules.mode', 'rules')
        self._rb_rules = QCheckBox('规则模式')
        self._rb_llm = QCheckBox('大模型模式')
        self._rb_rules.setChecked(current == 'rules')
        self._rb_llm.setChecked(current == 'llm')
        self._rb_rules.stateChanged.connect(self._on_mode_checkbox_changed)
        self._rb_llm.stateChanged.connect(self._on_mode_checkbox_changed)
        mode_row.addWidget(self._rb_rules)
        mode_row.addWidget(self._rb_llm)
        mode_row.addStretch()
        layout.addLayout(mode_row)
        layout.addWidget(self._separator())

        # ── 规则开关区块 ──
        layout.addWidget(SectionTitle('规则开关（规则模式下生效）'))
        self._rule_chks: dict[str, QCheckBox] = {}
        for key, (label, tip) in RULE_LABELS.items():
            chk = QCheckBox(label)
            chk.setToolTip(tip)
            chk.setChecked(self._config.get(f'rules.{key}', True))
            chk.stateChanged.connect(
                lambda v, k=key: self._mark(f'rules.{k}', bool(v)))
            self._rule_chks[key] = chk
            layout.addWidget(chk)

        layout.addStretch()
        scroll.setWidget(page)
        return scroll

    def _on_mode_checkbox_changed(self):
        sender = self.sender()
        if sender == self._rb_rules and self._rb_rules.isChecked():
            mode = 'rules'
        elif sender == self._rb_llm and self._rb_llm.isChecked():
            mode = 'llm'
        else:
            # 不允许两个都取消，恢复发送者为选中
            sender.blockSignals(True)
            sender.setChecked(True)
            sender.blockSignals(False)
            return
        self._mark('rules.mode', mode)
        # 互斥：取消另一个
        other = self._rb_llm if sender == self._rb_rules else self._rb_rules
        other.blockSignals(True)
        other.setChecked(False)
        other.blockSignals(False)
        # 同步 LLM 页面的 Checkbox
        self._chk_llm.blockSignals(True)
        self._chk_llm.setChecked(mode == 'llm')
        self._chk_llm.blockSignals(False)

    # ── 大模型页面 ────────────────────────────────────────────

    def _build_llm_page(self) -> QWidget:
        """构建大模型设置页面"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName('content_scroll')

        page = QWidget()
        page.setObjectName('content_page')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 页面标题
        title = QLabel('大模型设置')
        title.setObjectName('page_title')
        layout.addWidget(title)

        # ── 启用区块 ──
        self._chk_llm = QCheckBox('启用大模型模式（与规则模式互斥）')
        self._chk_llm.setChecked(self._config.get('rules.mode') == 'llm')
        self._chk_llm.stateChanged.connect(self._on_llm_checkbox_toggled)
        layout.addWidget(self._chk_llm)
        layout.addWidget(self._separator())

        # ── API 配置区块 ──
        layout.addWidget(SectionTitle('API 配置'))
        self._le_base_url: QLineEdit | None = None
        self._le_model_id: QLineEdit | None = None

        _api_fields = [
            ('Base URL', 'llm.base_url', 'https://api.openai.com/v1'),
            ('Model ID', 'llm.model_id', 'gpt-4o-mini'),
        ]
        for label, key, placeholder in _api_fields:
            row = QHBoxLayout()
            row.addWidget(QLabel(f'{label}：'))
            le = QLineEdit(str(self._config.get(key, placeholder)))
            le.setPlaceholderText(placeholder)
            le.textChanged.connect(lambda t, k=key: self._mark(k, t))
            row.addWidget(le, 1)
            layout.addLayout(row)
            if key == 'llm.base_url':
                self._le_base_url = le
            elif key == 'llm.model_id':
                self._le_model_id = le

        key_row = QHBoxLayout()
        key_row.addWidget(QLabel('API Key：'))
        self._le_apikey = QLineEdit(self._config.get('llm.api_key', ''))
        self._le_apikey.setEchoMode(QLineEdit.EchoMode.Password)
        self._le_apikey.setPlaceholderText('sk-...')
        self._le_apikey.textChanged.connect(lambda t: self._mark('llm.api_key', t))
        btn_show = QPushButton('显示')
        btn_show.setCheckable(True)
        btn_show.setFixedWidth(50)
        btn_show.toggled.connect(
            lambda on: self._le_apikey.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
        key_row.addWidget(self._le_apikey, 1)
        key_row.addWidget(btn_show)
        layout.addLayout(key_row)

        temp_row = QHBoxLayout()
        temp_val = self._config.get('llm.temperature', 0.2)
        self._lbl_temp = QLabel(f'Temperature：{temp_val:.1f}')
        self._lbl_temp.setObjectName('sub_label')
        temp_row.addWidget(self._lbl_temp)
        self._sld_temp = QSlider(Qt.Orientation.Horizontal)
        self._sld_temp.setRange(0, 20)
        self._sld_temp.setValue(int(temp_val * 10))
        self._sld_temp.valueChanged.connect(self._on_temp_changed)
        temp_row.addWidget(self._sld_temp)
        layout.addLayout(temp_row)
        layout.addWidget(self._separator())

        # ── 测试连接按钮 ──
        btn_row = QHBoxLayout()
        self._btn_test = QPushButton('测试连接')
        self._btn_test.clicked.connect(self._on_test_connection)
        btn_row.addWidget(self._btn_test)
        btn_reset_llm = QPushButton('恢复 API 默认配置')
        btn_reset_llm.setObjectName('btn_reset')
        btn_reset_llm.clicked.connect(self._confirm_and_reset_llm_api)
        btn_row.addWidget(btn_reset_llm)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addWidget(self._separator())

        # ── Prompt 模板区块 ──
        layout.addWidget(SectionTitle('Prompt 模板'))
        self._prompt_list = QListWidget()
        self._prompt_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._prompt_list.customContextMenuRequested.connect(self._show_prompt_menu)
        self._prompt_list.itemDoubleClicked.connect(
            lambda item: self._edit_prompt_by_id(item.data(Qt.ItemDataRole.UserRole)))
        self._refresh_prompts()
        layout.addWidget(self._prompt_list)

        btn_add = QPushButton('+ 新增模板')
        btn_add.clicked.connect(self._on_add_prompt)
        layout.addWidget(btn_add)

        layout.addStretch()
        scroll.setWidget(page)
        return scroll

    def _confirm_and_reset_llm_api(self):
        reply = QMessageBox.question(
            self, '确认恢复默认',
            '确定要将 API 配置（Base URL、Model ID、API Key、Temperature）恢复为默认值吗？\n'
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
        # 刷新 UI
        if self._le_base_url:
            self._le_base_url.blockSignals(True)
            self._le_base_url.setText(llm['base_url'])
            self._le_base_url.blockSignals(False)
        if self._le_model_id:
            self._le_model_id.blockSignals(True)
            self._le_model_id.setText(llm['model_id'])
            self._le_model_id.blockSignals(False)
        self._le_apikey.blockSignals(True)
        self._le_apikey.setText(llm['api_key'])
        self._le_apikey.blockSignals(False)
        self._sld_temp.blockSignals(True)
        self._sld_temp.setValue(int(llm['temperature'] * 10))
        self._sld_temp.blockSignals(False)
        self._lbl_temp.setText(f'Temperature：{llm["temperature"]:.1f}')
        self._do_save()

    def _on_llm_checkbox_toggled(self, checked):
        mode = 'llm' if checked else 'rules'
        self._mark('rules.mode', mode)
        # 同步规则页面的 Checkbox（不触发信号避免循环）
        self._rb_rules.blockSignals(True)
        self._rb_llm.blockSignals(True)
        self._rb_rules.setChecked(mode == 'rules')
        self._rb_llm.setChecked(mode == 'llm')
        self._rb_rules.blockSignals(False)
        self._rb_llm.blockSignals(False)

    # ── 关于页面 ──────────────────────────────────────────────

    def _build_about_page(self) -> QWidget:
        """构建关于页面"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName('content_scroll')

        page = QWidget()
        page.setObjectName('content_page')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 页面标题
        title = QLabel('关于')
        title.setObjectName('page_title')
        layout.addWidget(title)

        # ── 版本信息区块 ──
        layout.addWidget(SectionTitle('版本信息'))
        layout.addWidget(QLabel(f'当前版本：v{VERSION}'))
        btn_check = QPushButton('检查更新')
        btn_check.clicked.connect(self._on_check_update)
        layout.addWidget(btn_check)
        layout.addWidget(self._separator())

        # ── 作者区块 ──
        layout.addWidget(SectionTitle('作者'))
        layout.addWidget(QLabel('StoneLL1'))
        layout.addWidget(self._separator())

        # ── 项目地址区块 ──
        layout.addWidget(SectionTitle('项目地址'))
        github_link = QLabel(
            '<a href="https://github.com/StoneLL1/NeatCopy" style="color:#2383E2;">'
            'github.com/StoneLL1/NeatCopy</a>')
        github_link.setTextFormat(Qt.TextFormat.RichText)
        github_link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        github_link.linkActivated.connect(self._open_github)
        layout.addWidget(github_link)
        layout.addWidget(QLabel('欢迎 Star ⭐'))

        layout.addStretch()
        scroll.setWidget(page)
        return scroll

    # ── 事件处理 ──────────────────────────────────────────────

    def _on_check_update(self):
        for b in self.findChildren(QPushButton):
            if b.text() in ('检查更新', '检查中...'):
                b.setEnabled(False)
                b.setText('检查中...')
                break

        from PyQt6.QtCore import QThread as _QT
        from PyQt6.QtCore import pyqtSignal as _sig

        class _UpdateWorker(_QT):
            result = _sig(str, str)  # latest_version, download_url

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
        for b in self.findChildren(QPushButton):
            if b.text() in ('检查更新', '检查中...'):
                b.setEnabled(True)
                b.setText('检查更新')
                break

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

    def _open_github(self, url: str):
        QDesktopServices.openUrl(QUrl(url))

    # ── 热键录制 ──────────────────────────────────────────────

    def _on_clean_hotkey_btn(self, checked: bool):
        if checked:
            self._btn_record.setText('请按下热键组合...')
            self._btn_wheel_hotkey.setChecked(False)
            self._btn_preview_hotkey.setChecked(False)
            self.grabKeyboard()
            self._recording_target = 'clean'
        else:
            self.releaseKeyboard()
            self._recording_target = None

    def _on_wheel_hotkey_btn(self, checked: bool):
        if checked:
            self._btn_wheel_hotkey.setText('请按下热键组合...')
            self._btn_record.setChecked(False)
            self._btn_preview_hotkey.setChecked(False)
            self.grabKeyboard()
            self._recording_target = 'wheel'
        else:
            self.releaseKeyboard()
            self._recording_target = None

    def _on_preview_hotkey_btn(self, checked: bool):
        if checked:
            self._btn_preview_hotkey.setText('请按下热键组合...')
            self._btn_record.setChecked(False)
            self._btn_wheel_hotkey.setChecked(False)
            self.grabKeyboard()
            self._recording_target = 'preview'
        else:
            self.releaseKeyboard()
            self._recording_target = None

    def keyPressEvent(self, event):
        """捕获热键录制"""
        target = getattr(self, '_recording_target', None)
        if target is None:
            return super().keyPressEvent(event)

        from PyQt6.QtCore import Qt as _Qt
        key = event.key()
        mods = event.modifiers()

        # 忽略纯修饰键
        if key in (
            _Qt.Key.Key_Control, _Qt.Key.Key_Shift, _Qt.Key.Key_Alt,
            _Qt.Key.Key_Meta, _Qt.Key.Key_unknown
        ):
            return

        parts = []
        if mods & _Qt.KeyboardModifier.ControlModifier:
            parts.append('ctrl')
        if mods & _Qt.KeyboardModifier.ShiftModifier:
            parts.append('shift')
        if mods & _Qt.KeyboardModifier.AltModifier:
            parts.append('alt')

        try:
            key_str = _Qt.Key(key).name
            key_name = key_str.replace('Key_', '').lower()
        except (ValueError, KeyError):
            key_name = ''
        if key_name:
            parts.append(key_name)

        if len(parts) >= 2:
            hotkey_str = '+'.join(parts)
            if target == 'clean':
                self._btn_record.setText(hotkey_str)
                self._mark('general.custom_hotkey.keys', hotkey_str)
            elif target == 'wheel':
                self._btn_wheel_hotkey.setText(hotkey_str)
                self._mark('wheel.switch_hotkey', hotkey_str)
            elif target == 'preview':
                self._btn_preview_hotkey.setText(hotkey_str)
                self._mark('preview.hotkey', hotkey_str)

        self.releaseKeyboard()
        self._recording_target = None
        if target == 'clean':
            self._btn_record.setChecked(False)
        elif target == 'wheel':
            self._btn_wheel_hotkey.setChecked(False)
        elif target == 'preview':
            self._btn_preview_hotkey.setChecked(False)

    # ── 滑块事件 ──────────────────────────────────────────────

    def _on_interval_changed(self, value: int):
        self._lbl_interval.setText(f'间隔阈值：{value} ms')
        self._mark('general.double_ctrl_c.interval_ms', value)

    def _on_temp_changed(self, value: int):
        temp = value / 10.0
        self._lbl_temp.setText(f'Temperature：{temp:.1f}')
        self._mark('llm.temperature', temp)

    # ── 轮盘相关 ──────────────────────────────────────────────

    def _refresh_wheel_prompts(self):
        """刷新轮盘可见 Prompt 列表。"""
        self._wheel_prompt_list.blockSignals(True)
        self._wheel_prompt_list.clear()
        prompts = self._config.get('llm.prompts') or []
        for p in prompts:
            item = QListWidgetItem(p['name'])
            item.setData(Qt.ItemDataRole.UserRole, p['id'])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if p.get('visible_in_wheel', True)
                else Qt.CheckState.Unchecked
            )
            self._wheel_prompt_list.addItem(item)
        self._wheel_prompt_list.blockSignals(False)

    def _on_wheel_prompt_item_changed(self, item: QListWidgetItem):
        """处理轮盘可见 Prompt 勾选变化，最多5个。"""
        checked_count = sum(
            1 for i in range(self._wheel_prompt_list.count())
            if self._wheel_prompt_list.item(i).checkState() == Qt.CheckState.Checked
        )
        if checked_count > 5:
            self._wheel_prompt_list.blockSignals(True)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._wheel_prompt_list.blockSignals(False)
            self._status_lbl.setText('轮盘最多显示5个 Prompt')
            QTimer.singleShot(2000, lambda: self._status_lbl.setText(''))
            return

        prompts = list(self._config.get('llm.prompts') or [])
        for i in range(self._wheel_prompt_list.count()):
            list_item = self._wheel_prompt_list.item(i)
            pid = list_item.data(Qt.ItemDataRole.UserRole)
            visible = list_item.checkState() == Qt.CheckState.Checked
            for p in prompts:
                if p['id'] == pid:
                    p['visible_in_wheel'] = visible
        self._mark('llm.prompts', prompts)

    def _on_wheel_enabled_changed(self, state):
        enabled = bool(state)
        self._mark('wheel.enabled', enabled)
        self._update_wheel_subwidgets()

    def _update_wheel_subwidgets(self):
        enabled = self._chk_wheel.isChecked()
        self._chk_wheel_trigger.setEnabled(enabled)
        self._btn_wheel_hotkey.setEnabled(enabled)
        self._wheel_prompt_list.setEnabled(enabled)

    # ── 预览面板主题 ──────────────────────────────────────────────

    def _on_preview_theme_dark_clicked(self):
        self._btn_preview_theme_dark.setChecked(True)
        self._btn_preview_theme_light.setChecked(False)
        self._mark('preview.theme', 'dark')

    def _on_preview_theme_light_clicked(self):
        self._btn_preview_theme_dark.setChecked(False)
        self._btn_preview_theme_light.setChecked(True)
        self._mark('preview.theme', 'light')

    # ── Prompt 模板管理 ──────────────────────────────────────────────

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
        if hasattr(self, '_wheel_prompt_list'):
            self._refresh_wheel_prompts()

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

    # ── 测试连接 ──────────────────────────────────────────────

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
                    with httpx.Client(timeout=30.0) as client:
                        resp = client.post(f'{base_url}/chat/completions',
                                           json=payload, headers=headers)
                        resp.raise_for_status()
                        content = resp.json()['choices'][0]['message']['content']
                        self.success.emit(content)
                except Exception as e:
                    from llm_client import classify_error
                    self.error.emit(classify_error(e))

        worker = _TestWorker(llm_cfg)
        worker.success.connect(lambda r: (
            QMessageBox.information(self, '连接成功', f'模型回复：{r[:200]}'),
            self._btn_test.setEnabled(True),
            self._btn_test.setText('测试连接'),
        ))
        worker.error.connect(lambda e: (
            QMessageBox.critical(self, '连接失败', e),
            self._btn_test.setEnabled(True),
            self._btn_test.setText('测试连接'),
        ))
        worker.finished.connect(lambda: (
            self._btn_test.setEnabled(True),
            self._btn_test.setText('测试连接'),
        ))
        worker.start()
        self._test_worker = worker

    # ── 主题切换 ──────────────────────────────────────────────

    def _apply_theme(self):
        """Apply the current theme's stylesheet."""
        self.setStyleSheet(get_settings_stylesheet(self._theme))
        if hasattr(self, '_sidebar'):
            self._sidebar.set_theme(self._theme)

    def _on_theme_light_clicked(self):
        self._btn_theme_dark.setChecked(False)
        self._btn_theme_light.setChecked(True)
        self._theme = 'light'
        self._mark('ui.theme', 'light')
        self._apply_theme()

    def _on_theme_dark_clicked(self):
        self._btn_theme_light.setChecked(False)
        self._btn_theme_dark.setChecked(True)
        self._theme = 'dark'
        self._mark('ui.theme', 'dark')
        self._apply_theme()

    # ── 保存 ─────────────────────────────────────────────────

    def _mark(self, key: str, value):
        self._pending[key] = value

    def _do_save(self):
        if hasattr(self, '_chk_preview'):
            self._mark('preview.enabled', self._chk_preview.isChecked())
        for key, value in self._pending.items():
            self._config.set(key, value)
        self._pending.clear()
        if self._hotkey_manager:
            self._hotkey_manager.reload_config(self._config)
        self._status_lbl.setText('已保存 ✓')
        QTimer.singleShot(1500, lambda: self._status_lbl.setText(''))