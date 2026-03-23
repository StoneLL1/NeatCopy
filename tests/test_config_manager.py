import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config_manager import ConfigManager


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


class TestConfigManagerPrompts:
    def test_default_prompt_exists(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        prompts = cm.get('llm.prompts')
        assert len(prompts) >= 1
        assert prompts[0]['id'] == 'default'

    def test_default_prompt_is_readonly(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        prompts = cm.get('llm.prompts')
        assert prompts[0]['readonly'] is True
