
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from .config import BOT_TOKEN
from . import state
from .services.storage import load_bot_data
from .services.scheduler import register_jobs
from .handlers.start import start_command
from .handlers.user import (
    handle_text_messages,
    queue_command,
    reputation_command,
    admin_command,
    handle_photo,
    handle_photo_with_caption,
)
from .handlers.admin import admin_button_handler, button_handler

def main():
    # Логирование, как у тебя было
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO,
    )
    logger = logging.getLogger(__name__)

    # Загружаем состояние с диска
    load_bot_data()

    application = Application.builder().token(BOT_TOKEN).build()

    # Фоновые задачи (автосейв, статистика и т.д.)
    register_jobs(application.job_queue)

    # Команды
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("reputation", reputation_command))
    application.add_handler(CommandHandler("queue", queue_command))
    application.add_handler(CommandHandler("admin", admin_command))


    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))


    application.add_handler(MessageHandler(filters.PHOTO & filters.CAPTION, handle_photo_with_caption))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))


    application.add_handler(CallbackQueryHandler(admin_button_handler, pattern="^(admin_|restore_)"))

    application.add_handler(CallbackQueryHandler(button_handler))

    print("🤖 Бот запущен в автономном режиме...")
    print(f"👥 Администраторы: {len(state.admins_list)}")
    print(f"📨 Сообщений в очереди: {len(state.messages_queue)}")
    print(f"⭐ Пользователей в системе: {len(state.user_reputation)}")
    print("💾 Автосохранение данных: ✅ Включено")
    print("🔄 Фоновые задачи: ✅ Активны")
    print("📸 Поддержка фотографий: ✅ Включено")
    print("📱 Бот работает автономно 24/7!")

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
