import sys
import os
import traceback
import ctypes
sys.path.insert(0, os.path.dirname(__file__))

# 设置 AppUserModelID，让 Windows 任务栏显示应用图标而非 Python 图标
# （不设置时 Python 进程继承 python.exe 的 AUMID，任务栏显示 Python 默认图标）
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('NeatCopy.App')
except (AttributeError, OSError):
    pass


def _setup_logging():
    """崩溃时写 crash.log，方便冻结模式无 console 时排查问题。"""
    log_dir = os.path.join(os.environ.get('APPDATA', '.'), 'NeatCopy')
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, 'crash.log')

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QCursor, QIcon
from assets import asset as _asset
from config_manager import ConfigManager
from tray_manager import TrayManager
from hotkey_manager import HotkeyManager
from clip_processor import ClipProcessor
from wheel_window import WheelWindow
from ui.settings_window import SettingsWindow


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName('NeatCopy')
    app.setWindowIcon(QIcon(_asset('idle.ico')))  # 应用级别图标

    config = ConfigManager()
    tray = TrayManager(config)
    hotkey = HotkeyManager(config)
    processor = ClipProcessor(config)
    wheel = WheelWindow()

    tray.quit_requested.connect(app.quit)
    tray.pause_toggled.connect(hotkey.set_paused)

    def on_locked_prompt_changed(pid: str):
        config.set('wheel.locked_prompt_id', pid or None)
        if pid:
            prompts = config.get('llm.prompts') or []
            name = next((p['name'] for p in prompts if p['id'] == pid), None)
        else:
            name = None
        tray.update_locked_prompt(name)

    tray.locked_prompt_changed.connect(on_locked_prompt_changed)

    processor.processing_started.connect(tray.set_processing)

    def on_process_done(success: bool, message: str):
        toast_enabled = config.get('general.toast_notification', True)
        if success:
            tray.set_success(toast_enabled=toast_enabled, message=message)
        else:
            tray.set_error(message=message, toast_enabled=toast_enabled)

    processor.process_done.connect(on_process_done)

    # ── 清洗热键触发逻辑 ──────────────────────────────────────
    def on_hotkey_triggered():
        mode = config.get('rules.mode', 'rules')
        wheel_cfg = config.get('wheel') or {}
        wheel_enabled = wheel_cfg.get('enabled', True)
        trigger_with_clean = wheel_cfg.get('trigger_with_clean', True)

        if mode == 'llm' and wheel_enabled and trigger_with_clean:
            visible = processor.get_visible_prompts()
            if len(visible) == 0:
                return  # 静默不处理
            elif len(visible) == 1:
                # 跳过轮盘直接执行
                processor.process_with_prompt(visible[0]['id'])
                config.set('wheel.last_prompt_id', visible[0]['id'])
            else:
                last_id = wheel_cfg.get('last_prompt_id')
                pos = QCursor.pos()

                def on_wheel_selected(pid: str):
                    config.set('wheel.last_prompt_id', pid)
                    processor.process_with_prompt(pid)

                wheel.show_at(pos, visible, on_wheel_selected, last_id)
        else:
            processor.process()

    hotkey.hotkey_triggered.connect(on_hotkey_triggered)

    # ── 轮盘切换热键（锁定模式） ─────────────────────────────
    def on_wheel_hotkey_triggered():
        wheel_cfg = config.get('wheel') or {}
        if not wheel_cfg.get('enabled', True):
            return
        visible = processor.get_visible_prompts()
        if not visible:
            return
        pos = QCursor.pos()
        locked_id = wheel_cfg.get('locked_prompt_id')

        def on_lock_selected(pid: str):
            config.set('wheel.locked_prompt_id', pid)
            name = next((p['name'] for p in visible if p['id'] == pid), None)
            tray.update_locked_prompt(name)

        wheel.show_at(pos, visible, on_lock_selected, locked_id)

    hotkey.wheel_hotkey_triggered.connect(on_wheel_hotkey_triggered)

    # ── 初始化托盘锁定状态显示 ───────────────────────────────
    locked_id = config.get('wheel.locked_prompt_id')
    if locked_id:
        prompts = config.get('llm.prompts') or []
        locked_name = next((p['name'] for p in prompts if p['id'] == locked_id), None)
        tray.update_locked_prompt(locked_name)

    settings_win = SettingsWindow(config, hotkey_manager=hotkey)

    def on_open_settings():
        if settings_win.isVisible():
            settings_win.hide()
        else:
            settings_win.show()
            settings_win.raise_()
            settings_win.activateWindow()

    tray.open_settings_requested.connect(on_open_settings)

    sys.exit(app.exec())


if __name__ == '__main__':
    try:
        main()
    except Exception:
        log_path = _setup_logging()
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(traceback.format_exc())
        raise
