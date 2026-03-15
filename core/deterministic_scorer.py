"""
Calculates 60% of the total score (0-100) without LLM.

Factors:
- Ticket price:          15 points max
- Transport cost:        15 points max
- Travel time:           10 points max
- Calendar conflict:     10 points max
- Event language:        10 points max
"""


class DeterministicScorer:
    """Calculates 60% of total score without LLM."""

    def calculate(
        self,
        event: dict,
        profile: dict,
        transport_cost: float,
        transport_duration_min: int,
        calendar_free: bool,
    ) -> float:
        score = 0.0

        # Ticket price (15 points)
        ticket = event.get("ticket_price") or 0
        budget_ticket = profile.get("budget_limit_ticket", 50)
        if ticket == 0:
            score += 15.0
        elif ticket <= budget_ticket:
            score += 15.0 * (1 - ticket / budget_ticket)

        # Transport cost (15 points)
        budget_transport = profile.get("budget_limit_transport", 20)
        if transport_cost == 0:
            score += 15.0
        elif transport_cost <= budget_transport:
            score += 15.0 * (1 - transport_cost / budget_transport)

        # Travel time (10 points, 0 if > 60 min)
        if transport_duration_min <= 60:
            score += 10.0 * (1 - transport_duration_min / 60)

        # Calendar conflict (10 points)
        if calendar_free:
            score += 10.0

        # Language (10 points)
        event_lang = (event.get("detected_language") or "").lower()
        preferred = [
            lang.lower()
            for lang in profile.get("preferred_languages", ["en"])
        ]
        if event_lang in preferred:
            score += 10.0
        elif event_lang == "en":
            score += 7.0  # English always gets a bonus

        return round(score, 1)
