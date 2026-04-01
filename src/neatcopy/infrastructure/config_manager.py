from __future__ import annotations

# 配置管理单例：读写 ~/Library/Application Support/NeatCopy/config.json，支持嵌套键点号访问。
import json
import os
from pathlib import Path
from typing import Any

APP_NAME = 'NeatCopy'


def get_default_hotkey() -> str:
    return 'cmd+alt+v'


def get_default_clear_hotkey() -> str:
    return 'cmd+alt+k'


def get_default_config_dir() -> str:
    return os.path.join(str(Path.home()), 'Library', 'Application Support', APP_NAME)


BUILTIN_PROMPTS = [
    {
        'id': 'default',
        'name': '格式清洗',
        'content': (
            '你是一个文本格式整理助手。请整理以下文本的段落格式和标点符号，'
            '保留原文所有文字内容，不改变中英文，不增删任何内容，不修改任何措辞。'
            '只修正格式问题：合并不必要的换行，保留真正的段落分隔，'
            '统一全角半角标点，英文和数字统一半角，修复标点符号使用。'
            '你要做的只有一件事：直接返回整理后的文本，不要任何解释。'
        ),
        'readonly': True,
        'visible_in_wheel': True,
    },
    {
        'id': 'preset-prompt-master',
        'name': 'PromptMaster',
        'content': (
            '# Prompt Master Lite\n\n'
            'You are a prompt engineer. Take the user\'s rough idea and output a single '
            'production-ready prompt. Never discuss theory. Never show framework names.\n\n'
            '## Hard Rules\n'
            '- Never embed fabricated techniques.\n'
            '- Never add chain-of-thought scaffolding to reasoning-native models.\n'
            '- Never pad with unsolicited explanations.\n'
            '- For unclear parts, use `⚠️[说明...]` inline markers.\n\n'
            '## Intent Extraction\n'
            'Silently extract: Task | Target tool | Output format | Constraints | Input | '
            'Context | Audience. Missing critical items should be marked inline.\n\n'
            '## Output Rule\n'
            'Return one production-ready prompt only. No preamble.'
        ),
        'readonly': False,
        'visible_in_wheel': True,
    },
    {
        'id': 'preset-translate',
        'name': '翻译',
        'content': (
            '<task>\n'
            'Detect input language automatically.\n'
            '- If Chinese, translate to English.\n'
            '- If English, translate to Chinese.\n'
            '</task>\n\n'
            '<constraints>\n'
            '1. Output only the translated text.\n'
            '2. Preserve original formatting and tone.\n'
            '3. If the input language is mixed or unclear, translate to Chinese.\n'
            '</constraints>'
        ),
        'readonly': False,
        'visible_in_wheel': True,
    },
    {
        'id': 'preset-ask',
        'name': '随时提问',
        'content': '根据我的提问提供简短的回答，给出纯文本的答案',
        'readonly': False,
        'visible_in_wheel': True,
    },
]


DEFAULT_CONFIG = {
    'general': {
        'startup_with_windows': False,
        'toast_notification': True,
        'double_ctrl_c': {'enabled': False, 'interval_ms': 300},
        'custom_hotkey': {'enabled': True, 'keys': get_default_hotkey()},
        'clear_clipboard_hotkey': {'enabled': False, 'keys': get_default_clear_hotkey()},
    },
    'wheel': {
        'enabled': True,
    },
    'history': {
        'items': [],
        'max_items': 10,
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
        'timeout': 30,
        'active_prompt_id': 'default',
        'prompts': BUILTIN_PROMPTS,
    },
}


class ConfigManager:
    def __init__(self, config_dir: str | None = None):
        if config_dir is None:
            config_dir = get_default_config_dir()
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
        clear_hotkey = merged.get('general', {}).get('clear_clipboard_hotkey', {})
        if clear_hotkey.get('keys') == 'cmd+alt+backspace':
            clear_hotkey['keys'] = get_default_clear_hotkey()
        merged['llm']['prompts'] = self._normalize_prompts(merged.get('llm', {}).get('prompts'))
        active_id = merged.get('llm', {}).get('active_prompt_id', 'default')
        prompt_ids = {prompt['id'] for prompt in merged['llm']['prompts']}
        if active_id not in prompt_ids:
            merged['llm']['active_prompt_id'] = 'default'
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

    def _normalize_prompts(self, prompts: list[dict] | None) -> list[dict]:
        normalized: list[dict] = []
        existing_by_id = {
            prompt.get('id'): prompt
            for prompt in (prompts or [])
            if isinstance(prompt, dict) and prompt.get('id')
        }

        for builtin in BUILTIN_PROMPTS:
            existing = existing_by_id.pop(builtin['id'], None)
            merged = self._deep_copy(builtin)
            if existing:
                if 'visible_in_wheel' in existing:
                    merged['visible_in_wheel'] = bool(existing['visible_in_wheel'])
            normalized.append(merged)

        for prompt in prompts or []:
            if not isinstance(prompt, dict):
                continue
            if prompt.get('id') in {builtin['id'] for builtin in BUILTIN_PROMPTS}:
                continue
            custom_prompt = self._deep_copy(prompt)
            custom_prompt.setdefault('readonly', False)
            custom_prompt.setdefault('visible_in_wheel', True)
            normalized.append(custom_prompt)

        return normalized

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
        self.update_many({key: value})

    def update_many(self, updates: dict[str, Any]) -> None:
        """批量设置多个值，并在最后统一写入磁盘。"""
        if not updates:
            return
        for key, value in updates.items():
            parts = key.split('.')
            node = self._data
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = value
        self._write(self._data)

    def all(self) -> dict:
        return self._deep_copy(self._data)
