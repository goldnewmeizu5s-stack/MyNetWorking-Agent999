from pydantic import BaseModel


class FilteredEvent(BaseModel):
    # Original event data (from EventParser on bot side)
    source: str                    # "luma" | "meetup" | "other"
    source_id: str
    source_url: str
    title: str
    description: str
    datetime_start: str            # ISO format
    datetime_end: str | None
    location_name: str
    location_address: str
    location_city: str
    location_lat: float
    location_lon: float
    ticket_price: float | None     # None = free
    currency: str
    organizer_name: str
    organizer_url: str | None
    capacity: int | None
    food_included: bool

    # Enriched by Scout
    event_type: str                # "conference" | "meetup" | "workshop" | "networking_dinner" | "other"
    detected_language: str         # "en", "pt", "de" etc.
    organizer_info: str            # brief summary about organizer
    relevance_note: str            # why relevant
    estimated_audience: int | None


class ScoutOutput(BaseModel):
    filtered_events: list[FilteredEvent]
    total_parsed: int
    total_filtered: int
