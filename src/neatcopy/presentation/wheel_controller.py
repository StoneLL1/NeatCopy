from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import AppKit
from PyQt6.QtCore import QObject, QPoint, QTimer
from PyQt6.QtGui import QCursor

from neatcopy.application.history_service import PasteHistoryItem, PasteHistoryService
from neatcopy.infrastructure.clipboard import ClipboardPayload, clear_clipboard, read_payload, write_payload
from neatcopy.infrastructure.config_manager import BUILTIN_PROMPTS, get_default_config_dir
from neatcopy.presentation.ui.radial_menu import RadialMenuItem, RadialMenuWindow


@dataclass
class _MenuState:
    kind: str
    title: str
    items: list[RadialMenuItem]
    source_payload: ClipboardPayload | None = None


def select_wheel_prompts(prompts: list[dict]) -> list[dict]:
    visible = [prompt for prompt in prompts if prompt.get('visible_in_wheel', True)]
    builtin_ids = {prompt['id'] for prompt in BUILTIN_PROMPTS}
    user_defined = [prompt for prompt in visible if prompt.get('id') not in builtin_ids]
    builtin_editable = [
        prompt for prompt in visible
        if prompt.get('id') in builtin_ids and prompt.get('id') != 'default'
    ]
    fallback = [prompt for prompt in visible if prompt.get('id') == 'default']
    return (user_defined + builtin_editable + fallback)[:3]


def build_history_menu_items(history: list[PasteHistoryItem]) -> list[RadialMenuItem]:
    items: list[RadialMenuItem] = []
    for index in range(5):
        if index < len(history):
            entry = history[index]
            items.append(
                RadialMenuItem(
                    f'history_item:{index}',
                    WheelController._shorten(entry.label, 26),
                    thumbnail_png_base64=entry.payload.image_png_base64 if entry.payload.is_image else None,
                )
            )
        else:
            items.append(RadialMenuItem(f'history_empty:{index}', '暂无记录', enabled=False))
    items.append(RadialMenuItem('back', '返回'))
    return items


class WheelController(QObject):
    def __init__(self, config, clip_processor, hotkey_manager, tray_manager, parent=None):
        super().__init__(parent)
        self._config = config
        self._clip_processor = clip_processor
        self._hotkey_manager = hotkey_manager
        self._tray_manager = tray_manager
        self._history = PasteHistoryService(config)
        self._window = RadialMenuWindow()
        self._window.action_selected.connect(self._on_action_selected)
        self._window.dismissed.connect(self._dismiss)
        self._stack: list[_MenuState] = []
        self._pending_auto_paste = False
        self._log_path = Path(get_default_config_dir()) / 'wheel.log'
        self._anchor_pos = QPoint()
        self._target_app = None

        self._clip_processor.process_done.connect(self._on_process_done)

    def open_for_paste(self):
        self._log('open_for_paste called')
        if not self._config.get('wheel.enabled', True):
            self._log('wheel disabled, fallback to system paste')
            self._hotkey_manager.trigger_system_paste()
            return

        payload = read_payload()
        if payload is None:
            self._log('clipboard empty/unavailable, fallback to system paste')
            self._hotkey_manager.trigger_system_paste()
            return

        self._pending_auto_paste = False
        self._anchor_pos = QCursor.pos()
        self._target_app = self._frontmost_app()
        self._stack = [self._build_root_menu(payload)]
        self._log(f'root menu ready kind={payload.kind}')
        self._show_current()

    def _build_root_menu(self, source_payload: ClipboardPayload) -> _MenuState:
        is_text = source_payload.is_text
        llm_enabled = True
        config = self.__dict__.get('_config')
        if config is not None:
            llm_enabled = bool(config.get('llm.enabled', False))
        return _MenuState(
            kind='root',
            title='粘贴',
            source_payload=source_payload,
            items=[
                RadialMenuItem('history', '历史记录'),
                RadialMenuItem('paste', '直接粘贴'),
                RadialMenuItem('rules', '规则清洗', enabled=is_text),
                RadialMenuItem('llm', '大模型处理', enabled=is_text and llm_enabled),
                RadialMenuItem('clear_clipboard', '删除内容'),
            ],
        )

    def _build_history_menu(self) -> _MenuState:
        history = self._history.list_entries()
        return _MenuState(kind='history', title='历史', items=build_history_menu_items(history))

    def _build_history_action_menu(self, source_payload: ClipboardPayload) -> _MenuState:
        is_text = source_payload.is_text
        llm_enabled = True
        config = self.__dict__.get('_config')
        if config is not None:
            llm_enabled = bool(config.get('llm.enabled', False))
        return _MenuState(
            kind='history_action',
            title='操作',
            source_payload=source_payload,
            items=[
                RadialMenuItem('paste_selected', '直接粘贴'),
                RadialMenuItem('delete_selected', '删除记录'),
                RadialMenuItem('back', '返回'),
                RadialMenuItem('rules_selected', '规则清洗', enabled=is_text),
                RadialMenuItem('llm_selected', '大模型处理', enabled=is_text and llm_enabled),
            ],
        )

    def _build_llm_menu(self, source_payload: ClipboardPayload, title: str) -> _MenuState:
        prompts = self._get_wheel_prompts()
        items = [RadialMenuItem(f'prompt:{prompt["id"]}', prompt['name']) for prompt in prompts[:3]]
        while len(items) < 3:
            items.append(RadialMenuItem(f'prompt_empty:{len(items)}', '暂无模板', enabled=False))
        items.append(RadialMenuItem('back', '返回'))
        return _MenuState(kind='llm', title=title, items=items, source_payload=source_payload)

    def _get_wheel_prompts(self) -> list[dict]:
        return select_wheel_prompts(self._config.get('llm.prompts', []) or [])

    def _show_current(self):
        if not self._stack:
            self._window.hide()
            return
        state = self._stack[-1]
        self._log(f'show menu kind={state.kind} title={state.title} items={len(state.items)}')
        self._window.show_menu(state.items, state.title, self._anchor_pos)

    def _on_action_selected(self, action_id: str):
        state = self._stack[-1]

        if action_id == 'back':
            if len(self._stack) > 1:
                self._stack.pop()
                self._show_current()
            else:
                self._dismiss()
            return

        if state.kind == 'root':
            self._handle_root_action(action_id, state.source_payload)
            return
        if state.kind == 'history':
            self._handle_history_action(action_id)
            return
        if state.kind == 'history_action':
            self._handle_selected_payload_action(action_id, state.source_payload, llm_title='模型')
            return
        if state.kind == 'llm':
            self._handle_llm_action(action_id, state.source_payload)

    def _handle_root_action(self, action_id: str, source_payload: ClipboardPayload | None):
        if source_payload is None:
            return
        if action_id == 'history':
            self._stack.append(self._build_history_menu())
            self._show_current()
            return
        if action_id == 'clear_clipboard':
            clear_clipboard()
            self._dismiss()
            self._tray_manager.show_info('剪贴板已清空')
            return
        if action_id == 'llm':
            self._stack.append(self._build_llm_menu(source_payload, '模型'))
            self._show_current()
            return
        self._handle_selected_payload_action(action_id, source_payload, llm_title='模型')

    def _handle_history_action(self, action_id: str):
        if not action_id.startswith('history_item:'):
            return
        index = int(action_id.split(':', 1)[1])
        history = self._history.list_entries()
        if index >= len(history):
            return
        self._stack.append(self._build_history_action_menu(history[index].payload))
        self._show_current()

    def _handle_selected_payload_action(self, action_id: str, source_payload: ClipboardPayload | None, llm_title: str):
        if source_payload is None:
            return
        if action_id in {'paste', 'paste_selected'}:
            self._history.add_payload(source_payload)
            write_payload(source_payload)
            self._dismiss()
            self._paste_to_target_app()
            return
        if action_id == 'delete_selected':
            if len(self._stack) >= 2 and self._stack[-2].kind == 'history':
                self._history.delete_payload(source_payload)
                self._stack.pop()
                self._stack[-1] = self._build_history_menu()
                self._show_current()
                self._tray_manager.show_info('历史记录已删除')
            return
        if action_id in {'rules', 'rules_selected'}:
            if not source_payload.is_text:
                return
            self._history.add_payload(source_payload)
            self._pending_auto_paste = True
            self._dismiss()
            self._clip_processor.process_text(source_payload.text or '', mode='rules')
            return
        if action_id in {'llm', 'llm_selected'}:
            if not source_payload.is_text:
                return
            self._stack.append(self._build_llm_menu(source_payload, llm_title))
            self._show_current()

    def _handle_llm_action(self, action_id: str, source_payload: ClipboardPayload | None):
        if source_payload is None or not source_payload.is_text:
            return
        if not action_id.startswith('prompt:'):
            return
        prompt_id = action_id.split(':', 1)[1]
        self._history.add_payload(source_payload)
        self._pending_auto_paste = True
        self._dismiss()
        self._clip_processor.process_text(source_payload.text or '', mode='llm', prompt_id=prompt_id)

    def _on_process_done(self, success: bool, _message: str):
        if not self._pending_auto_paste:
            return
        should_paste = success
        self._pending_auto_paste = False
        if should_paste:
            self._paste_to_target_app()

    def _dismiss(self):
        self._stack.clear()
        self._window.hide()
        self._anchor_pos = QPoint()
        self._log('menu dismissed')

    @staticmethod
    def _shorten(text: str, limit: int) -> str:
        stripped = ' '.join(text.split())
        if len(stripped) <= limit:
            return stripped
        return stripped[: limit - 1] + '…'

    def _log(self, message: str):
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._log_path, 'a', encoding='utf-8') as f:
                f.write(message.rstrip() + '\n')
        except Exception:
            pass

    def _frontmost_app(self):
        workspace = AppKit.NSWorkspace.sharedWorkspace()
        app = workspace.frontmostApplication()
        if app is not None:
            self._log(f'frontmost app={app.bundleIdentifier() or "unknown"}')
        return app

    def _paste_to_target_app(self):
        target = self._target_app
        if target is not None:
            try:
                target.activateWithOptions_(
                    AppKit.NSApplicationActivateIgnoringOtherApps
                )
                self._log(f'reactivate target app={target.bundleIdentifier() or "unknown"}')
            except Exception as exc:
                self._log(f'reactivate failed: {exc}')
        QTimer.singleShot(80, self._hotkey_manager.trigger_system_paste)
