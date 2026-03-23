# Liquidity Sniper

Local desktop trading signal app for MT5. The trading and scanner behavior stays the same, but the repository is now organized around clear application, domain, infrastructure, UI, and legacy boundaries.

## Strategy

- HTF: `H1`, `H4`
- HTF context: `OB`, `FVG`, `Previous Day High/Low`, `Previous Week High/Low`, session liquidity
- LTF: `M3`, `M5`, `M15`
- LTF confirmation: liquidity sweep + MSS + strict iFVG
- Entry: first edge of iFVG
- SL: high/low of the origin candle
- Alerts: Telegram

## Features

- Desktop UI built with `PySide6`
- Scanner engine runs off the UI thread
- 2-stage flow: `WATCH ARMED` -> `CONFIRMED SIGNAL`
- Persistent runtime state after restart
- SQLite history for signals, alerts, and rejections
- Structured logs to console and `logs/app.log`
- Cooldown and signal-key deduplication
- Portable MT5 launcher flow for Windows deployments
- Build outputs for portable `.exe` and Windows installer

## Repository Layout

- [`app/`](./app) -> application bootstrap, controller wiring, runtime coordination
- [`app/runtime/`](./app/runtime) -> scanner engine runtime loop
- [`domain/`](./domain) -> detectors, strategy engine, reasoning, domain models and enums
- [`infra/config/`](./infra/config) -> config loading, constants, runtime path helpers
- [`infra/mt5/`](./infra/mt5) -> MT5 runtime lifecycle and data gateway adapters
- [`infra/storage/`](./infra/storage) -> SQLite and runtime state persistence
- [`infra/telegram/`](./infra/telegram) -> Telegram transport integrations
- [`services/`](./services) -> orchestration use cases such as scanning, alerts, and command services
- [`ui/`](./ui) -> PySide6 desktop presentation layer
- [`legacy/scanner/`](./legacy/scanner) -> original scanner pipeline kept during migration
- [`scanner/`](./scanner) -> compatibility shim forwarding old `scanner.*` imports into `legacy/scanner/`
- [`scripts/`](./scripts) -> build and helper scripts
- [`packaging/`](./packaging) -> PyInstaller spec and installer definitions
- [`assets/`](./assets) -> icons, branding, and version metadata
- [`scripts/portable/`](./scripts/portable) -> portable runtime launch and health-check helpers
- [`tools/portable/`](./tools/portable) -> backward-compatible wrappers for older portable script paths

## Legacy Notes

The original scanner package still exists under [`legacy/scanner/`](./legacy/scanner) because it powers the live setup pipeline and remains risky to rewrite in one pass.

New work should go here instead:

- add or refine trading logic in [`domain/`](./domain)
- add orchestration workflows in [`services/`](./services)
- add adapters in [`infra/`](./infra)
- add UI widgets or presentation changes in [`ui/`](./ui)

The root [`scanner/`](./scanner) package now exists only to preserve older import paths while the migration settles.
When new layers still need the old pipeline, they should go through [`legacy/bridges/`](./legacy/bridges) instead of importing deep legacy modules directly.

## Run

Requirements:

- Windows
- MetaTrader 5 installed or bundled in portable mode and logged in to the broker
- Python 3.12 to run from source or build
- `MetaTrader5`
- `PySide6`

Run the desktop app:

```bash
python main.py
```

Run the portable Windows bundle:

```text
run.bat
```

Open the app without auto-starting the scanner:

```bash
python main.py --no-autostart
```

Run one scan cycle and exit:

```bash
python main.py --once
```

Run headless:

```bash
python main.py --headless
```

Override the loop interval:

```bash
python main.py --interval 30
```

Portable deployment instructions:

```text
prepare_portable.md
```

## Config

- Default config: [`config/default.json`](./config/default.json)
- User override: [`config/user.json`](./config/user.json)
- Secrets: local `.env` created from [`.env.example`](./.env.example)

Security note:

- `.env` is intentionally ignored by git and should never be committed.
- Build outputs no longer bundle the real `.env` file into `dist/` or the installer.
- Provision Telegram secrets privately on the target machine after deployment.

Current config assumptions:

- `entry_model = ifvg_first_edge`
- `sl_model = origin_candle_extreme`
- `strict_ifvg = true`

## Runtime Data

By default the app creates runtime folders at:

```text
%LOCALAPPDATA%\OpenClaw\
  config\
  data\
  logs\
```

Those hold:

- `config/.env`
- `config/user.json`
- `data/runtime_state.json`
- `data/history.db`
- `logs/app.log`

When launched via `run.bat`, the portable launcher redirects runtime paths into the bundle:

```text
project_root\runtime\
project_root\logs\
```

## Build

Root build commands remain available for compatibility, but the real build assets now live under [`scripts/`](./scripts) and [`packaging/`](./packaging).

Build the portable exe:

```bash
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

Build the installer:

```bash
powershell -ExecutionPolicy Bypass -File .\build_installer.ps1
```

Outputs:

- Portable: [`dist/OpenClawScanner/`](./dist/OpenClawScanner)
- Installer: [`dist/installer/OpenClawScannerSetup.exe`](./dist/installer/OpenClawScannerSetup.exe)

The build includes `.env.example` for reference only. Real secrets must be supplied privately as `.env` after deployment.

## Notes

- The scanner retries around temporary MT5 readiness issues instead of killing the whole app immediately.
- Telegram is optional, but MT5 is required.
- Runtime state can be reset with [`reset_state.bat`](./reset_state.bat) or `ResetScannerState.bat` inside the portable bundle.
