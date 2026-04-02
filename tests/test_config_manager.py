import os
import json
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from neatcopy.infrastructure.config_manager import BUILTIN_PROMPTS, ConfigManager


class TestConfigManagerDefaults:
    def test_creates_config_file_on_first_load(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        config_path = tmp_config_dir / 'NeatCopy' / 'config.json'
        assert config_path.exists()

    def test_default_toast_notification_is_true(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        assert cm.get('general.toast_notification') is True

    def test_default_mode_is_rules(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        assert cm.get('rules.mode') == 'rules'

    def test_default_llm_enabled_is_false(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        assert cm.get('llm.enabled') is False

    def test_default_timeout_is_30_seconds(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        assert cm.get('llm.timeout') == 30

    def test_default_clear_clipboard_hotkey_is_disabled(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        assert cm.get('general.clear_clipboard_hotkey.enabled') is False
        assert cm.get('general.clear_clipboard_hotkey.keys') == 'cmd+alt+k'


class TestConfigManagerGetSet:
    def test_set_persists_to_disk(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        cm.set('general.toast_notification', False)
        cm2 = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        assert cm2.get('general.toast_notification') is False

    def test_get_nested_key(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        val = cm.get('general.double_ctrl_c.interval_ms')
        assert val == 300

    def test_set_nested_key(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        cm.set('general.double_ctrl_c.interval_ms', 500)
        assert cm.get('general.double_ctrl_c.interval_ms') == 500

    def test_get_nonexistent_key_returns_none(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        assert cm.get('nonexistent.key') is None

    def test_get_nonexistent_key_returns_default(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        assert cm.get('nonexistent.key', default='fallback') == 'fallback'

    def test_update_many_persists_in_one_write_path(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        cm.update_many({
            'general.toast_notification': False,
            'general.double_ctrl_c.interval_ms': 450,
        })
        cm2 = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        assert cm2.get('general.toast_notification') is False
        assert cm2.get('general.double_ctrl_c.interval_ms') == 450


class TestConfigManagerCorruptedFile:
    """C3 回归测试：损坏的 config.json 应回退到默认配置。"""

    def test_corrupted_json_falls_back_to_defaults(self, tmp_config_dir):
        cfg_dir = tmp_config_dir / 'NeatCopy'
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_file = cfg_dir / 'config.json'
        cfg_file.write_text('{corrupted json!!!', encoding='utf-8')
        cm = ConfigManager(config_dir=str(cfg_dir))
        assert cm.get('general.toast_notification') is True
        assert cm.get('rules.mode') == 'rules'

    def test_corrupted_json_creates_backup(self, tmp_config_dir):
        cfg_dir = tmp_config_dir / 'NeatCopy'
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_file = cfg_dir / 'config.json'
        cfg_file.write_text('{bad}', encoding='utf-8')
        ConfigManager(config_dir=str(cfg_dir))
        assert (cfg_dir / 'config.json.bak').exists()

    def test_empty_file_falls_back_to_defaults(self, tmp_config_dir):
        cfg_dir = tmp_config_dir / 'NeatCopy'
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_file = cfg_dir / 'config.json'
        cfg_file.write_text('', encoding='utf-8')
        cm = ConfigManager(config_dir=str(cfg_dir))
        assert cm.get('general.toast_notification') is True


class TestConfigManagerAllReturnsCopy:
    """H2 回归测试：all() 返回深拷贝，外部修改不影响内部状态。"""

    def test_all_returns_copy(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        data = cm.all()
        data['general']['toast_notification'] = 'MUTATED'
        assert cm.get('general.toast_notification') is True


class TestConfigManagerPrompts:
    def test_builtin_prompts_exist(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        prompts = cm.get('llm.prompts')
        prompt_ids = [prompt['id'] for prompt in prompts]
        assert prompt_ids[:4] == [prompt['id'] for prompt in BUILTIN_PROMPTS]

    def test_default_prompt_is_readonly(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        prompts = cm.get('llm.prompts')
        assert prompts[0]['readonly'] is True

    def test_existing_config_is_migrated_with_missing_builtin_prompts(self, tmp_config_dir):
        cfg_dir = tmp_config_dir / 'NeatCopy'
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_file = cfg_dir / 'config.json'
        cfg_file.write_text(json.dumps({
            'llm': {
                'active_prompt_id': 'default',
                'prompts': [{'id': 'default', 'name': '旧默认', 'content': '旧内容', 'readonly': True}],
            }
        }, ensure_ascii=False), encoding='utf-8')

        cm = ConfigManager(config_dir=str(cfg_dir))

        prompts = cm.get('llm.prompts')
        prompt_ids = [prompt['id'] for prompt in prompts]
        assert prompt_ids[:4] == [prompt['id'] for prompt in BUILTIN_PROMPTS]
        assert cm.get('llm.timeout') == 30

    def test_migrates_old_clear_clipboard_hotkey_default(self, tmp_config_dir):
        cfg_dir = tmp_config_dir / 'NeatCopy'
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_file = cfg_dir / 'config.json'
        cfg_file.write_text(json.dumps({
            'general': {
                'clear_clipboard_hotkey': {
                    'enabled': False,
                    'keys': 'cmd+alt+backspace',
                }
            }
        }, ensure_ascii=False), encoding='utf-8')

        cm = ConfigManager(config_dir=str(cfg_dir))

        assert cm.get('general.clear_clipboard_hotkey.keys') == 'cmd+alt+k'
