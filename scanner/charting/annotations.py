import datetime as dt

from ..deps import Rectangle


def get_chart_window(rates, focus_indices, timeframe_name, chart_windows):
    if rates is None or len(rates) == 0:
        return None, 0

    window = chart_windows[timeframe_name]
    focus_min = min(focus_indices) if focus_indices else len(rates) - 1
    focus_max = max(focus_indices) if focus_indices else len(rates) - 1
    start = max(0, focus_min - window // 3)
    end = min(len(rates), max(focus_max + window // 3, start + window))

    if end - start < window:
        start = max(0, end - window)

    return rates[start:end], start


def configure_chart_axes(ax, window_rates, title):
    times = [dt.datetime.fromtimestamp(int(item)) for item in window_rates["time"]]
    x_positions = list(range(len(window_rates)))
    step = max(1, len(window_rates) // 6)
    tick_positions = x_positions[::step]
    tick_labels = [times[index].strftime("%m-%d\n%H:%M") for index in tick_positions]

    ax.set_title(title, fontsize=12, weight="bold")
    ax.set_facecolor("#0f172a")
    ax.figure.set_facecolor("#0f172a")
    ax.grid(True, color="#334155", linestyle="--", linewidth=0.5, alpha=0.4)
    ax.tick_params(colors="#e2e8f0")
    for spine in ax.spines.values():
        spine.set_color("#475569")

    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, color="#cbd5e1", fontsize=8)
    ax.yaxis.set_tick_params(labelcolor="#cbd5e1")
    ax.set_xlim(-1, len(window_rates))


def draw_candles(ax, window_rates, point):
    highs = window_rates["high"]
    lows = window_rates["low"]
    opens = window_rates["open"]
    closes = window_rates["close"]
    y_span = float(highs.max() - lows.min())
    min_body = max(y_span * 0.002, point * 2)

    for index in range(len(window_rates)):
        open_price = float(opens[index])
        close_price = float(closes[index])
        high_price = float(highs[index])
        low_price = float(lows[index])
        color = "#22c55e" if close_price >= open_price else "#ef4444"
        ax.vlines(index, low_price, high_price, color=color, linewidth=1.1, zorder=2)
        body_low = min(open_price, close_price)
        body_height = max(abs(close_price - open_price), min_body)
        body = Rectangle(
            (index - 0.32, body_low),
            0.64,
            body_height,
            facecolor=color,
            edgecolor=color,
            linewidth=1.0,
            alpha=0.9,
            zorder=3,
        )
        ax.add_patch(body)


def draw_reference_level(ax, value, label, color, line_style="-"):
    ax.axhline(value, color=color, linestyle=line_style, linewidth=1.0, alpha=0.9, zorder=1.5)
    ax.text(
        ax.get_xlim()[1] - 0.4,
        value,
        f" {label}",
        color="#f8fafc",
        fontsize=9,
        va="center",
        ha="left",
        bbox={"facecolor": color, "alpha": 0.25, "edgecolor": color, "pad": 2},
    )
