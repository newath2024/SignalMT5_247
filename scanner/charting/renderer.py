import tempfile
from pathlib import Path

from ..config import CHART_WINDOWS
from ..deps import CHARTING_AVAILABLE, Rectangle, plt
from .annotations import configure_chart_axes, draw_candles, draw_reference_level, get_chart_window


def render_htf_chart(snapshot, signal, output_path):
    zone = signal.get("htf_zone")
    timeframe_name = signal.get("htf_chart_timeframe")
    if not CHARTING_AVAILABLE or zone is None or timeframe_name not in ("H1", "H4"):
        return False

    rates = snapshot["rates"][timeframe_name]
    window_rates, _ = get_chart_window(rates, [len(rates) - 1], timeframe_name, CHART_WINDOWS)
    if window_rates is None or len(window_rates) < 20:
        return False

    figure, ax = plt.subplots(figsize=(14, 7), dpi=150)
    configure_chart_axes(ax, window_rates, f"{snapshot['symbol']} {timeframe_name} - HTF Context")
    draw_candles(ax, window_rates, snapshot["point"])

    zone_color = "#38bdf8" if zone["bias"] == "Long" else "#f59e0b"
    ax.axhspan(zone["low"], zone["high"], color=zone_color, alpha=0.18, zorder=1)
    ax.axhline(snapshot["current_price"], color="#e2e8f0", linestyle=":", linewidth=1.0)
    ax.text(
        len(window_rates) - 1.0,
        zone["high"],
        f" {zone['label']}",
        color="#f8fafc",
        fontsize=10,
        va="bottom",
        ha="right",
        bbox={"facecolor": zone_color, "alpha": 0.35, "edgecolor": zone_color, "pad": 3},
    )

    figure.tight_layout()
    figure.savefig(output_path, bbox_inches="tight")
    plt.close(figure)
    return True


def render_ltf_chart(snapshot, signal, output_path):
    timeframe_name = signal.get("timeframe")
    sweep_index = signal.get("sweep_index")
    mss_index = signal.get("mss_index")
    ifvg_source_index = signal.get("ifvg_source_index")
    ifvg_origin_candle_index = signal.get("ifvg_origin_candle_index")
    liquidity_map = signal.get("liquidity_map", {})
    swept_liquidity = signal.get("swept_liquidity", [])
    if CHARTING_AVAILABLE is False or None in (sweep_index, mss_index, ifvg_source_index):
        return False
    if not swept_liquidity:
        return False

    rates = snapshot["rates"][timeframe_name]
    window_rates, window_start = get_chart_window(
        rates,
        [
            value
            for value in (sweep_index, mss_index, ifvg_source_index, ifvg_origin_candle_index, len(rates) - 1)
            if value is not None
        ],
        timeframe_name,
        CHART_WINDOWS,
    )
    if window_rates is None or len(window_rates) < 20:
        return False

    sweep_x = sweep_index - window_start
    mss_x = mss_index - window_start
    ifvg_x = ifvg_source_index - window_start
    origin_x = ifvg_origin_candle_index - window_start if ifvg_origin_candle_index is not None else None
    if min(sweep_x, mss_x, ifvg_x) < 0:
        return False

    figure, ax = plt.subplots(figsize=(16, 8), dpi=150)
    configure_chart_axes(ax, window_rates, f"{snapshot['symbol']} {timeframe_name} - LTF Trigger")
    draw_candles(ax, window_rates, snapshot["point"])

    line_palette = {
        "PDH": "#3b82f6",
        "PDL": "#3b82f6",
        "PWH": "#a855f7",
        "PWL": "#a855f7",
        "ASH": "#ef4444",
        "ASL": "#ef4444",
        "LOH": "#f97316",
        "LOL": "#16a34a",
    }
    for label, value in liquidity_map.items():
        style = "--" if label in swept_liquidity else ":"
        draw_reference_level(ax, value, label, line_palette.get(label, "#94a3b8"), style)

    ifvg_color = "#22c55e" if signal["bias"] == "Long" else "#f97316"
    ifvg_width = len(window_rates) - ifvg_x
    ifvg_box = Rectangle(
        (ifvg_x - 0.5, signal["entry_low"]),
        ifvg_width,
        max(signal["entry_high"] - signal["entry_low"], snapshot["point"] * 3),
        facecolor=ifvg_color,
        edgecolor=ifvg_color,
        linewidth=1.2,
        alpha=0.18,
        zorder=1,
    )
    ax.add_patch(ifvg_box)

    sweep_price = signal["sweep_price"]
    mss_price = float(rates["close"][mss_index])
    ax.scatter([sweep_x], [sweep_price], color="#facc15", s=55, zorder=5)
    ax.annotate(
        f"Sweep ({', '.join(swept_liquidity)})",
        xy=(sweep_x, sweep_price),
        xytext=(sweep_x + 2, sweep_price),
        color="#f8fafc",
        arrowprops={"arrowstyle": "->", "color": "#facc15"},
        fontsize=10,
    )

    ax.scatter([mss_x], [mss_price], color="#e879f9", s=55, zorder=5)
    ax.annotate(
        "MSS",
        xy=(mss_x, mss_price),
        xytext=(mss_x + 2, mss_price),
        color="#f8fafc",
        arrowprops={"arrowstyle": "->", "color": "#e879f9"},
        fontsize=10,
    )

    ax.text(
        ifvg_x + 1,
        signal["entry_high"],
        "iFVG",
        color="#f8fafc",
        fontsize=10,
        va="bottom",
        bbox={"facecolor": ifvg_color, "alpha": 0.35, "edgecolor": ifvg_color, "pad": 3},
    )
    ax.axhline(signal["entry_price"], color="#38bdf8", linestyle="-.", linewidth=1.0)
    ax.axhline(signal["stop_loss"], color="#ef4444", linestyle="--", linewidth=1.0)
    ax.axhline(signal["tp1"], color="#22c55e", linestyle="--", linewidth=1.0)

    if origin_x is not None and origin_x >= 0:
        origin_price = (
            signal["ifvg_origin_candle_low"]
            if signal["bias"] == "Long"
            else signal["ifvg_origin_candle_high"]
        )
        ax.scatter([origin_x], [origin_price], color="#ef4444", s=45, zorder=5)
        ax.annotate(
            "Origin stop",
            xy=(origin_x, origin_price),
            xytext=(origin_x + 2, origin_price),
            color="#f8fafc",
            arrowprops={"arrowstyle": "->", "color": "#ef4444"},
            fontsize=10,
        )

    figure.tight_layout()
    figure.savefig(output_path, bbox_inches="tight")
    plt.close(figure)
    return True


def build_signal_charts(snapshot, signal):
    if not CHARTING_AVAILABLE:
        return None

    required_fields = [
        "htf_zone",
        "htf_chart_timeframe",
        "timeframe",
        "sweep_index",
        "mss_index",
        "ifvg_source_index",
        "entry_low",
        "entry_high",
        "entry_price",
        "sweep_price",
        "tp1",
        "stop_loss",
        "swept_liquidity",
        "liquidity_map",
    ]
    if any(signal.get(field) is None for field in required_fields):
        return None

    temp_dir = Path(tempfile.gettempdir())
    htf_file = tempfile.NamedTemporaryFile(delete=False, suffix="_htf.png", dir=temp_dir)
    ltf_file = tempfile.NamedTemporaryFile(delete=False, suffix="_ltf.png", dir=temp_dir)
    htf_path = Path(htf_file.name)
    ltf_path = Path(ltf_file.name)
    htf_file.close()
    ltf_file.close()

    htf_ok = render_htf_chart(snapshot, signal, htf_path)
    ltf_ok = render_ltf_chart(snapshot, signal, ltf_path)
    if not htf_ok or not ltf_ok:
        for path in (htf_path, ltf_path):
            if path.exists():
                path.unlink(missing_ok=True)
        return None

    return {"htf": htf_path, "ltf": ltf_path}
