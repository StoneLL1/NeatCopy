"""macOS clipboard and end-to-end processor behavior."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import clip_processor as clip_module
from clip_processor import ClipProcessor, _LLMWorker, _read_clipboard, _write_clipboard


pytestmark = pytest.mark.skipif(sys.platform != 'darwin', reason='macOS only')


class DummyConfig:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key, default=None):
        node = self.values
        for part in key.split('.'):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node


class DummyHistory:
    def __init__(self):
        self.entries = []

    def add(self, *args):
        self.entries.append(args)
        return True


def test_native_clipboard_round_trip(qapp):
    text = 'NeatCopy macOS clipboard\n第二行'
    assert _write_clipboard(text) is True
    assert _read_clipboard() == text


def test_native_clipboard_normalizes_newlines(qapp):
    qapp.clipboard().setText('a\r\nb\rc')
    assert _read_clipboard() == 'a\nb\nc'


def test_native_clipboard_write_failure_is_reported(monkeypatch, qapp):
    class BrokenClipboard:
        def setText(self, text):
            raise RuntimeError('clipboard unavailable')

    monkeypatch.setattr(type(qapp), 'clipboard', staticmethod(lambda: BrokenClipboard()))
    assert _write_clipboard('text') is False


def test_rules_pipeline_reads_cleans_writes_and_records(monkeypatch, qapp):
    config = DummyConfig({
        'rules': {'mode': 'rules'},
        'history': {'enabled': True},
    })
    history = DummyHistory()
    processor = ClipProcessor(config, history)
    writes = []
    done = []
    started = []
    processor.process_done.connect(lambda ok, msg: done.append((ok, msg)))
    processor.processing_started.connect(lambda: started.append(True))
    monkeypatch.setattr(clip_module, '_read_clipboard', lambda: 'hello\nworld')
    monkeypatch.setattr(clip_module, '_write_clipboard', lambda text: writes.append(text) or True)

    processor.process()

    assert started == [True]
    assert writes == ['hello world']
    assert done == [(True, '已清洗，可直接粘贴')]
    assert history.entries == [('hello\nworld', 'hello world', 'rules', None)]


def test_rules_pipeline_preserves_clipboard_on_write_failure(monkeypatch, qapp):
    processor = ClipProcessor(DummyConfig({'rules': {'mode': 'rules'}}))
    done = []
    processor.process_done.connect(lambda ok, msg: done.append((ok, msg)))
    monkeypatch.setattr(clip_module, '_read_clipboard', lambda: 'input')
    monkeypatch.setattr(clip_module, '_write_clipboard', lambda text: False)

    processor.process()

    assert done == [(False, '写入剪贴板失败')]


def test_llm_success_updates_clipboard_preview_and_history(monkeypatch, qapp):
    history = DummyHistory()
    processor = ClipProcessor(DummyConfig({'history': {'enabled': True}}), history)
    processor._current_prompt_obj = {'name': '翻译'}
    processor._current_original = '你好'
    done = []
    previews = []
    processor.process_done.connect(lambda ok, msg: done.append((ok, msg)))
    processor.preview_ready.connect(lambda text, name: previews.append((text, name)))
    monkeypatch.setattr(clip_module, '_write_clipboard', lambda text: True)

    processor._on_llm_success('Hello')

    assert done == [(True, '大模型处理完成，可直接粘贴')]
    assert previews == [('Hello', '翻译')]
    assert history.entries == [('你好', 'Hello', 'llm', '翻译')]


def test_llm_failure_does_not_write_clipboard(monkeypatch, qapp):
    processor = ClipProcessor(DummyConfig())
    writes = []
    done = []
    previews = []
    processor.process_done.connect(lambda ok, msg: done.append((ok, msg)))
    processor.preview_failed.connect(previews.append)
    monkeypatch.setattr(clip_module, '_write_clipboard', lambda text: writes.append(text) or True)

    processor._on_llm_error('网络连接失败')

    assert writes == []
    assert done == [(False, '网络连接失败')]
    assert previews == ['网络连接失败']


def test_keyless_local_llm_is_allowed(monkeypatch, qapp):
    processor = ClipProcessor(DummyConfig({'llm': {
        'base_url': 'http://localhost:11434/v1',
        'api_key': '',
        'prompts': [{'id': 'local', 'name': 'Local', 'content': 'prompt'}],
    }}))
    started = []
    monkeypatch.setattr(processor, '_start_llm_worker',
                        lambda *args: started.append(args))

    processor._process_llm_by_id('input', 'local')

    assert len(started) == 1


def test_keyless_cloud_llm_is_rejected(qapp):
    processor = ClipProcessor(DummyConfig({'llm': {
        'base_url': 'https://api.openai.com/v1',
        'api_key': '',
        'prompts': [{'id': 'cloud', 'name': 'Cloud', 'content': 'prompt'}],
    }}))
    done = []
    processor.process_done.connect(lambda ok, message: done.append((ok, message)))

    processor._process_llm_by_id('input', 'cloud')

    assert done == [(False, '请先在设置中配置 API Key')]


def test_llm_worker_uses_openai_compatible_payload(monkeypatch, qapp):
    captured = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {'choices': [{'message': {'content': 'result'}}]}

    class Client:
        def __init__(self, timeout):
            captured['timeout'] = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, json, headers):
            captured.update(url=url, payload=json, headers=headers)
            return Response()

    import httpx
    monkeypatch.setattr(httpx, 'Client', Client)
    worker = _LLMWorker('raw', 'prompt', {
        'api_key': 'secret', 'base_url': 'https://example.test/v1/',
        'model_id': 'model', 'temperature': 0.1, 'timeout': 7,
    })
    succeeded = []
    worker.succeeded.connect(succeeded.append)

    worker.run()

    assert succeeded == ['result']
    assert captured['url'] == 'https://example.test/v1/chat/completions'
    assert captured['headers']['Authorization'] == 'Bearer secret'
    assert captured['payload']['messages'][1]['content'] == '<text>\nraw\n</text>'
