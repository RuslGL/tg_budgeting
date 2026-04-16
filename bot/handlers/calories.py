import logging
import re
from datetime import date, datetime

import aiohttp
from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
from bot.states import CalorieForm
from services import llm, sheets, transcription

logger = logging.getLogger(__name__)

router = Router()


async def _trigger_sync() -> None:
    url = f"{config.DASHBOARD_URL}/cal/{config.CALORIES_SECRET}/api/sync"
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(url, timeout=aiohttp.ClientTimeout(total=10))
    except Exception as e:
        logger.warning("Dashboard sync trigger failed: %s", e)


def _calc_kbju(per_100g: dict, grams: float) -> dict:
    ratio = grams / 100
    return {
        "calories": round(per_100g["calories"] * ratio),
        "protein": round(per_100g["protein"] * ratio, 1),
        "fat": round(per_100g["fat"] * ratio, 1),
        "carbs": round(per_100g["carbs"] * ratio, 1),
    }


SOURCE_LABELS = {
    "cache":     "[база]",
    "fatsecret": "[FatSecret]",
    "gpt":       "[GPT]",
}


def _format_added(food_name: str, grams: float, kbju: dict, source: str, today_total: dict, cal_limit: int) -> str:
    label = SOURCE_LABELS.get(source, "")
    consumed = today_total.get("calories", 0)
    limit = cal_limit or 2000
    pct = round(consumed / limit * 100) if limit else 0
    return (
        f"Добавлено: {food_name}, {int(grams)}г {label}\n"
        f"Калории: {kbju['calories']} | Б: {kbju['protein']} | Ж: {kbju['fat']} | У: {kbju['carbs']}\n"
        f"\nСегодня: {consumed} / {limit} ккал ({pct}%)"
    )


def _recent_keyboard(meals: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for m in meals:
        label = f"{m['food_name']}, {int(m['grams'])}г — {int(m['calories'])} ккал · {m['time']}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"del_meal:{m['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _process_food_item(message: Message, food_name: str, grams: float) -> None:
    today = date.today().isoformat()
    now = datetime.now().strftime("%H:%M")

    from services import food_db as fdb
    source = "db"
    per_100g = None

    logger.info("[calories] processing: food=%s grams=%s", food_name, grams)

    # 1. Local cache
    cached = fdb.search_cache(food_name)
    if cached:
        per_100g = cached
        source = "cache"
        logger.info("[calories] found in cache: original_source=%s cal=%.1f", cached.get("source"), per_100g.get("calories", 0))
    else:
        logger.info("[calories] not in cache, trying FatSecret")
        # 2. FatSecret via translated name + GPT verification
        fs_result = None
        try:
            english_name = await llm.translate_food_name(food_name)
            logger.info("[calories] translated: '%s' -> '%s'", food_name, english_name)
            fs_candidate = fdb.search_fatsecret(english_name)
            if fs_candidate:
                logger.info("[calories] FatSecret found: cal=%.1f", fs_candidate.get("calories", 0))
                match_ok = await llm.verify_food_match(food_name, english_name)
                logger.info("[calories] GPT verification: match=%s", match_ok)
                if match_ok:
                    fdb.save_food(food_name, english_name,
                                  fs_candidate["calories"], fs_candidate["protein"],
                                  fs_candidate["fat"], fs_candidate["carbs"],
                                  source="fatsecret")
                    per_100g = fs_candidate
                    source = "fatsecret"
                    fs_result = fs_candidate
                else:
                    logger.info("[calories] FatSecret result rejected, falling back to GPT")
            else:
                logger.info("[calories] FatSecret returned no results")
        except Exception as e:
            logger.warning("[calories] FatSecret lookup failed: %s", e)

        # 3. GPT fallback
        if not fs_result:
            logger.info("[calories] using GPT to estimate KBJU for '%s'", food_name)
            try:
                per_100g = await llm.estimate_kbju_per100g(food_name)
                source = "gpt"
                logger.info("[calories] GPT result (not cached): cal=%.1f", per_100g.get("calories", 0))
            except Exception as e:
                logger.error("[calories] estimate_kbju_per100g failed: %s", e)
                await message.answer("Не удалось определить калорийность. Попробуй ещё раз.")
                return

    kbju = _calc_kbju(per_100g, grams)
    logger.info("[calories] kbju for %dg: cal=%d prot=%.1f fat=%.1f carbs=%.1f", grams, kbju["calories"], kbju["protein"], kbju["fat"], kbju["carbs"])

    try:
        sheets.append_meal(today, now, food_name, grams,
                           kbju["calories"], kbju["protein"], kbju["fat"], kbju["carbs"])
        logger.info("[calories] saved to sheets ok")
    except Exception as e:
        logger.error("[calories] append_meal failed: %s", e)
        await message.answer("Ошибка при сохранении. Попробуй ещё раз.")
        return

    limits = sheets.get_cal_limits()
    cal_limit = int(limits.get("cal_limit", 2000))
    today_total = sheets.get_today_cal_total(today)
    logger.info("[calories] today total: cal=%s limit=%s", today_total.get("calories"), cal_limit)

    await message.answer(_format_added(food_name, grams, kbju, source, today_total, cal_limit))
    await _trigger_sync()


async def _handle_text(message: Message, text: str, state: FSMContext) -> None:
    if re.search(r"(собственный|мой|свой)\s+продукт", text.lower()):
        await state.set_state(CalorieForm.entering_custom_product)
        await state.update_data(asked_at=datetime.now().isoformat())
        await message.answer(
            "Напиши название и КБЖУ с упаковки.\n"
            "Например: батончик Fit Kit, б 22 ж 4 у 32\n"
            "Калории посчитаю сам. Если данные на 100г — добавь вес: батончик 60г, б 22 ж 4 у 32"
        )
        return

    if re.search(r"удали(ть)?\s+последн", text.lower()):
        today = date.today().isoformat()
        try:
            meal = sheets.get_last_meal(today)
        except Exception as e:
            logger.error("get_last_meal failed: %s", e)
            await message.answer("Ошибка при получении последней записи.")
            return
        if not meal:
            await message.answer("Сегодня нет записей о приёмах пищи.")
            return
        try:
            sheets.delete_cal_meal(meal["id"])
        except Exception as e:
            logger.error("delete_cal_meal failed: %s", e)
            await message.answer("Ошибка при удалении.")
            return
        await message.answer(
            f"Удалено: {meal['food_name']}, {int(meal['grams'])}г — {int(meal['calories'])} ккал ({meal['time']})"
        )
        await _trigger_sync()
        return

    try:
        parsed = await llm.parse_meal(text)
    except Exception as e:
        logger.error("parse_meal failed: %s", e)
        await message.answer("Не удалось обработать сообщение. Попробуй ещё раз.")
        return

    msg_type = parsed.get("type", "unclear")

    if msg_type == "weight":
        value = parsed.get("value")
        if not value:
            await message.answer("Не удалось распознать вес. Напиши, например: вес 82.5")
            return
        try:
            sheets.log_weight(date.today().isoformat(), float(value))
        except Exception as e:
            logger.error("log_weight failed: %s", e)
            await message.answer("Ошибка при сохранении веса.")
            return
        await message.answer(f"Вес записан: {value} кг")
        await _trigger_sync()

    elif msg_type == "show_recent":
        try:
            limits = sheets.get_cal_limits()
            limit = int(limits.get("recent_meals_limit", 15))
            meals = sheets.get_recent_meals(limit)
        except Exception as e:
            logger.error("get_recent_meals failed: %s", e)
            await message.answer("Не удалось загрузить историю.")
            return
        if not meals:
            await message.answer("Нет записей о приёмах пищи.")
            return
        keyboard = _recent_keyboard(meals)
        await message.answer("Последние приёмы пищи (нажми для удаления):", reply_markup=keyboard)

    elif msg_type == "set_limits":
        await state.set_state(CalorieForm.entering_cal_limit)
        await message.answer("Какой общий лимит калорий?")

    elif msg_type == "meals":
        items = parsed.get("items", [])
        if not items:
            await message.answer("Не удалось распознать еду. Попробуй написать, например: куриная грудка 200г")
            return
        for item in items:
            food_name = item.get("food_name", "").strip()
            grams = item.get("grams")
            if not food_name:
                continue
            if grams is None:
                remaining = [i for i in items if i != item and i.get("food_name")]
                await state.set_state(CalorieForm.clarifying_grams)
                await state.update_data(
                    pending_food=food_name,
                    remaining_items=remaining,
                    asked_at=datetime.now().isoformat(),
                )
                await message.answer(f"Сколько грамм {food_name}?")
                return
            await _process_food_item(message, food_name, float(grams))

    else:
        await message.answer("Не понял. Напиши что ел (например: гречка 150г) или свой вес (вес 82.5)")


@router.message(default_state, F.text)
async def handle_text(message: Message, state: FSMContext) -> None:
    await _handle_text(message, message.text.strip(), state)


@router.message(default_state, F.voice)
async def handle_voice(message: Message, bot: Bot, state: FSMContext) -> None:
    try:
        file = await bot.get_file(message.voice.file_id)
        file_bytes = await bot.download_file(file.file_path)
        text = await transcription.transcribe(file_bytes.read())
    except Exception as e:
        logger.error("Transcription failed: %s", e)
        await message.answer("Не удалось распознать голосовое сообщение.")
        return
    await _handle_text(message, text, state)


@router.callback_query(F.data.startswith("del_meal:"))
async def handle_delete_meal(callback: CallbackQuery) -> None:
    meal_id = callback.data.split(":", 1)[1]
    try:
        sheets.delete_cal_meal(meal_id)
    except Exception as e:
        logger.error("delete_cal_meal failed: %s", e)
        await callback.answer("Ошибка при удалении.")
        return
    # Remove the button from the keyboard
    markup = callback.message.reply_markup
    new_rows = [row for row in markup.inline_keyboard if not any(btn.callback_data == callback.data for btn in row)]
    new_markup = InlineKeyboardMarkup(inline_keyboard=new_rows) if new_rows else None
    await callback.message.edit_reply_markup(reply_markup=new_markup)
    await callback.answer("Удалено.")
    await _trigger_sync()


FSM_TIMEOUT_SECONDS = 120


def _is_timed_out(data: dict) -> bool:
    asked_at = data.get("asked_at")
    if not asked_at:
        return False
    return (datetime.now() - datetime.fromisoformat(asked_at)).total_seconds() > FSM_TIMEOUT_SECONDS


async def _voice_to_text(message: Message, bot: Bot) -> str | None:
    try:
        file = await bot.get_file(message.voice.file_id)
        file_bytes = await bot.download_file(file.file_path)
        return await transcription.transcribe(file_bytes.read())
    except Exception as e:
        logger.error("Transcription failed: %s", e)
        await message.answer("Не удалось распознать голосовое сообщение.")
        return None


async def _clarify_grams(message: Message, text: str, state: FSMContext) -> None:
    data = await state.get_data()
    if _is_timed_out(data):
        await state.clear()
        await message.answer("Время вышло. Напиши заново, что ел.")
        return

    food_name = data.get("pending_food", "")
    remaining = data.get("remaining_items", [])

    nums = re.findall(r"\d+(?:[.,]\d+)?", text)
    if not nums:
        await message.answer("Не понял. Укажи количество в граммах, например: 150")
        return

    grams = float(nums[0].replace(",", "."))
    await state.clear()
    await _process_food_item(message, food_name, grams)
    for item in remaining:
        if item.get("grams"):
            await _process_food_item(message, item["food_name"], float(item["grams"]))


@router.message(CalorieForm.clarifying_grams, F.text)
async def handle_clarify_grams_text(message: Message, state: FSMContext) -> None:
    await _clarify_grams(message, message.text.strip(), state)


@router.message(CalorieForm.clarifying_grams, F.voice)
async def handle_clarify_grams_voice(message: Message, bot: Bot, state: FSMContext) -> None:
    text = await _voice_to_text(message, bot)
    if text:
        await _clarify_grams(message, text, state)


async def _parse_cal_limit(text: str) -> int | None:
    nums = re.findall(r"\d+", text)
    return int(nums[0]) if nums else None


async def _handle_cal_limit(message: Message, text: str, state: FSMContext) -> None:
    data = await state.get_data()
    if _is_timed_out(data):
        await state.clear()
        await message.answer("Время вышло. Начни заново.")
        return
    cal_limit = await _parse_cal_limit(text)
    if not cal_limit:
        await message.answer("Не понял. Укажи число калорий, например: 2100")
        return
    await state.update_data(new_cal_limit=cal_limit, asked_at=datetime.now().isoformat())
    await state.set_state(CalorieForm.entering_macros)
    await message.answer("Какие белки, жиры и углеводы?\nНапример: Б 140 Ж 78 У 220")


@router.message(CalorieForm.entering_cal_limit, F.text)
async def handle_enter_cal_limit_text(message: Message, state: FSMContext) -> None:
    await _handle_cal_limit(message, message.text.strip(), state)


@router.message(CalorieForm.entering_cal_limit, F.voice)
async def handle_enter_cal_limit_voice(message: Message, bot: Bot, state: FSMContext) -> None:
    text = await _voice_to_text(message, bot)
    if text:
        await _handle_cal_limit(message, text, state)


def _extract_macro(text: str, keys: list[str]) -> int | None:
    for key in keys:
        m = re.search(rf"{key}\D*?(\d+)", text)
        if m:
            return int(m.group(1))
    return None


def _scale_macros(protein: int, fat: int, carbs: int, cal_limit: int) -> tuple[int, int, int]:
    """Proportionally scale macros to match calorie limit."""
    computed = protein * 4 + fat * 9 + carbs * 4
    if computed == 0:
        return protein, fat, carbs
    ratio = cal_limit / computed
    p = round(protein * ratio)
    f = round(fat * ratio)
    c = round(carbs * ratio)
    # Fix rounding drift on protein
    drift = cal_limit - (p * 4 + f * 9 + c * 4)
    p += round(drift / 4)
    return p, f, c


async def _handle_macros(message: Message, text: str, state: FSMContext) -> None:
    data = await state.get_data()
    if _is_timed_out(data):
        await state.clear()
        await message.answer("Время вышло. Начни заново.")
        return

    upper = text.upper()
    protein = _extract_macro(upper, ["Б", "П", "БЕЛК"])
    fat = _extract_macro(upper, ["Ж", "ЖИР"])
    carbs = _extract_macro(upper, ["У", "УГЛ"])

    if protein is None or fat is None or carbs is None:
        nums = re.findall(r"\d+", text)
        if len(nums) >= 3:
            protein, fat, carbs = int(nums[0]), int(nums[1]), int(nums[2])
        else:
            await message.answer("Не понял. Укажи три числа, например: Б 140 Ж 78 У 220")
            return

    cal_limit = data.get("new_cal_limit", 2000)
    computed = protein * 4 + fat * 9 + carbs * 4

    note = ""
    if abs(computed - cal_limit) > 50:
        protein, fat, carbs = _scale_macros(protein, fat, carbs, cal_limit)
        note = f"\nБЖУ скорректированы пропорционально под {cal_limit} ккал."

    await state.update_data(protein=protein, fat=fat, carbs=carbs, asked_at=datetime.now().isoformat())
    await state.set_state(CalorieForm.entering_goal_weight)
    await message.answer(
        f"Б: {protein} | Ж: {fat} | У: {carbs}{note}\n\nКакая цель по весу (кг)? Или напиши «пропустить»."
    )


@router.message(CalorieForm.entering_macros, F.text)
async def handle_enter_macros_text(message: Message, state: FSMContext) -> None:
    await _handle_macros(message, message.text.strip(), state)


@router.message(CalorieForm.entering_macros, F.voice)
async def handle_enter_macros_voice(message: Message, bot: Bot, state: FSMContext) -> None:
    text = await _voice_to_text(message, bot)
    if text:
        await _handle_macros(message, text, state)


async def _handle_goal_weight(message: Message, text: str, state: FSMContext) -> None:
    data = await state.get_data()
    if _is_timed_out(data):
        await state.clear()
        await message.answer("Время вышло. Начни заново.")
        return

    goal_weight = None
    if not any(w in text.lower() for w in ["пропуст", "нет", "skip", "no"]):
        nums = re.findall(r"\d+(?:[.,]\d+)?", text)
        if nums:
            goal_weight = float(nums[0].replace(",", "."))

    await _save_limits(message, state,
                       data["new_cal_limit"], data["protein"], data["fat"], data["carbs"],
                       goal_weight)


@router.message(CalorieForm.entering_goal_weight, F.text)
async def handle_enter_goal_weight_text(message: Message, state: FSMContext) -> None:
    await _handle_goal_weight(message, message.text.strip(), state)


@router.message(CalorieForm.entering_goal_weight, F.voice)
async def handle_enter_goal_weight_voice(message: Message, bot: Bot, state: FSMContext) -> None:
    text = await _voice_to_text(message, bot)
    if text:
        await _handle_goal_weight(message, text, state)


async def _handle_custom_product(message: Message, text: str, state: FSMContext) -> None:
    data = await state.get_data()
    if _is_timed_out(data):
        await state.clear()
        await message.answer("Время вышло. Начни заново.")
        return

    upper = text.upper()

    # Extract macros
    protein = _extract_macro(upper, ["Б", "БЕЛ", "П"])
    fat     = _extract_macro(upper, ["Ж", "ЖИР"])
    carbs   = _extract_macro(upper, ["У", "УГЛ"])
    cal_match = re.search(r"(?:КАЛ|ККАЛ|CAL)\D*?(\d+)", upper)
    calories_given = int(cal_match.group(1)) if cal_match else None

    if protein is None or fat is None or carbs is None:
        await message.answer(
            "Не нашёл КБЖУ. Напиши, например:\n"
            "батончик Fit Kit, б 22 ж 4 у 32\n"
            "или с граммами (тогда пересчитаю на 100г): батончик 60г, б 22 ж 4 у 32"
        )
        return

    # Calories: compute from macros if not given
    calories_computed = round(protein * 4 + fat * 9 + carbs * 4)
    calories_base = calories_given if calories_given else calories_computed

    # Extract grams — optional
    grams_match = re.search(r"(\d+(?:[.,]\d+)?)\s*г(?:рамм)?", text.lower())
    grams = float(grams_match.group(1).replace(",", ".")) if grams_match else None

    if grams:
        # Values are per-100g, scale to portion
        per_100g = {
            "calories": calories_base / grams * 100,
            "protein":  protein  / grams * 100,
            "fat":      fat      / grams * 100,
            "carbs":    carbs    / grams * 100,
        }
        kbju = _calc_kbju(per_100g, grams)
    else:
        # Values are for the whole portion
        grams = 0
        kbju = {
            "calories": calories_base,
            "protein":  float(protein),
            "fat":      float(fat),
            "carbs":    float(carbs),
        }

    # Extract food name: text before the first digit
    name_match = re.match(r"^([^\d]+)", text.strip())
    food_name = name_match.group(1).strip().rstrip(",. ") if name_match else "продукт"

    await state.clear()

    today = date.today().isoformat()
    now = datetime.now().strftime("%H:%M")
    try:
        sheets.append_meal(today, now, food_name, grams,
                           kbju["calories"], kbju["protein"], kbju["fat"], kbju["carbs"])
    except Exception as e:
        logger.error("append_meal (custom) failed: %s", e)
        await message.answer("Ошибка при сохранении.")
        return

    limits = sheets.get_cal_limits()
    cal_limit = int(limits.get("cal_limit", 2000))
    today_total = sheets.get_today_cal_total(today)
    grams_str = f"{int(grams)}г" if grams else "порция"
    await message.answer(
        f"Добавлено: {food_name}, {grams_str} [свой]\n"
        f"Калории: {kbju['calories']} | Б: {kbju['protein']} | Ж: {kbju['fat']} | У: {kbju['carbs']}\n"
        f"\nСегодня: {today_total.get('calories', 0)} / {cal_limit} ккал "
        f"({round(today_total.get('calories', 0) / cal_limit * 100)}%)"
    )
    await _trigger_sync()


@router.message(CalorieForm.entering_custom_product, F.text)
async def handle_custom_product_text(message: Message, state: FSMContext) -> None:
    await _handle_custom_product(message, message.text.strip(), state)


@router.message(CalorieForm.entering_custom_product, F.voice)
async def handle_custom_product_voice(message: Message, bot: Bot, state: FSMContext) -> None:
    text = await _voice_to_text(message, bot)
    if text:
        await _handle_custom_product(message, text, state)


async def _save_limits(message: Message, state: FSMContext, cal_limit: int, protein: int, fat: int, carbs: int, goal_weight: float | None = None) -> None:
    await state.clear()
    try:
        sheets.set_cal_limit("cal_limit", str(cal_limit))
        sheets.set_cal_limit("protein_limit", str(protein))
        sheets.set_cal_limit("fat_limit", str(fat))
        sheets.set_cal_limit("carbs_limit", str(carbs))
        if goal_weight is not None:
            sheets.set_cal_limit("goal_weight", str(goal_weight))
    except Exception as e:
        logger.error("set_cal_limit failed: %s", e)
        await message.answer("Ошибка при сохранении.")
        return
    await _trigger_sync()
    gw_text = f" | Цель: {goal_weight} кг" if goal_weight else ""
    await message.answer(f"Лимиты обновлены: {cal_limit} ккал\nБ: {protein} | Ж: {fat} | У: {carbs}{gw_text}")
