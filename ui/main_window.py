from __future__ import annotations

import threading
import time
from pathlib import Path


def launch_desktop(controller, auto_start: bool = True):
    try:
        from PySide6.QtCore import QTimer, Qt
        from PySide6.QtGui import QColor, QFont, QIcon
        from PySide6.QtWidgets import (
            QAbstractItemView,
            QApplication,
            QCheckBox,
            QComboBox,
            QFileDialog,
            QFormLayout,
            QFrame,
            QGridLayout,
            QGroupBox,
            QHBoxLayout,
            QHeaderView,
            QLabel,
            QMainWindow,
            QMessageBox,
            QPushButton,
            QScrollArea,
            QSpinBox,
            QSplitter,
            QTableWidget,
            QTableWidgetItem,
            QTabWidget,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:
        raise SystemExit(
            "PySide6 is not installed for this interpreter.\n"
            "Run: python -m pip install PySide6"
        ) from exc

    from core.constants import APP_NAME
    from core.paths import BUNDLE_ROOT
    from ui.presentation import (
        format_duration,
        format_cooldown,
        format_relative_age,
        format_phase,
        format_price,
        format_score,
        format_short_time,
        format_symbol_focus,
        format_htf_context_short,
        get_scanner_status_meta,
        get_priority_label,
        get_state_badge,
        get_state_label,
        format_timestamp,
        format_zone,
        is_actionable_symbol,
        is_recent,
        log_matches_filter,
        sort_symbol_rows,
        state_colors,
    )

    class MetricCard(QFrame):
        def __init__(self, title: str):
            super().__init__()
            self.setObjectName("metricCard")
            layout = QVBoxLayout(self)
            layout.setContentsMargins(16, 14, 16, 14)
            layout.setSpacing(4)
            title_label = QLabel(title)
            title_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #64748b;")
            self.value_label = QLabel("--")
            self.value_label.setStyleSheet("font-size: 26px; font-weight: 700; color: #0f172a;")
            self.note_label = QLabel("")
            self.note_label.setWordWrap(True)
            self.note_label.setStyleSheet("font-size: 12px; color: #64748b;")
            layout.addWidget(title_label)
            layout.addWidget(self.value_label)
            layout.addWidget(self.note_label)

        def set_value(self, value: str, note: str):
            self.value_label.setText(value)
            self.note_label.setText(note)

    class MainWindow(QMainWindow):
        def __init__(self, controller, auto_start: bool):
            super().__init__()
            self.controller = controller
            self.auto_start = auto_start
            self._symbol_rows = []
            self._last_snapshot = None
            self._pulse_on = False

            self.setWindowTitle(f"{controller.config.app.name} Control Center")
            self.resize(1540, 960)
            icon_path = BUNDLE_ROOT / "assets" / "openclaw.ico"
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))

            self.setStyleSheet(
                """
                QMainWindow, QWidget { background: #f8fafc; color: #0f172a; }
                QGroupBox {
                    border: 1px solid #dbe4ee;
                    border-radius: 10px;
                    margin-top: 6px;
                    background: #ffffff;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 4px;
                    color: #334155;
                    font-weight: 600;
                }
                QFrame#metricCard {
                    border: 1px solid #dbe4ee;
                    border-radius: 12px;
                    background: #ffffff;
                }
                QPushButton {
                    background: #ffffff;
                    border: 1px solid #cbd5e1;
                    border-radius: 8px;
                    padding: 6px 14px;
                }
                QPushButton:hover { background: #f8fafc; }
                QPushButton:pressed { background: #eef2f7; }
                QTableWidget {
                    background: #ffffff;
                    border: 1px solid #dbe4ee;
                    gridline-color: #e5e7eb;
                    selection-background-color: #dbeafe;
                    selection-color: #0f172a;
                }
                QHeaderView::section {
                    background: #f8fafc;
                    border: none;
                    border-bottom: 1px solid #dbe4ee;
                    border-right: 1px solid #eef2f7;
                    padding: 8px;
                    font-weight: 600;
                    color: #334155;
                }
                QTextEdit {
                    background: #ffffff;
                    border: 1px solid #dbe4ee;
                    border-radius: 10px;
                    padding: 8px;
                }
                QScrollArea {
                    border: none;
                    background: transparent;
                }
                """
            )

            self.activity_indicator = QLabel()
            self.activity_indicator.setFixedSize(12, 12)
            self.status_label = QLabel("Scanner: IDLE")
            self.status_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #334155;")
            self.scan_progress_label = QLabel("Awaiting first scan cycle.")
            self.scan_progress_label.setStyleSheet("font-size: 12px; color: #64748b;")
            self.last_scan_label = QLabel("Last scan: -")
            self.last_scan_label.setStyleSheet("font-size: 12px; color: #64748b;")
            self.mt5_label = QLabel("MT5: checking")
            self.telegram_label = QLabel("Telegram: checking")

            self.interval_spin = QSpinBox()
            self.interval_spin.setRange(5, 3600)
            self.interval_spin.setValue(controller.config.scanner.loop_interval_sec)
            self.ob_fvg_mode_combo = QComboBox()
            self.ob_fvg_mode_combo.addItem("Medium", "medium")
            self.ob_fvg_mode_combo.addItem("Strict", "strict")
            self.start_button = QPushButton("Start")
            self.stop_button = QPushButton("Stop")
            self.rescan_now_button = QPushButton("Rescan Now")
            self.rescan_selected_button = QPushButton("Rescan Selected")
            self.refresh_button = QPushButton("Refresh UI")
            self.clear_log_button = QPushButton("Clear Activity Log")
            self.export_log_button = QPushButton("Export Logs")
            self.actionable_only_checkbox = QCheckBox("Show only actionable setups")
            self.symbol_count_label = QLabel("Showing 0/0 symbols")
            self.symbol_count_label.setStyleSheet("font-size: 12px; color: #64748b;")

            self.symbol_table = QTableWidget(0, 8)
            self.watch_table = QTableWidget(0, 9)
            self.alert_table = QTableWidget(0, 9)
            self.log_view = QTextEdit()
            self.log_view.setReadOnly(True)
            self.log_filter = QComboBox()
            self.log_filter.addItem("All", "all")
            self.log_filter.addItem("Signals Only", "signals")
            self.log_filter.addItem("Warnings / Errors", "warnings")

            self.inspector_fields = {}
            self.metric_cards = {
                "active_watches": MetricCard("Active Watches"),
                "confirmed_signals": MetricCard("Confirmed Today"),
                "coverage": MetricCard("Coverage"),
                "loop_interval": MetricCard("Loop Interval"),
            }

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

        def _build_ui(self):
            root = QWidget()
            self.setCentralWidget(root)

            outer = QVBoxLayout(root)
            outer.setContentsMargins(16, 16, 16, 16)
            outer.setSpacing(12)

            header = QGroupBox()
            header_layout = QVBoxLayout(header)
            header_layout.setContentsMargins(12, 12, 12, 12)
            header_layout.setSpacing(10)

            top_row = QHBoxLayout()
            title = QLabel(
                f"{self.controller.config.app.name}  v{self.controller.config.app.version}"
                f"  |  strategy v{self.controller.config.app.strategy_version}"
            )
            title.setStyleSheet("font-size: 22px; font-weight: 700; color: #0f172a;")
            subtitle = QLabel(self.controller.config.app.tagline)
            subtitle.setStyleSheet("font-size: 12px; color: #64748b;")
            title_box = QVBoxLayout()
            title_box.addWidget(title)
            title_box.addWidget(subtitle)
            top_row.addLayout(title_box, 1)
            top_row.addWidget(QLabel("Interval"))
            top_row.addWidget(self.interval_spin)
            top_row.addWidget(QLabel("OB FVG"))
            top_row.addWidget(self.ob_fvg_mode_combo)
            top_row.addWidget(self.start_button)
            top_row.addWidget(self.stop_button)
            header_layout.addLayout(top_row)

            control_row = QHBoxLayout()
            status_box = QVBoxLayout()
            status_box.setSpacing(2)
            status_top_row = QHBoxLayout()
            status_top_row.setSpacing(8)
            status_top_row.addWidget(self.activity_indicator, 0, Qt.AlignVCenter)
            status_top_row.addWidget(self.status_label, 1)
            status_top_row.addStretch(1)
            status_bottom_row = QHBoxLayout()
            status_bottom_row.setSpacing(12)
            status_bottom_row.addWidget(self.scan_progress_label)
            status_bottom_row.addWidget(self.last_scan_label)
            status_bottom_row.addStretch(1)
            status_box.addLayout(status_top_row)
            status_box.addLayout(status_bottom_row)
            control_row.addLayout(status_box, 1)
            control_row.addWidget(self.mt5_label)
            control_row.addWidget(self.telegram_label)
            control_row.addSpacing(12)
            control_row.addWidget(self.rescan_now_button)
            control_row.addWidget(self.rescan_selected_button)
            control_row.addWidget(self.refresh_button)
            control_row.addWidget(self.clear_log_button)
            control_row.addWidget(self.export_log_button)
            header_layout.addLayout(control_row)
            outer.addWidget(header)

            metrics_layout = QGridLayout()
            metrics_layout.setHorizontalSpacing(12)
            metrics_layout.setVerticalSpacing(12)
            metrics_layout.addWidget(self.metric_cards["active_watches"], 0, 0)
            metrics_layout.addWidget(self.metric_cards["confirmed_signals"], 0, 1)
            metrics_layout.addWidget(self.metric_cards["coverage"], 0, 2)
            metrics_layout.addWidget(self.metric_cards["loop_interval"], 0, 3)
            outer.addLayout(metrics_layout)

            tabs = QTabWidget()
            tabs.addTab(self._build_symbol_tab(), "Symbol Health")
            tabs.addTab(self._build_watch_tab(), "Watch Pipeline")
            tabs.addTab(self._build_alert_tab(), "Recent Alerts")
            tabs.addTab(self._build_activity_tab(), "Activity Log")
            outer.addWidget(tabs, 1)

        def _build_symbol_tab(self):
            widget = QWidget()
            layout = QVBoxLayout(widget)

            splitter = QSplitter(Qt.Horizontal)
            splitter.setChildrenCollapsible(False)

            table_box = QGroupBox("Scanner State")
            table_layout = QVBoxLayout(table_box)
            table_layout.setContentsMargins(10, 12, 10, 10)
            table_header_row = QHBoxLayout()
            table_header_row.addWidget(self.actionable_only_checkbox)
            table_header_row.addWidget(self.symbol_count_label)
            table_header_row.addStretch(1)
            table_header_row.addWidget(self._make_legend_pill("⚪ Idle", "idle"))
            table_header_row.addWidget(self._make_legend_pill("🟡 Waiting", "context_found"))
            table_header_row.addWidget(self._make_legend_pill("🟢 Armed / Ready", "armed"))
            table_header_row.addWidget(self._make_legend_pill("🔴 Rejected", "rejected"))
            table_layout.addLayout(table_header_row)
            self.symbol_table.setHorizontalHeaderLabels(
                ["Symbol", "Status", "HTF", "Next", "TF", "Price", "Priority", "Updated"]
            )
            self._configure_table(self.symbol_table, stretch_column=3)
            table_layout.addWidget(self.symbol_table)

            inspector_box = QGroupBox("Symbol Inspector")
            inspector_box_layout = QVBoxLayout(inspector_box)
            inspector_box_layout.setContentsMargins(10, 12, 10, 10)

            inspector_scroll = QScrollArea()
            inspector_scroll.setWidgetResizable(True)
            inspector_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            inspector_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            inspector_scroll.setFrameShape(QFrame.NoFrame)

            inspector_panel = QWidget()
            inspector_layout = QVBoxLayout(inspector_panel)
            inspector_layout.setContentsMargins(12, 12, 12, 12)
            inspector_layout.setSpacing(12)

            self._add_inspector_section(
                inspector_layout,
                "Status",
                (
                    ("current_state", "Current State"),
                    ("priority", "Priority"),
                    ("phase", "Phase"),
                    ("reason", "Next Step"),
                    ("score", "Score"),
                    ("cooldown_info", "Cooldown"),
                ),
            )
            self._add_inspector_section(
                inspector_layout,
                "HTF Context",
                (
                    ("htf_bias", "HTF Bias"),
                    ("htf_context", "Context"),
                    ("htf_zone_type", "Zone Type"),
                    ("zone", "Zone"),
                    ("htf_zone_source", "Source"),
                ),
            )
            self._add_inspector_section(
                inspector_layout,
                "Structure",
                (
                    ("market_structure_bias", "Market Bias"),
                    ("liquidity_interaction_state", "Liquidity"),
                    ("reaction_strength", "Reaction"),
                    ("htf_context_reason", "Context Note"),
                    ("timeline", "Recent Timeline"),
                ),
            )
            self._add_inspector_section(
                inspector_layout,
                "LTF Confirmation",
                (
                    ("last_detected_sweep", "Last Sweep"),
                    ("last_detected_mss", "MSS"),
                    ("last_detected_ifvg", "iFVG"),
                    ("active_watch_info", "Watch"),
                    ("zone_top_bottom", "Entry Zone"),
                    ("last_alert_time", "Last Alert"),
                    ("rejection_reason", "Rejection"),
                ),
            )
            inspector_layout.addStretch(1)

            inspector_scroll.setWidget(inspector_panel)
            inspector_box_layout.addWidget(inspector_scroll)

            splitter.addWidget(table_box)
            splitter.addWidget(inspector_box)
            splitter.setStretchFactor(0, 4)
            splitter.setStretchFactor(1, 2)
            layout.addWidget(splitter)
            return widget

        def _build_watch_tab(self):
            widget = QWidget()
            layout = QVBoxLayout(widget)
            box = QGroupBox("Watch Pipeline")
            inner = QVBoxLayout(box)
            inner.setContentsMargins(10, 12, 10, 10)
            self.watch_table.setHorizontalHeaderLabels(
                ["Symbol", "TF", "Direction", "HTF Context", "LTF Sweep", "Current State", "Waiting For", "Zone", "Armed Since"]
            )
            self._configure_table(self.watch_table, stretch_column=3)
            inner.addWidget(self.watch_table)
            layout.addWidget(box)
            return widget

        def _build_alert_tab(self):
            widget = QWidget()
            layout = QVBoxLayout(widget)
            box = QGroupBox("Recent Alerts")
            inner = QVBoxLayout(box)
            inner.setContentsMargins(10, 12, 10, 10)
            self.alert_table.setHorizontalHeaderLabels(
                ["Time", "Symbol", "TF", "Direction", "Alert Type", "Reason", "Entry", "SL", "Status"]
            )
            self._configure_table(self.alert_table, stretch_column=5)
            inner.addWidget(self.alert_table)
            layout.addWidget(box)
            return widget

        def _build_activity_tab(self):
            widget = QWidget()
            layout = QVBoxLayout(widget)
            box = QGroupBox("Activity Log")
            inner = QVBoxLayout(box)
            inner.setContentsMargins(10, 12, 10, 10)

            filter_row = QHBoxLayout()
            filter_row.addWidget(QLabel("Filter"))
            filter_row.addWidget(self.log_filter)
            filter_row.addStretch(1)
            inner.addLayout(filter_row)

            self.log_view.setLineWrapMode(QTextEdit.NoWrap)
            inner.addWidget(self.log_view)
            layout.addWidget(box)
            return widget

        @staticmethod
        def _configure_table(table, stretch_column: int | None = None):
            table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            table.setSelectionBehavior(QAbstractItemView.SelectRows)
            table.setSelectionMode(QAbstractItemView.SingleSelection)
            table.setAlternatingRowColors(False)
            table.verticalHeader().setVisible(False)
            table.verticalHeader().setDefaultSectionSize(32)
            header = table.horizontalHeader()
            header.setStretchLastSection(False)
            for index in range(table.columnCount()):
                header.setSectionResizeMode(index, QHeaderView.ResizeToContents)
            if stretch_column is not None:
                header.setSectionResizeMode(stretch_column, QHeaderView.Stretch)

        def _make_legend_pill(self, text: str, state: str) -> QLabel:
            palette = state_colors(state)
            pill = QLabel(text)
            pill.setStyleSheet(
                "padding: 4px 10px; border-radius: 999px; "
                f"background: {palette['bg']}; color: {palette['fg']}; font-size: 12px; font-weight: 600;"
            )
            return pill

        def _create_inspector_value_label(self) -> QLabel:
            value = QLabel("-")
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value.setStyleSheet("font-size: 12px; color: #0f172a;")
            return value

        def _add_inspector_section(self, parent_layout, title: str, fields):
            section = QGroupBox(title)
            form = QFormLayout(section)
            form.setContentsMargins(10, 12, 10, 10)
            form.setSpacing(8)
            for key, label_text in fields:
                value = self._create_inspector_value_label()
                self.inspector_fields[key] = value
                form.addRow(label_text, value)
            parent_layout.addWidget(section)

        def _wire_events(self):
            self.start_button.clicked.connect(self.start_scanner)
            self.stop_button.clicked.connect(self.stop_scanner)
            self.rescan_now_button.clicked.connect(self.rescan_now)
            self.rescan_selected_button.clicked.connect(self.rescan_selected_symbol)
            self.refresh_button.clicked.connect(self.refresh_snapshot)
            self.clear_log_button.clicked.connect(self.clear_activity_log)
            self.export_log_button.clicked.connect(self.export_logs)
            self.ob_fvg_mode_combo.currentIndexChanged.connect(self.change_ob_fvg_mode)
            self.log_filter.currentIndexChanged.connect(self.refresh_activity_log)
            self.actionable_only_checkbox.stateChanged.connect(self._refresh_symbol_table_view)
            self.symbol_table.itemSelectionChanged.connect(self.update_symbol_inspector)

        def _selected_symbol(self) -> str | None:
            row = self.symbol_table.currentRow()
            if row < 0 or row >= len(self._symbol_rows):
                return None
            return self._symbol_rows[row]["symbol"]

        def _run_background(self, target):
            thread = threading.Thread(target=target, daemon=True)
            thread.start()

        def start_scanner(self):
            ok, message = self.controller.start(interval_sec=self.interval_spin.value())
            if not ok:
                QMessageBox.information(self, APP_NAME, message)

        def stop_scanner(self):
            self.controller.stop()

        def rescan_now(self):
            self._run_background(self.controller.rescan_now)

        def rescan_selected_symbol(self):
            symbol = self._selected_symbol()
            if not symbol:
                QMessageBox.information(self, APP_NAME, "Select a symbol first.")
                return
            self._run_background(lambda: self.controller.rescan_symbol(symbol))

        def clear_activity_log(self):
            self.controller.clear_activity_log()
            self.refresh_snapshot()

        def export_logs(self):
            default_path = Path(self.controller.logger.log_file).with_name("openclaw_export.log")
            target, _ = QFileDialog.getSaveFileName(
                self,
                "Export Logs",
                str(default_path),
                "Log Files (*.log);;Text Files (*.txt)",
            )
            if not target:
                return
            Path(target).write_text(self.log_view.toPlainText(), encoding="utf-8")

        def change_ob_fvg_mode(self, _index=None):
            mode = self.ob_fvg_mode_combo.currentData()
            if not mode:
                return
            ok, message = self.controller.set_ob_fvg_mode(mode)
            if not ok:
                QMessageBox.information(self, APP_NAME, message)
            self.refresh_snapshot()

        def closeEvent(self, event):
            self.controller.shutdown()
            super().closeEvent(event)

        def refresh_snapshot(self):
            snapshot = self.controller.snapshot()
            self._last_snapshot = snapshot

            scanner = snapshot["scanner"]
            connections = snapshot["connections"]
            metrics = snapshot["metrics"]
            strategy = snapshot.get("strategy", {})
            current_ob_fvg_mode = str(strategy.get("ob_fvg_mode", "medium"))

            self.mt5_label.setText(
                f"MT5: {'connected' if connections['mt5']['connected'] else 'disconnected'}"
            )
            telegram_text = "configured" if connections["telegram"]["configured"] else "missing config"
            self.telegram_label.setText(f"Telegram: {telegram_text}")
            previous_signal_state = self.ob_fvg_mode_combo.blockSignals(True)
            combo_index = self.ob_fvg_mode_combo.findData(current_ob_fvg_mode)
            if combo_index >= 0 and combo_index != self.ob_fvg_mode_combo.currentIndex():
                self.ob_fvg_mode_combo.setCurrentIndex(combo_index)
            self.ob_fvg_mode_combo.blockSignals(previous_signal_state)

            self.metric_cards["active_watches"].set_value(
                str(metrics["active_watches"]),
                "Armed or waiting for MSS in persistent state.",
            )
            self.metric_cards["confirmed_signals"].set_value(
                str(metrics["confirmed_signals_today"]),
                "Counted from SQLite history.",
            )
            self.metric_cards["coverage"].set_value(
                f"{metrics['scanned_symbols']}/{metrics['total_symbols']}",
                "Symbols scanned in the current session.",
            )
            self.metric_cards["loop_interval"].set_value(
                f"{scanner['interval_sec']}s",
                "Used for the next scanner cycle.",
            )

            self._fill_symbol_table(snapshot["symbols"])
            self._fill_watch_table(snapshot["watches"])
            self._fill_alert_table(snapshot["alerts"])
            self.refresh_activity_log()
            self.update_symbol_inspector()
            self._render_status_feedback()

        def _tick_status_feedback(self):
            self._pulse_on = not self._pulse_on
            self._render_status_feedback()

        def _render_status_feedback(self):
            snapshot = self._last_snapshot
            if not snapshot:
                return

            scanner = snapshot["scanner"]
            metrics = snapshot["metrics"]
            strategy = snapshot.get("strategy", {})
            status = str(scanner.get("status") or "idle").lower()
            pulse = bool(scanner.get("running")) and status in {"running", "scanning", "starting"}
            meta = get_scanner_status_meta(status, pulse=self._pulse_on and pulse)
            self.activity_indicator.setStyleSheet(
                f"background: {meta['dot']}; border-radius: 6px; border: 1px solid rgba(15, 23, 42, 0.10);"
            )
            self.status_label.setText(self._build_status_headline(scanner))
            self.scan_progress_label.setText(self._build_scan_progress_text(scanner, metrics, strategy))
            self.last_scan_label.setText(self._build_last_scan_text(scanner))

        @staticmethod
        def _build_status_headline(scanner: dict) -> str:
            status = str(scanner.get("status") or "idle").lower()
            meta = get_scanner_status_meta(status)
            progress = dict(scanner.get("progress") or {})
            if status == "scanning":
                total = max(0, int(progress.get("total") or 0))
                current = max(1, int(progress.get("current") or 0)) if total else int(progress.get("current") or 0)
                if total:
                    return f"Scanner: {meta['label']} ({current}/{total} symbols)"
                return f"Scanner: {meta['label']}"
            if status == "running":
                next_scan_at = scanner.get("next_scan_at")
                if next_scan_at is not None:
                    remaining = max(0, int(next_scan_at - time.time()))
                    return f"Scanner: {meta['label']} (next scan in {format_duration(remaining)})"
            return f"Scanner: {meta['label']}"

        @staticmethod
        def _build_scan_progress_text(scanner: dict, metrics: dict, strategy: dict) -> str:
            progress = dict(scanner.get("progress") or {})
            status = str(scanner.get("status") or "idle").lower()
            pieces = []
            if status == "scanning":
                total = max(0, int(progress.get("total") or 0))
                current = max(1, int(progress.get("current") or 0)) if total else int(progress.get("current") or 0)
                if total:
                    pieces.append(f"Scanning {current}/{total} symbols...")
                current_symbol = progress.get("current_symbol")
                if current_symbol:
                    pieces.append(f"Current symbol {current_symbol}")
            else:
                scanned_symbols = int(metrics.get("scanned_symbols") or 0)
                total_symbols = int(metrics.get("total_symbols") or 0)
                if total_symbols:
                    pieces.append(f"Coverage {scanned_symbols}/{total_symbols}")
            pieces.append(f"Interval {scanner.get('interval_sec', 0)}s")
            pieces.append(f"OB FVG {strategy.get('ob_fvg_mode', 'medium')}")
            if status == "error" and scanner.get("last_error"):
                pieces.append(f"Error: {scanner['last_error']}")
            return " | ".join(piece for piece in pieces if piece)

        @staticmethod
        def _build_last_scan_text(scanner: dict) -> str:
            last_cycle = dict(scanner.get("last_cycle") or {})
            finished_at = last_cycle.get("finished_at")
            if finished_at:
                return f"Last scan: {format_short_time(finished_at)} ({format_relative_age(finished_at)})"
            progress = dict(scanner.get("progress") or {})
            if progress.get("active") and progress.get("started_at"):
                return f"Current cycle: started {format_short_time(progress['started_at'])} ({format_relative_age(progress['started_at'])})"
            return "Last scan: waiting for first cycle"

        def _fill_symbol_table(self, rows: list[dict]):
            selected_symbol = self._selected_symbol()
            display_rows = sort_symbol_rows(rows)
            total_rows = len(display_rows)
            if self.actionable_only_checkbox.isChecked():
                display_rows = [item for item in display_rows if is_actionable_symbol(item)]
            self._symbol_rows = display_rows
            self.symbol_count_label.setText(f"Showing {len(display_rows)}/{total_rows} symbols")
            self.symbol_table.setRowCount(len(display_rows))
            bold_font = QFont()
            bold_font.setBold(True)
            for row_index, item in enumerate(display_rows):
                state = item.get("state", "idle")
                priority = get_priority_label(item)
                values = [
                    item.get("symbol", "-"),
                    get_state_badge(state),
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
                    self.symbol_table.setItem(row_index, column_index, cell)

                self._paint_row(self.symbol_table, row_index, state)
                if priority == "High":
                    for column_index in range(self.symbol_table.columnCount()):
                        current_item = self.symbol_table.item(row_index, column_index)
                        if current_item is not None:
                            current_item.setFont(bold_font)
                if is_recent(item.get("last_alert_time")) and state in {"confirmed", "cooldown"}:
                    accent_font = QFont(bold_font)
                    accent_font.setUnderline(True)
                    self.symbol_table.item(row_index, 0).setFont(accent_font)
                    self.symbol_table.item(row_index, 1).setFont(accent_font)

            if selected_symbol:
                for row_index, item in enumerate(display_rows):
                    if item.get("symbol") == selected_symbol:
                        self.symbol_table.selectRow(row_index)
                        break
            elif display_rows and self.symbol_table.currentRow() < 0:
                self.symbol_table.selectRow(0)

        def _fill_watch_table(self, rows: list[dict]):
            self.watch_table.setRowCount(len(rows))
            for row_index, item in enumerate(rows):
                values = [
                    item.get("symbol", "-"),
                    item.get("timeframe", "-"),
                    item.get("direction") or ("LONG" if item.get("bias") == "Long" else "SHORT" if item.get("bias") == "Short" else "-"),
                    format_htf_context_short({"htf_context": item.get("htf_context"), "detail": {}}),
                    item.get("ltf_sweep_status", "-"),
                    get_state_badge(item.get("status")),
                    item.get("waiting_for", "-"),
                    format_zone(item.get("zone_top"), item.get("zone_bottom")),
                    format_short_time(item.get("armed_at")),
                ]
                for column_index, value in enumerate(values):
                    watch_cell = QTableWidgetItem(str(value))
                    if column_index in {1, 2, 5, 8}:
                        watch_cell.setTextAlignment(Qt.AlignCenter)
                    self.watch_table.setItem(row_index, column_index, watch_cell)
                self._paint_row(self.watch_table, row_index, item.get("status", "idle"))

        def _fill_alert_table(self, rows: list[dict]):
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
                    self.alert_table.setItem(row_index, column_index, QTableWidgetItem(str(value)))
                alert_state = "confirmed" if item.get("status") == "sent" else "rejected" if "blocked" in str(item.get("status")) else "idle"
                self._paint_row(self.alert_table, row_index, alert_state, tint_only=True)

        def refresh_activity_log(self):
            if not self._last_snapshot:
                return
            filter_key = self.log_filter.currentData()
            lines = []
            for entry in self._last_snapshot["logs"]:
                if not log_matches_filter(entry, filter_key):
                    continue
                suffix = ""
                if entry.get("reason"):
                    suffix = f" | reason={entry['reason']}"
                lines.append(
                    f"[{entry['level']}] {entry['symbol']} {entry['timeframe']} {entry['message']} | "
                    f"phase={entry['phase']}{suffix}"
                )
            self.log_view.setPlainText("\n".join(lines[-150:]))

        def update_symbol_inspector(self):
            row = self.symbol_table.currentRow()
            if row < 0 or row >= len(self._symbol_rows):
                for label in self.inspector_fields.values():
                    label.setText("-")
                return
            else:
                payload = self._symbol_rows[row]

            detail = dict((payload or {}).get("detail") or {})
            detail["current_state"] = get_state_badge((payload or {}).get("state", "-"))
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
            detail["timeline"] = self._format_detail_text(detail.get("timeline"))
            detail["zone"] = self._format_detail_text(detail.get("zone"))
            detail["zone_top_bottom"] = self._format_detail_text(detail.get("zone_top_bottom"))
            detail["htf_zone_source"] = self._format_detail_text(detail.get("htf_zone_source"))
            cooldown_value = format_cooldown((payload or {}).get("cooldown_remaining"))
            if cooldown_value != "-":
                detail["cooldown_info"] = cooldown_value
            for key, label in self.inspector_fields.items():
                value = detail.get(key, "-")
                if key in {"last_alert_time"}:
                    value = format_timestamp(value)
                label.setText(str(value or "-"))

        def _refresh_symbol_table_view(self):
            if not self._last_snapshot:
                return
            self._fill_symbol_table(self._last_snapshot.get("symbols") or [])
            self.update_symbol_inspector()

        @staticmethod
        def _format_detail_text(value) -> str:
            text = str(value or "-").strip()
            if not text or text == "-":
                return "-"
            return (
                text.replace("Previous Day High", "PDH")
                .replace("Previous Day Low", "PDL")
                .replace("Previous Week High", "PWH")
                .replace("Previous Week Low", "PWL")
            )

        def _format_structure_note(self, payload: dict | None, detail: dict) -> str:
            liquidity_state = str(detail.get("liquidity_interaction_state") or "").strip()
            reaction = str(detail.get("reaction_strength") or "-").strip()
            market_bias = str(detail.get("market_structure_bias") or detail.get("htf_bias") or "-").strip()
            if liquidity_state and liquidity_state not in {"-", "Untouched"}:
                context = format_htf_context_short(payload)
                return f"{context} | {reaction} reaction | {market_bias}"
            zone_type = str(detail.get("htf_zone_type") or "").strip()
            if zone_type and zone_type != "-":
                return f"{zone_type} | {reaction} reaction | {market_bias}"
            return self._format_detail_text(detail.get("htf_context_reason"))

        @staticmethod
        def _paint_row(table, row_index: int, state: str, tint_only: bool = False):
            palette = state_colors(state)
            background = QColor(palette["bg"])
            foreground = QColor(palette["fg"])
            for column_index in range(table.columnCount()):
                item = table.item(row_index, column_index)
                if item is None:
                    continue
                if not tint_only or column_index in {0, 1, table.columnCount() - 1}:
                    item.setBackground(background)
                item.setForeground(foreground)

    app = QApplication.instance() or QApplication([])
    window = MainWindow(controller, auto_start=auto_start)
    window.show()
    return app.exec()
