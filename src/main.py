import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication
from config_manager import ConfigManager
from tray_manager import TrayManager
from hotkey_manager import HotkeyManager
from clip_processor import ClipProcessor
from ui.settings_window import SettingsWindow


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName('NeatCopy')

    config = ConfigManager()
    tray = TrayManager()
    hotkey = HotkeyManager(config)
    processor = ClipProcessor(config)

    tray.quit_requested.connect(app.quit)
    tray.pause_toggled.connect(hotkey.set_paused)
    hotkey.hotkey_triggered.connect(processor.process)
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

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
