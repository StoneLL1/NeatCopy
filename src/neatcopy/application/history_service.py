from __future__ import annotations

from dataclasses import dataclass

from neatcopy.infrastructure.clipboard import ClipboardPayload


@dataclass(frozen=True)
class PasteHistoryItem:
    payload: ClipboardPayload
    label: str


class PasteHistoryService:
    def __init__(self, config):
        self._config = config

    def list_items(self) -> list[str]:
        return [item.label for item in self.list_entries()]

    def list_entries(self) -> list[PasteHistoryItem]:
        items = self._config.get('history.items', [])
        if not isinstance(items, list):
            return []
        entries: list[PasteHistoryItem] = []
        for item in items:
            normalized = self._normalize_item(item)
            if normalized is not None:
                entries.append(normalized)
        return entries

    def add_item(self, text: str) -> None:
        value = str(text or '').strip()
        if not value:
            return
        self.add_payload(ClipboardPayload(kind='text', text=value))

    def add_payload(self, payload: ClipboardPayload) -> None:
        normalized = self._normalize_payload(payload)
        if normalized is None:
            return
        items = [
            item for item in self.list_entries()
            if not self._is_duplicate(item.payload, normalized.payload)
        ]
        items.insert(0, normalized)
        max_items = int(self._config.get('history.max_items', 10) or 10)
        max_items = max(10, max_items)
        self._config.set('history.items', [self._serialize_item(item) for item in items[:max_items]])

    def delete_item(self, index: int) -> bool:
        items = self.list_entries()
        if index < 0 or index >= len(items):
            return False
        items.pop(index)
        self._config.set('history.items', [self._serialize_item(item) for item in items])
        return True

    def delete_payload(self, payload: ClipboardPayload) -> bool:
        items = self.list_entries()
        for index, item in enumerate(items):
            if self._is_duplicate(item.payload, payload):
                items.pop(index)
                self._config.set('history.items', [self._serialize_item(entry) for entry in items])
                return True
        return False

    def _normalize_item(self, item) -> PasteHistoryItem | None:
        if isinstance(item, str):
            payload = ClipboardPayload(kind='text', text=item.strip())
            return self._normalize_payload(payload)
        if not isinstance(item, dict):
            return None
        kind = item.get('kind')
        if kind == 'text':
            payload = ClipboardPayload(kind='text', text=str(item.get('text', '')).strip())
            return self._normalize_payload(payload)
        if kind == 'image':
            payload = ClipboardPayload(
                kind='image',
                image_png_base64=item.get('image_png_base64'),
                image_width=self._safe_int(item.get('image_width')),
                image_height=self._safe_int(item.get('image_height')),
            )
            return self._normalize_payload(payload)
        return None

    def _normalize_payload(self, payload: ClipboardPayload) -> PasteHistoryItem | None:
        if payload.is_text:
            text = str(payload.text or '').strip()
            if not text:
                return None
            normalized = ClipboardPayload(kind='text', text=text)
            return PasteHistoryItem(payload=normalized, label=normalized.display_label)
        if payload.is_image and payload.image_png_base64:
            normalized = ClipboardPayload(
                kind='image',
                image_png_base64=payload.image_png_base64,
                image_width=payload.image_width,
                image_height=payload.image_height,
            )
            return PasteHistoryItem(payload=normalized, label=normalized.display_label)
        return None

    def _serialize_item(self, item: PasteHistoryItem) -> dict:
        if item.payload.is_image:
            return {
                'kind': 'image',
                'image_png_base64': item.payload.image_png_base64,
                'image_width': item.payload.image_width,
                'image_height': item.payload.image_height,
            }
        return {
            'kind': 'text',
            'text': item.payload.text,
        }

    def _is_duplicate(self, left: ClipboardPayload, right: ClipboardPayload) -> bool:
        if left.kind != right.kind:
            return False
        if left.is_image:
            return left.image_png_base64 == right.image_png_base64
        return left.text == right.text

    def _safe_int(self, value) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
