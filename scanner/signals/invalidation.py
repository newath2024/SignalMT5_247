from ..utils import format_price


def build_invalidation_lines(bias, timeframe_name, stop_loss, digits, zone_label):
    if bias == "Long":
        return [
            f"{timeframe_name} closes below iFVG origin low {format_price(stop_loss, digits)}",
            f"Price accepts below HTF zone {zone_label}",
        ]

    return [
        f"{timeframe_name} closes above iFVG origin high {format_price(stop_loss, digits)}",
        f"Price accepts above HTF zone {zone_label}",
    ]
