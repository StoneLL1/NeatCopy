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
    def test_default_prompt_exists(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        prompts = cm.get('llm.prompts')
        assert len(prompts) >= 1
        assert prompts[0]['id'] == 'default'

    def test_default_prompt_is_readonly(self, tmp_config_dir):
        cm = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        prompts = cm.get('llm.prompts')
        assert prompts[0]['readonly'] is True


class TestHistoryConfig:
    def test_default_history_config_exists(self, tmp_config_dir):
        """默认配置包含 history 组"""
        from config_manager import ConfigManager
        config = ConfigManager(config_dir=str(tmp_config_dir))
        assert config.get('history.enabled') is True
        assert config.get('history.max_count') == 500
        assert config.get('history.hotkey') == 'ctrl+h'
        assert config.get('history.window_width') == 600
        assert config.get('history.window_height') == 400

    def test_history_config_merge(self, tmp_config_dir):
        """旧配置文件自动补 history 默认值"""
        from config_manager import ConfigManager
        import json
        config_path = tmp_config_dir / 'NeatCopy' / 'config.json'
        config_path.parent.mkdir(parents=True, exist_ok=True)
        old_config = {'general': {'toast_notification': True}}
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(old_config, f)
        config = ConfigManager(config_dir=str(tmp_config_dir))
        assert config.get('history.enabled') is True
        assert config.get('history.max_count') == 500
