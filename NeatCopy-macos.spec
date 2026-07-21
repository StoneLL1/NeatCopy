# PyInstaller bundle definition for the Apple Silicon macOS build.
# Run with the Python environment used for this project:
#   pyinstaller --noconfirm --clean NeatCopy-macos.spec

from PyInstaller.utils.hooks import collect_submodules
import sys

sys.path.insert(0, 'src')
from version import VERSION


hiddenimports = [
    'PyQt6.sip',
    'AppKit',
    'Quartz',
    'ApplicationServices',
    *collect_submodules('ui'),
]

a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['win32clipboard', 'win32con', 'winreg', 'keyboard'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    name='NeatCopy',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='arm64',
    codesign_identity=None,
    entitlements_file=None,
    exclude_binaries=True,
)

app = BUNDLE(
    exe,
    a.binaries,
    a.datas,
    a.zipfiles,
    name='NeatCopy.app',
    icon='assets/idle.png',
    bundle_identifier='com.stonell1.neatcopy',
    info_plist={
        'CFBundleDisplayName': 'NeatCopy',
        'CFBundleName': 'NeatCopy',
        'CFBundleShortVersionString': VERSION,
        'CFBundleVersion': VERSION,
        'LSMinimumSystemVersion': '11.0',
        'LSUIElement': True,
        'NSAccessibilityUsageDescription': 'NeatCopy 需要辅助功能权限来向前台应用发送复制按键并取得当前选中文本。',
        'NSAppleEventsUsageDescription': 'NeatCopy 使用系统事件完成全局快捷键和剪贴板工作流。',
    },
)
