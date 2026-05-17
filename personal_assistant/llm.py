import json

from openai import AsyncOpenAI

import config
from services import proxy

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        http_client = proxy.make_openai_http_client()
        _client = AsyncOpenAI(
            api_key=config.OPENAI_API_KEY,
            **({"http_client": http_client} if http_client else {}),
        )
    return _client


ASSISTANT_PROMPT = """Ты помощник для управления личными контактами. Разбери команду пользователя и верни JSON.

Возможные действия (action):
- update_deadline      — перенести/поставить дату встречи (обновить столбец E)
- write_result         — записать итог контакта (столбец F) + опционально обновить D и E
- write_comment        — добавить заметку в комментарии (столбец C)
- set_color            — изменить цвет ячейки (статус или тип встречи)
- clear_event          — отменить встречу (очистить D и E)
- write_birthday       — записать день рождения (столбец B)
- show_week            — показать дедлайны на 7 дней
- show_no_plan         — показать контакты без запланированных событий
- show_all             — показать всех контактов
- show_columns         — показать описание колонок таблицы
- unclear              — непонятно

Поля ответа:
- action: одно из значений выше
- contact_name: имя контакта (строка, или null если не применимо)
- value: основное значение для действия (текст, дата, название плана — или null)
- next_event_date: новая дата события при write_result (строка вида "до 1 июня" или null)
- next_planned: описание следующего события при write_result (строка или null)
- color_target: "A" или "D" (только для set_color)
- color: "red" | "yellow" | "green" | "blue" | "fuchsia" (только для set_color)

Правила для write_result:
- Если в сообщении есть "следующая встреча до..." — заполни next_event_date
- Если есть описание следующего события — заполни next_planned
- value — это описание того что произошло (итог)

Правила для set_color:
- Колонка A: статус отношений (red=нет контакта, yellow=увял, green=периодический)
- Колонка D: тип встречи (blue=живая встреча, fuchsia=онлайн)
- Если сказано "встретились" без уточнения онлайн/живая — color=blue, color_target=D
- Если сказано "онлайн с ..." — color=fuchsia, color_target=D
- Если сказано "статус зелёный/периодический" — color=green, color_target=A

Примеры:
- "перенеси Женю на 5 мая" → {"action": "update_deadline", "contact_name": "Женя", "value": "до 5.05", ...}
- "выполнено Женя, следующая встреча до 1 июня" → {"action": "write_result", "contact_name": "Женя", "value": "встреча состоялась", "next_event_date": "до 1.06", "next_planned": "встреча", ...}
- "запиши в комментарии к Роману: предпочитает вечера" → {"action": "write_comment", "contact_name": "Роман", "value": "предпочитает вечера", ...}
- "встретились с Женей, живая встреча" → {"action": "set_color", "contact_name": "Женя", "color_target": "D", "color": "blue", ...}
- "онлайн с Романом" → {"action": "set_color", "contact_name": "Роман", "color_target": "D", "color": "fuchsia", ...}
- "статус Женя — периодический контакт" → {"action": "set_color", "contact_name": "Женя", "color_target": "A", "color": "green", ...}
- "запиши ДР Романа 15 марта" → {"action": "write_birthday", "contact_name": "Роман", "value": "15.03", ...}
- "отмени встречу с Женей" → {"action": "clear_event", "contact_name": "Женя", ...}
- "покажи кто на этой неделе" → {"action": "show_week", ...}
- "покажи всех без плана" → {"action": "show_no_plan", ...}
- "список контактов" → {"action": "show_all", ...}
- "что куда записывать" → {"action": "show_columns", ...}

Отвечай строго в формате JSON, без пояснений."""


async def parse_assistant_command(text: str) -> dict:
    client = _get_client()
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": ASSISTANT_PROMPT},
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(response.choices[0].message.content)
