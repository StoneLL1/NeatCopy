"""Product-level macOS regressions spanning UI, shortcuts and shutdown."""
import json
import os
import sys

import pytest
from PyQt6.QtCore import QEvent, QPoint, Qt
from PyQt6.QtGui import QKeyEvent

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import clip_processor as clip_module
import hotkey_manager as hotkey_module
import main as main_module
import ui.settings_window as settings_module
import wheel_window as wheel_module
from clip_processor import ClipProcessor, _LLMWorker
from config_manager import ConfigManager
from hotkey_manager import HotkeyManager
from platform_defaults import HISTORY_HOTKEY, PREVIEW_HOTKEY
from ui.preview_window import PreviewWindow
from ui.settings_window import SettingsWindow
from wheel_window import WheelWindow


pytestmark = pytest.mark.skipif(sys.platform != 'darwin', reason='macOS only')


class FlatConfig:
    def __init__(self, values=None):
        self.values = values or {}
        self.update_calls = []

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value

    def update(self, values):
        self.update_calls.append(dict(values))
        self.values.update(values)


def test_unsafe_legacy_command_shortcuts_are_migrated(tmp_path):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps({
        'preview': {'hotkey': 'cmd+q'},
        'history': {'hotkey': 'cmd+h'},
    }), encoding='utf-8')

    config = ConfigManager(str(tmp_path))

    assert config.get('preview.hotkey') == PREVIEW_HOTKEY == 'ctrl+q'
    assert config.get('history.hotkey') == HISTORY_HOTKEY == 'ctrl+h'
    persisted = json.loads(path.read_text(encoding='utf-8'))
    assert persisted['preview']['hotkey'] == 'ctrl+q'
    assert persisted['history']['hotkey'] == 'ctrl+h'


def test_single_instance_lock_rejects_second_process_slot(monkeypatch, tmp_path):
    monkeypatch.setenv('APPDATA', str(tmp_path))
    first, first_duplicate = main_module._check_single_instance()
    second, second_duplicate = main_module._check_single_instance()
    try:
        assert first_duplicate is False
        assert second is None
        assert second_duplicate is True
    finally:
        first.close()


def test_pause_suppresses_every_hotkey_signal(monkeypatch, qapp):
    monkeypatch.setattr(HotkeyManager, '_register_hotkey', lambda self: None)
    manager = HotkeyManager(FlatConfig())
    emitted = []
    manager.hotkey_triggered.connect(lambda: emitted.append('clean'))
    manager.wheel_hotkey_triggered.connect(lambda: emitted.append('wheel'))
    manager.preview_hotkey_triggered.connect(lambda: emitted.append('preview'))
    manager.history_hotkey_triggered.connect(lambda: emitted.append('history'))
    manager.set_paused(True)

    manager._on_hotkey()
    manager._on_wheel_hotkey()
    manager._on_preview_hotkey()
    manager._on_history_hotkey()

    assert emitted == []


def test_accessibility_retry_stops_after_grant(monkeypatch, qapp):
    monkeypatch.setattr(HotkeyManager, '_register_hotkey', lambda self: None)
    manager = HotkeyManager(FlatConfig())

    class Monitor:
        def __init__(self):
            self.starts = 0

        def start(self):
            self.starts += 1

    manager._on_macos_permission_missing()
    assert manager._permission_retry.isActive()

    monkeypatch.setattr(hotkey_module, 'accessibility_granted', lambda: True)
    manager._retry_macos_permissions()

    assert not manager._permission_retry.isActive()


def test_input_permission_retry_starts_double_copy_monitor(monkeypatch, qapp):
    monkeypatch.setattr(HotkeyManager, '_register_hotkey', lambda self: None)
    manager = HotkeyManager(FlatConfig())

    class Monitor:
        def __init__(self):
            self.starts = 0

        def start(self):
            self.starts += 1

    monitor = Monitor()
    manager._mac_input = monitor
    manager._on_macos_input_permission_missing()
    assert manager._input_permission_retry.isActive()

    monkeypatch.setattr(hotkey_module, 'listen_event_access_granted', lambda: True)
    manager._retry_macos_input_permission()

    assert monitor.starts == 1
    assert not manager._input_permission_retry.isActive()


def test_monitor_is_not_created_before_input_permission(monkeypatch, qapp):
    monkeypatch.setattr(HotkeyManager, '_register_hotkey', lambda self: None)
    manager = HotkeyManager(FlatConfig())

    class Monitor:
        def __init__(self):
            self.starts = 0

        def start(self):
            self.starts += 1

    monitor = Monitor()
    requested = []
    manager._mac_input = monitor
    monkeypatch.setattr(hotkey_module, 'listen_event_access_granted', lambda: False)
    monkeypatch.setattr(hotkey_module, 'request_listen_event_access',
                        lambda: requested.append(True))

    manager._start_macos_monitor_when_authorized(monitor)

    assert requested == [True]
    assert monitor.starts == 0
    assert manager._input_permission_retry.isActive()


def test_released_clean_hotkey_waits_for_new_pasteboard(monkeypatch, qapp):
    monkeypatch.setattr(HotkeyManager, '_register_hotkey', lambda self: None)
    manager = HotkeyManager(FlatConfig())
    counts = iter([7, 7, 8])
    copied = []
    emitted = []
    monkeypatch.setattr(hotkey_module, 'accessibility_granted', lambda: True)
    monkeypatch.setattr(hotkey_module, 'clipboard_change_count',
                        lambda: next(counts))
    monkeypatch.setattr(hotkey_module, 'simulate_copy', lambda: copied.append(True))
    monkeypatch.setattr(hotkey_module.QTimer, 'singleShot',
                        lambda delay, callback: callback())
    manager.hotkey_triggered.connect(lambda: emitted.append(True))

    manager._on_hotkey()

    assert copied == [True]
    assert emitted == [True]
    assert manager._simulating is False


def test_clean_hotkey_never_processes_stale_clipboard(monkeypatch, qapp):
    monkeypatch.setattr(HotkeyManager, '_register_hotkey', lambda self: None)
    manager = HotkeyManager(FlatConfig())
    errors = []
    emitted = []
    manager.registration_failed.connect(errors.append)
    manager.hotkey_triggered.connect(lambda: emitted.append(True))
    manager._simulating = True
    manager._mac_capture_token = 4
    monkeypatch.setattr(hotkey_module, 'clipboard_change_count', lambda: 9)

    manager._wait_for_macos_clipboard_change(
        4, 9, hotkey_module.time.monotonic() - 1, 'clean')

    assert emitted == []
    assert errors and '没有复制到新内容' in errors[0]


def test_wheel_is_independent_top_level_window_on_macos(qapp):
    wheel = WheelWindow()

    window_type = wheel.windowFlags() & Qt.WindowType.WindowType_Mask
    assert window_type == Qt.WindowType.Window
    assert wheel.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert not hasattr(wheel, '_mouse_monitor')
    wheel.deleteLater()


def test_wheel_activates_globally_and_restores_previous_app(monkeypatch, qapp):
    previous = object()
    activations = []
    restored = []
    monkeypatch.setattr(
        wheel_module, '_macos_frontmost_application', lambda: previous)
    monkeypatch.setattr(
        wheel_module, '_activate_macos_application',
        lambda: activations.append(True))
    monkeypatch.setattr(
        wheel_module, '_restore_macos_application', restored.append)
    wheel = WheelWindow()

    wheel.show_at(
        QPoint(300, 300),
        [{'id': 'one', 'name': 'One'}, {'id': 'two', 'name': 'Two'}],
        lambda prompt_id: None,
    )
    qapp.processEvents()

    assert wheel.isVisible()
    assert activations
    assert wheel._previous_macos_app is previous

    wheel._anim.stop()
    wheel._close_wheel(cancelled=True)
    wheel._anim.stop()
    wheel._finish_close()

    assert not wheel.isVisible()
    assert restored == [previous]
    wheel.deleteLater()


def test_hotkey_recorder_uses_physical_macos_modifier_names(qapp):
    window = SettingsWindow(FlatConfig())
    window._on_nav_select(1)

    # On macOS Qt reports the physical Control key as MetaModifier.
    window._recording_target = 'preview'
    window.keyPressEvent(QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Q,
        Qt.KeyboardModifier.MetaModifier,
    ))
    assert window._btn_preview_hotkey.text() == 'ctrl+q'
    assert window._pending['preview.hotkey'] == 'ctrl+q'

    # Conversely, physical Command arrives as ControlModifier.
    window._recording_target = 'history'
    window.keyPressEvent(QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_H,
        Qt.KeyboardModifier.ControlModifier,
    ))
    assert window._btn_history_hotkey.text() == 'cmd+h'
    assert window._pending['history.hotkey'] == 'cmd+h'
    window.deleteLater()


def test_settings_startup_is_deferred_and_saved_transactionally(monkeypatch, qapp):
    config = FlatConfig({
        'general.startup_with_windows': False,
        'general.toast_notification': True,
        'ui.theme': 'light',
    })
    enabled = []
    monkeypatch.setattr(settings_module, '_autostart_enable',
                        lambda: enabled.append(True) or (True, ''))
    window = SettingsWindow(config)
    saved = []
    window.settings_saved.connect(lambda: saved.append(True))

    window._toggle_startup.checked = True
    assert enabled == []
    assert config.get('general.startup_with_windows') is False

    assert window._do_save() is True
    assert enabled == [True]
    assert config.update_calls[-1] == {'general.startup_with_windows': True}
    assert saved == [True]
    window.deleteLater()


def test_settings_failed_transaction_keeps_pending(monkeypatch, qapp):
    class BrokenConfig(FlatConfig):
        def update(self, values):
            raise OSError('disk full')

    config = BrokenConfig({
        'general.startup_with_windows': False,
        'general.toast_notification': True,
        'ui.theme': 'light',
    })
    warnings = []
    monkeypatch.setattr(settings_module.QMessageBox, 'warning',
                        lambda *args: warnings.append(args))
    window = SettingsWindow(config)
    window._mark('general.toast_notification', False)

    assert window._do_save() is False
    assert window._pending == {'general.toast_notification': False}
    assert warnings
    window.deleteLater()


def test_preview_apply_reports_real_result_and_escapes_prompt(qapp):
    preview = PreviewWindow(FlatConfig({'preview.theme': 'dark'}))
    applied = []
    preview.apply_to_clipboard.connect(applied.append)
    preview.update_result('edited result', '<b>unsafe</b>')

    assert '&lt;b&gt;unsafe&lt;/b&gt;' in preview.prompt_label.text()
    preview._on_apply_clicked()
    assert applied == ['edited result']
    assert preview.status_label.text() == '正在应用...'
    preview.set_apply_result(False)
    assert preview.status_label.text() == '应用失败'
    preview.deleteLater()


def test_wheel_geometry_selection_and_shutdown(monkeypatch, qapp):
    wheel = WheelWindow()
    wheel._prompts = [{'id': 'a'}, {'id': 'b'}, {'id': 'c'}, {'id': 'd'}]
    selected = []
    wheel._selected_callback = selected.append
    wheel._wheel_open = True
    monkeypatch.setattr(wheel, '_uninstall_mouse_hook', lambda: None)
    monkeypatch.setattr(wheel, '_close_wheel',
                        lambda cancelled=True: setattr(wheel, '_wheel_open', False))

    assert wheel._index_at(130, 50) == 0
    assert wheel._index_at(210, 130) == 1
    assert wheel._index_at(130, 130) == -1
    wheel._select(2)
    qapp.processEvents()
    assert selected == ['c']
    wheel.shutdown()
    assert wheel._wheel_open is False
    wheel.deleteLater()


def test_worker_rejects_empty_response_and_copies_config(monkeypatch, qapp):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {'choices': [{'message': {'content': ''}}]}

    class Client:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, *args, **kwargs):
            return Response()

    import httpx
    monkeypatch.setattr(httpx, 'Client', Client)
    source = {'api_key': 'before', 'timeout': 3}
    worker = _LLMWorker('input', 'prompt', source)
    source['api_key'] = 'after'
    failures = []
    worker.failed.connect(failures.append)

    worker.run()

    assert worker._llm_config['api_key'] == 'before'
    assert failures and '模型返回了空结果' in failures[0]


def test_processor_worker_cleanup_is_identity_safe(qapp):
    processor = ClipProcessor(FlatConfig())
    current = object()
    obsolete = object()
    idle = []
    processor.became_idle.connect(lambda: idle.append(True))
    processor._current_worker = current
    processor._current_prompt_obj = {'name': 'x'}
    processor._current_original = 'input'

    processor._on_worker_finished(obsolete)
    assert processor._current_worker is current
    processor._on_worker_finished(current)

    assert processor._current_worker is None
    assert processor._current_prompt_obj is None
    assert processor._current_original is None
    assert idle == [True]
