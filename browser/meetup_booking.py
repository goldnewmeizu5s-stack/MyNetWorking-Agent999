"""Meetup booking logic - used by browser_worker.py."""


def get_meetup_form_fields(event_url: str) -> list[str]:
    """Determine which fields a Meetup event RSVP requires."""
    # Meetup RSVP is typically just a button click (auth-based)
    return []


def validate_meetup_booking_data(form_data: dict) -> tuple[bool, list[str]]:
    """Validate that all required fields are present for Meetup RSVP."""
    # Meetup RSVP doesn't require form data
    return True, []
