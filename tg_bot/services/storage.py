import json
import os
import logging
from datetime import datetime
from typing import Any, Dict


from ..config import DATA_FILE, BACKUP_FILE, MAIN_ADMIN_ID
from .. import state

logger = logging.getLogger(__name__)

def _serialize_message(msg: Dict[str, Any]) -> Dict[str, Any]:
    """Готовим dict так, чтобы он влез в json."""
    ts = msg.get("timestamp")
    if hasattr(ts, "isoformat"):
        ts = ts.isoformat()

    return {
        "user_id": msg["user"].id,
        "username": msg.get("username"),
        "first_name": msg.get("first_name"),
        "text": msg.get("text"),
        "photo_id": msg.get("photo_id"),
        "timestamp": ts,
        "message_id": msg.get("message_id", 0),
        "has_photo": msg.get("has_photo", False),
    }

def _restore_user(user_id: int, username: str | None, first_name: str | None):
    """
    После рестарта Telegram не даёт нам объекта User назад.
    Создаём лёгкий объект с нужными полями, чтобы старые сообщения не сломались.
    """
    u = type("User", (), {})()
    u.id = user_id
    u.username = username
    u.first_name = first_name
    u.last_name = None
    return u

def _deserialize_message(msg_data: Dict[str, Any]) -> Dict[str, Any]:
    """Берём dict из json и превращаем обратно в формат очереди."""
    ts_raw = msg_data.get("timestamp")
    try:
        ts = datetime.fromisoformat(ts_raw) if isinstance(ts_raw, str) else ts_raw
    except Exception:
        ts = datetime.now()

    restored = {
        "user": _restore_user(
            msg_data["user_id"],
            msg_data.get("username"),
            msg_data.get("first_name"),
        ),
        "username": msg_data.get("username"),
        "first_name": msg_data.get("first_name"),
        "text": msg_data.get("text", ""),
        "photo_id": msg_data.get("photo_id"),
        "timestamp": ts,
        "message_id": msg_data.get("message_id", 0),
        "has_photo": msg_data.get("has_photo", False),
    }
    return restored

def save_bot_data() -> bool:
    """
    Сливаем состояние бота (очередь, репутации, блоки, опубликованные, отклонённые)
    в JSON-файл. Это твоя "база данных".
    """
    try:
        data = {
            "messages_queue": [_serialize_message(m) for m in state.messages_queue],
            "user_reputation": state.user_reputation,
            "user_blocks": state.user_blocks,
            "admins_list": state.admins_list,
            "published_messages": [_serialize_message(m) for m in state.published_messages],
            "rejected_messages": [_serialize_message(m) for m in state.rejected_messages],
        }

        # основная копия
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # бэкап на случай крэша
        try:
            with open(BACKUP_FILE, "w", encoding="utf-8") as fb:
                json.dump(data, fb, ensure_ascii=False, indent=2)
        except Exception as backup_err:
            logger.warning(f"Не удалось сохранить BACKUP_FILE: {backup_err}")

        logger.info("Данные бота сохранены")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения данных: {e}")
        return False

def load_bot_data() -> bool:
    """
    Загружаем состояние из файла при старте бота.
    """
    try:
        if not os.path.exists(DATA_FILE):
            return False

        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # очередь сообщений
        state.messages_queue[:] = [
            _deserialize_message(msg)
            for msg in data.get("messages_queue", [])
        ]

        # репутация
        state.user_reputation.clear()
        state.user_reputation.update(data.get("user_reputation", {}))

        # блокировки
        state.user_blocks.clear()
        state.user_blocks.update(data.get("user_blocks", {}))

        # список админов (гарантируем, что главный не потеряется)
        admins_from_file = data.get("admins_list", [MAIN_ADMIN_ID])
        if MAIN_ADMIN_ID not in admins_from_file:
            admins_from_file.append(MAIN_ADMIN_ID)
        state.admins_list[:] = admins_from_file

        # опубликованные
        state.published_messages[:] = [
            _deserialize_message(msg)
            for msg in data.get("published_messages", [])
        ]

        # отклонённые
        state.rejected_messages[:] = [
            _deserialize_message(msg)
            for msg in data.get("rejected_messages", [])
        ]

        logger.info("Данные бота загружены")
        return True

    except Exception as e:
        logger.error(f"Ошибка загрузки данных: {e}")
        return False
