from sqlalchemy import Column, String, JSON, DateTime, ForeignKey, UUID
from datetime import datetime, timezone
from sqlalchemy.orm import relationship
from app.db.base import Base

class ToolCall(Base):
    __tablename__ = "tool_calls"
    id = Column(UUID, primary_key=True)
    session_message_id = Column(UUID, ForeignKey("session_messages.id"))
    tool_name = Column(String)
    params = Column(JSON)
    response = Column(JSON)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    session_message = relationship("SessionMessage", backref="tool_calls")
