from __future__ import annotations

from typing import Any

from ui.presentation import (
    format_cooldown,
    format_htf_context_short,
    format_phase,
    format_price,
    format_relative_age,
    format_score,
    format_symbol_focus,
    format_timestamp,
    get_priority_label,
    get_state_label,
)
from ui.theme import bias_tone, liquidity_tone, priority_tone, reaction_tone, state_tone


def direction_tone(direction: str) -> str:
    value = str(direction or "").strip().lower()
    if value in {"long", "buy"}:
        return "success"
    if value in {"short", "sell"}:
        return "danger"
    return "neutral"


def alert_status_tone(item: dict[str, Any]) -> str:
    status = str(item.get("status") or "").lower()
    if status == "sent":
        return "success"
    if "blocked" in status or "failed" in status:
        return "danger"
    return "neutral"


def format_detail_text(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        text = "\n".join(str(item) for item in value if str(item).strip())
    else:
        text = str(value or "-").strip()
    if not text or text == "-":
        return "--"
    return text


def format_structure_note(payload: dict[str, Any] | None, detail: dict[str, Any]) -> str:
    reaction = str(detail.get("reaction_strength") or "--").strip()
    market_bias = str(detail.get("market_structure_bias") or detail.get("htf_bias") or "--").strip()
    tier = str(detail.get("htf_tier") or "--").strip()
    strength = str(detail.get("context_strength") or "--").strip()
    structural = str(detail.get("confluence_structural") or "--").strip().lower()
    higher_tf = str(detail.get("confluence_higher_tf") or "--").strip().lower()
    zone_type = str(detail.get("htf_zone_type") or "").strip()
    if zone_type and zone_type != "-":
        if tier == "C" and structural != "yes" and higher_tf != "yes":
            return f"{zone_type} | no structural confluence | context weak | {market_bias}"
        return f"{zone_type} | tier {tier} | {strength} | {reaction} reaction | {market_bias}"
    return format_detail_text(detail.get("htf_context_reason"))


def inspector_field_tone(key: str, value: Any, payload: dict[str, Any]) -> str | None:
    text = str(value or "").strip()
    if not text or text in {"-", "--"}:
        return None
    if key == "current_state":
        return state_tone(payload.get("state"))
    if key == "priority":
        return priority_tone(text)
    if key == "phase":
        return "info"
    if key in {"htf_bias", "market_structure_bias"}:
        return bias_tone(text)
    if key == "liquidity_interaction_state":
        return liquidity_tone(text)
    if key == "reaction_strength":
        return reaction_tone(text)
    if key in {"confluence_structural", "confluence_higher_tf"}:
        return "success" if text.lower() == "yes" else "warning"
    if key == "context_strength":
        return "success" if text.lower() == "strong" else "info" if text.lower() == "moderate" else "warning"
    if key == "score":
        return "info"
    if key == "cooldown_info":
        return "neutral"
    return None


def build_inspector_model(payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    detail = dict((payload or {}).get("detail") or {})
    detail["current_state"] = get_state_label((payload or {}).get("state", "-"))
    detail["priority"] = get_priority_label(payload)
    detail["htf_bias"] = (payload or {}).get("bias", "-")
    detail["phase"] = format_phase((payload or {}).get("phase", "-"))
    detail["reason"] = format_symbol_focus(payload)
    detail["score"] = format_score((payload or {}).get("score"), (payload or {}).get("grade"))
    detail["htf_context"] = format_htf_context_short(payload)
    detail["last_alert_time"] = (payload or {}).get("last_alert_time")
    detail["htf_context_reason"] = format_structure_note(payload, detail)
    detail["last_detected_sweep"] = format_detail_text(detail.get("last_detected_sweep"))
    detail["last_detected_mss"] = format_detail_text(detail.get("last_detected_mss"))
    detail["last_detected_ifvg"] = format_detail_text(detail.get("last_detected_ifvg"))
    detail["active_watch_info"] = format_detail_text(detail.get("active_watch_info"))
    detail["rejection_reason"] = format_detail_text(detail.get("rejection_reason"))
    detail["rejection_debug"] = format_detail_text(detail.get("rejection_debug"))
    detail["timeline"] = format_detail_text(detail.get("timeline"))
    detail["zone"] = format_detail_text(detail.get("zone"))
    detail["zone_top_bottom"] = format_detail_text(detail.get("zone_top_bottom"))
    detail["htf_zone_source"] = format_detail_text(detail.get("htf_zone_source"))
    detail["cooldown_info"] = format_cooldown((payload or {}).get("cooldown_remaining"))

    summary_bits = [
        detail["htf_context"],
        str(payload.get("tf") or "-"),
        format_price(payload.get("price")),
        format_symbol_focus(payload),
        format_relative_age(payload.get("last_update")),
    ]
    summary = "  |  ".join(bit for bit in summary_bits if bit and bit != "-")
    return detail, summary or "Live market snapshot"


def format_inspector_value(key: str, value: Any) -> str:
    if key == "last_alert_time":
        return str(format_timestamp(value) or "--")
    return str(value or "--")
