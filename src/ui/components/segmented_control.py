"""Shadcn-style segmented control (pill-style selector) widget."""

from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
    QButtonGroup,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor

from ui.styles import ColorPalette, FONT_FAMILY, FONT_SIZE_XS, RADIUS_SM


class SegmentedControl(QWidget):
    """A horizontal row of mutually-exclusive buttons with a Shadcn segmented look.

    The selected button gets an elevated bg + fg text; unselected buttons are
    transparent with muted text.  An optional ``full_width`` mode stretches all
    buttons to fill the available width equally.

    Signals:
        selectionChanged(int): emitted when the selected index changes.
    """

    selectionChanged = pyqtSignal(int)

    def __init__(
        self,
        options: list[str],
        parent=None,
        full_width: bool = False,
    ):
        super().__init__(parent)
        self._options = options
        self._full_width = full_width
        self._theme = "light"
        self._current_index = 0
        self._shadows: list[QGraphicsDropShadowEffect] = []

        self.setObjectName("segmentedContainer")

        # Layout -----------------------------------------------------------
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(3, 3, 3, 3)
        self._layout.setSpacing(2)

        # Button group (exclusive) -----------------------------------------
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)

        for i, label in enumerate(options):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setObjectName("segButton")
            if full_width:
                btn.setMinimumWidth(0)

            # Each button gets its own shadow effect (toggled on/off)
            shadow = QGraphicsDropShadowEffect(btn)
            shadow.setBlurRadius(4)
            shadow.setOffset(0, 1)
            shadow.setEnabled(False)
            btn.setGraphicsEffect(shadow)
            self._shadows.append(shadow)

            self._layout.addWidget(btn, stretch=1 if full_width else 0)
            self._button_group.addButton(btn, id=i)

        # Select first option by default
        if options:
            self._button_group.button(0).setChecked(True)

        # Connections
        self._button_group.idClicked.connect(self._on_button_clicked)

        # Apply initial theme
        self.set_theme(self._theme)

    # ── Public API ───────────────────────────────────────────────────────

    def setCurrentIndex(self, index: int):
        """Programmatically select the button at *index*."""
        if 0 <= index < len(self._options) and index != self._current_index:
            btn = self._button_group.button(index)
            if btn:
                btn.setChecked(True)
            self._current_index = index
            self._apply_button_styles()
            self.selectionChanged.emit(index)

    def currentIndex(self) -> int:
        """Return the index of the currently selected option."""
        return self._current_index

    def set_theme(self, theme: str):
        """Re-apply styles for *theme* ('light' or 'dark')."""
        self._theme = theme
        c = ColorPalette.get(theme)

        # Update all shadow colours
        shadow_color = QColor(c["border"])
        for shadow in self._shadows:
            shadow.setColor(shadow_color)

        # Container
        self.setStyleSheet(f"""
            QWidget#segmentedContainer {{
                background: {c['surface_alt']};
                border-radius: {RADIUS_SM};
            }}
        """)

        self._apply_button_styles()

    # ── Internals ────────────────────────────────────────────────────────

    def _apply_button_styles(self):
        """Refresh per-button QSS based on current selection and theme."""
        c = ColorPalette.get(self._theme)

        checked_id = self._button_group.checkedId()

        for i in range(len(self._options)):
            btn = self._button_group.button(i)
            if btn is None:
                continue

            is_selected = i == checked_id

            # Toggle shadow visibility
            self._shadows[i].setEnabled(is_selected)

            if is_selected:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {c['bg']};
                        color: {c['fg']};
                        border: none;
                        border-radius: 4px;
                        padding: 4px 12px;
                        font-family: {FONT_FAMILY};
                        font-size: {FONT_SIZE_XS};
                        font-weight: 500;
                    }}
                    QPushButton:hover {{
                        background: {c['bg']};
                        color: {c['fg']};
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent;
                        color: {c['muted']};
                        border: none;
                        border-radius: 4px;
                        padding: 4px 12px;
                        font-family: {FONT_FAMILY};
                        font-size: {FONT_SIZE_XS};
                        font-weight: 500;
                    }}
                    QPushButton:hover {{
                        color: {c['fg']};
                    }}
                """)

    def _on_button_clicked(self, index: int):
        """Handle exclusive button group click."""
        self._current_index = index
        self._apply_button_styles()
        self.selectionChanged.emit(index)
