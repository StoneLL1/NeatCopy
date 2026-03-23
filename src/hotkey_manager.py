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
        self._hooks: list = []  # 保存已注册的钩子引用
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def set_paused(self, paused: bool):
        self._paused = paused

    def reload_config(self, config):
        self._config = config
        self._unhook_own()
        self._register_hooks()

    def _unhook_own(self):
        """仅移除本管理器注册的钩子。"""
        for hook in self._hooks:
            try:
                keyboard.unhook(hook)
            except (ValueError, KeyError):
                pass
        self._hooks.clear()

    def _listen(self):
        self._register_hooks()
        keyboard.wait()

    def _register_hooks(self):
        cfg_hotkey = self._config.get('general.custom_hotkey') or {}
        if cfg_hotkey.get('enabled', True):
            keys = cfg_hotkey.get('keys', 'ctrl+shift+c')
            try:
                hook = keyboard.add_hotkey(keys, self._on_custom_hotkey, suppress=True)
                self._hooks.append(hook)
            except Exception:
                # suppress=True 可能需要管理员权限，回退到不拦截模式
                try:
                    hook = keyboard.add_hotkey(keys, self._on_custom_hotkey)
                    self._hooks.append(hook)
                except Exception:
                    pass

        cfg_double = self._config.get('general.double_ctrl_c') or {}
        if cfg_double.get('enabled', False):
            hook = keyboard.on_press_key('c', self._on_c_pressed)
            self._hooks.append(hook)

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
