from __future__ import annotations

import base64
from dataclasses import dataclass

import AppKit
from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication


@dataclass(frozen=True)
class ClipboardPayload:
    kind: str
    text: str | None = None
    image_png_base64: str | None = None
    image_width: int | None = None
    image_height: int | None = None

    @property
    def is_text(self) -> bool:
        return self.kind == 'text'

    @property
    def is_image(self) -> bool:
        return self.kind == 'image'

    @property
    def display_label(self) -> str:
        if self.is_image:
            size = ''
            if self.image_width and self.image_height:
                size = f' {self.image_width}x{self.image_height}'
            return f'[图片]{size}'
        stripped = ' '.join((self.text or '').split())
        return stripped


def read_text() -> str | None:
    payload = read_payload()
    if payload is None or not payload.is_text:
        return None
    return payload.text


def write_text(text: str) -> bool:
    return write_payload(ClipboardPayload(kind='text', text=text))


def read_payload() -> ClipboardPayload | None:
    native_payload = _read_native_pasteboard_payload()
    if native_payload is not None:
        return native_payload

    app = QApplication.instance()
    if not app:
        return None

    clipboard = app.clipboard()
    mime = clipboard.mimeData()
    if mime and mime.hasImage():
        image = clipboard.image()
        if not image.isNull():
            encoded = _encode_image(image)
            if encoded:
                return ClipboardPayload(
                    kind='image',
                    image_png_base64=encoded,
                    image_width=image.width(),
                    image_height=image.height(),
                )

    text = clipboard.text()
    if not text:
        return None
    return ClipboardPayload(
        kind='text',
        text=text.replace('\r\n', '\n').replace('\r', '\n'),
    )


def write_payload(payload: ClipboardPayload) -> bool:
    if _write_native_pasteboard_payload(payload):
        return True

    app = QApplication.instance()
    if not app:
        return False

    clipboard = app.clipboard()
    if payload.is_image:
        image = _decode_image(payload.image_png_base64)
        if image is None:
            return False
        clipboard.setImage(image)
        return True

    clipboard.setText((payload.text or ''))
    return True


def clear_clipboard() -> bool:
    if _clear_native_pasteboard():
        return True

    app = QApplication.instance()
    if not app:
        return False
    app.clipboard().clear()
    return True


def _read_qt_clipboard() -> str | None:
    return read_text()


def _write_qt_clipboard(text: str) -> bool:
    return write_text(text)


def _encode_image(image: QImage) -> str | None:
    image_bytes = QByteArray()
    buffer = QBuffer(image_bytes)
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        return None
    if not image.save(buffer, 'PNG'):
        return None
    return base64.b64encode(bytes(image_bytes)).decode('ascii')


def _decode_image(image_png_base64: str | None) -> QImage | None:
    if not image_png_base64:
        return None
    raw = base64.b64decode(image_png_base64)
    image = QImage()
    if not image.loadFromData(raw, 'PNG'):
        return None
    return image


def _read_native_pasteboard_payload() -> ClipboardPayload | None:
    pasteboard = AppKit.NSPasteboard.generalPasteboard()
    if pasteboard is None:
        return None

    image = AppKit.NSImage.alloc().initWithPasteboard_(pasteboard)
    if image is not None:
        ns_data = image.TIFFRepresentation()
        if ns_data is not None:
            bitmap = AppKit.NSBitmapImageRep.imageRepWithData_(ns_data)
            if bitmap is not None:
                png_type = getattr(AppKit, 'NSBitmapImageFileTypePNG', None)
                if png_type is None:
                    png_type = getattr(AppKit, 'NSPNGFileType', None)
                if png_type is None:
                    return None
                png_data = bitmap.representationUsingType_properties_(
                    png_type,
                    None,
                )
                if png_data is not None:
                    raw = bytes(png_data)
                    return ClipboardPayload(
                        kind='image',
                        image_png_base64=base64.b64encode(raw).decode('ascii'),
                        image_width=int(bitmap.pixelsWide()),
                        image_height=int(bitmap.pixelsHigh()),
                    )

    text = pasteboard.stringForType_(AppKit.NSPasteboardTypeString)
    if text:
        return ClipboardPayload(
            kind='text',
            text=str(text).replace('\r\n', '\n').replace('\r', '\n'),
        )
    return None


def _write_native_pasteboard_payload(payload: ClipboardPayload) -> bool:
    pasteboard = AppKit.NSPasteboard.generalPasteboard()
    if pasteboard is None:
        return False

    pasteboard.clearContents()
    if payload.is_image:
        if not payload.image_png_base64:
            return False
        raw = base64.b64decode(payload.image_png_base64)
        ns_data = AppKit.NSData.dataWithBytes_length_(raw, len(raw))
        image = AppKit.NSImage.alloc().initWithData_(ns_data)
        if image is None:
            return False
        return bool(pasteboard.writeObjects_([image]))

    text = payload.text or ''
    return bool(pasteboard.setString_forType_(text, AppKit.NSPasteboardTypeString))


def _clear_native_pasteboard() -> bool:
    pasteboard = AppKit.NSPasteboard.generalPasteboard()
    if pasteboard is None:
        return False
    pasteboard.clearContents()
    return True
