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


def _check_single_instance():
    """检查是否已有实例运行，使用 Windows 命名互斥体。

    Returns:
        tuple: (mutex_handle, is_duplicate) - is_duplicate 为 True 表示已有实例
    """
    mutex_name = "NeatCopy_SingleInstance_Mutex"
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
    last_error = ctypes.windll.kernel32.GetLastError()
    is_duplicate = (last_error == 183)  # ERROR_ALREADY_EXISTS
    return mutex, is_duplicate


def _setup_logging():
    """崩溃时写 crash.log，方便冻结模式无 console 时排查问题。"""
    log_dir = os.path.join(os.environ.get('APPDATA', '.'), 'NeatCopy')
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, 'crash.log')

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QCursor, QIcon
from assets import asset as _asset
from config_manager import ConfigManager
from autostart_manager import sync_from_config
from tray_manager import TrayManager
from hotkey_manager import HotkeyManager
from clip_processor import ClipProcessor
from wheel_window import WheelWindow
from ui.settings_window import SettingsWindow
from ui.preview_window import PreviewWindow
from ui.history_window import HistoryWindow
from history_manager import HistoryManager


def main():
    # 单实例检测（先检测，弹窗放在 QApplication 创建后）
    _mutex, is_duplicate = _check_single_instance()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName('NeatCopy')
    app.setWindowIcon(QIcon(_asset('idle.ico')))  # 应用级别图标

    if is_duplicate:
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.warning(None, 'NeatCopy', 'NeatCopy 已在运行中，请检查系统托盘。')
        sys.exit(1)

    config = ConfigManager()
    # 初始化历史管理器
    history = HistoryManager(
        max_count=config.get('history.max_count', 500)
    )
    # 同步开机自启动注册表状态
    sync_from_config(config.get('general.startup_with_windows', False))
    tray = TrayManager(config)
    hotkey = HotkeyManager(config)
    processor = ClipProcessor(config, history_manager=history)
    wheel = WheelWindow()
    preview = PreviewWindow(config)
    history_win = HistoryWindow(config, history)

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

    # ── 预览面板信号连接 ───────────────────────────────────────
    hotkey.preview_hotkey_triggered.connect(preview.toggle_visibility)
    processor.processing_started.connect(
        lambda: preview.set_status("处理中...") if preview.isVisible() else None)
    processor.preview_ready.connect(
        lambda result, prompt_name: preview.update_result(result, prompt_name))
    processor.preview_failed.connect(
        lambda error: preview.set_status(f"处理失败: {error}"))
    preview.apply_to_clipboard.connect(
        lambda text: processor.write_to_clipboard(text))

    # ── 历史记录信号连接 ─────────────────────────────────────────
    hotkey.history_hotkey_triggered.connect(history_win.toggle_visibility)
    tray.open_history_requested.connect(history_win.toggle_visibility)
    history_win.copy_to_clipboard.connect(
        lambda text: processor.write_to_clipboard(text))

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
