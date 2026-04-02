import os
import sys

from PyQt6.QtCore import Qt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from neatcopy.presentation.ui import settings_window


class TestModifiersToTokens:
    def test_maps_command_and_control_correctly_on_macos(self, monkeypatch):
        monkeypatch.setattr(settings_window.sys, 'platform', 'darwin')

        assert settings_window._modifiers_to_tokens(Qt.KeyboardModifier.ControlModifier) == ['cmd']
        assert settings_window._modifiers_to_tokens(Qt.KeyboardModifier.MetaModifier) == ['ctrl']

    def test_keeps_standard_mapping_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(settings_window.sys, 'platform', 'linux')

        assert settings_window._modifiers_to_tokens(Qt.KeyboardModifier.ControlModifier) == ['ctrl']
        assert settings_window._modifiers_to_tokens(Qt.KeyboardModifier.MetaModifier) == ['cmd']
