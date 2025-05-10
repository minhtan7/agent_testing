from sqlalchemy import Column, DateTime, Enum, ForeignKey, text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.enums import SessionStatusEnum
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.study_plan import StudyPlan
from app.models.section_progress import SectionProgress
from app.models.user import User

class LearningSession(Base):
    """A single synchronous study run between the user and the AI tutor."""

    __tablename__ = "learning_sessions"

    id: uuid.UUID = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: uuid.UUID = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    study_plan_id: uuid.UUID = Column(
        UUID(as_uuid=True), ForeignKey("study_plans.id", ondelete="SET NULL"), nullable=True
    )

    status = Column(
        Enum(SessionStatusEnum, name="session_status_enum"), nullable=False, default=SessionStatusEnum.active
    )

    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="learning_sessions", lazy="joined")
    study_plan = relationship("StudyPlan", back_populates="learning_sessions", lazy="joined")
    messages = relationship(
        "SessionMessage", back_populates="session", cascade="all, delete-orphan", lazy="noload"
    )
    section_progress = relationship(
        "SectionProgress", back_populates="session", cascade="all, delete-orphan", lazy="noload"
    )

    # Helper
    def close(self):
        """Mark session completed and stamp end‑time."""
        self.status = SessionStatusEnum.completed
        self.ended_at = datetime.now(timezone.utc)

    @classmethod
    def start_learning_session(cls, user_id: UUID, plan: StudyPlan, db: Session):
        session = LearningSession(user_id=user_id, study_plan_id=plan.id)
        db.add(session)
        db.flush()  # so session.id is available

        progresses = [
            SectionProgress(session_id=session.id, section_id=s.id)
            for s in plan.sections  # ORM relationship list
        ]
        db.add_all(progresses)
        db.commit()
        return session
