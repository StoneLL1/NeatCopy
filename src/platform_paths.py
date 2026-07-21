"""Portable locations used by the application data and logs."""
import os
import sys
from pathlib import Path


def app_data_dir() -> Path:
    """Return the per-user NeatCopy data directory.

    APPDATA remains supported as an explicit override for tests and for users
    migrating an existing Windows data directory.  On macOS the native
    location is ``~/Library/Application Support/NeatCopy``.
    """
    override = os.environ.get('APPDATA')
    if override:
        return Path(override) / 'NeatCopy'
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'NeatCopy'
    return Path.home() / 'NeatCopy'
