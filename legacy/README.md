# Legacy Modules

`legacy/scanner/` contains the original MT5 scanner pipeline that still powers parts of the live product.

It remains in the repository for compatibility and incremental migration only.

New work should prefer these locations:

- `domain/` for strategy, detectors, scoring, and setup reasoning
- `infra/` for MT5, Telegram, config, and storage adapters
- `services/` for scan/alert/use-case orchestration
- `ui/` for PySide6 presentation

When the new architecture still needs something from the old scanner, prefer going through
`legacy/bridges/` instead of importing deep `legacy.scanner.*` modules directly.

The root `scanner/` package now exists only as a compatibility shim that forwards imports into `legacy/scanner/`.
