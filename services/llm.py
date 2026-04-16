import json
from datetime import date, timedelta

from openai import AsyncOpenAI

import config

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    return _client


SYSTEM_PROMPT = """Ты помощник для учёта личных финансов. Твоя задача — извлечь данные о финансовой операции из сообщения пользователя.

Верни JSON со следующими полями:
- amount: число (сумма операции), null если не указана
- category: одна строка точно из списка доступных категорий (см. ниже). Правила выбора категории:
  1. Совпадение должно быть по смыслу всей фразы, а не по отдельному слову. Например, "аренда библиотеки" и "аренда жилья" — разные вещи, даже если оба содержат слово "аренда".
  2. Если ты не уверен на 100% — верни "unknown". Лучше уточнить у пользователя, чем записать в неправильную категорию.
  3. Никогда не выбирай категорию только потому, что в ней есть похожее слово — контекст важнее.
- date: дата в формате YYYY-MM-DD. Если в сообщении есть явная дата — используй её. Если есть слово "вчера" — сегодня минус 1 день. Если "позавчера" — сегодня минус 2 дня. Если дата не указана — используй сегодняшнюю.
- missing: список полей, которые не удалось определить (например ["amount"])

Сегодняшняя дата: {today}
Доступные категории: {categories}

Важно: category должна быть точно из списка выше или "unknown". Никаких других значений.
Отвечай строго в формате JSON, без пояснений."""


async def parse_transaction(text: str, categories: list[str]) -> dict:
    client = _get_client()
    today = date.today().isoformat()
    prompt = SYSTEM_PROMPT.format(today=today, categories=", ".join(categories))

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    return json.loads(response.choices[0].message.content)


MEAL_PROMPT = """Ты помощник для учёта питания. Определи смысл сообщения пользователя.

Верни JSON с одним из вариантов:
1. Запись приёма пищи:
   {"type": "meals", "items": [{"food_name": "название продукта", "grams": число или null}, ...]}
   - food_name: короткое стандартное название (например "куриная грудка", "гречка отварная")
   - grams: число если указано, null если не указано
   - Можно несколько позиций в одном сообщении

2. Запись личного веса:
   {"type": "weight", "value": число}
   - Только если пользователь сообщает свой вес тела (не вес еды)
   - Примеры: "вес 82.5", "сегодня 81 кг", "взвесился — 83"

3. Изменение лимитов КБЖУ:
   {"type": "set_limits"}
   - Если пользователь хочет изменить лимит калорий или КБЖУ

4. Показать последние приёмы пищи:
   {"type": "show_recent"}
   - Если пользователь хочет посмотреть что ел, показать историю, удалить запись
   - Примеры: "что я сегодня ел", "последние", "покажи", "история", "удалить"

5. Непонятно:
   {"type": "unclear"}

Отвечай строго в формате JSON, без пояснений."""


async def parse_meal(text: str) -> dict:
    client = _get_client()
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": MEAL_PROMPT},
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(response.choices[0].message.content)


FOOD_TRANSLATION_PROMPT = """Translate a Russian food name to English for searching in the FatSecret nutrition database.
Preserve all details — cooking method, skin/bone presence, fat content. These affect nutrition values.

Cooking method mapping:
отварной / отварная / варёный / варёная / вареный = boiled
на пару / паровой / паровая = steamed
жареный / жареная / жареное = fried
запечённый / запечённая / запечённое / в духовке = baked
тушёный / тушёная / тушёное = stewed
копчёный / копчёная = smoked
сырой / сырая / свежий = raw
гриль / на гриле = grilled

Skin/fat mapping:
без кожи / без шкуры = skinless
с кожей / со шкурой = skin on
обезжиренный / нежирный = low fat / skim
жирный = full fat
цельный / 3.2% / 2.5% etc = add the percentage as-is

Examples:
куриная грудка отварная → chicken breast boiled skinless
куриная грудка жареная → chicken breast fried
куриная грудка на пару → chicken breast steamed skinless
куриная грудка с кожей запечённая → chicken breast baked skin on
говядина отварная → beef boiled
говядина жареная → beef fried
лосось на гриле → salmon grilled
гречка отварная → buckwheat groats cooked
рис отварной → white rice cooked
рис бурый отварной → brown rice cooked
молоко 3.2% → milk 3.2% fat
кефир 1% → kefir 1% fat
творог обезжиренный → cottage cheese skim
яйцо варёное → egg boiled
яичница → fried eggs
картофель варёный → potato boiled
картофель жареный → potato fried

Return only the English name, nothing else."""


async def translate_food_name(food_name: str) -> str:
    """Translate Russian food name to English for FatSecret search."""
    client = _get_client()
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": FOOD_TRANSLATION_PROMPT},
            {"role": "user", "content": food_name},
        ],
        temperature=0,
        max_tokens=30,
    )
    return response.choices[0].message.content.strip().strip("'\"")


async def verify_food_match(russian_name: str, english_result: str) -> bool:
    """Check if FatSecret result is a reasonable match for the original Russian food name."""
    client = _get_client()
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": (
            f"User asked for: '{russian_name}'\n"
            f"Food database search term: '{english_result}'\n"
            f"Are these the same food ingredient (ignore cooking method differences)? "
            f"For example: 'куриная грудка отварная' and 'chicken breast' are the same. "
            f"Answer only 'yes' or 'no'."
        )}],
        temperature=0,
        max_tokens=5,
    )
    answer = response.choices[0].message.content.strip().lower()
    return answer.startswith("yes")


async def estimate_kbju_per100g(food_name: str) -> dict:
    """Estimate calories/protein/fat/carbs per 100g for a given food."""
    client = _get_client()
    prompt = (
        f"Дай данные КБЖУ на 100г для '{food_name}'. "
        'Верни JSON: {"calories": float, "protein": float, "fat": float, "carbs": float}. '
        "Значения на 100г. Без пояснений."
    )
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(response.choices[0].message.content)


NOTE_PROMPT = """Ты помощник для записной книжки. Определи категорию заметки, дату события и очищенный текст из сообщения пользователя.

Верни JSON с тремя полями:
- category: одна строка точно из списка доступных категорий (см. ниже). Назначай категорию ТОЛЬКО если она явно упомянута в тексте сообщения (например, пользователь написал слово из списка категорий). Если категория не упомянута явно — верни "unknown".
- event_date: дата события в формате YYYY-MM-DD. Используй точные даты ниже:
  - "сегодня" = {today}
  - "завтра" = {tomorrow}
  - "послезавтра" = {day_after_tomorrow}
  - "в понедельник" = {next_monday}
  - "во вторник" = {next_tuesday}
  - "в среду" = {next_wednesday}
  - "в четверг" = {next_thursday}
  - "в пятницу" = {next_friday}
  - "в субботу" = {next_saturday}
  - "в воскресенье" = {next_sunday}
  - явная дата ("15 апреля", "2026-04-15") = та дата
  - если дата не упомянута — верни null
- note_text: текст заметки, очищенный от слова-триггера категории. Если пользователь написал "календарь подготовить документы" — верни "подготовить документы". Если слово категории органично входит в смысл фразы — оставь его.

Сегодня: {today} ({weekday})
Доступные категории: {categories}

Важно: category должна быть точно из списка выше или "unknown". Никаких других значений.
Отвечай строго в формате JSON, без пояснений."""


WEEKDAYS_RU = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]


async def parse_note(text: str, categories: list[str]) -> dict:
    client = _get_client()
    today_dt = date.today()
    today = today_dt.isoformat()

    def _next_weekday(target_wd: int) -> str:
        days_ahead = (target_wd - today_dt.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return (today_dt + timedelta(days=days_ahead)).isoformat()

    prompt = NOTE_PROMPT.format(
        today=today,
        tomorrow=(today_dt + timedelta(days=1)).isoformat(),
        day_after_tomorrow=(today_dt + timedelta(days=2)).isoformat(),
        next_monday=_next_weekday(0),
        next_tuesday=_next_weekday(1),
        next_wednesday=_next_weekday(2),
        next_thursday=_next_weekday(3),
        next_friday=_next_weekday(4),
        next_saturday=_next_weekday(5),
        next_sunday=_next_weekday(6),
        weekday=WEEKDAYS_RU[today_dt.weekday()],
        categories=", ".join(categories),
    )

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    return json.loads(response.choices[0].message.content)
