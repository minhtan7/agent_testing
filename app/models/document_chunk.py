"""DocumentChunk – atomic slice of a PDF/EPUB with positional metadata and optional
vector embedding.

Why keep it in SQL *and* in the vector store?
------------------------------------------------
* SQL row = **source‑of‑truth** linking the chunk → document → user; enables
  cascading deletes, versioning, migrations and rich analytics.
* Vector DB row = fast semantic search.  We store only the embedding + the
  `chunk_id` key there.  If you use pgvector, both live in Postgres and you’re
  done.

Coordinates are **normalised (0‑1)** against the page media box, so the
front‑end can highlight the exact rectangle regardless of screen DPI.
"""

import enum
import uuid
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector  # pip install pgvector

from app.db.base import Base
from app.models.enums import ContentTypeEnum


EMBEDDING_DIM = 1536  # adjust to match your model


class DocumentChunk(Base):
    """Smallest retrievable unit for RAG and UI highlighting."""

    __tablename__ = "document_chunks"

    # -------- identifiers -------- #
    id: uuid.UUID = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    document_id: uuid.UUID = Column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )

    # -------- content positioning -------- #
    chunk_index = Column(Integer, nullable=False)            # 0‑based across entire doc
    page_number = Column(Integer, nullable=True)             # PDF page (1‑based)
    char_start = Column(Integer, nullable=True)               # offset in original page text
    char_end = Column(Integer, nullable=True)

    # Normalised bounding‑box (0‑1 in PDF coordinate space)
    bbox_x0 = Column(Float, nullable=True)
    bbox_y0 = Column(Float, nullable=True)
    bbox_x1 = Column(Float, nullable=True)
    bbox_y1 = Column(Float, nullable=True)

    # -------- content -------- #
    content_type = Column(
        Enum(ContentTypeEnum, name="content_type_enum"), nullable=False, default=ContentTypeEnum.text
    )
    text_content = Column(Text, nullable=True)
    blob_url = Column(String(1024), nullable=True)  # for figures/tables stored off‑site
    token_count = Column(Integer, nullable=True)

    # -------- vector embedding -------- #
    embedding = Column(Vector(EMBEDDING_DIM), nullable=True, index=True)

    # -------- timestamps -------- #
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # -------- relationships -------- #
    document = relationship("Document", back_populates="chunks", lazy="joined")

    # -------- helpers -------- #
    def coords(self) -> Optional[tuple[float, float, float, float]]:
        """Return (x0, y0, x1, y1) if we have a bounding box."""
        if None in (self.bbox_x0, self.bbox_y0, self.bbox_x1, self.bbox_y1):
            return None
        return (self.bbox_x0, self.bbox_y0, self.bbox_x1, self.bbox_y1)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Chunk id={self.id} doc={self.document_id} page={self.page_number} index={self.chunk_index}>"
        )
