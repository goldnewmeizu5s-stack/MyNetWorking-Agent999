from pydantic import BaseModel


class OnboardingResult(BaseModel):
    name: str
    current_city: str
    current_lat: float
    current_lon: float
    interests: list[str]
    budget_limit_ticket: float
    budget_limit_transport: float
    email: str | None = None
    linkedin_url: str | None = None
    company: str | None = None
    role: str | None = None
    preferred_languages: list[str] = ["en"]
    preferred_time: str = "any"
    planned_locations: list[dict] | None = None
