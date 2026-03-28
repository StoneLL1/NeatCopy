# 扇形轮盘 Prompt 快捷选择器：围绕鼠标位置展开，支持鼠标点击和数字键。
import math
import ctypes
import ctypes.wintypes as wintypes
from PyQt6.QtWidgets import QWidget, QApplication, QGraphicsOpacityEffect
from PyQt6.QtCore import (
    Qt, QPoint, QPropertyAnimation, QEasingCurve, pyqtSignal, QTimer
)
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QPainterPath, QBrush, QCursor

_user32 = ctypes.windll.user32
_WH_MOUSE_LL = 14
_WM_LBUTTONDOWN = 0x0201
_WM_RBUTTONDOWN = 0x0204
_MOUSEHOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


class _MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ('pt', wintypes.POINT),
        ('mouseData', wintypes.DWORD),
        ('flags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong)),
    ]


class WheelWindow(QWidget):
    prompt_selected = pyqtSignal(str)   # 发射选中的 prompt id
    wheel_cancelled = pyqtSignal()      # ESC / 点击外部取消

    _WINDOW_SIZE = 240
    _OUTER_R = 100
    _INNER_R = 34
    _BG_COLOR = QColor(40, 40, 40, 230)
    _HOVER_COLOR = QColor(80, 80, 80, 230)
    _BORDER_COLOR = QColor(100, 100, 100, 150)
    _TEXT_COLOR = QColor(255, 255, 255)
    _NUM_COLOR = QColor(180, 180, 180)
    _CENTER_LABEL_COLOR = QColor(160, 160, 160)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._prompts: list[dict] = []
        self._hovered: int = -1
        self._selected_callback = None
        self._last_prompt_id: str | None = None   # 记住上次，供高亮默认用
        self._mouse_hook_handle = None
        self._mouse_hook_proc = None
        self._wheel_open = False

        # 无边框置顶普通窗口。不使用 Popup（会在 WM_ACTIVATEAPP 时被 Qt 强制关闭）
        # 也不使用 Tool（阻止 Windows 赋予焦点）。点击轮盘外部通过 WH_MOUSE_LL 检测。
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self._WINDOW_SIZE, self._WINDOW_SIZE)
        self.setMouseTracking(True)

        # 字体（避免在 paintEvent 中每帧重复创建）
        self._font_name = QFont('Microsoft YaHei UI', 9)
        self._font_num = QFont('Microsoft YaHei UI', 8)

        # 透明度动画
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._anim = QPropertyAnimation(self._opacity_effect, b'opacity', self)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # ── 公开接口 ──────────────────────────────────────────────

    def show_at(self, pos: QPoint, prompts: list[dict], callback,
                last_prompt_id: str | None = None):
        """在屏幕坐标 pos 附近显示轮盘。callback(prompt_id) 在选中后调用。"""
        if not prompts:
            return
        self._prompts = prompts[:5]   # 最多5个
        self._selected_callback = callback
        self._last_prompt_id = last_prompt_id
        self._hovered = -1

        # 把轮盘中心放在鼠标位置，确保不超出屏幕
        screen = QApplication.screenAt(pos)
        if screen is None:
            screen = QApplication.primaryScreen()
        screen_rect = screen.availableGeometry()
        half = self._WINDOW_SIZE // 2
        x = max(screen_rect.left(), min(pos.x() - half, screen_rect.right() - self._WINDOW_SIZE))
        y = max(screen_rect.top(), min(pos.y() - half, screen_rect.bottom() - self._WINDOW_SIZE))
        self.move(x, y)

        self._opacity_effect.setOpacity(0.0)
        self._wheel_open = True
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

        # 展开动画：先断开上一次 _close_wheel 留下的 finished→hide 连接，否则 open 动画
        # 结束时也会触发 hide()，导致轮盘每次第二次弹出后 150ms 内自动消失。
        self._anim.stop()
        if self._anim.receivers(self._anim.finished) > 0:
            self._anim.finished.disconnect()
        self._anim.setDuration(150)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

        # 安装全局鼠标钩子，检测轮盘外点击
        self._install_mouse_hook()

    # ── 内部逻辑 ─────────────────────────────────────────────

    def _install_mouse_hook(self):
        """安装 WH_MOUSE_LL 低级鼠标钩子，点击轮盘外部时关闭。"""
        self._uninstall_mouse_hook()  # 确保不重复安装

        def _hook(nCode, wParam, lParam):
            if nCode >= 0 and wParam in (_WM_LBUTTONDOWN, _WM_RBUTTONDOWN):
                if self._wheel_open:
                    click_pos = QCursor.pos()
                    if not self.geometry().contains(click_pos):
                        # 点击在轮盘外部，延到下一帧关闭（不在钩子内直接操作 Qt）
                        QTimer.singleShot(0, lambda: self._close_wheel(cancelled=True))
            return _user32.CallNextHookEx(None, nCode, wParam, ctypes.c_long(lParam))

        self._mouse_hook_proc = _MOUSEHOOKPROC(_hook)
        self._mouse_hook_handle = _user32.SetWindowsHookExW(
            _WH_MOUSE_LL, self._mouse_hook_proc, None, 0)

    def _uninstall_mouse_hook(self):
        if self._mouse_hook_handle:
            _user32.UnhookWindowsHookEx(self._mouse_hook_handle)
            self._mouse_hook_handle = None
            self._mouse_hook_proc = None

    def _close_wheel(self, cancelled: bool = True):
        """动画关闭轮盘。"""
        if not self._wheel_open:
            return   # 防止重入
        self._wheel_open = False
        self._uninstall_mouse_hook()

        self._anim.stop()
        if self._anim.receivers(self._anim.finished) > 0:
            self._anim.finished.disconnect()
        self._anim.setDuration(100)
        self._anim.setStartValue(self._opacity_effect.opacity())
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self.hide)
        self._anim.start()
        if cancelled:
            self.wheel_cancelled.emit()

    def _select(self, index: int):
        if 0 <= index < len(self._prompts):
            pid = self._prompts[index]['id']
            self._close_wheel(cancelled=False)
            if self._selected_callback:
                # 延迟一帧，让动画先启动再回调
                QTimer.singleShot(0, lambda: self._selected_callback(pid))
            self.prompt_selected.emit(pid)

    def _index_at(self, x: int, y: int) -> int:
        """计算 (x, y) 相对窗口中心落在哪个扇区，不在环内返回 -1。"""
        cx = cy = self._WINDOW_SIZE // 2
        dx, dy = x - cx, y - cy
        r = math.hypot(dx, dy)
        if r < self._INNER_R or r > self._OUTER_R:
            return -1
        n = len(self._prompts)
        if n == 0:
            return -1
        # 角度从正上方（-90°）开始，顺时针
        angle = math.degrees(math.atan2(dy, dx)) + 90
        if angle < 0:
            angle += 360
        sector_size = 360.0 / n
        idx = int(angle / sector_size) % n
        return idx

    # ── 事件 ──────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        n = len(self._prompts)
        if n == 0:
            return

        cx = cy = self._WINDOW_SIZE // 2
        sector_deg = 360.0 / n
        start_offset = -90.0  # 从正上方开始

        for i, prompt in enumerate(self._prompts):
            start_angle = start_offset + i * sector_deg
            is_hovered = (i == self._hovered)
            is_last = (prompt['id'] == self._last_prompt_id)

            # 扇形路径（环形）
            path = QPainterPath()
            # 外弧
            outer_rect_x = cx - self._OUTER_R
            outer_rect_y = cy - self._OUTER_R
            outer_size = self._OUTER_R * 2
            path.moveTo(
                cx + self._OUTER_R * math.cos(math.radians(start_angle)),
                cy + self._OUTER_R * math.sin(math.radians(start_angle)),
            )
            path.arcTo(outer_rect_x, outer_rect_y, outer_size, outer_size,
                       -start_angle, -sector_deg)
            # 内弧（反向）
            inner_rect_x = cx - self._INNER_R
            inner_rect_y = cy - self._INNER_R
            inner_size = self._INNER_R * 2
            path.arcTo(inner_rect_x, inner_rect_y, inner_size, inner_size,
                       -(start_angle + sector_deg), sector_deg)
            path.closeSubpath()

            # 填充
            if is_hovered:
                fill = self._HOVER_COLOR
            elif is_last:
                fill = QColor(60, 60, 60, 230)
            else:
                fill = self._BG_COLOR
            painter.fillPath(path, QBrush(fill))

            # 扇区边框
            painter.setPen(QPen(self._BORDER_COLOR, 1))
            painter.drawPath(path)

            # 文字位置：沿径向中点
            mid_angle = math.radians(start_angle + sector_deg / 2)
            text_r = (self._INNER_R + self._OUTER_R) / 2
            tx = cx + text_r * math.cos(mid_angle)
            ty = cy + text_r * math.sin(mid_angle)

            # Prompt 名称
            painter.setFont(self._font_name)
            painter.setPen(QPen(self._TEXT_COLOR))
            name = prompt.get('name', '')
            if len(name) > 5:
                name = name[:4] + '…'
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(name)
            th = fm.height()
            painter.drawText(int(tx - tw / 2), int(ty + th / 4), name)

            # 数字标签
            num_r = self._INNER_R + 14
            nx = cx + num_r * math.cos(mid_angle)
            ny = cy + num_r * math.sin(mid_angle)
            painter.setFont(self._font_num)
            painter.setPen(QPen(self._NUM_COLOR))
            num_str = str(i + 1)
            fm_num = painter.fontMetrics()
            nw = fm_num.horizontalAdvance(num_str)
            nh = fm_num.height()
            painter.drawText(int(nx - nw / 2), int(ny + nh / 4), num_str)

        # 中心圆（ESC 提示）
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(30, 30, 30, 230)))
        painter.drawEllipse(cx - self._INNER_R, cy - self._INNER_R,
                            self._INNER_R * 2, self._INNER_R * 2)
        painter.setFont(self._font_num)
        painter.setPen(QPen(self._CENTER_LABEL_COLOR))
        esc_txt = 'ESC'
        fm_center = painter.fontMetrics()
        fw = fm_center.horizontalAdvance(esc_txt)
        fh = fm_center.height()
        painter.drawText(cx - fw // 2, cy + fh // 4, esc_txt)

        # 外圆边框
        painter.setPen(QPen(self._BORDER_COLOR, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(cx - self._OUTER_R, cy - self._OUTER_R,
                            self._OUTER_R * 2, self._OUTER_R * 2)

    def mouseMoveEvent(self, event):
        new_hovered = self._index_at(event.pos().x(), event.pos().y())
        if new_hovered != self._hovered:
            self._hovered = new_hovered
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self._index_at(event.pos().x(), event.pos().y())
            if idx >= 0:
                self._select(idx)
            else:
                # 点击中心圆等同 ESC
                cx = cy = self._WINDOW_SIZE // 2
                dx = event.pos().x() - cx
                dy = event.pos().y() - cy
                if math.hypot(dx, dy) <= self._INNER_R:
                    self._close_wheel(cancelled=True)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._close_wheel(cancelled=True)
        elif Qt.Key.Key_1 <= key <= Qt.Key.Key_5:
            idx = key - Qt.Key.Key_1
            self._select(idx)

    def leaveEvent(self, event):
        self._hovered = -1
        self.update()
