
import logging
import os
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from .. import state
from ..config import DATA_FILE
from ..keyboards import get_admin_keyboard, get_main_keyboard
from ..services.reputation import (
    get_user_reputation,
    get_user_info,
)
from ..services.auth import is_admin, is_main_admin, remove_admin
from ..services.storage import save_bot_data
from ..services.publishing import (
    publish_to_channel,
    send_approval_request,
    send_photo_approval_request,
)

logger = logging.getLogger(__name__)
async def safe_edit_message_text(query, text: str, reply_markup=None):
    # если текст и клавиатура не меняются — просто ничего не делаем
    if getattr(query.message, "text", None) == text and (
        reply_markup is None or query.message.reply_markup == reply_markup
    ):
        return
    try:
        await query.edit_message_text(text, reply_markup=reply_markup)
    except BadRequest as e:
        # Телега ругается, если правка идентична текущему состоянию — игнорим
        if "Message is not modified" in str(e):
            return
        raise

async def safe_edit_message_caption(query, caption: str, reply_markup=None):
    if getattr(query.message, "caption", None) == caption and (
        reply_markup is None or query.message.reply_markup == reply_markup
    ):
        return
    try:
        await query.edit_message_caption(caption=caption, reply_markup=reply_markup)
    except BadRequest as e:
        if "Message is not modified" in str(e):
            return
        raise


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.edit_message_text("❌ У вас нет прав для выполнения этого действия.")
        return

    data = query.data

    # админ нажал "🚪 Выйти из админки"
    if data == "admin_exit":
        if is_main_admin(user_id):
            # Главный админ бессмертный. Мы не даём ему самострел в колено.
            await query.edit_message_text(
                "🦾 Ты главный админ. Саморазжалование невозможно."
            )
        else:
            removed = remove_admin(user_id)
            if removed:
                await query.edit_message_text(
                    "🚪 Вы вышли из админки.\n"
                    "Права администратора сняты."
                )
            else:
                await query.edit_message_text(
                    "Хмм. Похоже, вы уже не админ."
                )
        return


    # 👤 Информация об авторе
    if data.startswith("userinfo_"):
        queue_index = int(data.split("_")[1])

        if queue_index not in state.pending_approvals:
            await query.edit_message_text("❌ Сообщение уже обработано или не найдено.")
            return

        message_data = state.pending_approvals[queue_index]
        user_info_text = get_user_info(message_data['user'])

        await query.message.reply_text(user_info_text)
        return

    # Одобрение / Отклонение
    if data.startswith(("approve_", "reject_")):
        queue_index = int(data.split("_")[1])
        action = data.split("_")[0]

        if queue_index not in state.pending_approvals:
            await query.edit_message_text("❌ Сообщение уже обработано или не найдено.")
            return

        message_data = state.pending_approvals[queue_index]
        user_rep = get_user_reputation(message_data['user'].id)

        if action == "approve":
            success = await publish_to_channel(context, message_data)

            if success:
                status_text = "✅ Сообщение одобрено и опубликовано в канал!"
                # уведомляем автора
                try:
                    if message_data.get('has_photo'):
                        await context.bot.send_message(
                            chat_id=message_data['user'].id,
                            text=(
                                "🎉 Ваше фото было одобрено и опубликовано!\n"
                                f"⭐ Ваша репутация: {user_rep}/10"
                            ),
                            reply_markup=get_main_keyboard(message_data['user'].id)
                        )
                    else:
                        await context.bot.send_message(
                            chat_id=message_data['user'].id,
                            text=(
                                "🎉 Ваше сообщение было одобрено и опубликовано!\n"
                                f"⭐ Ваша репутация: {user_rep}/10"
                            ),
                            reply_markup=get_main_keyboard(message_data['user'].id)
                        )
                except Exception as e:
                    logger.error(f"Не удалось уведомить пользователя: {e}")
            else:
                status_text = "❌ Ошибка публикации в канал!"

            # Обновляем сообщение у админа
            if message_data.get('has_photo'):
                await query.edit_message_caption(
                    caption=(
                        f"{status_text}\n\n"
                        f"👤 Автор: {message_data['first_name']} (@{message_data['username']})\n"
                        f"⭐ Репутация: {user_rep}/10\n"
                        f"📝 Текст: {message_data['text']}"
                    )
                )
            else:
                await query.edit_message_text(
                    f"{status_text}\n\n"
                    f"👤 Автор: {message_data['first_name']} (@{message_data['username']})\n"
                    f"⭐ Репутация: {user_rep}/10\n"
                    f"📝 Текст: {message_data['text']}"
                )

            logger.info(f"Сообщение {queue_index} одобрено админом {user_id}")

        elif action == "reject":
            # Переносим в архив отклонённых
            state.rejected_messages.append(message_data)
            save_bot_data()

            await query.edit_message_text(
                "❌ Сообщение отклонено и перемещено в архив отклонённых.\n\n"
                f"👤 Автор: {message_data['first_name']} (@{message_data['username']})\n"
                f"⭐ Репутация: {user_rep}/10\n"
                f"📝 Текст: {message_data['text']}"
            )

            # Уведомляем автора
            try:
                if message_data.get('has_photo'):
                    await context.bot.send_message(
                        chat_id=message_data['user'].id,
                        text=(
                            "❌ Ваше фото было отклонено модератором.\n"
                            f"⭐ Ваша репутация: {user_rep}/10"
                        ),
                        reply_markup=get_main_keyboard(message_data['user'].id)
                    )
                else:
                    await context.bot.send_message(
                        chat_id=message_data['user'].id,
                        text=(
                            "❌ Ваше сообщение было отклонено модератором.\n"
                            f"⭐ Ваша репутация: {user_rep}/10"
                        ),
                        reply_markup=get_main_keyboard(message_data['user'].id)
                    )
            except Exception as e:
                logger.error(f"Не удалось уведомить пользователя: {e}")
            logger.info(f"Сообщение {queue_index} отклонено админом {user_id}")

        # В любом случае убираем из pending
        if queue_index in state.pending_approvals:
            del state.pending_approvals[queue_index]

        save_bot_data()


async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.edit_message_text("❌ У вас нет прав администратора.")
        return

    data = query.data

    if data == "admin_back":
        await safe_edit_message_text(
            query,
            "👨‍💻 Панель администратора\n\nВыберите раздел:",
            reply_markup=get_admin_keyboard(user_id)
        )
        return

    if data == "admin_queue":
        if not state.messages_queue:
            await query.edit_message_text("📭 Очередь сообщений пуста.")
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

        await query.edit_message_text(
            f"{queue_info}\n\n"
            "Используйте кнопку '🔙 Назад' для возврата в меню.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]])
        )

    elif data == "admin_reputation_table":
        from ..services.reputation import get_reputation_table
        reputation_table_text = get_reputation_table()
        await query.edit_message_text(
            f"{reputation_table_text}\n\n"
            "Используйте кнопку '🔙 Назад' для возврата в меню.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]])
        )

    elif data == "admin_status":
        photo_count = sum(1 for msg in state.messages_queue if msg.get('has_photo'))
        text_count = len(state.messages_queue) - photo_count

        status_text = (
            "🤖 Статус автономной системы:\n\n"
            f"📊 Сохранение данных: {'✅ Активно' if os.path.exists(DATA_FILE) else '❌ Не активно'}\n"
            f"💾 Размер файла данных: {os.path.getsize(DATA_FILE) if os.path.exists(DATA_FILE) else 0} байт\n"
            f"🕒 Последнее сохранение: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
            f"📨 Сообщений в очереди: {len(state.messages_queue)}\n"
            f"📸 Фотографий: {photo_count}\n"
            f"📝 Текстовых: {text_count}\n"
            f"⏳ Ожидают модерации: {len(state.pending_approvals)}\n"
            f"👥 Пользователей в системе: {len(state.user_reputation)}\n"
            f"🚫 Заблокировано: {len(state.user_blocks)}\n\n"
            "🔄 Автономные функции:\n"
            "• Автосохранение каждые 5 минут\n"
            "• Очистка старых данных\n"
            "• Проверка зависших одобрений\n"
            "• Ежедневная статистика\n"
            "• Повторная отправка неудачных постов"
        )

        await query.edit_message_text(
            status_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]])
        )

    elif data == "admin_rejected":
        if not state.rejected_messages:
            await query.edit_message_text("📦 Нет отклонённых сообщений.")
            return

        text_lines = ["📦 Отклонённые сообщения:\n"]
        for i, msg in enumerate(state.rejected_messages, 1):
            message_type = "📸" if msg.get('has_photo') else "📝"
            text_lines.append(
                f"{i}. {message_type} {msg['first_name']} (@{msg['username']}) — {msg['text'][:50]}..."
            )

        keyboard = [
            [InlineKeyboardButton(f"🔁 Одобрить #{i + 1}", callback_data=f"restore_{i}")]
            for i in range(len(state.rejected_messages))
        ]
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])

        await query.edit_message_text(
            "\n".join(text_lines),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("restore_"):
        index = int(data.split("_")[1])
        if 0 <= index < len(state.rejected_messages):
            message_data = state.rejected_messages.pop(index)
            state.messages_queue.append(message_data)

            queue_index = len(state.messages_queue) - 1
            state.pending_approvals[queue_index] = message_data

            # снова отправляем на модерацию
            if message_data.get("has_photo"):
                await send_photo_approval_request(context, message_data, queue_index)
            else:
                await send_approval_request(context, message_data, queue_index)

            save_bot_data()

            await query.edit_message_text(
                "✅ Сообщение восстановлено и снова отправлено на модерацию.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]])
            )
        else:
            await query.edit_message_text("❌ Сообщение не найдено.")
