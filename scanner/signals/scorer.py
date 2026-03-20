from ..config.ltf import (
    LTF_ENTRY_LOCATION_IFVG_WEIGHT,
    LTF_ENTRY_LOCATION_INTERNAL_SCORE,
    LTF_ENTRY_LOCATION_MODE_WEIGHT,
    LTF_ENTRY_LOCATION_STRICT_SCORE,
    LTF_STOP_VALIDITY_MAX_RANGE,
    MIN_RR,
    MIN_SCORE,
)
from ..utils import clamp, get_session_quality


def score_signal(context, trigger, ifvg, risk, rr_value):
    session_quality, session_note = get_session_quality()
    entry_location = clamp(
        LTF_ENTRY_LOCATION_IFVG_WEIGHT * ifvg["entry_quality"]
        + LTF_ENTRY_LOCATION_MODE_WEIGHT
        * (
            LTF_ENTRY_LOCATION_STRICT_SCORE
            if ifvg["mode"] == "strict"
            else LTF_ENTRY_LOCATION_INTERNAL_SCORE
        )
    )
    stop_validity = 1.0 if risk <= trigger["avg_range"] * LTF_STOP_VALIDITY_MAX_RANGE else 0.72
    rr_score = 1.0 if rr_value >= MIN_RR else clamp(rr_value / MIN_RR)

    score_components = {
        "htf_zone_quality": context["zone_quality"],
        "htf_reaction_clarity": context["reaction_clarity"],
        "liquidity_sweep_quality": trigger["sweep_quality"],
        "mss_clarity": trigger["mss_quality"],
        "ifvg_quality": ifvg["quality"],
        "entry_location": entry_location,
        "structural_stop_validity": stop_validity,
        "rr": rr_score,
        "session_quality": session_quality,
        "no_chase": trigger["execution"]["no_chase"],
    }
    score = round(sum(score_components.values()), 1)
    return {
        "score": score,
        "score_components": score_components,
        "session_note": session_note,
        "valid": score >= MIN_SCORE,
    }
