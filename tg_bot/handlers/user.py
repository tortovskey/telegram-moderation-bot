

import logging
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from .. import state
from ..config import ADMIN_SECRET_WORD, ADMIN_ACCESS_CODE
from ..keyboards import get_main_keyboard, get_admin_keyboard
from ..services import moderation
from ..services.reputation import (
    get_user_reputation,
    decrease_reputation,
    block_user,
    is_user_blocked,
    get_unblock_time,
    get_reputation_table,
)
from ..services.auth import (
    add_admin,
    is_admin,
)
from ..services.storage import save_bot_data
from ..services.publishing import (
    send_approval_request,
    send_photo_approval_request,
)
logger = logging.getLogger(__name__)


async def send_monkey_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мемный стикер после защиты админки."""
    monkey_sticker_id = "CAACAgIAAxkBAAIBIWgAAb1i3RAAAfgR5QABl2QAAQGQe6kAApYwAAJw6_lJAAHjWqoRAAH1LzAE"
    try:
        await update.message.reply_sticker(monkey_sticker_id)
    except Exception:
        # fallback, если стикер не отправился
        await update.message.reply_text("🖕")


async def countdown_timer(update: Update, context: ContextTypes.DEFAULT_TYPE, seconds: int = 5):
    """Драматичная обратная перемотка перед тем как мы говорим 'нет' :)"""
    for i in range(seconds, 0, -1):
        try:
            await update.message.reply_text(f"⏰ {i}...")
            await asyncio.sleep(1)
        except Exception:
            break
    await send_monkey_sticker(update, context)


async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Это роутер. Он решает: это команда из клавиатуры или обычный текст.
    """
    user_message = update.message.text

    if user_message == "🔍 Я найду тебя":
        from .start import start_command
        await start_command(update, context)

    elif user_message == "⭐ Репутация":
        await reputation_command(update, context)

    elif user_message == "📋 Очередь":
        await queue_command(update, context)

    elif user_message == "👨‍💻 Админка":
        await admin_command(update, context)

    elif user_message == "🔐 Админка":
        await request_admin_access(update, context)

    else:
        await handle_text_message(update, context)


async def request_admin_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Пользователь нажал '🔐 Админка' — предлагаем ввести секретный код.
    """
    user_id = update.message.from_user.id

    if is_admin(user_id):
        await admin_command(update, context)
        return

    await update.message.reply_text(
        "🔐 Для доступа к админке введите секретный код:\n\n"
        "У вас есть 3 попытки. После неудачных попыток доступ будет временно заблокирован.",
        reply_markup=get_main_keyboard(user_id)
    )

    context.user_data['waiting_for_admin_code'] = True


async def handle_admin_code_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает ввод кода для входа в админку.
    """
    user = update.message.from_user
    user_id = user.id
    user_message = update.message.text

    # если пользователь не в режиме ввода кода — обрабатываем как обычный текст
    if not context.user_data.get('waiting_for_admin_code'):
        await handle_text_message(update, context)
        return

    # регистрируем попытку
    if user_id not in state.admin_access_attempts:
        state.admin_access_attempts[user_id] = 0

    # код верный?
    if user_message == ADMIN_ACCESS_CODE:
        if add_admin(user_id):
            state.admin_access_attempts[user_id] = 0
            context.user_data['waiting_for_admin_code'] = False

            await update.message.reply_text(
                "🎉 Поздравляем! Вы получили права администратора!\n\n"
                "Теперь вам доступны:\n"
                "• Просмотр очереди сообщений\n"
                "• Одобрение/отклонение сообщений\n\n"
                "Используйте кнопку '👨‍💻 Админка' для доступа к панели управления.",
                reply_markup=get_main_keyboard(user_id)
            )
            logging.info(f"Пользователь {user_id} (@{user.username}) получил права админа через код")
        return

    # код неверный
    state.admin_access_attempts[user_id] += 1
    remaining_attempts = 3 - state.admin_access_attempts[user_id]

    if remaining_attempts > 0:
        await update.message.reply_text(
            f"❌ Неверный код! Осталось попыток: {remaining_attempts}",
            reply_markup=get_main_keyboard(user_id)
        )
    else:
        await update.message.reply_text("🚫 Доступ заблокирован! Запускаю систему защиты...")
        await countdown_timer(update, context, 5)

        state.admin_access_attempts[user_id] = 0
        context.user_data['waiting_for_admin_code'] = False


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Это обычное пользовательское сообщение (не кнопка).
    Проверяем:
    - не вбивает ли он админ-код
    - не в бане ли он
    - не матерится ли он
    - если всё норм → кладём в очередь и отправляем модераторам
    """
    # если он сейчас вводит админ-код — передаём в соответствующую функцию
    if context.user_data.get('waiting_for_admin_code'):
        await handle_admin_code_input(update, context)
        return

    user_message = update.message.text
    user = update.message.from_user
    username = user.username or "Без имени"
    first_name = user.first_name or "Пользователь"

    # секретное слово мгновенного входа в админку (чисто для своих)
    if user_message.strip().lower() == ADMIN_SECRET_WORD.lower():
        if add_admin(user.id):
            await update.message.reply_text(
                "🎉 Поздравляем! Вы получили права администратора!\n\n"
                "Теперь вам доступны:\n"
                "• Просмотр очереди сообщений\n"
                "• Одобрение/отклонение сообщений\n\n"
                "Используйте кнопку '👨‍💻 Админка' для доступа к панели управления.",
                reply_markup=get_main_keyboard(user.id)
            )
            logging.info(f"Пользователь {user.id} (@{username}) получил права админа (секретное слово)")
        return

    # проверка бана
    if is_user_blocked(user.id):
        unblock_time = get_unblock_time(user.id)
        moscow_time = unblock_time.strftime("%d.%m.%Y %H:%M:%S (МСК)")

        await update.message.reply_text(
            "🚫 Вы заблокированы за нарушение правил!\n\n"
            f"⏰ Разблокировка: {moscow_time}\n"
            "📋 Причина: использование нецензурной лексики\n\n"
            "После разблокировки ваша репутация будет восстановлена до 10 баллов.",
            reply_markup=get_main_keyboard(user.id)
        )
        return

    # проверка на мат
    if moderation.contains_bad_words(user_message):
        _ = decrease_reputation(user.id)
        current_rep = get_user_reputation(user.id)

        warning_text = (
            "⚠️ Использование нецензурной лексики запрещено!\n\n"
            f"📉 Ваша репутация снижена: {current_rep + 1} → {current_rep}/10\n"
            "❌ Сообщение удалено и не будет опубликовано"
        )

        if current_rep == 0:
            unblock_time = block_user(user.id)
            moscow_time = unblock_time.strftime("%d.%m.%Y %H:%M:%S (МСК)"

            )

            warning_text += (
                "\n\n🚫 ВАША РЕПУТАЦИЯ ОБНУЛЕНА!\n"
                "🔒 Вы заблокированы на 24 часа\n"
                f"⏰ Разблокировка: {moscow_time}"
            )

            # уведомляем админов про бан
            for admin_id in state.admins_list:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=(
                            "🚫 Пользователь заблокирован:\n"
                            f"👤 {first_name} (@{username})\n"
                            f"🆔 ID: {user.id}\n"
                            f"⏰ До: {moscow_time}\n"
                            f"📝 Сообщение: {user_message}"
                        ),
                    )
                except Exception as e:
                    logging.error(f"Ошибка уведомления админа {admin_id}: {e}")

        await update.message.reply_text(
            warning_text,
            reply_markup=get_main_keyboard(user.id)
        )
        return

    # сюда мы попадаем если всё норм → добавляем сообщение в очередь
    message_data = {
        "user": user,
        "username": username,
        "first_name": first_name,
        "text": user_message,
        "timestamp": update.message.date,
        "message_id": update.message.message_id,
        "has_photo": False,
    }

    state.messages_queue.append(message_data)
    queue_index = len(state.messages_queue) - 1

    save_bot_data()

    current_rep = get_user_reputation(user.id)
    await update.message.reply_text(
        "✅ Я принял ваше сообщение. В скором времени его опубликуют.\n\n"
        f"📝 Ваше сообщение: {user_message}\n"
        f"⭐ Ваша репутация: {current_rep}/10\n"
        f"📊 Ваше место в очереди: {queue_index + 1}",
        reply_markup=get_main_keyboard(user.id)
    )

    # кидаем админам на одобрение
    await send_approval_request(context, message_data, queue_index)
    logging.info(f"Сообщение от {username} добавлено в очередь. Репутация: {current_rep}/10")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Фото без подписи.
    """
    user = update.message.from_user
    username = user.username or "Без имени"
    first_name = user.first_name or "Пользователь"

    # бан-проверка
    if is_user_blocked(user.id):
        unblock_time = get_unblock_time(user.id)
        moscow_time = unblock_time.strftime("%d.%m.%Y %H:%M:%S (МСК)")

        await update.message.reply_text(
            "🚫 Вы заблокированы за нарушение правил!\n\n"
            f"⏰ Разблокировка: {moscow_time}\n"
            "📋 Причина: использование нецензурной лексики\n\n"
            "После разблокировки ваша репутация будет восстановлена до 10 баллов.",
            reply_markup=get_main_keyboard(user.id)
        )
        return

    # берём самое большое качество фото (последний элемент в массиве photo)
    photo = update.message.photo[-1]
    photo_id = photo.file_id

    message_data = {
        "user": user,
        "username": username,
        "first_name": first_name,
        "text": "📸 Фото без подписи",
        "photo_id": photo_id,
        "timestamp": update.message.date,
        "message_id": update.message.message_id,
        "has_photo": True,
    }

    state.messages_queue.append(message_data)
    queue_index = len(state.messages_queue) - 1
    save_bot_data()

    current_rep = get_user_reputation(user.id)
    await update.message.reply_text(
        "✅ Я принял ваше фото. В скором времени его опубликуют.\n\n"
        "📸 Тип: Фото без подписи\n"
        f"⭐ Ваша репутация: {current_rep}/10\n"
        f"📊 Ваше место в очереди: {queue_index + 1}",
        reply_markup=get_main_keyboard(user.id)
    )

    await send_photo_approval_request(context, message_data, queue_index)
    logging.info(f"Фото от {username} добавлено в очередь. Репутация: {current_rep}/10")


async def handle_photo_with_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Фото с подписью.
    """
    user = update.message.from_user
    username = user.username or "Без имени"
    first_name = user.first_name or "Пользователь"
    caption_text = update.message.caption or ""

    # бан-проверка
    if is_user_blocked(user.id):
        unblock_time = get_unblock_time(user.id)
        moscow_time = unblock_time.strftime("%d.%m.%Y %H:%M:%S (МСК)")

        await update.message.reply_text(
            "🚫 Вы заблокированы за нарушение правил!\n\n"
            f"⏰ Разблокировка: {moscow_time}\n"
            "📋 Причина: использование нецензурной лексики\n\n"
            "После разблокировки ваша репутация будет восстановлена до 10 баллов.",
            reply_markup=get_main_keyboard(user.id)
        )
        return

    # мат-проверка подписи
    if moderation.contains_bad_words(caption_text):
        _ = decrease_reputation(user.id)
        current_rep = get_user_reputation(user.id)

        warning_text = (
            "⚠️ Использование нецензурной лексики запрещено!\n\n"
            f"📉 Ваша репутация снижена: {current_rep + 1} → {current_rep}/10\n"
            "❌ Сообщение удалено и не будет опубликовано"
        )

        if current_rep == 0:
            unblock_time = block_user(user.id)
            moscow_time = unblock_time.strftime("%d.%m.%Y %H:%M:%S (МСК)")

            warning_text += (
                "\n\n🚫 ВАША РЕПУТАЦИЯ ОБНУЛЕНА!\n"
                "🔒 Вы заблокированы на 24 часа\n"
                f"⏰ Разблокировка: {moscow_time}"
            )

            for admin_id in state.admins_list:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=(
                            "🚫 Пользователь заблокирован:\n"
                            f"👤 {first_name} (@{username})\n"
                            f"🆔 ID: {user.id}\n"
                            f"⏰ До: {moscow_time}\n"
                            f"📝 Сообщение: {caption_text}"
                        ),
                    )
                except Exception as e:
                    logging.error(f"Ошибка уведомления админа {admin_id}: {e}")

        await update.message.reply_text(
            warning_text,
            reply_markup=get_main_keyboard(user.id)
        )
        return

    # всё ок — складываем в очередь
    photo = update.message.photo[-1]
    photo_id = photo.file_id

    message_data = {
        "user": user,
        "username": username,
        "first_name": first_name,
        "text": caption_text,
        "photo_id": photo_id,
        "timestamp": update.message.date,
        "message_id": update.message.message_id,
        "has_photo": True,
    }

    state.messages_queue.append(message_data)
    queue_index = len(state.messages_queue) - 1
    save_bot_data()

    current_rep = get_user_reputation(user.id)
    await update.message.reply_text(
        "✅ Я принял ваше фото с подписью. В скором времени его опубликуют.\n\n"
        "📸 Тип: Фото с подписью\n"
        f"📝 Подпись: {caption_text}\n"
        f"⭐ Ваша репутация: {current_rep}/10\n"
        f"📊 Ваше место в очереди: {queue_index + 1}",
        reply_markup=get_main_keyboard(user.id)
    )

    await send_photo_approval_request(context, message_data, queue_index)
    logging.info(f"Фото с подписью от {username} добавлено в очередь. Репутация: {current_rep}/10")


async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ очереди. Админ видит всех, обычный юзер — только свои посты."""
    user = update.message.from_user
    user_id = user.id

    if is_admin(user_id):
        if not state.messages_queue:
            await update.message.reply_text(
                "📭 Очередь сообщений пуста.",
                reply_markup=get_main_keyboard(user_id)
            )
            return

        queue_info = f"📋 Вся очередь сообщений ({len(state.messages_queue)}):\n\n"
        for i, msg in enumerate(state.messages_queue, 1):
            status = "⏳ Ожидает" if (i - 1) in state.pending_approvals else "✅ Обработано"
            user_rep = get_user_reputation(msg['user'].id)
            message_type = "📸" if msg.get('has_photo') else "📝"
            queue_info += (
                f"{i}. {message_type} @{msg['username']} (⭐{user_rep}): "
                f"{msg['text'][:50]}... [{status}]\n"
            )

        await update.message.reply_text(
            queue_info,
            reply_markup=get_main_keyboard(user_id)
        )
    else:
        user_messages = []
        for index, msg in enumerate(state.messages_queue):
            if msg['user'].id == user_id:
                message_type = "📸" if msg.get('has_photo') else "📝"
                user_messages.append({
                    "index": index,
                    "text": msg['text'],
                    "type": message_type,
                    "status": "⏳ Ожидает" if index in state.pending_approvals else "✅ Обработано",
                })

        if not user_messages:
            await update.message.reply_text(
                "📭 У вас нет сообщений в очереди.",
                reply_markup=get_main_keyboard(user_id)
            )
            return

        queue_info = f"📋 Ваши сообщения в очереди ({len(user_messages)}):\n\n"
        for msg in user_messages:
            position = msg["index"] + 1
            queue_info += (
                f"{position}. {msg['type']} {msg['text'][:50]}... [{msg['status']}]\n"
            )

        await update.message.reply_text(
            queue_info,
            reply_markup=get_main_keyboard(user_id)
        )


async def reputation_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ репутации пользователю. Админу — ещё и общая таблица рейтинга."""
    user = update.message.from_user
    user_id = user.id
    username = user.username or "Без имени"
    current_rep = get_user_reputation(user_id)

    if is_admin(user_id):
        reputation_table = get_reputation_table()
        await update.message.reply_text(
            f"{reputation_table}\n\n"
            "👤 Ваш профиль:\n"
            f"⭐ Репутация: {current_rep}/10\n"
            f"📝 Имя: {user.first_name or 'Не указано'}\n"
            f"🔗 Username: @{username}\n"
            "🎯 Статус: 👨‍💻 Администратор",
            reply_markup=get_main_keyboard(user_id)
        )
    else:
        if is_user_blocked(user_id):
            unblock_time = get_unblock_time(user_id)
            moscow_time = unblock_time.strftime("%d.%m.%Y %H:%M:%S (МСК)")

            await update.message.reply_text(
                "🚫 Вы заблокированы!\n\n"
                f"⭐ Текущая репутация: {current_rep}/10\n"
                f"⏰ Разблокировка: {moscow_time}\n\n"
                "После разблокировки репутация будет восстановлена.",
                reply_markup=get_main_keyboard(user_id)
            )
        else:
            await update.message.reply_text(
                "👤 Ваш профиль:\n"
                f"⭐ Репутация: {current_rep}/10\n"
                f"📝 Имя: {user.first_name or 'Не указано'}\n"
                f"🔗 Username: @{username}\n"
                "🎯 Статус: 👤 Пользователь\n\n"
                "💡 Репутация снижается за использование нецензурной лексики",
                reply_markup=get_main_keyboard(user_id)
            )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Кнопка "👨‍💻 Админка".
    Если это админ — кидаем ему меню.
    Если не админ — запускаем сценарий ввода кода.
    """
    user = update.message.from_user

    if not is_admin(user.id):
        await request_admin_access(update, context)
        return

    await update.message.reply_text(
        "👨‍💻 Панель администратора\n\n"
        "Выберите раздел:",
        reply_markup=get_admin_keyboard(user.id)
    )
