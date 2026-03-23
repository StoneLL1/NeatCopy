# 全局热键监听：独立热键 + 双击 Ctrl+C，在后台线程中运行。
import threading
import time
import keyboard
from PyQt6.QtCore import QObject, pyqtSignal


class HotkeyManager(QObject):
    hotkey_triggered = pyqtSignal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._paused = False
        self._last_ctrl_c_time = 0.0
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def set_paused(self, paused: bool):
        self._paused = paused

    def reload_config(self, config):
        self._config = config
        keyboard.unhook_all()
        self._register_hooks()

    def _listen(self):
        self._register_hooks()
        keyboard.wait()

    def _register_hooks(self):
        cfg_hotkey = self._config.get('general.custom_hotkey') or {}
        if cfg_hotkey.get('enabled', True):
            keys = cfg_hotkey.get('keys', 'ctrl+shift+c')
            try:
                keyboard.add_hotkey(keys, self._on_custom_hotkey, suppress=True)
            except Exception:
                pass

        cfg_double = self._config.get('general.double_ctrl_c') or {}
        if cfg_double.get('enabled', False):
            keyboard.on_press_key('c', self._on_c_pressed)

    def _on_custom_hotkey(self):
        if not self._paused:
            self.hotkey_triggered.emit()

    def _on_c_pressed(self, event):
        if not keyboard.is_pressed('ctrl'):
            return
        if self._paused:
            return
        cfg = self._config.get('general.double_ctrl_c') or {}
        interval_ms = cfg.get('interval_ms', 300)
        now = time.time()
        with self._lock:
            if (now - self._last_ctrl_c_time) * 1000 <= interval_ms:
                self._last_ctrl_c_time = 0.0
                self.hotkey_triggered.emit()
            else:
                self._last_ctrl_c_time = now
