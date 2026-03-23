# OpenAI 兼容接口客户端，失败时抛出异常，不静默处理。
import httpx

ERROR_MESSAGES = {
    401: 'API Key 无效，请在设置中检查',
    402: '账户余额不足',
    429: '请求频率超限或余额不足',
    404: '模型 ID 不存在，请检查设置',
}


def classify_error(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return '请求超时（30s），请检查网络连接'
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return ERROR_MESSAGES.get(code, f'请求失败（HTTP {code}）')
    if isinstance(exc, httpx.ConnectError):
        return '网络连接失败，请检查代理或网络设置'
    return f'未知错误：{exc}'


class LLMClient:
    async def format(self, text: str, prompt: str, config: dict) -> str:
        """调用 OpenAI 兼容接口整理文本格式，失败时抛出异常。"""
        headers = {'Authorization': f'Bearer {config.get("api_key", "")}'}
        payload = {
            'model': config.get('model_id', 'gpt-4o-mini'),
            'temperature': config.get('temperature', 0.2),
            'messages': [
                {'role': 'system', 'content': prompt},
                {'role': 'user', 'content': text},
            ],
        }
        base_url = config.get('base_url', 'https://api.openai.com/v1').rstrip('/')
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f'{base_url}/chat/completions',
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()['choices'][0]['message']['content']

    async def test_connection(self, config: dict) -> str:
        """发送固定测试文本验证连接，返回模型回复。"""
        return await self.format(
            '测试文本：hello world',
            '请原样返回我发送给你的文字，不做任何修改。',
            config,
        )
