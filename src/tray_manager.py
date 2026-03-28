# 托盘管理：图标三态变色、右键菜单、Toast 通知。
import sys
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QTimer, pyqtSignal, QObject
from assets import asset as _asset


class TrayManager(QObject):
    open_settings_requested = pyqtSignal()
    pause_toggled = pyqtSignal(bool)
    quit_requested = pyqtSignal()
    locked_prompt_changed = pyqtSignal(str)   # 从菜单切换锁定时发射 prompt id（空字符串=解除）

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self._config = config
        self._locked_name: str | None = None   # 当前锁定的 prompt 名称
        self._icon_idle = QIcon(_asset('idle.png'))
        self._icon_processing = QIcon(_asset('processing.png'))
        self._icon_success = QIcon(_asset('success.png'))
        self._icon_error = QIcon(_asset('error.png'))

        self._tray = QSystemTrayIcon(self._icon_idle)
        self._tray.setToolTip('NeatCopy')
        self._build_menu()
        self._tray.show()

        self._restore_timer = QTimer(self)
        self._restore_timer.setSingleShot(True)
        self._restore_timer.timeout.connect(self._restore_idle)

    def _build_menu(self):
        # 所有 QMenu/QAction 必须存为实例变量，防止 GC 回收
        self._menu = QMenu()
        self._act_settings = QAction('打开设置', self._menu)
        self._act_settings.triggered.connect(self.open_settings_requested)

        # 锁定 Prompt 状态显示与子菜单
        self._act_locked = QAction('当前锁定：无', self._menu)
        self._act_locked.setEnabled(False)   # 仅显示用，不可直接点击
        self._menu_lock = QMenu('切换锁定 Prompt', self._menu)

        self._act_pause = QAction('暂停监听', self._menu)
        self._act_pause.setCheckable(True)
        self._act_pause.triggered.connect(self._on_pause_toggled)
        self._act_quit = QAction('退出', self._menu)
        self._act_quit.triggered.connect(self.quit_requested)

        self._menu.addAction(self._act_settings)
        self._menu.addSeparator()
        self._menu.addAction(self._act_locked)
        self._menu.addMenu(self._menu_lock)
        self._menu.addSeparator()
        self._menu.addAction(self._act_pause)
        self._menu.addSeparator()
        self._menu.addAction(self._act_quit)
        self._tray.setContextMenu(self._menu)

        # 右键菜单弹出时刷新锁定子菜单
        self._menu.aboutToShow.connect(self._refresh_lock_submenu)

    def _refresh_lock_submenu(self):
        """每次菜单弹出时重建"切换锁定 Prompt"子菜单。"""
        self._menu_lock.clear()
        if self._config is None:
            return

        prompts = self._config.get('llm.prompts') or []
        visible = [p for p in prompts if p.get('visible_in_wheel', True)][:5]
        locked_id = self._config.get('wheel.locked_prompt_id')

        # 解除锁定选项
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

        # 轮盘未启用时隐藏子菜单
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

    def _on_pause_toggled(self, checked: bool):
        self._act_pause.setText('继续监听' if checked else '暂停监听')
        self.pause_toggled.emit(checked)

    def set_processing(self):
        self._restore_timer.stop()
        self._tray.setIcon(self._icon_processing)
        self._tray.setToolTip('NeatCopy — 处理中...')

    def set_success(self, toast_enabled: bool = True, message: str = '已清洗，可直接粘贴'):
        self._tray.setIcon(self._icon_success)
        self._tray.setToolTip('NeatCopy — 成功')
        if toast_enabled:
            self._tray.showMessage('NeatCopy', message,
                                   QSystemTrayIcon.MessageIcon.Information, 2000)
        self._restore_timer.start(1500)

    def set_error(self, message: str, toast_enabled: bool = True):
        self._tray.setIcon(self._icon_error)
        self._tray.setToolTip('NeatCopy — 错误')
        if toast_enabled:
            self._tray.showMessage('NeatCopy', message,
                                   QSystemTrayIcon.MessageIcon.Critical, 3000)
        self._restore_timer.start(1500)

    def _restore_idle(self):
        self._tray.setIcon(self._icon_idle)
        self._tray.setToolTip('NeatCopy')
