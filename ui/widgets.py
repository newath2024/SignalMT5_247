from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStyledItemDelegate,
    QStyle,
    QStyleOptionViewItem,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from .theme import (
    ACCENT_CYAN,
    ACCENT_GREEN,
    ACCENT_RED,
    BACKGROUND_CARD_ALT,
    BORDER_STRONG,
    MONO_FONT_FAMILY,
    SPACE_1,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_5,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
    badge_palette,
    badge_stylesheet,
    css_color,
    rgba,
)


BADGE_ROLE = int(Qt.UserRole) + 100


def _monospace_font(point_size: int = 9) -> QFont:
    font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
    font.setFamilies([MONO_FONT_FAMILY, font.family()])
    font.setPointSize(point_size)
    return font


def _draw_brand_mark(painter: QPainter, rect: QRectF) -> None:
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)

    size = min(rect.width(), rect.height())
    pad = size * 0.08
    canvas = rect.adjusted(pad, pad, -pad, -pad)

    shell = QPainterPath()
    shell.addRoundedRect(canvas, size * 0.18, size * 0.18)
    painter.fillPath(shell, css_color(BACKGROUND_CARD_ALT))
    painter.setPen(QPen(css_color(rgba(BORDER_STRONG, 0.75)), max(1.0, size * 0.02)))
    painter.drawPath(shell)

    center = canvas.center()
    ring_radius = size * 0.24
    ring_pen = QPen(css_color(rgba(ACCENT_CYAN, 0.78)), max(1.4, size * 0.04))
    ring_pen.setCapStyle(Qt.RoundCap)
    painter.setPen(ring_pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawEllipse(center, ring_radius, ring_radius)

    cross_pen = QPen(css_color(rgba(ACCENT_CYAN, 0.34)), max(1.0, size * 0.028))
    cross_pen.setCapStyle(Qt.RoundCap)
    painter.setPen(cross_pen)
    cross_span = ring_radius * 1.28
    cross_gap = ring_radius * 0.46
    painter.drawLine(
        center.x() - cross_span,
        center.y(),
        center.x() - cross_gap,
        center.y(),
    )
    painter.drawLine(
        center.x() + cross_gap,
        center.y(),
        center.x() + cross_span,
        center.y(),
    )
    painter.drawLine(
        center.x(),
        center.y() - cross_span,
        center.x(),
        center.y() - cross_gap,
    )
    painter.drawLine(
        center.x(),
        center.y() + cross_gap,
        center.x(),
        center.y() + cross_span,
    )

    liquidity_y = canvas.top() + canvas.height() * 0.37
    liq_pen = QPen(css_color(rgba(TEXT_SECONDARY, 0.86)), max(1.0, size * 0.03))
    liq_pen.setCapStyle(Qt.RoundCap)
    painter.setPen(liq_pen)
    painter.drawLine(
        canvas.left() + canvas.width() * 0.18,
        liquidity_y,
        canvas.right() - canvas.width() * 0.18,
        liquidity_y,
    )

    wick_pen = QPen(css_color(rgba(ACCENT_GREEN, 0.96)), max(1.4, size * 0.042))
    wick_pen.setCapStyle(Qt.RoundCap)
    painter.setPen(wick_pen)
    wick_top = canvas.top() + canvas.height() * 0.22
    wick_bottom = canvas.bottom() - canvas.height() * 0.20
    painter.drawLine(center.x(), wick_top, center.x(), wick_bottom)

    body = QRectF(
        center.x() - canvas.width() * 0.075,
        center.y() - canvas.height() * 0.11,
        canvas.width() * 0.15,
        canvas.height() * 0.24,
    )
    body_path = QPainterPath()
    body_path.addRoundedRect(body, size * 0.05, size * 0.05)
    painter.fillPath(body_path, css_color(rgba(ACCENT_GREEN, 0.90)))

    sweep_radius = size * 0.05
    painter.setPen(Qt.NoPen)
    painter.setBrush(css_color(rgba(ACCENT_RED, 0.94)))
    painter.drawEllipse(
        QRectF(
            center.x() - sweep_radius,
            liquidity_y - canvas.height() * 0.12 - sweep_radius,
            sweep_radius * 2,
            sweep_radius * 2,
        )
    )
    painter.restore()


def build_brand_icon(size: int = 64) -> QIcon:
    icon_size = max(16, int(size))
    pixmap = QPixmap(icon_size, icon_size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    _draw_brand_mark(painter, QRectF(0, 0, icon_size, icon_size))
    painter.end()
    return QIcon(pixmap)


class PanelCard(QFrame):
    def __init__(self, parent: QWidget | None = None, *, object_name: str = "PanelCard"):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setFrameShape(QFrame.NoFrame)
        self.setAttribute(Qt.WA_StyledBackground, True)


class LiveIndicator(QFrame):
    def __init__(self, size: int = 10, parent: QWidget | None = None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        self.setFrameShape(QFrame.NoFrame)
        self.set_color(TEXT_TERTIARY)

    def set_color(self, color: str) -> None:
        radius = max(2, self._size // 2)
        self.setStyleSheet(
            "QFrame {"
            f"background: {color};"
            "border: 1px solid rgba(255, 255, 255, 0.10);"
            f"border-radius: {radius}px;"
            "}"
        )


class BrandMark(QWidget):
    def __init__(self, size: int = 42, parent: QWidget | None = None):
        super().__init__(parent)
        self._size = max(20, int(size))
        self.setFixedSize(self._size, self._size)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        _draw_brand_mark(painter, QRectF(0, 0, self.width(), self.height()))
        painter.end()


class StatusBadge(QLabel):
    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.setMinimumHeight(28)
        self.set_badge(text or "--")

    def set_badge(self, text: str, tone: str = "neutral") -> None:
        self.setText(text)
        self.setStyleSheet(badge_stylesheet(badge_palette(tone), padding="5px 10px", radius=999))


class ConnectionBadge(StatusBadge):
    def __init__(self, name: str, parent: QWidget | None = None):
        self.name = name
        super().__init__(parent=parent)

    def set_connection(self, active: bool, state_text: str, tone: str) -> None:
        self.set_badge(f"{self.name}: {state_text}", tone=tone)


class StatCard(PanelCard):
    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent, object_name="StatCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_4, SPACE_4, SPACE_4, SPACE_4)
        layout.setSpacing(SPACE_1)

        self.title_label = QLabel(title)
        self.title_label.setProperty("uiClass", "kpiTitle")
        self.value_label = QLabel("--")
        self.value_label.setProperty("uiClass", "kpiValue")
        self.note_label = QLabel("")
        self.note_label.setProperty("uiClass", "kpiNote")
        self.note_label.setWordWrap(True)

        layout.addWidget(self.title_label)
        layout.addSpacing(2)
        layout.addWidget(self.value_label)
        layout.addSpacing(2)
        layout.addWidget(self.note_label)
        layout.addStretch(1)

        self.setMinimumHeight(126)

    def set_value(self, value: str, note: str) -> None:
        self.value_label.setText(value)
        self.note_label.setText(note)


class CommandBar(PanelCard):
    def __init__(self, app_name: str, version: str, strategy_version: str, tagline: str, parent: QWidget | None = None):
        super().__init__(parent, object_name="CommandBar")
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACE_5, SPACE_5, SPACE_5, SPACE_5)
        root.setSpacing(SPACE_4)

        top_row = QHBoxLayout()
        top_row.setSpacing(SPACE_4)

        brand_cluster = QHBoxLayout()
        brand_cluster.setSpacing(SPACE_3)
        brand_cluster.addWidget(BrandMark(44), 0, Qt.AlignTop)

        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        eyebrow = QLabel("Precision Liquidity Terminal")
        eyebrow.setProperty("uiClass", "eyebrow")
        self.title_label = QLabel(f"{app_name}  v{version}  |  strategy v{strategy_version}")
        self.title_label.setProperty("uiClass", "heroTitle")
        self.subtitle_label = QLabel(tagline)
        self.subtitle_label.setProperty("uiClass", "subtitle")
        title_box.addWidget(eyebrow)
        title_box.addWidget(self.title_label)
        title_box.addWidget(self.subtitle_label)
        brand_cluster.addLayout(title_box, 1)
        top_row.addLayout(brand_cluster, 1)

        control_cluster = QHBoxLayout()
        control_cluster.setSpacing(SPACE_2)
        interval_label = QLabel("Interval")
        interval_label.setProperty("uiClass", "meta")
        ob_label = QLabel("iFVG Mode")
        ob_label.setProperty("uiClass", "meta")
        self.interval_spin = QSpinBox()
        self.interval_spin.setFixedWidth(84)
        self.ob_fvg_mode_combo = QComboBox()
        self.ob_fvg_mode_combo.setFixedWidth(110)
        self.start_button = QPushButton("Arm Scanner")
        self.start_button.setProperty("variant", "success")
        self.stop_button = QPushButton("Disarm")
        self.stop_button.setProperty("variant", "danger")
        for button in (self.start_button, self.stop_button):
            button.setCursor(Qt.PointingHandCursor)
        control_cluster.addWidget(interval_label)
        control_cluster.addWidget(self.interval_spin)
        control_cluster.addSpacing(SPACE_2)
        control_cluster.addWidget(ob_label)
        control_cluster.addWidget(self.ob_fvg_mode_combo)
        control_cluster.addSpacing(SPACE_3)
        control_cluster.addWidget(self.start_button)
        control_cluster.addWidget(self.stop_button)
        top_row.addLayout(control_cluster)
        root.addLayout(top_row)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(SPACE_4)

        live_box = QVBoxLayout()
        live_box.setSpacing(6)
        status_row = QHBoxLayout()
        status_row.setSpacing(SPACE_2)
        self.live_indicator = LiveIndicator(10)
        self.status_badge = StatusBadge("STANDBY")
        self.status_title = QLabel("Scanner on standby")
        self.status_title.setProperty("uiClass", "commandHeadline")
        status_row.addWidget(self.live_indicator, 0, Qt.AlignVCenter)
        status_row.addWidget(self.status_badge, 0, Qt.AlignVCenter)
        status_row.addWidget(self.status_title, 1, Qt.AlignVCenter)
        self.scan_progress_label = QLabel("Awaiting first sweep check.")
        self.scan_progress_label.setProperty("uiClass", "meta")
        self.last_scan_label = QLabel("Last sweep check: waiting for first cycle")
        self.last_scan_label.setProperty("uiClass", "metaMuted")
        live_box.addLayout(status_row)
        live_box.addWidget(self.scan_progress_label)
        live_box.addWidget(self.last_scan_label)
        bottom_row.addLayout(live_box, 1)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(SPACE_2)
        self.mt5_badge = ConnectionBadge("MT5")
        self.telegram_badge = ConnectionBadge("Telegram")
        badge_row.addWidget(self.mt5_badge)
        badge_row.addWidget(self.telegram_badge)
        badge_row.addStretch(1)
        bottom_row.addLayout(badge_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(SPACE_2)
        self.rescan_now_button = QPushButton("Sweep Check Now")
        self.rescan_now_button.setProperty("variant", "primary")
        self.rescan_selected_button = QPushButton("Sweep Check Symbol")
        self.refresh_button = QPushButton("Refresh Panel")
        self.clear_log_button = QPushButton("Clear Telemetry")
        self.export_log_button = QPushButton("Export Telemetry")
        for button in (
            self.rescan_now_button,
            self.rescan_selected_button,
            self.refresh_button,
            self.clear_log_button,
            self.export_log_button,
        ):
            button.setCursor(Qt.PointingHandCursor)
            action_row.addWidget(button)
        bottom_row.addLayout(action_row)
        root.addLayout(bottom_row)


class InspectorField(QWidget):
    def __init__(self, title: str, *, multiline: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.multiline = multiline

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.caption_label = QLabel(title)
        self.caption_label.setProperty("uiClass", "fieldLabel")
        self.value_label = QLabel("--")
        self.value_label.setWordWrap(True)
        self.value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.value_label.setProperty("uiClass", "fieldValueMultiline" if multiline else "fieldValue")
        if multiline:
            self.value_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        layout.addWidget(self.caption_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str, *, tone: str | None = None, monospace: bool = False) -> None:
        self.value_label.setText(value or "--")
        if tone:
            self.value_label.setStyleSheet(
                badge_stylesheet(badge_palette(tone), padding="4px 8px", radius=10, font_size=11)
            )
            self.value_label.setProperty("uiClass", "")
        else:
            self.value_label.setStyleSheet("")
            self.value_label.setProperty("uiClass", "fieldValueMultiline" if self.multiline else "fieldValue")

        if monospace:
            self.value_label.setFont(_monospace_font(9))
        else:
            self.value_label.setFont(QFont())

        self.value_label.style().unpolish(self.value_label)
        self.value_label.style().polish(self.value_label)


class SectionCard(PanelCard):
    def __init__(self, title: str, hint: str | None = None, parent: QWidget | None = None):
        super().__init__(parent, object_name="SectionCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_4, SPACE_4, SPACE_4, SPACE_4)
        layout.setSpacing(SPACE_3)

        header = QVBoxLayout()
        header.setSpacing(2)

        self.title_label = QLabel(title)
        self.title_label.setProperty("uiClass", "sectionTitle")
        header.addWidget(self.title_label)

        if hint:
            self.hint_label = QLabel(hint)
            self.hint_label.setProperty("uiClass", "sectionHint")
            self.hint_label.setWordWrap(True)
            header.addWidget(self.hint_label)
        else:
            self.hint_label = None

        layout.addLayout(header)
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(SPACE_3)
        layout.addLayout(self.content_layout)

    def add_widget(self, widget: QWidget) -> None:
        self.content_layout.addWidget(widget)


class InspectorPanel(PanelCard):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent, object_name="InspectorPanel")
        self.fields: dict[str, InspectorField] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACE_4, SPACE_4, SPACE_4, SPACE_4)
        root.setSpacing(SPACE_4)

        header = QVBoxLayout()
        header.setSpacing(4)
        title = QLabel("Target Detail")
        title.setProperty("uiClass", "eyebrow")
        self.symbol_label = QLabel("No active target")
        self.symbol_label.setProperty("uiClass", "inspectorTitle")
        self.summary_label = QLabel("Select a market from Market Radar to inspect the live HTF/LTF setup context.")
        self.summary_label.setProperty("uiClass", "subtitle")
        self.status_badge = StatusBadge("Standby")

        header_row = QHBoxLayout()
        header_row.addWidget(self.symbol_label, 1)
        header_row.addWidget(self.status_badge, 0, Qt.AlignRight | Qt.AlignTop)

        header.addWidget(title)
        header.addLayout(header_row)
        header.addWidget(self.summary_label)
        root.addLayout(header)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("QFrame { color: rgba(255, 255, 255, 0.06); background: rgba(255, 255, 255, 0.06); max-height: 1px; }")
        root.addWidget(divider)

        self.placeholder_card = PanelCard(object_name="InspectorPlaceholder")
        placeholder_layout = QVBoxLayout(self.placeholder_card)
        placeholder_layout.setContentsMargins(SPACE_4, SPACE_5, SPACE_4, SPACE_5)
        placeholder_layout.setSpacing(SPACE_2)
        placeholder_title = QLabel("Radar-first workflow")
        placeholder_title.setProperty("uiClass", "sectionTitle")
        placeholder_copy = QLabel(
            "Review the market radar first. Click any market to load HTF bias, liquidity interaction, and LTF execution detail here."
        )
        placeholder_copy.setWordWrap(True)
        placeholder_copy.setProperty("uiClass", "sectionHint")
        placeholder_layout.addWidget(placeholder_title)
        placeholder_layout.addWidget(placeholder_copy)
        root.addWidget(self.placeholder_card)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        container.setProperty("uiClass", "surface")
        self.sections_layout = QVBoxLayout(container)
        self.sections_layout.setContentsMargins(0, 0, 0, 0)
        self.sections_layout.setSpacing(SPACE_4)
        self.sections_layout.addStretch(1)
        self.scroll.setWidget(container)
        root.addWidget(self.scroll, 1)

        self._container = container

    def add_section(self, title: str, fields: Iterable[tuple[str, str]], *, multiline_keys: set[str] | None = None) -> None:
        multiline_keys = multiline_keys or set()
        section = SectionCard(title)
        for key, label in fields:
            field = InspectorField(label, multiline=key in multiline_keys)
            self.fields[key] = field
            section.add_widget(field)
        self.sections_layout.insertWidget(self.sections_layout.count() - 1, section)

    def set_header(self, symbol: str, summary: str, state_label: str, tone: str) -> None:
        self.symbol_label.setText(symbol)
        self.summary_label.setText(summary)
        self.status_badge.set_badge(state_label, tone=tone)
        self.placeholder_card.hide()
        self.scroll.show()

    def clear(self) -> None:
        self.symbol_label.setText("No active target")
        self.summary_label.setText("Select a market from Market Radar to inspect the live HTF/LTF setup context.")
        self.status_badge.set_badge("Standby", tone="neutral")
        self.placeholder_card.show()
        self.scroll.hide()
        for field in self.fields.values():
            field.set_value("--")


class BadgeDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        badge = index.data(BADGE_ROLE)
        if not badge:
            super().paint(painter, option, index)
            return

        option_copy = QStyleOptionViewItem(option)
        self.initStyleOption(option_copy, index)
        option_copy.text = ""

        widget = option.widget
        style = widget.style() if widget is not None else None
        if style is not None:
            style.drawControl(QStyle.CE_ItemViewItem, option_copy, painter, widget)

        palette = badge_palette(str(badge.get("tone") or "neutral"))
        text = str(badge.get("text") or index.data(Qt.DisplayRole) or "")
        rect = option.rect.adjusted(8, 7, -8, -7)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), 10, 10)
        painter.fillPath(path, css_color(palette.background))
        painter.setPen(QPen(css_color(palette.border), 1))
        painter.drawPath(path)
        painter.setPen(css_color(palette.foreground))
        painter.drawText(rect, Qt.AlignCenter, text)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        hint = super().sizeHint(option, index)
        return QSize(max(hint.width(), 88), max(hint.height(), 32))


class ModernTableWidget(QTableWidget):
    def __init__(self, columns: int, parent: QWidget | None = None, *, compact: bool = False):
        super().__init__(0, columns, parent)
        self.setObjectName("CompactTable" if compact else "MarketTable")
        self.setFrameShape(QFrame.NoFrame)
        self.setShowGrid(False)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.setCornerButtonEnabled(False)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setFocusPolicy(Qt.NoFocus)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(40 if not compact else 36)
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setMinimumHeight(40)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    def set_badge_columns(self, *columns: int) -> None:
        for column in columns:
            self.setItemDelegateForColumn(column, BadgeDelegate(self))


class TelemetryLogView(QPlainTextEdit):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("LogView")
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setFont(_monospace_font(9))
        self.setFrameShape(QFrame.NoFrame)
