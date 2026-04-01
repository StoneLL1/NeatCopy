from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal, QThread

from neatcopy.domain.rule_engine import RuleEngine
from neatcopy.infrastructure.clipboard import read_payload, write_text
from neatcopy.infrastructure.llm_client import LLMClient, classify_error

class _LLMWorker(QThread):
    succeeded = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, text: str, prompt: str, llm_config: dict, parent=None):
        super().__init__(parent)
        self._text = text
        self._prompt = prompt
        self._llm_config = llm_config

    def run(self):
        try:
            content = LLMClient().format_sync(
                self._text,
                self._prompt,
                self._llm_config,
            )
            self.succeeded.emit(content)
        except Exception as e:
            self.failed.emit(classify_error(e, timeout=self._llm_config.get('timeout', 30)))


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
        payload = read_payload()
        if payload is None:
            self.process_done.emit(False, '读取剪贴板失败，请重试')
            return
        if not payload.is_text:
            self.process_done.emit(False, '检测到图片，文本清洗与模型处理不可用')
            return
        text = payload.text or ''
        if not text.strip():
            self.process_done.emit(False, '剪贴板为空')
            return

        self.process_text(text)

    def process_text(self, text: str, mode: str | None = None, prompt_id: str | None = None):
        if text is None:
            self.process_done.emit(False, '读取剪贴板失败，请重试')
            return
        if not text.strip():
            self.process_done.emit(False, '剪贴板为空')
            return

        resolved_mode = mode or 'rules'
        if resolved_mode == 'llm':
            self._process_llm(text, prompt_id=prompt_id)
        else:
            self._process_rules(text)

    def _process_rules(self, text: str):
        self.processing_started.emit()
        try:
            rule_config = self._config.get('rules') or {}
            cleaned = RuleEngine.clean(text, rule_config)
            if write_text(cleaned):
                self.process_done.emit(True, '已清洗，可直接粘贴')
            else:
                self.process_done.emit(False, '写入剪贴板失败')
        except Exception as e:
            self.process_done.emit(False, f'清洗出错：{e}')

    def _process_llm(self, text: str, prompt_id: str | None = None):
        # 若上一次请求仍在运行，拒绝新请求，防止 QThread 被 GC 且重复触发
        if self._current_worker is not None and self._current_worker.isRunning():
            self.process_done.emit(False, '正在处理中，请稍候')
            return

        llm_config = self._config.get('llm') or {}
        if not llm_config.get('api_key'):
            self.process_done.emit(False, '请先在设置中配置 API Key')
            return

        active_id = prompt_id or llm_config.get('active_prompt_id', 'default')
        prompts = llm_config.get('prompts') or []
        prompt_obj = next((p for p in prompts if p['id'] == active_id),
                          prompts[0] if prompts else None)
        if not prompt_obj:
            self.process_done.emit(False, '未找到有效的 Prompt 模板')
            return

        self.processing_started.emit()
        worker = _LLMWorker(text, prompt_obj['content'], llm_config)
        worker.succeeded.connect(self._on_llm_success)
        worker.failed.connect(self._on_llm_error)
        worker.finished.connect(lambda: setattr(self, '_current_worker', None))
        worker.start()
        self._current_worker = worker

    def _on_llm_success(self, result: str):
        if write_text(result):
            self.process_done.emit(True, '大模型处理完成，可直接粘贴')
        else:
            self.process_done.emit(False, '写入剪贴板失败')

    def _on_llm_error(self, message: str):
        # 不写剪贴板，原文保持不变
        self.process_done.emit(False, message)
