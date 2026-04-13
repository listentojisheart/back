"""
SQLAlchemy models for the TK-7 system.

Tables:
- users: authenticated users
- invite_codes: for gated registration
- conversations: user sessions grouping messages
- messages: individual user/assistant turns
- uploaded_files: PDFs/DOCX user uploads for extraction
- hu_cards: Hu pattern library cards (Branch A)
- journal_fingerprints: Journal pattern library (Branch B)
- extraction_jobs: async extraction task tracking
- usage_events: per-message token + cost tracking for billing audit
"""
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, ForeignKey, DateTime,
    Float, JSON, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.db.session import Base


def _now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Rate limit override (0 = use default)
    daily_limit_override: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    monthly_limit_override: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Registration trail
    invite_code_used: Mapped[str | None] = mapped_column(String(64), nullable=True)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    uploaded_files = relationship("UploadedFile", back_populates="user", cascade="all, delete-orphan")
    usage_events = relationship("UsageEvent", back_populates="user", cascade="all, delete-orphan")


class InviteCode(Base):
    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)  # e.g., "For Hu", "Lab batch 1"
    max_uses: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), default="Untitled", nullable=False)
    mode: Mapped[str] = mapped_column(String(32), default="branch_a_beta", nullable=False)  # branch_a_alpha | branch_a_beta | branch_b_alpha | branch_b_beta
    model: Mapped[str] = mapped_column(String(64), default="claude-opus-4-6", nullable=False)
    language: Mapped[str] = mapped_column(String(16), default="auto", nullable=False)  # auto | en | zh
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.id")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user | assistant | system
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Per-message metadata
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mode: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Provenance (for Branch A/B outputs: list of pattern IDs cited)
    provenance: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # File attachment reference (if this message uploaded a file)
    attached_file_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("uploaded_files.id", ondelete="SET NULL"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # PDF/DOCX → text
    storage_path: Mapped[str | None] = mapped_column(String(512), nullable=True)  # if we keep original
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    user = relationship("User", back_populates="uploaded_files")


class HuCard(Base):
    """Branch A pattern library cards. One row per extracted paper."""
    __tablename__ = "hu_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    paper_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    authors: Mapped[str] = mapped_column(Text, nullable=False)  # comma-joined
    journal: Mapped[str] = mapped_column(String(128), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    author_position: Mapped[str] = mapped_column(String(64), nullable=False)  # "1st", "2nd_substantive", etc.
    method_path: Mapped[str] = mapped_column(String(64), nullable=False)  # "structural", "RDD", "ml", ...
    opening_style: Mapped[str] = mapped_column(String(64), nullable=False)
    publisher_era: Mapped[str | None] = mapped_column(String(64), nullable=True)
    red_line_gold_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Full card body as YAML/JSON
    full_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    card_data: Mapped[dict] = mapped_column(JSON, nullable=False)  # parsed for querying

    # Meta
    extractor_version: Mapped[str] = mapped_column(String(32), default="v1.5", nullable=False)
    extracted_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class JournalFingerprint(Base):
    """Branch B journal pattern library."""
    __tablename__ = "journal_fingerprints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    journal_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    publisher_era: Mapped[str | None] = mapped_column(String(64), nullable=True)
    maturity_tier: Mapped[str] = mapped_column(String(32), nullable=False)  # SEED, CANDIDATE, COMMITTED, ROBUST
    cards_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    min_threshold: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    branch_b_authorization: Mapped[str] = mapped_column(String(32), default="denied", nullable=False)
    # denied, gap_audit_only, full_generation

    fingerprint_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    fingerprint_data: Mapped[dict] = mapped_column(JSON, nullable=False)

    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class ExtractionJob(Base):
    """Tracks async extraction jobs (TK-7 extraction takes time)."""
    __tablename__ = "extraction_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("uploaded_files.id", ondelete="SET NULL"), nullable=True)
    branch: Mapped[str] = mapped_column(String(16), nullable=False)  # a | b
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    # queued | running | completed | failed

    # Outputs
    produced_card_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("hu_cards.id", ondelete="SET NULL"), nullable=True)
    produced_fingerprint_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("journal_fingerprints.id", ondelete="SET NULL"), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UsageEvent(Base):
    """Audit trail for API usage + cost, used by rate limiter and billing."""
    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)  # chat, extraction, etc.
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    user = relationship("User", back_populates="usage_events")

    __table_args__ = (
        Index("ix_usage_user_date", "user_id", "created_at"),
    )
