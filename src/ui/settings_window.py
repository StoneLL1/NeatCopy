# 设置界面：三Tab（通用/清洗规则/大模型），点击保存后写入配置。
import uuid
from PyQt6.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QCheckBox, QSlider, QPushButton, QGroupBox,
    QRadioButton, QLineEdit, QListWidget, QListWidgetItem,
    QTextEdit, QInputDialog, QMessageBox, QMenu, QSizePolicy,
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, QTimer


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
        self.setMinimumWidth(480)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
        import os
        icon_path = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'idle.png'))
        self.setWindowIcon(QIcon(icon_path))
        check_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'check.png')
        ).replace('\\', '/')
        self.setStyleSheet(f"""
            QDialog {{ background:#F3F3F3; font-family:"Microsoft YaHei UI","Segoe UI",sans-serif; font-size:13px; color:#1A1A1A; }}
            QTabWidget::pane {{ border:1px solid #E0E0E0; border-radius:8px; background:#FFF; top:-1px; }}
            QTabBar::tab {{ background:transparent; color:#606060; padding:8px 20px; border:none; border-bottom:2px solid transparent; }}
            QTabBar::tab:selected {{ color:#3B82F6; border-bottom:2px solid #3B82F6; font-weight:bold; }}
            QTabBar::tab:hover:!selected {{ color:#1A1A1A; background:#F0F0F0; border-radius:4px 4px 0 0; }}
            QGroupBox {{ background:#FAFAFA; border:1px solid #E5E5E5; border-radius:8px; margin-top:16px; padding:16px 12px 12px; font-weight:bold; }}
            QGroupBox::title {{ subcontrol-origin:margin; left:12px; top:4px; padding:0 6px; background:#FAFAFA; color:#3B82F6; }}
            QCheckBox {{ spacing:8px; font-weight:normal; padding:4px 0; }}
            QCheckBox::indicator {{ width:18px; height:18px; border:2px solid #C0C0C0; border-radius:4px; background:#FFF; }}
            QCheckBox::indicator:hover {{ border-color:#3B82F6; }}
            QCheckBox::indicator:checked {{ background:#3B82F6; border-color:#3B82F6; image:url({check_path}); }}
            QRadioButton {{ spacing:8px; font-weight:normal; padding:4px 0; }}
            QRadioButton::indicator {{ width:18px; height:18px; border:2px solid #C0C0C0; border-radius:10px; background:#FFF; }}
            QRadioButton::indicator:hover {{ border-color:#3B82F6; }}
            QRadioButton::indicator:checked {{ border:5px solid #3B82F6; background:#3B82F6; }}
            QPushButton {{ background:#FFF; border:1px solid #D0D0D0; border-radius:6px; padding:6px 16px; min-height:20px; }}
            QPushButton:hover {{ background:#F0F0F0; border-color:#B0B0B0; }}
            QPushButton:pressed {{ background:#E0E0E0; }}
            QPushButton:checked {{ background:#EBF2FF; border-color:#3B82F6; color:#3B82F6; }}
            QPushButton#btn_save {{ background:#3B82F6; border:1px solid #2563EB; color:#FFF; font-weight:bold; padding:7px 24px; }}
            QPushButton#btn_save:hover {{ background:#2563EB; }}
            QPushButton#btn_save:pressed {{ background:#1D4ED8; }}
            QLineEdit {{ border:1px solid #D0D0D0; border-radius:6px; padding:6px 10px; background:#FFF; selection-background-color:#3B82F6; }}
            QLineEdit:focus {{ border:2px solid #3B82F6; padding:5px 9px; }}
            QTextEdit {{ border:1px solid #D0D0D0; border-radius:6px; padding:6px; background:#FFF; }}
            QTextEdit:focus {{ border:2px solid #3B82F6; padding:5px; }}
            QListWidget {{ border:1px solid #D0D0D0; border-radius:6px; background:#FFF; padding:4px; outline:none; }}
            QListWidget::item {{ padding:6px 8px; border-radius:4px; }}
            QListWidget::item:hover {{ background:#F0F4FF; }}
            QListWidget::item:selected {{ background:#E0EAFF; color:#1A1A1A; }}
            QSlider::groove:horizontal {{ height:4px; background:#E0E0E0; border-radius:2px; }}
            QSlider::handle:horizontal {{ width:16px; height:16px; margin:-6px 0; background:#FFF; border:2px solid #3B82F6; border-radius:9px; }}
            QSlider::handle:horizontal:hover {{ background:#EBF2FF; }}
            QSlider::sub-page:horizontal {{ background:#3B82F6; border-radius:2px; }}
            QLabel {{ background:transparent; }}
            QLabel#status_label {{ color:#4CAF50; font-weight:bold; }}
            QScrollBar:vertical {{ width:6px; background:transparent; }}
            QScrollBar::handle:vertical {{ background:#C0C0C0; border-radius:3px; min-height:30px; }}
            QScrollBar::handle:vertical:hover {{ background:#A0A0A0; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; background:none; }}
            QMenu {{ background:#FFF; border:1px solid #E0E0E0; border-radius:8px; padding:4px; }}
            QMenu::item {{ padding:6px 24px 6px 12px; border-radius:4px; }}
            QMenu::item:selected {{ background:#EBF2FF; }}
            QMenu::item:disabled {{ color:#A0A0A0; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_general_tab(), '通用')
        self._tabs.addTab(self._build_rules_tab(), '清洗规则')
        self._tabs.addTab(self._build_llm_tab(), '大模型')
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
        layout.setSpacing(8)

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
        self._btn_record.setToolTip('点击后按下组合键进行录制')
        self._btn_record.toggled.connect(self._on_record_toggle)
        self._recording_keys: list[str] = []
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

        layout.addStretch()
        return w

    def _on_interval_changed(self, value: int):
        self._lbl_interval.setText(f'间隔阈值：{value} ms')
        self._mark('general.double_ctrl_c.interval_ms', value)

    def _on_record_toggle(self, recording: bool):
        if recording:
            self._btn_record.setText('按下组合键...')
            self._recording_keys = []
        else:
            if self._recording_keys:
                combo = '+'.join(self._recording_keys)
                self._btn_record.setText(combo)
                self._mark('general.custom_hotkey.keys', combo)

    # Qt.Key 到 keyboard 库键名的映射
    _KEY_MAP = {
        Qt.Key.Key_F1: 'f1', Qt.Key.Key_F2: 'f2', Qt.Key.Key_F3: 'f3',
        Qt.Key.Key_F4: 'f4', Qt.Key.Key_F5: 'f5', Qt.Key.Key_F6: 'f6',
        Qt.Key.Key_F7: 'f7', Qt.Key.Key_F8: 'f8', Qt.Key.Key_F9: 'f9',
        Qt.Key.Key_F10: 'f10', Qt.Key.Key_F11: 'f11', Qt.Key.Key_F12: 'f12',
        Qt.Key.Key_Insert: 'insert', Qt.Key.Key_Delete: 'delete',
        Qt.Key.Key_Home: 'home', Qt.Key.Key_End: 'end',
        Qt.Key.Key_PageUp: 'page up', Qt.Key.Key_PageDown: 'page down',
        Qt.Key.Key_Space: 'space', Qt.Key.Key_Tab: 'tab',
        Qt.Key.Key_Escape: 'esc', Qt.Key.Key_Return: 'enter',
        Qt.Key.Key_Enter: 'enter', Qt.Key.Key_Backspace: 'backspace',
    }

    def keyPressEvent(self, event):
        if not self._btn_record.isChecked():
            return super().keyPressEvent(event)
        mods = []
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            mods.append('ctrl')
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            mods.append('shift')
        if event.modifiers() & Qt.KeyboardModifier.AltModifier:
            mods.append('alt')
        # 优先查映射表（F 键、特殊键）
        key_name = self._KEY_MAP.get(Qt.Key(event.key()))
        if not key_name:
            key_text = event.text().lower().strip()
            if key_text and key_text.isprintable():
                key_name = key_text
        if key_name:
            self._recording_keys = mods + [key_name]
            self._btn_record.setChecked(False)

    # ── 规则 Tab ──────────────────────────────────────────────

    def _build_rules_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)

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
        layout.setSpacing(8)

        self._chk_llm = QCheckBox('启用大模型模式（与规则模式互斥）')
        self._chk_llm.setChecked(self._config.get('rules.mode') == 'llm')
        self._chk_llm.stateChanged.connect(self._on_llm_checkbox_toggled)
        layout.addWidget(self._chk_llm)

        api_box = QGroupBox('API 配置')
        api_lay = QVBoxLayout(api_box)

        for label, key, placeholder in [
            ('Base URL', 'llm.base_url', 'https://api.openai.com/v1'),
            ('Model ID', 'llm.model_id', 'gpt-4o-mini'),
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(f'{label}：'))
            le = QLineEdit(str(self._config.get(key, placeholder)))
            le.setPlaceholderText(placeholder)
            le.textChanged.connect(lambda t, k=key: self._mark(k, t))
            row.addWidget(le)
            api_lay.addLayout(row)

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

        self._btn_test = QPushButton('测试连接')
        self._btn_test.clicked.connect(self._on_test_connection)
        layout.addWidget(self._btn_test)

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

    # ── 保存 ─────────────────────────────────────────────────

    def _mark(self, key: str, value):
        self._pending[key] = value

    def _do_save(self):
        for key, value in self._pending.items():
            self._config.set(key, value)
        self._pending.clear()
        if self._hotkey_manager:
            self._hotkey_manager.reload_config(self._config)
        self._status_lbl.setText('已保存 ✓')
        QTimer.singleShot(1500, lambda: self._status_lbl.setText(''))
