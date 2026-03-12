"""Entrypoint: Telegram bot + scheduler."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from bot.handlers import (
    booking,
    challenge,
    contacts,
    debrief,
    events,
    settings,
    start,
    stats,
    voice,
)
from bot.middleware import DependencyMiddleware, LoggingMiddleware
from config import Config
from core.cache import CacheManager
from core.context_builder import ContextBuilder
from core.crewai_client import CrewAIClient
from core.crew_tracker import CrewTracker
from core.deterministic_scorer import DeterministicScorer
from core.event_parser import EventParser
from core.preference_learner import PreferenceLearner
from db.postgres import Database
from db.redis import RedisCache
from scheduler import SchedulerManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    config = Config()

    # Initialize database
    db = Database(config.database_url)
    await db.init_db()

    # Initialize Redis
    redis = RedisCache(config.redis_url)
    await redis.connect()

    # Initialize core services
    crewai_client = CrewAIClient(
        base_url=config.crewai_platform_url,
        bearer_token=config.crewai_bearer_token,
    )
    context_builder = ContextBuilder(db=db, redis=redis)
    event_parser = EventParser(redis_cache=redis)
    scorer = DeterministicScorer()
    preference_learner = PreferenceLearner(db=db)
    crew_tracker = CrewTracker(db=db)
    cache_manager = CacheManager(redis=redis)

    # Initialize bot
    bot = Bot(token=config.telegram_bot_token)
    storage = RedisStorage.from_url(config.redis_url)
    dp = Dispatcher(storage=storage)

    # Register middleware
    dependencies = {
        "db": db,
        "redis": redis,
        "crewai_client": crewai_client,
        "context_builder": context_builder,
        "event_parser": event_parser,
        "scorer": scorer,
        "preference_learner": preference_learner,
        "crew_tracker": crew_tracker,
        "cache_manager": cache_manager,
        "bot": bot,
    }

    dp.message.middleware(LoggingMiddleware())
    dp.message.middleware(DependencyMiddleware(dependencies))
    dp.callback_query.middleware(DependencyMiddleware(dependencies))

    # Register routers
    dp.include_router(start.router)
    dp.include_router(events.router)
    dp.include_router(booking.router)
    dp.include_router(debrief.router)
    dp.include_router(settings.router)
    dp.include_router(stats.router)
    dp.include_router(contacts.router)
    dp.include_router(challenge.router)
    dp.include_router(voice.router)

    # Initialize scheduler
    scheduler_manager = SchedulerManager(
        db=db,
        redis=redis,
        crewai_client=crewai_client,
        context_builder=context_builder,
        event_parser=event_parser,
        scorer=scorer,
        bot=bot,
    )
    scheduler_manager.start()

    logger.info("Bot starting...")

    try:
        await dp.start_polling(bot)
    finally:
        scheduler_manager.stop()
        await crewai_client.close()
        await redis.close()
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
