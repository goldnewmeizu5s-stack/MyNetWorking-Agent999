from pydantic import BaseModel


class ROIReport(BaseModel):
    event_id: str
    actual_cost: float
    contacts_count: int
    contacts_quality_avg: float
    user_rating: int
    roi_score: float
    comparison_to_forecast: str    # e.g. "Forecast: EUR5.50, actual: EUR3.00 (saving 45%)"


class AggregatedStats(BaseModel):
    period: str
    total_events: int
    total_spent: float
    avg_roi: float
    best_event_type: str
    best_event_title: str | None
    contacts_total: int
    challenges_completed: int
    challenges_assigned: int
    trend: str                     # "improving" | "stable" | "declining"
    trend_detail: str
    recommendation_next_week: str
