from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import AppKit
import Quartz
from PyQt6.QtCore import QObject, QTimer, Qt, pyqtSignal

from neatcopy.infrastructure.config_manager import get_default_config_dir


_VALID_MODIFIERS = {'ctrl', 'shift', 'alt', 'cmd', 'command'}
_MODIFIER_FLAGS = {
    'cmd': Quartz.kCGEventFlagMaskCommand,
    'command': Quartz.kCGEventFlagMaskCommand,
    'ctrl': Quartz.kCGEventFlagMaskControl,
    'shift': Quartz.kCGEventFlagMaskShift,
    'alt': Quartz.kCGEventFlagMaskAlternate,
}
_KEY_CODE_C = 8
_KEY_CODE_V = 9
_KEY_CODE_MAP = {
    0: 'a', 1: 's', 2: 'd', 3: 'f', 4: 'h', 5: 'g', 6: 'z', 7: 'x',
    8: 'c', 9: 'v', 11: 'b', 12: 'q', 13: 'w', 14: 'e', 15: 'r',
    16: 'y', 17: 't', 18: '1', 19: '2', 20: '3', 21: '4', 22: '6',
    23: '5', 24: '=', 25: '9', 26: '7', 27: '-', 28: '8', 29: '0',
    30: ']', 31: 'o', 32: 'u', 33: '[', 34: 'i', 35: 'p', 37: 'l',
    38: 'j', 39: "'", 40: 'k', 41: ';', 42: '\\', 43: ',', 44: '/',
    45: 'n', 46: 'm', 47: '.', 48: 'tab', 49: 'space', 50: '`',
    51: 'backspace', 53: 'esc', 36: 'enter', 117: 'delete',
}


def default_hotkey() -> str:
    return 'cmd+alt+v'


def copy_shortcut_label() -> str:
    return 'Cmd+C'


def hotkey_example() -> str:
    return default_hotkey()


def _parse_hotkey(keys_str: str):
    parts = [p.strip().lower() for p in keys_str.split('+') if p.strip()]
    if not parts:
        return set(), ''
    modifiers = {p for p in parts if p in _VALID_MODIFIERS}
    keys = [p for p in parts if p not in modifiers]
    key = keys[-1] if keys else ''
    if len(keys) > 1:
        return modifiers, ''
    return modifiers, key


class HotkeyManager(QObject):
    hotkey_triggered = pyqtSignal()
    clear_clipboard_triggered = pyqtSignal()
    paste_triggered = pyqtSignal()
    debug_message = pyqtSignal(str)
    _hotkey_pressed = pyqtSignal()
    _clear_hotkey_pressed = pyqtSignal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._paused = False
        self._hotkey_available = False
        self._lock = threading.Lock()
        self._last_copy_time = 0.0
        self._simulating = False
        self._tap = None
        self._source = None
        self._run_loop = None
        self._listener_thread = None
        self._log_path = Path(get_default_config_dir()) / 'hotkey.log'
        self._hotkey_pressed.connect(
            self._on_hotkey,
            Qt.ConnectionType.QueuedConnection,
        )
        self._clear_hotkey_pressed.connect(
            self._on_clear_hotkey,
            Qt.ConnectionType.QueuedConnection,
        )
        try:
            self._register_hotkey()
        except Exception as exc:
            self._hotkey_available = False
            self._log(f'register hotkey failed: {exc!r}')
            QTimer.singleShot(
                0,
                lambda: self.debug_message.emit('热键监听不可用，请检查系统权限或兼容性'),
            )

    def set_paused(self, paused: bool):
        self._paused = paused
        self._log(f'paused={paused}')

    def reload_config(self, config):
        self._config = config
        self._log(
            'reload_config '
            f'hotkey={self._config.get("general.custom_hotkey.keys")} '
            f'clear_hotkey={self._config.get("general.clear_clipboard_hotkey.keys")}'
        )

    def _register_hotkey(self):
        self._unregister_hotkey()
        self._listener_thread = threading.Thread(
            target=self._run_event_tap,
            name='neatcopy-hotkey-listener',
            daemon=True,
        )
        self._listener_thread.start()
        self._hotkey_available = True
        self.debug_message.emit('热键监听已启动')
        self._log('listener thread started')

    def _unregister_hotkey(self):
        if self._run_loop is not None:
            Quartz.CFRunLoopStop(self._run_loop)
            self._run_loop = None
        self._tap = None
        self._source = None
        self._listener_thread = None

    def _run_event_tap(self):
        try:
            mask = Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
            tap = Quartz.CGEventTapCreate(
                Quartz.kCGHIDEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionDefault,
                mask,
                self._tap_callback,
                None,
            )
        except Exception as exc:
            self._hotkey_available = False
            self._log(f'CGEventTapCreate failed: {exc!r}')
            self.debug_message.emit('热键监听启动失败，请检查辅助功能和输入监控权限')
            return
        if tap is None:
            self._hotkey_available = False
            self._log('CGEventTapCreate returned None')
            self.debug_message.emit('热键监听启动失败，请检查辅助功能和输入监控权限')
            return

        source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
        run_loop = Quartz.CFRunLoopGetCurrent()
        Quartz.CFRunLoopAddSource(run_loop, source, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(tap, True)

        self._tap = tap
        self._source = source
        self._run_loop = run_loop
        self._log('event tap enabled')
        Quartz.CFRunLoopRun()
        self._log('event tap stopped')

    def _tap_callback(self, _proxy, event_type, event, _refcon):
        if event_type != Quartz.kCGEventKeyDown:
            return event
        if self._paused or self._simulating:
            return event

        key_code = int(Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode))
        key_token = _KEY_CODE_MAP.get(key_code, '')
        modifiers = self._event_modifiers(int(Quartz.CGEventGetFlags(event)))
        if key_token:
            self._log(f'key_down key={key_token} code={key_code} modifiers={sorted(modifiers)}')

        if key_token == 'v' and modifiers == {'cmd'}:
            if self._is_neatcopy_frontmost():
                self._log('skip paste interception because neatcopy is frontmost')
                return event
            self._log('paste shortcut intercepted')
            self.paste_triggered.emit()
            return None

        cfg_hotkey = self._config.get('general.custom_hotkey') or {}
        if cfg_hotkey.get('enabled', True):
            expected_modifiers, trigger_key = _parse_hotkey(
                cfg_hotkey.get('keys', default_hotkey())
            )
            if trigger_key and key_token == trigger_key and expected_modifiers.issubset(modifiers):
                self._log(f'hotkey matched key={key_token} modifiers={sorted(modifiers)}')
                self._hotkey_pressed.emit()
                return event

        clear_hotkey = self._config.get('general.clear_clipboard_hotkey') or {}
        if clear_hotkey.get('enabled', False):
            expected_modifiers, trigger_key = _parse_hotkey(clear_hotkey.get('keys', ''))
            if trigger_key and key_token == trigger_key and expected_modifiers.issubset(modifiers):
                self._log(f'clear hotkey matched key={key_token} modifiers={sorted(modifiers)}')
                self._clear_hotkey_pressed.emit()
                return None

        if key_code == _KEY_CODE_C and modifiers & {'cmd', 'ctrl'}:
            self._on_double_copy_key()
        return event

    def _on_hotkey(self):
        if self._paused or self._simulating:
            return
        self._simulating = True
        self.debug_message.emit('已捕获独立热键，开始处理')
        self._log('hotkey triggered')

        def _simulate():
            self._post_command_key(_KEY_CODE_C)

            def _done():
                self._simulating = False
                self.hotkey_triggered.emit()

            QTimer.singleShot(180, _done)

        QTimer.singleShot(120, _simulate)

    def _on_clear_hotkey(self):
        if self._paused or self._simulating:
            return
        self.debug_message.emit('已捕获清空剪贴板热键')
        self._log('clear clipboard hotkey triggered')
        self.clear_clipboard_triggered.emit()

    def trigger_system_paste(self):
        if not self._hotkey_available:
            self._log('skip system paste because hotkey integration unavailable')
            return
        if self._simulating:
            return
        self._simulating = True
        self._log('simulate cmd+v')

        def _simulate():
            self._post_command_key(_KEY_CODE_V)
            QTimer.singleShot(120, self._clear_simulating)

        QTimer.singleShot(0, _simulate)

    def _on_double_copy_key(self):
        if self._paused:
            return
        cfg = self._config.get('general.double_ctrl_c') or {}
        if not cfg.get('enabled', False):
            return
        interval_ms = cfg.get('interval_ms', 300)
        now = time.time()
        with self._lock:
            if (now - self._last_copy_time) * 1000 <= interval_ms:
                self._last_copy_time = 0.0
                self.debug_message.emit('已捕获双击复制，开始处理')
                self._log('double copy matched')
                QTimer.singleShot(100, self.hotkey_triggered.emit)
            else:
                self._last_copy_time = now

    def _event_modifiers(self, flags: int) -> set[str]:
        modifiers = set()
        for name, mask in _MODIFIER_FLAGS.items():
            if flags & mask:
                modifiers.add('cmd' if name == 'command' else name)
        return modifiers

    def _is_neatcopy_frontmost(self) -> bool:
        try:
            workspace = AppKit.NSWorkspace.sharedWorkspace()
            frontmost = workspace.frontmostApplication()
            if frontmost is None:
                return False
            if int(frontmost.processIdentifier()) == os.getpid():
                return True
            bundle_id = frontmost.bundleIdentifier() or ''
            return bundle_id == 'com.neatcopy.app'
        except Exception as exc:
            self._log(f'frontmost app check failed: {exc!r}')
            return False

    def _post_command_key(self, key_code: int):
        source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
        key_down = Quartz.CGEventCreateKeyboardEvent(source, key_code, True)
        Quartz.CGEventSetFlags(key_down, Quartz.kCGEventFlagMaskCommand)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, key_down)

        key_up = Quartz.CGEventCreateKeyboardEvent(source, key_code, False)
        Quartz.CGEventSetFlags(key_up, Quartz.kCGEventFlagMaskCommand)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, key_up)

    def _clear_simulating(self):
        self._simulating = False

    def _log(self, message: str):
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._log_path, 'a', encoding='utf-8') as f:
                f.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} {message}\n')
        except Exception:
            pass
