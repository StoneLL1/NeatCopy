# 剪贴板处理调度：读取剪贴板 → 规则/LLM → 写回剪贴板。
# 所有剪贴板操作必须在主线程（Qt event loop）中执行。
import win32clipboard
import win32con
from PyQt6.QtCore import QObject, pyqtSignal, QThread

from rule_engine import RuleEngine


def _read_clipboard() -> str | None:
    try:
        win32clipboard.OpenClipboard()
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        return None
    except Exception:
        return None
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass


def _write_clipboard(text: str) -> bool:
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
        return True
    except Exception:
        return False
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass


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
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(f'{base_url}/chat/completions',
                                   json=payload, headers=headers)
                resp.raise_for_status()
                content = resp.json()['choices'][0]['message']['content']
                self.succeeded.emit(content)
        except Exception as e:
            self.failed.emit(classify_error(e))


class ClipProcessor(QObject):
    process_done = pyqtSignal(bool, str)     # (success, message)
    processing_started = pyqtSignal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._current_worker = None

    def reload_config(self, config):
        self._config = config

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
            self._process_llm(text)
        else:
            self._process_rules(text)

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
        if not llm_config.get('api_key'):
            self.process_done.emit(False, '请先在设置中配置 API Key')
            return

        active_id = llm_config.get('active_prompt_id', 'default')
        prompts = llm_config.get('prompts') or []
        prompt_obj = next((p for p in prompts if p['id'] == active_id),
                          prompts[0] if prompts else None)
        if not prompt_obj:
            self.process_done.emit(False, '未找到有效的 Prompt 模板')
            return

        self.processing_started.emit()
        worker = _LLMWorker(text, prompt_obj['content'], llm_config, parent=self)
        worker.succeeded.connect(self._on_llm_success)
        worker.failed.connect(self._on_llm_error)
        worker.start()
        self._current_worker = worker

    def _on_llm_success(self, result: str):
        if _write_clipboard(result):
            self.process_done.emit(True, '大模型处理完成，可直接粘贴')
        else:
            self.process_done.emit(False, '写入剪贴板失败')

    def _on_llm_error(self, message: str):
        # 不写剪贴板，原文保持不变
        self.process_done.emit(False, message)
