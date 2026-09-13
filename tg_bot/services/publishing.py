"""
publishing.py
Логика публикации и уведомления админов:
- отправка заявки модераторам (текст / фото)
- публикация одобренного поста в канал
"""

import logging
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .. import state                              # глобальное состояние
from ..config import CHANNEL_ID, HASHTAG          # настройки канала/хэштега
from .reputation  import get_user_reputation       # рейтинг юзера
from .storage import save_bot_data                # чтобы фиксировать опубликованное

logger = logging.getLogger(__name__)


async def send_approval_request(context: ContextTypes.DEFAULT_TYPE, message_data: dict, queue_index: int):
    """
    Отправить админам карточку сообщения (только текст).
    Админы получают кнопки "✅ Одобрить" / "❌ Отклонить" / "👤 Инфо".
    """
    user_rep = get_user_reputation(message_data['user'].id)

    keyboard = [
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{queue_index}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{queue_index}"),
        ],
        [
            InlineKeyboardButton("👤 Информация пользователя", callback_data=f"userinfo_{queue_index}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = (
        "📩 Новое сообщение для публикации:\n\n"
        f"👤 От: {message_data['first_name']} (@{message_data['username']})\n"
        f"⭐ Репутация: {user_rep}/10\n"
        f"📝 Текст: {message_data['text']}\n\n"
        "Опубликовать в канал?"
    )

    # помечаем это сообщение как ожидающее решения
    state.pending_approvals[queue_index] = message_data

    # рассылаем всем админам
    for admin_id in state.admins_list:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=message_text,
                reply_markup=reply_markup
            )
            logger.info(
                f"Запрос на одобрение (текст) отправлен админу {admin_id} для сообщения {queue_index}"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки админу {admin_id}: {e}")


async def send_photo_approval_request(context: ContextTypes.DEFAULT_TYPE, message_data: dict, queue_index: int):
    """
    То же самое, но для фото/фото+текст.
    """
    user_rep = get_user_reputation(message_data['user'].id)

    keyboard = [
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{queue_index}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{queue_index}"),
        ],
        [
            InlineKeyboardButton("👤 Информация пользователя", callback_data=f"userinfo_{queue_index}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # собираем подпись для админа
    caption_text = (
        "📸 Новое фото для публикации:\n\n"
        f"👤 От: {message_data['first_name']} (@{message_data['username']})\n"
        f"⭐ Репутация: {user_rep}/10\n"
    )

    if message_data['text'] != "📸 Фото без подписи":
        caption_text += f"📝 Подпись: {message_data['text']}\n\n"
    else:
        caption_text += "📝 Подпись: Без подписи\n\n"

    caption_text += "Опубликовать в канал?"

    # тоже в pending, чтобы потом approve/reject знал что одобрять
    state.pending_approvals[queue_index] = message_data

    for admin_id in state.admins_list:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=message_data['photo_id'],
                caption=caption_text,
                reply_markup=reply_markup
            )
            logger.info(
                f"Запрос на одобрение (фото) отправлен админу {admin_id} для сообщения {queue_index}"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки фото админу {admin_id}: {e}")


async def publish_to_channel(context: ContextTypes.DEFAULT_TYPE, message_data: dict) -> bool:
    """
    Реально отправляет одобренный пост в канал.
    Если всё ок — пишем в published_messages и сохраняем.
    Возвращает True/False.
    """
    try:
        if message_data.get("has_photo"):
            # Фото-пост
            if message_data['text'] != "📸 Фото без подписи":
                caption = f"{message_data['text']}\n\n{HASHTAG}"
            else:
                caption = f"{HASHTAG}"

            result_msg = await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=message_data['photo_id'],
                caption=caption
            )
        else:
            # Текстовый пост
            full_text = f"{message_data['text']}\n\n{HASHTAG}"
            result_msg = await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=full_text
            )

        # логируем в историю
        state.published_messages.append({
            "user": message_data["user"],
            "username": message_data.get("username"),
            "first_name": message_data.get("first_name"),
            "text": message_data.get("text"),
            "photo_id": message_data.get("photo_id"),
            "timestamp": datetime.now(),
            "message_id": result_msg.message_id,
            "has_photo": message_data.get("has_photo", False),
        })

        save_bot_data()

        logger.info(f"Сообщение опубликовано в канал {CHANNEL_ID}")
        return True

    except Exception as e:
        logger.error(f"Ошибка публикации в канал: {e}")
        return False
