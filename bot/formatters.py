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
    recommendation = event.get("recommendation", "")
    recommendation_reason = event.get("recommendation_reason", "")
    estimated_audience = event.get("estimated_audience")
    source_url = event.get("source_url", "")

    # Score label
    if score >= 80:
        score_label = "⭐️ Strong recommend"
    elif score >= 60:
        score_label = "👍 Suitable"
    elif score >= 40:
        score_label = "🤔 Borderline"
    else:
        score_label = "👎 Skip"

    # Price
    if ticket_price is None or ticket_price == 0:
        price_str = "🎟 Free"
    else:
        price_str = f"🎟 {currency}{ticket_price:.0f}"

    card = f"<b>Score: {score:.0f}/100</b> — <i>{score_label}</i>\n"
    card += f"<b>{title}</b>\n"

    if datetime_start and str(datetime_start) not in ("None", ""):
        card += f"📅 {datetime_start}\n"

    location_parts = []
    if location and str(location) not in ("None", ""):
        location_parts.append(location)
    if location_city and str(location_city) not in ("None", ""):
        location_parts.append(location_city)
    if location_parts:
        card += f"📍 {', '.join(location_parts)}\n"

    card += f"{price_str}"
    if transport_cost and float(transport_cost) > 0:
        card += f" + 🚌 €{float(transport_cost):.2f} transport"
        if transport_duration and int(transport_duration) > 0:
            card += f" (~{transport_duration} min)"
    card += "\n"

    if language and str(language) not in ("None", ""):
        card += f"🗣 {language.upper()}\n"

    if estimated_audience and str(estimated_audience) not in ("None", ""):
        card += f"👥 ~{estimated_audience} participants\n"

    if recommendation_reason and str(recommendation_reason) not in ("None", ""):
        card += f"\n{recommendation_reason}"

    if source_url and str(source_url) not in ("None", ""):
        card += f"\n🔗 <a href='{source_url}'>Event page</a>"

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
