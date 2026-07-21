"""Platform-specific user-facing defaults.

The Windows build historically used Ctrl-based shortcuts.  macOS users
expect the same actions to use Command, while still allowing old config files
and manually entered Ctrl shortcuts to work.
"""
import sys


IS_MACOS = sys.platform == 'darwin'
PRIMARY_MODIFIER = 'cmd' if IS_MACOS else 'ctrl'
PRIMARY_MODIFIER_LABEL = '⌘' if IS_MACOS else 'Ctrl'

CLEAN_HOTKEY = f'{PRIMARY_MODIFIER}+shift+c'
WHEEL_HOTKEY = f'{PRIMARY_MODIFIER}+shift+p'
# Command+Q and Command+H are operating-system conventions on macOS. A
# global event tap must never steal them from every foreground application.
PREVIEW_HOTKEY = 'ctrl+q'
HISTORY_HOTKEY = 'ctrl+h'
DOUBLE_COPY_LABEL = f'双击 {PRIMARY_MODIFIER_LABEL}+C'
