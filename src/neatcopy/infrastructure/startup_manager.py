import plistlib
from pathlib import Path


APP_NAME = 'NeatCopy'
MAC_LAUNCH_AGENT_ID = 'com.neatcopy.app'


def _startup_command() -> str:
    import sys

    if getattr(sys, 'frozen', False):
        return [sys.executable]
    pythonw = sys.executable
    main_py = os.path.normpath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'main.py')
    )
    return [pythonw, main_py]


def _mac_launch_agent_path() -> Path:
    return Path.home() / 'Library' / 'LaunchAgents' / f'{MAC_LAUNCH_AGENT_ID}.plist'


class StartupManager:
    """管理 macOS LaunchAgent 自启动项。"""

    def apply(self, enabled: bool) -> None:
        plist_path = _mac_launch_agent_path()
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        if not enabled:
            plist_path.unlink(missing_ok=True)
            return
        command = _startup_command()
        if not isinstance(command, list):
            command = [command]
        payload = {
            'Label': MAC_LAUNCH_AGENT_ID,
            'ProgramArguments': command,
            'RunAtLoad': True,
            'KeepAlive': False,
            'WorkingDirectory': str(Path(command[-1]).resolve().parent),
        }
        with open(plist_path, 'wb') as f:
            plistlib.dump(payload, f)
