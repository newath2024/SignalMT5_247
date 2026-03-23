"""Legacy scanner pipeline kept for compatibility during the repo migration.

The package intentionally avoids eager imports so the new architecture can
import individual legacy modules without pulling the full runtime graph.
"""


def main_loop(*args, **kwargs):
    from .app import main_loop as _main_loop

    return _main_loop(*args, **kwargs)


def launch(*args, **kwargs):
    from app.bootstrap import main

    return main(*args, **kwargs)


def parse_args(*args, **kwargs):
    from app.bootstrap import parse_args as _parse_args

    return _parse_args(*args, **kwargs)


__all__ = ["launch", "main_loop", "parse_args"]
