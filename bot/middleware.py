"""Middleware for logging and dependency injection."""

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

logger = logging.getLogger(__name__)


class DependencyMiddleware(BaseMiddleware):
    """Inject dependencies (db, crewai_client, etc.) into handlers."""

    def __init__(self, dependencies: dict):
        self.dependencies = dependencies

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        data.update(self.dependencies)
        return await handler(event, data)


class LoggingMiddleware(BaseMiddleware):
    """Log all incoming updates."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        user_info = f"user={user.id}" if user else "unknown"
        event_type = type(event).__name__
        logger.info(f"[{event_type}] {user_info}")

        try:
            result = await handler(event, data)
            return result
        except Exception:
            logger.exception(f"Error handling {event_type} from {user_info}")
            raise
