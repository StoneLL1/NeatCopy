# 全局热键监听：使用 Win32 RegisterHotKey 实现独立热键，keyboard 库实现双击 Ctrl+C。
import ctypes
import ctypes.wintypes as wintypes
import threading
import time
from PyQt6.QtCore import QObject, pyqtSignal

user32 = ctypes.windll.user32

WM_HOTKEY = 0x0312
# RegisterHotKey 修饰键常量
_MOD_MAP = {'ctrl': 0x0002, 'shift': 0x0004, 'alt': 0x0001}
# 虚拟键码映射（小写键名 → VK 代码）
_VK_MAP = {
    **{chr(c): c - 32 for c in range(ord('a'), ord('z') + 1)},  # a-z → 0x41-0x5A
    **{str(i): 0x30 + i for i in range(10)},                      # 0-9 → 0x30-0x39
    **{f'f{i}': 0x70 + i - 1 for i in range(1, 13)},              # f1-f12
    'space': 0x20, 'enter': 0x0D, 'tab': 0x09, 'esc': 0x1B,
    'backspace': 0x08, 'delete': 0x2E, 'insert': 0x2D,
    'home': 0x24, 'end': 0x23, 'page up': 0x21, 'page down': 0x22,
}

HOTKEY_ID_CUSTOM = 1
HOTKEY_ID_SENTINEL = 0xBFFF  # 用于退出消息循环的哨兵


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


class HotkeyManager(QObject):
    hotkey_triggered = pyqtSignal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._paused = False
        self._hotkey_thread_id = None  # Win32 线程 ID，用于 PostThreadMessage
        self._lock = threading.Lock()
        self._last_ctrl_c_time = 0.0
        self._kb_hooks: list = []
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def set_paused(self, paused: bool):
        self._paused = paused

    def reload_config(self, config):
        self._config = config
        # 发送退出信号给旧的消息循环，重新启动
        self._stop_listen()
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def _stop_listen(self):
        """通知消息循环线程退出。"""
        tid = self._hotkey_thread_id
        if tid:
            # 注册一个哨兵热键然后注销，触发 WM_HOTKEY 退出循环
            # 或直接 PostThreadMessage WM_QUIT
            ctypes.windll.user32.PostThreadMessageW(tid, 0x0012, 0, 0)  # WM_QUIT
            self._hotkey_thread_id = None
        # 清理 keyboard 库钩子
        self._unhook_keyboard()

    def _unhook_keyboard(self):
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

    def _listen(self):
        """后台线程：注册热键，运行 Win32 消息循环。"""
        # 保存线程 ID 供 reload_config 使用
        self._hotkey_thread_id = ctypes.windll.kernel32.GetCurrentThreadId()

        registered = False
        cfg_hotkey = self._config.get('general.custom_hotkey') or {}
        if cfg_hotkey.get('enabled', True):
            keys = cfg_hotkey.get('keys', 'ctrl+shift+c')
            mods, vk = _parse_hotkey(keys)
            if vk:
                ok = user32.RegisterHotKey(None, HOTKEY_ID_CUSTOM, mods, vk)
                registered = bool(ok)

        # 双击 Ctrl+C（仍使用 keyboard 库，作为可选功能）
        cfg_double = self._config.get('general.double_ctrl_c') or {}
        if cfg_double.get('enabled', False):
            try:
                import keyboard
                hook = keyboard.on_press_key('c', self._on_c_pressed)
                self._kb_hooks.append(hook)
            except Exception:
                pass

        # Win32 消息循环
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID_CUSTOM:
                if not self._paused:
                    self.hotkey_triggered.emit()
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        # 清理
        if registered:
            user32.UnregisterHotKey(None, HOTKEY_ID_CUSTOM)

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
