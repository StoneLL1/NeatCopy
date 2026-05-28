# 托盘管理：图标三态变色、右键菜单、Toast 通知。
from PyQt6.QtWidgets import (
    QSystemTrayIcon, QMenu, QApplication, QLabel, QWidget, QVBoxLayout,
    QWidgetAction, QPushButton,
)
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import (
    QTimer, pyqtSignal, QObject, QPropertyAnimation, QPoint, QEasingCurve,
    Qt,
)
from assets import asset as _asset
from ui.styles import ColorPalette, FONT_SIZE_XS, FONT_SIZE_SM, RADIUS_SM, RADIUS_MD


# ── Toast 通知类型配色 ────────────────────────────────────────
_TOAST_COLORS = {
    'save':    lambda c: (c['fg'],       c['bg']),          # ✓ 已保存 — fg/bg inversion
    'success': lambda c: (c['success'],  '#ffffff'),        # ✓ 清洗完成
    'error':   lambda c: (c['danger'],   '#ffffff'),        # ✕ 处理失败
    'info':    lambda c: (c['fg'],       c['bg']),          # 已应用到剪贴板 — fg/bg inversion
    'warn':    lambda c: (c['warn'],     '#ffffff'),        # ! 连接超时
}


class ToastWidget(QWidget):
    """轻量 Toast 悬浮通知，淡入从底部上滑，淡出后自动销毁。"""

    def __init__(self, text: str, toast_type: str = 'info',
                 duration: int = 2000, theme: str = 'light'):
        super().__init__(None)
        self._duration = duration

        # 无边框 + 置顶 + 不抢焦点 + 不显示在任务栏
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        c = ColorPalette.get(theme)
        bg_color, fg_color = _TOAST_COLORS.get(
            toast_type, _TOAST_COLORS['info'])(c)

        # 内部容器用于 QSS border-radius
        self._container = QWidget()
        self._container.setObjectName('toast_root')
        self._container.setStyleSheet(f"""
            QWidget#toast_root {{
                background: {bg_color};
                color: {fg_color};
                border-radius: {RADIUS_SM};
                font-size: {FONT_SIZE_XS};
                font-weight: 500;
                padding: 8px 16px;
            }}
        """)

        inner = QVBoxLayout(self._container)
        inner.setContentsMargins(0, 0, 0, 0)
        label = QLabel(text)
        label.setStyleSheet('background: transparent; border: none;')
        inner.addWidget(label)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._container)

        # 使用顶层窗口透明度，避免 QGraphicsEffect 抢占 QWidget pixmap 绘制。
        self.setWindowOpacity(0.0)

        self.adjustSize()

    # ── 动画 ──────────────────────────────────────────────────
    def show_animated(self):
        """淡入：上滑 8px，然后延迟淡出。"""
        base_pos = self.pos()
        down_pos = QPoint(base_pos.x(), base_pos.y() + 8)

        # 透明度淡入
        self._anim_opacity_in = QPropertyAnimation(self, b'windowOpacity')
        self._anim_opacity_in.setDuration(250)
        self._anim_opacity_in.setStartValue(0.0)
        self._anim_opacity_in.setEndValue(1.0)
        self._anim_opacity_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        # 位置上滑
        self._anim_pos = QPropertyAnimation(self, b'pos')
        self._anim_pos.setDuration(250)
        self._anim_pos.setStartValue(down_pos)
        self._anim_pos.setEndValue(base_pos)
        self._anim_pos.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.show()
        self._anim_opacity_in.start()
        self._anim_pos.start()

        # 延迟淡出
        QTimer.singleShot(self._duration, self._fade_out)

    def _fade_out(self):
        """淡出 200ms 后关闭并销毁。"""
        base_pos = self.pos()
        down_pos = QPoint(base_pos.x(), base_pos.y() + 4)

        self._anim_pos_out = QPropertyAnimation(self, b'pos')
        self._anim_pos_out.setDuration(200)
        self._anim_pos_out.setStartValue(base_pos)
        self._anim_pos_out.setEndValue(down_pos)
        self._anim_pos_out.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim_pos_out.start()

        self._anim_opacity_out = QPropertyAnimation(self, b'windowOpacity')
        self._anim_opacity_out.setDuration(200)
        self._anim_opacity_out.setStartValue(1.0)
        self._anim_opacity_out.setEndValue(0.0)
        self._anim_opacity_out.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim_opacity_out.finished.connect(self.close)
        self._anim_opacity_out.start()


def _get_menu_stylesheet(theme: str) -> str:
    """生成托盘右键菜单样式。"""
    c = ColorPalette.get(theme)
    return f"""
        QMenu {{
            background: {c['bg']};
            border: 1px solid {c['border']};
            border-radius: {RADIUS_MD};
            padding: 4px 0;
        }}
        QMenu::item {{
            padding: 8px 12px;
            border-radius: {RADIUS_SM};
            color: {c['fg']};
            font-size: {FONT_SIZE_SM};
        }}
        QMenu::item:selected {{
            background: {c['accent_soft']};
        }}
        QMenu::item:disabled {{
            color: {c['muted']};
        }}
        QMenu::separator {{
            height: 1px;
            background: {c['border']};
            margin: 4px 0;
        }}
    """


def _make_exit_action(menu: QMenu, theme: str) -> QWidgetAction:
    """创建带 danger 文字色的退出 action（QWidgetAction 方案）。
    QMenu::item QSS 无法按 action 单独定位颜色，
    因此用 QWidgetAction 内嵌一个自绘 label 来实现 danger 色。"""
    c = ColorPalette.get(theme)
    danger_color = c['danger']
    danger_soft = c['danger_soft']

    action = QWidgetAction(menu)

    exit_btn = QPushButton('退出')
    exit_btn.setObjectName('exit_btn')
    exit_btn.setFlat(True)
    exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    exit_btn.setStyleSheet(f"""
        QPushButton#exit_btn {{
            color: {danger_color};
            background: transparent;
            border: none;
            border-radius: 6px;
            padding: 8px 12px;
            font-size: {FONT_SIZE_SM};
            font-weight: normal;
            text-align: left;
        }}
        QPushButton#exit_btn:hover {{
            background: {danger_soft};
            color: {danger_color};
        }}
        QPushButton#exit_btn:pressed {{
            background: {danger_color};
            color: #ffffff;
        }}
    """)
    exit_btn.clicked.connect(action.trigger)
    action.setDefaultWidget(exit_btn)

    return action


class TrayManager(QObject):
    open_settings_requested = pyqtSignal()
    open_history_requested = pyqtSignal()
    pause_toggled = pyqtSignal(bool)
    quit_requested = pyqtSignal()
    locked_prompt_changed = pyqtSignal(str)

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self._config = config
        self._locked_name: str | None = None
        self._icon_idle = QIcon(_asset('idle.png'))
        self._icon_processing = QIcon(_asset('processing.png'))
        self._icon_success = QIcon(_asset('success.png'))
        self._icon_error = QIcon(_asset('error.png'))

        self._tray = QSystemTrayIcon(self._icon_idle)
        self._tray.setToolTip('NeatCopy')
        self._tray.activated.connect(self._on_tray_activated)
        self._build_menu()
        self._tray.show()

        self._restore_timer = QTimer(self)
        self._restore_timer.setSingleShot(True)
        self._restore_timer.timeout.connect(self._restore_idle)

        self._toast: ToastWidget | None = None

    def _theme(self) -> str:
        return self._config.get('ui.theme', 'light') if self._config else 'light'

    def _build_menu(self):
        self._menu = QMenu()
        self._menu.setStyleSheet(_get_menu_stylesheet(self._theme()))

        self._act_settings = QAction('打开设置', self._menu)
        self._act_settings.triggered.connect(self.open_settings_requested)
        self._act_history = QAction('历史记录', self._menu)
        self._act_history.triggered.connect(self.open_history_requested)

        self._act_locked = QAction('当前锁定：无', self._menu)
        self._act_locked.setEnabled(False)
        self._menu_lock = QMenu('切换锁定 Prompt', self._menu)
        self._menu_lock.setStyleSheet(_get_menu_stylesheet(self._theme()))

        self._act_pause = QAction('暂停监听', self._menu)
        self._act_pause.setCheckable(True)
        self._act_pause.triggered.connect(self._on_pause_toggled)

        # 退出项使用 QWidgetAction 实现 danger 色
        self._act_quit = _make_exit_action(self._menu, self._theme())
        self._act_quit.triggered.connect(self.quit_requested)

        self._menu.addAction(self._act_settings)
        self._menu.addAction(self._act_history)
        self._menu.addSeparator()
        self._menu.addAction(self._act_locked)
        self._menu.addMenu(self._menu_lock)
        self._menu.addSeparator()
        self._menu.addAction(self._act_pause)
        self._menu.addSeparator()
        self._menu.addAction(self._act_quit)
        self._tray.setContextMenu(self._menu)

        self._menu.aboutToShow.connect(self._refresh_lock_submenu)

    def _refresh_lock_submenu(self):
        """每次菜单弹出时重建"切换锁定 Prompt"子菜单。"""
        self._menu_lock.clear()
        self._menu_lock.setStyleSheet(_get_menu_stylesheet(self._theme()))

        if self._config is None:
            return

        prompts = self._config.get('llm.prompts') or []
        visible = [p for p in prompts if p.get('visible_in_wheel', True)][:5]
        locked_id = self._config.get('wheel.locked_prompt_id')

        act_none = QAction('（无 / 解除锁定）', self._menu_lock)
        act_none.setCheckable(True)
        act_none.setChecked(not locked_id)
        act_none.triggered.connect(lambda: self._on_lock_selected(''))
        self._menu_lock.addAction(act_none)

        if visible:
            self._menu_lock.addSeparator()
        for p in visible:
            act = QAction(p['name'], self._menu_lock)
            act.setCheckable(True)
            act.setChecked(p['id'] == locked_id)
            pid = p['id']
            act.triggered.connect(lambda checked, _pid=pid: self._on_lock_selected(_pid))
            self._menu_lock.addAction(act)

        wheel_cfg = self._config.get('wheel') or {}
        wheel_enabled = wheel_cfg.get('enabled', True)
        self._menu_lock.setEnabled(wheel_enabled)
        self._act_locked.setVisible(wheel_enabled)

    def _on_lock_selected(self, pid: str):
        self.locked_prompt_changed.emit(pid)

    def update_locked_prompt(self, name: str | None):
        """更新托盘菜单中锁定 Prompt 的显示名称。"""
        self._locked_name = name
        if name:
            self._act_locked.setText(f'当前锁定：{name}')
        else:
            self._act_locked.setText('当前锁定：无')

    def _on_tray_activated(self, reason):
        """托盘图标点击事件处理。"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.open_settings_requested.emit()

    def _on_pause_toggled(self, checked: bool):
        self._act_pause.setText('继续监听' if checked else '暂停监听')
        self.pause_toggled.emit(checked)

    # ── 状态切换 ───────────────────────────────────────────────

    def set_processing(self):
        self._restore_timer.stop()
        self._tray.setIcon(self._icon_processing)
        self._tray.setToolTip('NeatCopy — 处理中...')

    def set_success(self, toast_enabled: bool = True, message: str = '已清洗，可直接粘贴'):
        self._tray.setIcon(self._icon_success)
        self._tray.setToolTip('NeatCopy — 成功')
        if toast_enabled:
            self._show_toast('✓ ' + message, 'success')
        self._restore_timer.start(1500)

    def set_error(self, message: str, toast_enabled: bool = True):
        self._tray.setIcon(self._icon_error)
        self._tray.setToolTip('NeatCopy — 错误')
        if toast_enabled:
            self._show_toast('✗ ' + message, 'error', duration=3000)
        self._restore_timer.start(1500)

    def show_save_toast(self, message: str = '已保存'):
        """显示保存成功的 accent 色 Toast。"""
        self._show_toast('✓ ' + message, 'save')

    def show_info_toast(self, message: str):
        """显示信息型 Toast。"""
        self._show_toast(message, 'info')

    def show_warn_toast(self, message: str):
        """显示警告型 Toast。"""
        self._show_toast('⚠ ' + message, 'warn')

    # ── Toast ──────────────────────────────────────────────────

    def _show_toast(self, text: str, toast_type: str = 'info',
                    duration: int = 2000):
        """在屏幕右下角显示 Toast。"""
        if self._toast is not None:
            self._toast.close()
            self._toast = None

        toast = ToastWidget(text, toast_type, duration,
                            theme=self._theme())
        self._toast = toast

        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.right() - toast.width() - 16
            y = geo.bottom() - toast.height() - 16
            toast.move(x, y)

        toast.show_animated()

    def _restore_idle(self):
        self._tray.setIcon(self._icon_idle)
        self._tray.setToolTip('NeatCopy')

    def refresh_style(self):
        """主题切换后刷新菜单样式。"""
        self._menu.setStyleSheet(_get_menu_stylesheet(self._theme()))
        self._menu_lock.setStyleSheet(_get_menu_stylesheet(self._theme()))
        # 重建退出 action 以更新 danger 色
        self._menu.removeAction(self._act_quit)
        self._act_quit = _make_exit_action(self._menu, self._theme())
        self._act_quit.triggered.connect(self.quit_requested)
        self._menu.addAction(self._act_quit)
