# API Egress через туннель: как строить backend-приложения

## Firewall

### RU VPS (62.113.105.235)

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp      # SSH
ufw allow 443/tcp     # Xray REALITY (личный VPN)
ufw --force enable
```

Открыто публично: только SSH и порт REALITY.
Всё остальное — закрыто. PostgreSQL и Redis недоступны снаружи.

### Foreign VPS (154.83.140.179)

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp                                              # SSH
ufw allow from 62.113.105.235 to any port 51820 proto udp   # AWG только с RU VPS
ufw allow in on awg0 from 10.10.10.1 to any port 1080 proto tcp  # Dante только из туннеля
ufw --force enable
```

Открыто публично: только SSH и AWG от RU VPS.
Dante SOCKS5 (1080) — **недоступен из интернета**, только через AWG туннель.

### Проверка после изменений

```bash
# Туннель живой
ping -c 2 10.10.10.2

# SOCKS5 работает через туннель
curl -x socks5://10.10.10.2:1080 https://ifconfig.me
# Должен вернуть IP foreign VPS: 154.83.140.179
```

---

## Архитектура

```
[Твой Python backend на RU VPS]
        |
        | SOCKS5 через AWG туннель
        v
[Foreign VPS 10.10.10.2:1080]
        |
        v
[OpenAI / Anthropic / YouTube API / etc.]
```

RU VPS (10.10.10.1) соединён с Foreign VPS (10.10.10.2) через AmneziaWG туннель.
На Foreign VPS поднят Dante SOCKS5 прокси на порту 1080.
Все внешние API вызовы должны идти через него.

---

## Правило

> Любой HTTP-клиент, обращающийся к внешнему API, обязан использовать прокси `socks5://10.10.10.2:1080`.
> Прямые соединения с openai.com, anthropic.com и другими иностранными сервисами с RU VPS — запрещены.

---

## Настройка окружения

В `.env` на RU VPS:

```env
EXTERNAL_EGRESS_MODE=wireguard_gateway
HTTP_PROXY=socks5://10.10.10.2:1080
HTTPS_PROXY=socks5://10.10.10.2:1080

OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Python: базовый HTTP клиент

Используй `httpx` с SOCKS5 прокси. Требует пакет `httpx[socks]`.

```python
# app/core/http_client.py
import httpx
from app.core.config import settings

def make_proxy_transport() -> httpx.AsyncHTTPTransport:
    return httpx.AsyncHTTPTransport(
        proxy=httpx.Proxy(settings.https_proxy),
    )

def make_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        connect=10.0,
        read=60.0,
        write=30.0,
        pool=10.0,
    )

# Единственный клиент на всё приложение
_client: httpx.AsyncClient | None = None

async def get_http_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            transport=make_proxy_transport(),
            timeout=make_timeout(),
        )
    return _client

async def close_http_client() -> None:
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
```

```python
# app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_api_key: str
    anthropic_api_key: str
    https_proxy: str = "socks5://10.10.10.2:1080"
    http_proxy: str = "socks5://10.10.10.2:1080"

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## Python: OpenAI через прокси

```python
# app/services/external_api/openai_client.py
import httpx
from openai import AsyncOpenAI
from app.core.config import settings

def make_openai_client() -> AsyncOpenAI:
    proxy_transport = httpx.AsyncHTTPTransport(
        proxy=httpx.Proxy(settings.https_proxy)
    )
    http_client = httpx.AsyncClient(
        transport=proxy_transport,
        timeout=httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0),
    )
    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        http_client=http_client,
    )

openai_client = make_openai_client()
```

```python
# app/services/external_api/openai_service.py
from app.services.external_api.openai_client import openai_client

async def chat_completion(messages: list[dict]) -> str:
    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
    )
    return response.choices[0].message.content
```

**Роутер никогда не вызывает OpenAI напрямую:**

```python
# app/api/routes/chat.py
from fastapi import APIRouter
from app.services.external_api.openai_service import chat_completion

router = APIRouter()

@router.post("/chat")
async def chat(payload: ChatRequest):
    return await chat_completion(payload.messages)
```

---

## Python: Anthropic через прокси

```python
# app/services/external_api/anthropic_client.py
import httpx
from anthropic import AsyncAnthropic
from app.core.config import settings

def make_anthropic_client() -> AsyncAnthropic:
    proxy_transport = httpx.AsyncHTTPTransport(
        proxy=httpx.Proxy(settings.https_proxy)
    )
    http_client = httpx.AsyncClient(
        transport=proxy_transport,
        timeout=httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0),
    )
    return AsyncAnthropic(
        api_key=settings.anthropic_api_key,
        http_client=http_client,
    )

anthropic_client = make_anthropic_client()
```

```python
# app/services/external_api/anthropic_service.py
from app.services.external_api.anthropic_client import anthropic_client

async def complete(prompt: str) -> str:
    response = await anthropic_client.messages.create(
        model="claude-opus-4-7",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
```

---

## Python: любой другой внешний API через прокси

```python
# app/services/external_api/client.py
import httpx
from app.core.config import settings

async def fetch_external(url: str, **kwargs) -> httpx.Response:
    transport = httpx.AsyncHTTPTransport(proxy=httpx.Proxy(settings.https_proxy))
    async with httpx.AsyncClient(transport=transport, timeout=30.0) as client:
        return await client.get(url, **kwargs)
```

---

## Docker Compose на RU VPS

```yaml
# docker-compose.yml
services:
  backend:
    build: .
    env_file: .env
    environment:
      - HTTP_PROXY=socks5://10.10.10.2:1080
      - HTTPS_PROXY=socks5://10.10.10.2:1080
      - NO_PROXY=localhost,127.0.0.1,postgres,redis
    depends_on:
      - postgres
      - redis
    network_mode: host  # чтобы видеть 10.10.10.2 из AWG туннеля

  postgres:
    image: postgres:16
    env_file: .env
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redisdata:/data

volumes:
  pgdata:
  redisdata:
```

> `network_mode: host` обязателен — иначе контейнер не видит AWG интерфейс 10.10.10.1 и не достучится до 10.10.10.2.

---

## Проверка что трафик идёт через туннель

На RU VPS:
```bash
# Проверить что API вызов уходит через прокси
curl -x socks5://10.10.10.2:1080 https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY" | head -c 200

# Проверить внешний IP через туннель (должен быть IP foreign VPS)
curl -x socks5://10.10.10.2:1080 https://ifconfig.me
```

Если `ifconfig.me` вернул IP иностранного VPS — всё работает правильно.

---

## Что запрещено

```python
# ПЛОХО — прямой вызов без прокси
import httpx
response = await httpx.get("https://api.openai.com/...")

# ПЛОХО — openai без http_client
from openai import AsyncOpenAI
client = AsyncOpenAI(api_key=key)  # пойдёт напрямую, заблокируется

# ПЛОХО — в роутере напрямую
@app.post("/chat")
async def chat():
    response = await httpx.post("https://api.openai.com/...")
```

---

## Зависимости

```toml
# pyproject.toml
[project]
dependencies = [
    "fastapi",
    "uvicorn[standard]",
    "httpx[socks]",      # обязательно [socks] для SOCKS5
    "openai",
    "anthropic",
    "pydantic-settings",
    "sqlalchemy[asyncio]",
    "asyncpg",
    "redis[hiredis]",
]
```
