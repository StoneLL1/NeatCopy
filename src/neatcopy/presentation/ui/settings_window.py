from __future__ import annotations

# 设置界面：三Tab（通用/清洗规则/大模型），点击保存后写入配置。
import sys
import os
import uuid
import base64
from PyQt6.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QCheckBox, QSlider, QPushButton, QGroupBox,
    QLineEdit, QListWidget, QListWidgetItem,
    QTextEdit, QInputDialog, QMessageBox, QMenu, QSpinBox, QScrollArea,
)
from PyQt6.QtGui import QColor, QFontDatabase, QIcon, QImage, QKeyEvent, QLinearGradient, QPainter, QPaintEvent, QPen, QPixmap
from PyQt6.QtCore import QPointF
from PyQt6.QtCore import Qt, QTimer

from neatcopy.application.history_service import PasteHistoryService
from neatcopy.application.settings_service import SettingsService
from neatcopy.infrastructure.hotkey_manager import (
    _parse_hotkey,
    copy_shortcut_label,
    hotkey_example,
)
from neatcopy.infrastructure.llm_client import LLMClient, classify_error


def _asset(filename: str) -> str:
    if getattr(sys, 'frozen', False):
        base = os.path.join(sys._MEIPASS, 'assets')
    else:
        base = os.path.normpath(
            os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'assets')
        )
    return os.path.join(base, filename)


COPY_SHORTCUT = copy_shortcut_label()
HOTKEY_EXAMPLE = hotkey_example()

_QT_KEY_MAP = {
    Qt.Key.Key_Space: 'space',
    Qt.Key.Key_Return: 'enter',
    Qt.Key.Key_Enter: 'enter',
    Qt.Key.Key_Tab: 'tab',
    Qt.Key.Key_Escape: 'esc',
    Qt.Key.Key_Backspace: 'backspace',
    Qt.Key.Key_Delete: 'delete',
    Qt.Key.Key_Insert: 'insert',
    Qt.Key.Key_Home: 'home',
    Qt.Key.Key_End: 'end',
    Qt.Key.Key_PageUp: 'page up',
    Qt.Key.Key_PageDown: 'page down',
}


def _modifiers_to_tokens(modifiers: Qt.KeyboardModifier) -> list[str]:
    tokens = []
    is_macos = sys.platform == 'darwin'
    if modifiers & Qt.KeyboardModifier.ControlModifier:
        # Qt on macOS reports the physical Command key as ControlModifier.
        tokens.append('cmd' if is_macos else 'ctrl')
    if modifiers & Qt.KeyboardModifier.AltModifier:
        tokens.append('alt')
    if modifiers & Qt.KeyboardModifier.ShiftModifier:
        tokens.append('shift')
    if modifiers & Qt.KeyboardModifier.MetaModifier:
        # Qt on macOS reports the physical Control key as MetaModifier.
        tokens.append('ctrl' if is_macos else 'cmd')
    return tokens


def _key_to_token(key: int) -> str:
    if key in _QT_KEY_MAP:
        return _QT_KEY_MAP[key]
    if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
        return chr(key).lower()
    if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        return chr(key)
    if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F12:
        return f'f{key - Qt.Key.Key_F1 + 1}'
    return ''


class _HotkeyCaptureDialog(QDialog):
    def __init__(self, current_hotkey: str, parent=None):
        super().__init__(parent)
        self._captured = ''
        self.setWindowTitle('录制热键 // INPUT CAPTURE')
        self.setModal(True)
        self.setFixedSize(360, 140)
        self.setStyleSheet("""
            QDialog {
                background:#05090D;
                color:#E8FFF6;
                font-family:"SF Mono","Menlo","Monaco","Courier New",monospace;
                border:2px solid #26FFD5;
            }
            QLabel {
                color:#D7FFF0;
                letter-spacing:0.04em;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(QLabel('按下你想设置的组合键'))
        self._preview = QLabel(current_hotkey or HOTKEY_EXAMPLE)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet(
            'QLabel { border:2px solid #FF4FD8; border-radius:0px; padding:12px; '
            'background:#090F14; color:#26FFD5; font-weight:bold; font-size:16px; }'
        )
        layout.addWidget(self._preview)

        hint = QLabel('Esc 取消')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

    @property
    def captured(self) -> str:
        return self._captured

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return

        tokens = _modifiers_to_tokens(event.modifiers())
        key_token = _key_to_token(event.key())
        if not key_token:
            return

        combo = '+'.join(tokens + [key_token]) if tokens else key_token
        self._captured = combo
        self._preview.setText(combo)
        self.accept()


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
    _fonts_loaded = False

    def __init__(self, config, hotkey_manager=None, parent=None):
        super().__init__(parent)
        self._ensure_fonts()
        self._config = config
        self._hotkey_manager = hotkey_manager
        self._history_service = PasteHistoryService(config)
        self._settings_service = SettingsService(config, hotkey_manager=hotkey_manager)
        self._pending: dict = {}
        self._tab_copy = {
            0: ('通用设置', '触发方式、通知与粘贴轮盘。'),
            1: ('清洗规则', '规则模式与文本清洗选项。'),
            2: ('大模型', '模型连接、模板与智能处理。'),
        }

        self.setWindowTitle('NeatCopy // Neo Arcade Console')
        self.resize(900, 680)
        self.setMinimumSize(860, 640)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
        self.setWindowIcon(QIcon(_asset('idle.png')))
        check_path = _asset('check.png').replace('\\', '/')
        self.setStyleSheet(f"""
            QDialog {{
                background:transparent;
                font-family:"Avenir Next","PingFang SC","Segoe UI",sans-serif;
                font-size:13px;
                color:#DDFEF5;
            }}
            QWidget#sidebar {{
                background:rgba(7,12,16,0.92);
                border:2px solid rgba(38,255,213,0.65);
                border-radius:8px;
            }}
            QWidget#content_surface {{
                background:rgba(5,9,13,0.94);
                border:2px solid rgba(255,79,216,0.55);
                border-radius:8px;
            }}
            QWidget#surface_header {{
                background:transparent;
                border-bottom:1px solid rgba(38,255,213,0.24);
            }}
            QWidget#hero_panel {{
                background:rgba(8,14,20,0.96);
                border-radius:6px;
                border:2px solid rgba(255,79,216,0.52);
            }}
            QLabel#hero_eyebrow {{
                color:#26FFD5;
                font-family:"Silkscreen","SF Mono","Menlo","Monaco",monospace;
                font-size:11px;
                font-weight:700;
                letter-spacing:0.08em;
                text-transform:uppercase;
            }}
            QLabel#hero_title {{
                color:#F5FF63;
                font-family:"Silkscreen","SF Mono","Menlo","Monaco",monospace;
                font-size:28px;
                font-weight:800;
            }}
            QLabel#hero_subtitle {{
                color:#C6FFEF;
                font-family:"Fusion Pixel 10px Prop zh_hans","Avenir Next","PingFang SC","Segoe UI",sans-serif;
                font-size:13px;
                line-height:1.4em;
            }}
            QLabel#hero_chip {{
                color:#E7FFF8;
                background:rgba(9,18,24,0.96);
                border:1px solid rgba(38,255,213,0.48);
                border-radius:0px;
                padding:5px 9px;
                font-family:"Silkscreen","SF Mono","Menlo","Monaco",monospace;
                font-size:9px;
                font-weight:700;
            }}
            QLabel#sidebar_section {{
                color:#FF4FD8;
                font-family:"Silkscreen","SF Mono","Menlo","Monaco",monospace;
                font-size:10px;
                font-weight:700;
                letter-spacing:0.08em;
                text-transform:uppercase;
            }}
            QWidget#signal_panel {{
                background:rgba(9,15,21,0.94);
                border:1px solid rgba(245,255,99,0.35);
                border-radius:4px;
            }}
            QWidget#logo_panel {{
                background:rgba(8,14,20,0.58);
                border:1px solid rgba(38,255,213,0.16);
                border-radius:4px;
            }}
            QLabel#stone_logo {{
                background:transparent;
                padding:8px;
            }}
            QLabel#signal_value {{
                color:#F5FF63;
                font-family:"Fusion Pixel 10px Prop zh_hans","Silkscreen","SF Mono","Menlo","Monaco",monospace;
                font-size:12px;
                font-weight:700;
            }}
            QLabel#signal_label {{
                color:#95BBAE;
                font-size:11px;
            }}
            QLabel#surface_eyebrow {{
                color:#26FFD5;
                font-family:"Silkscreen","SF Mono","Menlo","Monaco",monospace;
                font-size:11px;
                font-weight:700;
                letter-spacing:0.06em;
            }}
            QLabel#surface_title {{
                color:#F7FCE2;
                font-family:"Fusion Pixel 10px Prop zh_hans","Silkscreen","SF Mono","Menlo","Monaco",monospace;
                font-size:22px;
                font-weight:700;
            }}
            QLabel#surface_meta {{
                color:#8AD7C3;
                font-family:"Fusion Pixel 10px Prop zh_hans","Avenir Next","PingFang SC","Segoe UI",sans-serif;
                font-size:12px;
            }}
            QLabel#section_intro {{
                color:#89C9B8;
                font-size:12px;
                padding:0 0 4px 0;
            }}
            QTabWidget::pane {{
                border:none;
                background:transparent;
                top:0px;
            }}
            QScrollArea {{
                border:none;
                background:transparent;
            }}
            QScrollArea > QWidget > QWidget {{
                background:transparent;
            }}
            QTabBar {{
                background:rgba(7,12,17,0.84);
                border:1px solid rgba(38,255,213,0.24);
                padding:4px;
            }}
            QTabBar::tab {{
                background:rgba(10,19,26,0.96);
                color:#A8EBDD;
                text-align:center;
                padding:13px 0px 11px 0px;
                margin:0 4px 0 0;
                border:1px solid rgba(38,255,213,0.26);
                border-radius:0px;
                font-family:"Avenir Next","PingFang SC","Segoe UI",sans-serif;
                font-size:14px;
                font-weight:700;
                min-width:110px;
            }}
            QTabBar::tab:selected {{
                color:#081015;
                background:qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #8dfff1, stop:0.12 #26FFD5, stop:1 #18b9a0);
                border-color:#26FFD5;
            }}
            QTabBar::tab:hover:!selected {{
                color:#F6FFF3;
                background:rgba(255,79,216,0.18);
                border-color:rgba(255,79,216,0.32);
            }}
            QGroupBox {{
                background:rgba(8,13,18,0.92);
                border:1px solid rgba(38,255,213,0.18);
                border-radius:4px;
                margin-top:18px;
                font-weight:normal;
            }}
            QGroupBox::title {{
                subcontrol-origin:margin;
                left:14px;
                top:4px;
                padding:0 8px;
                background:rgba(5,9,13,0.96);
                color:#BCEFE2;
                font-family:"Silkscreen","SF Mono","Menlo","Monaco",monospace;
                font-size:11px;
                font-weight:700;
            }}
            QCheckBox {{
                spacing:10px;
                font-weight:600;
                padding:6px 0;
                color:#DDFEF5;
                font-size:13px;
            }}
            QCheckBox::indicator {{
                width:18px;
                height:18px;
                border:2px solid #26FFD5;
                border-radius:0px;
                background:#0A1218;
            }}
            QCheckBox::indicator:hover {{ border-color:#F5FF63; }}
            QCheckBox::indicator:checked {{
                background:#F5FF63;
                border-color:#F5FF63;
                image:url({check_path});
            }}
            QCheckBox::indicator:checked:hover {{
                background:#FFF98B;
                border-color:#FFF98B;
            }}
            QPushButton {{
                background:rgba(8,16,21,0.96);
                border:2px solid rgba(38,255,213,0.40);
                border-radius:0px;
                padding:7px 12px;
                min-height:30px;
                color:#E1FFF7;
                font-weight:700;
                font-size:13px;
            }}
            QPushButton:hover {{
                background:rgba(19,32,40,0.98);
                border-color:#26FFD5;
            }}
            QPushButton:pressed {{
                background:rgba(29,48,60,1.0);
            }}
            QPushButton:checked {{
                background:rgba(245,255,99,0.95);
                border-color:#F5FF63;
                color:#071015;
            }}
            QPushButton#btn_save {{
                background:#FF4FD8;
                border:2px solid #FF4FD8;
                color:#071015;
                font-weight:800;
                padding:10px 24px;
                border-radius:0px;
            }}
            QPushButton#btn_save:hover {{ background:#FF7BE3; border-color:#FF7BE3; }}
            QPushButton#btn_save:pressed {{ background:#F5FF63; border-color:#F5FF63; }}
            QPushButton#btn_reset {{
                background:rgba(19,8,18,0.78);
                border:1px solid rgba(255,79,216,0.28);
                color:#FF9FEF;
            }}
            QPushButton#btn_reset:hover {{
                background:rgba(39,13,35,0.92);
                border-color:rgba(255,79,216,0.54);
            }}
            QLineEdit {{
                border:1px solid rgba(38,255,213,0.20);
                border-radius:0px;
                padding:8px 10px;
                background:rgba(5,11,15,0.92);
                selection-background-color:#FF4FD8;
                color:#E8FFF6;
                font-size:13px;
            }}
            QLineEdit:focus {{
                border:2px solid #26FFD5;
                padding:7px 9px;
            }}
            QTextEdit {{
                border:1px solid rgba(38,255,213,0.20);
                border-radius:0px;
                padding:8px;
                background:rgba(5,11,15,0.92);
                color:#E8FFF6;
                font-size:13px;
            }}
            QTextEdit:focus {{
                border:2px solid #26FFD5;
                padding:7px;
            }}
            QListWidget {{
                border:1px solid rgba(38,255,213,0.20);
                border-radius:0px;
                background:rgba(5,11,15,0.88);
                padding:6px;
                outline:none;
                font-size:13px;
            }}
            QListWidget::item {{
                padding:9px 10px;
                border-radius:0px;
                color:#E1FFF7;
                margin:2px 0;
            }}
            QListWidget::item:hover {{ background:rgba(24,39,49,0.92); }}
            QListWidget::item:selected {{
                background:rgba(255,79,216,0.22);
                color:#F4FFF9;
            }}
            QSlider::groove:horizontal {{
                height:4px;
                background:#12313B;
                border-radius:0px;
            }}
            QSlider::handle:horizontal {{
                width:16px;
                height:16px;
                margin:-6px 0;
                background:#F5FF63;
                border:2px solid #26FFD5;
                border-radius:0px;
            }}
            QSlider::handle:horizontal:hover {{ background:#FFF98B; }}
            QSlider::handle:horizontal:pressed {{
                background:#FF4FD8;
                border-color:#FF4FD8;
            }}
            QSlider::sub-page:horizontal {{
                background:#26FFD5;
                border-radius:0px;
            }}
            QLabel {{
                background:transparent;
                color:#B7FFE6;
            }}
            QLabel#status_label {{
                color:#F5FF63;
                font-weight:800;
                font-size:13px;
            }}
            QScrollBar:vertical {{ width:5px; background:transparent; }}
            QScrollBar::handle:vertical {{ background:#26FFD5; border-radius:0px; min-height:24px; }}
            QScrollBar::handle:vertical:hover {{ background:#F5FF63; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; background:none; }}
            QMenu {{
                background:#071015;
                border:2px solid rgba(38,255,213,0.65);
                border-radius:0px;
                padding:6px;
            }}
            QMenu::item {{ padding:5px 20px 5px 10px; border-radius:0px; color:#E1FFF7; }}
            QMenu::item:selected {{ background:rgba(255,79,216,0.22); }}
            QMenu::item:disabled {{ color:#5A887C; }}
            QToolTip {{
                background:#061014;
                border:1px solid #26FFD5;
                border-radius:0px;
                padding:5px 8px;
                color:#E8FFF6;
                font-size:12px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        sidebar = QWidget()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(250)
        sidebar_lay = QVBoxLayout(sidebar)
        sidebar_lay.setContentsMargins(14, 14, 14, 14)
        sidebar_lay.setSpacing(12)

        hero = QWidget()
        hero.setObjectName('hero_panel')
        hero_lay = QVBoxLayout(hero)
        hero_lay.setContentsMargins(14, 14, 14, 14)
        hero_lay.setSpacing(6)
        self._hero_eyebrow = self._make_label('NEATCOPY', 'hero_eyebrow')
        hero_lay.addWidget(self._hero_eyebrow)
        self._hero_title = self._make_label('NeatCopy', 'hero_title')
        hero_lay.addWidget(self._hero_title)
        self._hero_subtitle = self._make_label(
            '剪贴板清洗与粘贴控制',
            'hero_subtitle',
        )
        hero_lay.addWidget(self._hero_subtitle)
        chip_row = QHBoxLayout()
        chip_row.setSpacing(6)
        self._hero_hotkey_chip = self._make_label('', 'hero_chip')
        chip_row.addWidget(self._hero_hotkey_chip)
        self._hero_mode_chip = self._make_label('', 'hero_chip')
        chip_row.addWidget(self._hero_mode_chip)
        chip_row.addStretch()
        hero_lay.addLayout(chip_row)
        sidebar_lay.addWidget(hero)

        sidebar_lay.addWidget(self._make_label('OVERVIEW', 'sidebar_section'))
        signal_panel = QWidget()
        signal_panel.setObjectName('signal_panel')
        signal_lay = QVBoxLayout(signal_panel)
        signal_lay.setContentsMargins(12, 12, 12, 12)
        signal_lay.setSpacing(10)
        self._sidebar_hotkey_value, hotkey_row = self._make_signal_row('HOTKEY', '')
        signal_lay.addLayout(hotkey_row)
        self._sidebar_mode_value, mode_row = self._make_signal_row('MODE', '')
        signal_lay.addLayout(mode_row)
        self._sidebar_wheel_value, wheel_row = self._make_signal_row('WHEEL', '')
        signal_lay.addLayout(wheel_row)
        self._sidebar_prompt_value, prompt_row = self._make_signal_row('ACTIVE PROMPT', '')
        signal_lay.addLayout(prompt_row)
        sidebar_lay.addWidget(signal_panel)
        sidebar_lay.addSpacing(18)

        logo_panel = QWidget()
        logo_panel.setObjectName('logo_panel')
        logo_lay = QVBoxLayout(logo_panel)
        logo_lay.setContentsMargins(10, 14, 10, 14)
        logo_lay.setSpacing(0)
        self._stone_logo = QLabel()
        self._stone_logo.setObjectName('stone_logo')
        self._stone_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stone_pixmap = QPixmap(_asset('cyber-stone-logo.png'))
        self._stone_logo.setPixmap(
            stone_pixmap.scaled(
                104,
                104,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        )
        logo_lay.addWidget(self._stone_logo)
        sidebar_lay.addWidget(logo_panel)
        sidebar_lay.addStretch()
        layout.addWidget(sidebar)

        content = QWidget()
        content.setObjectName('content_surface')
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(16, 16, 16, 16)
        content_lay.setSpacing(12)

        header = QWidget()
        header.setObjectName('surface_header')
        header_lay = QVBoxLayout(header)
        header_lay.setContentsMargins(0, 0, 0, 10)
        header_lay.setSpacing(4)
        header_lay.addWidget(self._make_label('CONTROL SURFACE', 'surface_eyebrow'))
        self._surface_title = self._make_label('', 'surface_title')
        header_lay.addWidget(self._surface_title)
        self._surface_meta = self._make_label('', 'surface_meta')
        header_lay.addWidget(self._surface_meta)
        content_lay.addWidget(header)
        self._refresh_hero_summary()

        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.TabPosition.North)
        self._tabs.setDocumentMode(True)
        self._tabs.tabBar().setExpanding(True)
        self._tabs.addTab(self._wrap_tab(self._build_general_tab()), '通用')
        self._tabs.addTab(self._wrap_tab(self._build_rules_tab()), '清洗规则')
        self._tabs.addTab(self._wrap_tab(self._build_llm_tab()), '大模型')
        self._tabs.currentChanged.connect(self._refresh_surface_header)
        content_lay.addWidget(self._tabs)

        bottom = QHBoxLayout()
        self._status_lbl = QLabel('')
        self._status_lbl.setObjectName('status_label')
        bottom.addWidget(self._status_lbl)
        bottom.addStretch()
        save_btn = QPushButton('保存')
        save_btn.setObjectName('btn_save')
        save_btn.clicked.connect(self._do_save)
        bottom.addWidget(save_btn)
        content_lay.addLayout(bottom)
        layout.addWidget(content, 1)
        self._refresh_surface_header()

    @classmethod
    def _ensure_fonts(cls) -> None:
        if cls._fonts_loaded:
            return
        QFontDatabase.addApplicationFont(_asset('Silkscreen-Regular.ttf'))
        QFontDatabase.addApplicationFont(_asset('FusionPixel-zh_hans.ttf'))
        cls._fonts_loaded = True

    def _make_label(self, text: str, object_name: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setWordWrap(True)
        return label

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        rect = self.rect()
        bg = QLinearGradient(QPointF(rect.topLeft()), QPointF(rect.bottomRight()))
        bg.setColorAt(0.0, QColor(3, 7, 10))
        bg.setColorAt(0.55, QColor(8, 10, 16))
        bg.setColorAt(1.0, QColor(11, 4, 16))
        painter.fillRect(rect, bg)

        painter.setPen(QPen(QColor(38, 255, 213, 16), 1))
        step = 24
        for x in range(0, rect.width(), step):
            painter.drawLine(x, 0, x, rect.height())
        for y in range(0, rect.height(), step):
            painter.drawLine(0, y, rect.width(), y)

        painter.setPen(QPen(QColor(255, 79, 216, 18), 1))
        for y in range(6, rect.height(), 6):
            painter.drawLine(0, y, rect.width(), y)

        painter.setPen(QPen(QColor(38, 255, 213, 120), 2))
        painter.drawRect(rect.adjusted(6, 6, -7, -7))
        painter.setPen(QPen(QColor(245, 255, 99, 180), 2))
        corner = 22
        painter.drawLine(16, 16, 16 + corner, 16)
        painter.drawLine(16, 16, 16, 16 + corner)
        painter.drawLine(rect.width() - 16, 16, rect.width() - 16 - corner, 16)
        painter.drawLine(rect.width() - 16, 16, rect.width() - 16, 16 + corner)
        painter.drawLine(16, rect.height() - 16, 16 + corner, rect.height() - 16)
        painter.drawLine(16, rect.height() - 16, 16, rect.height() - 16 - corner)
        painter.drawLine(rect.width() - 16, rect.height() - 16, rect.width() - 16 - corner, rect.height() - 16)
        painter.drawLine(rect.width() - 16, rect.height() - 16, rect.width() - 16, rect.height() - 16 - corner)
        super().paintEvent(event)

    def _make_signal_row(self, label: str, value: str):
        row = QVBoxLayout()
        row.setSpacing(2)
        value_label = self._make_label(value, 'signal_value')
        row.addWidget(value_label)
        row.addWidget(self._make_label(label, 'signal_label'))
        return value_label, row

    def _wrap_tab(self, widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(widget)
        return scroll

    def _tune_group_layout(self, layout):
        layout.setContentsMargins(14, 26, 14, 12)
        layout.setSpacing(10)

    def _refresh_hero_summary(self):
        hotkey = self._config.get('general.custom_hotkey.keys', HOTKEY_EXAMPLE)
        clear_hotkey_enabled = self._config.get('general.clear_clipboard_hotkey.enabled', False)
        clear_hotkey = self._config.get('general.clear_clipboard_hotkey.keys', '')
        wheel_enabled = self._config.get('wheel.enabled', True)
        prompts = self._config.get('llm.prompts') or []
        active_id = self._config.get('llm.active_prompt_id', 'default')
        active_prompt = next((prompt.get('name', 'Default') for prompt in prompts if prompt.get('id') == active_id), 'Default')
        self._hero_hotkey_chip.setText(
            f'HK // {hotkey}'
        )
        self._hero_mode_chip.setText('FLOW // WHEEL')
        hotkey_summary = hotkey.upper()
        if clear_hotkey_enabled and clear_hotkey:
            hotkey_summary = f'{hotkey.upper()} / CLR {clear_hotkey.upper()}'
        self._sidebar_hotkey_value.setText(hotkey_summary)
        self._sidebar_mode_value.setText('RULES + WHEEL')
        self._sidebar_wheel_value.setText('ON' if wheel_enabled else 'OFF')
        self._sidebar_prompt_value.setText(active_prompt)

    def _refresh_surface_header(self):
        title, meta = self._tab_copy.get(self._tabs.currentIndex(), ('Settings', ''))
        self._surface_title.setText(title)
        pending_count = len(self._pending)
        if pending_count:
            self._surface_meta.setText(f'{meta}  当前有 {pending_count} 项未保存改动。')
        else:
            self._surface_meta.setText(meta)

    # ── 通用 Tab ──────────────────────────────────────────────

    def _build_general_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(self._make_label('控制系统入口、反馈与粘贴轮盘的触发方式。', 'section_intro'))

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
        hk_lay = QVBoxLayout(hk_box)
        self._tune_group_layout(hk_lay)
        self._chk_hotkey = QCheckBox('启用')
        self._chk_hotkey.setChecked(self._config.get('general.custom_hotkey.enabled', True))
        self._chk_hotkey.stateChanged.connect(
            lambda v: self._apply_immediate_update('general.custom_hotkey.enabled', bool(v)))
        self._btn_record = QPushButton(
            self._config.get('general.custom_hotkey.keys', HOTKEY_EXAMPLE))
        self._btn_record.clicked.connect(self._on_record_hotkey)
        hk_lay.addWidget(self._chk_hotkey)
        hk_row = QHBoxLayout()
        hk_row.setSpacing(10)
        hk_row.addWidget(QLabel('热键'))
        hk_row.addWidget(self._btn_record, 1)
        hk_lay.addLayout(hk_row)
        layout.addWidget(hk_box)

        clear_hk_box = QGroupBox('一键删除当前剪贴板')
        clear_hk_lay = QVBoxLayout(clear_hk_box)
        self._tune_group_layout(clear_hk_lay)
        self._chk_clear_hotkey = QCheckBox('启用')
        self._chk_clear_hotkey.setChecked(
            self._config.get('general.clear_clipboard_hotkey.enabled', False)
        )
        self._chk_clear_hotkey.stateChanged.connect(
            lambda v: self._apply_immediate_update('general.clear_clipboard_hotkey.enabled', bool(v))
        )
        self._btn_record_clear_hotkey = QPushButton(
            self._config.get('general.clear_clipboard_hotkey.keys', 'cmd+alt+k')
        )
        self._btn_record_clear_hotkey.clicked.connect(self._on_record_clear_hotkey)
        clear_hk_lay.addWidget(self._chk_clear_hotkey)
        clear_hk_row = QHBoxLayout()
        clear_hk_row.setSpacing(10)
        clear_hk_row.addWidget(QLabel('热键'))
        clear_hk_row.addWidget(self._btn_record_clear_hotkey, 1)
        clear_hk_lay.addLayout(clear_hk_row)
        clear_hk_lay.addWidget(QLabel('触发后立即清空当前剪贴板内容，不经过转盘。'))
        layout.addWidget(clear_hk_box)

        # 双击复制快捷键
        dbl_box = QGroupBox(f'双击 {COPY_SHORTCUT}')
        dbl_lay = QVBoxLayout(dbl_box)
        self._tune_group_layout(dbl_lay)
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

        wheel_box = QGroupBox('粘贴轮盘')
        wheel_lay = QVBoxLayout(wheel_box)
        self._tune_group_layout(wheel_lay)
        self._chk_wheel = QCheckBox('拦截 Cmd+V 并显示轮盘')
        self._chk_wheel.setChecked(self._config.get('wheel.enabled', True))
        self._chk_wheel.stateChanged.connect(
            lambda v: self._mark('wheel.enabled', bool(v)))
        wheel_lay.addWidget(self._chk_wheel)
        wheel_lay.addWidget(QLabel('轮盘包含：历史记录、直接粘贴、规则清洗、大模型处理'))
        layout.addWidget(wheel_box)

        history_box = QGroupBox('历史记录管理')
        history_lay = QVBoxLayout(history_box)
        self._tune_group_layout(history_lay)
        history_lay.addWidget(QLabel('图片条目显示缩略图，文本条目显示摘要。可手动删除或清空全部历史。'))
        self._history_list = QListWidget()
        self._history_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._history_list.setIconSize(QPixmap(56, 56).size())
        history_lay.addWidget(self._history_list)
        history_btn_row = QHBoxLayout()
        self._btn_refresh_history = QPushButton('刷新历史')
        self._btn_refresh_history.clicked.connect(self._refresh_history_list)
        history_btn_row.addWidget(self._btn_refresh_history)
        self._btn_delete_history = QPushButton('删除所选')
        self._btn_delete_history.setObjectName('btn_reset')
        self._btn_delete_history.clicked.connect(self._on_delete_selected_history)
        history_btn_row.addWidget(self._btn_delete_history)
        self._btn_clear_history = QPushButton('清空全部')
        self._btn_clear_history.setObjectName('btn_reset')
        self._btn_clear_history.clicked.connect(self._on_clear_all_history)
        history_btn_row.addWidget(self._btn_clear_history)
        history_lay.addLayout(history_btn_row)
        layout.addWidget(history_box)
        self._refresh_history_list()

        layout.addStretch()
        btn_reset_general = QPushButton('恢复通用默认设置')
        btn_reset_general.setObjectName('btn_reset')
        btn_reset_general.clicked.connect(self._confirm_and_reset_general)
        layout.addWidget(btn_reset_general)
        return w

    def _confirm_and_reset_general(self):
        reply = self._ask_confirmation(
            '确认恢复默认',
            f'确定要将通用设置（热键、双击 {COPY_SHORTCUT}、Toast 通知等）恢复为默认值吗？\n此操作不可撤销。',
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        from neatcopy.infrastructure.config_manager import DEFAULT_CONFIG
        g = DEFAULT_CONFIG['general']
        # 写入待保存列表
        self._mark('general.toast_notification',         g['toast_notification'])
        self._mark('general.startup_with_windows',       g['startup_with_windows'])
        self._mark('general.double_ctrl_c.enabled',      g['double_ctrl_c']['enabled'])
        self._mark('general.double_ctrl_c.interval_ms',  g['double_ctrl_c']['interval_ms'])
        self._mark('general.custom_hotkey.enabled',      g['custom_hotkey']['enabled'])
        self._mark('general.custom_hotkey.keys',         g['custom_hotkey']['keys'])
        self._mark('general.clear_clipboard_hotkey.enabled', g['clear_clipboard_hotkey']['enabled'])
        self._mark('general.clear_clipboard_hotkey.keys',    g['clear_clipboard_hotkey']['keys'])
        self._mark('wheel.enabled',                      DEFAULT_CONFIG['wheel']['enabled'])
        # 刷新 UI（阻断信号，避免触发二次 _mark）
        for widget, value in [
            (self._chk_toast,    g['toast_notification']),
            (self._chk_startup,  g['startup_with_windows']),
            (self._chk_hotkey,   g['custom_hotkey']['enabled']),
            (self._chk_clear_hotkey, g['clear_clipboard_hotkey']['enabled']),
            (self._chk_dbl,      g['double_ctrl_c']['enabled']),
            (self._chk_wheel,    DEFAULT_CONFIG['wheel']['enabled']),
        ]:
            widget.blockSignals(True)
            widget.setChecked(value)
            widget.blockSignals(False)
        self._btn_record.blockSignals(True)
        self._btn_record.setText(g['custom_hotkey']['keys'])
        self._btn_record.blockSignals(False)
        self._btn_record_clear_hotkey.blockSignals(True)
        self._btn_record_clear_hotkey.setText(g['clear_clipboard_hotkey']['keys'])
        self._btn_record_clear_hotkey.blockSignals(False)
        self._sld_interval.blockSignals(True)
        self._sld_interval.setValue(g['double_ctrl_c']['interval_ms'])
        self._sld_interval.blockSignals(False)
        self._lbl_interval.setText(f'间隔阈值：{g["double_ctrl_c"]["interval_ms"]} ms')
        self._do_save()

    def _on_interval_changed(self, value: int):
        self._lbl_interval.setText(f'间隔阈值：{value} ms')
        self._mark('general.double_ctrl_c.interval_ms', value)

    def _refresh_history_list(self):
        if not hasattr(self, '_history_list'):
            return
        self._history_list.clear()
        for index, entry in enumerate(self._history_service.list_entries()):
            item = QListWidgetItem(entry.label)
            item.setData(Qt.ItemDataRole.UserRole, index)
            if entry.payload.is_image and entry.payload.image_png_base64:
                icon = self._icon_from_history_image(entry.payload.image_png_base64)
                if icon is not None:
                    item.setIcon(icon)
                item.setText(f'图片  {entry.payload.image_width or "?"}x{entry.payload.image_height or "?"}')
            self._history_list.addItem(item)

    def _icon_from_history_image(self, image_png_base64: str) -> QIcon | None:
        try:
            raw = base64.b64decode(image_png_base64)
        except Exception:
            return None
        image = QImage()
        if not image.loadFromData(raw, 'PNG'):
            return None
        pixmap = QPixmap.fromImage(image).scaled(
            56,
            56,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        return QIcon(pixmap)

    def _on_delete_selected_history(self):
        item = self._history_list.currentItem() if hasattr(self, '_history_list') else None
        if not item:
            self._show_message('information', '未选择记录', '请先选中一条历史记录。')
            return
        index = item.data(Qt.ItemDataRole.UserRole)
        entries = self._history_service.list_entries()
        if index is None or index >= len(entries):
            self._refresh_history_list()
            return
        history_items = self._config.get('history.items', [])
        if not isinstance(history_items, list):
            history_items = []
        history_items = list(history_items)
        if index < len(history_items):
            history_items.pop(index)
        else:
            self._history_service.delete_item(int(index))
            self._refresh_history_list()
            return
        self._mark('history.items', history_items)
        self._do_save()
        self._refresh_history_list()

    def _on_clear_all_history(self):
        reply = self._ask_confirmation('确认清空', '确定清空全部历史记录吗？此操作不可撤销。')
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._mark('history.items', [])
        self._do_save()
        self._refresh_history_list()

    # ── 规则 Tab ──────────────────────────────────────────────

    def _build_rules_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(self._make_label('独立热键默认走规则清洗；轮盘中可单独选择规则清洗或大模型处理。', 'section_intro'))

        rules_box = QGroupBox('规则开关')
        rules_lay = QVBoxLayout(rules_box)
        self._tune_group_layout(rules_lay)
        rules_lay.setSpacing(6)
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
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(self._make_label('连接模型服务，维护 Prompt 模板，并控制轮盘中的智能入口。', 'section_intro'))

        self._chk_llm = QCheckBox('显示大模型配置与轮盘入口')
        self._chk_llm.setChecked(self._config.get('llm.enabled', False))
        self._chk_llm.stateChanged.connect(
            lambda value: self._mark('llm.enabled', bool(value))
        )
        layout.addWidget(self._chk_llm)

        api_box = QGroupBox('API 配置')
        api_lay = QVBoxLayout(api_box)
        self._tune_group_layout(api_lay)

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
        btn_show.setFixedWidth(68)
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

        timeout_row = QHBoxLayout()
        timeout_row.addWidget(QLabel('请求超时：'))
        self._spn_timeout = QSpinBox()
        self._spn_timeout.setRange(5, 300)
        self._spn_timeout.setSuffix(' s')
        self._spn_timeout.setValue(int(self._config.get('llm.timeout', 30)))
        self._spn_timeout.valueChanged.connect(
            lambda value: self._mark('llm.timeout', int(value))
        )
        timeout_row.addWidget(self._spn_timeout)
        timeout_row.addStretch()
        api_lay.addLayout(timeout_row)
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
        self._tune_group_layout(prompt_lay)
        self._prompt_list = QListWidget()
        self._prompt_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._prompt_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._prompt_list.customContextMenuRequested.connect(self._show_prompt_menu)
        self._prompt_list.itemDoubleClicked.connect(
            lambda item: self._edit_prompt_by_id(item.data(Qt.ItemDataRole.UserRole)))
        self._refresh_prompts()
        prompt_lay.addWidget(self._prompt_list)

        prompt_btn_row = QHBoxLayout()
        self._btn_use_prompt = QPushButton('确认切换')
        self._btn_use_prompt.clicked.connect(self._on_use_selected_prompt)
        prompt_btn_row.addWidget(self._btn_use_prompt)
        self._btn_delete_prompt = QPushButton('删除模板')
        self._btn_delete_prompt.setObjectName('btn_reset')
        self._btn_delete_prompt.clicked.connect(self._on_delete_selected_prompt)
        prompt_btn_row.addWidget(self._btn_delete_prompt)
        btn_add = QPushButton('+ 新增模板')
        btn_add.clicked.connect(self._on_add_prompt)
        prompt_btn_row.addWidget(btn_add)
        prompt_lay.addLayout(prompt_btn_row)
        layout.addWidget(prompt_box)

        layout.addStretch()
        return w

    def _confirm_and_reset_llm_api(self):
        reply = self._ask_confirmation(
            '确认恢复默认',
            '确定要将 API 配置（Base URL、Model ID、API Key、Temperature、超时）恢复为默认值吗？\n'
            'API Key 将被清空，Prompt 模板不受影响。此操作不可撤销。',
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        from neatcopy.infrastructure.config_manager import DEFAULT_CONFIG
        llm = DEFAULT_CONFIG['llm']
        self._mark('llm.base_url',    llm['base_url'])
        self._mark('llm.model_id',    llm['model_id'])
        self._mark('llm.api_key',     llm['api_key'])
        self._mark('llm.enabled',     llm['enabled'])
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
        self._chk_llm.blockSignals(True)
        self._chk_llm.setChecked(llm['enabled'])
        self._chk_llm.blockSignals(False)
        self._le_apikey.blockSignals(True)
        self._le_apikey.setText(llm['api_key'])
        self._le_apikey.blockSignals(False)
        self._sld_temp.blockSignals(True)
        self._sld_temp.setValue(int(llm['temperature'] * 10))
        self._sld_temp.blockSignals(False)
        self._lbl_temp.setText(f'Temperature：{llm["temperature"]:.1f}')
        self._spn_timeout.blockSignals(True)
        self._spn_timeout.setValue(int(llm['timeout']))
        self._spn_timeout.blockSignals(False)
        self._do_save()

    def _on_temp_changed(self, value: int):
        temp = value / 10.0
        self._lbl_temp.setText(f'Temperature：{temp:.1f}')
        self._mark('llm.temperature', temp)

    def _refresh_prompts(self):
        current_id = self._prompt_list.currentItem().data(Qt.ItemDataRole.UserRole) if self._prompt_list.currentItem() else None
        self._prompt_list.clear()
        prompts = self._config.get('llm.prompts') or []
        active_id = self._config.get('llm.active_prompt_id', 'default')
        for p in prompts:
            tag = '[默认] ' if p['id'] == active_id else ''
            lock = ' 🔒' if p.get('readonly') else ''
            wheel = ' ◉轮盘' if p.get('visible_in_wheel', True) else ''
            item = QListWidgetItem(f"{tag}{p['name']}{lock}{wheel}")
            item.setData(Qt.ItemDataRole.UserRole, p['id'])
            self._prompt_list.addItem(item)
            if current_id and p['id'] == current_id:
                self._prompt_list.setCurrentItem(item)
            elif not current_id and p['id'] == active_id:
                self._prompt_list.setCurrentItem(item)

    def _on_use_selected_prompt(self):
        item = self._prompt_list.currentItem()
        if not item:
            self._show_message('information', '未选择模板', '请先选中一个 Prompt 模板。')
            return
        pid = item.data(Qt.ItemDataRole.UserRole)
        self._set_active_prompt(pid)

    def _on_delete_selected_prompt(self):
        item = self._prompt_list.currentItem()
        if not item:
            self._show_message('information', '未选择模板', '请先选中一个 Prompt 模板。')
            return
        pid = item.data(Qt.ItemDataRole.UserRole)
        prompts = self._config.get('llm.prompts') or []
        prompt = next((p for p in prompts if p['id'] == pid), None)
        if not prompt:
            return
        if prompt.get('readonly', False):
            self._show_message('information', '只读模板', '默认模板不能删除。')
            return
        reply = self._ask_confirmation('确认删除', f'确定删除模板“{prompt["name"]}”吗？此操作不可撤销。')
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._delete_prompt_by_id(pid)

    def _set_active_prompt(self, pid: str):
        if not pid:
            return
        if self._config.get('llm.active_prompt_id', 'default') == pid:
            self._show_message('information', '无需切换', '当前已经在使用这个 Prompt 模板。')
            return
        self._mark('llm.active_prompt_id', pid)
        self._do_save()
        self._refresh_prompts()
        self._show_message('information', '切换成功', '已切换到所选 Prompt 模板。')

    def _delete_prompt_by_id(self, pid: str):
        prompts = self._config.get('llm.prompts') or []
        new_prompts = [p for p in prompts if p['id'] != pid]
        self._mark('llm.prompts', new_prompts)
        if self._config.get('llm.active_prompt_id', 'default') == pid:
            fallback_id = new_prompts[0]['id'] if new_prompts else 'default'
            self._mark('llm.active_prompt_id', fallback_id)
        self._do_save()
        self._refresh_prompts()

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
        act_toggle_wheel = menu.addAction(
            '从轮盘隐藏' if prompt.get('visible_in_wheel', True) else '加入轮盘'
        )
        act_edit = menu.addAction('编辑')
        act_edit.setEnabled(not prompt.get('readonly', False))
        act_del = menu.addAction('删除')
        act_del.setEnabled(not prompt.get('readonly', False))
        action = menu.exec(self._prompt_list.mapToGlobal(pos))

        if action == act_default:
            self._set_active_prompt(pid)
        elif action == act_toggle_wheel:
            self._toggle_prompt_visible_in_wheel(pid)
        elif action == act_edit:
            self._edit_prompt_by_id(pid)
        elif action == act_del:
            self._delete_prompt_by_id(pid)

    def _toggle_prompt_visible_in_wheel(self, pid: str):
        prompts = list(self._config.get('llm.prompts') or [])
        changed = False
        for prompt in prompts:
            if prompt.get('id') == pid:
                prompt['visible_in_wheel'] = not prompt.get('visible_in_wheel', True)
                changed = True
                break
        if not changed:
            return
        self._mark('llm.prompts', prompts)
        self._do_save()
        self._refresh_prompts()

    def _edit_prompt_by_id(self, pid: str):
        prompts = list(self._config.get('llm.prompts') or [])
        prompt = next((p for p in prompts if p['id'] == pid), None)
        if not prompt:
            return
        if prompt.get('readonly', False):
            self._show_message('information', '只读模板', '默认模板为只读，不能直接编辑。')
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
            'visible_in_wheel': True,
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
                    content = LLMClient().test_connection_sync(self._cfg)
                    self.success.emit(content)
                except Exception as e:
                    self.error.emit(classify_error(e, timeout=self._cfg.get('timeout', 30)))

        worker = _TestWorker(llm_cfg)
        worker.success.connect(lambda r: (
            self._show_message('information', '连接成功', f'模型回复：{r[:200]}'),
            self._btn_test.setEnabled(True),
            self._btn_test.setText('测试连接'),
        ))
        worker.error.connect(lambda e: (
            self._show_message('critical', '连接失败', e),
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
        self._status_lbl.setText(f'待保存 {len(self._pending)} 项改动')
        self._refresh_surface_header()

    def _do_save(self):
        updates = dict(self._pending)
        self._pending.clear()
        self._settings_service.apply_updates(updates)
        self._refresh_hero_summary()
        self._refresh_history_list()
        self._status_lbl.setText('已保存 ✓')
        self._refresh_surface_header()
        QTimer.singleShot(1500, lambda: self._status_lbl.setText(''))

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_history_list()

    def _on_record_hotkey(self):
        current = self._btn_record.text().strip() or HOTKEY_EXAMPLE
        self._record_hotkey_for_button(
            current=current,
            button=self._btn_record,
            config_key='general.custom_hotkey.keys',
            apply_now=True,
        )

    def _on_record_clear_hotkey(self):
        current = self._btn_record_clear_hotkey.text().strip() or 'cmd+alt+k'
        self._record_hotkey_for_button(
            current=current,
            button=self._btn_record_clear_hotkey,
            config_key='general.clear_clipboard_hotkey.keys',
            apply_now=True,
        )

    def _record_hotkey_for_button(self, current: str, button: QPushButton, config_key: str, apply_now: bool = False):
        dlg = _HotkeyCaptureDialog(current, self)
        if not dlg.exec():
            return
        combo = dlg.captured.strip().lower()
        if not combo:
            return
        _, vk = _parse_hotkey(combo)
        if not vk:
            self._show_message('warning', '热键无效', f'无法识别这个热键组合，请使用 {HOTKEY_EXAMPLE} 这类格式。')
            return
        button.setText(combo)
        if apply_now:
            self._apply_immediate_update(config_key, combo)
        else:
            self._mark(config_key, combo)

    def _create_message_box(self, icon, title: str, text: str) -> QMessageBox:
        box = QMessageBox(self)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStyleSheet("""
            QMessageBox {
                background:#071015;
                color:#E8FFF6;
                font-family:"Avenir Next","PingFang SC","Segoe UI",sans-serif;
                font-size:13px;
            }
            QMessageBox QLabel {
                color:#E8FFF6;
                min-width:300px;
            }
            QMessageBox QPushButton {
                min-width:88px;
                padding:7px 12px;
                background:rgba(8,16,21,0.96);
                border:2px solid rgba(38,255,213,0.40);
                color:#E1FFF7;
                font-weight:700;
            }
            QMessageBox QPushButton:hover {
                background:rgba(19,32,40,0.98);
                border-color:#26FFD5;
            }
        """)
        return box

    def _ask_confirmation(self, title: str, text: str):
        box = self._create_message_box(QMessageBox.Icon.Question, title, text)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        yes_button = box.button(QMessageBox.StandardButton.Yes)
        no_button = box.button(QMessageBox.StandardButton.No)
        if yes_button is not None:
            yes_button.setText('确认')
        if no_button is not None:
            no_button.setText('取消')
        return QMessageBox.StandardButton(box.exec())

    def _show_message(self, level: str, title: str, text: str):
        icon_map = {
            'information': QMessageBox.Icon.Information,
            'warning': QMessageBox.Icon.Warning,
            'critical': QMessageBox.Icon.Critical,
        }
        box = self._create_message_box(icon_map.get(level, QMessageBox.Icon.Information), title, text)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        ok_button = box.button(QMessageBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setText('确定')
        return box.exec()

    def _apply_immediate_update(self, key: str, value):
        self._mark(key, value)
        self._do_save()
