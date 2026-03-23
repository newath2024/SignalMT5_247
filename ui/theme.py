from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor


FONT_FAMILY = "Segoe UI"
FONT_SIZE = 10
MONO_FONT_FAMILY = "Consolas"

BACKGROUND_PRIMARY = "#08111f"
BACKGROUND_ELEVATED = "#0d1728"
BACKGROUND_CARD = "#101b2d"
BACKGROUND_CARD_ALT = "#162338"
BACKGROUND_TABLE = "#0c1525"
BACKGROUND_INPUT = "#0b1423"
BACKGROUND_OVERLAY = "#0f1a2d"

BORDER_SUBTLE = "#20314a"
BORDER_STRONG = "#355171"
DIVIDER = "#1b2a40"

TEXT_PRIMARY = "#e5edf7"
TEXT_SECONDARY = "#9cb0c8"
TEXT_TERTIARY = "#71849d"
TEXT_DIM = "#5a6b82"

ACCENT_BLUE = "#38bdf8"
ACCENT_CYAN = "#22d3ee"
ACCENT_GREEN = "#22c55e"
ACCENT_AMBER = "#f59e0b"
ACCENT_RED = "#ef4444"
ACCENT_SLATE = "#94a3b8"

SHADOW = "#030712"

SPACE_1 = 4
SPACE_2 = 8
SPACE_3 = 12
SPACE_4 = 16
SPACE_5 = 20
SPACE_6 = 24

RADIUS_SM = 8
RADIUS_MD = 12
RADIUS_LG = 16
RADIUS_XL = 20
RADIUS_PILL = 999


@dataclass(frozen=True)
class BadgePalette:
    background: str
    foreground: str
    border: str
    dot: str


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    raw = value.lstrip("#")
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def rgba(value: str, alpha: float) -> str:
    red, green, blue = _hex_to_rgb(value)
    alpha_channel = max(0, min(255, int(round(alpha * 255))))
    return f"rgba({red}, {green}, {blue}, {alpha_channel})"


def qcolor(value: str, alpha: float = 1.0) -> QColor:
    red, green, blue = _hex_to_rgb(value)
    color = QColor(red, green, blue)
    color.setAlpha(max(0, min(255, int(round(alpha * 255)))))
    return color


def css_color(value: str) -> QColor:
    text = str(value or "").strip()
    if text.startswith("rgba(") and text.endswith(")"):
        raw = [part.strip() for part in text[5:-1].split(",")]
        if len(raw) == 4:
            red, green, blue, alpha = (int(part) for part in raw)
            return QColor(red, green, blue, alpha)
    return QColor(text)


BADGE_TONES: dict[str, BadgePalette] = {
    "neutral": BadgePalette(rgba(ACCENT_SLATE, 0.12), TEXT_SECONDARY, rgba(ACCENT_SLATE, 0.26), ACCENT_SLATE),
    "info": BadgePalette(rgba(ACCENT_BLUE, 0.16), "#c8efff", rgba(ACCENT_BLUE, 0.30), ACCENT_BLUE),
    "success": BadgePalette(rgba(ACCENT_GREEN, 0.16), "#d9fce8", rgba(ACCENT_GREEN, 0.32), ACCENT_GREEN),
    "warning": BadgePalette(rgba(ACCENT_AMBER, 0.18), "#ffe8b2", rgba(ACCENT_AMBER, 0.34), ACCENT_AMBER),
    "danger": BadgePalette(rgba(ACCENT_RED, 0.15), "#ffd3d8", rgba(ACCENT_RED, 0.30), ACCENT_RED),
    "muted": BadgePalette(rgba(ACCENT_SLATE, 0.08), TEXT_TERTIARY, rgba(ACCENT_SLATE, 0.16), TEXT_TERTIARY),
}


STATE_TO_TONE = {
    "idle": "neutral",
    "cooldown": "neutral",
    "context_found": "warning",
    "setup_building": "warning",
    "waiting_mss": "warning",
    "watch_armed": "success",
    "armed": "success",
    "entry_ready": "success",
    "confirmed": "success",
    "alerted": "success",
    "rejected": "muted",
    "expired": "muted",
    "error": "danger",
}


PRIORITY_TO_TONE = {
    "high": "success",
    "medium": "warning",
    "low": "neutral",
}


SCANNER_STATUS = {
    "idle": {"label": "IDLE", "tone": "neutral", "dot": ACCENT_SLATE, "pulse": "#b5c2d3"},
    "starting": {"label": "STARTING", "tone": "warning", "dot": ACCENT_AMBER, "pulse": "#f7c768"},
    "scanning": {"label": "SCANNING", "tone": "warning", "dot": ACCENT_AMBER, "pulse": "#ffd36d"},
    "running": {"label": "RUNNING", "tone": "success", "dot": ACCENT_GREEN, "pulse": "#57db89"},
    "stopping": {"label": "STOPPING", "tone": "danger", "dot": ACCENT_RED, "pulse": "#fb7785"},
    "stopped": {"label": "STOPPED", "tone": "danger", "dot": ACCENT_RED, "pulse": ACCENT_RED},
    "error": {"label": "ERROR", "tone": "danger", "dot": ACCENT_RED, "pulse": "#fb7785"},
}


def badge_palette(tone: str) -> BadgePalette:
    return BADGE_TONES.get(tone, BADGE_TONES["neutral"])


def state_tone(state: str | None) -> str:
    return STATE_TO_TONE.get(str(state or "").lower(), "neutral")


def state_badge_palette(state: str | None) -> BadgePalette:
    return badge_palette(state_tone(state))


def priority_tone(priority: str | None) -> str:
    return PRIORITY_TO_TONE.get(str(priority or "").lower(), "neutral")


def priority_badge_palette(priority: str | None) -> BadgePalette:
    return badge_palette(priority_tone(priority))


def bias_tone(bias: str | None) -> str:
    value = str(bias or "").strip().lower()
    if value == "long" or value == "bullish":
        return "success"
    if value == "short" or value == "bearish":
        return "danger"
    return "neutral"


def bias_badge_palette(bias: str | None) -> BadgePalette:
    return badge_palette(bias_tone(bias))


def liquidity_tone(state: str | None) -> str:
    value = str(state or "").strip().lower()
    if "reclaim" in value:
        return "success"
    if "swept" in value or "tapped" in value:
        return "warning"
    return "neutral"


def liquidity_badge_palette(state: str | None) -> BadgePalette:
    return badge_palette(liquidity_tone(state))


def reaction_tone(value: str | None) -> str:
    reaction = str(value or "").strip().lower()
    if reaction == "strong":
        return "success"
    if reaction in {"moderate", "light"}:
        return "warning"
    return "neutral"


def reaction_badge_palette(value: str | None) -> BadgePalette:
    return badge_palette(reaction_tone(value))


def scanner_status_palette(status: str | None, pulse: bool = False) -> dict[str, str]:
    entry = SCANNER_STATUS.get(str(status or "").lower(), SCANNER_STATUS["idle"])
    palette = badge_palette(entry["tone"])
    dot = entry["pulse"] if pulse else entry["dot"]
    return {
        "label": str(entry["label"]),
        "tone": str(entry["tone"]),
        "dot": str(dot),
        "background": palette.background,
        "foreground": palette.foreground,
        "border": palette.border,
    }


def connection_badge_palette(active: bool, kind: str = "default") -> BadgePalette:
    if active:
        return badge_palette("success" if kind == "mt5" else "info")
    return badge_palette("muted")


def connection_tone(active: bool, kind: str = "default") -> str:
    if active:
        return "success" if kind == "mt5" else "info"
    return "muted"


def row_palette_for_state(state: str | None) -> dict[str, QColor]:
    key = str(state or "").lower()
    if key in {"armed", "watch_armed", "entry_ready", "confirmed", "alerted"}:
        return {"background": qcolor(ACCENT_GREEN, 0.13), "foreground": qcolor(TEXT_PRIMARY)}
    if key in {"context_found", "setup_building", "waiting_mss"}:
        return {"background": qcolor(ACCENT_AMBER, 0.11), "foreground": qcolor(TEXT_PRIMARY)}
    if key in {"rejected", "expired"}:
        return {"background": qcolor(ACCENT_RED, 0.05), "foreground": qcolor(TEXT_SECONDARY)}
    if key == "error":
        return {"background": qcolor(ACCENT_RED, 0.12), "foreground": qcolor("#ffd5db")}
    if key == "cooldown":
        return {"background": qcolor(ACCENT_SLATE, 0.08), "foreground": qcolor(TEXT_SECONDARY)}
    return {"background": qcolor(ACCENT_SLATE, 0.06), "foreground": qcolor(TEXT_PRIMARY)}


def badge_stylesheet(
    palette: BadgePalette,
    *,
    padding: str = "4px 10px",
    radius: int = RADIUS_PILL,
    font_size: int = 11,
    font_weight: int = 600,
) -> str:
    return (
        "QLabel {"
        f"background: {palette.background};"
        f"color: {palette.foreground};"
        f"border: 1px solid {palette.border};"
        f"border-radius: {radius}px;"
        f"padding: {padding};"
        f"font-size: {font_size}px;"
        f"font-weight: {font_weight};"
        "}"
    )


def build_stylesheet() -> str:
    return f"""
    QMainWindow {{
        background: {BACKGROUND_PRIMARY};
    }}
    QWidget {{
        color: {TEXT_PRIMARY};
        font-family: "{FONT_FAMILY}";
        font-size: {FONT_SIZE}pt;
    }}
    QWidget#AppRoot {{
        background: {BACKGROUND_PRIMARY};
    }}
    QToolTip {{
        background: {BACKGROUND_OVERLAY};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_STRONG};
        padding: 6px 8px;
    }}
    QFrame#PanelCard,
    QFrame#StatCard,
    QFrame#SectionCard,
    QFrame#CommandBar,
    QFrame#InspectorPanel {{
        background: {BACKGROUND_CARD};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: {RADIUS_LG}px;
    }}
    QWidget[uiClass="surface"] {{
        background: transparent;
    }}
    QLabel,
    QCheckBox,
    QScrollArea > QWidget > QWidget {{
        background: transparent;
    }}
    QLabel[uiClass="eyebrow"] {{
        color: {TEXT_TERTIARY};
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.6px;
        text-transform: uppercase;
    }}
    QLabel[uiClass="heroTitle"] {{
        color: {TEXT_PRIMARY};
        font-size: 24px;
        font-weight: 700;
    }}
    QLabel[uiClass="subtitle"] {{
        color: {TEXT_SECONDARY};
        font-size: 12px;
    }}
    QLabel[uiClass="meta"] {{
        color: {TEXT_SECONDARY};
        font-size: 12px;
    }}
    QLabel[uiClass="metaMuted"] {{
        color: {TEXT_TERTIARY};
        font-size: 11px;
    }}
    QLabel[uiClass="sectionTitle"] {{
        color: {TEXT_PRIMARY};
        font-size: 13px;
        font-weight: 700;
    }}
    QLabel[uiClass="sectionHint"] {{
        color: {TEXT_TERTIARY};
        font-size: 11px;
    }}
    QLabel[uiClass="kpiTitle"] {{
        color: {TEXT_SECONDARY};
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.5px;
    }}
    QLabel[uiClass="kpiValue"] {{
        color: {TEXT_PRIMARY};
        font-size: 30px;
        font-weight: 700;
    }}
    QLabel[uiClass="kpiNote"] {{
        color: {TEXT_TERTIARY};
        font-size: 11px;
    }}
    QLabel[uiClass="fieldLabel"] {{
        color: {TEXT_TERTIARY};
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }}
    QLabel[uiClass="fieldValue"] {{
        color: {TEXT_PRIMARY};
        font-size: 12px;
        font-weight: 600;
    }}
    QLabel[uiClass="fieldValueMuted"] {{
        color: {TEXT_SECONDARY};
        font-size: 12px;
        font-weight: 500;
    }}
    QLabel[uiClass="fieldValueMultiline"] {{
        color: {TEXT_SECONDARY};
        font-size: 11px;
        font-weight: 500;
        line-height: 1.4;
    }}
    QLabel[uiClass="commandHeadline"] {{
        color: {TEXT_PRIMARY};
        font-size: 15px;
        font-weight: 700;
    }}
    QPushButton {{
        background: {BACKGROUND_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: {RADIUS_MD}px;
        padding: 8px 14px;
        min-height: 18px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background: {BACKGROUND_CARD_ALT};
        border-color: {BORDER_STRONG};
    }}
    QPushButton:pressed {{
        background: {BACKGROUND_OVERLAY};
    }}
    QPushButton:disabled {{
        color: {TEXT_DIM};
        background: {BACKGROUND_PRIMARY};
        border-color: {DIVIDER};
    }}
    QPushButton[variant="primary"] {{
        background: {rgba(ACCENT_BLUE, 0.16)};
        color: #c8efff;
        border-color: {rgba(ACCENT_BLUE, 0.34)};
    }}
    QPushButton[variant="primary"]:hover {{
        background: {rgba(ACCENT_BLUE, 0.24)};
        border-color: {rgba(ACCENT_BLUE, 0.48)};
    }}
    QPushButton[variant="primary"]:pressed {{
        background: {rgba(ACCENT_BLUE, 0.32)};
        border-color: {rgba(ACCENT_BLUE, 0.56)};
    }}
    QPushButton[variant="success"] {{
        background: {rgba(ACCENT_GREEN, 0.18)};
        color: #ddfceb;
        border-color: {rgba(ACCENT_GREEN, 0.34)};
    }}
    QPushButton[variant="success"]:hover {{
        background: {rgba(ACCENT_GREEN, 0.26)};
        border-color: {rgba(ACCENT_GREEN, 0.48)};
    }}
    QPushButton[variant="success"]:pressed {{
        background: {rgba(ACCENT_GREEN, 0.34)};
        border-color: {rgba(ACCENT_GREEN, 0.58)};
    }}
    QPushButton[variant="danger"] {{
        background: {rgba(ACCENT_RED, 0.14)};
        color: #ffd5db;
        border-color: {rgba(ACCENT_RED, 0.28)};
    }}
    QPushButton[variant="danger"]:hover {{
        background: {rgba(ACCENT_RED, 0.22)};
        border-color: {rgba(ACCENT_RED, 0.42)};
    }}
    QPushButton[variant="danger"]:pressed {{
        background: {rgba(ACCENT_RED, 0.30)};
        border-color: {rgba(ACCENT_RED, 0.52)};
    }}
    QPushButton[variant="success"]:disabled,
    QPushButton[variant="danger"]:disabled,
    QPushButton[variant="primary"]:disabled {{
        color: {TEXT_DIM};
        background: {BACKGROUND_PRIMARY};
        border-color: {DIVIDER};
    }}
    QLineEdit,
    QComboBox,
    QSpinBox {{
        background: {BACKGROUND_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: {RADIUS_MD}px;
        padding: 7px 10px;
        selection-background-color: {rgba(ACCENT_BLUE, 0.28)};
    }}
    QLineEdit:focus,
    QComboBox:focus,
    QSpinBox:focus {{
        border-color: {ACCENT_BLUE};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QSpinBox::up-button,
    QSpinBox::down-button {{
        width: 18px;
        border: none;
        background: transparent;
    }}
    QCheckBox {{
        color: {TEXT_SECONDARY};
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 14px;
        height: 14px;
        border-radius: 4px;
        border: 1px solid {BORDER_STRONG};
        background: {BACKGROUND_INPUT};
    }}
    QCheckBox::indicator:checked {{
        background: {ACCENT_BLUE};
        border-color: {ACCENT_BLUE};
    }}
    QTabWidget::pane {{
        border: 1px solid {BORDER_SUBTLE};
        border-radius: {RADIUS_LG}px;
        background: {BACKGROUND_CARD};
        top: -1px;
    }}
    QTabBar::tab {{
        background: transparent;
        color: {TEXT_TERTIARY};
        padding: 10px 14px;
        margin-right: 6px;
        border: 1px solid transparent;
        border-top-left-radius: {RADIUS_MD}px;
        border-top-right-radius: {RADIUS_MD}px;
        font-weight: 600;
    }}
    QTabBar::tab:selected {{
        background: {BACKGROUND_CARD_ALT};
        color: {TEXT_PRIMARY};
        border-color: {BORDER_STRONG};
        border-bottom-color: {ACCENT_BLUE};
    }}
    QTabBar::tab:hover:!selected {{
        color: {TEXT_PRIMARY};
        background: {rgba(ACCENT_SLATE, 0.08)};
    }}
    QSplitter::handle {{
        background: {DIVIDER};
    }}
    QTableWidget#MarketTable,
    QTableWidget#CompactTable {{
        background: {BACKGROUND_TABLE};
        alternate-background-color: {BACKGROUND_CARD_ALT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: {RADIUS_LG}px;
        gridline-color: transparent;
        selection-background-color: {rgba(ACCENT_BLUE, 0.18)};
        selection-color: {TEXT_PRIMARY};
        outline: 0;
    }}
    QHeaderView::section {{
        background: {BACKGROUND_CARD_ALT};
        color: {TEXT_SECONDARY};
        border: none;
        border-bottom: 1px solid {DIVIDER};
        padding: 10px 8px;
        font-size: 11px;
        font-weight: 700;
    }}
    QTableCornerButton::section {{
        background: {BACKGROUND_CARD_ALT};
        border: none;
        border-bottom: 1px solid {DIVIDER};
    }}
    QAbstractItemView {{
        background: transparent;
    }}
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QPlainTextEdit#LogView {{
        background: {BACKGROUND_TABLE};
        color: {TEXT_SECONDARY};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: {RADIUS_LG}px;
        padding: 10px 12px;
        selection-background-color: {rgba(ACCENT_BLUE, 0.24)};
    }}
    QScrollBar:vertical {{
        width: 12px;
        background: transparent;
        margin: 4px 0;
    }}
    QScrollBar::handle:vertical {{
        background: {rgba(ACCENT_SLATE, 0.24)};
        min-height: 28px;
        border-radius: 6px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {rgba(ACCENT_SLATE, 0.42)};
    }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        height: 0;
        background: transparent;
    }}
    """
