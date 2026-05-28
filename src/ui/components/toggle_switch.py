"""Shadcn-style toggle switch widget for NeatCopy UI."""

from PyQt6.QtCore import (
    QPropertyAnimation,
    QSize,
    QEasingCurve,
    Qt,
    pyqtProperty,
    pyqtSignal,
    QRectF,
)
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush
from PyQt6.QtWidgets import QWidget

from ui.styles import ColorPalette


class ToggleSwitch(QWidget):
    """Custom toggle switch with smooth animation, inspired by Shadcn/Switch.

    Track: 36x20px pill shape.
    Thumb: 16x16px circle that slides between off (x=2) and on (x=18).
    """

    toggled = pyqtSignal(bool)

    # Animation duration in milliseconds
    _ANIM_DURATION = 150
    # Geometry constants
    _TRACK_W = 36
    _TRACK_H = 20
    _PAINT_PAD = 1
    _THUMB_SIZE = 16
    _THUMB_MARGIN = 2  # (TRACK_H - THUMB_SIZE) / 2
    _THUMB_X_OFF = 2
    _THUMB_X_ON = 18  # _THUMB_X_OFF + (TRACK_W - THUMB_SIZE - 2 * _THUMB_MARGIN) = 2 + 16 = 18

    def __init__(self, parent=None, checked=False):
        super().__init__(parent)
        self._checked = checked
        self._theme = 'light'
        self._colors = ColorPalette.get(self._theme)

        # Thumb position (animated). Stored as float for smooth interpolation.
        self._thumb_x = float(
            self._THUMB_X_ON if self._checked else self._THUMB_X_OFF
        )

        self.setFixedSize(self.sizeHint())
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_animation()

    # ── Public API ──────────────────────────────────────────────────────

    @pyqtProperty(bool)
    def checked(self) -> bool:  # type: ignore[override]
        return self._checked

    @checked.setter
    def checked(self, value: bool) -> None:
        if self._checked == value:
            return
        self._checked = value
        self._animate_to(value)
        self.toggled.emit(value)

    def set_checked_silent(self, value: bool) -> None:
        """Set checked state without emitting the toggled signal."""
        if self._checked == value:
            return
        self._checked = value
        self._animate_to(value)

    def set_theme(self, theme: str) -> None:
        """Update color cache for the given theme and repaint."""
        self._theme = theme
        self._colors = ColorPalette.get(theme)
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802 – Qt naming convention
        return QSize(self._TRACK_W + self._PAINT_PAD * 2,
                     self._TRACK_H + self._PAINT_PAD * 2)

    # ── Painting ────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track_color = QColor(
            self._colors['accent'] if self._checked else self._colors['border_strong']
        )
        thumb_color = QColor(self._colors['bg'])

        # Track (pill shape)
        pad = self._PAINT_PAD
        track_rect = QRectF(pad, pad, self._TRACK_W, self._TRACK_H)
        painter.setPen(QPen(track_color, 0))
        painter.setBrush(QBrush(track_color))
        painter.drawRoundedRect(track_rect, self._TRACK_H / 2, self._TRACK_H / 2)

        # Thumb shadow (soft dark ellipse behind the thumb)
        shadow_rect = QRectF(
            pad + self._thumb_x,
            pad + self._THUMB_MARGIN + 0.5,
            self._THUMB_SIZE,
            self._THUMB_SIZE,
        )
        shadow_color = QColor(0, 0, 0, 38)  # ~0.15 alpha
        painter.setPen(QPen(shadow_color, 0))
        painter.setBrush(QBrush(shadow_color))
        painter.drawEllipse(shadow_rect)

        # Thumb (white circle)
        thumb_rect = QRectF(
            pad + self._thumb_x,
            pad + self._THUMB_MARGIN,
            self._THUMB_SIZE,
            self._THUMB_SIZE,
        )
        painter.setPen(QPen(thumb_color, 0))
        painter.setBrush(QBrush(thumb_color))
        painter.drawEllipse(thumb_rect)

        painter.end()

    # ── Interaction ─────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.checked = not self._checked
        else:
            super().mousePressEvent(event)

    # ── Animation internals ─────────────────────────────────────────────

    def _setup_animation(self) -> None:
        self._anim = QPropertyAnimation(self, b"thumb_x_prop")
        self._anim.setDuration(self._ANIM_DURATION)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _animate_to(self, on: bool) -> None:
        target = float(self._THUMB_X_ON if on else self._THUMB_X_OFF)
        self._anim.stop()
        self._anim.setStartValue(self._thumb_x)
        self._anim.setEndValue(target)
        self._anim.start()

    # Qt property used by QPropertyAnimation to drive the thumb position.
    @pyqtProperty(float)
    def thumb_x_prop(self) -> float:
        return self._thumb_x

    @thumb_x_prop.setter
    def thumb_x_prop(self, value: float) -> None:
        self._thumb_x = value
        self.update()
