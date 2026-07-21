# src/history_manager.py
"""历史记录数据管理：读写 history.json，增删查接口。"""
import json
import os
import uuid
import copy
from datetime import datetime
from pathlib import Path
from typing import Any

from platform_paths import app_data_dir
from storage import atomic_write_json


class HistoryManager:
    """历史记录管理器，负责读写 history.json 文件。"""

    def __init__(self, config_dir: str | None = None, max_count: int = 500):
        if config_dir is None:
            history_path = app_data_dir() / 'history.json'
        else:
            # Preserve the original test/migration API: an explicit APPDATA
            # root contains the NeatCopy subdirectory.
            history_path = Path(config_dir) / 'NeatCopy' / 'history.json'
        self._history_path = history_path
        self._history_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._max_count = max(1, int(max_count))
        except (TypeError, ValueError):
            self._max_count = 500
        self._data = self._load()
        self._revision = 0

    def _load(self) -> dict:
        """加载历史文件，不存在或损坏时返回空结构。"""
        if not self._history_path.exists():
            return {'entries': []}
        try:
            with open(self._history_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict) or not isinstance(data.get('entries'), list):
                raise ValueError('history root must contain an entries list')
            entries = []
            for entry in data['entries']:
                if not isinstance(entry, dict) or not isinstance(entry.get('id'), str):
                    continue
                entries.append({
                    'id': entry['id'],
                    'timestamp': str(entry.get('timestamp') or ''),
                    'mode': str(entry.get('mode') or 'rules'),
                    'prompt_name': entry.get('prompt_name'),
                    'original': str(entry.get('original') or ''),
                    'result': str(entry.get('result') or ''),
                })
            data = {'entries': entries[-self._max_count:]}
            try:
                os.chmod(self._history_path, 0o600)
            except OSError:
                pass
            return data
        except (json.JSONDecodeError, TypeError, ValueError, IOError):
            # 文件损坏，备份后重建
            backup = self._history_path.with_suffix('.json.bak')
            try:
                self._history_path.rename(backup)
            except Exception:
                pass
            return {'entries': []}

    def _write(self) -> bool:
        """写入历史文件，失败时静默返回 False。"""
        try:
            atomic_write_json(self._history_path, self._data)
            return True
        except (IOError, OSError):
            return False

    def add(self, original: str, result: str, mode: str, prompt_name: str | None) -> bool:
        """添加历史记录，超出上限时删除最旧条目。"""
        entry = {
            'id': str(uuid.uuid4()),
            'timestamp': datetime.now().isoformat(timespec='seconds'),
            'mode': mode,
            'prompt_name': prompt_name,
            'original': original,
            'result': result,
        }
        previous = copy.deepcopy(self._data)
        self._data['entries'].append(entry)
        # 容量控制：超出时保留最新的 max_count 条
        if len(self._data['entries']) > self._max_count:
            self._data['entries'] = self._data['entries'][-self._max_count:]
        success = self._write()
        if success:
            self._revision += 1
        else:
            self._data = previous
        return success

    def get_all(self) -> list[dict]:
        """返回所有历史记录（按时间倒序）。"""
        entries = self._data.get('entries', [])
        # 倒序排列（最新在前）
        return copy.deepcopy(list(reversed(entries)))

    @property
    def revision(self) -> int:
        """Monotonic in-memory version for UI refresh checks."""
        return self._revision

    def set_max_count(self, max_count: int) -> bool:
        """更新容量并立即裁剪超出上限的旧记录。"""
        new_limit = max(1, int(max_count))
        previous_limit = self._max_count
        previous_entries = self._data.get('entries', [])
        self._max_count = new_limit
        if len(previous_entries) <= new_limit:
            return True

        self._data['entries'] = previous_entries[-new_limit:]
        if self._write():
            self._revision += 1
            return True

        self._max_count = previous_limit
        self._data['entries'] = previous_entries
        return False

    def delete(self, entry_id: str) -> bool:
        """根据 ID 删除指定条目。"""
        entries = self._data.get('entries', [])
        for i, entry in enumerate(entries):
            if entry.get('id') == entry_id:
                entries.pop(i)
                success = self._write()
                if success:
                    self._revision += 1
                else:
                    entries.insert(i, entry)
                return success
        return False

    def clear(self) -> bool:
        """清空所有历史记录。"""
        previous = self._data.get('entries', [])
        self._data['entries'] = []
        success = self._write()
        if success:
            self._revision += 1
        else:
            self._data['entries'] = previous
        return success

    def search(self, keyword: str) -> list[dict]:
        """全文搜索，匹配原文或结果内容（不区分大小写）。"""
        if not keyword:
            return self.get_all()
        keyword_lower = keyword.lower()
        entries = self._data.get('entries', [])
        matched = [
            e for e in entries
            if keyword_lower in e.get('original', '').lower()
            or keyword_lower in e.get('result', '').lower()
        ]
        return copy.deepcopy(list(reversed(matched)))

    def get_by_id(self, entry_id: str) -> dict | None:
        """根据 ID 获取单个条目。"""
        entries = self._data.get('entries', [])
        for entry in entries:
            if entry.get('id') == entry_id:
                return copy.deepcopy(entry)
        return None
