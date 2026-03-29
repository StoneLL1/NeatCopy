"""Notion-style sidebar navigation widget."""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem
from PyQt6.QtCore import pyqtSignal, Qt

from ui.styles import get_sidebar_stylesheet


class SidebarWidget(QWidget):
    """Left sidebar navigation with Notion-style visual indicators."""

    currentChanged = pyqtSignal(int)  # emits page index

    def __init__(self, items: list[str], theme: str = 'light', parent=None):
        super().__init__(parent)
        self._theme = theme
        self._items = items
        self.setFixedWidth(150)  # 缩窄侧边栏
        self.setObjectName('sidebar')

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(0)

        # App name label - 字体由 QSS 控制
        app_name = QLabel('NeatCopy')
        app_name.setObjectName('sidebarAppName')
        app_name.setContentsMargins(16, 0, 0, 16)
        layout.addWidget(app_name)

        # Navigation list
        self._list = QListWidget()
        self._list.setObjectName('sidebarNav')
        self._list.setCurrentRow(0)
        for item_text in items:
            item = QListWidgetItem(item_text)
            # 字体样式由 QSS 控制，这里只设置高度
            item.setSizeHint(item.sizeHint().expandedTo(
                item.sizeHint().__class__(0, 36)))
            self._list.addItem(item)
        self._list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._list)

        layout.addStretch()
        self._apply_theme()

    def _on_row_changed(self, row: int):
        self.currentChanged.emit(row)

    def set_theme(self, theme: str):
        self._theme = theme
        self._apply_theme()

    def _apply_theme(self):
        self.setStyleSheet(get_sidebar_stylesheet(self._theme))

    def setCurrentIndex(self, index: int):
        self._list.setCurrentRow(index)


# Alias for convenient import
Sidebar = SidebarWidget
