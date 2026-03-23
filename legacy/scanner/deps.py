import sys

try:
    import MetaTrader5 as mt5
except ImportError as exc:
    install_cmd = f'"{sys.executable}" -m pip install MetaTrader5'
    raise SystemExit(
        "MetaTrader5 is not installed for this interpreter.\n"
        f"Python: {sys.executable}\n"
        f"Run: {install_cmd}"
    ) from exc

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    CHARTING_AVAILABLE = True
except ImportError:
    plt = None
    Rectangle = None
    CHARTING_AVAILABLE = False
