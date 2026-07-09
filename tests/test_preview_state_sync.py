import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import main


class DummyPreview:
    def __init__(self):
        self.statuses = []
        self.results = []

    def set_status(self, status):
        self.statuses.append(status)

    def update_result(self, result, prompt_name):
        self.results.append((result, prompt_name))


def test_replays_latest_result_when_preview_created_after_llm_success():
    state = main.create_preview_state()
    main.record_preview_ready(state, "new result", "Translate")

    preview = DummyPreview()
    main.replay_preview_state(preview, state)

    assert preview.results == [("new result", "Translate")]
    assert preview.statuses == []


def test_replays_processing_status_when_preview_created_after_start():
    state = main.create_preview_state()
    main.record_preview_processing(state)

    preview = DummyPreview()
    main.replay_preview_state(preview, state)

    assert preview.results == []
    assert preview.statuses == ["处理中..."]


def test_failed_state_keeps_last_successful_result_visible():
    state = main.create_preview_state()
    main.record_preview_ready(state, "previous result", "Summary")
    main.record_preview_failed(state, "timeout")

    preview = DummyPreview()
    main.replay_preview_state(preview, state)

    assert preview.results == [("previous result", "Summary")]
    assert preview.statuses == ["处理失败: timeout"]
