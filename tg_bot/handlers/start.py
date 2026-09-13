

import logging
from telegram import Update
from telegram.ext import ContextTypes

from ..services.reputation  import get_user_reputation
from ..services.auth import is_admin
from ..keyboards import get_main_keyboard

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    current_rep = get_user_reputation(user.id)
    admin_status = " (Администратор)" if is_admin(user.id) else ""

    welcome_text = (
        f"🔍 Я найду тебя! — бот для публикации сообщений{admin_status}\n\n"
        f"⭐ Ваша репутация: {current_rep}/10\n\n"
        f"🤖 АВТОНОМНЫЙ РЕЖИМ: бот работает 24/7\n\n"
        f"Как это работает:\n"
        f"1. Вы отправляете текст или фото\n"
        f"2. Бот проверяет на мат и правила\n"
        f"3. Сообщение уходит модератору\n"
        f"4. После одобрения оно публикуется в канал\n\n"
        f"📋 Правила:\n"
        f"- Не использовать нецензурную лексику\n"
        f"- За каждое нарушение репутация снижается на 1\n"
        f"- При репутации 0 — блокировка на 24 часа\n\n"
        f"📸 Можно отправлять:\n"
        f"- Текстовые сообщения\n"
        f"- Фотографии\n"
        f"- Фотографии с подписью\n\n"
        f"Используйте кнопки ниже 👇"
    )

    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_keyboard(user.id)
    )
