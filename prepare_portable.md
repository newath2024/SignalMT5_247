# OpenClaw Portable MT5 Deployment

This bundle is designed for Windows-only deployment with a local portable MT5 terminal.

## Final structure

```text
project_root/
  .venv/                   # optional local Python runtime prepared on the source machine
  python_embedded/         # optional alternative to .venv for a more portable Python runtime
  mt5_portable/
    terminal64.exe
    ...
  runtime/
    config/
    data/
  logs/
  tools/
    portable/
      launch_portable.py
      health_check.py
      env_loader.py
  portable.env
  run.bat
  restart_bot.bat
  first_run_check.bat
  prepare_portable.md
  ... existing bot source files ...
```

`runtime/` and `logs/` are created automatically when you run the launcher.

## What this setup does

`run.bat` performs this flow:

1. Uses the local Python runtime from `.venv\Scripts\python.exe` or `python_embedded\python.exe`
2. Launches `mt5_portable\terminal64.exe /portable`
3. Waits until the MT5 terminal is actually ready
4. Verifies that a saved MT5 login/session exists
5. Starts `restart_bot.bat`
6. `restart_bot.bat` runs the bot and restarts it if it exits unexpectedly

## Source-machine preparation

### 1. Prepare the portable MT5 folder

Place a full MT5 terminal under:

```text
project_root\mt5_portable\
```

Required file:

```text
project_root\mt5_portable\terminal64.exe
```

The launcher always starts MT5 with:

```text
terminal64.exe /portable
```

That keeps MT5 runtime files inside the portable MT5 folder instead of the normal user profile as much as MT5 allows.

### 2. Prepare the Python runtime

Recommended for this repo:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-portable.txt
```

Important:

- Copying a Windows `.venv` to another PC can work if the target machine is very similar, but it is not guaranteed across every Windows/Python installation.
- If you want the most portable source-based bundle, put the official Windows embeddable Python distribution into `python_embedded\` and let `run.bat` use that.
- The scripts already support both `.venv` and `python_embedded`.

### 3. Login to MT5 once in portable mode

Run:

```text
run.bat
```

Or run this once for an isolated check:

```text
first_run_check.bat
```

If the terminal opens but the bot does not start because no session is available:

1. Open `project_root\mt5_portable\terminal64.exe` manually
2. Make sure you launch it with portable mode:
   `terminal64.exe /portable`
3. Login to your broker account
4. Tick `Save password`
5. Confirm the account is actually connected and receiving prices
6. Close MT5 cleanly
7. Run `run.bat` again

### 4. Preserve the saved MT5 session

Do not delete the MT5 data folders that portable mode creates under `mt5_portable\`.

The exact subfolders can vary by MT5 build/broker, but in portable mode you must preserve the full contents of the `mt5_portable\` folder after you logged in successfully.

Practically:

- Keep the entire `mt5_portable\` directory
- Do not copy only `terminal64.exe`
- Do not remove `config`, `bases`, `profiles`, or other data folders created by MT5

If MT5 does not auto-login on the new machine:

- Re-open the MT5 terminal from `mt5_portable\terminal64.exe /portable`
- Check whether the remembered account/server are still present
- Login once again manually and tick `Save password`
- Close MT5 and retry `run.bat`

## What to copy to the target machine

Copy the entire project folder, including:

- source files
- `.venv` or `python_embedded`
- `mt5_portable`
- `.env` if you use Telegram secrets there
- `portable.env`
- `run.bat`, `restart_bot.bat`, `first_run_check.bat`

Do not copy only the source code.

The app can still reuse the root `.env` on first run because the runtime loader copies legacy root secrets into `runtime\config\.env` when needed.

## Target-machine run steps

On the destination Windows PC or VPS:

1. Copy the whole folder
2. Double-click `run.bat`
3. Wait for MT5 to launch
4. If a saved session exists, the bot will start automatically
5. If the bot crashes, `restart_bot.bat` will restart it

## Runtime paths in portable mode

When launched by `run.bat`, the app uses relative portable paths:

- app config/state:
  `project_root\runtime\config\`
  `project_root\runtime\data\`
- launcher log:
  `project_root\logs\launcher.log`
- supervisor log:
  `project_root\logs\supervisor.log`
- app log:
  `project_root\logs\app.log`

No absolute `C:\...` path is required by the launcher setup.

## Useful config toggles

Edit `portable.env` if needed:

```text
OPENCLAW_MT5_TERMINAL=mt5_portable\terminal64.exe
OPENCLAW_MT5_WINDOW_MODE=normal
OPENCLAW_MT5_START_TIMEOUT_SEC=90
OPENCLAW_MT5_INIT_RETRIES=15
OPENCLAW_MT5_INIT_RETRY_DELAY_SEC=3
OPENCLAW_MT5_REQUIRE_SAVED_SESSION=true
OPENCLAW_MT5_TICK_MAX_AGE_SEC=0
OPENCLAW_BOT_RUN_MODE=headless
OPENCLAW_BOT_RESTART_DELAY_SEC=10
```

Window mode values:

- `normal`
- `minimize`
- `hide`

Default is `normal`.

`hide` is supported but less safe on Windows than `minimize`.

## Health check

Run:

```text
first_run_check.bat
```

Or manually:

```text
.\.venv\Scripts\python.exe .\tools\portable\health_check.py --launch
```

This verifies:

- the MT5 portable terminal exists
- `mt5.initialize()` works
- a saved session is available
- the configured probe symbol can provide tick data if a symbol is defined

## Notes for unattended usage

- `restart_bot.bat` restarts the bot process if it exits with a non-zero exit code
- headless mode is the best default for Windows VPS
- if you want the UI instead, set:
  `OPENCLAW_BOT_RUN_MODE=desktop`
- if you want Windows auto-start, create a Task Scheduler task that runs `run.bat` at logon

## Limitations

- MT5 saved login portability depends on what the broker terminal stores in portable mode; most of the time copying the full portable folder is enough, but some brokers/builds may still require one manual login on the new machine
- a copied `.venv` is not guaranteed to be portable across all Windows machines
- hiding MT5 is riskier than minimizing it, so `normal` or `minimize` is safer for production
