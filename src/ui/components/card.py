"""Shadcn-style Card widget replacing QGroupBox."""

from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt

from ui.styles import ColorPalette, FONT_SIZE_SM, FONT_SIZE_XS, RADIUS_MD


class Card(QFrame):
    """Shadcn-style card container replacing QGroupBox."""

    def __init__(self, title: str = '', description: str = '', parent=None):
        super().__init__(parent)
        self.setObjectName('card')

        self._title = title
        self._description = description
        self._theme = 'light'

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)  # sp-5 = 20px
        layout.setSpacing(0)

        # Title label
        if title:
            self._title_label = QLabel(title)
            self._title_label.setObjectName('card_title')
            self._title_label.setStyleSheet(f"""
                QLabel#card_title {{
                    font-size: {FONT_SIZE_SM};
                    font-weight: 600;
                    padding-bottom: 16px;
                    background: transparent;
                }}
            """)
            layout.addWidget(self._title_label)
        else:
            self._title_label = None

        # Description label
        if description:
            self._desc_label = QLabel(description)
            self._desc_label.setObjectName('card_desc')
            self._desc_label.setWordWrap(True)
            self._desc_label.setStyleSheet(f"""
                QLabel#card_desc {{
                    font-size: {FONT_SIZE_XS};
                    margin-top: -16px;
                    padding-bottom: 12px;
                    background: transparent;
                }}
            """)
            layout.addWidget(self._desc_label)
        else:
            self._desc_label = None

        # Content area — callers add child widgets here
        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._content_layout)

        # Apply initial styling
        self.set_theme(self._theme)

    def content_layout(self) -> QVBoxLayout:
        """Return the QVBoxLayout where child widgets should be added."""
        return self._content_layout

    def set_theme(self, theme: str):
        """Re-apply styling for the given theme."""
        self._theme = theme
        c = ColorPalette.get(theme)

        self.setStyleSheet(f"""
            QFrame#card {{
                background: {c['bg']};
                border: 1px solid {c['border']};
                border-radius: {RADIUS_MD};
            }}
        """)

        if self._title_label:
            self._title_label.setStyleSheet(f"""
                QLabel#card_title {{
                    color: {c['fg']};
                    font-size: {FONT_SIZE_SM};
                    font-weight: 600;
                    padding-bottom: 16px;
                    background: transparent;
                }}
            """)

        if self._desc_label:
            self._desc_label.setStyleSheet(f"""
                QLabel#card_desc {{
                    color: {c['muted']};
                    font-size: {FONT_SIZE_XS};
                    margin-top: -16px;
                    padding-bottom: 12px;
                    background: transparent;
                }}
            """)

        self.update()
