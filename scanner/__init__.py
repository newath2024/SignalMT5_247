"""Compatibility import bridge for legacy ``scanner.*`` paths.

Canonical implementations now live under ``app`` / ``domain`` / ``infra`` /
``services`` while unresolved legacy imports continue to resolve through the
``legacy.scanner`` package during migration.
"""

from pathlib import Path

_package_dir = Path(__file__).resolve().parent
_legacy_dir = _package_dir.parent / "legacy" / "scanner"
__path__ = [str(_package_dir)]
if _legacy_dir.exists():
    __path__.append(str(_legacy_dir))


def __getattr__(name: str):
    if name in {"launch", "main_loop", "parse_args"}:
        from legacy import scanner as legacy_scanner

        return getattr(legacy_scanner, name)
    raise AttributeError(name)

__all__ = ["launch", "main_loop", "parse_args"]
