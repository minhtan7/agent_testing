"""User domain model plus refresh‑token storage.

⚠️  Do **not** store raw OAuth access / refresh tokens.  Encrypt them or, even
better, keep only a *hash* so leaked DB dumps are useless.  Here we persist a
SHA‑256 digest so logout/invalidate simply means deleting the DB row and, if
needed, revoking the token at the IdP.
"""

import uuid
from datetime import timedelta

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(Base):
    """Application user. Supports Google OAuth **and** optional local password."""

    __tablename__ = "users"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # --- auth & identity --- #
    email = Column(String(320), unique=True, nullable=False)
    google_sub = Column(String(255), unique=True, nullable=True)  # "sub" claim from Google ID token
    password_hash = Column(String(255), nullable=True)  # null when using OAuth‑only
    is_active = Column(Boolean, nullable=False, default=True)

    # --- public profile --- #
    name = Column(String(255), nullable=True)
    slug = Column(String(255), unique=True, nullable=True)  # e.g. "/u/alan‑turing"
    avatar_url = Column(String(1024), nullable=True)  # Cloudinary‑sized avatar
    bio = Column(Text, nullable=True)

    # --- timestamps --- #
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # --- relationships --- #
    documents = relationship("Document", back_populates="user", lazy="noload")
    study_plans = relationship("StudyPlan", back_populates="user", lazy="noload")
    learning_sessions = relationship("LearningSession", back_populates="user", lazy="noload")   
    refresh_tokens = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan", lazy="noload"
    )

    # --- helpers --- #
    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} email={self.email} active={self.is_active}>"


# ---------------------------------------------------------------------------
# Refresh tokens (hashed)
# ---------------------------------------------------------------------------

class RefreshToken(Base):
    """Server‑side representation of an OAuth / JWT refresh token.

    We store **only** a SHA‑256 hash, so real tokens never hit the DB.  The
    application compares `hash(token)` on incoming requests.
    """

    __tablename__ = "refresh_tokens"

    id: uuid.UUID = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: uuid.UUID = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    token_hash = Column(String(64), nullable=False)  # 64‑hex chars from SHA‑256
    issued_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, nullable=False, default=False)

    user = relationship("User", back_populates="refresh_tokens", lazy="joined")

    # --- helpers --- #
    def is_valid(self, now: DateTime | None = None) -> bool:
        """True if not revoked and not expired."""
        now = now or func.now()
        return (not self.revoked) and (self.expires_at > now)
