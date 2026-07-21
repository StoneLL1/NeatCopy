"""Native macOS global keyboard integration.

Normal shortcuts use Carbon ``RegisterEventHotKey``.  A registered hotkey is
delivered to the app without reading the global keyboard stream, so preview,
history and wheel shortcuts do not depend on Accessibility permission.

The optional double-Command+C feature still needs a Quartz event tap because
it observes a shortcut owned by the foreground application.  Synthetic copy
for the clean shortcut also requires Accessibility permission.
"""
from __future__ import annotations

import ctypes
import logging
import os
import threading
import time
from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal

import ApplicationServices
import Quartz


logger = logging.getLogger(__name__)

_MODIFIER_MASK = (
    Quartz.kCGEventFlagMaskCommand
    | Quartz.kCGEventFlagMaskControl
    | Quartz.kCGEventFlagMaskShift
    | Quartz.kCGEventFlagMaskAlternate
)

_KEYCODES = {
    **dict(zip('abcdefghijklmnopqrstuvwxyz', [0, 11, 8, 2, 14, 3, 5, 4, 34, 38, 40, 37, 46,
                                                45, 31, 35, 12, 15, 1, 17, 32, 9, 13, 7, 16, 6])),
    **{str(i): code for i, code in zip(range(10), [29, 18, 19, 20, 21, 23, 22, 26, 28, 25])},
    **{f'f{i}': code for i, code in enumerate(
        [122, 120, 99, 118, 96, 97, 98, 100, 101, 109, 103, 111], start=1)},
    'space': 49,
    'enter': 36,
    'tab': 48,
    'esc': 53,
    'escape': 53,
    'backspace': 51,
    'delete': 117,
    'home': 115,
    'end': 119,
    'pageup': 116,
    'page up': 116,
    'pagedown': 121,
    'page down': 121,
}

_MODIFIERS = {
    'cmd': Quartz.kCGEventFlagMaskCommand,
    'command': Quartz.kCGEventFlagMaskCommand,
    'meta': Quartz.kCGEventFlagMaskCommand,
    'ctrl': Quartz.kCGEventFlagMaskControl,
    'control': Quartz.kCGEventFlagMaskControl,
    'shift': Quartz.kCGEventFlagMaskShift,
    'alt': Quartz.kCGEventFlagMaskAlternate,
    'option': Quartz.kCGEventFlagMaskAlternate,
}


@dataclass(frozen=True)
class HotkeySpec:
    keycode: int
    modifiers: int


def parse_hotkey(value: str) -> HotkeySpec | None:
    """Parse a persisted shortcut and reject ambiguous/invalid values."""
    parts = [part.strip().lower() for part in (value or '').split('+')]
    modifiers = 0
    keycode = None
    for part in parts:
        if part in _MODIFIERS:
            modifiers |= _MODIFIERS[part]
        elif part in _KEYCODES:
            if keycode is not None:
                return None
            keycode = _KEYCODES[part]
        elif part:
            return None
    if keycode is None or not modifiers:
        return None
    return HotkeySpec(keycode, modifiers)


def accessibility_granted() -> bool:
    """Return whether macOS permits NeatCopy to post synthetic copy events."""
    try:
        return bool(Quartz.CGPreflightPostEventAccess())
    except Exception:
        try:
            return bool(ApplicationServices.AXIsProcessTrusted())
        except Exception:
            return False


def request_accessibility_permission() -> bool:
    """Request the Accessibility-backed permission for event posting."""
    try:
        return bool(Quartz.CGRequestPostEventAccess())
    except Exception:
        try:
            options = {ApplicationServices.kAXTrustedCheckOptionPrompt: True}
            return bool(ApplicationServices.AXIsProcessTrustedWithOptions(options))
        except Exception:
            return False


def listen_event_access_granted() -> bool:
    """Return whether macOS allows passive global keyboard observation."""
    try:
        return bool(Quartz.CGPreflightListenEventAccess())
    except Exception:
        return False


def request_listen_event_access() -> bool:
    """Request Input Monitoring permission for the optional double-copy feature."""
    try:
        return bool(Quartz.CGRequestListenEventAccess())
    except Exception:
        return False


def clipboard_change_count() -> int:
    """Return the native pasteboard generation, or ``-1`` when unavailable."""
    try:
        from AppKit import NSPasteboard
        pasteboard = NSPasteboard.generalPasteboard()
        return int(pasteboard.changeCount()) if pasteboard is not None else -1
    except Exception:
        logger.exception('Could not read the macOS pasteboard change count')
        return -1


def _four_char_code(value: str) -> int:
    return int.from_bytes(value.encode('ascii'), byteorder='big')


class _EventTypeSpec(ctypes.Structure):
    _fields_ = [('event_class', ctypes.c_uint32), ('event_kind', ctypes.c_uint32)]


class _EventHotKeyID(ctypes.Structure):
    _fields_ = [('signature', ctypes.c_uint32), ('identifier', ctypes.c_uint32)]


_CARBON = ctypes.CDLL('/System/Library/Frameworks/Carbon.framework/Carbon')
_EVENT_HANDLER_PROC = ctypes.CFUNCTYPE(
    ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)

_CARBON.GetApplicationEventTarget.argtypes = []
_CARBON.GetApplicationEventTarget.restype = ctypes.c_void_p
_CARBON.InstallEventHandler.argtypes = [
    ctypes.c_void_p,
    _EVENT_HANDLER_PROC,
    ctypes.c_uint32,
    ctypes.POINTER(_EventTypeSpec),
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_void_p),
]
_CARBON.InstallEventHandler.restype = ctypes.c_int32
_CARBON.RemoveEventHandler.argtypes = [ctypes.c_void_p]
_CARBON.RemoveEventHandler.restype = ctypes.c_int32
_CARBON.RegisterEventHotKey.argtypes = [
    ctypes.c_uint32,
    ctypes.c_uint32,
    _EventHotKeyID,
    ctypes.c_void_p,
    ctypes.c_uint32,
    ctypes.POINTER(ctypes.c_void_p),
]
_CARBON.RegisterEventHotKey.restype = ctypes.c_int32
_CARBON.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
_CARBON.UnregisterEventHotKey.restype = ctypes.c_int32
_CARBON.GetEventParameter.argtypes = [
    ctypes.c_void_p,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_void_p,
    ctypes.c_uint32,
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.c_void_p,
]
_CARBON.GetEventParameter.restype = ctypes.c_int32

_NO_ERR = 0
_EVENT_NOT_HANDLED_ERR = -9874
_EVENT_CLASS_KEYBOARD = _four_char_code('keyb')
_EVENT_HOT_KEY_RELEASED = 6
_EVENT_PARAM_DIRECT_OBJECT = _four_char_code('----')
_TYPE_EVENT_HOT_KEY_ID = _four_char_code('hkid')
_NEATCOPY_SIGNATURE = _four_char_code('NtCp')

# Carbon modifier constants are intentionally different from CGEvent flags.
_CMD_KEY = 1 << 8
_SHIFT_KEY = 1 << 9
_OPTION_KEY = 1 << 11
_CONTROL_KEY = 1 << 12

_ACTION_IDS = {
    'clean': 1,
    'wheel': 2,
    'preview': 3,
    'history': 4,
}


def _carbon_modifiers(cg_modifiers: int) -> int:
    result = 0
    if cg_modifiers & Quartz.kCGEventFlagMaskCommand:
        result |= _CMD_KEY
    if cg_modifiers & Quartz.kCGEventFlagMaskShift:
        result |= _SHIFT_KEY
    if cg_modifiers & Quartz.kCGEventFlagMaskAlternate:
        result |= _OPTION_KEY
    if cg_modifiers & Quartz.kCGEventFlagMaskControl:
        result |= _CONTROL_KEY
    return result


class MacHotkeyRegistrar(QObject):
    """Register action shortcuts with the macOS application event target."""

    clean_hotkey = pyqtSignal()
    wheel_hotkey = pyqtSignal()
    preview_hotkey = pyqtSignal()
    history_hotkey = pyqtSignal()
    registration_failed = pyqtSignal(str, str)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._handler_ref = ctypes.c_void_p()
        self._handler_proc = _EVENT_HANDLER_PROC(self._handle_event)
        self._hotkey_refs: dict[str, ctypes.c_void_p] = {}
        self._last_trigger: dict[str, float] = {}

    def register(self) -> None:
        self.unregister()
        target = _CARBON.GetApplicationEventTarget()
        # Dispatch on release, not key-down. This guarantees the physical C
        # from Ctrl/Command+Shift+C is up before NeatCopy injects Command+C.
        event_type = _EventTypeSpec(_EVENT_CLASS_KEYBOARD, _EVENT_HOT_KEY_RELEASED)
        status = _CARBON.InstallEventHandler(
            target,
            self._handler_proc,
            1,
            ctypes.byref(event_type),
            None,
            ctypes.byref(self._handler_ref),
        )
        if status != _NO_ERR:
            message = f'无法安装系统快捷键处理器（错误 {status}）'
            logger.error(message)
            self.registration_failed.emit('all', message)
            return

        definitions = (
            ('clean', 'general.custom_hotkey.enabled', 'general.custom_hotkey.keys', 'cmd+shift+c'),
            ('wheel', 'wheel.enabled', 'wheel.switch_hotkey', 'cmd+shift+p'),
            ('preview', 'preview.enabled', 'preview.hotkey', 'ctrl+q'),
            ('history', 'history.enabled', 'history.hotkey', 'ctrl+h'),
        )
        for action, enabled_key, shortcut_key, default in definitions:
            if not self._config.get(enabled_key, True):
                continue
            shortcut = self._config.get(shortcut_key, default)
            spec = parse_hotkey(shortcut)
            if spec is None:
                message = f'快捷键“{shortcut}”格式无效'
                logger.warning('%s: %s', action, message)
                self.registration_failed.emit(action, message)
                continue
            hotkey_id = _EventHotKeyID(_NEATCOPY_SIGNATURE, _ACTION_IDS[action])
            hotkey_ref = ctypes.c_void_p()
            status = _CARBON.RegisterEventHotKey(
                spec.keycode,
                _carbon_modifiers(spec.modifiers),
                hotkey_id,
                target,
                0,
                ctypes.byref(hotkey_ref),
            )
            if status != _NO_ERR:
                if status == -9878:
                    detail = '已被其他应用占用'
                elif status == -9879:
                    detail = '该组合不受 macOS 支持'
                else:
                    detail = f'系统错误 {status}'
                message = f'快捷键“{shortcut}”注册失败（{detail}）'
                logger.warning('%s: %s', action, message)
                self.registration_failed.emit(action, message)
                continue
            self._hotkey_refs[action] = hotkey_ref
            logger.info('Registered macOS hotkey %s=%s', action, shortcut)

    def unregister(self) -> None:
        for hotkey_ref in self._hotkey_refs.values():
            if hotkey_ref:
                _CARBON.UnregisterEventHotKey(hotkey_ref)
        self._hotkey_refs.clear()
        self._last_trigger.clear()
        if self._handler_ref:
            _CARBON.RemoveEventHandler(self._handler_ref)
            self._handler_ref = ctypes.c_void_p()

    def close(self) -> None:
        self.unregister()

    @property
    def registered_actions(self) -> frozenset[str]:
        return frozenset(self._hotkey_refs)

    def _handle_event(self, next_handler, event, user_data) -> int:
        hotkey_id = _EventHotKeyID()
        actual_size = ctypes.c_uint32()
        status = _CARBON.GetEventParameter(
            event,
            _EVENT_PARAM_DIRECT_OBJECT,
            _TYPE_EVENT_HOT_KEY_ID,
            None,
            ctypes.sizeof(hotkey_id),
            ctypes.byref(actual_size),
            ctypes.byref(hotkey_id),
        )
        if status != _NO_ERR or hotkey_id.signature != _NEATCOPY_SIGNATURE:
            return _EVENT_NOT_HANDLED_ERR
        action = next(
            (name for name, identifier in _ACTION_IDS.items()
             if identifier == hotkey_id.identifier),
            None,
        )
        if action not in self._hotkey_refs:
            return _EVENT_NOT_HANDLED_ERR

        # Carbon can repeat a held hotkey. Suppress only rapid repeats, while
        # preserving intentional consecutive presses.
        now = time.monotonic()
        if now - self._last_trigger.get(action, 0.0) < 0.12:
            return _NO_ERR
        self._last_trigger[action] = now
        logger.info('Triggered macOS hotkey action=%s', action)
        signal = getattr(self, f'{action}_hotkey')
        signal.emit()
        return _NO_ERR


class MacDoubleCopyMonitor(QObject):
    """Observe double Command+C using a permission-gated Quartz event tap."""

    double_copy = pyqtSignal(int)
    permission_missing = pyqtSignal()
    startup_failed = pyqtSignal(str)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._thread = None
        self._tap = None
        self._run_loop = None
        self._first_copy_released_at = 0.0
        self._copy_key_down = False
        self._double_candidate = False
        self._double_candidate_count = -1
        self._process_id = os.getpid()
        self._paused = False

    def set_paused(self, paused: bool) -> None:
        self._paused = paused

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            logger.info('macOS double-copy event tap is already running')
            return
        logger.info('Starting macOS double-copy event tap thread')
        self._thread = threading.Thread(
            target=self._run, name='NeatCopy-macOS-double-copy', daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._run_loop is not None:
            Quartz.CFRunLoopStop(self._run_loop)
        if (self._thread and self._thread.is_alive()
                and self._thread is not threading.current_thread()):
            self._thread.join(timeout=0.5)
        self._thread = None
        self._run_loop = None
        self._tap = None

    def _run(self) -> None:
        logger.info('Creating passive macOS double-copy event tap')
        mask = (
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
            | Quartz.CGEventMaskBit(Quartz.kCGEventKeyUp)
        )
        try:
            tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionListenOnly,
                mask,
                self._event_callback,
                None,
            )
        except Exception:
            logger.exception('Creating the double-copy event tap failed')
            tap = None
        if tap is None:
            logger.warning('Double-copy event tap unavailable; Input Monitoring is required')
            self.permission_missing.emit()
            return

        try:
            self._tap = tap
            run_loop = Quartz.CFRunLoopGetCurrent()
            self._run_loop = run_loop
            # CGEventTapCreate returns a CFMachPort. Core Foundation—not
            # Core Graphics—creates the run-loop source for that port.
            source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
            Quartz.CFRunLoopAddSource(
                run_loop, source, Quartz.kCFRunLoopCommonModes)
            Quartz.CGEventTapEnable(tap, True)
            logger.info('Started macOS double-copy event tap')
            Quartz.CFRunLoopRun()
        except Exception as exc:
            self._tap = None
            self._run_loop = None
            logger.exception('Configuring the double-copy event tap failed')
            self.startup_failed.emit(f'双击 ⌘C 监听启动失败：{exc}')

    def _event_callback(self, proxy, event_type, event, refcon):
        if event_type in (
            Quartz.kCGEventTapDisabledByTimeout,
            Quartz.kCGEventTapDisabledByUserInput,
        ) and self._tap is not None:
            Quartz.CGEventTapEnable(self._tap, True)
            return event
        if event_type not in (Quartz.kCGEventKeyDown, Quartz.kCGEventKeyUp) or self._paused:
            return event
        if (event_type == Quartz.kCGEventKeyDown
                and Quartz.CGEventGetIntegerValueField(
                    event, Quartz.kCGKeyboardEventAutorepeat)):
            return event

        keycode = int(Quartz.CGEventGetIntegerValueField(
            event, Quartz.kCGKeyboardEventKeycode))
        if keycode != _KEYCODES['c']:
            return event

        # Synthetic Command+C from NeatCopy must never count as a user copy.
        source_pid = int(Quartz.CGEventGetIntegerValueField(
            event, Quartz.kCGEventSourceUnixProcessID))
        if source_pid == self._process_id:
            return event
        if not self._config.get('general.double_ctrl_c.enabled', False):
            return event

        if event_type == Quartz.kCGEventKeyDown:
            flags = int(Quartz.CGEventGetFlags(event)) & _MODIFIER_MASK
            if flags != Quartz.kCGEventFlagMaskCommand or self._copy_key_down:
                return event
            self._copy_key_down = True
            now = time.monotonic()
            interval = float(
                self._config.get('general.double_ctrl_c.interval_ms', 300)) / 1000.0
            if (self._first_copy_released_at
                    and now - self._first_copy_released_at <= interval):
                # The tap runs at head-insert, before the foreground app has
                # handled the second copy. Capture the old generation now.
                self._double_candidate = True
                self._double_candidate_count = clipboard_change_count()
            else:
                self._double_candidate = False
                self._double_candidate_count = -1
            return event

        if not self._copy_key_down:
            return event
        self._copy_key_down = False
        now = time.monotonic()
        if self._double_candidate:
            before_count = self._double_candidate_count
            self._double_candidate = False
            self._double_candidate_count = -1
            self._first_copy_released_at = 0.0
            logger.info('Detected completed double Command+C')
            self.double_copy.emit(before_count)
        else:
            self._first_copy_released_at = now
        return event


# Compatibility name for external imports made by the first macOS builds.
MacGlobalInput = MacDoubleCopyMonitor


def simulate_copy() -> None:
    """Inject a plain Command+C to copy the foreground selection."""
    down = Quartz.CGEventCreateKeyboardEvent(None, _KEYCODES['c'], True)
    up = Quartz.CGEventCreateKeyboardEvent(None, _KEYCODES['c'], False)
    for event in (down, up):
        Quartz.CGEventSetFlags(event, Quartz.kCGEventFlagMaskCommand)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
