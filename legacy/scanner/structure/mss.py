from ..config.ltf import (
    LTF_MSS_MIN_BREAK_POINTS,
    LTF_MSS_MIN_BREAK_RANGE_RATIO,
    LTF_MSS_QUALITY_BASE,
    LTF_MSS_QUALITY_BODY_SCALE,
    LTF_MSS_QUALITY_BREAK_SCALE,
)
from ..utils import body_strength, clamp


def detect_mss_break(rates, bias, structure_level, avg_range, point, start_index, end_index):
    opens = rates["open"]
    closes = rates["close"]

    for index in range(start_index, min(len(rates), end_index)):
        if bias == "Long":
            break_distance = float(closes[index]) - structure_level
            valid_break = (
                break_distance > max(avg_range * LTF_MSS_MIN_BREAK_RANGE_RATIO, point * LTF_MSS_MIN_BREAK_POINTS)
                and float(closes[index]) > float(opens[index])
            )
        else:
            break_distance = structure_level - float(closes[index])
            valid_break = (
                break_distance > max(avg_range * LTF_MSS_MIN_BREAK_RANGE_RATIO, point * LTF_MSS_MIN_BREAK_POINTS)
                and float(closes[index]) < float(opens[index])
            )

        if not valid_break:
            continue

        mss_quality = clamp(
            LTF_MSS_QUALITY_BASE
            + clamp(break_distance / max(avg_range * 0.55, point * 4)) * LTF_MSS_QUALITY_BREAK_SCALE
            + body_strength(rates[index], point) * LTF_MSS_QUALITY_BODY_SCALE
        )
        return {"mss_index": index, "mss_quality": mss_quality}

    return None
