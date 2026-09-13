"""
reputation.py
Тут у нас:
- учёт репутации
- блокировки (бан на 24 часа)
- инфо о пользователе
- таблица репутаций для админов
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List

from .. import state  # <-- важно: два точки в начале, значит "подняться на уровень пакета Tg_Bot"
from .storage import save_bot_data  # сохраним изменения на диск

logger = logging.getLogger(__name__)


def get_user_reputation(user_id: int) -> int:
    """Вернуть текущую репутацию юзера. Если его нет в словаре — дать 10."""
    return state.user_reputation.get(user_id, 10)


def decrease_reputation(user_id: int) -> int:
    """
    Уменьшить репутацию на 1 за нарушение.
    Минимум 0.
    """
    current_rep = get_user_reputation(user_id)
    new_rep = max(0, current_rep - 1)
    state.user_reputation[user_id] = new_rep
    save_bot_data()
    return new_rep


def block_user(user_id: int, hours: int = 24) -> datetime:
    """
    Заблокировать пользователя на заданное количество часов.
    Возвращает время конца бана (datetime).
    """
    unblock_time = datetime.now() + timedelta(hours=hours)
    state.user_blocks[user_id] = unblock_time.timestamp()
    save_bot_data()
    return unblock_time


def is_user_blocked(user_id: int) -> bool:
    """
    Проверить, заблокирован ли пользователь.
    Если бан истёк — снять бан и восстановить репутацию до 10.
    """
    if user_id not in state.user_blocks:
        return False

    unblock_ts = state.user_blocks[user_id]
    if time.time() >= unblock_ts:
        # бан истёк — снимаем и возвращаем репутацию
        del state.user_blocks[user_id]
        state.user_reputation[user_id] = 10
        save_bot_data()
        return False

    return True


def get_unblock_time(user_id: int):
    """
    Вернуть datetime конца блокировки.
    Если не заблокирован — None.
    """
    if user_id in state.user_blocks:
        unblock_ts = state.user_blocks[user_id]
        return datetime.fromtimestamp(unblock_ts)
    return None


def get_user_info(user_obj) -> str:
    """
    Собрать карточку пользователя для админов,
    включая репутацию и статус блокировки.
    """
    info = (
        f"👤 Информация о пользователе:\n\n"
        f"🆔 ID: {getattr(user_obj, 'id', '—')}\n"
        f"📝 Имя: {getattr(user_obj, 'first_name', None) or 'Не указано'}\n"
        f"📝 Фамилия: {getattr(user_obj, 'last_name', None) or 'Не указана'}\n"
        f"🔗 Username: @{getattr(user_obj, 'username', None) or 'Не установлен'}\n"
        f"⭐ Репутация: {get_user_reputation(getattr(user_obj,'id',0))}/10\n"
        f"🚫 Статус: {'Заблокирован' if is_user_blocked(getattr(user_obj,'id',0)) else 'Активен'}"
    )
    return info


def get_reputation_table() -> str:
    """
    Статистика репутаций всех пользователей для администратора.
    Максимум топ-20 в тексте (чтобы не заспамить телеграм).
    """
    if not state.user_reputation:
        return "📊 Таблица репутации пуста."

    user_rows: List[Dict[str, int | str]] = []

    # Соберём имя и юзернейм из сообщений очереди
    for user_id, reputation in state.user_reputation.items():
        user_info = None

        # ищем первое сообщение в очереди от этого юзера, чтобы достать имя
        for msg in state.messages_queue:
            if msg['user'].id == user_id:
                user_info = msg['user']
                break

        if user_info:
            username = getattr(user_info, "username", None) or "Без имени"
            first_name = getattr(user_info, "first_name", None) or "Пользователь"
            user_rows.append({
                "username": username,
                "first_name": first_name,
                "reputation": reputation,
            })

    # отсортировать по репутации
    user_rows.sort(key=lambda x: x['reputation'], reverse=True)

    table = "🏆 Таблица репутации пользователей:\n\n"
    for i, row in enumerate(user_rows[:20], 1):
        table += f"{i}. {row['first_name']} (@{row['username']}) - ⭐{row['reputation']}/10\n"

    if len(user_rows) > 20:
        table += f"\n... и ещё {len(user_rows) - 20} пользователей"

    return table
