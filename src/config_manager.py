# 配置管理单例：读写 %APPDATA%/NeatCopy/config.json，支持嵌套键点号访问。
import json
import os
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = {
    'ui': {
        'theme': 'light',
    },
    'general': {
        'startup_with_windows': False,
        'toast_notification': True,
        'double_ctrl_c': {'enabled': False, 'interval_ms': 300},
        'custom_hotkey': {'enabled': True, 'keys': 'ctrl+shift+c'},
    },
    'rules': {
        'mode': 'rules',
        'merge_soft_newline': True,
        'keep_hard_newline': True,
        'merge_spaces': True,
        'smart_punctuation': True,
        'pangu_spacing': True,
        'trim_lines': True,
        'protect_code_blocks': True,
        'protect_lists': True,
    },
    'llm': {
        'enabled': False,
        'base_url': 'https://api.openai.com/v1',
        'api_key': '',
        'model_id': 'gpt-4o-mini',
        'temperature': 0.2,
        'active_prompt_id': 'default',
        'prompts': [
            {
                'id': 'default',
                'name': '格式清洗',
                'content': (
                    '你是一个文本格式整理助手。请整理以下文本的段落格式和标点符号，'
                    '保留原文所有文字内容，不增删任何内容，不修改任何措辞。'
                    '只修正格式问题：合并不必要的换行，保留真正的段落分隔，'
                    '修复标点符号使用。直接返回整理后的文本，不要任何解释。'
                ),
                'readonly': True,
                'visible_in_wheel': True,
            }
        ],
    },
    'wheel': {
        'enabled': True,
        'trigger_with_clean': True,
        'switch_hotkey': 'ctrl+shift+p',
        'last_prompt_id': None,
        'locked_prompt_id': None,
    },
    'preview': {
        'enabled': True,
        'hotkey': 'ctrl+q',
        'window_width': 320,
        'window_height': 200,
        'theme': 'dark',
    },
}


class ConfigManager:
    def __init__(self, config_dir: str | None = None):
        if config_dir is None:
            appdata = os.environ.get('APPDATA', str(Path.home()))
            config_dir = os.path.join(appdata, 'NeatCopy')
        self._config_path = Path(config_dir) / 'config.json'
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        if not self._config_path.exists():
            self._write(DEFAULT_CONFIG)
            return self._deep_copy(DEFAULT_CONFIG)
        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, ValueError):
            # 配置文件损坏，备份后重置为默认
            backup = self._config_path.with_suffix('.json.bak')
            self._config_path.rename(backup)
            self._write(DEFAULT_CONFIG)
            return self._deep_copy(DEFAULT_CONFIG)
        merged = self._merge_defaults(data, DEFAULT_CONFIG)
        # 旧配置兼容：为缺少 visible_in_wheel 的 prompt 自动补 True
        for p in merged.get('llm', {}).get('prompts', []):
            if 'visible_in_wheel' not in p:
                p['visible_in_wheel'] = True
        return merged

    def _deep_copy(self, obj):
        return json.loads(json.dumps(obj))

    def _merge_defaults(self, data: dict, defaults: dict) -> dict:
        result = self._deep_copy(defaults)
        for k, v in data.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = self._merge_defaults(v, result[k])
            else:
                result[k] = v
        return result

    def _write(self, data: dict) -> None:
        with open(self._config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """点号分隔的嵌套键访问，如 'general.toast_notification'。"""
        parts = key.split('.')
        node = self._data
        for part in parts:
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, key: str, value: Any) -> None:
        """设置值并立即写入磁盘。"""
        parts = key.split('.')
        node = self._data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
        self._write(self._data)

    def all(self) -> dict:
        return self._deep_copy(self._data)
