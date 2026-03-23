import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication
from config_manager import ConfigManager
from tray_manager import TrayManager


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName('NeatCopy')

    config = ConfigManager()
    tray = TrayManager()

    tray.quit_requested.connect(app.quit)

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
