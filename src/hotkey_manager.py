# 全局热键：Win32 RegisterHotKey + WH_KEYBOARD_LL，均由 Qt 主线程消息泵驱动。
import ctypes
import ctypes.wintypes as wintypes
import threading
import time
from PyQt6.QtCore import QObject, pyqtSignal, QAbstractNativeEventFilter, QByteArray

user32 = ctypes.windll.user32

WM_HOTKEY = 0x0312
WM_KEYDOWN = 0x0100
WH_KEYBOARD_LL = 13
VK_C = 0x43
VK_CONTROL = 0x11

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
HOTKEY_ID_WHEEL = 2
HOTKEY_ID_PREVIEW = 3

# WH_KEYBOARD_LL 回调签名
_HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int,
                                wintypes.WPARAM, wintypes.LPARAM)


class _KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ('vkCode', wintypes.DWORD),
        ('scanCode', wintypes.DWORD),
        ('flags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong)),
    ]


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

    def __init__(self, callback, wheel_callback=None, preview_callback=None):
        super().__init__()
        self._callback = callback
        self._wheel_callback = wheel_callback
        self._preview_callback = preview_callback

    def nativeEventFilter(self, eventType, message):
        if eventType == QByteArray(b'windows_generic_MSG'):
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY:
                if msg.wParam == HOTKEY_ID_CUSTOM:
                    self._callback()
                    return True, 0
                elif msg.wParam == HOTKEY_ID_WHEEL and self._wheel_callback:
                    self._wheel_callback()
                    return True, 0
                elif msg.wParam == HOTKEY_ID_PREVIEW and self._preview_callback:
                    self._preview_callback()
                    return True, 0
        return False, 0


class HotkeyManager(QObject):
    hotkey_triggered = pyqtSignal()
    wheel_hotkey_triggered = pyqtSignal()   # 独立轮盘切换热键
    preview_hotkey_triggered = pyqtSignal()  # 预览面板热键

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._paused = False
        self._registered = False
        self._wheel_registered = False
        self._preview_registered = False
        self._filter = None
        self._ll_hook = None
        self._ll_proc = None  # prevent GC of ctypes callback
        self._lock = threading.Lock()
        self._last_ctrl_c_time = 0.0
        self._simulating = False  # 防止注入 Ctrl+C 时 Shift 仍按下导致 WM_HOTKEY 重入
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

        # 清洗独立热键（RegisterHotKey）
        cfg_hotkey = self._config.get('general.custom_hotkey') or {}
        if cfg_hotkey.get('enabled', True):
            keys = cfg_hotkey.get('keys', 'ctrl+shift+c')
            mods, vk = _parse_hotkey(keys)
            if vk:
                ok = user32.RegisterHotKey(None, HOTKEY_ID_CUSTOM, mods, vk)
                self._registered = bool(ok)

        # 轮盘切换热键
        cfg_wheel = self._config.get('wheel') or {}
        if cfg_wheel.get('enabled', True):
            wheel_keys = cfg_wheel.get('switch_hotkey', 'ctrl+shift+p')
            w_mods, w_vk = _parse_hotkey(wheel_keys)
            if w_vk:
                ok2 = user32.RegisterHotKey(None, HOTKEY_ID_WHEEL, w_mods, w_vk)
                self._wheel_registered = bool(ok2)

        # 预览面板热键
        cfg_preview = self._config.get('preview') or {}
        if cfg_preview.get('enabled', True):
            preview_keys = cfg_preview.get('hotkey', 'ctrl+q')
            p_mods, p_vk = _parse_hotkey(preview_keys)
            if p_vk:
                ok3 = user32.RegisterHotKey(None, HOTKEY_ID_PREVIEW, p_mods, p_vk)
                self._preview_registered = bool(ok3)

        if (self._registered or self._wheel_registered or self._preview_registered) and app:
            self._filter = _HotkeyFilter(self._on_hotkey, self._on_wheel_hotkey, self._on_preview_hotkey)
            app.installNativeEventFilter(self._filter)

        # 双击 Ctrl+C（WH_KEYBOARD_LL 低级键盘钩子，主线程消息泵驱动）
        cfg_double = self._config.get('general.double_ctrl_c') or {}
        if cfg_double.get('enabled', False):
            self._install_ll_hook()

    def _install_ll_hook(self):
        """安装 WH_KEYBOARD_LL 钩子检测双击 Ctrl+C。不拦截按键，正常复制不受影响。"""
        LLKHF_INJECTED = 0x10  # keybd_event/SendInput 注入的事件，跳过避免自触发

        def hook_proc(nCode, wParam, lParam):
            if nCode >= 0 and wParam == WM_KEYDOWN:
                kb = _KBDLLHOOKSTRUCT.from_address(lParam)
                if kb.vkCode == VK_C and not (kb.flags & LLKHF_INJECTED):
                    # 检查 Ctrl 是否按下（高位为1表示按下）
                    if user32.GetAsyncKeyState(VK_CONTROL) & 0x8000:
                        self._on_ctrl_c()
            return user32.CallNextHookEx(None, nCode, wParam, ctypes.c_long(lParam))

        self._ll_proc = _HOOKPROC(hook_proc)
        self._ll_hook = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, self._ll_proc, None, 0)

    def _unregister_hotkey(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if self._filter and app:
            app.removeNativeEventFilter(self._filter)
            self._filter = None
        if self._registered:
            user32.UnregisterHotKey(None, HOTKEY_ID_CUSTOM)
            self._registered = False
        if self._wheel_registered:
            user32.UnregisterHotKey(None, HOTKEY_ID_WHEEL)
            self._wheel_registered = False
        if self._preview_registered:
            user32.UnregisterHotKey(None, HOTKEY_ID_PREVIEW)
            self._preview_registered = False
        if self._ll_hook:
            user32.UnhookWindowsHookEx(self._ll_hook)
            self._ll_hook = None
            self._ll_proc = None

    def _on_hotkey(self):
        if self._paused or self._simulating:
            # _simulating=True 说明是我们自己注入的 Ctrl+C 在 Shift 仍按下时触发的重入，忽略
            return
        self._simulating = True
        from PyQt6.QtCore import QTimer
        def _simulate():
            # Shift 仍物理按下时，注入的 Ctrl+C 会被系统识别为 Ctrl+Shift+C
            # 再次触发 RegisterHotKey 并消耗按键，导致 App X 收不到 Ctrl+C
            # 先注入 Shift-up，确保系统只看到普通 Ctrl+C
            VK_SHIFT = 0x10
            if user32.GetAsyncKeyState(VK_SHIFT) & 0x8000:
                user32.keybd_event(VK_SHIFT, 0, 2, 0)    # Shift up
            user32.keybd_event(VK_CONTROL, 0, 0, 0)      # Ctrl down
            user32.keybd_event(VK_C, 0, 0, 0)            # C down
            user32.keybd_event(VK_C, 0, 2, 0)            # C up
            user32.keybd_event(VK_CONTROL, 0, 2, 0)      # Ctrl up
            # 等待 App 写入剪贴板后触发处理，同时重置标志位
            def _done():
                self._simulating = False
                self.hotkey_triggered.emit()
            QTimer.singleShot(150, _done)
        QTimer.singleShot(0, _simulate)

    def _on_wheel_hotkey(self):
        if self._paused:
            return
        self.wheel_hotkey_triggered.emit()

    def _on_preview_hotkey(self):
        """预览面板热键回调（toggle 行为）。"""
        self.preview_hotkey_triggered.emit()

    def _on_ctrl_c(self):
        """检测双击 Ctrl+C：两次 Ctrl+C 间隔在阈值内触发清洗。"""
        if self._paused:
            return
        cfg = self._config.get('general.double_ctrl_c') or {}
        interval_ms = cfg.get('interval_ms', 300)
        now = time.time()
        with self._lock:
            if (now - self._last_ctrl_c_time) * 1000 <= interval_ms:
                self._last_ctrl_c_time = 0.0
                # 延迟 80ms 让系统复制操作完成，避免清洗结果被覆盖
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(80, self.hotkey_triggered.emit)
            else:
                self._last_ctrl_c_time = now
