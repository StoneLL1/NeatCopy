# 托盘管理：图标三态变色、右键菜单、Toast 通知。
import os
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QTimer, pyqtSignal, QObject


def _asset(filename: str) -> str:
    base = os.path.join(os.path.dirname(__file__), '..', 'assets')
    return os.path.normpath(os.path.join(base, filename))


class TrayManager(QObject):
    open_settings_requested = pyqtSignal()
    pause_toggled = pyqtSignal(bool)
    quit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
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
        self._act_pause = QAction('暂停监听', self._menu)
        self._act_pause.setCheckable(True)
        self._act_pause.triggered.connect(self._on_pause_toggled)
        self._act_quit = QAction('退出', self._menu)
        self._act_quit.triggered.connect(self.quit_requested)

        self._menu.addAction(self._act_settings)
        self._menu.addAction(self._act_pause)
        self._menu.addSeparator()
        self._menu.addAction(self._act_quit)
        self._tray.setContextMenu(self._menu)

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
