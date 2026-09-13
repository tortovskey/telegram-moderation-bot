

import logging
from .. import state
from ..config import MAIN_ADMIN_ID
from .storage import save_bot_data

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    """Проверяем, есть ли пользователь в списке админов."""
    return user_id in state.admins_list


def is_main_admin(user_id: int) -> bool:
    """Главный админ — тот, чей айди равен MAIN_ADMIN_ID из конфига."""
    return user_id == MAIN_ADMIN_ID


def add_admin(user_id: int) -> bool:
    """
    Добавить нового админа.
    Возвращает True, если действительно добавили, False если он уже админ.
    """
    if user_id not in state.admins_list:
        state.admins_list.append(user_id)
        save_bot_data()
        logger.info(f"Добавлен новый админ: {user_id}")
        return True
    return False


def remove_admin(user_id: int) -> bool:
    """
    Убрать админа (но главного админа никогда не трогаем).
    Возвращает True, если удалили.
    """
    if user_id in state.admins_list and not is_main_admin(user_id):
        state.admins_list.remove(user_id)
        save_bot_data()
        logger.info(f"Админ удалён: {user_id}")
        return True
    return False
