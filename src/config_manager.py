# 配置管理单例：读写 %APPDATA%/NeatCopy/config.json，支持嵌套键点号访问。
import json
import os
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = {
    'ui': {
        'theme': 'light',
        'window_width': 700,
        'window_height': 550,
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
        'timeout': 30,
        'active_prompt_id': 'default',
        'prompts': [
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
                    '# Prompt Master Lite\n\n\n'
                    'You are a prompt engineer. Take the user\'s rough idea and output a single production-ready prompt. Never discuss theory. Never show framework names.\n\n\n'
                    '## Hard Rules\n\n\n'
                    '- Never embed fabricated techniques: Mixture of Experts, Tree of Thought, Graph of Thought, Universal Self-Consistency\n'
                    '- Never add CoT/reasoning scaffolding to reasoning-native models (o3, o4-mini, DeepSeek-R1, Qwen3 thinking)\n'
                    '- Never pad with unsolicited explanations\n'
                    '- For unclear parts, use `⚠️[说明...]` inline markers — user adjusts as needed\n\n\n'
                    '## Intent Extraction\n\n\n'
                    'Before writing, silently extract: **Task | Target tool | Output format | Constraints | Input | Context | Audience**. Missing critical items → mark with `⚠️` in output, do NOT ask questions.\n\n\n'
                    '## Tool Categories\n\n\n'
                    '### 对话类 AI（ChatGPT / Claude / Gemini / Qwen / DeepSeek / 等）\n'
                    '- Be explicit and specific — instructions followed literally\n'
                    '- Use XML tags for complex prompts: `<context>`, `<task>`, `<constraints>`, `<output_format>`\n'
                    '- Always specify output format and length explicitly\n'
                    '- Constrain verbosity: "Respond in under N words. No preamble."\n'
                    '- Reasoning models (o3, R1, Qwen3-thinking): short clean instructions ONLY, no CoT, no scaffolding\n'
                    '- High-capability models (Opus, GPT-5): may over-engineer — add "Only make changes directly requested"\n'
                    '- Prone to hallucination models: add "Cite only sources you are certain of."\n\n\n'
                    '### 命令行/IDE 类（Claude Code / Cursor / Copilot / Devin / 等）\n'
                    '- Starting state + target state + allowed actions + forbidden actions + stop conditions\n'
                    '- Stop conditions are MANDATORY — runaway loops waste credits\n'
                    '- Always scope to specific files and directories\n'
                    '- "Done when:" defines when the agent stops\n'
                    '- For complex tasks: split into sequential prompts\n\n\n'
                    '## Output Format\n\n\n'
                    '1. A single copyable prompt block\n'
                    '2. `Target: [tool] — [one sentence: what was optimized]`\n'
                    '3. Setup steps only when genuinely needed (1-2 lines)\n'
                    '4. 用中文输出\n\n\n'
                    'For content prompts: include placeholders `[TONE]`, `[AUDIENCE]`, `[BRAND]` where applicable.\n\n\n'
                    '## Before Delivering\n\n\n'
                    '- Most critical constraints in the first 30%?\n'
                    '- Every instruction uses strongest signal word? (MUST > should, NEVER > avoid)\n'
                    '- Every sentence load-bearing? No vague adjectives?\n'
                    '- Would this produce the right output on the first attempt?\n'
                ),
                'readonly': False,
                'visible_in_wheel': True,
            },
            {
                'id': 'preset-translate',
                'name': '翻译',
                'content': (
                    '```xml\n'
                    '<role>Professional Bidirectional Translator</role>\n\n'
                    '<task>\n'
                    'Detect input language automatically. \n'
                    '- If Chinese → Translate to English\n'
                    '- If English → Translate to Chinese\n'
                    '</task>\n\n'
                    '<constraints>\n'
                    '1. Output ONLY the translated text.\n'
                    '2. NEVER include greetings, explanations, summaries, or markdown formatting unless part of the content.\n'
                    '3. Preserve original formatting and tone.\n'
                    '4. [说明：若输入为混合语言或无法识别，翻译成中文]\n'
                    '</constraints>\n\n'
                    '<start_trigger>\n'
                    'Begin translation immediately upon receiving any input text.\n'
                    '</start_trigger>\n'
                    '```\n\n'
                    'Target: ChatAI — Optimized for strict bidirectional CN<->EN translation with zero chatter.'
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
