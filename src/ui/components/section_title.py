"""Notion-style section title component with optional separator."""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt

from ui.styles import ColorPalette


class SectionTitle(QWidget):
    """A section header with title label and optional separator line.

    Notion-style visual: "── 标题 ──" followed by a subtle separator line.
    """

    def __init__(self, title: str, theme: str = 'light', with_separator: bool = True, parent=None):
        super().__init__(parent)
        self._theme = theme

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(4)

        # Title label
        title_label = QLabel(f'── {title} ──')
        title_label.setObjectName('sectionTitle')
        layout.addWidget(title_label)

        # Optional separator line
        if with_separator:
            separator = QFrame()
            separator.setObjectName('sectionSeparator')
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setFixedHeight(1)
            layout.addWidget(separator)

    def set_theme(self, theme: str):
        self._theme = theme
        # Style is applied via parent stylesheet