import logging
from datetime import date, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import config
from personal_assistant import sheets

logger = logging.getLogger(__name__)

TIMEZONE = "Europe/Moscow"
USER_ID = config.ASSISTANT_USER_ID


async def check_deadlines(bot: Bot) -> None:
    """Send deadline reminders based on days until event."""
    try:
        contacts = sheets.get_all_contacts()
    except Exception as e:
        logger.error("Ошибка получения контактов: %s", e)
        return

    today = date.today()
    messages = []

    for c in contacts:
        if not c["event_date"]:
            continue
        deadline = sheets.parse_deadline_date(c["event_date"])
        if not deadline:
            continue

        days_left = (deadline - today).days

        if days_left < 0:
            # Overdue
            messages.append(
                f"ПРОСРОЧЕНО ({abs(days_left)} дн.) — {c['name']}"
                + (f": {c['planned']}" if c["planned"] else "")
            )
        elif days_left == 0:
            messages.append(
                f"СЕГОДНЯ — {c['name']}"
                + (f": {c['planned']}" if c["planned"] else "")
            )
        elif 1 <= days_left <= 7:
            messages.append(
                f"Через {days_left} дн. — {c['name']}"
                + (f": {c['planned']}" if c["planned"] else "")
                + f" (до {c['event_date']})"
            )

    if messages:
        text = "Напоминание о дедлайнах:\n" + "\n".join(messages)
        try:
            await bot.send_message(USER_ID, text)
        except Exception as e:
            logger.error("Ошибка отправки напоминания: %s", e)


async def check_deadlines_last_day(bot: Bot) -> None:
    """Extra reminder for contacts with deadline today."""
    try:
        contacts = sheets.get_all_contacts()
    except Exception as e:
        logger.error("Ошибка получения контактов: %s", e)
        return

    today = date.today()
    messages = []

    for c in contacts:
        if not c["event_date"]:
            continue
        deadline = sheets.parse_deadline_date(c["event_date"])
        if not deadline:
            continue
        if (deadline - today).days == 0:
            messages.append(
                f"ПОСЛЕДНИЙ ДЕНЬ — {c['name']}"
                + (f": {c['planned']}" if c["planned"] else "")
            )

    if messages:
        text = "Напоминание (последний день):\n" + "\n".join(messages)
        try:
            await bot.send_message(USER_ID, text)
        except Exception as e:
            logger.error("Ошибка отправки напоминания: %s", e)


async def friday_no_plan(bot: Bot) -> None:
    """Friday reminder: contacts with no planned event."""
    try:
        contacts = sheets.get_all_contacts()
    except Exception as e:
        logger.error("Ошибка получения контактов: %s", e)
        return

    no_plan = [c for c in contacts if not c["event_date"] or not c["planned"]]
    if not no_plan:
        return

    names = ", ".join(c["name"] for c in no_plan)
    text = f"По этим контактам ничего не запланировано: {names}"
    try:
        await bot.send_message(USER_ID, text)
    except Exception as e:
        logger.error("Ошибка отправки пятничного напоминания: %s", e)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    # Daily at 8:00 — deadline check (7→1 days + overdue)
    scheduler.add_job(
        check_deadlines,
        CronTrigger(hour=8, minute=0, timezone=TIMEZONE),
        args=[bot],
        id="deadlines_8",
    )

    # Last day extra reminders at 12:00, 18:00, 21:00
    for hour in [12, 18, 21]:
        scheduler.add_job(
            check_deadlines_last_day,
            CronTrigger(hour=hour, minute=0, timezone=TIMEZONE),
            args=[bot],
            id=f"last_day_{hour}",
        )

    # Friday at 8:00 — no-plan reminder
    scheduler.add_job(
        friday_no_plan,
        CronTrigger(day_of_week="fri", hour=8, minute=0, timezone=TIMEZONE),
        args=[bot],
        id="friday_no_plan",
    )

    return scheduler
