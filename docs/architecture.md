# Architecture

NeatCopy is organized as a small layered desktop application for macOS.

## Repository Layout

- `src/main.py`: application entry point
- `src/neatcopy/app.py`: bootstrap wiring for runtime services and UI
- `src/neatcopy/application/`: application workflows such as clipboard processing, history, and settings updates
- `src/neatcopy/domain/`: text cleanup rules and pure business logic
- `src/neatcopy/infrastructure/`: OS integration and external IO such as clipboard, hotkeys, config, startup, permissions, and LLM HTTP access
- `src/neatcopy/presentation/`: tray integration and interactive UI controllers
- `src/neatcopy/presentation/ui/`: concrete PyQt UI components
- `tests/`: regression coverage for config, history, rules, wheel interactions, LLM client, and settings hotkey capture
- `assets/`: runtime images, fonts, and packaging assets

## Layer Boundaries

- `presentation` depends on `application` and selected `infrastructure` adapters
- `application` coordinates use cases and should stay free of UI code
- `domain` should remain deterministic and easy to test
- `infrastructure` contains macOS specific behavior and other side effects

## Packaging

- Development dependencies live in `requirements-dev.txt`
- Runtime dependencies live in `requirements.txt`
- macOS packaging is defined in `NeatCopy.spec`
- Build steps and macOS permission notes are documented in `BUILD_MAC.md`
