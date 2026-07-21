"""Crash-safety and macOS LaunchAgent tests."""
import json
import os
import plistlib
import stat
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import autostart_manager
from config_manager import ConfigManager
from history_manager import HistoryManager
from storage import atomic_write_json


def test_atomic_json_write_replaces_content_and_is_private(tmp_path):
    path = tmp_path / 'data.json'
    atomic_write_json(path, {'value': 1})
    atomic_write_json(path, {'value': 2})

    assert json.loads(path.read_text(encoding='utf-8')) == {'value': 2}
    # Windows chmod only exposes its read-only bit; POSIX systems can verify
    # the complete private-file mode.
    if os.name != 'nt':
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert list(tmp_path.glob('*.tmp')) == []


def test_config_rejects_non_object_root_and_creates_backup(tmp_path):
    config_path = tmp_path / 'config.json'
    config_path.write_text('[]', encoding='utf-8')

    config = ConfigManager(config_dir=str(tmp_path))

    assert config.get('rules.mode') == 'rules'
    assert (tmp_path / 'config.json.bak').exists()


def test_config_failed_write_does_not_mutate_memory(monkeypatch, tmp_path):
    config = ConfigManager(config_dir=str(tmp_path))
    before = config.all()
    monkeypatch.setattr(config, '_write', lambda data: (_ for _ in ()).throw(OSError('disk full')))

    with pytest.raises(OSError):
        config.set('rules.mode', 'llm')

    assert config.all() == before


def test_config_multi_update_is_single_transaction(monkeypatch, tmp_path):
    config = ConfigManager(config_dir=str(tmp_path))
    writes = []
    original = config._write
    monkeypatch.setattr(config, '_write', lambda data: writes.append(data.copy()) or original(data))

    config.update({'rules.mode': 'llm', 'history.max_count': 99})

    assert len(writes) == 1
    assert config.get('rules.mode') == 'llm'
    assert config.get('history.max_count') == 99


def test_history_failed_mutations_roll_back(monkeypatch, tmp_path):
    history = HistoryManager(config_dir=str(tmp_path))
    assert history.add('a', 'b', 'rules', None)
    original = history.get_all()
    monkeypatch.setattr(history, '_write', lambda: False)

    assert history.add('c', 'd', 'rules', None) is False
    assert history.delete(original[0]['id']) is False
    assert history.clear() is False

    assert history.get_all() == original


def test_history_limit_change_trims_immediately(tmp_path):
    history = HistoryManager(config_dir=str(tmp_path), max_count=5)
    for index in range(5):
        history.add(str(index), str(index), 'rules', None)

    assert history.set_max_count(2) is True

    assert [entry['original'] for entry in history.get_all()] == ['4', '3']


@pytest.mark.skipif(sys.platform != 'darwin', reason='macOS only')
def test_launch_agent_enable_validate_refresh_and_disable(monkeypatch, tmp_path):
    plist_path = tmp_path / 'com.stonell1.neatcopy.plist'
    current_program = ['/Applications/NeatCopy.app/Contents/MacOS/NeatCopy']
    monkeypatch.setattr(autostart_manager, '_mac_plist_path', lambda: plist_path)
    monkeypatch.setattr(autostart_manager, '_mac_program_arguments', lambda: current_program)

    assert autostart_manager.enable() == (True, '')
    assert autostart_manager.is_enabled() is True
    with plist_path.open('rb') as handle:
        payload = plistlib.load(handle)
    assert payload['ProgramArguments'] == current_program
    assert payload['LimitLoadToSessionType'] == 'Aqua'

    payload['ProgramArguments'] = ['/stale/path']
    with plist_path.open('wb') as handle:
        plistlib.dump(payload, handle)
    assert autostart_manager.is_enabled() is False
    assert autostart_manager.sync_from_config(True) == (True, '')
    assert autostart_manager.is_enabled() is True
    assert autostart_manager.disable() is True
    assert not plist_path.exists()
