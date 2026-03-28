# 扇形轮盘 Prompt 快捷选择器：围绕鼠标位置展开，支持鼠标点击和数字键。
import math
import ctypes
import ctypes.wintypes as wintypes
from PyQt6.QtWidgets import QWidget, QApplication, QGraphicsOpacityEffect
from PyQt6.QtCore import (
    Qt, QPoint, QPropertyAnimation, QEasingCurve, pyqtSignal, QTimer
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QPainterPath, QBrush, QCursor, QRadialGradient
)

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

    _WINDOW_SIZE = 268
    _OUTER_R = 112
    _INNER_R = 40

    # ── 调色板（Editorial Monochrome） ───────────────────────
    # 扇区基底（径向渐变：内深 → 外略浅，纯灰阶）
    _SECTOR_INNER = QColor(16, 16, 16, 242)
    _SECTOR_OUTER = QColor(26, 26, 26, 235)
    # 悬停：白色高亮（纯亮度，无色相）
    _HOVER_TINT   = QColor(255, 255, 255,  18)
    _HOVER_BORDER = QColor(255, 255, 255, 128)
    _HOVER_TEXT   = QColor(255, 255, 255)
    _HOVER_NUM    = QColor(195, 195, 195)
    # 上次使用：略亮边框区分（无色相）
    _LAST_TINT    = QColor(255, 255, 255,  10)
    _LAST_BORDER  = QColor(255, 255, 255,  62)
    _LAST_TEXT    = QColor(235, 235, 235)
    # 普通状态
    _BORDER_NORMAL = QColor(255, 255, 255,  18)
    _TEXT_NORMAL   = QColor(205, 205, 205)
    _NUM_NORMAL    = QColor( 70,  70,  70)
    # 中心圆
    _CENTER_INNER  = QColor(10,  10,  10, 252)
    _CENTER_OUTER  = QColor(20,  20,  20, 246)
    _CENTER_BORDER = QColor(255, 255, 255,  25)
    _CENTER_TEXT   = QColor( 55,  55,  55)
    # 装饰外圈
    _DECO_RING     = QColor(255, 255, 255,  10)
    # 数字药丸背景
    _PILL_HOVER    = QColor(255, 255, 255,  22)
    _PILL_NORMAL   = QColor(255, 255, 255,  13)

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
        self._font_name = QFont('Microsoft YaHei UI', 10)
        self._font_name.setBold(True)
        self._font_num = QFont('Microsoft YaHei UI', 7)
        self._font_num.setBold(True)

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

        # 扇区基底径向渐变（所有扇区共用，从中心到外缘）
        base_grad = QRadialGradient(cx, cy, self._OUTER_R * 1.05)
        inner_stop = self._INNER_R / (self._OUTER_R * 1.05)
        base_grad.setColorAt(inner_stop, self._SECTOR_INNER)
        base_grad.setColorAt(1.0, self._SECTOR_OUTER)

        for i, prompt in enumerate(self._prompts):
            start_angle = start_offset + i * sector_deg
            is_hovered = (i == self._hovered)
            is_last = (prompt['id'] == self._last_prompt_id)

            # 环形扇区路径
            path = QPainterPath()
            outer_size = self._OUTER_R * 2
            inner_size = self._INNER_R * 2
            path.moveTo(
                cx + self._OUTER_R * math.cos(math.radians(start_angle)),
                cy + self._OUTER_R * math.sin(math.radians(start_angle)),
            )
            path.arcTo(cx - self._OUTER_R, cy - self._OUTER_R,
                       outer_size, outer_size, -start_angle, -sector_deg)
            path.arcTo(cx - self._INNER_R, cy - self._INNER_R,
                       inner_size, inner_size,
                       -(start_angle + sector_deg), sector_deg)
            path.closeSubpath()

            # 1. 基底渐变填充
            painter.fillPath(path, QBrush(base_grad))

            # 2. 状态叠加色（半透明覆盖层）
            if is_hovered:
                painter.fillPath(path, QBrush(self._HOVER_TINT))
            elif is_last:
                painter.fillPath(path, QBrush(self._LAST_TINT))

            # 3. 边框
            if is_hovered:
                painter.setPen(QPen(self._HOVER_BORDER, 1.2))
            elif is_last:
                painter.setPen(QPen(self._LAST_BORDER, 0.8))
            else:
                painter.setPen(QPen(self._BORDER_NORMAL, 0.6))
            painter.drawPath(path)

            # 文字位置
            mid_angle = math.radians(start_angle + sector_deg / 2)
            text_r = self._INNER_R + (self._OUTER_R - self._INNER_R) * 0.60
            tx = cx + text_r * math.cos(mid_angle)
            ty = cy + text_r * math.sin(mid_angle)

            # Prompt 名称
            painter.setFont(self._font_name)
            if is_hovered:
                painter.setPen(QPen(self._HOVER_TEXT))
            elif is_last:
                painter.setPen(QPen(self._LAST_TEXT))
            else:
                painter.setPen(QPen(self._TEXT_NORMAL))
            name = prompt.get('name', '')
            if len(name) > 5:
                name = name[:4] + '…'
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(name)
            th = fm.height()
            painter.drawText(int(tx - tw / 2), int(ty + th / 4), name)

            # 数字标签（带小药丸背景）
            num_r = self._INNER_R + 13
            nx = cx + num_r * math.cos(mid_angle)
            ny = cy + num_r * math.sin(mid_angle)
            painter.setFont(self._font_num)
            num_str = str(i + 1)
            fm_num = painter.fontMetrics()
            nw = fm_num.horizontalAdvance(num_str)
            nh = fm_num.height()

            pill_w = nw + 7
            pill_h = nh - 1
            pill_x = int(nx - pill_w / 2)
            pill_y = int(ny - pill_h / 2)
            pill_color = self._PILL_HOVER if is_hovered else self._PILL_NORMAL
            painter.setBrush(QBrush(pill_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(pill_x, pill_y, pill_w, pill_h, 3, 3)

            painter.setPen(QPen(self._HOVER_NUM if is_hovered else self._NUM_NORMAL))
            painter.drawText(int(nx - nw / 2), int(ny + nh / 4), num_str)

        # ── 中心圆（ESC 提示） ────────────────────────────────
        center_grad = QRadialGradient(cx, cy, self._INNER_R)
        center_grad.setColorAt(0.0, self._CENTER_INNER)
        center_grad.setColorAt(1.0, self._CENTER_OUTER)
        painter.setBrush(QBrush(center_grad))
        painter.setPen(QPen(self._CENTER_BORDER, 0.8))
        painter.drawEllipse(cx - self._INNER_R, cy - self._INNER_R,
                            self._INNER_R * 2, self._INNER_R * 2)
        painter.setFont(self._font_num)
        painter.setPen(QPen(self._CENTER_TEXT))
        esc_txt = 'ESC'
        fm_center = painter.fontMetrics()
        fw = fm_center.horizontalAdvance(esc_txt)
        fh = fm_center.height()
        painter.drawText(cx - fw // 2, cy + fh // 4, esc_txt)

        # ── 装饰外圈 ──────────────────────────────────────────
        deco_r = self._OUTER_R + 4
        painter.setPen(QPen(self._DECO_RING, 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(cx - deco_r, cy - deco_r, deco_r * 2, deco_r * 2)

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
