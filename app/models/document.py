import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.enums import StorageProvider, UploadStatusEnum  # reuse existing enum

class Document(Base):
    __tablename__ = "documents"

    # -------- identifiers -------- #
    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: uuid.UUID = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # -------- storage pointers -------- #
    storage_provider = Column(
        Enum(StorageProvider, name="storage_provider_enum"), nullable=False, default=StorageProvider.cloudinary
    )
    storage_url = Column(String(1024), nullable=False)  # e.g. https://res.cloudinary.com/.../file.pdf
    storage_public_id = Column(String(255), nullable=False)  # cloudinary public_id for cleanup / transforms

    # -------- metadata -------- #
    original_filename = Column(String(255), nullable=False)
    mime_type = Column(String(128), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    pages = Column(Integer, nullable=True)
    title = Column(String(255), nullable=True)
    
    # -------- vector search -------- #
    pinecone_namespace = Column(String(255), nullable=True)  # Store the Pinecone namespace for this document

    status = Column(
        Enum(UploadStatusEnum, name="upload_status_enum"), nullable=False, default=UploadStatusEnum.pending
    )

    # -------- timestamps -------- #
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # -------- relationships -------- #
    user = relationship("User", back_populates="documents", lazy="joined")
    study_plans = relationship("StudyPlan", back_populates="document", lazy="noload")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan", lazy="noload")

    # -------- helpers -------- #
    def __repr__(self) -> str:  # pragma: no cover
        return f"<Document id={self.id} provider={self.storage_provider.value} user_id={self.user_id}>"