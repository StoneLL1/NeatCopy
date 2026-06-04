from __future__ import annotations

import re

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QStyle, QStyledItemDelegate

from ui.history_list_model import ModeRole, SummaryRole, TimeTextRole
from ui.styles import ColorPalette


def _qc(color_str: str) -> QColor:
    """Convert a ColorPalette string (including rgba with float alpha) to QColor."""
    m = re.match(r'rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)', color_str)
    if m:
        return QColor(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(float(m.group(4)) * 255))
    return QColor(color_str)


class HistoryItemDelegate(QStyledItemDelegate):
    ROW_HEIGHT = 76

    def __init__(self, theme: str = "light", parent=None):
        super().__init__(parent)
        self._theme = theme

    def set_theme(self, theme: str) -> None:
        self._theme = theme

    def sizeHint(self, option, index):  # noqa: N802
        return QSize(0, self.ROW_HEIGHT)

    def paint(self, painter: QPainter, option, index):  # noqa: N802
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        c = ColorPalette.get(self._theme)
        rect = option.rect
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        # Background: flat fill matching original QListWidget::item QSS
        if selected:
            bg = _qc(c["selected_bg"])
        elif hovered:
            bg = _qc(c["fg_soft"])
        else:
            bg = Qt.GlobalColor.transparent

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRect(rect)

        # Bottom border separator
        painter.setPen(QPen(QColor(c["border"]), 1))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())

        # Content area: matching original widget margins(16, 14, 16, 14), spacing 8
        content = rect.adjusted(16, 14, -16, -14)
        top_rect = QRect(content.left(), content.top(), content.width(), 20)
        summary_rect = QRect(content.left(), content.top() + 28, content.width(), 20)

        # Time label: font-family mono, font-size 11px
        time_text = index.data(TimeTextRole) or "--:--"
        time_font = QFont("Cascadia Code")
        time_font.setPixelSize(11)
        painter.setFont(time_font)
        painter.setPen(QColor(c["muted"]))
        painter.drawText(top_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, time_text)

        # Mode badge: font-size 10px, bold, pill-shaped
        mode = index.data(ModeRole) or "rules"
        mode_text = "规则" if mode == "rules" else self._llm_text(index)

        badge_font = QFont()
        badge_font.setPixelSize(10)
        badge_font.setBold(True)
        painter.setFont(badge_font)
        metrics = painter.fontMetrics()
        badge_w = metrics.horizontalAdvance(mode_text) + 16
        badge_rect = QRect(top_rect.right() - badge_w, top_rect.top(), badge_w, 20)

        # Badge colors matching original QSS:
        # rules: bg surface_alt, fg muted
        # llm: bg selected_bg (accent_soft), fg accent
        if mode == "rules":
            badge_bg = _qc(c["surface_alt"])
            badge_fg = QColor(c["muted"])
        else:
            badge_bg = _qc(c.get("selected_bg", c["accent_soft"]))
            badge_fg = QColor(c["accent"])

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(badge_bg)
        painter.drawRoundedRect(badge_rect, 10, 10)
        painter.setPen(badge_fg)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, mode_text)

        # Summary: font-size 12px, color fg
        summary = index.data(SummaryRole) or ""
        summary_font = QFont()
        summary_font.setPixelSize(12)
        painter.setFont(summary_font)
        painter.setPen(QColor(c["fg"]))
        elided = painter.fontMetrics().elidedText(
            summary,
            Qt.TextElideMode.ElideRight,
            summary_rect.width(),
        )
        painter.drawText(summary_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)

        painter.restore()

    @staticmethod
    def _llm_text(index) -> str:
        from ui.history_list_model import PromptNameRole

        prompt_name = index.data(PromptNameRole) or ""
        return f"LLM: {prompt_name}" if prompt_name else "LLM"
