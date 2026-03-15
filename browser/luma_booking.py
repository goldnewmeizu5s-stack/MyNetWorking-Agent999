"""Luma booking logic - used by browser_worker.py."""


def get_luma_form_fields(event_url: str) -> list[str]:
    """Determine which fields a Luma event form requires."""
    # Standard Luma fields
    return ["name", "email"]


def validate_luma_booking_data(form_data: dict) -> tuple[bool, list[str]]:
    """Validate that all required fields are present for Luma booking."""
    required = ["name", "email"]
    missing = [f for f in required if not form_data.get(f)]
    return len(missing) == 0, missing
