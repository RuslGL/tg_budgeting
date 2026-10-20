from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message

import config


class AuthMiddleware(BaseMiddleware):
    def __init__(self, allowed_users: set[int] | None = None) -> None:
        self.allowed_users = allowed_users if allowed_users is not None else config.ALLOWED_USERS

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        if event.from_user and event.from_user.id in self.allowed_users:
            return await handler(event, data)
