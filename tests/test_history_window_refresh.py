# tests/test_history_window_refresh.py
"""Offscreen PyQt tests for HistoryWindow conditional refresh behavior."""
import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from PyQt6.QtWidgets import QApplication

from ui.history_window import HistoryWindow


@pytest.fixture(scope='module')
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class DummyConfig:
    def __init__(self):
        self.values = {
            'ui.theme': 'light',
            'history.window_width': 720,
            'history.window_height': 520,
        }

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


class DummyHistory:
    def __init__(self):
        self.revision = 0
        self.get_all_calls = 0
        self.search_calls = 0
        self.entries = [
            {
                'id': '1',
                'timestamp': '2026-06-04T10:00:00',
                'mode': 'rules',
                'prompt_name': None,
                'original': '原文',
                'result': '结果',
            }
        ]

    def get_all(self):
        self.get_all_calls += 1
        return list(self.entries)

    def search(self, keyword):
        self.search_calls += 1
        return list(self.entries)

    def get_by_id(self, entry_id):
        return next((e for e in self.entries if e['id'] == entry_id), None)


def test_constructor_does_not_refresh_list(qapp):
    history = DummyHistory()
    window = HistoryWindow(DummyConfig(), history)

    assert history.get_all_calls == 0
    assert window.list_widget.count() == 0

    window.deleteLater()


def test_show_event_refreshes_first_time(qapp):
    history = DummyHistory()
    window = HistoryWindow(DummyConfig(), history)

    window.show()
    qapp.processEvents()

    assert history.get_all_calls == 1
    assert window.list_widget.count() == 1

    window.hide()
    window.deleteLater()


def test_repeated_show_without_dirty_does_not_refresh_again(qapp):
    history = DummyHistory()
    window = HistoryWindow(DummyConfig(), history)

    window.show()
    qapp.processEvents()
    window.hide()
    qapp.processEvents()
    window.show()
    qapp.processEvents()

    assert history.get_all_calls == 1

    window.hide()
    window.deleteLater()


def test_mark_dirty_forces_refresh_on_next_show(qapp):
    history = DummyHistory()
    window = HistoryWindow(DummyConfig(), history)

    window.show()
    qapp.processEvents()
    window.hide()
    qapp.processEvents()

    history.entries.append({
        'id': '2',
        'timestamp': '2026-06-04T10:01:00',
        'mode': 'rules',
        'prompt_name': None,
        'original': '新增原文',
        'result': '新增结果',
    })
    history.revision += 1
    window.mark_dirty()

    window.show()
    qapp.processEvents()

    assert history.get_all_calls == 2
    assert window.list_widget.count() == 2

    window.hide()
    window.deleteLater()


def test_search_keyword_change_refreshes_list(qapp):
    history = DummyHistory()
    window = HistoryWindow(DummyConfig(), history)

    window._refresh_list()
    window.search_input.setText('原文')
    window._do_search()

    assert history.search_calls == 1

    window.deleteLater()
