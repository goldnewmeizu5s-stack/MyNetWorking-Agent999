from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from models.user import Base


class Methodology(Base):
    __tablename__ = "methodologies"

    methodology_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    full_text = Column(Text)
    category = Column(String(255))
    event_types = Column(JSONB, default=["any"])
    difficulty = Column(String(20))
    skills = Column(JSONB, default=[])
    # embedding column deferred to Phase 5 (requires pgvector extension)
