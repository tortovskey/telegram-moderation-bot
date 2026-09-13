

from telegram import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from .services.auth import is_admin, is_main_admin


def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """
    Клавиатура, которую видит пользователь.
    Если он админ — у него кнопка 👨‍💻 Админка,
    если нет — 🔐 Админка (с запросом кода).
    """
    keyboard = [
        [KeyboardButton("🔍 Я найду тебя")],
        [KeyboardButton("⭐ Репутация"), KeyboardButton("📋 Очередь")],
    ]

    if is_admin(user_id):
        keyboard.append([KeyboardButton("👨‍💻 Админка")])
    else:
        keyboard.append([KeyboardButton("🔐 Админка")])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_admin_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    Инлайн-клавиатура панели администратора.
    """
    keyboard = [
        [InlineKeyboardButton("📋 Вся очередь", callback_data="admin_queue")],
        [InlineKeyboardButton("👥 Таблица репутации", callback_data="admin_reputation_table")],
        [InlineKeyboardButton("🤖 Статус системы", callback_data="admin_status")],
        [InlineKeyboardButton("📦 Отклонённые сообщения", callback_data="admin_rejected")],
    ]

    # Главного админа нельзя выгнать из админки кнопкой "выйти"
    if not is_main_admin(user_id):
        keyboard.append([InlineKeyboardButton("🚪 Выйти из админки", callback_data="admin_exit")])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])

    return InlineKeyboardMarkup(keyboard)
