from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from services import sheets

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! Я бот для учёта бюджета.\n\n"
        "Отправь мне голосовое сообщение или текст с описанием расхода или дохода, "
        "и я занесу данные в таблицу.\n\n"
        "Например: «потратил 3000 на обед» или «получил 50000 зарплата».\n\n"
        "Команды:\n"
        "/start — это сообщение\n"
        "/help — помощь"
    )


@router.message(Command("reload"))
async def cmd_reload(message: Message) -> None:
    sheets.invalidate_cache()
    await message.answer("Кэш категорий сброшен. Новые категории уже доступны.")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Как пользоваться ботом:\n\n"
        "1. Отправь текст или голосовое сообщение с описанием операции.\n"
        "2. Укажи сумму, тип (расход или доход) и категорию.\n"
        "3. Если данных не хватает — я уточню.\n"
        "4. После подтверждения данные попадут в Google Таблицу.\n\n"
        "Примеры:\n"
        "— «потратил 1500 на такси»\n"
        "— «доход 80000 консалтинг»\n"
        "— «купил продукты 4200»"
    )
