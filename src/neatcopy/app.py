import os
import sys
import traceback

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QApplication

from neatcopy.application.clip_processor import ClipProcessor
from neatcopy.infrastructure.clipboard import clear_clipboard
from neatcopy.infrastructure.config_manager import ConfigManager, get_default_config_dir
from neatcopy.infrastructure.hotkey_manager import HotkeyManager
from neatcopy.infrastructure.permission_manager import PermissionManager
from neatcopy.presentation.tray_manager import TrayManager
from neatcopy.presentation.wheel_controller import WheelController
from neatcopy.presentation.ui.settings_window import SettingsWindow


def _setup_logging():
    """崩溃时写 crash.log，方便冻结模式无 console 时排查问题。"""
    log_dir = get_default_config_dir()
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, 'crash.log')


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName('NeatCopy')

    config = ConfigManager()
    tray = TrayManager()
    permissions = PermissionManager()
    hotkey = HotkeyManager(config)
    processor = ClipProcessor(config)
    wheel = WheelController(config, processor, hotkey, tray)

    tray.quit_requested.connect(app.quit)
    tray.process_requested.connect(processor.process)
    tray.pause_toggled.connect(hotkey.set_paused)
    hotkey.hotkey_triggered.connect(processor.process, Qt.ConnectionType.QueuedConnection)
    hotkey.clear_clipboard_triggered.connect(
        lambda: (clear_clipboard(), tray.show_info('剪贴板已清空')),
        Qt.ConnectionType.QueuedConnection,
    )
    hotkey.paste_triggered.connect(wheel.open_for_paste, Qt.ConnectionType.QueuedConnection)
    hotkey.debug_message.connect(tray.show_info)
    permissions.info_message.connect(tray.show_info)
    processor.processing_started.connect(tray.set_processing)

    def on_process_done(success: bool, message: str):
        toast_enabled = config.get('general.toast_notification', True)
        if success:
            tray.set_success(toast_enabled=toast_enabled, message=message)
        else:
            tray.set_error(message=message, toast_enabled=toast_enabled)

    processor.process_done.connect(on_process_done)

    settings_win = SettingsWindow(config, hotkey_manager=hotkey)

    def on_open_settings():
        if settings_win.isVisible():
            settings_win.hide()
        else:
            settings_win.show()
            settings_win.raise_()
            settings_win.activateWindow()

    tray.open_settings_requested.connect(on_open_settings)

    QTimer.singleShot(0, permissions.ensure_startup_permissions)

    sys.exit(app.exec())


def run():
    try:
        main()
    except Exception:
        log_path = _setup_logging()
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(traceback.format_exc())
        raise
