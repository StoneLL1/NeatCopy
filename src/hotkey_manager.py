"""Cross-platform global shortcut manager.

Windows keeps the original RegisterHotKey/keyboard-hook implementation. On
macOS, Quartz event taps provide the equivalent global key handling and are
kept in a worker thread so the Qt UI loop remains responsive.
"""
from __future__ import annotations

import ctypes
import logging
import sys
import threading
import time

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

if sys.platform == 'darwin':
    from macos_input import (
        MacDoubleCopyMonitor, MacHotkeyRegistrar, accessibility_granted,
        clipboard_change_count, listen_event_access_granted,
        request_accessibility_permission, request_listen_event_access,
        simulate_copy,
    )
else:
    import ctypes.wintypes as wintypes
    from PyQt6.QtCore import QAbstractNativeEventFilter, QByteArray

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

    def _parse_hotkey(keys_str: str):
        parts = [p.strip().lower() for p in keys_str.split('+')]
        mods = 0
        vk = 0
        for p in parts:
            if p in _MOD_MAP:
                mods |= _MOD_MAP[p]
            elif p in _VK_MAP:
                vk = _VK_MAP[p]
        return mods, vk

    HOTKEY_ID_CUSTOM = 1
    HOTKEY_ID_WHEEL = 2
    HOTKEY_ID_PREVIEW = 3
    HOTKEY_ID_HISTORY = 4
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

    class _HotkeyFilter(QAbstractNativeEventFilter):
        def __init__(self, callback, wheel_callback=None, preview_callback=None, history_callback=None):
            super().__init__()
            self._callback = callback
            self._wheel_callback = wheel_callback
            self._preview_callback = preview_callback
            self._history_callback = history_callback

        def nativeEventFilter(self, eventType, message):
            if eventType == QByteArray(b'windows_generic_MSG'):
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY:
                    callbacks = {
                        HOTKEY_ID_CUSTOM: self._callback,
                        HOTKEY_ID_WHEEL: self._wheel_callback,
                        HOTKEY_ID_PREVIEW: self._preview_callback,
                        HOTKEY_ID_HISTORY: self._history_callback,
                    }
                    callback = callbacks.get(msg.wParam)
                    if callback:
                        callback()
                        return True, 0
            return False, 0


logger = logging.getLogger(__name__)


class HotkeyManager(QObject):
    hotkey_triggered = pyqtSignal()
    wheel_hotkey_triggered = pyqtSignal()
    preview_hotkey_triggered = pyqtSignal()
    history_hotkey_triggered = pyqtSignal()
    permission_missing = pyqtSignal()
    input_monitoring_missing = pyqtSignal()
    registration_failed = pyqtSignal(str)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._paused = False
        self._registered = False
        self._wheel_registered = False
        self._preview_registered = False
        self._history_registered = False
        self._filter = None
        self._ll_hook = None
        self._ll_proc = None
        self._lock = threading.Lock()
        self._last_ctrl_c_time = 0.0
        self._simulating = False
        self._mac_capture_token = 0
        self._mac_hotkeys = None
        self._mac_input = None
        self._permission_retry = QTimer(self)
        self._permission_retry.setInterval(1500)
        self._permission_retry.timeout.connect(self._retry_macos_permissions)
        self._input_permission_retry = QTimer(self)
        self._input_permission_retry.setInterval(1500)
        self._input_permission_retry.timeout.connect(
            self._retry_macos_input_permission)
        self._register_hotkey()

    def set_paused(self, paused: bool):
        self._paused = paused
        if self._mac_input:
            self._mac_input.set_paused(paused)

    def reload_config(self, config):
        self._config = config
        self._unregister_hotkey()
        self._register_hotkey()

    def close(self):
        self._unregister_hotkey()

    def _register_hotkey(self):
        if sys.platform == 'darwin':
            self._register_macos()
            return

        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        cfg_hotkey = self._config.get('general.custom_hotkey') or {}
        if cfg_hotkey.get('enabled', True):
            keys = cfg_hotkey.get('keys', 'ctrl+shift+c')
            mods, vk = _parse_hotkey(keys)
            if vk:
                self._registered = bool(user32.RegisterHotKey(None, HOTKEY_ID_CUSTOM, mods, vk))

        cfg_wheel = self._config.get('wheel') or {}
        if cfg_wheel.get('enabled', True):
            mods, vk = _parse_hotkey(cfg_wheel.get('switch_hotkey', 'ctrl+shift+p'))
            if vk:
                self._wheel_registered = bool(user32.RegisterHotKey(None, HOTKEY_ID_WHEEL, mods, vk))

        cfg_preview = self._config.get('preview') or {}
        if cfg_preview.get('enabled', True):
            mods, vk = _parse_hotkey(cfg_preview.get('hotkey', 'ctrl+q'))
            if vk:
                self._preview_registered = bool(user32.RegisterHotKey(None, HOTKEY_ID_PREVIEW, mods, vk))

        cfg_history = self._config.get('history') or {}
        if cfg_history.get('enabled', True):
            mods, vk = _parse_hotkey(cfg_history.get('hotkey', 'ctrl+h'))
            if vk:
                self._history_registered = bool(user32.RegisterHotKey(None, HOTKEY_ID_HISTORY, mods, vk))

        if (self._registered or self._wheel_registered or self._preview_registered or self._history_registered) and app:
            self._filter = _HotkeyFilter(
                self._on_hotkey, self._on_wheel_hotkey,
                self._on_preview_hotkey, self._on_history_hotkey)
            app.installNativeEventFilter(self._filter)

        cfg_double = self._config.get('general.double_ctrl_c') or {}
        if cfg_double.get('enabled', False):
            self._install_ll_hook()

    def _register_macos(self):
        registrar = MacHotkeyRegistrar(self._config, self)
        registrar.clean_hotkey.connect(self._on_hotkey)
        registrar.wheel_hotkey.connect(self._on_wheel_hotkey)
        registrar.preview_hotkey.connect(self._on_preview_hotkey)
        registrar.history_hotkey.connect(self._on_history_hotkey)
        registrar.registration_failed.connect(self._on_macos_registration_failed)
        self._mac_hotkeys = registrar

        double_copy_enabled = self._config.get(
            'general.double_ctrl_c.enabled', False)
        monitor = None
        if double_copy_enabled:
            monitor = MacDoubleCopyMonitor(self._config, self)
            monitor.double_copy.connect(self._on_double_copy)
            monitor.permission_missing.connect(
                self._on_macos_input_permission_missing)
            monitor.startup_failed.connect(
                lambda message: self.registration_failed.emit(message))
            self._mac_input = monitor

        def _activate_current_registration():
            if self._mac_hotkeys is not registrar:
                return
            registrar.register()
            if monitor is not None and self._mac_input is monitor:
                self._start_macos_monitor_when_authorized(monitor)

        # Defer until the Qt event loop starts so callers can attach warning
        # handlers before a conflict or permission problem is reported.
        QTimer.singleShot(0, _activate_current_registration)

    def _on_macos_registration_failed(self, action: str, message: str):
        logger.warning('macOS hotkey registration failed for %s: %s', action, message)
        self.registration_failed.emit(message)

    def _start_macos_monitor_when_authorized(self, monitor):
        # Double-copy is passive observation. On modern macOS it belongs to
        # the separate Input Monitoring permission, not Accessibility.
        if self._mac_input is not monitor:
            return
        if not listen_event_access_granted():
            request_listen_event_access()
            self._on_macos_input_permission_missing()
            return
        monitor.start()

    def _on_macos_permission_missing(self):
        logger.warning('macOS Accessibility permission is unavailable')
        self.permission_missing.emit()
        if sys.platform == 'darwin' and not self._permission_retry.isActive():
            self._permission_retry.start()

    def _retry_macos_permissions(self):
        if sys.platform != 'darwin':
            self._permission_retry.stop()
            return
        if not accessibility_granted():
            return
        self._permission_retry.stop()

    def _on_macos_input_permission_missing(self):
        logger.warning('macOS Input Monitoring permission is unavailable')
        self.input_monitoring_missing.emit()
        if sys.platform == 'darwin' and not self._input_permission_retry.isActive():
            self._input_permission_retry.start()

    def _retry_macos_input_permission(self):
        if sys.platform != 'darwin':
            self._input_permission_retry.stop()
            return
        if not listen_event_access_granted():
            return
        self._input_permission_retry.stop()
        if self._mac_input:
            self._mac_input.start()

    def _install_ll_hook(self):
        """Install the Windows low-level hook for optional double Ctrl+C."""
        LLKHF_INJECTED = 0x10

        def hook_proc(nCode, wParam, lParam):
            if nCode >= 0 and wParam == WM_KEYDOWN:
                kb = _KBDLLHOOKSTRUCT.from_address(lParam)
                if kb.vkCode == VK_C and not (kb.flags & LLKHF_INJECTED):
                    if user32.GetAsyncKeyState(VK_CONTROL) & 0x8000:
                        self._on_ctrl_c()
            return user32.CallNextHookEx(None, nCode, wParam, ctypes.c_long(lParam))

        self._ll_proc = _HOOKPROC(hook_proc)
        self._ll_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._ll_proc, None, 0)

    def _unregister_hotkey(self):
        if sys.platform == 'darwin':
            self._permission_retry.stop()
            self._input_permission_retry.stop()
            self._mac_capture_token += 1
            self._simulating = False
            if self._mac_hotkeys:
                self._mac_hotkeys.close()
                self._mac_hotkeys.deleteLater()
                self._mac_hotkeys = None
            if self._mac_input:
                self._mac_input.stop()
                self._mac_input.deleteLater()
                self._mac_input = None
            return

        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if self._filter and app:
            app.removeNativeEventFilter(self._filter)
            self._filter = None
        for attr, hotkey_id in (
            ('_registered', HOTKEY_ID_CUSTOM),
            ('_wheel_registered', HOTKEY_ID_WHEEL),
            ('_preview_registered', HOTKEY_ID_PREVIEW),
            ('_history_registered', HOTKEY_ID_HISTORY),
        ):
            if getattr(self, attr):
                user32.UnregisterHotKey(None, hotkey_id)
                setattr(self, attr, False)
        if self._ll_hook:
            user32.UnhookWindowsHookEx(self._ll_hook)
            self._ll_hook = None
            self._ll_proc = None

    def _on_hotkey(self):
        if self._paused or self._simulating:
            return
        if sys.platform == 'darwin':
            # RegisterEventHotKey itself needs no special permission, but the
            # clean action must inject Command+C to capture the current
            # foreground selection.
            if not accessibility_granted():
                request_accessibility_permission()
                self._on_macos_permission_missing()
                return
            self._simulating = True
            self._mac_capture_token += 1
            token = self._mac_capture_token
            # MacHotkeyRegistrar dispatches kEventHotKeyReleased. One short
            # event-loop turn also lets the foreground app settle modifier
            # state before the synthetic Command+C arrives.
            logger.info('Clean shortcut released; scheduling foreground copy')
            QTimer.singleShot(20, lambda: self._inject_macos_copy(token))
            return

        self._simulating = True
        def _simulate():
            VK_SHIFT = 0x10
            if user32.GetAsyncKeyState(VK_SHIFT) & 0x8000:
                user32.keybd_event(VK_SHIFT, 0, 2, 0)
            user32.keybd_event(VK_CONTROL, 0, 0, 0)
            user32.keybd_event(VK_C, 0, 0, 0)
            user32.keybd_event(VK_C, 0, 2, 0)
            user32.keybd_event(VK_CONTROL, 0, 2, 0)
            QTimer.singleShot(150, self._finish_simulated_copy)
        QTimer.singleShot(0, _simulate)

    def _finish_simulated_copy(self):
        self._simulating = False
        self.hotkey_triggered.emit()

    def _inject_macos_copy(self, token: int):
        if token != self._mac_capture_token or not self._simulating:
            return
        before_count = clipboard_change_count()
        if before_count < 0:
            self._fail_macos_capture(token, '无法读取 macOS 剪贴板状态')
            return
        try:
            simulate_copy()
        except Exception:
            logger.exception('Could not inject Command+C for the clean hotkey')
            self._fail_macos_capture(
                token, '无法复制当前选中文本，请重新授权辅助功能权限')
            return
        logger.info('Injected Command+C; waiting for pasteboard generation change')
        self._wait_for_macos_clipboard_change(
            token, before_count, time.monotonic() + 1.0, 'clean')

    def _wait_for_macos_clipboard_change(
            self, token: int, before_count: int, deadline: float, source: str):
        if token != self._mac_capture_token or not self._simulating:
            return
        current_count = clipboard_change_count()
        if current_count >= 0 and current_count != before_count:
            logger.info(
                'Pasteboard updated source=%s before=%s after=%s',
                source, before_count, current_count)
            # Give promised pasteboard data a single event-loop turn before
            # the processor asks Qt to materialize its text.
            QTimer.singleShot(
                15, lambda: self._finish_macos_capture(token, source))
            return
        if time.monotonic() >= deadline:
            if source == 'double-copy':
                message = '第二次 ⌘C 没有产生新的剪贴板内容'
            else:
                message = '没有复制到新内容，请确认已选中文本并允许辅助功能权限'
            self._fail_macos_capture(token, message)
            return
        QTimer.singleShot(
            15,
            lambda: self._wait_for_macos_clipboard_change(
                token, before_count, deadline, source),
        )

    def _finish_macos_capture(self, token: int, source: str):
        if token != self._mac_capture_token or not self._simulating:
            return
        self._simulating = False
        logger.info('Clipboard capture completed source=%s', source)
        self.hotkey_triggered.emit()

    def _fail_macos_capture(self, token: int, message: str):
        if token != self._mac_capture_token:
            return
        self._simulating = False
        logger.warning('Clipboard capture failed: %s', message)
        self.registration_failed.emit(message)

    def _on_wheel_hotkey(self):
        if not self._paused:
            self.wheel_hotkey_triggered.emit()

    def _on_preview_hotkey(self):
        if not self._paused:
            self.preview_hotkey_triggered.emit()

    def _on_history_hotkey(self):
        if not self._paused:
            self.history_hotkey_triggered.emit()

    def _on_double_copy(self, before_count: int = -1):
        if self._paused or self._simulating:
            return
        if before_count < 0:
            self.registration_failed.emit('无法确认第二次 ⌘C 的剪贴板更新')
            return
        self._simulating = True
        self._mac_capture_token += 1
        token = self._mac_capture_token
        logger.info('Waiting for second Command+C pasteboard update')
        self._wait_for_macos_clipboard_change(
            token, before_count, time.monotonic() + 1.0, 'double-copy')

    def _on_ctrl_c(self):
        if self._paused:
            return
        cfg = self._config.get('general.double_ctrl_c') or {}
        interval_ms = cfg.get('interval_ms', 300)
        now = time.time()
        with self._lock:
            if (now - self._last_ctrl_c_time) * 1000 <= interval_ms:
                self._last_ctrl_c_time = 0.0
                QTimer.singleShot(80, self.hotkey_triggered.emit)
            else:
                self._last_ctrl_c_time = now
