# 剪贴板处理调度：读取剪贴板 → 规则/LLM → 写回剪贴板。
# 使用 win32clipboard 直接操作，绕过 Qt OleSetClipboard 无重试的问题。
# 写入时重试（App 可能以延迟渲染持有 clipboard owner，需等其释放）。
import time
from PyQt6.QtCore import QObject, pyqtSignal, QThread

from rule_engine import RuleEngine


def _read_clipboard() -> str | None:
    import win32clipboard
    for _ in range(5):
        try:
            win32clipboard.OpenClipboard(0)
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                    data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                    if data:
                        data = data.replace('\r\n', '\n').replace('\r', '\n')
                    return data if data else None
                return None
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            time.sleep(0.02)
    return None


def _write_clipboard(text: str) -> bool:
    import win32clipboard
    for attempt in range(10):
        try:
            win32clipboard.OpenClipboard(0)
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
                return True
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            if attempt < 9:
                time.sleep(0.05)
    return False


class _LLMWorker(QThread):
    succeeded = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, text: str, prompt: str, llm_config: dict, parent=None):
        super().__init__(parent)
        self._text = text
        self._prompt = prompt
        self._llm_config = llm_config

    def run(self):
        import httpx
        from llm_client import classify_error
        try:
            cfg = self._llm_config
            headers = {'Authorization': f'Bearer {cfg.get("api_key", "")}'}
            payload = {
                'model': cfg.get('model_id', 'gpt-4o-mini'),
                'temperature': cfg.get('temperature', 0.2),
                'messages': [
                    {'role': 'system', 'content': self._prompt},
                    {'role': 'user', 'content': self._text},
                ],
            }
            base_url = cfg.get('base_url', 'https://api.openai.com/v1').rstrip('/')
            timeout = float(cfg.get('timeout', 30))
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(f'{base_url}/chat/completions',
                                   json=payload, headers=headers)
                resp.raise_for_status()
                content = resp.json()['choices'][0]['message']['content']
                self.succeeded.emit(content)
        except Exception as e:
            self.failed.emit(classify_error(e, timeout=int(cfg.get('timeout', 30))))


class ClipProcessor(QObject):
    process_done = pyqtSignal(bool, str)     # (success, message)
    processing_started = pyqtSignal()
    preview_ready = pyqtSignal(str, str)    # (result, prompt_name) — LLM 成功时发射
    preview_failed = pyqtSignal(str)        # (error_message) — LLM 失败时发射

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._current_worker = None
        self._current_prompt_obj = None  # 当前处理的 prompt 对象，用于预览

    def reload_config(self, config):
        self._config = config

    def get_visible_prompts(self) -> list[dict]:
        """返回轮盘可见的 prompt 列表（visible_in_wheel=True，最多5个）。"""
        prompts = self._config.get('llm.prompts') or []
        visible = [p for p in prompts if p.get('visible_in_wheel', True)]
        return visible[:5]

    def process(self):
        text = _read_clipboard()
        if text is None:
            self.process_done.emit(False, '读取剪贴板失败，请重试')
            return
        if not text.strip():
            self.process_done.emit(False, '剪贴板为空')
            return

        mode = self._config.get('rules.mode', 'rules')
        if mode == 'llm':
            # 若有锁定的 prompt，使用锁定的；否则走正常逻辑
            locked_id = self._config.get('wheel.locked_prompt_id')
            if locked_id:
                self._process_llm_by_id(text, locked_id)
            else:
                self._process_llm(text)
        else:
            self._process_rules(text)

    def process_with_prompt(self, prompt_id: str):
        """指定 prompt_id 进行 LLM 处理（供轮盘选择后调用）。"""
        text = _read_clipboard()
        if text is None:
            self.process_done.emit(False, '读取剪贴板失败，请重试')
            return
        if not text.strip():
            self.process_done.emit(False, '剪贴板为空')
            return
        self._process_llm_by_id(text, prompt_id)

    def _process_rules(self, text: str):
        self.processing_started.emit()
        try:
            rule_config = self._config.get('rules') or {}
            cleaned = RuleEngine.clean(text, rule_config)
            if _write_clipboard(cleaned):
                self.process_done.emit(True, '已清洗，可直接粘贴')
            else:
                self.process_done.emit(False, '写入剪贴板失败')
        except Exception as e:
            self.process_done.emit(False, f'清洗出错：{e}')

    def _process_llm(self, text: str):
        llm_config = self._config.get('llm') or {}
        active_id = llm_config.get('active_prompt_id', 'default')
        self._process_llm_by_id(text, active_id)

    def _process_llm_by_id(self, text: str, prompt_id: str):
        """使用指定 prompt_id 调用 LLM。"""
        if self._current_worker is not None and self._current_worker.isRunning():
            self.process_done.emit(False, '正在处理中，请稍候')
            return

        llm_config = self._config.get('llm') or {}
        if not llm_config.get('api_key'):
            self.process_done.emit(False, '请先在设置中配置 API Key')
            return

        prompts = llm_config.get('prompts') or []
        prompt_obj = next((p for p in prompts if p['id'] == prompt_id),
                          prompts[0] if prompts else None)
        if not prompt_obj:
            self.process_done.emit(False, '未找到有效的 Prompt 模板')
            return

        self._start_llm_worker(text, prompt_obj, llm_config)

    def _start_llm_worker(self, text: str, prompt_obj: dict, llm_config: dict):
        self.processing_started.emit()
        self._current_prompt_obj = prompt_obj  # 保存以便预览信号使用
        worker = _LLMWorker(text, prompt_obj['content'], llm_config)
        worker.succeeded.connect(self._on_llm_success)
        worker.failed.connect(self._on_llm_error)
        worker.finished.connect(lambda: setattr(self, '_current_worker', None))
        worker.finished.connect(lambda: setattr(self, '_current_prompt_obj', None))
        worker.start()
        self._current_worker = worker

    def _on_llm_success(self, result: str):
        # 写入剪贴板（原有行为：双写模式）
        if _write_clipboard(result):
            self.process_done.emit(True, '大模型处理完成，可直接粘贴')
        else:
            self.process_done.emit(False, '写入剪贴板失败')

        # 发射预览信号（双写模式）
        prompt_name = self._current_prompt_obj.get('name', '默认') if self._current_prompt_obj else '默认'
        self.preview_ready.emit(result, prompt_name)

    def _on_llm_error(self, message: str):
        # 不写剪贴板，原文保持不变
        self.process_done.emit(False, message)
        # 发射预览失败信号
        self.preview_failed.emit(message)

    def write_to_clipboard(self, text: str) -> bool:
        """公共方法：将文本写入剪贴板（供预览面板应用按钮调用）。"""
        return _write_clipboard(text)
