from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)

from models.user import Base


class CrewRun(Base):
    __tablename__ = "crew_runs"

    run_id = Column(Integer, primary_key=True, autoincrement=True)
    crew_name = Column(String(50), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.user_id"))
    duration_sec = Column(Float)
    status = Column(String(20))
    output = Column(Text)
    error_message = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
