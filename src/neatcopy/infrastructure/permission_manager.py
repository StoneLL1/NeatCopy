from __future__ import annotations

import AppKit
import Quartz
from PyQt6.QtCore import QObject, QTimer, pyqtSignal


class PermissionManager(QObject):
    info_message = pyqtSignal(str)

    def ensure_startup_permissions(self) -> None:
        accessibility_ok = self._check_accessibility(prompt=True)
        input_ok = self._check_input_monitoring(prompt=True)
        if accessibility_ok and input_ok:
            return

        missing = []
        if not accessibility_ok:
            missing.append('辅助功能')
        if not input_ok:
            missing.append('输入监听')
        self.info_message.emit(
            f'NeatCopy 需要 {"、".join(missing)}权限，已尝试拉起系统授权。勾选后建议重新打开应用。'
        )
        QTimer.singleShot(300, self.open_missing_settings)

    def open_missing_settings(self) -> None:
        if not self._check_accessibility(prompt=False):
            self._open_settings_url(
                'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'
            )
        if not self._check_input_monitoring(prompt=False):
            QTimer.singleShot(
                500,
                lambda: self._open_settings_url(
                    'x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent'
                ),
            )

    def _check_accessibility(self, prompt: bool) -> bool:
        prompt_key = getattr(Quartz, 'kAXTrustedCheckOptionPrompt', None)
        checker = getattr(Quartz, 'AXIsProcessTrustedWithOptions', None)
        if prompt and checker is not None and prompt_key is not None:
            try:
                return bool(checker({prompt_key: True}))
            except Exception:
                pass
        fallback = getattr(Quartz, 'AXIsProcessTrusted', None)
        if fallback is not None:
            try:
                return bool(fallback())
            except Exception:
                return False
        return True

    def _check_input_monitoring(self, prompt: bool) -> bool:
        preflight = getattr(Quartz, 'CGPreflightListenEventAccess', None)
        if preflight is not None:
            try:
                if bool(preflight()):
                    return True
            except Exception:
                pass

        if prompt:
            requester = getattr(Quartz, 'CGRequestListenEventAccess', None)
            if requester is not None:
                try:
                    return bool(requester())
                except Exception:
                    return False
        return False if preflight is not None else True

    def _open_settings_url(self, url: str) -> None:
        ns_url = AppKit.NSURL.URLWithString_(url)
        if ns_url is not None:
            AppKit.NSWorkspace.sharedWorkspace().openURL_(ns_url)
