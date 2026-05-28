"""历史记录窗口组件：标准窗口 + 自定义标题栏，双栏布局，支持搜索、复制、删除。"""
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QListWidget, QListWidgetItem,
    QLineEdit, QMessageBox, QSizePolicy, QSplitter, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QCursor, QIcon, QPixmap, QPainter, QColor, QPen, QAction

from ui.styles import (
    get_history_stylesheet, ColorPalette,
    FONT_MONO, FONT_SIZE_XS, FONT_SIZE_SM, FONT_FAMILY, RADIUS_SM
)


class HistoryWindow(QWidget):
    """历史记录窗口，标准窗口 + 自定义标题栏，Shadcn 风格双栏布局。"""

    copy_to_clipboard = pyqtSignal(str)  # 请求写入剪贴板

    def __init__(self, config, history_manager):
        super().__init__()
        self._config = config
        self._history = history_manager
        self._current_entry_id = None
        self._theme = config.get('ui.theme', 'light')
        self._drag_pos = None
        self._resize_timer = None
        self._search_timer = QTimer()  # 搜索防抖定时器
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._do_search)

        self._setup_window_properties()
        self._create_ui()
        self._apply_theme(self._theme)

    # ================================================================
    #  窗口属性
    # ================================================================

    def _setup_window_properties(self):
        """设置窗口属性：标准窗口框、尺寸。"""
        self.setWindowTitle("历史记录 - NeatCopy")

        self.resize(
            self._config.get('history.window_width', 720),
            self._config.get('history.window_height', 520)
        )
        self.setMinimumSize(400, 300)

    @staticmethod
    def _create_search_icon() -> QIcon:
        """Create a 14x14 magnifying glass icon programmatically."""
        pm = QPixmap(14, 14)
        pm.fill(QColor(0, 0, 0, 0))
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(0, 0, 0, 120), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(2, 2, 7, 7)
        p.drawLine(9, 9, 13, 13)
        p.end()
        return QIcon(pm)

    # ================================================================
    #  主题样式
    # ================================================================

    def _apply_theme(self, theme: str):
        """应用指定主题的样式到所有组件。"""
        self._theme = theme
        c = ColorPalette.get(theme)
        self.setStyleSheet(get_history_stylesheet(theme))

        # 工具栏标题
        self.toolbar_title.setStyleSheet(f"""
            QLabel {{
                color: {c['fg']};
                font-size: {FONT_SIZE_SM};
                font-weight: 600;
                padding: 0 4px;
                background: transparent;
            }}
        """)

        # 关闭按钮
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {c['muted']};
                border: none;
                border-radius: {RADIUS_SM};
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {c['danger_soft']};
                color: {c['danger']};
            }}
        """)

        # 工具栏标题
        self.toolbar_title.setStyleSheet(f"""
            QLabel {{
                color: {c['fg']};
                font-size: {FONT_SIZE_SM};
                font-weight: 600;
                background: transparent;
            }}
        """)

        # 搜索框（额外覆盖 objectName 已在 stylesheet 中）
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {c['border']};
                border-radius: {RADIUS_SM};
                padding: 8px 12px 8px 24px;
                background: {c['surface_alt']};
                color: {c['fg']};
                font-family: {FONT_FAMILY};
            }}
            QLineEdit:focus {{
                border: 2px solid {c['accent']};
                padding: 7px 11px 7px 23px;
                background: {c['surface_alt']};
            }}
        """)

        # 清空按钮（ghost 样式 btn-sm）
        self.clear_all_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {c['border']};
                border-radius: {RADIUS_SM};
                padding: 4px 12px;
                min-height: 24px;
                color: {c['muted']};
                font-size: {FONT_SIZE_XS};
            }}
            QPushButton:hover {{
                background: {c['fg_soft']};
                border-color: {c['border_strong']};
                color: {c['fg']};
            }}
        """)

        # 元信息行
        self.time_label.setStyleSheet(f"""
            QLabel {{
                color: {c['muted']};
                font-family: {FONT_MONO};
                font-size: 11px;
                background: transparent;
            }}
        """)

        # 模式徽章
        self.mode_badge.setStyleSheet(f"""
            QLabel {{
                background: {c['accent_soft']};
                color: {c['accent']};
                border-radius: 9999px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: bold;
            }}
        """)

        # 区标签
        section_style = f"""
            QLabel {{
                color: {c['muted']};
                font-size: {FONT_SIZE_XS};
                font-weight: 600;
                padding: 2px 0;
                background: transparent;
            }}
        """
        self.original_section.setStyleSheet(section_style)
        self.result_section.setStyleSheet(section_style)

        # 文本编辑区
        edit_style = f"""
            QTextEdit {{
                background: {c['surface_alt']};
                border: 1px solid {c['border']};
                border-radius: {RADIUS_SM};
                padding: 12px;
                color: {c['fg']};
                font-size: {FONT_SIZE_SM};
            }}
            QTextEdit:focus {{
                border: 2px solid {c['accent']};
                padding: 11px;
            }}
        """
        self.original_edit.setStyleSheet(edit_style)
        self.result_edit.setStyleSheet(edit_style)

        # 复制按钮（btn-sm ghost）
        ghost_btn = f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {c['border']};
                border-radius: {RADIUS_SM};
                padding: 4px 12px;
                min-height: 24px;
                color: {c['fg']};
                font-size: {FONT_SIZE_XS};
            }}
            QPushButton:hover {{
                background: {c['fg_soft']};
                border-color: {c['border_strong']};
            }}
        """
        self.copy_original_btn.setStyleSheet(ghost_btn)
        self.copy_result_btn.setStyleSheet(ghost_btn)

        # 删除按钮（danger btn-sm, no border per design btn-danger）
        self.delete_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: {RADIUS_SM};
                padding: 4px 12px;
                min-height: 24px;
                color: {c['danger']};
                font-size: {FONT_SIZE_XS};
            }}
            QPushButton:hover {{
                background: {c['danger_soft']};
            }}
        """)

        # 空状态
        self.empty_icon.setStyleSheet(f"""
            QLabel {{
                color: {c['muted']};
                font-size: 32px;
                background: transparent;
            }}
        """)
        self.empty_label.setStyleSheet(f"""
            QLabel {{
                color: {c['muted']};
                font-size: {FONT_SIZE_XS};
                background: transparent;
            }}
        """)

        # 详情空状态
        self.detail_empty_icon.setStyleSheet(f"""
            QLabel {{
                color: {c['border_strong']};
                font-size: 36px;
                background: transparent;
            }}
        """)
        self.detail_empty_text.setStyleSheet(f"""
            QLabel {{
                color: {c['muted']};
                font-size: {FONT_SIZE_XS};
                background: transparent;
            }}
        """)

        # 操作按钮分隔线
        if hasattr(self, 'action_separator'):
            self.action_separator.setStyleSheet(
                f"background: {c['border']}; max-height: 1px; border: none;")

        # 重新刷新列表以更新自定义 item widget 颜色
        self._refresh_list()

    def set_theme(self, theme: str):
        """公共方法：动态切换主题。"""
        self._apply_theme(theme)

    # ================================================================
    #  UI 构建
    # ================================================================

    def _create_ui(self):
        """构建完整的 UI 布局：标题栏 + 工具栏 + 双栏主体。"""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # === 工具栏（含标题和关闭按钮）===
        toolbar = QWidget()
        toolbar.setObjectName("toolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(16, 12, 16, 12)
        toolbar_layout.setSpacing(12)

        self.toolbar_title = QLabel("历史记录")
        toolbar_layout.addWidget(self.toolbar_title)
        toolbar_layout.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setObjectName("search_input")
        self.search_input.setPlaceholderText("搜索原文或结果...")
        self.search_input.setFixedHeight(32)
        self.search_input.setMaximumWidth(280)
        self.search_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.search_input.textChanged.connect(self._on_search_changed)

        # Search icon (14x14 magnifying glass drawn programmatically)
        search_icon = self._create_search_icon()
        search_action = QAction(search_icon, '', self.search_input)
        self.search_input.addAction(search_action, QLineEdit.ActionPosition.LeadingPosition)

        toolbar_layout.addWidget(self.search_input)

        self.clear_all_btn = QPushButton("清空")
        self.clear_all_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        toolbar_layout.addWidget(self.clear_all_btn)
        self.clear_all_btn.clicked.connect(self._on_clear_all)

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.close_btn.clicked.connect(self.close)
        toolbar_layout.addWidget(self.close_btn)

        root.addWidget(toolbar)

        # === 双栏主体 ===
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左栏：列表
        self.list_widget = QListWidget()
        self.list_widget.setMinimumWidth(200)
        self.list_widget.setMaximumWidth(320)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        splitter.addWidget(self.list_widget)

        # 右栏：详情
        detail_container = QWidget()
        detail_layout = QVBoxLayout(detail_container)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(0)

        # 详情内容（有选中条目时显示）
        self.detail_content = QWidget()
        detail_inner = QVBoxLayout(self.detail_content)
        detail_inner.setContentsMargins(16, 16, 16, 16)
        detail_inner.setSpacing(12)

        # 元信息行: 时间 + 模式徽章
        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)
        self.time_label = QLabel("--")
        meta_row.addWidget(self.time_label)
        self.mode_badge = QLabel("--")
        meta_row.addWidget(self.mode_badge)
        meta_row.addStretch()
        detail_inner.addLayout(meta_row)

        # 原文区
        self.original_section = QLabel("原文")
        self.original_edit = QTextEdit()
        self.original_edit.setReadOnly(True)
        self.original_edit.setPlaceholderText("选择条目查看")
        self.original_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        detail_inner.addWidget(self.original_section)
        detail_inner.addWidget(self.original_edit, stretch=1)

        # 结果区
        self.result_section = QLabel("结果")
        self.result_edit = QTextEdit()
        self.result_edit.setReadOnly(True)
        self.result_edit.setPlaceholderText("选择条目查看")
        self.result_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        detail_inner.addWidget(self.result_section)
        detail_inner.addWidget(self.result_edit, stretch=1)

        # 操作按钮行
        self.action_separator = QFrame()
        self.action_separator.setFrameShape(QFrame.Shape.HLine)
        self.action_separator.setStyleSheet(f"background: {ColorPalette.get(self._theme)['border']}; max-height: 1px; border: none;")
        detail_inner.addWidget(self.action_separator)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 8, 0, 0)
        action_row.setSpacing(8)
        self.copy_original_btn = QPushButton("复制原文")
        self.copy_original_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.copy_original_btn.clicked.connect(self._on_copy_original)
        self.copy_result_btn = QPushButton("复制结果")
        self.copy_result_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.copy_result_btn.clicked.connect(self._on_copy_result)
        self.delete_btn = QPushButton("删除")
        self.delete_btn.setObjectName("btn_delete")
        self.delete_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.delete_btn.clicked.connect(self._on_delete_entry)
        action_row.addWidget(self.copy_original_btn)
        action_row.addWidget(self.copy_result_btn)
        action_row.addStretch()
        action_row.addWidget(self.delete_btn)
        detail_inner.addLayout(action_row)

        # 详情空状态（无选中条目时显示）
        self.detail_empty = QWidget()
        empty_layout = QVBoxLayout(self.detail_empty)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(8)
        self.detail_empty_icon = QLabel("H")
        self.detail_empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_empty_icon.setStyleSheet("font-size: 36px; font-weight: bold;")
        self.detail_empty_text = QLabel("选择一条记录查看详情")
        self.detail_empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.detail_empty_icon)
        empty_layout.addWidget(self.detail_empty_text)

        # 使用 stacked 方式切换：detail_empty 默认显示
        detail_layout.addWidget(self.detail_empty)
        detail_layout.addWidget(self.detail_content)
        self.detail_content.hide()

        splitter.addWidget(detail_container)
        splitter.setSizes([240, 480])
        root.addWidget(splitter, stretch=1)

        # 全局空状态（无任何记录时显示，覆盖整个窗口）
        self.global_empty = QWidget()
        self.global_empty.setObjectName("panel")
        global_empty_layout = QVBoxLayout(self.global_empty)
        global_empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        global_empty_layout.setSpacing(8)
        self.empty_icon = QLabel("H")
        self.empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_icon.setStyleSheet("font-size: 32px; font-weight: bold;")
        self.empty_label = QLabel("暂无记录")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        global_empty_layout.addWidget(self.empty_icon)
        global_empty_layout.addWidget(self.empty_label)

        self.global_empty.hide()
        root.addWidget(self.global_empty)

        self._refresh_list()

    # ================================================================
    #  列表项 Widget 工厂
    # ================================================================

    def _create_list_item_widget(self, entry):
        """为列表项创建两行格式的自定义 widget（优化版本）。"""
        c = ColorPalette.get(self._theme)
        widget = QWidget()
        widget.setObjectName("list_item")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        # 格式化时间
        timestamp = entry.get('timestamp', '')
        try:
            dt = datetime.fromisoformat(timestamp)
            time_str = dt.strftime('%H:%M')
        except Exception:
            time_str = '--:--'

        # 模式
        mode = entry.get('mode', 'rules')
        if mode == 'rules':
            mode_str = '规则'
        else:
            prompt_name = entry.get('prompt_name', '')
            mode_str = f'LLM: {prompt_name}' if prompt_name else 'LLM'

        # 摘要（仅显示第一行）
        original = entry.get('original', '')
        first_line = original.split('\n')[0] if original else ''
        summary = first_line[:30] if len(first_line) > 30 else first_line
        if len(first_line) > 30:
            summary += '...'

        # 顶行：时间 + 模式徽章
        top = QHBoxLayout()
        top.setSpacing(4)
        time_label = QLabel(time_str)
        time_label.setObjectName("time_label")
        top.addWidget(time_label)
        top.addStretch()

        mode_badge = QLabel(mode_str)
        mode_badge.setObjectName("mode_badge_rules" if mode == 'rules' else "mode_badge_llm")
        mode_badge.setFixedHeight(20)
        top.addWidget(mode_badge)
        layout.addLayout(top)

        # 底行：摘要
        summary_label = QLabel(summary)
        summary_label.setObjectName("summary_label")
        summary_label.setWordWrap(False)
        summary_label.setFixedHeight(18)
        layout.addWidget(summary_label)

        return widget

    # ================================================================
    #  数据操作
    # ================================================================

    def _refresh_list(self, keyword: str = ''):
        """刷新列表显示（优化版本：批量添加）。"""
        self.list_widget.clear()

        if keyword:
            entries = self._history.search(keyword)
        else:
            entries = self._history.get_all()

        if not entries:
            self.global_empty.show()
            self.list_widget.hide()
            self._clear_detail()
            return

        self.global_empty.hide()
        self.list_widget.show()

        # 批量添加：先禁用更新，添加完后再启用
        self.list_widget.setUpdatesEnabled(False)
        try:
            for entry in entries:
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, entry.get('id'))
                item.setSizeHint(self._calc_item_size(entry))
                self.list_widget.addItem(item)
                self.list_widget.setItemWidget(item, self._create_list_item_widget(entry))
        finally:
            self.list_widget.setUpdatesEnabled(True)

    def _calc_item_size(self, entry):
        """计算列表项的推荐大小（两行布局固定高度）。"""
        from PyQt6.QtCore import QSize
        return QSize(0, 62)

    def _on_item_clicked(self, item: QListWidgetItem):
        """点击列表项，显示详情。"""
        entry_id = item.data(Qt.ItemDataRole.UserRole)
        entry = self._history.get_by_id(entry_id)

        if not entry:
            self._clear_detail()
            return

        self._current_entry_id = entry_id
        c = ColorPalette.get(self._theme)

        # 显示详情内容，隐藏空状态
        self.detail_empty.hide()
        self.detail_content.show()

        # 显示时间
        timestamp = entry.get('timestamp', '')
        try:
            dt = datetime.fromisoformat(timestamp)
            time_str = dt.strftime('%m-%d %H:%M')
        except Exception:
            time_str = timestamp
        self.time_label.setText(time_str)

        # 显示模式
        mode = entry.get('mode', 'rules')
        if mode == 'rules':
            self.mode_badge.setText("规则")
            self.mode_badge.setStyleSheet(f"""
                QLabel {{
                    background: {c['surface_alt']};
                    color: {c['muted']};
                    border-radius: 9999px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: bold;
                }}
            """)
        else:
            prompt_name = entry.get('prompt_name', '')
            self.mode_badge.setText(f"LLM: {prompt_name}" if prompt_name else "LLM")
            self.mode_badge.setStyleSheet(f"""
                QLabel {{
                    background: {c['accent_soft']};
                    color: {c['accent']};
                    border-radius: 9999px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: bold;
                }}
            """)

        # 显示原文
        self.original_edit.setPlainText(entry.get('original', ''))

        # 显示结果
        self.result_edit.setPlainText(entry.get('result', ''))

    def _clear_detail(self):
        """清空详情面板。"""
        self._current_entry_id = None
        self.detail_content.hide()
        self.detail_empty.show()
        self.time_label.setText("--")
        self.mode_badge.setText("--")
        self.original_edit.clear()
        self.result_edit.clear()

    def _on_search_changed(self, keyword: str):
        """搜索框内容变化时，启动防抖定时器。"""
        self._search_timer.stop()
        self._search_timer.start(300)  # 300ms 防抖延迟

    def _do_search(self):
        """执行实际的搜索操作。"""
        keyword = self.search_input.text()
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
            # 显示前刷新主题
            new_theme = self._config.get('ui.theme', 'light')
            if new_theme != self._theme:
                self._apply_theme(new_theme)
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
    #  拖动（仅标题栏） + 尺寸保存
    # ================================================================

    def mousePressEvent(self, event):
        """鼠标按下时，仅在标题栏区域记录拖动位置。"""
        if event.button() == Qt.MouseButton.LeftButton:
            titlebar = self.findChild(QWidget, 'titlebar')
            if titlebar and titlebar.geometry().contains(event.pos()):
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标移动时拖动窗口。"""
        if hasattr(self, '_drag_pos') and self._drag_pos is not None:
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
