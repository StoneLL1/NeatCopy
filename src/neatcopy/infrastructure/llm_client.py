from __future__ import annotations

# OpenAI 兼容接口客户端，失败时抛出异常，不静默处理。
import httpx
import json
from pathlib import Path

from neatcopy.infrastructure.config_manager import get_default_config_dir

ERROR_MESSAGES = {
    401: 'API Key 无效，请在设置中检查',
    402: '账户余额不足',
    429: '请求频率超限或余额不足',
    404: '模型 ID 不存在，请检查设置',
}

_LOG_PATH = Path(get_default_config_dir()) / 'llm.log'


def _log(message: str) -> None:
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(message.rstrip() + '\n')
    except Exception:
        pass


def classify_error(exc: Exception, timeout: int | float = 30) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return f'请求超时（{int(timeout)}s），请检查网络连接'
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return ERROR_MESSAGES.get(code, f'请求失败（HTTP {code}）')
    if isinstance(exc, httpx.ConnectError):
        return '网络连接失败，请检查代理或网络设置'
    if isinstance(exc, httpx.ConnectTimeout):
        return '连接超时，请检查网络或 Base URL'
    if isinstance(exc, httpx.ReadError):
        return '读取响应失败，请稍后重试'
    if isinstance(exc, json.JSONDecodeError):
        return '服务端返回了非 JSON 响应，请检查 Base URL 是否正确'
    if isinstance(exc, KeyError):
        return '服务端返回格式不兼容，未找到模型输出内容'
    return f'未知错误：{exc}'


class LLMClient:
    @staticmethod
    def _get_timeout(config: dict) -> float:
        timeout = config.get('timeout', 30)
        try:
            timeout_value = float(timeout)
        except (TypeError, ValueError):
            timeout_value = 30.0
        return max(timeout_value, 1.0)

    @staticmethod
    def _build_request(text: str, prompt: str, config: dict) -> tuple[str, dict, dict]:
        api_key = str(config.get('api_key', '')).strip()
        base_url = str(config.get('base_url', 'https://api.openai.com/v1')).strip().rstrip('/')
        model_id = str(config.get('model_id', 'gpt-4o-mini')).strip()
        if not base_url:
            base_url = 'https://api.openai.com/v1'
        if not model_id:
            model_id = 'gpt-4o-mini'

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/json',
            'User-Agent': 'NeatCopy/1.0',
        }
        payload = {
            'model': model_id,
            'temperature': config.get('temperature', 0.2),
            'messages': [
                {'role': 'system', 'content': prompt},
                {'role': 'user', 'content': text},
            ],
        }
        if base_url.endswith('/chat/completions'):
            url = base_url
        else:
            url = f'{base_url}/chat/completions'
        return url, payload, headers

    @staticmethod
    def _extract_content(response: httpx.Response) -> str:
        _log(f'[response] status={response.status_code}')
        response.raise_for_status()
        data = response.json()
        message = data['choices'][0]['message']
        content = message['content']
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    text_parts.append(str(item.get('text', '')))
            if text_parts:
                return ''.join(text_parts)
        raise KeyError('message.content')

    async def format(self, text: str, prompt: str, config: dict) -> str:
        """调用 OpenAI 兼容接口整理文本格式，失败时抛出异常。"""
        url, payload, headers = self._build_request(text, prompt, config)
        timeout = self._get_timeout(config)
        _log(f'[request] async url={url} model={payload["model"]}')
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                resp = await client.post(url, json=payload, headers=headers)
                return self._extract_content(resp)
            except Exception as exc:
                _log(f'[error] async {type(exc).__name__}: {exc}')
                raise

    def format_sync(self, text: str, prompt: str, config: dict) -> str:
        """同步调用 OpenAI 兼容接口，供 QThread 场景复用。"""
        url, payload, headers = self._build_request(text, prompt, config)
        timeout = self._get_timeout(config)
        _log(f'[request] sync url={url} model={payload["model"]}')
        with httpx.Client(timeout=timeout) as client:
            try:
                resp = client.post(url, json=payload, headers=headers)
                return self._extract_content(resp)
            except Exception as exc:
                _log(f'[error] sync {type(exc).__name__}: {exc}')
                raise

    async def test_connection(self, config: dict) -> str:
        """发送固定测试文本验证连接，返回模型回复。"""
        return await self.format(
            '测试文本：hello world',
            '请原样返回我发送给你的文字，不做任何修改。',
            config,
        )

    def test_connection_sync(self, config: dict) -> str:
        """同步发送固定测试文本验证连接，供 QThread 场景复用。"""
        return self.format_sync(
            '测试文本：hello world',
            '请原样返回我发送给你的文字，不做任何修改。',
            config,
        )
