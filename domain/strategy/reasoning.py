"""Compatibility shim for strategy reasoning helpers.

Canonical implementation lives in ``domain.engine.reasoning`` and
``domain.scoring``. Safe to remove after import migration.
"""

from domain.engine.reasoning import (
    bias_label,
    build_detail_payload,
    compute_setup_score,
    derive_htf_bias,
    describe_context_wait,
    describe_error,
    describe_rejection,
    describe_waiting_mss_reason,
    describe_watch_reason,
    direction_label,
    format_bias_display,
    format_context_label,
    format_context_reason,
    format_entry_zone,
    format_htf_zone,
    format_htf_zone_source,
    format_htf_zone_type,
    format_ifvg_detail,
    format_mss_detail,
    format_rejection_debug,
    format_score,
    format_sweep_detail,
    format_timeline_lines,
    grade_from_score,
)

__all__ = [
    "bias_label",
    "build_detail_payload",
    "compute_setup_score",
    "derive_htf_bias",
    "describe_context_wait",
    "describe_error",
    "describe_rejection",
    "describe_waiting_mss_reason",
    "describe_watch_reason",
    "direction_label",
    "format_bias_display",
    "format_context_label",
    "format_context_reason",
    "format_entry_zone",
    "format_htf_zone",
    "format_htf_zone_source",
    "format_htf_zone_type",
    "format_ifvg_detail",
    "format_mss_detail",
    "format_rejection_debug",
    "format_score",
    "format_sweep_detail",
    "format_timeline_lines",
    "grade_from_score",
]
