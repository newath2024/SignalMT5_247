from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QHeaderView, QLabel, QSplitter, QTabWidget, QVBoxLayout, QWidget

from ui.theme import SPACE_3, SPACE_4, SPACE_5
from ui.widgets import PanelCard, StatusBadge


def build_main_window_layout(window) -> None:
    """Build the main window layout using already-created widgets."""
    root = QWidget()
    root.setObjectName("AppRoot")
    window.setCentralWidget(root)

    outer = QVBoxLayout(root)
    outer.setContentsMargins(SPACE_5, SPACE_5, SPACE_5, SPACE_5)
    outer.setSpacing(SPACE_4)

    outer.addWidget(window.command_bar)
    outer.addLayout(build_metric_row(window))

    content_splitter = QSplitter(Qt.Horizontal)
    content_splitter.setChildrenCollapsible(False)
    content_splitter.setHandleWidth(1)
    content_splitter.addWidget(build_left_panel(window))
    content_splitter.addWidget(window.inspector)
    content_splitter.setStretchFactor(0, 7)
    content_splitter.setStretchFactor(1, 3)
    outer.addWidget(content_splitter, 1)


def build_metric_row(window):
    layout = QGridLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setHorizontalSpacing(SPACE_4)
    layout.setVerticalSpacing(SPACE_4)
    layout.addWidget(window.metric_cards["active_watches"], 0, 0)
    layout.addWidget(window.metric_cards["confirmed_signals"], 0, 1)
    layout.addWidget(window.metric_cards["coverage"], 0, 2)
    layout.addWidget(window.metric_cards["loop_interval"], 0, 3)
    for index in range(4):
        layout.setColumnStretch(index, 1)
    return layout


def build_left_panel(window) -> QWidget:
    container = QWidget()
    container.setProperty("uiClass", "surface")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    left_splitter = QSplitter(Qt.Vertical)
    left_splitter.setChildrenCollapsible(False)
    left_splitter.setHandleWidth(1)
    left_splitter.addWidget(build_symbol_tab(window))
    left_splitter.addWidget(build_secondary_panel(window))
    left_splitter.setStretchFactor(0, 7)
    left_splitter.setStretchFactor(1, 3)
    layout.addWidget(left_splitter)
    return container


def build_secondary_panel(window) -> QWidget:
    container = QWidget()
    container.setProperty("uiClass", "surface")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, SPACE_4, 0, 0)
    layout.setSpacing(0)

    tabs = QTabWidget()
    tabs.addTab(build_watch_tab(window), "Target Pipeline")
    tabs.addTab(build_alert_tab(window), "Alert Feed")
    tabs.addTab(build_activity_tab(window), "Telemetry")
    layout.addWidget(tabs)
    return container


def build_panel_card(title: str, hint: str) -> tuple[PanelCard, QVBoxLayout]:
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


def build_symbol_tab(window) -> QWidget:
    card, layout = build_panel_card(
        "Market Radar",
        "Scan every market first, then click a row to load the selected target context on the right.",
    )
    top_row = QHBoxLayout()
    top_row.setSpacing(SPACE_3)
    top_row.addWidget(window.actionable_only_checkbox)
    top_row.addWidget(window.symbol_count_label)
    top_row.addStretch(1)
    top_row.addWidget(build_legend_badge("Setup Developing", "warning"))
    top_row.addWidget(build_legend_badge("Awaiting Trigger", "warning"))
    top_row.addWidget(build_legend_badge("Armed", "success"))
    top_row.addWidget(build_legend_badge("No Valid Setup", "muted"))
    layout.addLayout(top_row)

    window.symbol_table.setHorizontalHeaderLabels(
        ["Market", "State", "HTF Thesis", "Readiness", "TF", "Price", "Priority", "Updated"]
    )
    configure_table(window.symbol_table, stretch_column=3, badge_columns=(1, 6))
    layout.addWidget(window.symbol_table, 1)
    return card


def build_watch_tab(window) -> QWidget:
    card, layout = build_panel_card(
        "Target Pipeline",
        "Persistent targeting states for tracked markets and locked execution zones.",
    )
    window.watch_table.setHorizontalHeaderLabels(
        ["Market", "TF", "Side", "HTF Thesis", "Sweep State", "Target State", "Tracking", "Zone", "Locked Since"]
    )
    configure_table(window.watch_table, stretch_column=3, badge_columns=(2, 5))
    layout.addWidget(window.watch_table, 1)
    return card


def build_alert_tab(window) -> QWidget:
    card, layout = build_panel_card(
        "Alert Feed",
        "Fresh alerts, routed executions, and blocked states from the live strategy runtime.",
    )
    window.alert_table.setHorizontalHeaderLabels(
        ["Time", "Market", "TF", "Side", "Alert", "Reason", "Entry", "SL", "Status"]
    )
    configure_table(window.alert_table, stretch_column=5, badge_columns=(3, 8))
    layout.addWidget(window.alert_table, 1)
    return card


def build_activity_tab(window) -> QWidget:
    card, layout = build_panel_card(
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
    filter_row.addWidget(window.log_filter)
    filter_row.addWidget(search_label)
    filter_row.addWidget(window.log_symbol_filter, 1)
    layout.addLayout(filter_row)
    layout.addWidget(window.log_view, 1)
    return card


def build_legend_badge(text: str, tone: str) -> StatusBadge:
    badge = StatusBadge(text)
    badge.set_badge(text, tone=tone)
    return badge


def configure_table(table, stretch_column: int | None = None, badge_columns: tuple[int, ...] = ()) -> None:
    header = table.horizontalHeader()
    for index in range(table.columnCount()):
        header.setSectionResizeMode(index, QHeaderView.ResizeToContents)
    if stretch_column is not None:
        header.setSectionResizeMode(stretch_column, QHeaderView.Stretch)
    table.set_badge_columns(*badge_columns)
