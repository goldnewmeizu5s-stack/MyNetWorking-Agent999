from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class UserProfile(Base):
    __tablename__ = "users"

    user_id = Column(BigInteger, primary_key=True)  # telegram_id
    name = Column(String(255), nullable=False)
    email = Column(String(255))
    phone = Column(String(50))
    company = Column(String(255))
    role = Column(String(255))
    linkedin_url = Column(String(500))
    current_city = Column(String(255), nullable=False)
    current_lat = Column(Float, nullable=False)
    current_lon = Column(Float, nullable=False)
    planned_locations = Column(JSONB, default=[])
    interests = Column(JSONB, default=[])
    budget_limit_ticket = Column(Float, default=50.0)
    budget_limit_transport = Column(Float, default=20.0)
    preferred_languages = Column(JSONB, default=["en"])
    preferred_time = Column(String(20), default="any")
    registration_data = Column(JSONB, default={})
    onboarding_complete = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "company": self.company,
            "role": self.role,
            "linkedin_url": self.linkedin_url,
            "current_city": self.current_city,
            "current_lat": self.current_lat,
            "current_lon": self.current_lon,
            "planned_locations": self.planned_locations or [],
            "interests": self.interests or [],
            "budget_limit_ticket": self.budget_limit_ticket,
            "budget_limit_transport": self.budget_limit_transport,
            "preferred_languages": self.preferred_languages or ["en"],
            "preferred_time": self.preferred_time or "any",
            "registration_data": self.registration_data or {},
            "onboarding_complete": self.onboarding_complete,
        }
