from __future__ import annotations


def launch_desktop(controller, auto_start: bool = True):
    try:
        from PySide6.QtCore import QTimer, Qt
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import (
            QApplication,
            QFrame,
            QGridLayout,
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QMainWindow,
            QMessageBox,
            QPushButton,
            QSpinBox,
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

    class MetricCard(QFrame):
        def __init__(self, title: str):
            super().__init__()
            self.setFrameShape(QFrame.StyledPanel)
            layout = QVBoxLayout(self)
            title_label = QLabel(title)
            title_label.setStyleSheet("font-weight: 600; color: #6b7280;")
            self.value_label = QLabel("--")
            self.value_label.setStyleSheet("font-size: 24px; font-weight: 700;")
            self.note_label = QLabel("")
            self.note_label.setWordWrap(True)
            self.note_label.setStyleSheet("color: #6b7280;")
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
            self.setWindowTitle(f"{controller.config.app.name} Control Center")
            self.resize(1460, 920)
            icon_path = BUNDLE_ROOT / "assets" / "openclaw.ico"
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))

            self.status_label = QLabel("Idle")
            self.mt5_label = QLabel("MT5: checking")
            self.telegram_label = QLabel("Telegram: checking")
            self.interval_spin = QSpinBox()
            self.interval_spin.setRange(5, 3600)
            self.interval_spin.setValue(controller.config.scanner.loop_interval_sec)
            self.start_button = QPushButton("Start")
            self.stop_button = QPushButton("Stop")
            self.symbol_table = QTableWidget(0, 6)
            self.watch_table = QTableWidget(0, 6)
            self.alert_table = QTableWidget(0, 6)
            self.log_view = QTextEdit()
            self.log_view.setReadOnly(True)

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
            header_layout = QHBoxLayout(header)
            title = QLabel(
                f"{self.controller.config.app.name}  v{self.controller.config.app.version}"
                f"  |  strategy v{self.controller.config.app.strategy_version}"
            )
            title.setStyleSheet("font-size: 20px; font-weight: 700;")
            header_layout.addWidget(title, 1)
            header_layout.addWidget(QLabel("Interval"))
            header_layout.addWidget(self.interval_spin)
            header_layout.addWidget(self.start_button)
            header_layout.addWidget(self.stop_button)
            outer.addWidget(header)

            status_row = QHBoxLayout()
            status_row.addWidget(self.status_label, 1)
            status_row.addWidget(self.mt5_label)
            status_row.addWidget(self.telegram_label)
            outer.addLayout(status_row)

            metrics_layout = QGridLayout()
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
            self.symbol_table.setHorizontalHeaderLabels(["Symbol", "Status", "Message", "Price", "Bias", "TF"])
            self.symbol_table.horizontalHeader().setStretchLastSection(True)
            self.symbol_table.setEditTriggers(QTableWidget.NoEditTriggers)
            self.symbol_table.setSelectionBehavior(QTableWidget.SelectRows)
            layout.addWidget(self.symbol_table)
            return widget

        def _build_watch_tab(self):
            widget = QWidget()
            layout = QVBoxLayout(widget)
            self.watch_table.setHorizontalHeaderLabels(["Symbol", "Status", "Bias", "TF", "HTF Context", "Swept"])
            self.watch_table.horizontalHeader().setStretchLastSection(True)
            self.watch_table.setEditTriggers(QTableWidget.NoEditTriggers)
            layout.addWidget(self.watch_table)
            return widget

        def _build_alert_tab(self):
            widget = QWidget()
            layout = QVBoxLayout(widget)
            self.alert_table.setHorizontalHeaderLabels(["Time", "Symbol", "TF", "Stage", "Status", "Reason"])
            self.alert_table.horizontalHeader().setStretchLastSection(True)
            self.alert_table.setEditTriggers(QTableWidget.NoEditTriggers)
            layout.addWidget(self.alert_table)
            return widget

        def _build_activity_tab(self):
            widget = QWidget()
            layout = QVBoxLayout(widget)
            self.log_view.setLineWrapMode(QTextEdit.NoWrap)
            layout.addWidget(self.log_view)
            return widget

        def _wire_events(self):
            self.start_button.clicked.connect(self.start_scanner)
            self.stop_button.clicked.connect(self.stop_scanner)

        def start_scanner(self):
            ok, message = self.controller.start(interval_sec=self.interval_spin.value())
            if not ok:
                QMessageBox.information(self, APP_NAME, message)

        def stop_scanner(self):
            self.controller.stop()

        def closeEvent(self, event):
            self.controller.stop()
            super().closeEvent(event)

        def refresh_snapshot(self):
            snapshot = self.controller.snapshot()
            scanner = snapshot["scanner"]
            connections = snapshot["connections"]
            metrics = snapshot["metrics"]

            self.status_label.setText(
                f"Scanner: {scanner['status'].upper()} | interval {scanner['interval_sec']}s"
            )
            self.mt5_label.setText(
                f"MT5: {'connected' if connections['mt5']['connected'] else 'disconnected'}"
            )
            telegram_text = "configured" if connections["telegram"]["configured"] else "missing config"
            self.telegram_label.setText(f"Telegram: {telegram_text}")

            self.metric_cards["active_watches"].set_value(
                str(metrics["active_watches"]),
                "Currently armed in persistent state.",
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
                "Editable before the next start.",
            )

            self._fill_table(
                self.symbol_table,
                [
                    [
                        item["symbol"],
                        item["status"],
                        item["message"],
                        "-" if item["current_price"] is None else str(item["current_price"]),
                        item.get("bias", "-"),
                        item.get("timeframe", "-"),
                    ]
                    for item in snapshot["symbols"]
                ],
            )
            self._fill_table(
                self.watch_table,
                [
                    [
                        item.get("symbol", "-"),
                        item.get("status", "-"),
                        item.get("bias", "-"),
                        item.get("timeframe", "-"),
                        item.get("htf_context", "-"),
                        ", ".join(item.get("swept_liquidity", [])) or "-",
                    ]
                    for item in snapshot["watches"]
                ],
            )
            self._fill_table(
                self.alert_table,
                [
                    [
                        item.get("created_at", "-"),
                        item.get("symbol", "-"),
                        item.get("timeframe", "-"),
                        item.get("stage", "-"),
                        item.get("status", "-"),
                        item.get("reason", "") or "-",
                    ]
                    for item in snapshot["alerts"]
                ],
            )

            lines = []
            for entry in snapshot["logs"][-80:]:
                suffix = ""
                if entry.get("reason"):
                    suffix = f" | reason={entry['reason']}"
                lines.append(
                    f"[{entry['level']}] {entry['symbol']} {entry['timeframe']} {entry['message']} | "
                    f"phase={entry['phase']}{suffix}"
                )
            self.log_view.setPlainText("\n".join(lines))

        @staticmethod
        def _fill_table(table, rows):
            table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                for column_index, value in enumerate(row):
                    item = QTableWidgetItem(str(value))
                    item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                    table.setItem(row_index, column_index, item)

    app = QApplication.instance() or QApplication([])
    window = MainWindow(controller, auto_start=auto_start)
    window.show()
    return app.exec()
