# Preview State Sync and First-Open Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the LLM preview panel retain and replay the latest processing state/result while reducing first-open latency for preview and wheel windows.

**Architecture:** `main.py` owns a small preview state snapshot that is updated by processor signals whether or not the preview window exists. The preview window becomes a view over this state, and idle `QTimer.singleShot` prewarming constructs preview and wheel windows shortly after startup without showing them.

**Tech Stack:** Python 3, PyQt6 signals/widgets, pytest offscreen Qt tests, PyInstaller, Inno Setup, GitHub CLI.

## Global Constraints

- Do not change rule cleaning behavior.
- Do not import `httpx` during `import main`.
- Do not show, raise, activate, or process anything during preview or wheel prewarming.
- Keep edits scoped to preview state sync, first-open prewarming, focused tests, and release artifacts.
- Preserve existing user/unrelated worktree changes and stage only files related to this task.

---

## File Structure

- `src/main.py`: add the preview state model, state replay helper, unconditional preview signal handlers, and idle prewarming.
- `tests/test_preview_state_sync.py`: create focused offscreen tests for preview state replay and startup prewarm behavior.
- `docs/superpowers/specs/2026-07-09-preview-state-performance-design.md`: record the approved design.
- `docs/superpowers/plans/2026-07-09-preview-state-performance-plan.md`: record this implementation plan.

### Task 1: Failing Preview State Replay Tests

**Files:**
- Create: `tests/test_preview_state_sync.py`

**Interfaces:**
- Consumes: current `main.py` module import behavior.
- Produces: failing tests that require `main.create_preview_state()`, `main.record_preview_processing()`, `main.record_preview_ready()`, `main.replay_preview_state()` or equivalent public helper functions.

- [ ] **Step 1: Write the failing test file**

```python
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
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run: `python -m pytest tests/test_preview_state_sync.py -v`

Expected: FAIL because `main.create_preview_state` does not exist yet.

### Task 2: Implement Preview State Helpers

**Files:**
- Modify: `src/main.py`

**Interfaces:**
- Consumes: tests from Task 1.
- Produces:
  - `create_preview_state() -> dict`
  - `record_preview_processing(state: dict) -> None`
  - `record_preview_ready(state: dict, result: str, prompt_name: str) -> None`
  - `record_preview_failed(state: dict, error: str) -> None`
  - `replay_preview_state(preview, state: dict) -> None`

- [ ] **Step 1: Add minimal helper implementation near the top of `src/main.py` after imports**

```python
def create_preview_state() -> dict:
    return {
        'status': 'idle',
        'message': '等待处理',
        'result': '',
        'prompt_name': '',
        'error': '',
    }


def record_preview_processing(state: dict) -> None:
    state['status'] = 'processing'
    state['message'] = '处理中...'
    state['error'] = ''


def record_preview_ready(state: dict, result: str, prompt_name: str) -> None:
    state['status'] = 'done'
    state['message'] = '处理完成'
    state['result'] = result
    state['prompt_name'] = prompt_name
    state['error'] = ''


def record_preview_failed(state: dict, error: str) -> None:
    state['status'] = 'failed'
    state['message'] = f'处理失败: {error}'
    state['error'] = error


def replay_preview_state(preview, state: dict) -> None:
    if state.get('result'):
        preview.update_result(state.get('result', ''), state.get('prompt_name', ''))
    if state.get('status') in {'processing', 'failed'}:
        preview.set_status(state.get('message', '等待处理'))
```

- [ ] **Step 2: Run Task 1 tests and verify they pass**

Run: `python -m pytest tests/test_preview_state_sync.py -v`

Expected: PASS.

### Task 3: Wire State Into Runtime Signal Flow and Prewarming

**Files:**
- Modify: `src/main.py`

**Interfaces:**
- Consumes: helper functions from Task 2 and existing `ensure_preview()` / `ensure_wheel()` closures.
- Produces: runtime behavior where preview state is updated while hidden and prewarmed after startup.

- [ ] **Step 1: Import `QTimer`**

Change:

```python
from PyQt6.QtWidgets import QApplication
```

To:

```python
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
```

- [ ] **Step 2: Create preview state in `main()`**

Add after `settings_win = None`:

```python
    preview_state = create_preview_state()
```

- [ ] **Step 3: Replay state when creating preview**

Inside `ensure_preview()`, after connecting `apply_to_clipboard`, add:

```python
            replay_preview_state(preview, preview_state)
```

- [ ] **Step 4: Update preview signal handlers to always record state**

Replace the three preview handlers with:

```python
    def on_processing_started():
        record_preview_processing(preview_state)
        if preview is not None:
            replay_preview_state(preview, preview_state)

    def on_preview_ready(result: str, prompt_name: str):
        record_preview_ready(preview_state, result, prompt_name)
        if preview is not None:
            replay_preview_state(preview, preview_state)

    def on_preview_failed(error: str):
        record_preview_failed(preview_state, error)
        if preview is not None:
            replay_preview_state(preview, preview_state)
```

- [ ] **Step 5: Schedule idle prewarm after all signal connections**

Add before `sys.exit(app.exec())`:

```python
    QTimer.singleShot(0, ensure_preview)
    QTimer.singleShot(200, ensure_wheel)
```

- [ ] **Step 6: Run preview tests**

Run: `python -m pytest tests/test_preview_state_sync.py tests/test_lazy_imports.py -v`

Expected: PASS and `test_main_import_does_not_import_httpx` remains green.

### Task 4: Full Verification and Release Build

**Files:**
- Modify by build commands: `build/`, `dist/NeatCopy.exe`, `installer/Output/NeatCopy_Setup_v2.0.5.exe`

**Interfaces:**
- Consumes: source and tests from prior tasks.
- Produces: verified portable executable and installer.

- [ ] **Step 1: Run full automated tests**

Run: `python -m pytest tests -v`

Expected: all tests PASS.

- [ ] **Step 2: Build portable executable**

Run: `pyinstaller NeatCopy.spec --noconfirm`

Expected: exit code 0 and `dist/NeatCopy.exe` exists.

- [ ] **Step 3: Build installer**

Run: `ISCC installer/NeatCopy_Setup.iss`

Expected: exit code 0 and `installer/Output/NeatCopy_Setup_v2.0.5.exe` exists.

- [ ] **Step 4: Inspect git status**

Run: `git status --short`

Expected: source/test/docs changes and refreshed build artifacts are visible; unrelated pre-existing changes are not reverted.

### Task 5: Commit, Push, and GitHub Release

**Files:**
- Stage: `src/main.py`, `tests/test_preview_state_sync.py`, design/plan docs, release artifacts produced by the build.

**Interfaces:**
- Consumes: verified working tree from Task 4.
- Produces: pushed commit and GitHub release assets.

- [ ] **Step 1: Stage only task-related files**

Run:

```bash
git add src/main.py tests/test_preview_state_sync.py docs/superpowers/specs/2026-07-09-preview-state-performance-design.md docs/superpowers/plans/2026-07-09-preview-state-performance-plan.md dist/NeatCopy.exe installer/Output/NeatCopy_Setup_v2.0.5.exe
```

- [ ] **Step 2: Commit**

Run:

```bash
git commit -m "fix(preview): retain latest llm state and prewarm popups"
```

- [ ] **Step 3: Push**

Run: `git push origin master`

- [ ] **Step 4: Create or update release**

Run:

```bash
gh release view v2.0.5 --repo StoneLL1/NeatCopy
```

If the release exists, upload with clobber:

```bash
gh release upload v2.0.5 dist/NeatCopy.exe installer/Output/NeatCopy_Setup_v2.0.5.exe --repo StoneLL1/NeatCopy --clobber
```

If the release does not exist, create it:

```bash
gh release create v2.0.5 dist/NeatCopy.exe installer/Output/NeatCopy_Setup_v2.0.5.exe --repo StoneLL1/NeatCopy --title "NeatCopy v2.0.5" --notes "Fix preview panel state sync and prewarm prompt wheel/preview windows for faster first open."
```
