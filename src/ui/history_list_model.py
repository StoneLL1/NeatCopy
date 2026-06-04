from __future__ import annotations

from datetime import datetime
from typing import Any

from PyQt6.QtCore import QAbstractListModel, QModelIndex, Qt


EntryIdRole = Qt.ItemDataRole.UserRole.value + 1
TimeTextRole = Qt.ItemDataRole.UserRole.value + 2
ModeRole = Qt.ItemDataRole.UserRole.value + 3
PromptNameRole = Qt.ItemDataRole.UserRole.value + 4
SummaryRole = Qt.ItemDataRole.UserRole.value + 5
OriginalRole = Qt.ItemDataRole.UserRole.value + 6
ResultRole = Qt.ItemDataRole.UserRole.value + 7


class HistoryListModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: list[dict[str, Any]] = []
        self._entries_by_id: dict[str, dict[str, Any]] = {}

    def rowCount(self, parent=QModelIndex()):  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._entries)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._entries):
            return None

        entry = self._entries[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return self._summary(entry)
        if role == EntryIdRole:
            return entry.get("id")
        if role == TimeTextRole:
            return self._time_text(entry.get("timestamp", ""))
        if role == ModeRole:
            return entry.get("mode", "rules")
        if role == PromptNameRole:
            return entry.get("prompt_name")
        if role == SummaryRole:
            return self._summary(entry)
        if role == OriginalRole:
            return entry.get("original", "")
        if role == ResultRole:
            return entry.get("result", "")
        return None

    def set_entries(self, entries: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._entries = list(entries)
        self._entries_by_id = {
            entry.get("id"): entry
            for entry in self._entries
            if entry.get("id")
        }
        self.endResetModel()

    def entry_at(self, index: QModelIndex) -> dict[str, Any] | None:
        if not index.isValid() or not 0 <= index.row() < len(self._entries):
            return None
        return self._entries[index.row()]

    def entry_by_id(self, entry_id: str) -> dict[str, Any] | None:
        return self._entries_by_id.get(entry_id)

    def mode_text(self, index: QModelIndex) -> str:
        entry = self.entry_at(index)
        if entry is None:
            return ""
        if entry.get("mode", "rules") == "rules":
            return "规则"
        prompt_name = entry.get("prompt_name", "")
        return f"LLM: {prompt_name}" if prompt_name else "LLM"

    @staticmethod
    def _time_text(timestamp: str) -> str:
        try:
            return datetime.fromisoformat(timestamp).strftime("%H:%M")
        except Exception:
            return "--:--"

    @staticmethod
    def _summary(entry: dict[str, Any]) -> str:
        original = entry.get("original", "") or ""
        first_line = original.split("\n")[0] if original else ""
        summary = first_line[:30]
        if len(first_line) > 30:
            summary += "..."
        return summary
