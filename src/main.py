import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication
from config_manager import ConfigManager
from tray_manager import TrayManager
from hotkey_manager import HotkeyManager


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName('NeatCopy')

    config = ConfigManager()
    tray = TrayManager()
    hotkey = HotkeyManager(config)

    tray.quit_requested.connect(app.quit)
    tray.pause_toggled.connect(hotkey.set_paused)

    # 临时验证：热键触发时打印（Task 5 替换为 ClipProcessor）
    hotkey.hotkey_triggered.connect(lambda: print('[NeatCopy] 热键触发'))

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
