from __future__ import annotations

import threading
from pathlib import Path


def launch_desktop(controller, auto_start: bool = True):
    try:
        from PySide6.QtCore import QTimer, Qt
        from PySide6.QtGui import QColor, QFont, QIcon
        from PySide6.QtWidgets import (
            QAbstractItemView,
            QApplication,
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
        format_cooldown,
        format_phase,
        format_price,
        format_score,
        format_short_time,
        format_timestamp,
        format_zone,
        is_recent,
        log_matches_filter,
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
                """
            )

            self.status_label = QLabel("Idle")
            self.status_label.setStyleSheet("font-size: 13px; color: #334155;")
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

            self.symbol_table = QTableWidget(0, 10)
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

            self._timer = QTimer(self)
            self._timer.timeout.connect(self.refresh_snapshot)
            self._timer.start(2000)
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
            control_row.addWidget(self.status_label, 1)
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
            self.symbol_table.setHorizontalHeaderLabels(
                ["Symbol", "State", "Price", "HTF Bias", "TF", "Score", "Phase", "Reason", "Last Update", "Cooldown"]
            )
            self._configure_table(self.symbol_table, stretch_column=7)
            table_layout.addWidget(self.symbol_table)

            inspector_box = QGroupBox("Symbol Inspector")
            inspector_layout = QFormLayout(inspector_box)
            inspector_layout.setContentsMargins(12, 12, 12, 12)
            inspector_layout.setSpacing(10)

            for key, label_text in (
                ("current_state", "Current State"),
                ("htf_bias", "HTF Bias"),
                ("phase", "Phase"),
                ("reason", "Reason"),
                ("score", "Score"),
                ("htf_context", "HTF Context"),
                ("htf_zone_type", "HTF Zone Type"),
                ("htf_zone_source", "HTF Source"),
                ("htf_context_reason", "Context Detail"),
                ("last_detected_sweep", "Last Sweep"),
                ("last_detected_mss", "Last MSS"),
                ("last_detected_ifvg", "Last iFVG"),
                ("rejection_reason", "Rejection"),
                ("last_alert_time", "Last Alert"),
                ("last_alert_details", "Last Alert Details"),
                ("cooldown_info", "Cooldown"),
                ("active_watch_id", "Active Watch"),
                ("active_watch_info", "Active Watch Info"),
                ("zone", "Zone"),
                ("zone_top_bottom", "Zone Top/Bottom"),
                ("timeline", "Timeline"),
            ):
                value = QLabel("-")
                value.setWordWrap(True)
                value.setTextInteractionFlags(Qt.TextSelectableByMouse)
                self.inspector_fields[key] = value
                inspector_layout.addRow(label_text, value)

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
            header = table.horizontalHeader()
            header.setStretchLastSection(False)
            for index in range(table.columnCount()):
                header.setSectionResizeMode(index, QHeaderView.ResizeToContents)
            if stretch_column is not None:
                header.setSectionResizeMode(stretch_column, QHeaderView.Stretch)

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
            self.controller.stop()
            super().closeEvent(event)

        def refresh_snapshot(self):
            snapshot = self.controller.snapshot()
            self._last_snapshot = snapshot

            scanner = snapshot["scanner"]
            connections = snapshot["connections"]
            metrics = snapshot["metrics"]
            strategy = snapshot.get("strategy", {})
            current_ob_fvg_mode = str(strategy.get("ob_fvg_mode", "medium"))

            self.status_label.setText(
                f"Scanner: {scanner['status'].upper()} | interval {scanner['interval_sec']}s | OB FVG {current_ob_fvg_mode}"
            )
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

        def _fill_symbol_table(self, rows: list[dict]):
            selected_symbol = self._selected_symbol()
            self._symbol_rows = list(rows)
            self.symbol_table.setRowCount(len(rows))
            bold_font = QFont()
            bold_font.setBold(True)
            for row_index, item in enumerate(rows):
                values = [
                    item.get("symbol", "-"),
                    item.get("state", "-"),
                    format_price(item.get("price")),
                    item.get("bias", "neutral"),
                    item.get("tf", "-"),
                    format_score(item.get("score"), item.get("grade")),
                    format_phase(item.get("phase")),
                    item.get("reason", "-"),
                    format_timestamp(item.get("last_update")),
                    format_cooldown(item.get("cooldown_remaining")),
                ]
                for column_index, value in enumerate(values):
                    cell = QTableWidgetItem(str(value))
                    cell.setData(Qt.UserRole, item)
                    self.symbol_table.setItem(row_index, column_index, cell)

                state = item.get("state", "idle")
                self._paint_row(self.symbol_table, row_index, state)
                if state in {"armed", "waiting_mss", "confirmed"}:
                    self.symbol_table.item(row_index, 0).setFont(bold_font)
                    self.symbol_table.item(row_index, 1).setFont(bold_font)
                if is_recent(item.get("last_alert_time")) and state in {"confirmed", "cooldown"}:
                    accent_font = QFont(bold_font)
                    accent_font.setUnderline(True)
                    self.symbol_table.item(row_index, 0).setFont(accent_font)
                    self.symbol_table.item(row_index, 1).setFont(accent_font)

            if selected_symbol:
                for row_index, item in enumerate(rows):
                    if item.get("symbol") == selected_symbol:
                        self.symbol_table.selectRow(row_index)
                        break
            elif rows and self.symbol_table.currentRow() < 0:
                self.symbol_table.selectRow(0)

        def _fill_watch_table(self, rows: list[dict]):
            self.watch_table.setRowCount(len(rows))
            for row_index, item in enumerate(rows):
                values = [
                    item.get("symbol", "-"),
                    item.get("timeframe", "-"),
                    item.get("direction") or ("LONG" if item.get("bias") == "Long" else "SHORT" if item.get("bias") == "Short" else "-"),
                    item.get("htf_context", "-"),
                    item.get("ltf_sweep_status", "-"),
                    item.get("status", "-"),
                    item.get("waiting_for", "-"),
                    format_zone(item.get("zone_top"), item.get("zone_bottom")),
                    format_short_time(item.get("armed_at")),
                ]
                for column_index, value in enumerate(values):
                    self.watch_table.setItem(row_index, column_index, QTableWidgetItem(str(value)))
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
                payload = None
            else:
                payload = self._symbol_rows[row]

            detail = dict((payload or {}).get("detail") or {})
            detail.setdefault("current_state", (payload or {}).get("state", "-"))
            detail.setdefault("htf_bias", (payload or {}).get("bias", "-"))
            detail.setdefault("phase", format_phase((payload or {}).get("phase", "-")))
            detail.setdefault("reason", (payload or {}).get("reason", "-"))
            detail.setdefault("score", format_score((payload or {}).get("score"), (payload or {}).get("grade")))
            detail.setdefault("htf_context", (payload or {}).get("htf_context", "-"))
            detail.setdefault("last_alert_time", (payload or {}).get("last_alert_time"))
            cooldown_value = format_cooldown((payload or {}).get("cooldown_remaining"))
            if cooldown_value != "-":
                detail["cooldown_info"] = cooldown_value
            for key, label in self.inspector_fields.items():
                value = detail.get(key, "-")
                if key in {"last_alert_time"}:
                    value = format_timestamp(value)
                label.setText(str(value or "-"))

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
