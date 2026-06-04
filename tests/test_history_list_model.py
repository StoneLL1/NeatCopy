import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from PyQt6.QtCore import QModelIndex

from ui.history_list_model import (
    EntryIdRole,
    HistoryListModel,
    ModeRole,
    OriginalRole,
    PromptNameRole,
    ResultRole,
    SummaryRole,
    TimeTextRole,
)


def _entry(entry_id="1", original="第一行\n第二行", mode="rules", prompt_name=None):
    return {
        "id": entry_id,
        "timestamp": "2026-06-04T10:00:00",
        "mode": mode,
        "prompt_name": prompt_name,
        "original": original,
        "result": "处理结果",
    }


def test_model_exposes_entries_in_order():
    model = HistoryListModel()
    model.set_entries([_entry("1"), _entry("2", original="另一条")])

    assert model.rowCount() == 2
    first = model.index(0, 0)
    assert model.data(first, EntryIdRole) == "1"
    assert model.data(first, TimeTextRole) == "10:00"
    assert model.data(first, ModeRole) == "rules"
    assert model.data(first, PromptNameRole) is None
    assert model.data(first, SummaryRole) == "第一行"
    assert model.data(first, OriginalRole) == "第一行\n第二行"
    assert model.data(first, ResultRole) == "处理结果"


def test_model_truncates_long_summary_to_match_old_widget():
    model = HistoryListModel()
    model.set_entries([_entry(original="一" * 35)])

    text = model.data(model.index(0, 0), SummaryRole)

    assert text == ("一" * 30) + "..."


def test_model_supports_llm_mode_prompt_name():
    model = HistoryListModel()
    model.set_entries([_entry(mode="llm", prompt_name="翻译")])

    index = model.index(0, 0)

    assert model.mode_text(index) == "LLM: 翻译"


def test_model_returns_none_for_invalid_index():
    model = HistoryListModel()
    model.set_entries([_entry()])

    assert model.entry_at(QModelIndex()) is None
    assert model.entry_by_id("missing") is None


def test_delegate_imports_and_reports_fixed_row_size():
    from ui.history_item_delegate import HistoryItemDelegate

    delegate = HistoryItemDelegate(theme="light")

    assert delegate.sizeHint(None, QModelIndex()).height() == 76
