import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _required(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Environment variable {name} is required")
    return value.strip()


def _required_int(name: str) -> int:
    raw = _required(name)
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be an integer") from exc


BOT_TOKEN = _required("BOT_TOKEN")
CHANNEL_ID = _required("CHANNEL_ID")
HASHTAG = os.getenv("HASHTAG", f"#Ищу_тебя{CHANNEL_ID}")

ADMIN_SECRET_WORD = _required("ADMIN_SECRET_WORD")
ADMIN_ACCESS_CODE = _required("ADMIN_ACCESS_CODE")
MAIN_ADMIN_ID = _required_int("MAIN_ADMIN_ID")

DATA_FILE = os.getenv("DATA_FILE", "bot_data.json")
BACKUP_FILE = os.getenv("BACKUP_FILE", "bot_backup.json")
