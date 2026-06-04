from __future__ import annotations

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QStyle, QStyledItemDelegate

from ui.history_list_model import ModeRole, SummaryRole, TimeTextRole
from ui.styles import ColorPalette


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
        rect = option.rect.adjusted(4, 4, -4, -4)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        if selected:
            bg = QColor(c["accent_soft"])
        elif hovered:
            bg = QColor(c["fg_soft"])
        else:
            bg = QColor(c.get("card_bg", c["bg"]))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 6, 6)

        time_text = index.data(TimeTextRole) or "--:--"
        mode = index.data(ModeRole) or "rules"
        summary = index.data(SummaryRole) or ""
        mode_text = "规则" if mode == "rules" else self._llm_text(index)

        content = rect.adjusted(12, 10, -12, -10)
        top_rect = QRect(content.left(), content.top(), content.width(), 22)
        summary_rect = QRect(content.left(), content.top() + 32, content.width(), 22)

        time_font = QFont("Cascadia Code")
        time_font.setPointSize(8)
        painter.setFont(time_font)
        painter.setPen(QColor(c["muted"]))
        painter.drawText(top_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, time_text)

        badge_font = QFont()
        badge_font.setPointSize(8)
        badge_font.setBold(True)
        painter.setFont(badge_font)
        metrics = painter.fontMetrics()
        badge_w = metrics.horizontalAdvance(mode_text) + 16
        badge_rect = QRect(top_rect.right() - badge_w, top_rect.top() + 1, badge_w, 20)
        badge_bg = QColor(c["accent_soft"] if mode == "rules" else c["success_soft"])
        badge_fg = QColor(c["accent"] if mode == "rules" else c["success"])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(badge_bg)
        painter.drawRoundedRect(badge_rect, 10, 10)
        painter.setPen(badge_fg)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, mode_text)

        summary_font = QFont()
        summary_font.setPointSize(9)
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
