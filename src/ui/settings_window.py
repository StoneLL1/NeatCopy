# 设置界面：三Tab（通用/清洗规则/大模型），点击保存后写入配置。
import uuid
from PyQt6.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QCheckBox, QSlider, QPushButton, QGroupBox,
    QRadioButton, QLineEdit, QListWidget, QListWidgetItem,
    QTextEdit, QInputDialog, QMessageBox, QMenu, QSizePolicy,
)
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

        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_general_tab(), '通用')
        self._tabs.addTab(self._build_rules_tab(), '清洗规则')
        self._tabs.addTab(self._build_llm_tab(), '大模型')
        layout.addWidget(self._tabs)

        bottom = QHBoxLayout()
        self._status_lbl = QLabel('')
        self._status_lbl.setStyleSheet('color: #4CAF50;')
        bottom.addWidget(self._status_lbl)
        bottom.addStretch()
        save_btn = QPushButton('保存')
        save_btn.clicked.connect(self._do_save)
        bottom.addWidget(save_btn)
        layout.addLayout(bottom)

    # ── 通用 Tab ──────────────────────────────────────────────

    def _build_general_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

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
        key_text = event.text().lower().strip()
        if key_text and key_text.isprintable():
            self._recording_keys = mods + [key_text]
            self._btn_record.setChecked(False)

    # ── 规则 Tab ──────────────────────────────────────────────

    def _build_rules_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        mode_box = QGroupBox('清洗模式')
        mode_lay = QHBoxLayout(mode_box)
        self._rb_rules = QRadioButton('规则模式')
        self._rb_llm = QRadioButton('大模型模式')
        current = self._config.get('rules.mode', 'rules')
        self._rb_rules.setChecked(current == 'rules')
        self._rb_llm.setChecked(current == 'llm')
        self._rb_rules.toggled.connect(
            lambda on: self._mark('rules.mode', 'rules') if on else None)
        self._rb_llm.toggled.connect(
            lambda on: self._mark('rules.mode', 'llm') if on else None)
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

    # ── 大模型 Tab ────────────────────────────────────────────

    def _build_llm_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        self._chk_llm = QCheckBox('启用大模型模式（与规则模式互斥）')
        self._chk_llm.setChecked(self._config.get('llm.enabled', False))
        self._chk_llm.stateChanged.connect(
            lambda v: self._mark('llm.enabled', bool(v)))
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

        btn_test = QPushButton('测试连接')
        btn_test.clicked.connect(self._on_test_connection)
        layout.addWidget(btn_test)

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
        import asyncio
        self._do_save()
        llm_cfg = self._config.get('llm') or {}
        try:
            from llm_client import LLMClient, classify_error
            client = LLMClient()
            result = asyncio.run(client.test_connection(llm_cfg))
            QMessageBox.information(self, '连接成功', f'模型回复：{result[:200]}')
        except Exception as e:
            from llm_client import classify_error
            QMessageBox.critical(self, '连接失败', classify_error(e))

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
