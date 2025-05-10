"""StudyPlanSection – 1‑to‑many child rows of StudyPlan.

• Keeps high‑level metadata (title, order, est. minutes, completed flag).
• Stores the section body (tasks, resources, etc.) as JSONB to stay flexible.
• Lets the UI query / paginate sections without loading the full plan.
"""

import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class StudyPlanSection(Base):
    __tablename__ = "study_plan_sections"

    id: uuid.UUID = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    study_plan_id: uuid.UUID = Column(
        UUID(as_uuid=True), ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=False
    )

    # Display‑friendly fields
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    order = Column(Integer, nullable=False)
    estimated_minutes = Column(Integer, nullable=True)

    # Flexible payload (list of tasks, quizzes, etc.)
    content = Column(JSONB, nullable=False)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationship back to parent plan
    study_plan = relationship("StudyPlan", back_populates="sections", lazy="joined")

    def __repr__(self):  # pragma: no cover
        return f"<Section id={self.id} plan={self.study_plan_id} idx={self.order}>"
