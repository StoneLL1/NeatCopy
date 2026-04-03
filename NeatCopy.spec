# -*- mode: python ; coding: utf-8 -*-

import os

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules('neatcopy')

icon_path = None
if os.path.exists('assets/idle.icns'):
    icon_path = ['assets/idle.icns']

a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt5',
        'PySide2',
        'PySide6',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NeatCopy',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='NeatCopy',
)

app = BUNDLE(
    coll,
    name='NeatCopy.app',
    icon=icon_path[0] if icon_path else None,
    bundle_identifier='com.neatcopy.app',
)
