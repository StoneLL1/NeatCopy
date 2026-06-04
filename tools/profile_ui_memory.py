"""Profile NeatCopy UI construction costs on Windows.

This script is intentionally outside the app runtime. It creates short-lived
PyQt objects, prints RSS checkpoints, then exits.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wintypes
import json
import os
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


_psapi = ctypes.WinDLL("psapi")
_kernel32 = ctypes.WinDLL("kernel32")
_kernel32.GetCurrentProcess.restype = wintypes.HANDLE
_psapi.GetProcessMemoryInfo.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
    wintypes.DWORD,
]
_psapi.GetProcessMemoryInfo.restype = wintypes.BOOL


def rss_mb() -> float:
    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(counters)
    ok = _psapi.GetProcessMemoryInfo(
        _kernel32.GetCurrentProcess(),
        ctypes.byref(counters),
        counters.cb,
    )
    if not ok:
        raise OSError(ctypes.get_last_error())
    return counters.WorkingSetSize / (1024 * 1024)


class Checkpoints:
    def __init__(self) -> None:
        self._last_time = time.perf_counter()
        self._last_rss = rss_mb()
        self.rows: list[dict[str, float | str]] = []

    def add(self, label: str) -> None:
        now = time.perf_counter()
        mem = rss_mb()
        self.rows.append(
            {
                "label": label,
                "step_ms": round((now - self._last_time) * 1000, 2),
                "rss_mb": round(mem, 2),
                "delta_mb": round(mem - self._last_rss, 2),
            }
        )
        self._last_time = now
        self._last_rss = mem


def profile_history() -> list[dict[str, float | str]]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    from config_manager import ConfigManager
    from history_manager import HistoryManager
    from ui.history_window import HistoryWindow

    cp = Checkpoints()
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    cp.add("QApplication")

    config = ConfigManager()
    history = HistoryManager(max_count=config.get("history.max_count", 500))
    cp.add(f"HistoryManager entries={len(history._data.get('entries', []))}")

    window = HistoryWindow(config, history)
    cp.add("HistoryWindow constructed")

    window._refresh_list("")
    row_count = _history_row_count(window)
    cp.add(f"HistoryWindow refreshed rows={row_count}")
    window.deleteLater()
    app.processEvents()
    return cp.rows


def _history_row_count(window) -> int:
    model = getattr(window, "_history_model", None)
    if model is not None:
        return model.rowCount()
    list_widget = getattr(window, "list_widget", None)
    if list_widget is not None and hasattr(list_widget, "count"):
        return list_widget.count()
    return -1


def profile_settings() -> list[dict[str, float | str]]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    from config_manager import ConfigManager
    from ui.settings_window import SettingsWindow

    cp = Checkpoints()
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    cp.add("QApplication")

    config = ConfigManager()
    window = SettingsWindow(config, hotkey_manager=None)
    cp.add("SettingsWindow constructed")
    window.deleteLater()
    app.processEvents()
    return cp.rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "target",
        choices=["history", "settings"],
        help="UI path to profile",
    )
    args = parser.parse_args()

    rows = profile_history() if args.target == "history" else profile_settings()
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
