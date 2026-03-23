# 全局热键：Win32 RegisterHotKey + Qt nativeEventFilter，在主线程消息循环中接收。
import ctypes
import ctypes.wintypes as wintypes
import threading
import time
from PyQt6.QtCore import QObject, pyqtSignal, QAbstractNativeEventFilter, QByteArray

user32 = ctypes.windll.user32

WM_HOTKEY = 0x0312
_MOD_MAP = {'ctrl': 0x0002, 'shift': 0x0004, 'alt': 0x0001}
_VK_MAP = {
    **{chr(c): c - 32 for c in range(ord('a'), ord('z') + 1)},
    **{str(i): 0x30 + i for i in range(10)},
    **{f'f{i}': 0x70 + i - 1 for i in range(1, 13)},
    'space': 0x20, 'enter': 0x0D, 'tab': 0x09, 'esc': 0x1B,
    'backspace': 0x08, 'delete': 0x2E, 'insert': 0x2D,
    'home': 0x24, 'end': 0x23, 'page up': 0x21, 'page down': 0x22,
}

HOTKEY_ID_CUSTOM = 1


def _parse_hotkey(keys_str: str):
    """将 'ctrl+shift+c' 解析为 (modifiers_flags, vk_code)。"""
    parts = [p.strip().lower() for p in keys_str.split('+')]
    mods = 0
    vk = 0
    for p in parts:
        if p in _MOD_MAP:
            mods |= _MOD_MAP[p]
        elif p in _VK_MAP:
            vk = _VK_MAP[p]
    return mods, vk


class _HotkeyFilter(QAbstractNativeEventFilter):
    """拦截 Qt 主线程消息循环中的 WM_HOTKEY。"""

    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def nativeEventFilter(self, eventType, message):
        if eventType == QByteArray(b'windows_generic_MSG'):
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID_CUSTOM:
                self._callback()
                return True, 0
        return False, 0


class HotkeyManager(QObject):
    hotkey_triggered = pyqtSignal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._paused = False
        self._registered = False
        self._filter = None
        self._lock = threading.Lock()
        self._last_ctrl_c_time = 0.0
        self._kb_hooks: list = []
        self._register_hotkey()

    def set_paused(self, paused: bool):
        self._paused = paused

    def reload_config(self, config):
        self._config = config
        self._unregister_hotkey()
        self._register_hotkey()

    def _register_hotkey(self):
        """在主线程注册全局热键，通过 Qt 消息循环接收。"""
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()

        cfg_hotkey = self._config.get('general.custom_hotkey') or {}
        if cfg_hotkey.get('enabled', True):
            keys = cfg_hotkey.get('keys', 'ctrl+shift+c')
            mods, vk = _parse_hotkey(keys)
            if vk:
                ok = user32.RegisterHotKey(None, HOTKEY_ID_CUSTOM, mods, vk)
                self._registered = bool(ok)

        if self._registered and app:
            self._filter = _HotkeyFilter(self._on_hotkey)
            app.installNativeEventFilter(self._filter)

        # 双击 Ctrl+C（keyboard 库，可选）
        cfg_double = self._config.get('general.double_ctrl_c') or {}
        if cfg_double.get('enabled', False):
            try:
                import keyboard
                hook = keyboard.on_press_key('c', self._on_c_pressed)
                self._kb_hooks.append(hook)
            except Exception:
                pass

    def _unregister_hotkey(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if self._filter and app:
            app.removeNativeEventFilter(self._filter)
            self._filter = None
        if self._registered:
            user32.UnregisterHotKey(None, HOTKEY_ID_CUSTOM)
            self._registered = False
        # 清理 keyboard 钩子
        try:
            import keyboard
            for hook in self._kb_hooks:
                try:
                    keyboard.unhook(hook)
                except (ValueError, KeyError):
                    pass
        except ImportError:
            pass
        self._kb_hooks.clear()

    def _on_hotkey(self):
        if not self._paused:
            self.hotkey_triggered.emit()

    def _on_c_pressed(self, event):
        try:
            import keyboard as kb
            if not kb.is_pressed('ctrl'):
                return
        except Exception:
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
