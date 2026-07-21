"""macOS system-hotkey and optional Quartz-monitor regressions."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

if sys.platform != 'darwin':
    pytest.skip('macOS only', allow_module_level=True)

import Quartz
import macos_input
from macos_input import MacDoubleCopyMonitor, MacHotkeyRegistrar, parse_hotkey


class Config:
    def __init__(self, values=None):
        self.values = values or {
            'general': {
                'custom_hotkey': {'enabled': True, 'keys': 'cmd+shift+c'},
                'double_ctrl_c': {'enabled': False, 'interval_ms': 300},
            },
            'wheel': {'enabled': True, 'switch_hotkey': 'cmd+shift+p'},
            'preview': {'enabled': True, 'hotkey': 'cmd+q'},
            'history': {'enabled': True, 'hotkey': 'cmd+h'},
        }

    def get(self, key, default=None):
        node = self.values
        for part in key.split('.'):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node


def key_event(keycode, flags=0, repeat=False, down=True):
    event = Quartz.CGEventCreateKeyboardEvent(None, keycode, down)
    Quartz.CGEventSetFlags(event, flags)
    Quartz.CGEventSetIntegerValueField(
        event, Quartz.kCGKeyboardEventAutorepeat, int(repeat))
    return event


@pytest.mark.parametrize('value,keycode', [
    ('cmd+shift+c', 8), ('command+q', 12), ('ctrl+alt+f12', 111),
    ('cmd+1', 18), ('cmd+page up', 116),
])
def test_parse_hotkey_supported_keys(value, keycode):
    assert parse_hotkey(value).keycode == keycode


@pytest.mark.parametrize('value', ['', 'c', 'cmd', 'cmd+unknown'])
def test_parse_hotkey_rejects_incomplete_values(value):
    assert parse_hotkey(value) is None


class FakeCarbon:
    def __init__(self, registration_status=0):
        self.registration_status = registration_status
        self.registered = []
        self.unregistered = []
        self.hotkey_identifier = 1
        self.installed_kind = None

    def GetApplicationEventTarget(self):
        return 1

    def InstallEventHandler(self, target, proc, count, event_type, user_data, out_ref):
        self.installed_kind = event_type._obj.event_kind
        out_ref._obj.value = 100
        return 0

    def RemoveEventHandler(self, handler_ref):
        return 0

    def RegisterEventHotKey(self, keycode, modifiers, hotkey_id, target, options, out_ref):
        self.registered.append((keycode, modifiers, hotkey_id.identifier))
        if self.registration_status:
            return self.registration_status
        out_ref._obj.value = 1000 + hotkey_id.identifier
        return 0

    def UnregisterEventHotKey(self, hotkey_ref):
        self.unregistered.append(hotkey_ref.value)
        return 0

    def GetEventParameter(self, event, name, value_type, actual_type, size,
                          actual_size, out_hotkey_id):
        actual_size._obj.value = size
        out_hotkey_id._obj.signature = macos_input._NEATCOPY_SIGNATURE
        out_hotkey_id._obj.identifier = self.hotkey_identifier
        return 0


def test_system_hotkeys_register_without_accessibility(monkeypatch, qapp):
    fake = FakeCarbon()
    monkeypatch.setattr(macos_input, '_CARBON', fake)
    monkeypatch.setattr(macos_input, 'accessibility_granted',
                        lambda: pytest.fail('system registration must not ask for AX'))
    registrar = MacHotkeyRegistrar(Config())

    registrar.register()

    assert registrar.registered_actions == {'clean', 'wheel', 'preview', 'history'}
    assert fake.installed_kind == macos_input._EVENT_HOT_KEY_RELEASED
    assert [item[2] for item in fake.registered] == [1, 2, 3, 4]
    registrar.close()
    assert fake.unregistered == [1001, 1002, 1003, 1004]


def test_disabled_system_hotkey_is_not_registered(monkeypatch, qapp):
    config = Config()
    config.values['preview']['enabled'] = False
    fake = FakeCarbon()
    monkeypatch.setattr(macos_input, '_CARBON', fake)
    registrar = MacHotkeyRegistrar(config)

    registrar.register()

    assert registrar.registered_actions == {'clean', 'wheel', 'history'}


def test_registration_conflict_is_reported(monkeypatch, qapp):
    fake = FakeCarbon(registration_status=-9878)
    monkeypatch.setattr(macos_input, '_CARBON', fake)
    registrar = MacHotkeyRegistrar(Config())
    failures = []
    registrar.registration_failed.connect(lambda action, message: failures.append((action, message)))

    registrar.register()

    assert registrar.registered_actions == set()
    assert len(failures) == 4
    assert all('其他应用占用' in message for _, message in failures)


def test_registered_hotkey_dispatches_once_during_repeat(monkeypatch, qapp):
    fake = FakeCarbon()
    monkeypatch.setattr(macos_input, '_CARBON', fake)
    times = iter([10.0, 10.05])
    monkeypatch.setattr(macos_input.time, 'monotonic', lambda: next(times))
    registrar = MacHotkeyRegistrar(Config())
    emitted = []
    registrar.clean_hotkey.connect(lambda: emitted.append(True))
    registrar.register()

    assert registrar._handle_event(None, object(), None) == 0
    assert registrar._handle_event(None, object(), None) == 0
    assert emitted == [True]


def test_double_command_c_emits_only_on_second_user_copy(monkeypatch, qapp):
    config = Config()
    config.values['general']['double_ctrl_c']['enabled'] = True
    monitor = MacDoubleCopyMonitor(config)
    monitor._process_id = -1  # synthetic test events should count as user events
    emitted = []
    monitor.double_copy.connect(emitted.append)
    times = iter([10.0, 10.05, 10.2, 10.25])
    monkeypatch.setattr(macos_input.time, 'monotonic', lambda: next(times))
    monkeypatch.setattr(macos_input, 'clipboard_change_count', lambda: 41)
    events = [
        (Quartz.kCGEventKeyDown, key_event(8, Quartz.kCGEventFlagMaskCommand)),
        (Quartz.kCGEventKeyUp, key_event(8, down=False)),
        (Quartz.kCGEventKeyDown, key_event(8, Quartz.kCGEventFlagMaskCommand)),
        (Quartz.kCGEventKeyUp, key_event(8, down=False)),
    ]

    for event_type, event in events:
        monitor._event_callback(None, event_type, event, None)

    assert emitted == [41]


def test_held_command_c_does_not_count_as_double_copy(monkeypatch, qapp):
    config = Config()
    config.values['general']['double_ctrl_c']['enabled'] = True
    monitor = MacDoubleCopyMonitor(config)
    monitor._process_id = -1
    emitted = []
    monitor.double_copy.connect(emitted.append)
    event = key_event(8, Quartz.kCGEventFlagMaskCommand)

    monitor._event_callback(None, Quartz.kCGEventKeyDown, event, None)
    monitor._event_callback(None, Quartz.kCGEventKeyDown, event, None)

    assert emitted == []


def test_double_copy_monitor_uses_cf_mach_port_run_loop_source(monkeypatch, qapp):
    monitor = MacDoubleCopyMonitor(Config())
    tap = object()
    run_loop = object()
    source = object()
    calls = []
    monkeypatch.setattr(Quartz, 'CGEventTapCreate', lambda *args: tap)
    monkeypatch.setattr(Quartz, 'CFRunLoopGetCurrent', lambda: run_loop)
    monkeypatch.setattr(
        Quartz, 'CFMachPortCreateRunLoopSource',
        lambda allocator, received_tap, order: (
            calls.append(('source', received_tap)), source)[1])
    monkeypatch.setattr(
        Quartz, 'CFRunLoopAddSource',
        lambda loop, received_source, mode: calls.append(
            ('add', loop, received_source)))
    monkeypatch.setattr(
        Quartz, 'CGEventTapEnable',
        lambda received_tap, enabled: calls.append(
            ('enable', received_tap, enabled)))
    monkeypatch.setattr(Quartz, 'CFRunLoopRun', lambda: calls.append(('run',)))

    monitor._run()

    assert calls == [
        ('source', tap),
        ('add', run_loop, source),
        ('enable', tap, True),
        ('run',),
    ]


@pytest.mark.parametrize('event_type', [
    Quartz.kCGEventTapDisabledByTimeout,
    Quartz.kCGEventTapDisabledByUserInput,
])
def test_disabled_tap_is_reenabled(monkeypatch, qapp, event_type):
    monitor = MacDoubleCopyMonitor(Config())
    monitor._tap = object()
    calls = []
    monkeypatch.setattr(Quartz, 'CGEventTapEnable', lambda tap, enabled: calls.append((tap, enabled)))
    event = key_event(8)

    assert monitor._event_callback(None, event_type, event, None) is event
    assert calls == [(monitor._tap, True)]
