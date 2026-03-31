# tests/test_history_manager.py
"""HistoryManager 单元测试。"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from history_manager import HistoryManager


class TestHistoryManagerBasic:
    """基础功能测试：add 和 get_all。"""

    def test_add_and_get_all(self, tmp_config_dir):
        """添加记录后能正确获取所有条目。"""
        hm = HistoryManager(config_dir=str(tmp_config_dir))
        hm.add('原文内容', '处理后结果', 'rules', None)
        entries = hm.get_all()
        assert len(entries) == 1
        assert entries[0]['original'] == '原文内容'
        assert entries[0]['result'] == '处理后结果'
        assert entries[0]['mode'] == 'rules'
        assert entries[0]['prompt_name'] is None
        assert 'id' in entries[0]
        assert 'timestamp' in entries[0]

    def test_add_llm_mode_with_prompt_name(self, tmp_config_dir):
        """LLM 模式记录 prompt_name。"""
        hm = HistoryManager(config_dir=str(tmp_config_dir))
        hm.add('原文', '结果', 'llm', '格式清洗')
        entries = hm.get_all()
        assert entries[0]['mode'] == 'llm'
        assert entries[0]['prompt_name'] == '格式清洗'

    def test_empty_history_returns_empty_list(self, tmp_config_dir):
        """空历史返回空列表而非 None。"""
        hm = HistoryManager(config_dir=str(tmp_config_dir))
        assert hm.get_all() == []