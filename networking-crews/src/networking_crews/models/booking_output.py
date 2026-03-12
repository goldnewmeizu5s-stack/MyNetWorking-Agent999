from pydantic import BaseModel


class BookingCoordinationResult(BaseModel):
    status: str                        # "ready" | "missing_fields" | "error"
    missing_fields: list[str] | None   # ["company", "role"] if missing
    booking_instruction: dict | None   # {name: "...", email: "...", ...} for Playwright
    calendar_event_id: str | None
    error_message: str | None
