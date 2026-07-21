import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from ui.settings_window import SettingsWindow, _recorded_modifier_names


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class DummyConfig:
    def __init__(self):
        self.values = {
            "ui.theme": "light",
            "ui.window_width": 700,
            "ui.window_height": 520,
            "general.toast_notification": True,
            "general.startup_with_windows": False,
            "general.double_ctrl_c.enabled": False,
            "general.double_ctrl_c.interval": 800,
            "general.custom_hotkey.enabled": True,
            "general.custom_hotkey.keys": "ctrl+shift+c",
            "rules.mode": "rules",
            "llm.enabled": False,
            "llm.base_url": "",
            "llm.model_id": "",
            "llm.api_key": "",
            "llm.temperature": 0.2,
            "llm.timeout": 30,
            "llm.prompts": [],
            "preview.enabled": True,
            "preview.hotkey": "ctrl+q",
            "preview.theme": "dark",
            "wheel.enabled": True,
            "wheel.trigger_with_clean": True,
            "wheel.switch_hotkey": "ctrl+shift+p",
            "history.enabled": True,
            "history.max_count": 500,
            "history.hotkey": "ctrl+h",
        }

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


def test_settings_window_builds_only_initial_page_on_init(qapp):
    window = SettingsWindow(DummyConfig(), hotkey_manager=None)

    built = sorted(window._built_pages.keys())

    assert built == [0]
    assert window._content_stack.count() == 5
    window.deleteLater()


def test_selecting_tab_builds_that_page_once(qapp):
    window = SettingsWindow(DummyConfig(), hotkey_manager=None)

    window._on_nav_select(2)
    first_page = window._built_pages[2]
    window._on_nav_select(2)

    assert window._built_pages[2] is first_page
    assert sorted(window._built_pages.keys()) == [0, 2]
    window.deleteLater()


def test_windows_hotkey_recording_keeps_original_modifier_contract():
    modifiers = (
        Qt.KeyboardModifier.ControlModifier
        | Qt.KeyboardModifier.ShiftModifier
        | Qt.KeyboardModifier.MetaModifier
    )

    # Windows supports Ctrl/Shift/Alt. Its Meta/Windows key must never be
    # serialized as the macOS-only ``cmd`` token.
    assert _recorded_modifier_names(modifiers, 'win32') == ['ctrl', 'shift']
