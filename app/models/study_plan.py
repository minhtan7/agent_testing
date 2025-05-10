# Study plan model definition

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum, ForeignKey, text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.enums import StudyPlanStatusEnum
import uuid

class StudyPlan(Base):
    """Persisted representation of a learner‑specific study plan."""

    __tablename__ = "study_plans"

    # Primary key
    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # FK -> users.id  (author / owner of the plan)
    user_id: uuid.UUID = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # FK -> documents.id  (source material that the plan was built from)
    document_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )

    # The structured study plan – arbitrary depth; versioned for migrations.
    plan = Column(JSONB, nullable=False)

    # Optional short headline for quick display in dashboard
    title = Column(String(255), nullable=True)
    
    # Learner familiarity with the subject
    familiarity = Column(String(255), nullable=True)
    
    # Learner goal for studying this material
    goal = Column(String(255), nullable=True)

    # Version of the *plan* schema so agents can branch logic if necessary
    version = Column(Integer, nullable=False, default=1)

    # Lifecycle state
    status = Column(
        Enum(StudyPlanStatusEnum, name="study_plan_status_enum"), nullable=False, default=StudyPlanStatusEnum.draft
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # -------- relationships -------- #
    user = relationship("User", back_populates="study_plans", lazy="joined")
    document = relationship("Document", back_populates="study_plans", lazy="joined")
    sections = relationship("StudyPlanSection", back_populates="study_plan", cascade="all, delete-orphan", lazy="noload")
    learning_sessions = relationship("LearningSession", back_populates="study_plan", cascade="all, delete-orphan", lazy="noload")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<StudyPlan id={self.id} user_id={self.user_id} status={self.status}>"

# ---- Consider adding indexes via migrations ----
#  * A GIN index on plan for fast JSON path queries.
#  * A composite B‑tree index on (user_id, status) for dashboard filters.
