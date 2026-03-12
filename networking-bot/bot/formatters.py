"""Format event cards and other data for Telegram display."""


def format_event_card(event: dict) -> str:
    """Format a scored event as an HTML card for Telegram."""
    score = event.get("total_score", 0)
    title = event.get("title", "Untitled")
    datetime_start = event.get("datetime_start", "")
    location = event.get("location_name", "")
    location_city = event.get("location_city", "")
    ticket_price = event.get("ticket_price")
    currency = event.get("currency", "EUR")
    transport_cost = event.get("transport_cost", 0)
    transport_duration = event.get("transport_duration_min", 0)
    language = event.get("language", "")
    event_type = event.get("event_type", "")
    recommendation = event.get("recommendation", "")
    recommendation_reason = event.get("recommendation_reason", "")
    estimated_audience = event.get("estimated_audience")

    # Score emoji
    if score >= 80:
        score_label = "Strong recommend"
    elif score >= 60:
        score_label = "Suitable"
    elif score >= 40:
        score_label = "Borderline"
    else:
        score_label = "Skip"

    # Price
    if ticket_price is None or ticket_price == 0:
        price_str = "Free"
    else:
        price_str = f"{currency}{ticket_price:.2f}"

    # Transport
    transport_str = ""
    if transport_cost and transport_cost > 0:
        transport_str = f"\nTransport: EUR{transport_cost:.2f}"
    if transport_duration and transport_duration > 0:
        transport_str += f" (~{transport_duration} min)"

    # Audience
    audience_str = ""
    if estimated_audience:
        audience_str = f"\n~{estimated_audience} participants"

    card = (
        f"<b>Score: {score:.0f}/100</b>\n"
        f"<b>{title}</b>\n"
        f"{datetime_start}\n"
        f"{location}"
    )
    if location_city:
        card += f", {location_city}"
    card += (
        f"\n{price_str}"
        f"{transport_str}\n"
        f"{language.upper() if language else ''}"
        f"{audience_str}\n"
        f"<i>{score_label}</i>"
    )
    if recommendation_reason:
        card += f"\n{recommendation_reason}"

    return card


def format_weekly_report(stats: dict) -> str:
    """Format weekly stats for Telegram."""
    return (
        f"<b>Weekly Report</b>\n\n"
        f"Events: {stats.get('total_events', 0)}\n"
        f"Spent: EUR{stats.get('total_spent', 0):.2f}\n"
        f"Avg ROI: {stats.get('avg_roi', 0):.1f}\n"
        f"Contacts: {stats.get('contacts_total', 0)}\n"
        f"Best type: {stats.get('best_event_type', 'N/A')}\n"
        f"Trend: {stats.get('trend', 'N/A')}\n\n"
        f"{stats.get('recommendation_next_week', '')}"
    )
