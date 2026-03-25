from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QTableWidgetItem

from ui.presentation import (
    format_htf_context_short,
    format_price,
    format_relative_age,
    format_short_time,
    format_symbol_focus,
    format_timestamp,
    format_zone,
    get_priority_label,
    get_state_label,
    is_actionable_symbol,
    is_recent,
    sort_symbol_rows,
)
from ui.presenters.symbol_presenter import alert_status_tone, direction_tone
from ui.theme import FONT_FAMILY, FONT_SIZE, priority_tone, row_palette_for_state, state_tone
from ui.widgets import BADGE_ROLE


def fill_symbol_table(window, rows: list[dict]) -> None:
    selected_symbol = window._active_symbol
    display_rows = sort_symbol_rows(rows)
    total_rows = len(display_rows)
    if window.actionable_only_checkbox.isChecked():
        display_rows = [item for item in display_rows if is_actionable_symbol(item)]
    window._symbol_rows = display_rows
    window.symbol_count_label.setText(f"Tracking {len(display_rows)}/{total_rows} markets")

    vertical_scroll = window.symbol_table.verticalScrollBar().value()
    horizontal_scroll = window.symbol_table.horizontalScrollBar().value()
    signal_state = window.symbol_table.blockSignals(True)
    window.symbol_table.setUpdatesEnabled(False)
    try:
        prepare_table_rows(window.symbol_table, len(display_rows))
        top_symbols = {item.get("symbol") for item in display_rows[:3]}
        for row_index, item in enumerate(display_rows):
            state = item.get("state", "idle")
            priority = get_priority_label(item)
            values = [
                item.get("symbol", "-"),
                get_state_label(state),
                format_htf_context_short(item),
                format_symbol_focus(item),
                item.get("tf", "-"),
                format_price(item.get("price")),
                priority,
                format_relative_age(item.get("last_update")),
            ]
            row_payloads = []
            for column_index, value in enumerate(values):
                badge_payload = None
                if column_index == 1:
                    badge_payload = {"text": str(value), "tone": state_tone(state)}
                elif column_index == 6:
                    badge_payload = {"text": str(value), "tone": priority_tone(priority)}
                row_payloads.append(
                    {
                        "text": str(value),
                        "alignment": Qt.AlignCenter if column_index in {1, 4, 5, 6, 7} else None,
                        "user_role": item,
                        "badge": badge_payload,
                    }
                )
            sync_table_row(window.symbol_table, row_index, row_payloads)
            paint_row(window.symbol_table, row_index, state)
            emphasize_row(window.symbol_table, row_index, priority, item, rank=row_index, top_symbols=top_symbols)
    finally:
        window.symbol_table.setUpdatesEnabled(True)
        window.symbol_table.blockSignals(signal_state)
        window.symbol_table.verticalScrollBar().setValue(vertical_scroll)
        window.symbol_table.horizontalScrollBar().setValue(horizontal_scroll)

    restore_symbol_selection(window, display_rows, selected_symbol)


def fill_watch_table(window, rows: list[dict]) -> None:
    vertical_scroll = window.watch_table.verticalScrollBar().value()
    signal_state = window.watch_table.blockSignals(True)
    window.watch_table.setUpdatesEnabled(False)
    try:
        prepare_table_rows(window.watch_table, len(rows))
        for row_index, item in enumerate(rows):
            direction = item.get("direction") or ("LONG" if item.get("bias") == "Long" else "SHORT" if item.get("bias") == "Short" else "-")
            values = [
                item.get("symbol", "-"),
                item.get("timeframe", "-"),
                direction,
                format_htf_context_short({"htf_context": item.get("htf_context"), "detail": {}}),
                item.get("ltf_sweep_status", "-"),
                get_state_label(item.get("status")),
                item.get("waiting_for", "-"),
                format_zone(item.get("zone_top"), item.get("zone_bottom")),
                format_short_time(item.get("armed_at")),
            ]
            row_payloads = []
            for column_index, value in enumerate(values):
                badge_payload = None
                if column_index == 2:
                    badge_payload = {"text": str(value), "tone": direction_tone(direction)}
                elif column_index == 5:
                    badge_payload = {"text": str(value), "tone": state_tone(item.get("status"))}
                row_payloads.append(
                    {
                        "text": str(value),
                        "alignment": Qt.AlignCenter if column_index in {1, 2, 5, 8} else None,
                        "badge": badge_payload,
                    }
                )
            sync_table_row(window.watch_table, row_index, row_payloads)
            paint_row(window.watch_table, row_index, item.get("status", "idle"))
    finally:
        window.watch_table.setUpdatesEnabled(True)
        window.watch_table.blockSignals(signal_state)
        window.watch_table.verticalScrollBar().setValue(vertical_scroll)


def fill_alert_table(window, rows: list[dict]) -> None:
    vertical_scroll = window.alert_table.verticalScrollBar().value()
    signal_state = window.alert_table.blockSignals(True)
    window.alert_table.setUpdatesEnabled(False)
    try:
        prepare_table_rows(window.alert_table, len(rows))
        for row_index, item in enumerate(rows):
            values = [
                format_timestamp(item.get("time")),
                item.get("symbol", "-"),
                item.get("tf", "-"),
                item.get("direction", "-"),
                item.get("alert_type", "-"),
                item.get("reason", "-"),
                format_price(item.get("entry")),
                format_price(item.get("sl")),
                item.get("status", "-"),
            ]
            row_payloads = []
            for column_index, value in enumerate(values):
                badge_payload = None
                if column_index == 3:
                    badge_payload = {"text": str(value), "tone": direction_tone(str(value))}
                elif column_index == 8:
                    badge_payload = {"text": str(value), "tone": alert_status_tone(item)}
                row_payloads.append({"text": str(value), "badge": badge_payload})
            sync_table_row(window.alert_table, row_index, row_payloads)
            alert_state = "confirmed" if item.get("status") == "sent" else "rejected" if "blocked" in str(item.get("status")) else "idle"
            paint_row(window.alert_table, row_index, alert_state, tint_only=True)
    finally:
        window.alert_table.setUpdatesEnabled(True)
        window.alert_table.blockSignals(signal_state)
        window.alert_table.verticalScrollBar().setValue(vertical_scroll)


def prepare_table_rows(table, row_count: int) -> None:
    if table.rowCount() != row_count:
        table.setRowCount(row_count)


def sync_table_row(table, row_index: int, payloads: list[dict]) -> None:
    for column_index, payload in enumerate(payloads):
        current_item = table.item(row_index, column_index)
        if current_item is None:
            current_item = QTableWidgetItem()
            table.setItem(row_index, column_index, current_item)
        text = str(payload.get("text", ""))
        if current_item.text() != text:
            current_item.setText(text)
        alignment = payload.get("alignment")
        if alignment is not None and current_item.textAlignment() != alignment:
            current_item.setTextAlignment(alignment)
        user_role = payload.get("user_role")
        if user_role is not None:
            current_item.setData(Qt.UserRole, user_role)
        badge_payload = payload.get("badge")
        current_badge = current_item.data(BADGE_ROLE)
        if badge_payload:
            if current_badge != badge_payload:
                current_item.setData(BADGE_ROLE, badge_payload)
        elif current_badge is not None:
            current_item.setData(BADGE_ROLE, None)


def paint_row(table, row_index: int, state: str, tint_only: bool = False) -> None:
    palette = row_palette_for_state(state)
    for column_index in range(table.columnCount()):
        item = table.item(row_index, column_index)
        if item is None:
            continue
        if not tint_only or column_index in {0, 1, table.columnCount() - 1}:
            item.setBackground(palette["background"])
        item.setForeground(palette["foreground"])


def emphasize_row(table, row_index: int, priority: str, item: dict, *, rank: int, top_symbols: set[str]) -> None:
    if priority == "High":
        font = QFont(FONT_FAMILY, FONT_SIZE)
        font.setBold(True)
        for column_index in range(table.columnCount()):
            current_item = table.item(row_index, column_index)
            if current_item is not None:
                current_item.setFont(font)

    if item.get("symbol") in top_symbols and priority in {"High", "Medium"}:
        lead_font = QFont(FONT_FAMILY, FONT_SIZE)
        lead_font.setBold(True)
        if rank == 0:
            lead_font.setPointSize(FONT_SIZE + 1)
        for column_index in {0, 1, 3}:
            current_item = table.item(row_index, column_index)
            if current_item is not None:
                current_item.setFont(lead_font)

    if is_recent(item.get("last_alert_time")) and item.get("state") in {"confirmed", "cooldown"}:
        accent_font = QFont(FONT_FAMILY, FONT_SIZE)
        accent_font.setBold(True)
        accent_font.setUnderline(True)
        for column_index in {0, 1}:
            current_item = table.item(row_index, column_index)
            if current_item is not None:
                current_item.setFont(accent_font)


def restore_symbol_selection(window, display_rows: list[dict], selected_symbol: str | None) -> None:
    if not selected_symbol:
        window.symbol_table.clearSelection()
        window._active_symbol = None
        return
    for row_index, item in enumerate(display_rows):
        if item.get("symbol") == selected_symbol:
            window.symbol_table.selectRow(row_index)
            window._active_symbol = selected_symbol
            return
    window.symbol_table.clearSelection()
    window._active_symbol = None
