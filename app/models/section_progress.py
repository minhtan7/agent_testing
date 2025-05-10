"""SectionProgress – per-section runtime state for a learning session."""

import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.enums import SectionProgressStatusEnum  # pending / in_progress / completed / skipped


class SectionProgress(Base):
    __tablename__ = "section_progress"

    id: uuid.UUID = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )

    # --------- foreign keys --------- #
    session_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("learning_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("study_plan_sections.id", ondelete="CASCADE"),
        nullable=False,
    )

    # --------- state --------- #
    status = Column(
        Enum(SectionProgressStatusEnum, name="section_progress_status_enum"),
        nullable=False,
        default=SectionProgressStatusEnum.pending,
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # --------- timestamps --------- #
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # --------- relationships --------- #
    session = relationship("LearningSession", back_populates="section_progress", lazy="joined")
    section = relationship("StudyPlanSection", lazy="joined")

    # --------- helpers --------- #
    def __repr__(self):
        return f"<SectionProgress session={self.session_id} section={self.section_id} status={self.status}>"
