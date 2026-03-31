# Windows 开机自启动管理：操作注册表 Run 键。
import sys
from pathlib import Path

REG_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
APP_NAME = 'NeatCopy'


def is_enabled() -> bool:
    """检查注册表中是否已启用自启动。"""
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


def enable() -> bool:
    """启用开机自启动，写入注册表。"""
    try:
        import winreg
        # 获取当前 exe 路径（PyInstaller 打包后）或脚本路径
        if getattr(sys, 'frozen', False):
            exe_path = sys.executable
        else:
            exe_path = str(Path(__file__).parent.parent / 'src' / 'main.py')

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_WRITE)
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f'[Autostart] enable failed: {e}')
        return False


def disable() -> bool:
    """禁用开机自启动，删除注册表项。"""
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


def sync_from_config(enabled: bool) -> bool:
    """根据配置同步注册表状态。"""
    current = is_enabled()
    if enabled and not current:
        return enable()
    elif not enabled and current:
        return disable()
    return True