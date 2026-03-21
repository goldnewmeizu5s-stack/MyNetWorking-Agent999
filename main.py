"""Entrypoint: Telegram bot + scheduler."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.error_handler import ErrorForwarder
from bot.handlers import events, start
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
    logger.info("Database initialized")

    # One-time fix: geocode users stuck at (0, 0)
    try:
        fixed = await db.fix_zero_coordinates()
        if fixed:
            logger.info("Fixed zero coordinates for %d user(s)", fixed)
    except Exception as e:
        logger.warning("fix_zero_coordinates failed: %s", e)

    # Initialize Redis (fallback to None if unavailable)
    redis = None
    storage = MemoryStorage()
    try:
        redis = RedisCache(config.redis_url)
        await redis.connect()
        from aiogram.fsm.storage.redis import RedisStorage
        storage = RedisStorage.from_url(config.redis_url)
        logger.info("Redis connected")
    except Exception as e:
        logger.warning("Redis unavailable, using MemoryStorage: %s", e)

    # Initialize core services
    crewai_client = CrewAIClient(
        base_url=config.crewai_platform_url,
        bearer_token=config.crewai_bearer_token,
        poll_interval=config.crewai_poll_interval,
        max_retries=config.crewai_max_retries,
    )
    context_builder = ContextBuilder(db=db, redis=redis)
    event_parser = EventParser(redis_cache=redis)
    scorer = DeterministicScorer()
    preference_learner = PreferenceLearner(db=db)
    crew_tracker = CrewTracker(db=db)
    cache_manager = CacheManager(redis=redis)

    # Initialize bot
    bot = Bot(token=config.telegram_bot_token)
    error_forwarder = ErrorForwarder(bot=bot, admin_id=config.admin_telegram_id)

    # Initialize scheduler
    scheduler = SchedulerManager(
        db=db,
        redis=redis,
        crewai_client=crewai_client,
        context_builder=context_builder,
        event_parser=event_parser,
        scorer=scorer,
        bot=bot,
    )

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
        "error_forwarder": error_forwarder,
    }

    dp.message.middleware(LoggingMiddleware())
    dp.message.middleware(DependencyMiddleware(dependencies))
    dp.callback_query.middleware(DependencyMiddleware(dependencies))

    # Register MVP routers
    dp.include_router(start.router)
    dp.include_router(events.router)

    # Register optional routers
    try:
        from bot.handlers import booking, challenge, contacts, debug, debrief, settings, stats, voice
        dp.include_router(booking.router)
        dp.include_router(debug.router)
        dp.include_router(debrief.router)
        dp.include_router(settings.router)
        dp.include_router(stats.router)
        dp.include_router(contacts.router)
        dp.include_router(challenge.router)
        dp.include_router(voice.router)
    except Exception as e:
        logger.warning("Some optional handlers not loaded: %s", e)

    # Menu button handler - must be LAST to not intercept FSM states
    try:
        from bot.handlers import menu
        dp.include_router(menu.router)
    except Exception as e:
        logger.warning("Menu handler not loaded: %s", e)

    logger.info("Bot starting...")
    scheduler.start()
    logger.info("Scheduler started")

    @dp.errors()
    async def global_error_handler(event, exception):
        await error_forwarder.send_error(
            context=f"global ({type(event).__name__})",
            error=exception,
        )
        return True

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.stop()
        await crewai_client.close()
        if redis:
            await redis.close()
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
