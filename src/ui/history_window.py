"""历史记录窗口组件：双栏布局，左侧列表右侧详情，支持搜索、复制、删除。"""
import ctypes
import sys

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QListWidget, QListWidgetItem,
    QLineEdit, QMessageBox, QSizePolicy, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QCursor

from ui.styles import ColorPalette


class HistoryWindow(QWidget):
    """历史记录窗口，置顶悬浮窗，双栏布局。"""

    copy_to_clipboard = pyqtSignal(str)  # 请求写入剪贴板

    def __init__(self, config, history_manager):
        super().__init__()
        self._config = config
        self._history = history_manager
        self._current_entry_id = None
        self._theme = config.get('ui.theme', 'light')
        self._drag_pos = None
        self._resize_timer = None

        self._setup_window_properties()
        self._create_ui()
        self._apply_theme(self._theme)
        self._apply_acrylic_effect()

    # ================================================================
    #  窗口属性
    # ================================================================

    def _setup_window_properties(self):
        """设置窗口属性：无边框、置顶、透明背景、尺寸。"""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.resize(
            self._config.get('history.window_width', 600),
            self._config.get('history.window_height', 400)
        )
        self.setMinimumSize(400, 300)

    # ================================================================
    #  主题样式
    # ================================================================

    def _get_theme_styles(self, theme: str) -> dict:
        """返回指定主题的样式配置字典。基于 ColorPalette 基础色。"""
        c = ColorPalette.get(theme)

        if theme == 'light':
            return {
                'panel_bg': 'rgba(255, 255, 255, 230)',
                'panel_border': 'rgba(233, 233, 233, 180)',
                'header_bg': 'rgba(247, 247, 245, 200)',
                'list_bg': 'rgba(255, 255, 255, 220)',
                'list_border': 'rgba(218, 218, 218, 120)',
                'list_item_bg': 'transparent',
                'list_item_hover': 'rgba(240, 240, 240, 200)',
                'list_item_selected': 'rgba(228, 228, 228, 240)',
                'detail_bg': 'rgba(255, 255, 255, 220)',
                'detail_section_bg': 'rgba(247, 247, 245, 180)',
                'detail_section_border': 'rgba(218, 218, 218, 100)',
                'text_primary': c['text_primary'],
                'text_secondary': c['text_secondary'],
                'text_time': '#787774',
                'text_mode': '#37352F',
                'mode_rules': '#5cb85c',
                'mode_llm': '#0275d8',
                'edit_bg': 'rgba(247, 247, 245, 200)',
                'edit_text': c['text_primary'],
                'edit_selection': 'rgba(55, 53, 47, 80)',
                'scrollbar_bg': c['scrollbar_bg'],
                'scrollbar_handle': 'rgba(160, 160, 160, 120)',
                'search_bg': 'rgba(255, 255, 255, 240)',
                'search_border': 'rgba(218, 218, 218, 120)',
                'search_focus_border': 'rgba(55, 53, 47, 150)',
                'btn_bg': 'rgba(250, 250, 250, 200)',
                'btn_border': 'rgba(218, 218, 218, 140)',
                'btn_text': c['text_primary'],
                'btn_hover_bg': 'rgba(240, 240, 240, 220)',
                'btn_hover_border': 'rgba(200, 200, 200, 160)',
                'btn_pressed_bg': 'rgba(228, 228, 228, 240)',
                'btn_danger_bg': 'rgba(255, 255, 255, 200)',
                'btn_danger_border': 'rgba(217, 83, 79, 150)',
                'btn_danger_text': '#d9534f',
                'btn_danger_hover_bg': 'rgba(217, 83, 79, 200)',
                'btn_danger_hover_text': '#FFFFFF',
                'close_text': c['text_secondary'],
                'close_hover_bg': 'rgba(0, 0, 0, 15)',
                'close_hover_text': c['text_primary'],
                'title_text': c['text_primary'],
                'empty_text': c['text_secondary'],
                'meta_text': c['text_secondary'],
            }
        else:  # dark
            return {
                'panel_bg': 'rgba(25, 25, 25, 210)',
                'panel_border': 'rgba(55, 53, 47, 140)',
                'header_bg': 'rgba(31, 31, 31, 180)',
                'list_bg': 'rgba(31, 31, 31, 200)',
                'list_border': 'rgba(61, 60, 58, 100)',
                'list_item_bg': 'transparent',
                'list_item_hover': 'rgba(47, 47, 47, 200)',
                'list_item_selected': 'rgba(55, 55, 55, 240)',
                'detail_bg': 'rgba(31, 31, 31, 200)',
                'detail_section_bg': 'rgba(36, 36, 36, 180)',
                'detail_section_border': 'rgba(61, 60, 58, 100)',
                'text_primary': c['text_primary'],
                'text_secondary': c['text_secondary'],
                'text_time': '#A0A0A0',
                'text_mode': '#F0F0F0',
                'mode_rules': '#5cb85c',
                'mode_llm': '#0275d8',
                'edit_bg': 'rgba(36, 36, 36, 200)',
                'edit_text': c['text_primary'],
                'edit_selection': 'rgba(155, 154, 151, 100)',
                'scrollbar_bg': c['scrollbar_bg'],
                'scrollbar_handle': 'rgba(74, 74, 74, 100)',
                'search_bg': 'rgba(36, 36, 36, 220)',
                'search_border': 'rgba(61, 60, 58, 100)',
                'search_focus_border': 'rgba(155, 154, 151, 150)',
                'btn_bg': 'rgba(47, 47, 47, 160)',
                'btn_border': 'rgba(61, 60, 58, 100)',
                'btn_text': c['text_primary'],
                'btn_hover_bg': 'rgba(55, 55, 55, 180)',
                'btn_hover_border': 'rgba(78, 77, 74, 140)',
                'btn_pressed_bg': 'rgba(64, 64, 64, 200)',
                'btn_danger_bg': 'rgba(47, 47, 47, 160)',
                'btn_danger_border': 'rgba(217, 83, 79, 100)',
                'btn_danger_text': '#d9534f',
                'btn_danger_hover_bg': 'rgba(217, 83, 79, 180)',
                'btn_danger_hover_text': '#FFFFFF',
                'close_text': c['text_secondary'],
                'close_hover_bg': 'rgba(255, 255, 255, 25)',
                'close_hover_text': c['text_primary'],
                'title_text': c['text_primary'],
                'empty_text': c['text_secondary'],
                'meta_text': c['text_secondary'],
            }

    def _apply_theme(self, theme: str):
        """应用指定主题的样式到所有组件。"""
        self._theme = theme
        styles = self._get_theme_styles(theme)

        # 面板容器
        self.container.setStyleSheet(f"""
            #panel {{
                background: {styles['panel_bg']};
                border: 1px solid {styles['panel_border']};
                border-radius: 10px;
            }}
        """)

        # 标题栏
        self.title_label.setStyleSheet(f"""
            #titleLabel {{
                color: {styles['title_text']};
                font-size: 14px;
                font-weight: bold;
                padding-left: 8px;
            }}
        """)

        # 搜索框
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background: {styles['search_bg']};
                border: 1px solid {styles['search_border']};
                border-radius: 6px;
                padding: 6px 10px;
                color: {styles['text_primary']};
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {styles['search_focus_border']};
            }}
            QLineEdit::placeholder {{
                color: {styles['text_secondary']};
            }}
        """)

        # 清空全部按钮
        self.clear_all_btn.setStyleSheet(f"""
            #clearAllBtn {{
                background: {styles['btn_danger_bg']};
                color: {styles['btn_danger_text']};
                border: 1px solid {styles['btn_danger_border']};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
            }}
            #clearAllBtn:hover {{
                background: {styles['btn_danger_hover_bg']};
                color: {styles['btn_danger_hover_text']};
            }}
        """)

        # 列表区域
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background: {styles['list_bg']};
                border: 1px solid {styles['list_border']};
                border-radius: 6px;
                padding: 4px;
                outline: none;
            }}
            QListWidget::item {{
                background: {styles['list_item_bg']};
                border-radius: 4px;
                padding: 8px;
                margin: 2px 0;
            }}
            QListWidget::item:hover {{
                background: {styles['list_item_hover']};
            }}
            QListWidget::item:selected {{
                background: {styles['list_item_selected']};
            }}
            QScrollBar:vertical {{
                background: {styles['scrollbar_bg']};
                width: 6px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {styles['scrollbar_handle']};
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

        # 详情区标签
        self.time_label.setStyleSheet(f"""
            QLabel {{
                color: {styles['meta_text']};
                font-size: 12px;
            }}
        """)
        self.mode_label.setStyleSheet(f"""
            QLabel {{
                color: {styles['meta_text']};
                font-size: 12px;
            }}
        """)

        # 原文区标签
        self.original_section.setStyleSheet(f"""
            QLabel {{
                color: {styles['text_secondary']};
                font-size: 11px;
                padding: 4px 8px;
                background: {styles['detail_section_bg']};
                border: 1px solid {styles['detail_section_border']};
                border-radius: 4px 4px 0 0;
            }}
        """)
        self.original_edit.setStyleSheet(f"""
            QTextEdit {{
                background: {styles['edit_bg']};
                border: 1px solid {styles['detail_section_border']};
                border-radius: 0 0 4px 4px;
                padding: 8px;
                color: {styles['edit_text']};
                font-size: 13px;
                selection-background-color: {styles['edit_selection']};
            }}
            QScrollBar:vertical {{
                background: {styles['scrollbar_bg']};
                width: 6px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {styles['scrollbar_handle']};
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

        # 结果区标签
        self.result_section.setStyleSheet(f"""
            QLabel {{
                color: {styles['text_secondary']};
                font-size: 11px;
                padding: 4px 8px;
                background: {styles['detail_section_bg']};
                border: 1px solid {styles['detail_section_border']};
                border-radius: 4px 4px 0 0;
            }}
        """)
        self.result_edit.setStyleSheet(f"""
            QTextEdit {{
                background: {styles['edit_bg']};
                border: 1px solid {styles['detail_section_border']};
                border-radius: 0 0 4px 4px;
                padding: 8px;
                color: {styles['edit_text']};
                font-size: 13px;
                selection-background-color: {styles['edit_selection']};
            }}
            QScrollBar:vertical {{
                background: {styles['scrollbar_bg']};
                width: 6px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {styles['scrollbar_handle']};
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

        # 操作按钮
        btn_style = f"""
            QPushButton {{
                background: {styles['btn_bg']};
                color: {styles['btn_text']};
                border: 1px solid {styles['btn_border']};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: {styles['btn_hover_bg']};
                border: 1px solid {styles['btn_hover_border']};
            }}
            QPushButton:pressed {{
                background: {styles['btn_pressed_bg']};
            }}
        """
        self.copy_original_btn.setStyleSheet(btn_style)
        self.copy_result_btn.setStyleSheet(btn_style)

        self.delete_btn.setStyleSheet(f"""
            QPushButton {{
                background: {styles['btn_danger_bg']};
                color: {styles['btn_danger_text']};
                border: 1px solid {styles['btn_danger_border']};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: {styles['btn_danger_hover_bg']};
                color: {styles['btn_danger_hover_text']};
            }}
        """)

        # 关闭按钮
        self.close_btn.setStyleSheet(f"""
            #closeBtn {{
                background: transparent;
                border: none;
                font-size: 12px;
                color: {styles['close_text']};
                border-radius: 4px;
            }}
            #closeBtn:hover {{
                background: {styles['close_hover_bg']};
                color: {styles['close_hover_text']};
            }}
        """)

        # 空状态提示
        self.empty_label.setStyleSheet(f"""
            QLabel {{
                color: {styles['empty_text']};
                font-size: 13px;
                padding: 20px;
            }}
        """)

    def set_theme(self, theme: str):
        """公共方法：动态切换主题。"""
        self._apply_theme(theme)

    # ================================================================
    #  UI 构建
    # ================================================================

    def _create_ui(self):
        """构建完整的 UI 布局。"""
        # --- 外层容器 ---
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- 内容容器 ---
        self.container = QWidget()
        self.container.setObjectName("panel")
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(10)

        # === 顶部栏：标题 + 关闭按钮 ===
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.title_label = QLabel("历史记录")
        self.title_label.setObjectName("titleLabel")
        top_bar.addWidget(self.title_label)
        top_bar.addStretch()

        self.close_btn = QPushButton("关闭")
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.setFixedSize(50, 26)
        self.close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.close_btn.clicked.connect(self.hide)
        top_bar.addWidget(self.close_btn)

        layout.addLayout(top_bar)

        # === 工具栏：搜索框 + 清空按钮 ===
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索历史记录...")
        self.search_input.setFixedHeight(30)
        self.search_input.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self.search_input, stretch=1)

        self.clear_all_btn = QPushButton("清空全部")
        self.clear_all_btn.setObjectName("clearAllBtn")
        self.clear_all_btn.setFixedSize(80, 30)
        self.clear_all_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.clear_all_btn.clicked.connect(self._on_clear_all)
        toolbar.addWidget(self.clear_all_btn)

        layout.addLayout(toolbar)

        # === 双栏主体：列表 + 详情 ===
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左栏：列表区
        list_container = QWidget()
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(0)

        self.list_widget = QListWidget()
        self.list_widget.setMinimumWidth(180)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        list_layout.addWidget(self.list_widget)

        splitter.addWidget(list_container)

        # 右栏：详情区
        detail_container = QWidget()
        detail_layout = QVBoxLayout(detail_container)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(8)

        # 元信息行：时间 + 模式
        meta_row = QHBoxLayout()
        meta_row.setSpacing(16)

        self.time_label = QLabel("时间：--")
        self.time_label.setWordWrap(True)
        meta_row.addWidget(self.time_label)

        self.mode_label = QLabel("模式：--")
        self.mode_label.setWordWrap(True)
        meta_row.addWidget(self.mode_label)

        meta_row.addStretch()
        detail_layout.addLayout(meta_row)

        # 原文区
        self.original_section = QLabel("原文")
        detail_layout.addWidget(self.original_section)

        self.original_edit = QTextEdit()
        self.original_edit.setReadOnly(True)
        self.original_edit.setPlaceholderText("点击左侧条目查看详情")
        self.original_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        detail_layout.addWidget(self.original_edit, stretch=1)

        # 结果区
        self.result_section = QLabel("结果")
        detail_layout.addWidget(self.result_section)

        self.result_edit = QTextEdit()
        self.result_edit.setReadOnly(True)
        self.result_edit.setPlaceholderText("点击左侧条目查看详情")
        self.result_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        detail_layout.addWidget(self.result_edit, stretch=1)

        # 操作按钮行
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.copy_original_btn = QPushButton("复制原文")
        self.copy_original_btn.setFixedHeight(28)
        self.copy_original_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.copy_original_btn.clicked.connect(self._on_copy_original)
        action_row.addWidget(self.copy_original_btn)

        self.copy_result_btn = QPushButton("复制结果")
        self.copy_result_btn.setFixedHeight(28)
        self.copy_result_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.copy_result_btn.clicked.connect(self._on_copy_result)
        action_row.addWidget(self.copy_result_btn)

        action_row.addStretch()

        self.delete_btn = QPushButton("删除")
        self.delete_btn.setFixedHeight(28)
        self.delete_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.delete_btn.clicked.connect(self._on_delete_entry)
        action_row.addWidget(self.delete_btn)

        detail_layout.addLayout(action_row)

        splitter.addWidget(detail_container)

        # 设置初始分割比例
        splitter.setSizes([200, 400])

        layout.addWidget(splitter, stretch=1)

        # === 空状态提示（初始隐藏） ===
        self.empty_label = QLabel("暂无历史记录")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()
        layout.addWidget(self.empty_label)

        outer.addWidget(self.container)

        # 初始化列表
        self._refresh_list()

    def _apply_acrylic_effect(self):
        """应用 Windows 11 Acrylic 毛玻璃效果。"""
        if sys.platform != 'win32':
            return

        version = sys.getwindowsversion()
        if version.major < 10 or (version.major == 10 and version.build < 22000):
            # Win10 降级：根据主题设置背景
            styles = self._get_theme_styles(self._theme)
            self.container.setStyleSheet(f"""
                #panel {{
                    background: {styles['panel_bg'].replace('210', '235') if self._theme == 'dark' else styles['panel_bg'].replace('230', '245')};
                    border: 1px solid {styles['panel_border']};
                    border-radius: 10px;
                }}
            """)
            return

        hwnd = int(self.winId())
        DWMWA_SYSTEMBACKDROP_TYPE = 38
        value = 3  # Acrylic

        try:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_SYSTEMBACKDROP_TYPE,
                ctypes.byref(ctypes.c_int(value)),
                4
            )
        except Exception:
            styles = self._get_theme_styles(self._theme)
            self.container.setStyleSheet(f"""
                #panel {{
                    background: {styles['panel_bg'].replace('210', '235') if self._theme == 'dark' else styles['panel_bg'].replace('230', '245')};
                    border: 1px solid {styles['panel_border']};
                    border-radius: 10px;
                }}
            """)

    # ================================================================
    #  数据操作
    # ================================================================

    def _refresh_list(self, keyword: str = ''):
        """刷新列表显示。"""
        self.list_widget.clear()

        if keyword:
            entries = self._history.search(keyword)
        else:
            entries = self._history.get_all()

        if not entries:
            self.empty_label.show()
            self.list_widget.hide()
            self._clear_detail()
            return

        self.empty_label.hide()
        self.list_widget.show()

        for entry in entries:
            # 格式化显示：HH:MM [模式] 原文摘要
            timestamp = entry.get('timestamp', '')
            try:
                # 解析 ISO 格式时间，只显示 HH:MM
                from datetime import datetime
                dt = datetime.fromisoformat(timestamp)
                time_str = dt.strftime('%H:%M')
            except Exception:
                time_str = '--:--'

            mode = entry.get('mode', 'rules')
            if mode == 'rules':
                mode_str = '[规则]'
            else:
                prompt_name = entry.get('prompt_name', '')
                mode_str = f'[LLM-{prompt_name}]' if prompt_name else '[LLM]'

            original = entry.get('original', '')
            # 取前 30 字符作为摘要
            summary = original[:30].replace('\n', ' ') if len(original) > 30 else original.replace('\n', ' ')
            if len(original) > 30:
                summary += '...'

            display_text = f"{time_str} {mode_str} {summary}"

            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, entry.get('id'))
            self.list_widget.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem):
        """点击列表项，显示详情。"""
        entry_id = item.data(Qt.ItemDataRole.UserRole)
        entry = self._history.get_by_id(entry_id)

        if not entry:
            self._clear_detail()
            return

        self._current_entry_id = entry_id

        # 显示时间
        timestamp = entry.get('timestamp', '')
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(timestamp)
            time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            time_str = timestamp
        self.time_label.setText(f"时间：{time_str}")

        # 显示模式
        mode = entry.get('mode', 'rules')
        if mode == 'rules':
            self.mode_label.setText("模式：规则清洗")
        else:
            prompt_name = entry.get('prompt_name', '')
            self.mode_label.setText(f"模式：LLM - {prompt_name}" if prompt_name else "模式：LLM")

        # 显示原文
        self.original_edit.setPlainText(entry.get('original', ''))

        # 显示结果
        self.result_edit.setPlainText(entry.get('result', ''))

    def _clear_detail(self):
        """清空详情面板。"""
        self._current_entry_id = None
        self.time_label.setText("时间：--")
        self.mode_label.setText("模式：--")
        self.original_edit.clear()
        self.result_edit.clear()

    def _on_search_changed(self, keyword: str):
        """搜索框内容变化时刷新列表。"""
        self._refresh_list(keyword)

    def _on_copy_original(self):
        """复制原文到剪贴板。"""
        if self._current_entry_id:
            entry = self._history.get_by_id(self._current_entry_id)
            if entry:
                original = entry.get('original', '')
                if original:
                    self.copy_to_clipboard.emit(original)

    def _on_copy_result(self):
        """复制结果到剪贴板。"""
        if self._current_entry_id:
            entry = self._history.get_by_id(self._current_entry_id)
            if entry:
                result = entry.get('result', '')
                if result:
                    self.copy_to_clipboard.emit(result)

    def _on_delete_entry(self):
        """删除当前选中的历史条目。"""
        if not self._current_entry_id:
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            "确定要删除这条历史记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._history.delete(self._current_entry_id)
            self._current_entry_id = None
            self._refresh_list(self.search_input.text())

    def _on_clear_all(self):
        """清空所有历史记录。"""
        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空所有历史记录吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._history.clear()
            self._current_entry_id = None
            self._refresh_list()

    # ================================================================
    #  公共方法
    # ================================================================

    def toggle_visibility(self):
        """切换窗口可见性。"""
        if self.isVisible():
            self.hide()
        else:
            # 显示前刷新主题和列表
            new_theme = self._config.get('ui.theme', 'light')
            if new_theme != self._theme:
                self._apply_theme(new_theme)
            self._refresh_list()
            self.show()
            self.activateWindow()
            self.raise_()

    def showEvent(self, event):
        """每次显示时刷新主题和列表。"""
        super().showEvent(event)
        new_theme = self._config.get('ui.theme', 'light')
        if new_theme != self._theme:
            self._apply_theme(new_theme)
        self._refresh_list()

    # ================================================================
    #  拖动 + 尺寸保存
    # ================================================================

    def mousePressEvent(self, event):
        """鼠标按下时记录拖动位置。"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 点击容器非文本区域时允许拖动
            child = self.childAt(event.position().toPoint())
            if child is self.container or child is None:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标移动时拖动窗口。"""
        if self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放时清除拖动状态。"""
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        """窗口尺寸变化时延迟保存配置。"""
        super().resizeEvent(event)
        if self._resize_timer is None:
            self._resize_timer = QTimer(self)
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(self._save_window_size)
        self._resize_timer.start(500)

    def _save_window_size(self):
        """保存窗口尺寸到配置。"""
        self._config.set('history.window_width', self.width())
        self._config.set('history.window_height', self.height())