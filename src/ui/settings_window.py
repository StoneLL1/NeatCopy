# 设置界面：侧边栏导航 + GroupBox 分组布局
import uuid
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QCheckBox, QSlider, QPushButton, QGroupBox,
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
from ui.styles import get_settings_stylesheet, get_sidebar_stylesheet, ColorPalette
from ui.components.sidebar import Sidebar


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
    MAX_WHEEL_PROMPTS = 5

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
        """构建通用设置页面（GroupBox 分组布局）"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName('content_scroll')

        page = QWidget()
        page.setObjectName('content_page')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        # ── 通知 GroupBox ──
        notify_box = QGroupBox('通知')
        notify_lay = QVBoxLayout(notify_box)
        self._chk_toast = QCheckBox('显示清洗完成通知（Toast）')
        self._chk_toast.setChecked(self._config.get('general.toast_notification', True))
        self._chk_toast.stateChanged.connect(
            lambda v: self._mark('general.toast_notification', bool(v)))
        notify_lay.addWidget(self._chk_toast)
        layout.addWidget(notify_box)

        # ── 启动 GroupBox ──
        startup_box = QGroupBox('启动')
        startup_lay = QVBoxLayout(startup_box)
        self._chk_startup = QCheckBox('开机自动启动')
        self._chk_startup.setChecked(self._config.get('general.startup_with_windows', False))
        self._chk_startup.stateChanged.connect(self._on_startup_changed)
        startup_lay.addWidget(self._chk_startup)
        layout.addWidget(startup_box)

        # ── 界面主题 GroupBox ──
        theme_box = QGroupBox('界面主题')
        theme_lay = QHBoxLayout(theme_box)
        theme_lay.setSpacing(8)
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
        theme_lay.addWidget(QLabel('主题：'))
        theme_lay.addWidget(self._btn_theme_light)
        theme_lay.addWidget(self._btn_theme_dark)
        theme_lay.addStretch()
        layout.addWidget(theme_box)

        # ── 独立热键 GroupBox ──
        hk_box = QGroupBox('独立热键')
        hk_lay = QHBoxLayout(hk_box)
        self._chk_hotkey = QCheckBox('启用')
        self._chk_hotkey.setChecked(self._config.get('general.custom_hotkey.enabled', True))
        self._chk_hotkey.stateChanged.connect(
            lambda v: self._mark('general.custom_hotkey.enabled', bool(v)))
        self._btn_record = QPushButton(
            self._config.get('general.custom_hotkey.keys', 'ctrl+shift+c'))
        self._btn_record.setCheckable(True)
        self._btn_record.setObjectName('hotkey_btn')
        self._btn_record.clicked.connect(self._on_clean_hotkey_btn)
        hk_lay.addWidget(self._chk_hotkey)
        hk_lay.addWidget(QLabel('热键：'))
        hk_lay.addWidget(self._btn_record)
        layout.addWidget(hk_box)

        # ── 双击 Ctrl+C GroupBox ──
        dbl_box = QGroupBox('双击 Ctrl+C')
        dbl_lay = QVBoxLayout(dbl_box)
        self._chk_dbl = QCheckBox('启用（注意：可能与部分应用冲突）')
        self._chk_dbl.setChecked(self._config.get('general.double_ctrl_c.enabled', False))
        self._chk_dbl.stateChanged.connect(
            lambda v: self._mark('general.double_ctrl_c.enabled', bool(v)))
        interval = self._config.get('general.double_ctrl_c.interval_ms', 300)
        self._lbl_interval = QLabel(f'间隔阈值：{interval} ms')
        self._sld_interval = QSlider(Qt.Orientation.Horizontal)
        self._sld_interval.setRange(100, 500)
        self._sld_interval.setValue(interval)
        self._sld_interval.setTickInterval(50)
        self._sld_interval.valueChanged.connect(self._on_interval_changed)
        dbl_lay.addWidget(self._chk_dbl)
        dbl_lay.addWidget(self._lbl_interval)
        dbl_lay.addWidget(self._sld_interval)
        layout.addWidget(dbl_box)

        # ── 轮盘 Prompt 选择器 GroupBox ──
        layout.addWidget(self._build_wheel_basic_group())

        # ── 预览面板 GroupBox ──
        layout.addWidget(self._build_preview_group())

        # ── 历史记录 GroupBox ──
        layout.addWidget(self._build_history_group())

        layout.addStretch()
        btn_reset_general = QPushButton('恢复通用默认设置')
        btn_reset_general.setObjectName('btn_reset')
        btn_reset_general.clicked.connect(self._confirm_and_reset_general)
        layout.addWidget(btn_reset_general)

        scroll.setWidget(page)
        return scroll

    def _build_wheel_basic_group(self) -> QGroupBox:
        """构建轮盘基本设置分组（开关与热键）。"""
        wheel_box = QGroupBox('轮盘 Prompt 选择器')
        wheel_lay = QVBoxLayout(wheel_box)
        wheel_lay.setSpacing(6)

        # 启用开关
        self._chk_wheel = QCheckBox('启用轮盘 Prompt 选择器')
        self._chk_wheel.setChecked(self._config.get('wheel.enabled', True))
        self._chk_wheel.stateChanged.connect(self._on_wheel_enabled_changed)
        wheel_lay.addWidget(self._chk_wheel)

        # 随清洗触发
        self._chk_wheel_trigger = QCheckBox('随清洗热键触发（弹出轮盘后执行清洗）')
        self._chk_wheel_trigger.setChecked(self._config.get('wheel.trigger_with_clean', True))
        self._chk_wheel_trigger.stateChanged.connect(
            lambda v: self._mark('wheel.trigger_with_clean', bool(v)))
        wheel_lay.addWidget(self._chk_wheel_trigger)

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
        wheel_lay.addLayout(sw_hk_lay)

        self._update_wheel_subwidgets()
        return wheel_box

    def _build_preview_group(self) -> QGroupBox:
        """构建预览面板设置分组。"""
        preview_box = QGroupBox('预览面板')
        preview_lay = QVBoxLayout(preview_box)
        preview_lay.setSpacing(6)

        # 启用开关
        self._chk_preview = QCheckBox('启用预览面板（LLM 处理后查看结果）')
        self._chk_preview.setChecked(self._config.get('preview.enabled', True))
        self._chk_preview.stateChanged.connect(
            lambda v: self._mark('preview.enabled', bool(v)))
        preview_lay.addWidget(self._chk_preview)

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
        preview_lay.addLayout(hk_lay)

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
        preview_lay.addLayout(theme_lay)

        return preview_box

    def _build_history_group(self) -> QGroupBox:
        """构建历史记录设置分组。"""
        history_box = QGroupBox('历史记录')
        history_lay = QVBoxLayout(history_box)
        history_lay.setSpacing(6)

        # 启用开关
        self._chk_history = QCheckBox('启用历史记录（记录清洗前后文本）')
        self._chk_history.setChecked(self._config.get('history.enabled', True))
        self._chk_history.stateChanged.connect(
            lambda v: self._mark('history.enabled', bool(v)))
        history_lay.addWidget(self._chk_history)

        # 条数上限
        count_row = QHBoxLayout()
        count_row.addWidget(QLabel('最大条数：'))
        self._spin_history_count = QSpinBox()
        self._spin_history_count.setRange(50, 2000)
        self._spin_history_count.setValue(self._config.get('history.max_count', 500))
        self._spin_history_count.setToolTip('超出时自动删除最旧记录')
        self._spin_history_count.valueChanged.connect(
            lambda v: self._mark('history.max_count', v))
        count_row.addWidget(self._spin_history_count)
        count_row.addWidget(QLabel('条'))
        count_row.addStretch()
        history_lay.addLayout(count_row)

        # 快捷键录制
        hk_row = QHBoxLayout()
        hk_row.addWidget(QLabel('快捷键：'))
        self._btn_history_hotkey = QPushButton(
            self._config.get('history.hotkey', 'ctrl+h'))
        self._btn_history_hotkey.setCheckable(True)
        self._btn_history_hotkey.setObjectName('hotkey_btn')
        self._btn_history_hotkey.clicked.connect(self._on_history_hotkey_btn)
        hk_row.addWidget(self._btn_history_hotkey)
        hk_row.addStretch()
        history_lay.addLayout(hk_row)

        return history_box

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
        layout.setSpacing(12)

        # ── 清洗模式 GroupBox ──
        mode_box = QGroupBox('清洗模式')
        mode_lay = QHBoxLayout(mode_box)
        current = self._config.get('rules.mode', 'rules')
        self._rb_rules = QCheckBox('规则模式')
        self._rb_llm = QCheckBox('大模型模式')
        self._rb_rules.setChecked(current == 'rules')
        self._rb_llm.setChecked(current == 'llm')
        self._rb_rules.stateChanged.connect(self._on_mode_checkbox_changed)
        self._rb_llm.stateChanged.connect(self._on_mode_checkbox_changed)
        mode_lay.addWidget(self._rb_rules)
        mode_lay.addWidget(self._rb_llm)
        layout.addWidget(mode_box)

        # ── 规则开关 GroupBox ──
        rules_box = QGroupBox('规则开关（规则模式下生效）')
        rules_lay = QVBoxLayout(rules_box)
        rules_lay.setSpacing(2)
        self._rule_chks: dict[str, QCheckBox] = {}
        for key, (label, tip) in RULE_LABELS.items():
            chk = QCheckBox(label)
            chk.setToolTip(tip)
            chk.setChecked(self._config.get(f'rules.{key}', True))
            chk.stateChanged.connect(
                lambda v, k=key: self._mark(f'rules.{k}', bool(v)))
            self._rule_chks[key] = chk
            rules_lay.addWidget(chk)
        layout.addWidget(rules_box)

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
        layout.setSpacing(12)

        # ── 启用 ──
        self._chk_llm = QCheckBox('启用大模型模式（与规则模式互斥）')
        self._chk_llm.setChecked(self._config.get('rules.mode') == 'llm')
        self._chk_llm.stateChanged.connect(self._on_llm_checkbox_toggled)
        layout.addWidget(self._chk_llm)

        # ── API 配置 GroupBox ──
        api_box = QGroupBox('API 配置')
        api_lay = QVBoxLayout(api_box)
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
            row.addWidget(le)
            api_lay.addLayout(row)
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
        btn_show.setStyleSheet('padding: 0 10px;')
        btn_show.toggled.connect(
            lambda on: self._le_apikey.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
        key_row.addWidget(self._le_apikey, stretch=1)  # 输入框占剩余空间
        key_row.addWidget(btn_show)
        api_lay.addLayout(key_row)

        temp_row = QHBoxLayout()
        temp_val = self._config.get('llm.temperature', 0.2)
        self._lbl_temp = QLabel('Temperature：')
        self._lbl_temp_val = QLabel(f'{temp_val:.1f}')
        self._sld_temp = QSlider(Qt.Orientation.Horizontal)
        self._sld_temp.setRange(0, 20)
        self._sld_temp.setValue(int(temp_val * 10))
        self._sld_temp.valueChanged.connect(self._on_temp_changed)
        # 左侧：Temperature label + slider + 数值
        temp_row.addWidget(self._lbl_temp)
        temp_row.addWidget(self._sld_temp, stretch=1)
        temp_row.addWidget(self._lbl_temp_val)
        # 右侧：超时时长靠右对齐
        temp_row.addStretch()
        temp_row.addWidget(QLabel('超时时长：'))
        self._spin_timeout = QSpinBox()
        self._spin_timeout.setRange(10, 300)
        self._spin_timeout.setValue(int(self._config.get('llm.timeout', 30)))
        self._spin_timeout.setToolTip('LLM 请求最大等待时间（10-300 秒）')
        self._spin_timeout.valueChanged.connect(lambda v: self._mark('llm.timeout', v))
        temp_row.addWidget(self._spin_timeout)
        temp_row.addWidget(QLabel('秒'))
        api_lay.addLayout(temp_row)

        layout.addWidget(api_box)

        # ── 测试连接按钮 ──
        btn_row = QHBoxLayout()
        self._btn_test = QPushButton('测试连接')
        self._btn_test.clicked.connect(self._on_test_connection)
        btn_row.addWidget(self._btn_test)
        btn_reset_llm = QPushButton('恢复 API 默认配置')
        btn_reset_llm.setObjectName('btn_reset')
        btn_reset_llm.clicked.connect(self._confirm_and_reset_llm_api)
        btn_row.addWidget(btn_reset_llm)
        layout.addLayout(btn_row)

        # ── Prompt 模板 GroupBox ──
        prompt_box = QGroupBox('Prompt 模板')
        prompt_lay = QVBoxLayout(prompt_box)
        self._prompt_list = QListWidget()
        self._prompt_list.setMinimumHeight(150)  # 显示约5个模板
        self._prompt_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._prompt_list.customContextMenuRequested.connect(self._show_prompt_menu)
        self._prompt_list.itemDoubleClicked.connect(
            lambda item: self._edit_prompt_by_id(item.data(Qt.ItemDataRole.UserRole)))
        self._refresh_prompts()
        prompt_lay.addWidget(self._prompt_list)

        btn_add = QPushButton('+ 新增模板')
        btn_add.clicked.connect(self._on_add_prompt)
        prompt_lay.addWidget(btn_add)
        layout.addWidget(prompt_box)

        # ── 轮盘 Prompt 选择 GroupBox ──
        layout.addWidget(self._build_wheel_prompt_selector_group())

        layout.addStretch()
        scroll.setWidget(page)
        return scroll

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
        self._lbl_temp_val.setText(f'{llm["temperature"]:.1f}')
        self._spin_timeout.blockSignals(True)
        self._spin_timeout.setValue(llm['timeout'])
        self._spin_timeout.blockSignals(False)
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
        layout.setSpacing(12)

        # ── 版本信息 GroupBox ──
        version_box = QGroupBox('版本信息')
        version_lay = QVBoxLayout(version_box)
        version_lay.addWidget(QLabel(f'当前版本：v{VERSION}'))
        btn_check = QPushButton('检查更新')
        btn_check.clicked.connect(self._on_check_update)
        version_lay.addWidget(btn_check)
        layout.addWidget(version_box)

        # ── 作者 GroupBox ──
        author_box = QGroupBox('作者')
        author_lay = QVBoxLayout(author_box)
        author_lay.addWidget(QLabel('StoneLL1'))
        layout.addWidget(author_box)

        # ── 项目地址 GroupBox ──
        github_box = QGroupBox('项目地址')
        github_lay = QVBoxLayout(github_box)
        github_link = QLabel(
            '<a href="https://github.com/StoneLL1/NeatCopy" style="color:#2383E2;">'
            'github.com/StoneLL1/NeatCopy</a>')
        github_link.setTextFormat(Qt.TextFormat.RichText)
        github_link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        github_link.linkActivated.connect(self._open_github)
        github_lay.addWidget(github_link)
        github_lay.addWidget(QLabel('欢迎 Star ⭐'))
        layout.addWidget(github_box)

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
            self._btn_history_hotkey.setChecked(False)
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
            self._btn_history_hotkey.setChecked(False)
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
            self._btn_history_hotkey.setChecked(False)
            self.grabKeyboard()
            self._recording_target = 'preview'
        else:
            self.releaseKeyboard()
            self._recording_target = None

    def _on_history_hotkey_btn(self, checked: bool):
        """历史快捷键录制按钮回调。"""
        if checked:
            self._btn_history_hotkey.setText('请按下热键组合...')
            # 取消其他录制按钮的 checked 状态
            self._btn_record.setChecked(False)
            self._btn_wheel_hotkey.setChecked(False)
            self._btn_preview_hotkey.setChecked(False)
            self.grabKeyboard()
            self._recording_target = 'history'
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
            elif target == 'history':
                self._btn_history_hotkey.setText(hotkey_str)
                self._mark('history.hotkey', hotkey_str)

        self.releaseKeyboard()
        self._recording_target = None
        if target == 'clean':
            self._btn_record.setChecked(False)
        elif target == 'wheel':
            self._btn_wheel_hotkey.setChecked(False)
        elif target == 'preview':
            self._btn_preview_hotkey.setChecked(False)
        elif target == 'history':
            self._btn_history_hotkey.setChecked(False)

    # ── 滑块事件 ──────────────────────────────────────────────

    def _on_interval_changed(self, value: int):
        self._lbl_interval.setText(f'间隔阈值：{value} ms')
        self._mark('general.double_ctrl_c.interval_ms', value)

    def _on_temp_changed(self, value: int):
        temp = value / 10.0
        self._lbl_temp_val.setText(f'{temp:.1f}')
        self._mark('llm.temperature', temp)

    # ── 轮盘相关 ──────────────────────────────────────────────

    def _build_wheel_prompt_selector_group(self) -> QGroupBox:
        """构建轮盘 Prompt 选择器（左右两栏设计）。"""
        box = QGroupBox('轮盘 Prompt 选择')
        lay = QVBoxLayout(box)
        lay.setSpacing(6)

        # 左右两栏
        columns = QHBoxLayout()

        # 左栏：可用模板
        left_lay = QVBoxLayout()
        left_title = QLabel('可用模板')
        left_title.setStyleSheet('font-weight: bold;')
        left_lay.addWidget(left_title)
        self._wheel_all_list = QListWidget()
        self._wheel_all_list.setMinimumHeight(150)  # 显示约5个模板
        self._wheel_all_list.itemChanged.connect(self._on_wheel_all_item_changed)
        self._refresh_wheel_all_list()
        left_lay.addWidget(self._wheel_all_list)
        columns.addLayout(left_lay, stretch=1)

        # 右栏：轮盘模板
        right_lay = QVBoxLayout()
        right_title = QLabel(f'轮盘模板（最多{self.MAX_WHEEL_PROMPTS}个）')
        right_title.setStyleSheet('font-weight: bold;')
        right_lay.addWidget(right_title)
        self._wheel_selected_list = QListWidget()
        self._wheel_selected_list.setMinimumHeight(150)  # 显示约5个模板
        self._refresh_wheel_selected_list()
        right_lay.addWidget(self._wheel_selected_list)
        columns.addLayout(right_lay, stretch=1)

        lay.addLayout(columns)

        # 提示文字
        tip = QLabel('提示：勾选左侧模板添加到轮盘')
        tip.setStyleSheet('color: #666; font-size: 11px;')
        lay.addWidget(tip)

        return box

    def _refresh_wheel_all_list(self):
        """刷新左栏：所有prompt带勾选框。"""
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
        """刷新右栏：已勾选的prompt带序号。"""
        self._wheel_selected_list.clear()
        prompts = self._config.get('llm.prompts') or []
        selected = [p for p in prompts if p.get('visible_in_wheel', True)]
        for i, p in enumerate(selected[:self.MAX_WHEEL_PROMPTS], start=1):
            item = QListWidgetItem(f'{i}. {p["name"]}')
            item.setData(Qt.ItemDataRole.UserRole, p['id'])
            self._wheel_selected_list.addItem(item)

    def _on_wheel_all_item_changed(self, item: QListWidgetItem):
        """处理勾选变化：同步两栏并保存配置。"""
        # 检查勾选数量
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

        # 更新配置
        prompts = list(self._config.get('llm.prompts') or [])
        for i in range(self._wheel_all_list.count()):
            list_item = self._wheel_all_list.item(i)
            pid = list_item.data(Qt.ItemDataRole.UserRole)
            visible = list_item.checkState() == Qt.CheckState.Checked
            for p in prompts:
                if p['id'] == pid:
                    p['visible_in_wheel'] = visible
        self._mark('llm.prompts', prompts)

        # 同步刷新右栏
        self._refresh_wheel_selected_list()

    def _on_wheel_enabled_changed(self, state):
        enabled = bool(state)
        self._mark('wheel.enabled', enabled)
        self._update_wheel_subwidgets()

    def _update_wheel_subwidgets(self):
        enabled = self._chk_wheel.isChecked()
        self._chk_wheel_trigger.setEnabled(enabled)
        self._btn_wheel_hotkey.setEnabled(enabled)
        if hasattr(self, '_wheel_all_list'):
            self._wheel_all_list.setEnabled(enabled)

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

    def _on_startup_changed(self, state: int):
        enabled = bool(state)
        self._mark('general.startup_with_windows', enabled)
        # 实时更新注册表
        if enabled:
            ok, msg = _autostart_enable()
            if not ok and msg:
                QMessageBox.warning(self, '开机自启动', msg)
        else:
            _autostart_disable()

    # ── 关闭事件 ─────────────────────────────────────────────

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
            # 让按钮文字更宽，避免挤在一起
            for btn in (btn_save, btn_discard, btn_cancel):
                btn.setMinimumWidth(90)
            msg_box.exec()
            clicked = msg_box.clickedButton()
            if clicked == btn_save:
                self._do_save()
            elif clicked == btn_cancel:
                event.ignore()
                return
            # btn_discard: 直接关闭
        super().closeEvent(event)

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