"""Contracts that must remain stable when macOS support shares Windows code."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from platform_paths import app_data_dir


def test_appdata_override_keeps_windows_directory_layout(monkeypatch, tmp_path):
    monkeypatch.setenv('APPDATA', str(tmp_path))

    assert app_data_dir() == tmp_path / 'NeatCopy'


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows native contract')
def test_windows_hotkey_parser_keeps_original_ctrl_mapping():
    from hotkey_manager import _parse_hotkey

    assert _parse_hotkey('ctrl+shift+c') == (0x0002 | 0x0004, 0x43)
    assert _parse_hotkey('ctrl+h') == (0x0002, 0x48)


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows native contract')
def test_windows_autostart_source_mode_never_touches_registry(monkeypatch):
    import autostart_manager

    monkeypatch.delattr(sys, 'frozen', raising=False)

    assert autostart_manager.enable() == (
        False, '开机自启动仅在打包后的 exe 版本中可用')
