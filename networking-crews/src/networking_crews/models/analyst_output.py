from pydantic import BaseModel


class ScoredEvent(BaseModel):
    # ID and basic data
    source_id: str
    source_url: str
    title: str
    datetime_start: str
    datetime_end: str | None
    location_name: str
    location_address: str
    location_city: str
    ticket_price: float | None
    currency: str
    language: str
    event_type: str
    organizer_name: str

    # Scoring
    deterministic_score: float     # 0-60, from bot
    semantic_relevance: float      # 0-25
    semantic_organizer: float      # 0-10
    semantic_hidden_costs: float   # 0-5
    semantic_score: float          # 0-40 (sum of above three)
    total_score: float             # 0-100

    # Transport (calculated by Analyst via tools)
    transport_mode: str
    transport_cost: float
    transport_duration_min: int
    total_estimated_cost: float
    additional_costs_note: str

    # Recommendation
    recommendation: str            # "strong_recommend" | "suitable" | "borderline" | "skip"
    recommendation_reason: str


class AnalystOutput(BaseModel):
    scored_events: list[ScoredEvent]
    top_events: list[ScoredEvent]  # top-5
