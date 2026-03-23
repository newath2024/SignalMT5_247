import json

import requests

from ..config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, save_local_env_value
from ..utils import log
from .message_builder import build_signal_caption

_telegram_chat_id = TELEGRAM_CHAT_ID


def telegram_is_configured():
    return not get_telegram_missing_fields()


def get_telegram_missing_fields():
    missing = []
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN.startswith("YOUR_"):
        missing.append("TELEGRAM_BOT_TOKEN")
    if not _telegram_chat_id or _telegram_chat_id.startswith("YOUR_"):
        missing.append("TELEGRAM_CHAT_ID")
    return missing


def fetch_latest_telegram_chat_id():
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN.startswith("YOUR_"):
        return None

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        log(f"Telegram chat lookup failed: {exc}")
        return None

    updates = payload.get("result", [])
    for update in reversed(updates):
        message = update.get("message") or update.get("edited_message")
        if message and "chat" in message and "id" in message["chat"]:
            return str(message["chat"]["id"])
    return None


def ensure_telegram_chat_id():
    global _telegram_chat_id

    if _telegram_chat_id and not _telegram_chat_id.startswith("YOUR_"):
        return _telegram_chat_id

    chat_id = fetch_latest_telegram_chat_id()
    if not chat_id:
        return None

    _telegram_chat_id = chat_id
    save_local_env_value("TELEGRAM_CHAT_ID", chat_id)
    log(f"Detected Telegram chat id automatically: {chat_id}")
    return chat_id


def send_telegram(message):
    if TELEGRAM_BOT_TOKEN and not TELEGRAM_BOT_TOKEN.startswith("YOUR_"):
        ensure_telegram_chat_id()

    if not telegram_is_configured():
        missing_fields = ", ".join(get_telegram_missing_fields())
        log(f"Telegram is not configured, missing: {missing_fields}.")
        log("Open your bot in Telegram, send /start once, then run the script again.")
        log(message)
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": _telegram_chat_id, "text": message}

    try:
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        log(f"Telegram send failed: {exc}")
        return False


def send_signal_package(signal, htf_chart_path, ltf_chart_path):
    if TELEGRAM_BOT_TOKEN and not TELEGRAM_BOT_TOKEN.startswith("YOUR_"):
        ensure_telegram_chat_id()

    if not telegram_is_configured():
        missing_fields = ", ".join(get_telegram_missing_fields())
        log(f"Telegram is not configured, missing: {missing_fields}.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMediaGroup"
    caption = build_signal_caption(signal)
    media = [
        {"type": "photo", "media": "attach://htf_chart", "caption": caption},
        {"type": "photo", "media": "attach://ltf_chart"},
    ]

    with open(htf_chart_path, "rb") as htf_file, open(ltf_chart_path, "rb") as ltf_file:
        files = {
            "htf_chart": htf_file,
            "ltf_chart": ltf_file,
        }
        try:
            response = requests.post(
                url,
                data={"chat_id": _telegram_chat_id, "media": json.dumps(media)},
                files=files,
                timeout=30,
            )
            response.raise_for_status()
            return True
        except requests.RequestException as exc:
            log(f"Telegram media send failed: {exc}")
            return False
