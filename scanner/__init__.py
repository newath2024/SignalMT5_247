from .app import main_loop


def launch(*args, **kwargs):
    from app.bootstrap import main

    return main(*args, **kwargs)


def parse_args(*args, **kwargs):
    from app.bootstrap import parse_args as _parse_args

    return _parse_args(*args, **kwargs)


__all__ = ["launch", "main_loop", "parse_args"]
