# tests/test_history_window_refresh.py
"""Offscreen PyQt tests for HistoryWindow conditional refresh behavior."""
import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import re

import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor

from ui.history_window import HistoryWindow
from ui.styles import ColorPalette


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


def _row_count(window):
    return window._history_model.rowCount()


def test_constructor_does_not_refresh_list(qapp):
    history = DummyHistory()
    window = HistoryWindow(DummyConfig(), history)

    assert history.get_all_calls == 0
    assert _row_count(window) == 0

    window.deleteLater()


def test_show_event_refreshes_first_time(qapp):
    history = DummyHistory()
    window = HistoryWindow(DummyConfig(), history)

    window.show()
    qapp.processEvents()

    assert history.get_all_calls == 1
    assert _row_count(window) == 1

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
    assert _row_count(window) == 2

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


def test_history_window_uses_view_model_not_item_widgets(qapp):
    history = DummyHistory()
    window = HistoryWindow(DummyConfig(), history)

    window.show()
    qapp.processEvents()

    assert hasattr(window, "_history_model")
    assert window._history_model.rowCount() == 1

    window.hide()
    window.deleteLater()


def test_apply_theme_does_not_set_search_input_local_stylesheet(qapp, monkeypatch):
    history = DummyHistory()
    window = HistoryWindow(DummyConfig(), history)

    calls = []

    def record(style):
        calls.append(style)

    monkeypatch.setattr(window.search_input, "setStyleSheet", record)

    window._apply_theme("light")

    assert calls == []
    window.deleteLater()


def _qcolor_from_stylesheet(value: str) -> QColor:
    match = re.match(r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)", value)
    if match:
        return QColor(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
            int(float(match.group(4)) * 255),
        )
    return QColor(value)


def _widget_pixel_hex(widget, x=6, y=6):
    image = widget.grab().toImage()
    return image.pixelColor(x, y).name(QColor.NameFormat.HexArgb)


def test_theme_switch_uses_root_qss_for_action_separator(qapp):
    """Review item #1: action_separator must not carry theme-bound inline style."""
    history = DummyHistory()
    window = HistoryWindow(DummyConfig(), history)

    assert window.action_separator.objectName() == "detail_sep"
    assert window.action_separator.styleSheet() == ""

    window.set_theme("dark")
    qapp.processEvents()

    assert "QFrame#detail_sep" in window.styleSheet()
    assert ColorPalette.get("dark")["border"] in window.styleSheet()
    window.deleteLater()


def test_mode_badge_switches_rendered_style_between_rules_and_llm(qapp):
    """Review item #2 (rejected): mode_badge already renders correctly on switch."""
    window = HistoryWindow(DummyConfig(), DummyHistory())
    window.show()
    qapp.processEvents()

    rules_entry = {
        "id": "rules-1",
        "timestamp": "2026-06-04T10:00:00",
        "mode": "rules",
        "prompt_name": None,
        "original": "原文",
        "result": "结果",
    }
    llm_entry = {
        "id": "llm-1",
        "timestamp": "2026-06-04T10:00:01",
        "mode": "llm",
        "prompt_name": "翻译",
        "original": "原文",
        "result": "结果",
    }

    window._show_entry(rules_entry)
    qapp.processEvents()
    assert window.mode_badge.objectName() == "detail_mode_badge_rules"
    # Badge is tiny (~22x12px); sample corner pixel (0,0) to avoid text glyphs
    rules_bg = _widget_pixel_hex(window.mode_badge, x=0, y=0)

    window._show_entry(llm_entry)
    qapp.processEvents()
    assert window.mode_badge.objectName() == "detail_mode_badge_llm"
    llm_bg = _widget_pixel_hex(window.mode_badge, x=0, y=0)

    # The two modes must render different background colors
    assert rules_bg != llm_bg

    window.hide()
    window.deleteLater()
