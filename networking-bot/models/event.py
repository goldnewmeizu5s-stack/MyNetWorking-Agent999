import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from models.user import Base


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("user_id", "source", "source_id"),
    )

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(BigInteger, ForeignKey("users.user_id"))
    source = Column(String(20), nullable=False)
    source_id = Column(String(255), nullable=False)
    source_url = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text)
    datetime_start = Column(DateTime, nullable=False)
    datetime_end = Column(DateTime)
    location_name = Column(String(500))
    location_address = Column(Text)
    location_city = Column(String(255))
    location_lat = Column(Float)
    location_lon = Column(Float)
    ticket_price = Column(Float)
    currency = Column(String(10), default="EUR")
    language = Column(String(10))
    event_type = Column(String(50))
    categories = Column(JSONB, default=[])
    organizer_name = Column(String(500))
    organizer_url = Column(Text)
    organizer_info = Column(Text)
    capacity = Column(Integer)
    requires_approval = Column(Boolean, default=False)
    food_included = Column(Boolean, default=False)
    dress_code = Column(String(255))
    estimated_audience = Column(Integer)
    deterministic_score = Column(Float, default=0)
    semantic_score = Column(Float, default=0)
    total_score = Column(Float, default=0)
    transport_mode = Column(String(50))
    transport_cost = Column(Float)
    transport_duration_min = Column(Integer)
    total_estimated_cost = Column(Float)
    additional_costs_note = Column(Text)
    recommendation = Column(String(50))
    recommendation_reason = Column(Text)
    status = Column(String(30), default="discovered")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        return {
            "event_id": str(self.event_id),
            "source": self.source,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "title": self.title,
            "description": self.description,
            "datetime_start": self.datetime_start.isoformat() if self.datetime_start else None,
            "datetime_end": self.datetime_end.isoformat() if self.datetime_end else None,
            "location_name": self.location_name,
            "location_address": self.location_address,
            "location_city": self.location_city,
            "location_lat": self.location_lat,
            "location_lon": self.location_lon,
            "ticket_price": self.ticket_price,
            "currency": self.currency,
            "language": self.language,
            "event_type": self.event_type,
            "organizer_name": self.organizer_name,
            "total_score": self.total_score,
            "deterministic_score": self.deterministic_score,
            "semantic_score": self.semantic_score,
            "transport_mode": self.transport_mode,
            "transport_cost": self.transport_cost,
            "transport_duration_min": self.transport_duration_min,
            "total_estimated_cost": self.total_estimated_cost,
            "recommendation": self.recommendation,
            "recommendation_reason": self.recommendation_reason,
            "status": self.status,
        }


class EventResult(Base):
    __tablename__ = "event_results"

    result_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.event_id"))
    user_id = Column(BigInteger, ForeignKey("users.user_id"))
    contacts_made = Column(JSONB, default=[])
    user_rating = Column(
        Integer,
        CheckConstraint("user_rating BETWEEN 1 AND 10"),
    )
    actual_cost = Column(Float, default=0)
    notes = Column(Text)
    roi_score = Column(Float)
    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self) -> dict:
        return {
            "result_id": str(self.result_id),
            "event_id": str(self.event_id),
            "contacts_made": self.contacts_made or [],
            "user_rating": self.user_rating,
            "actual_cost": self.actual_cost,
            "notes": self.notes,
            "roi_score": self.roi_score,
        }
