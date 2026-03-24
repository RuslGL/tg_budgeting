from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message

import config


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        if event.from_user and event.from_user.id in config.ALLOWED_USERS:
            return await handler(event, data)
