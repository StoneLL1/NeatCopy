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


class TestHistoryManagerDelete:
    def test_delete_by_id(self, tmp_config_dir):
        """根据 ID 删除指定条目"""
        hm = HistoryManager(config_dir=str(tmp_config_dir))
        hm.add('原文1', '结果1', 'rules', None)
        hm.add('原文2', '结果2', 'rules', None)
        entries = hm.get_all()
        first_id = entries[0]['id']  # 最新那条
        hm.delete(first_id)
        remaining = hm.get_all()
        assert len(remaining) == 1
        assert remaining[0]['original'] == '原文1'

    def test_delete_nonexistent_id_returns_false(self, tmp_config_dir):
        """删除不存在的 ID 返回 False"""
        hm = HistoryManager(config_dir=str(tmp_config_dir))
        hm.add('原文', '结果', 'rules', None)
        result = hm.delete('nonexistent-id')
        assert result is False

    def test_clear_all(self, tmp_config_dir):
        """清空所有历史"""
        hm = HistoryManager(config_dir=str(tmp_config_dir))
        hm.add('原文1', '结果1', 'rules', None)
        hm.add('原文2', '结果2', 'rules', None)
        hm.clear()
        assert hm.get_all() == []


class TestHistoryManagerSearch:
    def test_search_matches_original(self, tmp_config_dir):
        """搜索匹配原文内容"""
        hm = HistoryManager(config_dir=str(tmp_config_dir))
        hm.add('PDF复制的文本段落', '清洗后文本', 'rules', None)
        hm.add('另一段内容', '结果', 'rules', None)
        results = hm.search('PDF')
        assert len(results) == 1
        assert 'PDF' in results[0]['original']

    def test_search_matches_result(self, tmp_config_dir):
        """搜索匹配结果内容"""
        hm = HistoryManager(config_dir=str(tmp_config_dir))
        hm.add('原文', '清洗后的格式化文本', 'rules', None)
        results = hm.search('格式化')
        assert len(results) == 1
        assert '格式化' in results[0]['result']

    def test_search_no_match_returns_empty(self, tmp_config_dir):
        """无匹配返回空列表"""
        hm = HistoryManager(config_dir=str(tmp_config_dir))
        hm.add('原文', '结果', 'rules', None)
        results = hm.search('不存在的内容')
        assert results == []

    def test_search_case_insensitive(self, tmp_config_dir):
        """搜索不区分大小写"""
        hm = HistoryManager(config_dir=str(tmp_config_dir))
        hm.add('Hello World', 'hello world', 'rules', None)
        results = hm.search('HELLO')
        assert len(results) == 1


class TestHistoryManagerCapacity:
    def test_max_count_limit(self, tmp_config_dir):
        """超出上限自动删除最旧"""
        hm = HistoryManager(config_dir=str(tmp_config_dir), max_count=3)
        hm.add('第1条', '结果1', 'rules', None)
        hm.add('第2条', '结果2', 'rules', None)
        hm.add('第3条', '结果3', 'rules', None)
        hm.add('第4条', '结果4', 'rules', None)  # 应触发删除第1条
        entries = hm.get_all()
        assert len(entries) == 3
        # 最旧的已被删除
        originals = [e['original'] for e in entries]
        assert '第1条' not in originals
        assert '第4条' in originals

    def test_update_max_count(self, tmp_config_dir):
        """动态更新上限"""
        hm = HistoryManager(config_dir=str(tmp_config_dir), max_count=5)
        hm.add('第1条', '结果1', 'rules', None)
        hm.set_max_count(2)
        hm.add('第2条', '结果2', 'rules', None)
        hm.add('第3条', '结果3', 'rules', None)  # 应触发删除
        entries = hm.get_all()
        assert len(entries) == 2