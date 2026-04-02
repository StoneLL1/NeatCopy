import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from neatcopy.infrastructure.config_manager import ConfigManager
from neatcopy.infrastructure.clipboard import ClipboardPayload
from neatcopy.presentation.wheel_controller import WheelController, build_history_menu_items, select_wheel_prompts


class TestSelectWheelPrompts:
    def test_prefers_user_defined_prompts(self, tmp_config_dir):
        config = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        prompts = config.get('llm.prompts')
        prompts.append({
            'id': 'custom-1',
            'name': '自定义 1',
            'content': 'a',
            'readonly': False,
            'visible_in_wheel': True,
        })
        prompts.append({
            'id': 'custom-2',
            'name': '自定义 2',
            'content': 'b',
            'readonly': False,
            'visible_in_wheel': True,
        })

        selected = select_wheel_prompts(prompts)

        assert [prompt['id'] for prompt in selected] == [
            'custom-1',
            'custom-2',
            'preset-prompt-master',
        ]

    def test_skips_hidden_prompts(self, tmp_config_dir):
        config = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        prompts = config.get('llm.prompts')
        for prompt in prompts:
            if prompt['id'] == 'preset-prompt-master':
                prompt['visible_in_wheel'] = False

        selected = select_wheel_prompts(prompts)

        assert [prompt['id'] for prompt in selected] == [
            'preset-translate',
            'preset-ask',
            'default',
        ]


class TestBuildHistoryMenuItems:
    def test_always_has_five_slots_and_back(self):
        text_payload = ClipboardPayload(kind='text', text='a')
        items = build_history_menu_items([
            type('HistoryEntry', (), {'label': 'a', 'payload': text_payload})(),
            type('HistoryEntry', (), {'label': 'b', 'payload': ClipboardPayload(kind='text', text='b')})(),
        ])

        assert len(items) == 6
        assert items[0].enabled is True
        assert items[1].enabled is True
        assert items[2].enabled is False
        assert items[-1].id == 'back'

    def test_image_history_item_includes_thumbnail_payload(self):
        image_payload = ClipboardPayload(kind='image', image_png_base64='ZmFrZQ==', image_width=10, image_height=10)
        items = build_history_menu_items([
            type('HistoryEntry', (), {'label': '[图片] 10x10', 'payload': image_payload})(),
        ])

        assert items[0].thumbnail_png_base64 == 'ZmFrZQ=='


class TestRootWheelMenu:
    def test_root_menu_includes_clear_clipboard_action(self):
        controller = WheelController.__new__(WheelController)

        state = controller._build_root_menu(ClipboardPayload(kind='text', text='demo'))

        assert state.kind == 'root'
        assert [item.id for item in state.items] == [
            'history',
            'paste',
            'rules',
            'llm',
            'clear_clipboard',
        ]

    def test_root_menu_disables_text_actions_for_images(self):
        controller = WheelController.__new__(WheelController)

        state = controller._build_root_menu(
            ClipboardPayload(kind='image', image_png_base64='ZmFrZQ==', image_width=10, image_height=10)
        )

        items = {item.id: item for item in state.items}

        assert items['paste'].enabled is True
        assert items['rules'].enabled is False
        assert items['llm'].enabled is False
