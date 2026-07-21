# 跨平台开机自启动管理：Windows 使用注册表，macOS 使用 LaunchAgent。
import os
import plistlib
import sys
import tempfile
from pathlib import Path

REG_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
APP_NAME = 'NeatCopy'
MAC_LABEL = 'com.stonell1.neatcopy'


def _is_macos() -> bool:
    return sys.platform == 'darwin'


def _mac_plist_path() -> Path:
    return Path.home() / 'Library' / 'LaunchAgents' / f'{MAC_LABEL}.plist'


def _mac_program_arguments() -> list[str]:
    if getattr(sys, 'frozen', False):
        return [str(Path(sys.executable).resolve())]
    return [str(Path(sys.executable).resolve()),
            str(Path(__file__).resolve().with_name('main.py'))]


def _mac_payload() -> dict:
    return {
        'Label': MAC_LABEL,
        'ProgramArguments': _mac_program_arguments(),
        'RunAtLoad': True,
        'ProcessType': 'Interactive',
        'LimitLoadToSessionType': 'Aqua',
    }


def is_enabled() -> bool:
    """检查注册表中是否已启用自启动。"""
    if _is_macos():
        path = _mac_plist_path()
        try:
            with path.open('rb') as handle:
                return plistlib.load(handle) == _mac_payload()
        except (OSError, plistlib.InvalidFileException, ValueError):
            return False
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, APP_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except Exception:
        return False


def enable() -> tuple[bool, str]:
    """启用开机自启动，写入注册表。仅在打包状态下生效。

    Returns:
        tuple: (success, message) - 成功时 message 为空，失败时为原因说明
    """
    if _is_macos():
        try:
            path = _mac_plist_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode='wb', dir=path.parent, prefix=f'.{path.name}.',
                    suffix='.tmp', delete=False,
                ) as handle:
                    temporary = Path(handle.name)
                    os.chmod(handle.name, 0o600)
                    plistlib.dump(_mac_payload(), handle, sort_keys=False)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, path)
                temporary = None
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            return True, ''
        except Exception as e:
            return False, f'写入 macOS 开机启动配置失败: {e}'
    try:
        import winreg
        # 只有打包后的 exe 才能开机自启动，脚本路径无效
        if not getattr(sys, 'frozen', False):
            return False, '开机自启动仅在打包后的 exe 版本中可用'

        exe_path = sys.executable

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_WRITE)
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(key)
        return True, ''
    except Exception as e:
        print(f'[Autostart] enable failed: {e}')
        return False, f'写入注册表失败: {e}'


def disable() -> bool:
    """禁用开机自启动，删除注册表项。"""
    if _is_macos():
        try:
            _mac_plist_path().unlink(missing_ok=True)
            return True
        except Exception as e:
            print(f'[Autostart] disable failed: {e}')
            return False
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_WRITE)
        try:
            winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError:
            pass  # 已经不存在
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f'[Autostart] disable failed: {e}')
        return False


def sync_from_config(enabled: bool) -> tuple[bool, str]:
    """根据配置同步注册表状态。

    Returns:
        tuple: (success, message)
    """
    if _is_macos():
        # Rewriting an enabled LaunchAgent refreshes a stale application path
        # after the user moves or reinstalls the .app bundle.
        if enabled:
            return enable()
        ok = disable()
        return ok, '' if ok else '删除 macOS 开机启动配置失败'

    current = is_enabled()
    if enabled and not current:
        return enable()
    elif not enabled and current:
        ok = disable()
        return ok, '' if ok else '删除注册表失败'
    return True, ''
