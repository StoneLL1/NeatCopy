import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from neatcopy.infrastructure.llm_client import LLMClient, classify_error


class TestClassifyError:
    def test_timeout_error(self):
        err = httpx.TimeoutException('timeout')
        msg = classify_error(err, timeout=45)
        assert '超时' in msg
        assert '45s' in msg

    def test_401_error(self):
        req = MagicMock()
        resp = httpx.Response(401, request=req)
        err = httpx.HTTPStatusError('', request=req, response=resp)
        msg = classify_error(err)
        assert 'Key' in msg or '无效' in msg

    def test_429_error(self):
        req = MagicMock()
        resp = httpx.Response(429, request=req)
        err = httpx.HTTPStatusError('', request=req, response=resp)
        msg = classify_error(err)
        assert '频率' in msg or '余额' in msg

    def test_404_error(self):
        req = MagicMock()
        resp = httpx.Response(404, request=req)
        err = httpx.HTTPStatusError('', request=req, response=resp)
        msg = classify_error(err)
        assert '模型' in msg or '不存在' in msg

    def test_connect_error(self):
        err = httpx.ConnectError('connection refused')
        msg = classify_error(err)
        assert '连接' in msg

    def test_unknown_error(self):
        err = ValueError('unexpected')
        msg = classify_error(err)
        assert '未知' in msg or 'unexpected' in msg


@pytest.mark.asyncio
class TestLLMClientFormat:
    async def test_success_returns_content(self):
        mock_json = {'choices': [{'message': {'content': '整理后的文本'}}]}
        config = {
            'base_url': 'https://api.openai.com/v1',
            'api_key': 'test-key',
            'model_id': 'gpt-4o-mini',
            'temperature': 0.2,
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_json
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch('httpx.AsyncClient') as MockAsyncClient:
            MockAsyncClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockAsyncClient.return_value.__aexit__ = AsyncMock(return_value=False)

            client = LLMClient()
            result = await client.format('原始文本', '系统prompt', config)
            assert result == '整理后的文本'

    async def test_401_raises_exception(self):
        config = {
            'base_url': 'https://api.openai.com/v1',
            'api_key': 'bad-key',
            'model_id': 'gpt-4o-mini',
            'temperature': 0.2,
        }
        req = MagicMock()
        resp = httpx.Response(401, request=req)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError('', request=req, response=resp))

        with patch('httpx.AsyncClient') as MockAsyncClient:
            MockAsyncClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockAsyncClient.return_value.__aexit__ = AsyncMock(return_value=False)

            client = LLMClient()
            with pytest.raises(httpx.HTTPStatusError):
                await client.format('文本', 'prompt', config)

    async def test_timeout_raises_exception(self):
        config = {
            'base_url': 'https://api.openai.com/v1',
            'api_key': 'key',
            'model_id': 'gpt-4o-mini',
            'temperature': 0.2,
        }
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException('timeout'))

        with patch('httpx.AsyncClient') as MockAsyncClient:
            MockAsyncClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockAsyncClient.return_value.__aexit__ = AsyncMock(return_value=False)

            client = LLMClient()
            with pytest.raises(httpx.TimeoutException):
                await client.format('文本', 'prompt', config)


class TestLLMClientSync:
    def test_build_timeout_uses_configured_value(self):
        assert LLMClient._get_timeout({'timeout': 45}) == 45.0

    def test_build_timeout_falls_back_on_invalid_value(self):
        assert LLMClient._get_timeout({'timeout': 'bad'}) == 30.0

    def test_build_request_accepts_full_chat_completions_endpoint(self):
        config = {
            'base_url': 'https://api.deepseek.com/v1/chat/completions',
            'api_key': 'test-key',
            'model_id': 'deepseek-chat',
            'temperature': 0.2,
        }
        url, payload, headers = LLMClient._build_request('原始文本', '系统prompt', config)
        assert url == 'https://api.deepseek.com/v1/chat/completions'
        assert payload['model'] == 'deepseek-chat'
        assert headers['Authorization'] == 'Bearer test-key'

    def test_extract_content_supports_content_array(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            'choices': [{
                'message': {
                    'content': [
                        {'type': 'text', 'text': '第一段'},
                        {'type': 'text', 'text': '第二段'},
                    ]
                }
            }]
        }
        assert LLMClient._extract_content(mock_resp) == '第一段第二段'

    def test_format_sync_returns_content(self):
        mock_json = {'choices': [{'message': {'content': '同步结果'}}]}
        config = {
            'base_url': 'https://api.openai.com/v1',
            'api_key': 'test-key',
            'model_id': 'gpt-4o-mini',
            'temperature': 0.2,
            'timeout': 45,
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_json
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp

        with patch('httpx.Client') as MockClient:
            MockClient.return_value.__enter__.return_value = mock_client
            MockClient.return_value.__exit__.return_value = False

            client = LLMClient()
            result = client.format_sync('原始文本', '系统prompt', config)
            assert result == '同步结果'
            MockClient.assert_called_once_with(timeout=45.0)

    def test_test_connection_sync_uses_shared_path(self):
        config = {
            'base_url': 'https://api.openai.com/v1',
            'api_key': 'test-key',
            'model_id': 'gpt-4o-mini',
            'temperature': 0.2,
        }
        with patch.object(LLMClient, 'format_sync', return_value='ok') as mock_format:
            client = LLMClient()
            result = client.test_connection_sync(config)
            assert result == 'ok'
            mock_format.assert_called_once()
