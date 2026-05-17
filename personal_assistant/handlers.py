import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from personal_assistant import llm, sheets
from personal_assistant.states import AssistantForm
from services import transcription

router = Router()
logger = logging.getLogger(__name__)

COLUMNS_TEXT = (
    "Колонки таблицы контактов:\n"
    "A — Имя (цвет: красный=нет контакта, жёлтый=увял, зелёный=периодический)\n"
    "B — ДР (день рождения)\n"
    "C — Комментарий (заметки с датой)\n"
    "D — Запланировано (тип события; цвет: голубой=живая встреча, фуксия=онлайн)\n"
    "E — Дата события (дедлайн: 'до 26.04' или '26.04.2026')\n"
    "F — Итог (результат с датой)"
)


def _contacts_keyboard(contacts: list[dict], prefix: str = "contact") -> InlineKeyboardMarkup:
    rows = []
    for c in contacts:
        rows.append([InlineKeyboardButton(
            text=c["name"],
            callback_data=f"{prefix}:{c['row']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _extract_text(message: Message, bot: Bot) -> str | None:
    if message.text:
        return message.text
    if message.voice:
        try:
            file = await bot.get_file(message.voice.file_id)
            buffer = await bot.download_file(file.file_path)
            return await transcription.transcribe(buffer.read())
        except Exception as e:
            logger.error("Ошибка транскрипции: %s", e)
    return None


def _format_contacts_list(contacts: list[dict]) -> str:
    if not contacts:
        return "Контактов нет."
    lines = []
    for c in contacts:
        line = c["name"]
        if c["birthday"]:
            line += f" (ДР: {c['birthday']})"
        if c["event_date"]:
            line += f" — до {c['event_date']}"
        lines.append(line)
    return "Контакты:\n" + "\n".join(lines)


def _format_week_deadlines(contacts: list[dict]) -> str:
    from datetime import date, timedelta
    today = date.today()
    week_end = today + timedelta(days=7)
    upcoming = []
    for c in contacts:
        d = sheets.parse_deadline_date(c["event_date"])
        if d and today <= d <= week_end:
            upcoming.append((d, c["name"], c["planned"], c["event_date"]))
    if not upcoming:
        return "На ближайшие 7 дней дедлайнов нет."
    upcoming.sort(key=lambda x: x[0])
    lines = ["Дедлайны на 7 дней:"]
    for d, name, planned, event_date in upcoming:
        lines.append(f"{event_date} — {name}" + (f" ({planned})" if planned else ""))
    return "\n".join(lines)


def _format_no_plan(contacts: list[dict]) -> str:
    no_plan = [c for c in contacts if not c["event_date"] or not c["planned"]]
    if not no_plan:
        return "У всех контактов есть план."
    lines = ["Без плана:"]
    for c in no_plan:
        lines.append(f"- {c['name']}")
    return "\n".join(lines)


async def _execute_action(message: Message, state: FSMContext, cmd: dict, contact: dict) -> None:
    action = cmd.get("action")
    value = cmd.get("value") or ""
    row = contact["row"]

    if action == "update_deadline":
        sheets.update_cell(row, sheets.COL_DATE, value)
        await message.answer(f"Дата события для {contact['name']} обновлена: {value}")

    elif action == "write_result":
        sheets.append_to_cell(row, sheets.COL_RESULT, value)
        next_date = cmd.get("next_event_date") or ""
        next_planned = cmd.get("next_planned") or ""
        if next_date:
            sheets.update_cell(row, sheets.COL_DATE, next_date)
        if next_planned:
            sheets.update_cell(row, sheets.COL_PLANNED, next_planned)
        reply = f"Итог для {contact['name']} записан."
        if next_date:
            reply += f"\nСледующее событие: {next_date}"
        await message.answer(reply)

    elif action == "write_comment":
        sheets.append_to_cell(row, sheets.COL_COMMENT, value)
        await message.answer(f"Комментарий к {contact['name']} добавлен.")

    elif action == "set_color":
        color_name = cmd.get("color", "")
        color_target = cmd.get("color_target", "A")
        col = sheets.COL_NAME if color_target == "A" else sheets.COL_PLANNED
        color_map = {
            "red": sheets.COLOR_RED,
            "yellow": sheets.COLOR_YELLOW,
            "green": sheets.COLOR_GREEN,
            "blue": sheets.COLOR_BLUE,
            "fuchsia": sheets.COLOR_FUCHSIA,
        }
        color = color_map.get(color_name, sheets.COLOR_NONE)
        try:
            sheets.set_cell_color(row, col, color)
        except Exception as e:
            logger.error("Ошибка смены цвета: %s", e)
            await message.answer("Не удалось сменить цвет.")
            return
        color_labels = {
            "red": "красный", "yellow": "жёлтый", "green": "зелёный",
            "blue": "голубой", "fuchsia": "фуксия",
        }
        await message.answer(
            f"Цвет {'статуса' if color_target == 'A' else 'встречи'} "
            f"для {contact['name']} — {color_labels.get(color_name, color_name)}."
        )

    elif action == "clear_event":
        sheets.update_cell(row, sheets.COL_PLANNED, "")
        sheets.update_cell(row, sheets.COL_DATE, "")
        await message.answer(f"Событие для {contact['name']} отменено.")

    elif action == "write_birthday":
        sheets.update_cell(row, sheets.COL_BIRTHDAY, value)
        await message.answer(f"ДР для {contact['name']}: {value}")

    else:
        await message.answer("Не понял команду.")

    await state.clear()


async def _resolve_and_execute(message: Message, state: FSMContext, cmd: dict) -> None:
    contact_name = cmd.get("contact_name")
    if not contact_name:
        await message.answer("Не понял команду.")
        return

    matches = sheets.find_contact(contact_name)

    if len(matches) == 1:
        await _execute_action(message, state, cmd, matches[0])

    elif len(matches) > 1:
        await state.set_state(AssistantForm.choosing_contact)
        await state.set_data({"cmd": cmd})
        kb = _contacts_keyboard(matches, prefix="choose")
        await message.answer(
            f"Нашёл несколько контактов с именем '{contact_name}'. Кого имеешь в виду?",
            reply_markup=kb,
        )

    else:
        all_contacts = sheets.get_all_contacts()
        if all_contacts:
            kb = _contacts_keyboard(all_contacts, prefix="choose")
            await message.answer(
                f"Не нашёл контакт '{contact_name}'. Выбери из списка:",
                reply_markup=kb,
            )
            await state.set_state(AssistantForm.choosing_contact)
            await state.set_data({"cmd": cmd})
        else:
            await message.answer("Контактов нет в таблице.")


@router.message(Command("contacts"))
async def cmd_contacts(message: Message) -> None:
    try:
        contacts = sheets.get_all_contacts()
        await message.answer(_format_contacts_list(contacts))
    except Exception as e:
        logger.error("Ошибка получения контактов: %s", e)
        await message.answer("Не удалось получить список контактов.")


@router.message(Command("columns"))
async def cmd_columns(message: Message) -> None:
    await message.answer(COLUMNS_TEXT)


@router.callback_query(AssistantForm.choosing_contact, F.data.startswith("choose:"))
async def handle_contact_choice(callback: CallbackQuery, state: FSMContext) -> None:
    row = int(callback.data.removeprefix("choose:"))
    data = await state.get_data()
    cmd = data.get("cmd", {})

    try:
        contacts = sheets.get_all_contacts()
        contact = next((c for c in contacts if c["row"] == row), None)
    except Exception as e:
        logger.error("Ошибка получения контакта: %s", e)
        await callback.message.answer("Ошибка при получении контакта.")
        await callback.answer()
        await state.clear()
        return

    if not contact:
        await callback.message.answer("Контакт не найден.")
        await callback.answer()
        await state.clear()
        return

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await _execute_action(callback.message, state, cmd, contact)


@router.message(F.text | F.voice)
async def handle_message(message: Message, state: FSMContext, bot: Bot) -> None:
    text = await _extract_text(message, bot)
    if not text:
        await message.answer("Отправь текст или голосовое сообщение.")
        return

    try:
        cmd = await llm.parse_assistant_command(text)
    except Exception as e:
        logger.error("Ошибка LLM: %s", e)
        await message.answer("Не удалось обработать команду. Попробуй ещё раз.")
        return

    action = cmd.get("action")

    if action == "show_all":
        try:
            contacts = sheets.get_all_contacts()
            await message.answer(_format_contacts_list(contacts))
        except Exception as e:
            logger.error("Ошибка получения контактов: %s", e)
            await message.answer("Не удалось получить список контактов.")
        return

    if action == "show_columns":
        await message.answer(COLUMNS_TEXT)
        return

    if action == "show_week":
        try:
            contacts = sheets.get_all_contacts()
            await message.answer(_format_week_deadlines(contacts))
        except Exception as e:
            logger.error("Ошибка: %s", e)
            await message.answer("Не удалось получить дедлайны.")
        return

    if action == "show_no_plan":
        try:
            contacts = sheets.get_all_contacts()
            await message.answer(_format_no_plan(contacts))
        except Exception as e:
            logger.error("Ошибка: %s", e)
            await message.answer("Не удалось получить данные.")
        return

    if action == "unclear":
        await message.answer(
            "Не понял команду. Примеры:\n"
            "- перенеси Женю на 5 мая\n"
            "- выполнено Женя, следующая встреча до 1 июня\n"
            "- запиши в комментарии к Роману: предпочитает вечера\n"
            "- встретились с Женей, живая встреча\n"
            "- покажи кто на этой неделе"
        )
        return

    try:
        await _resolve_and_execute(message, state, cmd)
    except Exception as e:
        logger.error("Ошибка выполнения команды: %s", e)
        await message.answer("Произошла ошибка. Попробуй ещё раз.")
