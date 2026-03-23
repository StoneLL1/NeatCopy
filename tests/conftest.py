import pytest


@pytest.fixture
def tmp_config_dir(tmp_path, monkeypatch):
    """将 APPDATA 重定向到临时目录，避免污染真实配置。"""
    monkeypatch.setenv('APPDATA', str(tmp_path))
    return tmp_path
