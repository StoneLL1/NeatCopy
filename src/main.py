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

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QCursor, QIcon
from assets import asset as _asset
from config_manager import ConfigManager
from autostart_manager import sync_from_config
from tray_manager import TrayManager
from hotkey_manager import HotkeyManager
from clip_processor import ClipProcessor
from history_manager import HistoryManager


def create_preview_state() -> dict:
    return {
        'status': 'idle',
        'message': '等待处理',
        'result': '',
        'prompt_name': '',
        'error': '',
    }


def record_preview_processing(state: dict) -> None:
    state['status'] = 'processing'
    state['message'] = '处理中...'
    state['error'] = ''


def record_preview_ready(state: dict, result: str, prompt_name: str) -> None:
    state['status'] = 'done'
    state['message'] = '处理完成'
    state['result'] = result
    state['prompt_name'] = prompt_name
    state['error'] = ''


def record_preview_failed(state: dict, error: str) -> None:
    state['status'] = 'failed'
    state['message'] = f'处理失败: {error}'
    state['error'] = error


def replay_preview_state(preview, state: dict) -> None:
    if state.get('result'):
        preview.update_result(state.get('result', ''), state.get('prompt_name', ''))
    if state.get('status') in {'processing', 'failed'}:
        preview.set_status(state.get('message', '等待处理'))


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
    wheel = None
    preview = None
    history_win = None
    settings_win = None
    preview_state = create_preview_state()

    def ensure_wheel():
        nonlocal wheel
        if wheel is None:
            from wheel_window import WheelWindow
            wheel = WheelWindow()
        return wheel

    def ensure_preview():
        nonlocal preview
        if preview is None:
            from ui.preview_window import PreviewWindow
            preview = PreviewWindow(config)
            preview.apply_to_clipboard.connect(
                lambda text: processor.write_to_clipboard(text))
            replay_preview_state(preview, preview_state)
        return preview

    def ensure_history_window():
        nonlocal history_win
        if history_win is None:
            from ui.history_window import HistoryWindow
            history_win = HistoryWindow(config, history)
            history_win.copy_to_clipboard.connect(
                lambda text: processor.write_to_clipboard(text))
        return history_win

    def ensure_settings_window():
        nonlocal settings_win
        if settings_win is None:
            from ui.settings_window import SettingsWindow
            settings_win = SettingsWindow(config, hotkey_manager=hotkey)
        return settings_win

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

    def mark_history_dirty_after_success(success: bool, message: str):
        if success and history_win is not None:
            history_win.mark_dirty()

    processor.process_done.connect(mark_history_dirty_after_success)

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

                ensure_wheel().show_at(pos, visible, on_wheel_selected, last_id)
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

        ensure_wheel().show_at(pos, visible, on_lock_selected, locked_id)

    hotkey.wheel_hotkey_triggered.connect(on_wheel_hotkey_triggered)

    # ── 预览面板信号连接 ───────────────────────────────────────
    def on_preview_hotkey_triggered():
        ensure_preview().toggle_visibility()

    def on_processing_started():
        if config.get('rules.mode', 'rules') != 'llm':
            return
        record_preview_processing(preview_state)
        if preview is not None:
            replay_preview_state(preview, preview_state)

    def on_preview_ready(result: str, prompt_name: str):
        record_preview_ready(preview_state, result, prompt_name)
        if preview is not None:
            replay_preview_state(preview, preview_state)

    def on_preview_failed(error: str):
        record_preview_failed(preview_state, error)
        if preview is not None:
            replay_preview_state(preview, preview_state)

    hotkey.preview_hotkey_triggered.connect(on_preview_hotkey_triggered)
    processor.processing_started.connect(on_processing_started)
    processor.preview_ready.connect(on_preview_ready)
    processor.preview_failed.connect(on_preview_failed)

    # ── 历史记录信号连接 ─────────────────────────────────────────
    def toggle_history_window():
        ensure_history_window().toggle_visibility()

    hotkey.history_hotkey_triggered.connect(toggle_history_window)
    tray.open_history_requested.connect(toggle_history_window)

    # ── 初始化托盘锁定状态显示 ───────────────────────────────
    locked_id = config.get('wheel.locked_prompt_id')
    if locked_id:
        prompts = config.get('llm.prompts') or []
        locked_name = next((p['name'] for p in prompts if p['id'] == locked_id), None)
        tray.update_locked_prompt(locked_name)

    def on_open_settings():
        win = ensure_settings_window()
        if win.isVisible():
            win.hide()
        else:
            win.show()
            win.raise_()
            win.activateWindow()

    tray.open_settings_requested.connect(on_open_settings)

    QTimer.singleShot(0, ensure_preview)
    QTimer.singleShot(200, ensure_wheel)

    sys.exit(app.exec())


if __name__ == '__main__':
    try:
        main()
    except Exception:
        log_path = _setup_logging()
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(traceback.format_exc())
        raise
