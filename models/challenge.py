import uuid

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from models.user import Base


class Challenge(Base):
    __tablename__ = "challenges"

    challenge_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.event_id"))
    user_id = Column(BigInteger, ForeignKey("users.user_id"))
    methodology_id = Column(Integer, ForeignKey("methodologies.methodology_id"))
    methodology_name = Column(String(500))
    description = Column(Text, nullable=False)
    success_metrics = Column(JSONB, default=[])
    tips = Column(JSONB, default=[])
    difficulty = Column(String(20))
    status = Column(String(30), default="assigned")
    user_feedback = Column(Text)
    coach_feedback = Column(Text)
    progress_note = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        return {
            "challenge_id": str(self.challenge_id),
            "event_id": str(self.event_id) if self.event_id else None,
            "methodology_id": self.methodology_id,
            "methodology_name": self.methodology_name,
            "description": self.description,
            "success_metrics": self.success_metrics or [],
            "tips": self.tips or [],
            "difficulty": self.difficulty,
            "status": self.status,
            "user_feedback": self.user_feedback,
            "coach_feedback": self.coach_feedback,
            "progress_note": self.progress_note,
        }
