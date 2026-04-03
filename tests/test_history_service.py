import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from neatcopy.application.history_service import PasteHistoryService
from neatcopy.infrastructure.config_manager import ConfigManager
from neatcopy.infrastructure.clipboard import ClipboardPayload


class TestPasteHistoryService:
    def test_add_item_keeps_latest_first(self, tmp_config_dir):
        config = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        history = PasteHistoryService(config)

        history.add_item('first')
        history.add_item('second')

        assert history.list_items() == ['second', 'first']

    def test_add_item_deduplicates_existing_text(self, tmp_config_dir):
        config = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        history = PasteHistoryService(config)

        history.add_item('same')
        history.add_item('other')
        history.add_item('same')

        assert history.list_items() == ['same', 'other']

    def test_add_item_caps_at_five(self, tmp_config_dir):
        config = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        history = PasteHistoryService(config)

        for index in range(12):
            history.add_item(f'item-{index}')

        assert history.list_items() == [
            'item-11',
            'item-10',
            'item-9',
            'item-8',
            'item-7',
            'item-6',
            'item-5',
            'item-4',
            'item-3',
            'item-2',
        ]

    def test_add_image_payload_to_history(self, tmp_config_dir):
        config = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        history = PasteHistoryService(config)

        history.add_payload(
            ClipboardPayload(
                kind='image',
                image_png_base64='ZmFrZS1pbWFnZQ==',
                image_width=128,
                image_height=64,
            )
        )

        entries = history.list_entries()

        assert len(entries) == 1
        assert entries[0].payload.is_image is True
        assert entries[0].label == '[图片] 128x64'

    def test_delete_history_item(self, tmp_config_dir):
        config = ConfigManager(config_dir=str(tmp_config_dir / 'NeatCopy'))
        history = PasteHistoryService(config)
        history.add_item('first')
        history.add_item('second')

        deleted = history.delete_item(0)

        assert deleted is True
        assert history.list_items() == ['first']
