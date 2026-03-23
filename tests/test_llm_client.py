import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from llm_client import LLMClient, classify_error


class TestClassifyError:
    def test_timeout_error(self):
        err = httpx.TimeoutException('timeout')
        msg = classify_error(err)
        assert '超时' in msg

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
