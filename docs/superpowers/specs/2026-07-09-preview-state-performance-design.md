# Preview State Sync and First-Open Performance Design

Date: 2026-07-09

## Goal

Fix three related LLM preview and prompt wheel issues:

- First open of the prompt wheel and preview panel should feel immediate after app startup.
- If AI processing finishes while the preview panel is closed, opening the panel later should show the latest result.
- The preview panel should show "processing", "done", and "failed" states promptly, even when the panel is created or shown after the state transition happened.

## Root Cause

The current app keeps `WheelWindow` and `PreviewWindow` fully lazy. `main.py` imports and constructs each window only on first use. That keeps startup light, but moves module import, Qt widget construction, DWM setup, and animation setup into the first user interaction.

The preview signal handlers in `main.py` only update the UI when `preview is not None and preview.isVisible()`. This discards `processing_started`, `preview_ready`, and `preview_failed` events while the panel is hidden or not yet constructed. The current `PreviewWindow` has local state, but there is no application-level preview state that can be replayed when the window appears.

## Chosen Approach

Use an application-level preview state snapshot and idle prewarming.

`main.py` will own a small state object with:

- `status`: one of `idle`, `processing`, `done`, `failed`
- `message`: the user-facing status text
- `result`: the latest LLM result text
- `prompt_name`: the prompt name for the latest result
- `error`: the latest failure message

Processor signals update this state unconditionally. If the preview window exists, the same handler also applies the state to the window. Opening or creating the preview window replays the latest state before showing it.

After the Qt event loop starts, `QTimer.singleShot` will prewarm `PreviewWindow` and `WheelWindow` during idle time. Prewarming creates the widgets but does not show them, trigger processing, read the clipboard, or change the user's active window.

## Detailed Behavior

### Preview State

When LLM work starts, `processor.processing_started` sets the preview state to:

- `status = "processing"`
- `message = "处理中..."`
- `result` and `prompt_name` remain unchanged so the old result stays available until a new one succeeds or fails.

When LLM work succeeds, `processor.preview_ready(result, prompt_name)` sets:

- `status = "done"`
- `message = "处理完成"`
- `result = result`
- `prompt_name = prompt_name`
- `error = ""`

When LLM work fails, `processor.preview_failed(error)` sets:

- `status = "failed"`
- `message = f"处理失败: {error}"`
- `error = error`
- The last successful `result` remains in the editor instead of being replaced by an error string.

If the preview panel is first opened after any of these transitions, `ensure_preview()` applies the stored state immediately.

### Preview Window API

`PreviewWindow` already exposes `update_result(result, prompt_name)` and `set_status(status)`. The initial implementation can replay state from `main.py` using those methods. If tests show direct replay needs cleaner boundaries, add a small helper in `main.py`, not a large new class in the UI layer.

### Prewarming

`main.py` schedules prewarming after signal connections are established:

- `QTimer.singleShot(0, ensure_preview)`
- `QTimer.singleShot(200, ensure_wheel)`

The exact delay can change if tests or manual startup behavior show a better order. The important constraints are:

- Do not construct these windows before `QApplication` exists.
- Do not call `show()`, `activateWindow()`, `raise_()`, or any processing action during prewarm.
- Keep imports lazy at module import time so `import main` still does not import network-only dependencies such as `httpx`.

## Files

- `src/main.py`: add preview state snapshot, replay helper, unconditional signal handling, idle prewarm timers.
- `tests/test_preview_state_sync.py`: add offscreen tests for hidden-window result replay and processing state replay.
- `docs/superpowers/plans/2026-07-09-preview-state-performance-plan.md`: implementation plan.

## Testing

Automated tests:

- A test where preview is not created when `preview_ready` arrives, then opening preview shows the latest result and prompt.
- A test where `processing_started` arrives before preview exists, then opening preview shows "处理中...".
- A test that `main` import remains lazy enough that `httpx` is not imported.
- Existing tests via `python -m pytest tests -v`.

Manual verification:

- Start the app from source.
- Open preview panel first time and verify it appears without noticeable construction delay after startup idle.
- Trigger LLM processing with preview closed, open preview after completion, and verify latest content appears.
- Trigger LLM processing with preview open and verify the status changes to processing and then done or failed.
- Open prompt wheel first time after startup idle and verify it appears promptly.

## Packaging and Release

After tests and manual checks:

- Build portable executable with the existing PyInstaller spec.
- Build installer with `installer/NeatCopy_Setup.iss`.
- Commit source, tests, docs, and refreshed release artifacts needed for the release.
- Push the branch to `origin`.
- Create or update the GitHub release for the selected version and upload both `dist/NeatCopy.exe` and `installer/Output/NeatCopy_Setup_v<version>.exe`.
