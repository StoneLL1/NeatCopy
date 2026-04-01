from __future__ import annotations

import math
import base64
from dataclasses import dataclass

from PyQt6.QtCore import QPoint, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QImage,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PyQt6.QtWidgets import QApplication, QWidget


@dataclass(frozen=True)
class RadialMenuItem:
    id: str
    label: str
    enabled: bool = True
    thumbnail_png_base64: str | None = None


class RadialMenuWindow(QWidget):
    action_selected = pyqtSignal(str)
    dismissed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[RadialMenuItem] = []
        self._title = ''
        self._subtitle = 'SELECT VECTOR'
        self._center = QPointF(0, 0)
        self._hovered_index: int | None = None
        self._pixmap_cache: dict[str, QPixmap] = {}
        self._outer_radius = 170.0
        self._inner_radius = 66.0
        self._base_color = QColor(7, 15, 22, 236)
        self._hover_color = QColor(28, 53, 64, 245)
        self._disabled_color = QColor(12, 20, 28, 170)
        self._stroke_color = QColor(38, 255, 213, 60)
        self._highlight_color = QColor(245, 255, 99, 210)
        self._text_color = QColor(233, 255, 247)
        self._muted_text = QColor(111, 176, 161)
        self._index_text = QColor(38, 255, 213)

        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)

    def show_menu(self, items: list[RadialMenuItem], title: str, anchor_pos: QPoint):
        self._items = items
        self._title = title
        self._pixmap_cache = {}
        screen = QApplication.screenAt(anchor_pos) or QApplication.primaryScreen()
        if not screen:
            return
        self.setGeometry(screen.geometry())
        local_x = anchor_pos.x() - self.geometry().x()
        local_y = anchor_pos.y() - self.geometry().y()
        padding = self._outer_radius + 24
        clamped_x = min(max(local_x, padding), self.width() - padding)
        clamped_y = min(max(local_y, padding), self.height() - padding)
        self._center = QPointF(clamped_x, clamped_y)
        self._hovered_index = None
        self.show()
        self.raise_()
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(2, 5, 7, 112))
        if not self._items:
            return

        sector_angle = 360.0 / len(self._items)
        start_angle = -90.0
        outer_rect = QRectF(
            self._center.x() - self._outer_radius,
            self._center.y() - self._outer_radius,
            self._outer_radius * 2,
            self._outer_radius * 2,
        )
        self._paint_backdrop(painter)

        for index, item in enumerate(self._items):
            angle = start_angle + index * sector_angle
            path = self._build_sector_path(angle, sector_angle)
            fill = self._disabled_color if not item.enabled else self._base_color
            if index == self._hovered_index and item.enabled:
                fill = self._hover_color
            painter.fillPath(path, fill)
            pen = QPen(
                self._highlight_color if index == self._hovered_index and item.enabled else self._stroke_color,
                3 if index == self._hovered_index and item.enabled else 1.5,
            )
            painter.setPen(pen)
            painter.drawPath(path)
            self._draw_label(painter, angle, sector_angle, index, item)

        center_rect = QRectF(
            self._center.x() - self._inner_radius,
            self._center.y() - self._inner_radius,
            self._inner_radius * 2,
            self._inner_radius * 2,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        center_gradient = QRadialGradient(self._center, self._inner_radius * 1.15)
        center_gradient.setColorAt(0.0, QColor(15, 24, 31, 252))
        center_gradient.setColorAt(0.62, QColor(8, 14, 19, 248))
        center_gradient.setColorAt(1.0, QColor(4, 8, 12, 250))
        painter.setBrush(center_gradient)
        painter.drawEllipse(center_rect)
        painter.setPen(QColor(38, 255, 213, 220))
        font = QFont('Menlo', 8)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.4)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(
            QRectF(center_rect.left(), center_rect.top() + 14, center_rect.width(), 14),
            Qt.AlignmentFlag.AlignHCenter,
            self._title.upper(),
        )
        title_font = QFont('Menlo', 13)
        title_font.setWeight(QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.setPen(QColor(245, 255, 99))
        focus_text = self._subtitle if self._hovered_index is None else self._items[self._hovered_index].label
        hovered_item = self._items[self._hovered_index] if self._hovered_index is not None else None
        if hovered_item and hovered_item.thumbnail_png_base64:
            self._draw_center_preview(painter, center_rect, hovered_item)
        else:
            painter.drawText(
                QRectF(center_rect.left() + 12, center_rect.top() + 32, center_rect.width() - 24, 34),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                focus_text,
            )
        hint_font = QFont('Menlo', 8)
        painter.setFont(hint_font)
        painter.setPen(QColor(143, 189, 177))
        hint_text = 'ESC TO CLOSE' if self._hovered_index is None else 'CLICK TO SELECT'
        painter.drawText(
            QRectF(center_rect.left() + 8, center_rect.bottom() - 24, center_rect.width() - 16, 14),
            Qt.AlignmentFlag.AlignHCenter,
            hint_text,
        )

    def mouseMoveEvent(self, event: QMouseEvent):
        hovered = self._index_at_position(event.position())
        if hovered != self._hovered_index:
            self._hovered_index = hovered
            self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() != Qt.MouseButton.LeftButton:
            self.close()
            self.dismissed.emit()
            return
        index = self._index_at_position(event.position())
        if index is None:
            self.close()
            self.dismissed.emit()
            return
        item = self._items[index]
        if not item.enabled:
            return
        self.action_selected.emit(item.id)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            self.dismissed.emit()
            return
        super().keyPressEvent(event)

    def _paint_backdrop(self, painter: QPainter):
        glow = QRadialGradient(self._center, self._outer_radius * 1.32)
        glow.setColorAt(0.0, QColor(38, 255, 213, 14))
        glow.setColorAt(0.55, QColor(38, 255, 213, 8))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(
            QRectF(
                self._center.x() - self._outer_radius * 1.32,
                self._center.y() - self._outer_radius * 1.32,
                self._outer_radius * 2.64,
                self._outer_radius * 2.64,
            )
        )
        outer_ring = QRectF(
            self._center.x() - self._outer_radius - 6,
            self._center.y() - self._outer_radius - 6,
            (self._outer_radius + 6) * 2,
            (self._outer_radius + 6) * 2,
        )
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(38, 255, 213, 34), 1.2))
        painter.drawEllipse(outer_ring)
        painter.setPen(QPen(QColor(245, 255, 99, 20), 1.0))
        painter.drawEllipse(
            QRectF(
                self._center.x() - self._inner_radius - 8,
                self._center.y() - self._inner_radius - 8,
                (self._inner_radius + 8) * 2,
                (self._inner_radius + 8) * 2,
            )
        )

    def _build_sector_path(self, start_angle: float, sector_angle: float) -> QPainterPath:
        path = QPainterPath()
        path.moveTo(self._center)
        outer_rect = QRectF(
            self._center.x() - self._outer_radius,
            self._center.y() - self._outer_radius,
            self._outer_radius * 2,
            self._outer_radius * 2,
        )
        path.arcTo(outer_rect, start_angle, sector_angle)
        path.closeSubpath()
        inner_path = QPainterPath()
        inner_path.addEllipse(self._center, self._inner_radius, self._inner_radius)
        return path.subtracted(inner_path)

    def _draw_label(
        self,
        painter: QPainter,
        start_angle: float,
        sector_angle: float,
        index: int,
        item: RadialMenuItem,
    ):
        mid_angle = math.radians(-(start_angle + sector_angle / 2))
        radius = self._outer_radius * 0.67
        pos = QPointF(
            self._center.x() + math.cos(mid_angle) * radius,
            self._center.y() + math.sin(mid_angle) * radius,
        )
        label_rect = QRectF(pos.x() - 52, pos.y() - 22, 104, 44)
        index_rect = QRectF(label_rect.left(), label_rect.top() - 18, label_rect.width(), 14)
        font = QFont('Menlo', 11 if len(self._items) <= 4 else 9)
        font.setWeight(QFont.Weight.Bold)
        index_font = QFont('Menlo', 7)
        index_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)
        index_font.setWeight(QFont.Weight.Bold)
        painter.setFont(index_font)
        painter.setPen(self._highlight_color if index == self._hovered_index and item.enabled else self._index_text)
        painter.drawText(
            index_rect,
            Qt.AlignmentFlag.AlignCenter,
            f'{index + 1:02d}',
        )
        if item.thumbnail_png_base64:
            self._draw_thumbnail(painter, label_rect, item, index)
            return
        painter.setFont(font)
        painter.setPen(self._highlight_color if index == self._hovered_index and item.enabled else (self._text_color if item.enabled else self._muted_text))
        painter.drawText(
            label_rect,
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            item.label,
        )

    def _draw_thumbnail(self, painter: QPainter, label_rect: QRectF, item: RadialMenuItem, index: int):
        pixmap = self._pixmap_for_item(item)
        thumb_rect = QRectF(label_rect.left() + 14, label_rect.top() - 2, label_rect.width() - 28, 34)
        caption_rect = QRectF(label_rect.left() + 4, label_rect.bottom() - 8, label_rect.width() - 8, 16)
        painter.setPen(QPen(
            self._highlight_color if index == self._hovered_index and item.enabled else self._stroke_color,
            1.3,
        ))
        painter.setBrush(QColor(5, 11, 15, 228))
        painter.drawRoundedRect(thumb_rect, 4, 4)
        if pixmap is not None and not pixmap.isNull():
            scaled = pixmap.scaled(
                int(thumb_rect.width() - 4),
                int(thumb_rect.height() - 4),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            draw_rect = QRectF(
                thumb_rect.center().x() - scaled.width() / 2,
                thumb_rect.center().y() - scaled.height() / 2,
                scaled.width(),
                scaled.height(),
            )
            painter.drawPixmap(draw_rect.toRect(), scaled)
        painter.setFont(QFont('Menlo', 7))
        painter.setPen(self._highlight_color if index == self._hovered_index and item.enabled else self._text_color)
        painter.drawText(caption_rect, Qt.AlignmentFlag.AlignCenter, '图片')

    def _draw_center_preview(self, painter: QPainter, center_rect: QRectF, item: RadialMenuItem):
        pixmap = self._pixmap_for_item(item)
        if pixmap is None or pixmap.isNull():
            painter.drawText(
                QRectF(center_rect.left() + 12, center_rect.top() + 32, center_rect.width() - 24, 34),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                item.label,
            )
            return
        preview_rect = QRectF(center_rect.left() + 10, center_rect.top() + 30, center_rect.width() - 20, 34)
        painter.setPen(QPen(QColor(38, 255, 213, 120), 1.2))
        painter.setBrush(QColor(7, 12, 16, 216))
        painter.drawRoundedRect(preview_rect, 5, 5)
        scaled = pixmap.scaled(
            int(preview_rect.width() - 6),
            int(preview_rect.height() - 6),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        draw_rect = QRectF(
            preview_rect.center().x() - scaled.width() / 2,
            preview_rect.center().y() - scaled.height() / 2,
            scaled.width(),
            scaled.height(),
        )
        painter.drawPixmap(draw_rect.toRect(), scaled)

    def _pixmap_for_item(self, item: RadialMenuItem) -> QPixmap | None:
        if not item.thumbnail_png_base64:
            return None
        cached = self._pixmap_cache.get(item.id)
        if cached is not None:
            return cached
        raw = base64.b64decode(item.thumbnail_png_base64)
        image = QImage()
        if not image.loadFromData(raw, 'PNG'):
            return None
        pixmap = QPixmap.fromImage(image)
        self._pixmap_cache[item.id] = pixmap
        return pixmap

    def _index_at_position(self, pos: QPointF) -> int | None:
        if not self._items:
            return None
        dx = pos.x() - self._center.x()
        dy = pos.y() - self._center.y()
        distance = math.hypot(dx, dy)
        if distance < self._inner_radius or distance > self._outer_radius:
            return None
        angle = (math.degrees(math.atan2(-dy, dx)) + 90.0) % 360.0
        sector_angle = 360.0 / len(self._items)
        return int(angle // sector_angle)
