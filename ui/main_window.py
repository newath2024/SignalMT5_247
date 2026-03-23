from __future__ import annotations

import threading
import time
from pathlib import Path

try:
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtGui import QFont, QIcon
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QGridLayout,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QSplitter,
        QTabWidget,
        QVBoxLayout,
        QWidget,
        QTableWidgetItem,
    )

    from core.constants import APP_NAME
    from core.paths import BUNDLE_ROOT
    from ui.presentation import (
        format_duration,
        format_cooldown,
        format_phase,
        format_price,
        format_relative_age,
        format_score,
        format_short_time,
        format_symbol_focus,
        format_timestamp,
        format_zone,
        format_htf_context_short,
        get_priority_label,
        get_state_label,
        is_actionable_symbol,
        is_recent,
        log_matches_filter,
        sort_symbol_rows,
    )
    from ui.theme import (
        FONT_FAMILY,
        FONT_SIZE,
        SPACE_3,
        SPACE_4,
        SPACE_5,
        build_stylesheet,
        bias_tone,
        connection_tone,
        liquidity_tone,
        priority_tone,
        reaction_tone,
        row_palette_for_state,
        scanner_status_palette,
        state_tone,
    )
    from ui.widgets import (
        BADGE_ROLE,
        CommandBar,
        InspectorPanel,
        ModernTableWidget,
        PanelCard,
        StatCard,
        StatusBadge,
        TelemetryLogView,
        build_brand_icon,
    )

    _PYSIDE_IMPORT_ERROR = None
except ImportError as exc:  # pragma: no cover - desktop-only import guard
    QMainWindow = object
    _PYSIDE_IMPORT_ERROR = exc


class MainWindow(QMainWindow):  # pragma: no cover - exercised via manual UI smoke test
    def __init__(self, controller, auto_start: bool):
        super().__init__()
        self.controller = controller
        self.auto_start = auto_start
        self._symbol_rows: list[dict] = []
        self._last_snapshot: dict | None = None
        self._pulse_on = False

        self.setWindowTitle(f"{controller.config.app.name} v{controller.config.app.version}")
        self.resize(1600, 980)
        self.setMinimumSize(1360, 860)
        icon_path = BUNDLE_ROOT / "assets" / "liquidity_sniper.ico"
        vector_icon_path = BUNDLE_ROOT / "assets" / "liquidity_sniper_mark.svg"
        legacy_icon_path = BUNDLE_ROOT / "assets" / "openclaw.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        elif vector_icon_path.exists():
            self.setWindowIcon(QIcon(str(vector_icon_path)))
        elif legacy_icon_path.exists():
            self.setWindowIcon(QIcon(str(legacy_icon_path)))
        else:
            self.setWindowIcon(build_brand_icon())

        self.command_bar = CommandBar(
            controller.config.app.name,
            controller.config.app.version,
            controller.config.app.strategy_version,
            controller.config.app.tagline,
        )
        self.interval_spin = self.command_bar.interval_spin
        self.interval_spin.setRange(5, 3600)
        self.interval_spin.setValue(controller.config.scanner.loop_interval_sec)
        self.ob_fvg_mode_combo = self.command_bar.ob_fvg_mode_combo
        self.ob_fvg_mode_combo.addItem("Medium", "medium")
        self.ob_fvg_mode_combo.addItem("Strict", "strict")
        self.start_button = self.command_bar.start_button
        self.stop_button = self.command_bar.stop_button
        self.rescan_now_button = self.command_bar.rescan_now_button
        self.rescan_selected_button = self.command_bar.rescan_selected_button
        self.refresh_button = self.command_bar.refresh_button
        self.clear_log_button = self.command_bar.clear_log_button
        self.export_log_button = self.command_bar.export_log_button

        self.actionable_only_checkbox = QCheckBox("Show only setups with edge")
        self.symbol_count_label = QLabel("Watching 0/0 markets")
        self.symbol_count_label.setProperty("uiClass", "meta")

        self.log_filter = QComboBox()
        self.log_filter.addItem("All", "all")
        self.log_filter.addItem("Targets Only", "signals")
        self.log_filter.addItem("Warnings / Errors", "warnings")
        self.log_symbol_filter = QLineEdit()
        self.log_symbol_filter.setPlaceholderText("Filter by market, symbol, or text")

        self.symbol_table = ModernTableWidget(8)
        self.watch_table = ModernTableWidget(9, compact=True)
        self.alert_table = ModernTableWidget(9, compact=True)
        self.log_view = TelemetryLogView()

        self.metric_cards = {
            "active_watches": StatCard("Active Setups"),
            "confirmed_signals": StatCard("Confirmed Today"),
            "coverage": StatCard("Market Coverage"),
            "loop_interval": StatCard("Sweep Cadence"),
        }

        self.inspector = InspectorPanel()
        self.inspector.add_section(
            "Target Status",
            (
                ("current_state", "Target State"),
                ("priority", "Priority"),
                ("phase", "Phase"),
                ("reason", "Execution Step"),
                ("score", "Score"),
                ("cooldown_info", "Cooldown"),
            ),
        )
        self.inspector.add_section(
            "HTF Thesis",
            (
                ("htf_bias", "HTF Bias"),
                ("htf_context", "Thesis"),
                ("htf_zone_type", "Zone Type"),
                ("zone", "Zone"),
                ("htf_zone_source", "Source"),
            ),
            multiline_keys={"zone", "htf_zone_source"},
        )
        self.inspector.add_section(
            "Market Structure",
            (
                ("market_structure_bias", "Market Bias"),
                ("liquidity_interaction_state", "Liquidity"),
                ("reaction_strength", "Reaction"),
                ("htf_context_reason", "Context Note"),
                ("timeline", "Recent Timeline"),
            ),
            multiline_keys={"htf_context_reason", "timeline"},
        )
        self.inspector.add_section(
            "Execution Trigger",
            (
                ("last_detected_sweep", "Last Sweep"),
                ("last_detected_mss", "MSS"),
                ("last_detected_ifvg", "iFVG"),
                ("active_watch_info", "Live Watch"),
                ("zone_top_bottom", "Entry Zone"),
                ("last_alert_time", "Last Alert"),
                ("rejection_reason", "No Edge"),
                ("rejection_debug", "Why No Edge"),
            ),
            multiline_keys={"active_watch_info", "rejection_reason", "rejection_debug"},
        )

        self._build_ui()
        self._wire_events()

        self._snapshot_timer = QTimer(self)
        self._snapshot_timer.timeout.connect(self.refresh_snapshot)
        self._snapshot_timer.start(1500)

        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.timeout.connect(self._tick_status_feedback)
        self._heartbeat_timer.start(1000)

        self.refresh_snapshot()
        if self.auto_start:
            QTimer.singleShot(200, self.start_scanner)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("AppRoot")
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(SPACE_5, SPACE_5, SPACE_5, SPACE_5)
        outer.setSpacing(SPACE_4)

        outer.addWidget(self.command_bar)
        outer.addLayout(self._build_metric_row())

        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setChildrenCollapsible(False)
        content_splitter.setHandleWidth(1)
        content_splitter.addWidget(self._build_left_panel())
        content_splitter.addWidget(self.inspector)
        content_splitter.setStretchFactor(0, 7)
        content_splitter.setStretchFactor(1, 3)
        outer.addWidget(content_splitter, 1)

    def _build_metric_row(self):
        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(SPACE_4)
        layout.setVerticalSpacing(SPACE_4)
        layout.addWidget(self.metric_cards["active_watches"], 0, 0)
        layout.addWidget(self.metric_cards["confirmed_signals"], 0, 1)
        layout.addWidget(self.metric_cards["coverage"], 0, 2)
        layout.addWidget(self.metric_cards["loop_interval"], 0, 3)
        for index in range(4):
            layout.setColumnStretch(index, 1)
        return layout

    def _build_left_panel(self) -> QWidget:
        container = QWidget()
        container.setProperty("uiClass", "surface")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        tabs = QTabWidget()
        tabs.addTab(self._build_symbol_tab(), "Market Radar")
        tabs.addTab(self._build_watch_tab(), "Target Pipeline")
        tabs.addTab(self._build_alert_tab(), "Alert Feed")
        tabs.addTab(self._build_activity_tab(), "Telemetry")
        layout.addWidget(tabs)
        return container

    def _build_panel_card(self, title: str, hint: str) -> tuple[PanelCard, QVBoxLayout]:
        card = PanelCard(object_name="PanelCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(SPACE_4, SPACE_4, SPACE_4, SPACE_4)
        layout.setSpacing(SPACE_3)

        title_label = QLabel(title)
        title_label.setProperty("uiClass", "sectionTitle")
        hint_label = QLabel(hint)
        hint_label.setProperty("uiClass", "sectionHint")
        hint_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(hint_label)
        return card, layout

    def _build_symbol_tab(self) -> QWidget:
        card, layout = self._build_panel_card(
            "Market Radar",
            "Live HTF/LTF sweep view across the hunting list, with the cleanest setups rising above the noise.",
        )
        top_row = QHBoxLayout()
        top_row.setSpacing(SPACE_3)
        top_row.addWidget(self.actionable_only_checkbox)
        top_row.addWidget(self.symbol_count_label)
        top_row.addStretch(1)
        top_row.addWidget(self._legend_badge("Standby", "neutral"))
        top_row.addWidget(self._legend_badge("Tracking", "warning"))
        top_row.addWidget(self._legend_badge("Locked Target", "success"))
        top_row.addWidget(self._legend_badge("Invalid / No Edge", "muted"))
        layout.addLayout(top_row)

        self.symbol_table.setHorizontalHeaderLabels(
            ["Market", "Status", "HTF Thesis", "Focus", "TF", "Price", "Priority", "Updated"]
        )
        self._configure_table(self.symbol_table, stretch_column=3, badge_columns=(1, 6))
        layout.addWidget(self.symbol_table, 1)
        return card

    def _build_watch_tab(self) -> QWidget:
        card, layout = self._build_panel_card(
            "Target Pipeline",
            "Persistent targeting states for tracked markets and locked execution zones.",
        )
        self.watch_table.setHorizontalHeaderLabels(
            ["Market", "TF", "Side", "HTF Thesis", "Sweep State", "Target State", "Tracking", "Zone", "Locked Since"]
        )
        self._configure_table(self.watch_table, stretch_column=3, badge_columns=(2, 5))
        layout.addWidget(self.watch_table, 1)
        return card

    def _build_alert_tab(self) -> QWidget:
        card, layout = self._build_panel_card(
            "Alert Feed",
            "Fresh alerts, routed executions, and blocked states from the live strategy runtime.",
        )
        self.alert_table.setHorizontalHeaderLabels(
            ["Time", "Market", "TF", "Side", "Alert", "Reason", "Entry", "SL", "Status"]
        )
        self._configure_table(self.alert_table, stretch_column=5, badge_columns=(3, 8))
        layout.addWidget(self.alert_table, 1)
        return card

    def _build_activity_tab(self) -> QWidget:
        card, layout = self._build_panel_card(
            "System Telemetry",
            "Scanner telemetry, targeting decisions, warnings, and export-ready operator logs.",
        )
        filter_row = QHBoxLayout()
        filter_row.setSpacing(SPACE_3)
        filter_label = QLabel("Filter")
        filter_label.setProperty("uiClass", "meta")
        search_label = QLabel("Search")
        search_label.setProperty("uiClass", "meta")
        filter_row.addWidget(filter_label)
        filter_row.addWidget(self.log_filter)
        filter_row.addWidget(search_label)
        filter_row.addWidget(self.log_symbol_filter, 1)
        layout.addLayout(filter_row)
        layout.addWidget(self.log_view, 1)
        return card

    def _legend_badge(self, text: str, tone: str) -> StatusBadge:
        badge = StatusBadge(text)
        badge.set_badge(text, tone=tone)
        return badge

    @staticmethod
    def _configure_table(table: ModernTableWidget, stretch_column: int | None = None, badge_columns: tuple[int, ...] = ()) -> None:
        header = table.horizontalHeader()
        for index in range(table.columnCount()):
            header.setSectionResizeMode(index, QHeaderView.ResizeToContents)
        if stretch_column is not None:
            header.setSectionResizeMode(stretch_column, QHeaderView.Stretch)
        table.set_badge_columns(*badge_columns)

    def _wire_events(self) -> None:
        self.start_button.clicked.connect(self.start_scanner)
        self.stop_button.clicked.connect(self.stop_scanner)
        self.rescan_now_button.clicked.connect(self.rescan_now)
        self.rescan_selected_button.clicked.connect(self.rescan_selected_symbol)
        self.refresh_button.clicked.connect(self.refresh_snapshot)
        self.clear_log_button.clicked.connect(self.clear_activity_log)
        self.export_log_button.clicked.connect(self.export_logs)
        self.ob_fvg_mode_combo.currentIndexChanged.connect(self.change_ob_fvg_mode)
        self.log_filter.currentIndexChanged.connect(self.refresh_activity_log)
        self.log_symbol_filter.textChanged.connect(self.refresh_activity_log)
        self.actionable_only_checkbox.stateChanged.connect(self._refresh_symbol_table_view)
        self.symbol_table.itemSelectionChanged.connect(self.update_symbol_inspector)

    def _selected_symbol(self) -> str | None:
        row = self.symbol_table.currentRow()
        if row < 0 or row >= len(self._symbol_rows):
            return None
        return self._symbol_rows[row]["symbol"]

    @staticmethod
    def _run_background(target) -> None:
        thread = threading.Thread(target=target, daemon=True)
        thread.start()

    def start_scanner(self) -> None:
        ok, message = self.controller.start(interval_sec=self.interval_spin.value())
        self.refresh_snapshot()
        if not ok:
            QMessageBox.information(self, APP_NAME, message)

    def stop_scanner(self) -> None:
        self.controller.stop()
        self.refresh_snapshot()

    def rescan_now(self) -> None:
        self._run_background(self.controller.rescan_now)

    def rescan_selected_symbol(self) -> None:
        symbol = self._selected_symbol()
        if not symbol:
            QMessageBox.information(self, APP_NAME, "Select a market first.")
            return
        self._run_background(lambda: self.controller.rescan_symbol(symbol))

    def clear_activity_log(self) -> None:
        self.controller.clear_activity_log()
        self.refresh_snapshot()

    def export_logs(self) -> None:
        default_path = Path(self.controller.logger.log_file).with_name("liquidity_sniper_export.log")
        target, _ = QFileDialog.getSaveFileName(
            self,
            "Export Telemetry",
            str(default_path),
            "Log Files (*.log);;Text Files (*.txt)",
        )
        if not target:
            return
        Path(target).write_text(self.log_view.toPlainText(), encoding="utf-8")

    def change_ob_fvg_mode(self, _index=None) -> None:
        mode = self.ob_fvg_mode_combo.currentData()
        if not mode:
            return
        ok, message = self.controller.set_ob_fvg_mode(mode)
        if not ok:
            QMessageBox.information(self, APP_NAME, message)
        self.refresh_snapshot()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.controller.shutdown()
        super().closeEvent(event)

    def refresh_snapshot(self) -> None:
        snapshot = self.controller.snapshot()
        self._last_snapshot = snapshot

        scanner = snapshot["scanner"]
        connections = snapshot["connections"]
        metrics = snapshot["metrics"]
        strategy = snapshot.get("strategy", {})
        current_ob_fvg_mode = str(strategy.get("ob_fvg_mode", "medium"))

        mt5_connected = bool(connections["mt5"]["connected"])
        self.command_bar.mt5_badge.set_connection(
            mt5_connected,
            "Linked" if mt5_connected else "Offline",
            tone=connection_tone(mt5_connected, "mt5"),
        )
        telegram_configured = bool(connections["telegram"]["configured"])
        self.command_bar.telegram_badge.set_connection(
            telegram_configured,
            "Routed" if telegram_configured else "Not Ready",
            tone=connection_tone(telegram_configured, "telegram"),
        )

        previous_signal_state = self.ob_fvg_mode_combo.blockSignals(True)
        combo_index = self.ob_fvg_mode_combo.findData(current_ob_fvg_mode)
        if combo_index >= 0 and combo_index != self.ob_fvg_mode_combo.currentIndex():
            self.ob_fvg_mode_combo.setCurrentIndex(combo_index)
        self.ob_fvg_mode_combo.blockSignals(previous_signal_state)

        self.metric_cards["active_watches"].set_value(
            str(metrics["active_watches"]),
            "Markets currently being tracked for MSS and iFVG execution alignment.",
        )
        self.metric_cards["confirmed_signals"].set_value(
            str(metrics["confirmed_signals_today"]),
            "Confirmed sniper entries recorded in local history during the current session.",
        )
        self.metric_cards["coverage"].set_value(
            f"{metrics['scanned_symbols']}/{metrics['total_symbols']}",
            "Markets processed by the active sweep engine during this runtime session.",
        )
        self.metric_cards["loop_interval"].set_value(
            f"{scanner['interval_sec']}s",
            "Configured delay before the next automated sweep check begins.",
        )

        self._fill_symbol_table(snapshot["symbols"])
        self._fill_watch_table(snapshot["watches"])
        self._fill_alert_table(snapshot["alerts"])
        self.refresh_activity_log()
        self.update_symbol_inspector()
        self._render_status_feedback()
        self._sync_scanner_action_buttons(scanner)

    def _tick_status_feedback(self) -> None:
        self._pulse_on = not self._pulse_on
        self._render_status_feedback()

    def _render_status_feedback(self) -> None:
        snapshot = self._last_snapshot
        if not snapshot:
            return

        scanner = snapshot["scanner"]
        metrics = snapshot["metrics"]
        strategy = snapshot.get("strategy", {})
        status = str(scanner.get("status") or "idle").lower()
        pulse = bool(scanner.get("running")) and status in {"running", "scanning", "starting"}
        meta = scanner_status_palette(status, pulse=self._pulse_on and pulse)

        self.command_bar.live_indicator.set_color(meta["dot"])
        self.command_bar.status_badge.set_badge(meta["label"], tone=meta["tone"])
        self.command_bar.status_title.setText(self._build_status_headline(scanner))
        self.command_bar.scan_progress_label.setText(
            self._build_scan_progress_text(scanner, metrics, strategy)
        )
        self.command_bar.last_scan_label.setText(self._build_last_scan_text(scanner))

    @staticmethod
    def _build_status_headline(scanner: dict) -> str:
        status = str(scanner.get("status") or "idle").lower()
        progress = dict(scanner.get("progress") or {})
        if status == "scanning":
            total = max(0, int(progress.get("total") or 0))
            current = max(1, int(progress.get("current") or 0)) if total else int(progress.get("current") or 0)
            if total:
                return f"Hunting liquidity across live markets  ({current}/{total})"
            return "Hunting liquidity across live markets"
        if status == "running":
            return "Scanner armed and scanning for sweep setups"
        if status == "starting":
            return "Arming scanner services"
        if status == "stopping":
            return "Disarming scanner services"
        if status == "error":
            return "Scanner requires operator attention"
        if status == "stopped":
            return "Scanner disarmed"
        return "Scanner on standby"

    @staticmethod
    def _build_scan_progress_text(scanner: dict, metrics: dict, strategy: dict) -> str:
        progress = dict(scanner.get("progress") or {})
        status = str(scanner.get("status") or "idle").lower()
        pieces: list[str] = []
        if status == "scanning":
            total = max(0, int(progress.get("total") or 0))
            current = max(1, int(progress.get("current") or 0)) if total else int(progress.get("current") or 0)
            if total:
                pieces.append(f"Sweep pass {current}/{total}")
            current_symbol = progress.get("current_symbol")
            if current_symbol:
                pieces.append(f"Tracking {current_symbol}")
        else:
            scanned_symbols = int(metrics.get("scanned_symbols") or 0)
            total_symbols = int(metrics.get("total_symbols") or 0)
            if total_symbols:
                pieces.append(f"Market coverage {scanned_symbols}/{total_symbols}")
            next_scan_at = scanner.get("next_scan_at")
            if status == "running" and next_scan_at is not None:
                remaining = max(0, int(next_scan_at - time.time()))
                pieces.append(f"Next sweep check in {format_duration(remaining)}")
        pieces.append(f"Cadence {scanner.get('interval_sec', 0)}s")
        pieces.append(f"iFVG mode {strategy.get('ob_fvg_mode', 'medium')}")
        if status == "error" and scanner.get("last_error"):
            pieces.append(f"Error: {scanner['last_error']}")
        return "  |  ".join(piece for piece in pieces if piece)

    @staticmethod
    def _build_last_scan_text(scanner: dict) -> str:
        last_cycle = dict(scanner.get("last_cycle") or {})
        finished_at = last_cycle.get("finished_at")
        if finished_at:
            return f"Last sweep check {format_short_time(finished_at)}  |  {format_relative_age(finished_at)}"
        progress = dict(scanner.get("progress") or {})
        if progress.get("active") and progress.get("started_at"):
            return (
                f"Current hunt started {format_short_time(progress['started_at'])}"
                f"  |  {format_relative_age(progress['started_at'])}"
            )
        return "Last sweep check waiting for first cycle"

    def _sync_scanner_action_buttons(self, scanner: dict | None) -> None:
        payload = dict(scanner or {})
        status = str(payload.get("status") or "idle").lower()
        running = bool(payload.get("running"))

        scanner_active = running or status in {"starting", "scanning", "running", "waiting_mt5"}
        stopping = status == "stopping"

        start_enabled = not scanner_active and status not in {"stopping"}
        stop_enabled = scanner_active or stopping
        if stopping:
            stop_enabled = False

        self.start_button.setEnabled(start_enabled)
        self.stop_button.setEnabled(stop_enabled)

        start_tooltip = "Arm the scanner loop" if start_enabled else "Scanner is already armed"
        stop_tooltip = "Disarm the scanner loop" if stop_enabled else (
            "Scanner is disarming" if stopping else "Scanner is already disarmed"
        )
        self.start_button.setToolTip(start_tooltip)
        self.stop_button.setToolTip(stop_tooltip)

    def _fill_symbol_table(self, rows: list[dict]) -> None:
        selected_symbol = self._selected_symbol()
        display_rows = sort_symbol_rows(rows)
        total_rows = len(display_rows)
        if self.actionable_only_checkbox.isChecked():
            display_rows = [item for item in display_rows if is_actionable_symbol(item)]
        self._symbol_rows = display_rows
        self.symbol_count_label.setText(f"Watching {len(display_rows)}/{total_rows} markets")

        signal_state = self.symbol_table.blockSignals(True)
        self.symbol_table.setUpdatesEnabled(False)
        try:
            self.symbol_table.clearSelection()
            self.symbol_table.setRowCount(len(display_rows))
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
                for column_index, value in enumerate(values):
                    cell = QTableWidgetItem(str(value))
                    cell.setData(Qt.UserRole, item)
                    if column_index in {1, 4, 5, 6, 7}:
                        cell.setTextAlignment(Qt.AlignCenter)
                    if column_index == 1:
                        cell.setData(BADGE_ROLE, {"text": str(value), "tone": state_tone(state)})
                    elif column_index == 6:
                        cell.setData(BADGE_ROLE, {"text": str(value), "tone": priority_tone(priority)})
                    self.symbol_table.setItem(row_index, column_index, cell)

                self._paint_row(self.symbol_table, row_index, state)
                self._emphasize_row(self.symbol_table, row_index, priority, item)
        finally:
            self.symbol_table.setUpdatesEnabled(True)
            self.symbol_table.blockSignals(signal_state)

        self._restore_symbol_selection(display_rows, selected_symbol)

    def _fill_watch_table(self, rows: list[dict]) -> None:
        signal_state = self.watch_table.blockSignals(True)
        self.watch_table.setUpdatesEnabled(False)
        try:
            self.watch_table.setRowCount(len(rows))
            for row_index, item in enumerate(rows):
                direction = (
                    item.get("direction")
                    or ("LONG" if item.get("bias") == "Long" else "SHORT" if item.get("bias") == "Short" else "-")
                )
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
                for column_index, value in enumerate(values):
                    cell = QTableWidgetItem(str(value))
                    if column_index in {1, 2, 5, 8}:
                        cell.setTextAlignment(Qt.AlignCenter)
                    if column_index == 2:
                        cell.setData(BADGE_ROLE, {"text": str(value), "tone": self._direction_tone(direction)})
                    elif column_index == 5:
                        cell.setData(BADGE_ROLE, {"text": str(value), "tone": state_tone(item.get("status"))})
                    self.watch_table.setItem(row_index, column_index, cell)
                self._paint_row(self.watch_table, row_index, item.get("status", "idle"))
        finally:
            self.watch_table.setUpdatesEnabled(True)
            self.watch_table.blockSignals(signal_state)

    def _fill_alert_table(self, rows: list[dict]) -> None:
        signal_state = self.alert_table.blockSignals(True)
        self.alert_table.setUpdatesEnabled(False)
        try:
            self.alert_table.setRowCount(len(rows))
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
                for column_index, value in enumerate(values):
                    cell = QTableWidgetItem(str(value))
                    if column_index == 3:
                        cell.setData(BADGE_ROLE, {"text": str(value), "tone": self._direction_tone(str(value))})
                    elif column_index == 8:
                        cell.setData(BADGE_ROLE, {"text": str(value), "tone": self._alert_status_tone(item)})
                    self.alert_table.setItem(row_index, column_index, cell)
                alert_state = (
                    "confirmed"
                    if item.get("status") == "sent"
                    else "rejected" if "blocked" in str(item.get("status")) else "idle"
                )
                self._paint_row(self.alert_table, row_index, alert_state, tint_only=True)
        finally:
            self.alert_table.setUpdatesEnabled(True)
            self.alert_table.blockSignals(signal_state)

    def refresh_activity_log(self) -> None:
        if not self._last_snapshot:
            return
        filter_key = self.log_filter.currentData()
        query = self.log_symbol_filter.text().strip().lower()
        lines = []
        for entry in self._last_snapshot["logs"]:
            if not log_matches_filter(entry, filter_key):
                continue
            if query:
                search_blob = " ".join(
                    str(entry.get(key) or "").lower()
                    for key in ("symbol", "timeframe", "message", "phase", "reason")
                )
                if query not in search_blob:
                    continue
            suffix = f" | reason={entry['reason']}" if entry.get("reason") else ""
            timestamp = str(entry.get("label") or format_timestamp(entry.get("timestamp")) or "-")
            lines.append(
                f"{timestamp} [{entry['level']}] {entry['symbol']} {entry['timeframe']} {entry['message']} | "
                f"phase={entry['phase']}{suffix}"
            )
        self.log_view.setPlainText("\n".join(lines[-150:]))

    def update_symbol_inspector(self) -> None:
        row = self.symbol_table.currentRow()
        if row < 0 or row >= len(self._symbol_rows):
            self.inspector.clear()
            return

        payload = self._symbol_rows[row]
        detail = dict((payload or {}).get("detail") or {})
        detail["current_state"] = get_state_label((payload or {}).get("state", "-"))
        detail["priority"] = get_priority_label(payload)
        detail["htf_bias"] = (payload or {}).get("bias", "-")
        detail["phase"] = format_phase((payload or {}).get("phase", "-"))
        detail["reason"] = format_symbol_focus(payload)
        detail["score"] = format_score((payload or {}).get("score"), (payload or {}).get("grade"))
        detail["htf_context"] = format_htf_context_short(payload)
        detail["last_alert_time"] = (payload or {}).get("last_alert_time")
        detail["htf_context_reason"] = self._format_structure_note(payload, detail)
        detail["last_detected_sweep"] = self._format_detail_text(detail.get("last_detected_sweep"))
        detail["last_detected_mss"] = self._format_detail_text(detail.get("last_detected_mss"))
        detail["last_detected_ifvg"] = self._format_detail_text(detail.get("last_detected_ifvg"))
        detail["active_watch_info"] = self._format_detail_text(detail.get("active_watch_info"))
        detail["rejection_reason"] = self._format_detail_text(detail.get("rejection_reason"))
        detail["rejection_debug"] = self._format_detail_text(detail.get("rejection_debug"))
        detail["timeline"] = self._format_detail_text(detail.get("timeline"))
        detail["zone"] = self._format_detail_text(detail.get("zone"))
        detail["zone_top_bottom"] = self._format_detail_text(detail.get("zone_top_bottom"))
        detail["htf_zone_source"] = self._format_detail_text(detail.get("htf_zone_source"))
        cooldown_value = format_cooldown((payload or {}).get("cooldown_remaining"))
        if cooldown_value != "-":
            detail["cooldown_info"] = cooldown_value

        symbol = str(payload.get("symbol") or "Unknown")
        summary_bits = [
            detail["htf_context"],
            str(payload.get("tf") or "-"),
            format_price(payload.get("price")),
            format_symbol_focus(payload),
            format_relative_age(payload.get("last_update")),
        ]
        summary = "  |  ".join(bit for bit in summary_bits if bit and bit != "-")
        self.inspector.set_header(
            symbol,
            summary or "Live market snapshot",
            detail["current_state"],
            tone=state_tone(payload.get("state")),
        )

        for key, field in self.inspector.fields.items():
            value = detail.get(key, "-")
            if key == "last_alert_time":
                value = format_timestamp(value)
            tone = self._inspector_field_tone(key, value, payload)
            monospace = key in {"timeline", "rejection_debug", "zone_top_bottom", "last_alert_time"}
            field.set_value(str(value or "--"), tone=tone, monospace=monospace)

    def _restore_symbol_selection(self, display_rows: list[dict], selected_symbol: str | None) -> None:
        if selected_symbol:
            for row_index, item in enumerate(display_rows):
                if item.get("symbol") == selected_symbol:
                    self.symbol_table.selectRow(row_index)
                    return
        if display_rows and self.symbol_table.currentRow() < 0:
            self.symbol_table.selectRow(0)

    def _refresh_symbol_table_view(self) -> None:
        if not self._last_snapshot:
            return
        self._fill_symbol_table(self._last_snapshot.get("symbols") or [])
        self.update_symbol_inspector()

    def _paint_row(self, table: ModernTableWidget, row_index: int, state: str, tint_only: bool = False) -> None:
        palette = row_palette_for_state(state)
        for column_index in range(table.columnCount()):
            item = table.item(row_index, column_index)
            if item is None:
                continue
            if not tint_only or column_index in {0, 1, table.columnCount() - 1}:
                item.setBackground(palette["background"])
            item.setForeground(palette["foreground"])

    def _emphasize_row(self, table: ModernTableWidget, row_index: int, priority: str, item: dict) -> None:
        if priority == "High":
            font = QFont(FONT_FAMILY, FONT_SIZE)
            font.setBold(True)
            for column_index in range(table.columnCount()):
                current_item = table.item(row_index, column_index)
                if current_item is not None:
                    current_item.setFont(font)

        if is_recent(item.get("last_alert_time")) and item.get("state") in {"confirmed", "cooldown"}:
            accent_font = QFont(FONT_FAMILY, FONT_SIZE)
            accent_font.setBold(True)
            accent_font.setUnderline(True)
            for column_index in {0, 1}:
                current_item = table.item(row_index, column_index)
                if current_item is not None:
                    current_item.setFont(accent_font)

    @staticmethod
    def _direction_tone(direction: str) -> str:
        value = str(direction or "").strip().lower()
        if value in {"long", "buy"}:
            return "success"
        if value in {"short", "sell"}:
            return "danger"
        return "neutral"

    @staticmethod
    def _alert_status_tone(item: dict) -> str:
        status = str(item.get("status") or "").lower()
        if status == "sent":
            return "success"
        if "blocked" in status or "failed" in status:
            return "danger"
        return "neutral"

    @staticmethod
    def _format_detail_text(value) -> str:
        if isinstance(value, (list, tuple)):
            text = "\n".join(str(item) for item in value if str(item).strip())
        else:
            text = str(value or "-").strip()
        if not text or text == "-":
            return "--"
        return (
            text.replace("Previous Day High", "PDH")
            .replace("Previous Day Low", "PDL")
            .replace("Previous Week High", "PWH")
            .replace("Previous Week Low", "PWL")
            .replace("Asia Session High", "ASH")
            .replace("Asia Session Low", "ASL")
            .replace("London Session High", "LOH")
            .replace("London Session Low", "LOL")
        )

    def _format_structure_note(self, payload: dict | None, detail: dict) -> str:
        liquidity_state = str(detail.get("liquidity_interaction_state") or "").strip()
        reaction = str(detail.get("reaction_strength") or "--").strip()
        market_bias = str(detail.get("market_structure_bias") or detail.get("htf_bias") or "--").strip()
        if liquidity_state and liquidity_state not in {"-", "Untouched"}:
            context = format_htf_context_short(payload)
            return f"{context} | {reaction} reaction | {market_bias}"
        zone_type = str(detail.get("htf_zone_type") or "").strip()
        if zone_type and zone_type != "-":
            return f"{zone_type} | {reaction} reaction | {market_bias}"
        return self._format_detail_text(detail.get("htf_context_reason"))

    def _inspector_field_tone(self, key: str, value, payload: dict) -> str | None:
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
        if key == "score":
            return "info"
        if key == "cooldown_info":
            return "neutral"
        return None


def launch_desktop(controller, auto_start: bool = True):
    if _PYSIDE_IMPORT_ERROR is not None:
        raise SystemExit(
            "PySide6 is not installed for this interpreter.\n"
            "Run: python -m pip install PySide6"
        ) from _PYSIDE_IMPORT_ERROR

    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    app.setApplicationName(controller.config.app.name)
    if hasattr(app, "setApplicationDisplayName"):
        app.setApplicationDisplayName(controller.config.app.name)
    app.setFont(QFont(FONT_FAMILY, FONT_SIZE))
    app.setStyleSheet(build_stylesheet())

    window = MainWindow(controller, auto_start=auto_start)
    app.setWindowIcon(window.windowIcon())
    window.show()
    return app.exec()

