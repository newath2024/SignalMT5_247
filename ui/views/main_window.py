from __future__ import annotations

import threading
from pathlib import Path

try:
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtGui import QFont, QIcon
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
    )

    from infra.config.constants import APP_NAME
    from infra.config.paths import BUNDLE_ROOT
    from ui.presenters.symbol_presenter import (
        build_inspector_model,
        format_inspector_value,
        inspector_field_tone,
    )
    from ui.presenters.table_presenter import fill_alert_table, fill_symbol_table, fill_watch_table
    from ui.theme import (
        FONT_FAMILY,
        FONT_SIZE,
        build_stylesheet,
        connection_tone,
        scanner_status_palette,
        state_tone,
    )
    from ui.viewmodels.main_window_vm import (
        build_metric_card_models,
        build_status_header_vm,
        render_activity_log,
        selected_payload_changed,
    )
    from ui.views.main_window_layout import build_main_window_layout
    from ui.widgets import (
        CommandBar,
        InspectorPanel,
        ModernTableWidget,
        StatCard,
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
        self._last_render_fingerprint: dict[str, object] = {}
        self._pulse_on = False
        self._active_symbol: str | None = None
        self._pending_snapshot_refresh = False

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
        self.exit_button = self.command_bar.exit_button

        self.actionable_only_checkbox = QCheckBox("Show only setups with edge")
        self.symbol_count_label = QLabel("Tracking 0/0 markets")
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
        self.symbol_table.set_empty_state("No markets in scope", "The radar will populate once symbols are configured for scanning.")
        self.watch_table.set_empty_state("No active pipeline targets", "Armed and developing setups will appear here during runtime.")
        self.alert_table.set_empty_state("No alerts yet", "Fresh execution alerts and blocked states will appear here during runtime.")

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
                ("htf_tier", "Tier"),
                ("context_strength", "Context Strength"),
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
                ("liquidity_interaction_state", "Context Model"),
                ("reaction_strength", "Reaction"),
                ("confluence_structural", "Structural Backing"),
                ("confluence_higher_tf", "Higher TF Backing"),
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
        self.inspector.clear()

        self._snapshot_timer = QTimer(self)
        self._snapshot_timer.timeout.connect(self.schedule_snapshot_refresh)
        self._snapshot_timer.start(1500)

        self._snapshot_refresh_timer = QTimer(self)
        self._snapshot_refresh_timer.setSingleShot(True)
        self._snapshot_refresh_timer.timeout.connect(self._perform_snapshot_refresh)

        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.timeout.connect(self._tick_status_feedback)
        self._heartbeat_timer.start(1000)

        self.schedule_snapshot_refresh(immediate=True)
        if self.auto_start:
            QTimer.singleShot(200, self.start_scanner)

    def _build_ui(self) -> None:
        build_main_window_layout(self)

    def _wire_events(self) -> None:
        self.start_button.clicked.connect(self.start_scanner)
        self.stop_button.clicked.connect(self.stop_scanner)
        self.rescan_now_button.clicked.connect(self.rescan_now)
        self.rescan_selected_button.clicked.connect(self.rescan_selected_symbol)
        self.refresh_button.clicked.connect(self.refresh_snapshot)
        self.clear_log_button.clicked.connect(self.clear_activity_log)
        self.export_log_button.clicked.connect(self.export_logs)
        self.exit_button.clicked.connect(self.exit_application)
        self.ob_fvg_mode_combo.currentIndexChanged.connect(self.change_ob_fvg_mode)
        self.log_filter.currentIndexChanged.connect(self.refresh_activity_log)
        self.log_symbol_filter.textChanged.connect(self.refresh_activity_log)
        self.actionable_only_checkbox.stateChanged.connect(self._refresh_symbol_table_view)
        self.symbol_table.itemSelectionChanged.connect(self._handle_target_selection_changed)

    def _selected_symbol(self) -> str | None:
        if self._active_symbol:
            return self._active_symbol
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
        self.schedule_snapshot_refresh(immediate=True)
        if not ok:
            QMessageBox.information(self, APP_NAME, message)

    def stop_scanner(self) -> None:
        self.controller.stop()
        self.schedule_snapshot_refresh(immediate=True)

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
        self.schedule_snapshot_refresh(immediate=True)

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
        self.schedule_snapshot_refresh(immediate=True)

    def exit_application(self) -> None:
        self.close()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.controller.shutdown()
        super().closeEvent(event)

    def refresh_snapshot(self) -> None:
        self.schedule_snapshot_refresh(immediate=True)

    def schedule_snapshot_refresh(self, immediate: bool = False) -> None:
        if immediate:
            self._pending_snapshot_refresh = False
            self._snapshot_refresh_timer.stop()
            self._perform_snapshot_refresh()
            return
        if self._pending_snapshot_refresh:
            return
        self._pending_snapshot_refresh = True
        self._snapshot_refresh_timer.start(120)

    def _perform_snapshot_refresh(self) -> None:
        self._pending_snapshot_refresh = False
        snapshot = self.controller.snapshot()
        previous_snapshot = self._last_snapshot
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

        for metric_key, card_model in build_metric_card_models(metrics, scanner).items():
            self.metric_cards[metric_key].set_value(card_model.value, card_model.hint)

        fill_symbol_table(self, snapshot["symbols"])
        fill_watch_table(self, snapshot["watches"])
        fill_alert_table(self, snapshot["alerts"])
        self.refresh_activity_log()
        if selected_payload_changed(previous_snapshot, snapshot, self._selected_symbol()):
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

        header_vm = build_status_header_vm(scanner, metrics, strategy)
        self.command_bar.live_indicator.set_color(meta["dot"])
        self.command_bar.status_badge.set_badge(meta["label"], tone=meta["tone"])
        self.command_bar.status_title.setText(header_vm.headline)
        self.command_bar.scan_progress_label.setText(header_vm.progress_text)
        self.command_bar.last_scan_label.setText(header_vm.last_scan_text)

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

    def refresh_activity_log(self) -> None:
        if not self._last_snapshot:
            return
        scrollbar = self.log_view.verticalScrollBar()
        previous_value = scrollbar.value()
        pinned_to_bottom = previous_value >= max(0, scrollbar.maximum() - 4)
        filter_key = self.log_filter.currentData()
        rendered = render_activity_log(self._last_snapshot["logs"], filter_key, self.log_symbol_filter.text())
        if rendered == self._last_render_fingerprint.get("log_text"):
            return
        self._last_render_fingerprint["log_text"] = rendered
        self.log_view.setPlainText(rendered)
        if pinned_to_bottom:
            scrollbar.setValue(scrollbar.maximum())
        else:
            scrollbar.setValue(min(previous_value, scrollbar.maximum()))

    def _handle_target_selection_changed(self) -> None:
        row = self.symbol_table.currentRow()
        if row < 0 or row >= len(self._symbol_rows):
            self._active_symbol = None
            self.inspector.clear()
            return
        self._active_symbol = self._symbol_rows[row].get("symbol")
        self.update_symbol_inspector()

    def update_symbol_inspector(self) -> None:
        row = self.symbol_table.currentRow()
        if row < 0 or row >= len(self._symbol_rows):
            self.inspector.clear()
            return

        payload = self._symbol_rows[row]
        detail, summary = build_inspector_model(payload)
        symbol = str(payload.get("symbol") or "Unknown")
        self.inspector.set_header(
            symbol,
            summary,
            detail["current_state"],
            tone=state_tone(payload.get("state")),
        )

        for key, field in self.inspector.fields.items():
            value = format_inspector_value(key, detail.get(key, "-"))
            tone = inspector_field_tone(key, value, payload)
            monospace = key in {"timeline", "rejection_debug", "zone_top_bottom", "last_alert_time"}
            field.set_value(str(value or "--"), tone=tone, monospace=monospace)

    def _refresh_symbol_table_view(self) -> None:
        if not self._last_snapshot:
            return
        fill_symbol_table(self, self._last_snapshot.get("symbols") or [])
        self.update_symbol_inspector()

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

