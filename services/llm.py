import json
from datetime import date

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
- category: одна строка точно из списка доступных категорий. Выбирай только если есть явное смысловое совпадение. Если подходящей категории нет — верни "unknown". Не придумывай и не угадывай.
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
