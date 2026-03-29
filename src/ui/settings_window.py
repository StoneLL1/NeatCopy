# 设置界面：三Tab（通用/清洗规则/大模型），点击保存后写入配置。
import sys
import os
import uuid
from PyQt6.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QCheckBox, QSlider, QPushButton, QGroupBox,
    QRadioButton, QLineEdit, QListWidget, QListWidgetItem,
    QTextEdit, QInputDialog, QMessageBox, QMenu, QSizePolicy,
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices

from version import VERSION
from assets import asset as _asset


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
    def __init__(self, config, hotkey_manager=None, parent=None):
        super().__init__(parent)
        self._config = config
        self._hotkey_manager = hotkey_manager
        self._pending: dict = {}

        self.setWindowTitle('NeatCopy 设置')
        self.setFixedWidth(520)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
        self.setWindowIcon(QIcon(_asset('idle.ico')))
        check_path = _asset('check.png').replace('\\', '/')
        self.setStyleSheet(f"""
            QDialog {{ background:#F5F5F5; font-family:"Microsoft YaHei UI","Segoe UI",sans-serif; font-size:13px; color:#202020; }}
            QTabWidget::pane {{ border:1px solid #E8E8E8; border-radius:8px; background:#FFFFFF; top:-1px; }}
            QTabBar::tab {{ background:transparent; color:#888; padding:8px 18px 6px; border:none; border-bottom:2px solid transparent; font-size:13px; }}
            QTabBar::tab:selected {{ color:#111; border-bottom:2px solid #222222; font-weight:bold; }}
            QTabBar::tab:hover:!selected {{ color:#555; background:#ECECEC; border-radius:4px 4px 0 0; }}
            QGroupBox {{ background:#FFFFFF; border:1px solid #EBEBEB; border-radius:8px; margin-top:12px; padding:14px 12px 10px; font-weight:normal; }}
            QGroupBox::title {{ subcontrol-origin:margin; left:10px; top:2px; padding:0 4px; background:#FFFFFF; color:#888; font-size:12px; }}
            QCheckBox {{ spacing:6px; font-weight:normal; padding:3px 0; color:#333; }}
            QCheckBox::indicator {{ width:16px; height:16px; border:1.5px solid #BEBEBE; border-radius:3px; background:#FFF; }}
            QCheckBox::indicator:hover {{ border-color:#555555; }}
            QCheckBox::indicator:checked {{ background:#222222; border-color:#222222; image:url({check_path}); }}
            QCheckBox::indicator:checked:hover {{ background:#111111; border-color:#111111; }}
            QPushButton {{ background:#FAFAFA; border:1px solid #DADADA; border-radius:6px; padding:5px 14px; min-height:28px; color:#333; }}
            QPushButton:hover {{ background:#F0F0F0; border-color:#C0C0C0; }}
            QPushButton:pressed {{ background:#E4E4E4; }}
            QPushButton:checked {{ background:#EBEBEB; border-color:#333333; color:#333333; }}
            QPushButton#btn_save {{ background:#222222; border:none; color:#FFF; font-weight:bold; padding:6px 28px; border-radius:6px; }}
            QPushButton#btn_save:hover {{ background:#111111; }}
            QPushButton#btn_save:pressed {{ background:#000000; }}
            QPushButton#btn_reset {{ background:#F5F5F5; border:1px solid #DADADA; border-radius:6px; padding:5px 14px; min-height:28px; color:#333333; }}
            QPushButton#btn_reset:hover {{ background:#EBEBEB; border-color:#C0C0C0; }}
            QPushButton#btn_reset:pressed {{ background:#E0E0E0; }}
            QLineEdit {{ border:1px solid #DADADA; border-radius:5px; padding:5px 8px; background:#FFF; selection-background-color:#444444; color:#333; }}
            QLineEdit:focus {{ border:1.5px solid #444444; padding:4px 7px; }}
            QTextEdit {{ border:1px solid #DADADA; border-radius:5px; padding:5px; background:#FFF; color:#333; }}
            QTextEdit:focus {{ border:1.5px solid #444444; padding:4px; }}
            QListWidget {{ border:1px solid #DADADA; border-radius:6px; background:#FFF; padding:3px; outline:none; }}
            QListWidget::item {{ padding:5px 8px; border-radius:4px; color:#333; }}
            QListWidget::item:hover {{ background:#F0F0F0; }}
            QListWidget::item:selected {{ background:#E0E0E0; color:#111111; }}
            QSlider::groove:horizontal {{ height:3px; background:#E0E0E0; border-radius:1px; }}
            QSlider::handle:horizontal {{ width:14px; height:14px; margin:-5px 0; background:#FFF; border:1.5px solid #444444; border-radius:7px; }}
            QSlider::handle:horizontal:hover {{ background:#EBEBEB; }}
            QSlider::handle:horizontal:pressed {{ background:#222222; border-color:#111111; }}
            QSlider::sub-page:horizontal {{ background:#444444; border-radius:1px; }}
            QLabel {{ background:transparent; color:#444; }}
            QLabel#status_label {{ color:#222222; font-weight:bold; }}
            QScrollBar:vertical {{ width:5px; background:transparent; }}
            QScrollBar::handle:vertical {{ background:#CCC; border-radius:2px; min-height:24px; }}
            QScrollBar::handle:vertical:hover {{ background:#AAA; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; background:none; }}
            QMenu {{ background:#FFF; border:1px solid #E0E0E0; border-radius:8px; padding:4px; }}
            QMenu::item {{ padding:5px 20px 5px 10px; border-radius:4px; }}
            QMenu::item:selected {{ background:#EBEBEB; }}
            QMenu::item:disabled {{ color:#B0B0B0; }}
            QToolTip {{ background:#FFF; border:1px solid #DDD; border-radius:4px; padding:4px 8px; color:#333; font-size:12px; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_general_tab(), '通用')
        self._tabs.addTab(self._build_rules_tab(), '清洗规则')
        self._tabs.addTab(self._build_llm_tab(), '大模型')
        self._tabs.addTab(self._build_about_tab(), '关于')
        layout.addWidget(self._tabs)

        bottom = QHBoxLayout()
        self._status_lbl = QLabel('')
        self._status_lbl.setObjectName('status_label')
        bottom.addWidget(self._status_lbl)
        bottom.addStretch()
        save_btn = QPushButton('保存')
        save_btn.setObjectName('btn_save')
        save_btn.clicked.connect(self._do_save)
        bottom.addWidget(save_btn)
        layout.addLayout(bottom)

    # ── 通用 Tab ──────────────────────────────────────────────

    def _build_general_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(6)

        self._chk_toast = QCheckBox('显示清洗完成通知（Toast）')
        self._chk_toast.setChecked(self._config.get('general.toast_notification', True))
        self._chk_toast.stateChanged.connect(
            lambda v: self._mark('general.toast_notification', bool(v)))
        layout.addWidget(self._chk_toast)

        self._chk_startup = QCheckBox('开机自动启动')
        self._chk_startup.setChecked(self._config.get('general.startup_with_windows', False))
        self._chk_startup.stateChanged.connect(
            lambda v: self._mark('general.startup_with_windows', bool(v)))
        layout.addWidget(self._chk_startup)

        # 独立热键
        hk_box = QGroupBox('独立热键')
        hk_lay = QHBoxLayout(hk_box)
        self._chk_hotkey = QCheckBox('启用')
        self._chk_hotkey.setChecked(self._config.get('general.custom_hotkey.enabled', True))
        self._chk_hotkey.stateChanged.connect(
            lambda v: self._mark('general.custom_hotkey.enabled', bool(v)))
        self._btn_record = QPushButton(
            self._config.get('general.custom_hotkey.keys', 'ctrl+shift+c'))
        self._btn_record.setCheckable(True)
        self._btn_record.clicked.connect(self._on_clean_hotkey_btn)
        hk_lay.addWidget(self._chk_hotkey)
        hk_lay.addWidget(QLabel('热键：'))
        hk_lay.addWidget(self._btn_record)
        layout.addWidget(hk_box)

        # 双击 Ctrl+C
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

        # 轮盘 Prompt 选择器设置
        layout.addWidget(self._build_wheel_group())

        # 预览面板设置
        layout.addWidget(self._build_preview_group())

        layout.addStretch()
        btn_reset_general = QPushButton('恢复通用默认设置')
        btn_reset_general.setObjectName('btn_reset')
        btn_reset_general.clicked.connect(self._confirm_and_reset_general)
        layout.addWidget(btn_reset_general)
        return w

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

    def _build_wheel_group(self) -> QGroupBox:
        """构建轮盘 Prompt 选择器设置分组。"""
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
        self._btn_wheel_hotkey.clicked.connect(self._on_wheel_hotkey_btn)
        sw_hk_lay.addWidget(self._btn_wheel_hotkey)
        sw_hk_lay.addStretch()
        wheel_lay.addLayout(sw_hk_lay)

        # 可见 Prompt 配置
        wheel_lay.addWidget(QLabel('轮盘显示的 Prompt（最多5个）：'))
        self._wheel_prompt_list = QListWidget()
        self._wheel_prompt_list.setMaximumHeight(100)
        self._wheel_prompt_list.itemChanged.connect(self._on_wheel_prompt_item_changed)
        self._refresh_wheel_prompts()
        wheel_lay.addWidget(self._wheel_prompt_list)

        # 根据启用状态更新子控件可用性
        self._update_wheel_subwidgets()
        return wheel_box

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
            # 超过5个，阻止勾选
            self._wheel_prompt_list.blockSignals(True)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._wheel_prompt_list.blockSignals(False)
            # 状态栏提示（借用 _status_lbl）
            self._status_lbl.setText('轮盘最多显示5个 Prompt')
            QTimer.singleShot(2000, lambda: self._status_lbl.setText(''))
            return

        # 更新 pending 中的 prompts 列表
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
        self._btn_preview_hotkey.clicked.connect(self._on_preview_hotkey_btn)
        hk_lay.addWidget(self._btn_preview_hotkey)
        hk_lay.addStretch()
        preview_lay.addLayout(hk_lay)

        # 主题切换按钮
        theme_lay = QHBoxLayout()
        theme_lay.addWidget(QLabel('面板主题：'))
        self._btn_theme_dark = QPushButton('深色')
        self._btn_theme_dark.setCheckable(True)
        self._btn_theme_light = QPushButton('浅色')
        self._btn_theme_light.setCheckable(True)
        current_theme = self._config.get('preview.theme', 'dark')
        self._btn_theme_dark.setChecked(current_theme == 'dark')
        self._btn_theme_light.setChecked(current_theme == 'light')
        self._btn_theme_dark.clicked.connect(self._on_theme_dark_clicked)
        self._btn_theme_light.clicked.connect(self._on_theme_light_clicked)
        theme_lay.addWidget(self._btn_theme_dark)
        theme_lay.addWidget(self._btn_theme_light)
        theme_lay.addStretch()
        preview_lay.addLayout(theme_lay)

        return preview_box

    def _on_preview_hotkey_btn(self, checked: bool):
        """预览热键录制按钮点击。"""
        if checked:
            self._btn_preview_hotkey.setText('请按下热键组合...')
            # 取消其他录制按钮的 checked 状态
            self._btn_record.setChecked(False)
            self._btn_wheel_hotkey.setChecked(False)
            self.grabKeyboard()
            self._recording_target = 'preview'
        else:
            self.releaseKeyboard()
            self._recording_target = None

    def _on_theme_dark_clicked(self):
        """深色主题按钮点击。"""
        self._btn_theme_dark.setChecked(True)
        self._btn_theme_light.setChecked(False)
        self._mark('preview.theme', 'dark')

    def _on_theme_light_clicked(self):
        """浅色主题按钮点击。"""
        self._btn_theme_dark.setChecked(False)
        self._btn_theme_light.setChecked(True)
        self._mark('preview.theme', 'light')

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

    def keyPressEvent(self, event):
        """捕获热键录制（清洗热键和轮盘切换热键通用）。"""
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

        # 始终用枚举名获取键名，避免 Ctrl 按住时 event.text() 返回控制字符（如 \x03）
        try:
            key_str = _Qt.Key(key).name  # e.g. 'Key_C' → 'c', 'Key_F5' → 'f5'
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

    def _on_interval_changed(self, value: int):
        self._lbl_interval.setText(f'间隔阈值：{value} ms')
        self._mark('general.double_ctrl_c.interval_ms', value)

    # ── 规则 Tab ──────────────────────────────────────────────

    def _build_rules_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(6)

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
        return w

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
        # 同步 LLM Tab 的 Checkbox
        self._chk_llm.blockSignals(True)
        self._chk_llm.setChecked(mode == 'llm')
        self._chk_llm.blockSignals(False)

    # ── 大模型 Tab ────────────────────────────────────────────

    def _build_llm_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(6)

        self._chk_llm = QCheckBox('启用大模型模式（与规则模式互斥）')
        self._chk_llm.setChecked(self._config.get('rules.mode') == 'llm')
        self._chk_llm.stateChanged.connect(self._on_llm_checkbox_toggled)
        layout.addWidget(self._chk_llm)

        api_box = QGroupBox('API 配置')
        api_lay = QVBoxLayout(api_box)

        _api_fields = [
            ('Base URL', 'llm.base_url', 'https://api.openai.com/v1'),
            ('Model ID', 'llm.model_id', 'gpt-4o-mini'),
        ]
        self._le_base_url: QLineEdit | None = None
        self._le_model_id: QLineEdit | None = None
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
        btn_show.setFixedWidth(50)
        btn_show.toggled.connect(
            lambda on: self._le_apikey.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
        key_row.addWidget(self._le_apikey)
        key_row.addWidget(btn_show)
        api_lay.addLayout(key_row)

        temp_row = QHBoxLayout()
        temp_val = self._config.get('llm.temperature', 0.2)
        self._lbl_temp = QLabel(f'Temperature：{temp_val:.1f}')
        self._sld_temp = QSlider(Qt.Orientation.Horizontal)
        self._sld_temp.setRange(0, 20)
        self._sld_temp.setValue(int(temp_val * 10))
        self._sld_temp.valueChanged.connect(self._on_temp_changed)
        temp_row.addWidget(self._lbl_temp)
        temp_row.addWidget(self._sld_temp)
        api_lay.addLayout(temp_row)
        layout.addWidget(api_box)

        btn_row = QHBoxLayout()
        self._btn_test = QPushButton('测试连接')
        self._btn_test.clicked.connect(self._on_test_connection)
        btn_row.addWidget(self._btn_test)
        btn_reset_llm = QPushButton('恢复 API 默认配置')
        btn_reset_llm.setObjectName('btn_reset')
        btn_reset_llm.clicked.connect(self._confirm_and_reset_llm_api)
        btn_row.addWidget(btn_reset_llm)
        layout.addLayout(btn_row)

        prompt_box = QGroupBox('Prompt 模板')
        prompt_lay = QVBoxLayout(prompt_box)
        self._prompt_list = QListWidget()
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

        layout.addStretch()
        return w

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
        # 同步规则Tab的RadioButton（不触发信号避免循环）
        self._rb_rules.blockSignals(True)
        self._rb_llm.blockSignals(True)
        self._rb_rules.setChecked(mode == 'rules')
        self._rb_llm.setChecked(mode == 'llm')
        self._rb_rules.blockSignals(False)
        self._rb_llm.blockSignals(False)

    def _on_temp_changed(self, value: int):
        temp = value / 10.0
        self._lbl_temp.setText(f'Temperature：{temp:.1f}')
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
        # 同步轮盘可见 Prompt 列表
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
        # 先编辑内容
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

    # ── 关于 Tab ──────────────────────────────────────────────

    def _build_about_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 20, 12, 12)
        layout.setSpacing(12)

        # 版本信息
        version_box = QGroupBox('版本信息')
        version_lay = QVBoxLayout(version_box)
        version_lay.addWidget(QLabel(f'当前版本：v{VERSION}'))
        btn_check = QPushButton('检查更新')
        btn_check.clicked.connect(self._on_check_update)
        version_lay.addWidget(btn_check)
        layout.addWidget(version_box)

        # 作者信息
        author_box = QGroupBox('作者')
        author_lay = QVBoxLayout(author_box)
        author_lay.addWidget(QLabel('StoneLL1'))
        layout.addWidget(author_box)

        # GitHub 链接
        github_box = QGroupBox('项目地址')
        github_lay = QVBoxLayout(github_box)
        github_link = QLabel('<a href="https://github.com/StoneLL1/NeatCopy" style="color:#333;">github.com/StoneLL1/NeatCopy</a>')
        github_link.setTextFormat(Qt.TextFormat.RichText)
        github_link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        github_link.linkActivated.connect(self._open_github)
        github_lay.addWidget(github_link)
        github_lay.addWidget(QLabel('欢迎 Star ⭐'))
        layout.addWidget(github_box)

        layout.addStretch()
        return w

    def _on_check_update(self):
        btn = self.findChild(QPushButton, 'btn_check_update')
        if btn:
            btn.setEnabled(False)
            btn.setText('检查中...')

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
        btn = self.findChild(QPushButton)
        # 查找"检查更新"按钮
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

    # ── 保存 ─────────────────────────────────────────────────

    def _mark(self, key: str, value):
        self._pending[key] = value

    def _do_save(self):
        # 保存预览启用状态
        if hasattr(self, '_chk_preview'):
            self._mark('preview.enabled', self._chk_preview.isChecked())
        for key, value in self._pending.items():
            self._config.set(key, value)
        self._pending.clear()
        if self._hotkey_manager:
            self._hotkey_manager.reload_config(self._config)
        self._status_lbl.setText('已保存 ✓')
        QTimer.singleShot(1500, lambda: self._status_lbl.setText(''))
