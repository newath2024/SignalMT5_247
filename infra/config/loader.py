import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from domain.enums import AlertMode

from .constants import APP_NAME, APP_TAGLINE, APP_VERSION, CONFIG_SCHEMA_VERSION, STRATEGY_NAME, STRATEGY_VERSION
from .paths import DEFAULT_CONFIG_FILE, ENV_FILE, USER_CONFIG_FILE, ensure_runtime_layout


@dataclass(frozen=True)
class AppMeta:
    name: str
    version: str
    strategy_name: str
    strategy_version: str
    schema_version: int
    tagline: str


@dataclass(frozen=True)
class ScannerConfig:
    symbols: list[str]
    symbol_aliases: dict[str, str]
    htf_timeframes: list[str]
    canonical_htf_timeframes: list[str]
    legacy_htf_timeframes: list[str]
    ltf_timeframes: list[str]
    loop_interval_sec: int
    ob_fvg_mode: str
    strict_ifvg: bool
    entry_model: str
    sl_model: str
    alert_mode: AlertMode
    cooldown_sec: int


@dataclass(frozen=True)
class TelegramConfig:
    enabled: bool
    bot_token: str
    chat_id: str


@dataclass(frozen=True)
class StorageConfig:
    state_backend: str
    history_backend: str


@dataclass(frozen=True)
class AppConfig:
    app: AppMeta
    scanner: ScannerConfig
    telegram: TelegramConfig
    storage: StorageConfig

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def split_htf_timeframes(htf_timeframes: list[str]) -> tuple[list[str], list[str]]:
    """Separate canonical HTF inputs from legacy compatibility HTF inputs."""
    canonical = [item for item in htf_timeframes if item in {"H1", "H4"}]
    legacy = [item for item in htf_timeframes if item == "M30"]
    return canonical, legacy


def load_raw_app_config() -> dict[str, Any]:
    """Load merged config payload before validation and normalization."""
    ensure_runtime_layout()

    default_payload = _load_json_file(DEFAULT_CONFIG_FILE)
    user_payload = _load_json_file(USER_CONFIG_FILE)
    env_payload = _load_env_file(ENV_FILE)

    merged = _deep_merge(default_payload, user_payload)
    telegram_payload = dict(merged.get("telegram", {}))
    if env_payload.get("TELEGRAM_BOT_TOKEN"):
        telegram_payload["bot_token"] = env_payload["TELEGRAM_BOT_TOKEN"]
    if env_payload.get("TELEGRAM_CHAT_ID"):
        telegram_payload["chat_id"] = env_payload["TELEGRAM_CHAT_ID"]
    merged["telegram"] = telegram_payload
    return merged


def validate_config_payload(raw: dict[str, Any]) -> None:
    """Validate config semantics before constructing typed runtime config."""
    app = raw.get("app", {})
    scanner = raw.get("scanner", {})
    symbol_aliases_raw = scanner.get("symbol_aliases", {})
    entry_model = str(scanner.get("entry_model", "ifvg_first_edge"))
    sl_model = str(scanner.get("sl_model", "origin_candle_extreme"))
    strict_ifvg = bool(scanner.get("strict_ifvg", True))
    ob_fvg_mode = str(scanner.get("ob_fvg_mode", "medium")).strip().lower()
    htf_timeframes = [str(item) for item in scanner.get("htf_timeframes", ["M30", "H1", "H4"])]
    ltf_timeframes = [str(item) for item in scanner.get("ltf_timeframes", ["M3", "M5", "M15"])]

    if symbol_aliases_raw is None:
        symbol_aliases_raw = {}
    if not isinstance(symbol_aliases_raw, dict):
        raise ValueError("scanner.symbol_aliases must be a key/value object.")
    if entry_model != "ifvg_first_edge":
        raise ValueError("Only 'ifvg_first_edge' is supported for entry_model in the current strategy.")
    if sl_model != "origin_candle_extreme":
        raise ValueError("Only 'origin_candle_extreme' is supported for sl_model in the current strategy.")
    if not strict_ifvg:
        raise ValueError("The current production strategy requires strict_iFVG=true.")
    if any(item not in {"M30", "H1", "H4"} for item in htf_timeframes):
        raise ValueError("Only M30, H1, and H4 are supported for HTF scanning.")
    if any(item not in {"M3", "M5", "M15"} for item in ltf_timeframes):
        raise ValueError("Only M3, M5, and M15 are supported for LTF scanning.")
    if ob_fvg_mode not in {"strict", "medium"}:
        raise ValueError("Only 'strict' and 'medium' are supported for scanner.ob_fvg_mode.")
    if int(raw.get("schema_version", app.get("schema_version", CONFIG_SCHEMA_VERSION))) != CONFIG_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported config schema version: {raw.get('schema_version', app.get('schema_version'))}. "
            f"Expected {CONFIG_SCHEMA_VERSION}."
        )


def normalize_app_config(raw: dict[str, Any]) -> AppConfig:
    """Normalize validated config into typed runtime settings."""
    validate_config_payload(raw)

    app = raw.get("app", {})
    scanner = raw.get("scanner", {})
    telegram = raw.get("telegram", {})
    storage = raw.get("storage", {})
    symbol_aliases_raw = scanner.get("symbol_aliases", {}) or {}
    htf_timeframes = [str(item) for item in scanner.get("htf_timeframes", ["M30", "H1", "H4"])]
    canonical_htf_timeframes, legacy_htf_timeframes = split_htf_timeframes(htf_timeframes)

    return AppConfig(
        app=AppMeta(
            name=str(app.get("name", APP_NAME)),
            version=str(app.get("version", APP_VERSION)),
            strategy_name=str(app.get("strategy_name", STRATEGY_NAME)),
            strategy_version=str(app.get("strategy_version", STRATEGY_VERSION)),
            schema_version=int(raw.get("schema_version", CONFIG_SCHEMA_VERSION)),
            tagline=str(app.get("tagline", APP_TAGLINE)),
        ),
        scanner=ScannerConfig(
            symbols=[str(item).upper() for item in scanner.get("symbols", [])],
            symbol_aliases={str(key): str(value).upper() for key, value in symbol_aliases_raw.items()},
            htf_timeframes=htf_timeframes,
            canonical_htf_timeframes=canonical_htf_timeframes,
            legacy_htf_timeframes=legacy_htf_timeframes,
            ltf_timeframes=[str(item) for item in scanner.get("ltf_timeframes", ["M3", "M5", "M15"])],
            loop_interval_sec=max(5, int(scanner.get("loop_interval_sec", 60))),
            ob_fvg_mode=str(scanner.get("ob_fvg_mode", "medium")).strip().lower(),
            strict_ifvg=bool(scanner.get("strict_ifvg", True)),
            entry_model=str(scanner.get("entry_model", "ifvg_first_edge")),
            sl_model=str(scanner.get("sl_model", "origin_candle_extreme")),
            alert_mode=AlertMode(str(scanner.get("alert_mode", AlertMode.BOTH.value))),
            cooldown_sec=max(0, int(scanner.get("cooldown_sec", 1800))),
        ),
        telegram=TelegramConfig(
            enabled=bool(telegram.get("enabled", True)),
            bot_token=str(telegram.get("bot_token", "")).strip(),
            chat_id=str(telegram.get("chat_id", "")).strip(),
        ),
        storage=StorageConfig(
            state_backend=str(storage.get("state_backend", "json")),
            history_backend=str(storage.get("history_backend", "sqlite")),
        ),
    )


def load_app_config() -> AppConfig:
    """Load, validate, and normalize the runtime config."""
    return normalize_app_config(load_raw_app_config())


def save_user_config_patch(patch: dict[str, Any]) -> dict[str, Any]:
    ensure_runtime_layout()
    current_payload = _load_json_file(USER_CONFIG_FILE)
    merged = _deep_merge(current_payload, patch)
    USER_CONFIG_FILE.write_text(json.dumps(merged, ensure_ascii=True, indent=2), encoding="utf-8")
    return merged
