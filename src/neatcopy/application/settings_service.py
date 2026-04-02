from neatcopy.infrastructure.startup_manager import StartupManager


class SettingsService:
    """统一处理设置保存后的副作用，避免 UI 直接操作基础设施。"""

    def __init__(self, config, hotkey_manager=None, startup_manager=None):
        self._config = config
        self._hotkey_manager = hotkey_manager
        self._startup_manager = startup_manager or StartupManager()

    def apply_updates(self, updates: dict) -> None:
        self._config.update_many(updates)
        self._startup_manager.apply(
            bool(self._config.get('general.startup_with_windows', False))
        )
        if self._hotkey_manager:
            self._hotkey_manager.reload_config(self._config)
