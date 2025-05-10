from sqlalchemy import Column, Text, DateTime, Enum, ForeignKey, String, Integer, text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.enums import MessageRoleEnum
import uuid

class SessionMessage(Base):
    """Single turn in the learning session conversation."""

    __tablename__ = "session_messages"

    id: uuid.UUID = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    session_id: uuid.UUID = Column(
        UUID(as_uuid=True), ForeignKey("learning_sessions.id", ondelete="CASCADE"), nullable=False
    )

    role = Column(
        Enum(MessageRoleEnum, name="message_role_enum"), nullable=False  # user / assistant / tool
    )
    content = Column(Text, nullable=True)  # empty for tool calls w/o payload

    # If the assistant invoked a tool, store its name; keep args in "content" or JSON field
    tool_called = Column(String(128), nullable=True)

    # Telemetry – helps measure latency & cost
    latency_ms = Column(Integer, nullable=True)
    tokens_input = Column(Integer, nullable=True)
    tokens_output = Column(Integer, nullable=True)
    cost_usd_millis = Column(Integer, nullable=True)  # store milli‑dollars to avoid float

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    session = relationship("LearningSession", back_populates="messages", lazy="joined")

    def __repr__(self):  # pragma: no cover
        return f"<Msg id={self.id} sess={self.session_id} role={self.role}>"
