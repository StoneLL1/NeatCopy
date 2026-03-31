# src/history_manager.py
"""历史记录数据管理：读写 history.json，增删查接口。"""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


class HistoryManager:
    """历史记录管理器，负责读写 history.json 文件。"""

    def __init__(self, config_dir: str | None = None, max_count: int = 500):
        if config_dir is None:
            config_dir = os.environ.get('APPDATA', str(Path.home()))
        self._history_path = Path(config_dir) / 'NeatCopy' / 'history.json'
        self._history_path.parent.mkdir(parents=True, exist_ok=True)
        self._max_count = max_count
        self._data = self._load()

    def _load(self) -> dict:
        """加载历史文件，不存在或损坏时返回空结构。"""
        if not self._history_path.exists():
            return {'entries': []}
        try:
            with open(self._history_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if 'entries' not in data or not isinstance(data['entries'], list):
                return {'entries': []}
            return data
        except (json.JSONDecodeError, ValueError, IOError):
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
            with open(self._history_path, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
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
        self._data['entries'].append(entry)
        # 容量控制：超出时保留最新的 max_count 条
        if len(self._data['entries']) > self._max_count:
            self._data['entries'] = self._data['entries'][-self._max_count:]
        return self._write()

    def get_all(self) -> list[dict]:
        """返回所有历史记录（按时间倒序）。"""
        entries = self._data.get('entries', [])
        # 倒序排列（最新在前）
        return list(reversed(entries))

    def set_max_count(self, max_count: int):
        """更新最大条数上限。"""
        self._max_count = max_count

    def delete(self, entry_id: str) -> bool:
        """根据 ID 删除指定条目。"""
        entries = self._data.get('entries', [])
        for i, entry in enumerate(entries):
            if entry.get('id') == entry_id:
                entries.pop(i)
                return self._write()
        return False

    def clear(self) -> bool:
        """清空所有历史记录。"""
        self._data['entries'] = []
        return self._write()

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
        return list(reversed(matched))

    def get_by_id(self, entry_id: str) -> dict | None:
        """根据 ID 获取单个条目。"""
        entries = self._data.get('entries', [])
        for entry in entries:
            if entry.get('id') == entry_id:
                return entry
        return None