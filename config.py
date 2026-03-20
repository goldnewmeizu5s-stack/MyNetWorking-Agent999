import os
from dataclasses import dataclass, field


@dataclass
class Config:
    # Telegram
    telegram_bot_token: str = field(
        default_factory=lambda: os.environ["TELEGRAM_BOT_TOKEN"]
    )

    # OpenAI (Whisper STT)
    openai_api_key: str = field(
        default_factory=lambda: os.environ.get("OPENAI_API_KEY", "")
    )

    # CrewAI Platform
    crewai_platform_url: str = field(
        default_factory=lambda: os.environ.get(
            "CREWAI_PLATFORM_URL", ""
        )
    )
    crewai_bearer_token: str = field(
        default_factory=lambda: os.environ.get("CREWAI_BEARER_TOKEN", "")
    )

    # Database
    database_url: str = field(
        default_factory=lambda: os.environ["DATABASE_URL"]
    )
    redis_url: str = field(
        default_factory=lambda: os.environ.get(
            "REDIS_URL", "redis://localhost:6379"
        )
    )

    # Admin
    admin_telegram_id: int = field(
        default_factory=lambda: int(os.environ.get("ADMIN_TELEGRAM_ID", "1010004170"))
    )

    # Defaults
    default_city: str = field(
        default_factory=lambda: os.environ.get("DEFAULT_CITY", "Tbilisi")
    )
    default_radius_km: int = field(
        default_factory=lambda: int(
            os.environ.get("DEFAULT_RADIUS_KM", "15")
        )
    )
    event_scan_days_ahead: int = field(
        default_factory=lambda: int(
            os.environ.get("EVENT_SCAN_DAYS_AHEAD", "14")
        )
    )
    max_events_shown: int = field(
        default_factory=lambda: int(
            os.environ.get("MAX_EVENTS_SHOWN", "5")
        )
    )
    playwright_timeout_sec: int = field(
        default_factory=lambda: int(
            os.environ.get("PLAYWRIGHT_TIMEOUT_SEC", "60")
        )
    )

    # CrewAI polling
    crewai_poll_interval: int = field(
        default_factory=lambda: int(
            os.environ.get("CREWAI_POLL_INTERVAL", "5")
        )
    )
    crewai_max_retries: int = field(
        default_factory=lambda: int(
            os.environ.get("CREWAI_MAX_RETRIES", "90")
        )
    )
