"""
Фоновые задачи JobQueue:
- автосохранение каждые 5 минут
- чистка старых данных
- снятие истёкших блокировок
- пинг зависших модераций
- ежедневная статистика админам
- повторная отправка запросов на одобрение
"""

import logging
import time
from datetime import datetime
from telegram.ext import ContextTypes, JobQueue

# ВАЖНО: все импорты пакетные/относительные:
from .. import state
from .storage import save_bot_data
from .reputation import   get_user_reputation
from .publishing import send_approval_request, send_photo_approval_request

logger = logging.getLogger(__name__)


async def auto_save_job(context: ContextTypes.DEFAULT_TYPE):
    """Периодически сохраняем состояние (очередь, репутации и т.д.) в JSON."""
    save_bot_data()
    logger.debug("Автосохранение выполнено")


async def cleanup_old_data(context: ContextTypes.DEFAULT_TYPE):
    """
    Чистим мусор:
    - убираем из очереди сообщения старше 7 дней
    - снимаем истёкшие блокировки юзеров
    """
    try:
        current_time = datetime.now()

        # срезаем очередь по возрасту
        state.messages_queue[:] = [
            msg for msg in state.messages_queue
            if (current_time - msg["timestamp"]).days < 7
        ]

        # снимаем просроченные баны
        current_ts = time.time()
        for uid, unblock_time in list(state.user_blocks.items()):
            if current_ts >= unblock_time:
                del state.user_blocks[uid]

        logger.info("Очистка старых данных выполнена")
    except Exception as e:
        logger.error(f"Ошибка очистки данных: {e}")


async def check_pending_approvals(context: ContextTypes.DEFAULT_TYPE):
    """
    Если запрос на модерацию висит больше суток -> выкидываем его из pending_approvals.
    (Типа заявка протухла: админы не отреагировали, значит пост неактуален.)
    """
    try:
        now = datetime.now()
        expired_indices: list[int] = []

        for queue_index, message_data in state.pending_approvals.items():
            if queue_index < len(state.messages_queue):
                message_time = state.messages_queue[queue_index]["timestamp"]
                age_seconds = (now - message_time).total_seconds()
                if age_seconds >= 24 * 3600:
                    expired_indices.append(queue_index)

        for idx in expired_indices:
            if idx in state.pending_approvals:
                del state.pending_approvals[idx]
                logger.info(f"Удалено просроченное одобрение #{idx}")
    except Exception as e:
        logger.error(f"Ошибка проверки одобрений: {e}")


async def send_daily_stats(context: ContextTypes.DEFAULT_TYPE):
    """
    Ежедневная сводка для админов. Сколько очереди, сколько фоток, сколько банов и т.д.
    Это даёт админам понимание, жив бот или умер.
    """
    try:
        photo_count = sum(1 for msg in state.messages_queue if msg.get("has_photo"))
        text_count = len(state.messages_queue) - photo_count

        stats_text = (
            f"📊 Ежедневная статистика бота:\n\n"
            f"📅 Дата: {datetime.now().strftime('%d.%m.%Y')}\n"
            f"👥 Уникальных пользователей в очереди: "
            f"{len(set(msg['user'].id for msg in state.messages_queue))}\n"
            f"📨 Сообщений в очереди: {len(state.messages_queue)}\n"
            f"📸 Фотографий: {photo_count}\n"
            f"📝 Текстовых: {text_count}\n"
            f"⏳ В ожидании модерации: {len(state.pending_approvals)}\n"
            f"✅ Всего опубликовано: {len(state.published_messages)}\n"
            f"🚫 В блоке сейчас: {len(state.user_blocks)}\n"
            f"👨‍💻 Администраторов: {len(state.admins_list)}"
        )

        for admin_id in state.admins_list:
            try:
                await context.bot.send_message(chat_id=admin_id, text=stats_text)
            except Exception as e:
                logger.error(f"Не удалось отправить статистику админу {admin_id}: {e}")

    except Exception as e:
        logger.error(f"Ошибка отправки статистики: {e}")


async def auto_retry_failed_posts(context: ContextTypes.DEFAULT_TYPE):
    """
    Если пост завис в pending_approvals больше 30 минут —
    значит админ ничего не нажал, бот пинает админов ещё раз.
    """
    try:
        now = datetime.now()

        for queue_index, message_data in list(state.pending_approvals.items()):
            if queue_index >= len(state.messages_queue):
                # такого сообщения уже нет в очереди, странный кейс -> пропускаем
                continue

            message_time = state.messages_queue[queue_index]["timestamp"]
            age_seconds = (now - message_time).total_seconds()

            if age_seconds >= 30 * 60:  # 30 минут
                if message_data.get("has_photo"):
                    await send_photo_approval_request(context, message_data, queue_index)
                else:
                    await send_approval_request(context, message_data, queue_index)

                logger.info(
                    f"Повторная отправка запроса модерации для сообщения #{queue_index}"
                )

    except Exception as e:
        logger.error(f"Ошибка повторной отправки: {e}")


def register_jobs(job_queue: JobQueue | None):
    """
    Подписываем все фоновые задачи на JobQueue.
    Это вызывается из app.py после создания Application.
    """
    if not job_queue:
        return

    # каждые 5 минут — сохранить состояние
    job_queue.run_repeating(auto_save_job, interval=300, first=10)

    # раз в час — чистка мусора/банов
    job_queue.run_repeating(cleanup_old_data, interval=3600, first=60)

    # раз в 30 минут — выкинуть протухшие approvals
    job_queue.run_repeating(check_pending_approvals, interval=1800, first=120)

    # каждые 15 минут — повторное напоминание админам о висящих постах
    job_queue.run_repeating(auto_retry_failed_posts, interval=900, first=180)

    # каждый день в 10:00 (серверное локальное время процесса) — статс-дайджест
    # Важно: run_daily ждёт объект time() (без даты).
    from datetime import time as _time
    job_queue.run_daily(send_daily_stats, time=_time(hour=10, minute=0, second=0))
