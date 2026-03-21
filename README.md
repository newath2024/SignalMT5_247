# OpenClaw Scanner

Local desktop trading signal app cho MT5, duoc refactor theo huong production-grade nhung van chay local.

Logic detect hien tai duoc giu nguyen trong [`scanner/`](./scanner). Lop moi chi bo sung architecture, UI desktop, persistent state, logging, SQLite history, va packaging.

## Strategy

- HTF: `H1`, `H4`
- HTF context: `OB`, `FVG`, `Previous Day High/Low`, `Previous Week High/Low`
- LTF: `M3`, `M5`, `M15`
- LTF confirmation: liquidity sweep + MSS + strict iFVG
- Entry: first edge of iFVG
- SL: high/low cua candle tao ra iFVG
- Alerts: Telegram

## App Features

- Desktop UI bang `PySide6`
- Scanner engine chay thread rieng, UI khong block
- 2-stage pipeline: `WATCH ARMED` -> `CONFIRMED SIGNAL`
- Persistent state sau restart
- SQLite history cho signals, alerts, rejection history
- Structured logging ra console va `logs/app.log`
- Cooldown + dedup theo signal key
- Build duoc ra portable `.exe` va installer Windows

## Architecture

- [`ui/`](./ui) -> desktop UI
- [`app/`](./app) -> app controller va bootstrap
- [`engine/`](./engine) -> scanner engine
- [`data/`](./data) -> MT5 gateway
- [`detectors/`](./detectors) -> wrapper detect thuần quanh logic cu
- [`strategy/`](./strategy) -> ghep HTF + LTF + signal pipeline
- [`services/`](./services) -> scan service, alert orchestration
- [`storage/`](./storage) -> SQLite + runtime state
- [`notifiers/`](./notifiers) -> Telegram notifier
- [`core/`](./core) -> config, paths, logging, enums
- [`scanner/`](./scanner) -> legacy strategy logic goc

## Run

Yeu cau:

- Windows
- MetaTrader 5 da cai va login broker
- Python 3.12 de build
- `MetaTrader5` package
- `PySide6` package neu chay tu source

Chay desktop app:

```bash
python main.py
```

Mo app nhung chua auto start scanner:

```bash
python main.py --no-autostart
```

Chay 1 scan cycle roi thoat:

```bash
python main.py --once
```

Chay headless:

```bash
python main.py --headless
```

Override loop interval:

```bash
python main.py --interval 30
```

## Config

- Default config: [`config/default.json`](./config/default.json)
- User override: [`config/user.json`](./config/user.json)
- Secrets: `.env`

Config hien tai chi support:

- `entry_model = ifvg_first_edge`
- `sl_model = origin_candle_extreme`
- `strict_ifvg = true`

## Runtime Data

Luc app chay, no se tao runtime folders tai:

```text
%LOCALAPPDATA%\OpenClaw\
  config\
  data\
  logs\
```

Thu muc nay chua:

- `config/.env`
- `config/user.json`
- `data/runtime_state.json`
- `data/history.db`
- `logs/app.log`

## Build

Build portable exe:

```bash
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

Build installer:

```bash
powershell -ExecutionPolicy Bypass -File .\build_installer.ps1
```

Outputs:

- Portable: [`dist/OpenClawScanner/`](./dist/OpenClawScanner)
- Installer: [`dist/installer/OpenClawScannerSetup.exe`](./dist/installer/OpenClawScannerSetup.exe)

## Notes

- Scanner se khong crash toan app neu 1 symbol loi.
- Telegram la optional, nhung MT5 la bat buoc.
- Ban co the reset runtime state bang [`reset_state.bat`](./reset_state.bat) hoac `ResetScannerState.bat` trong bundle portable.
