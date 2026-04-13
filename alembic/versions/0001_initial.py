"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-04-13

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("is_admin", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("daily_limit_override", sa.Integer, nullable=False, server_default="0"),
        sa.Column("monthly_limit_override", sa.Integer, nullable=False, server_default="0"),
        sa.Column("invite_code_used", sa.String(64), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "invite_codes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("max_uses", sa.Integer, nullable=False, server_default="1"),
        sa.Column("used_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_invite_codes_code", "invite_codes", ["code"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False, server_default="Untitled"),
        sa.Column("mode", sa.String(32), nullable=False, server_default="branch_a_beta"),
        sa.Column("model", sa.String(64), nullable=False, server_default="claude-opus-4-6"),
        sa.Column("language", sa.String(16), nullable=False, server_default="auto"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("archived", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    op.create_table(
        "uploaded_files",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("extracted_text", sa.Text, nullable=True),
        sa.Column("storage_path", sa.String(512), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_uploaded_files_user_id", "uploaded_files", ["user_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("conversation_id", sa.Integer, sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float, nullable=False, server_default="0"),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("mode", sa.String(32), nullable=True),
        sa.Column("provenance", sa.JSON, nullable=True),
        sa.Column("attached_file_id", sa.Integer, sa.ForeignKey("uploaded_files.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    op.create_table(
        "hu_cards",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("paper_id", sa.String(255), nullable=False, unique=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("authors", sa.Text, nullable=False),
        sa.Column("journal", sa.String(128), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("author_position", sa.String(64), nullable=False),
        sa.Column("method_path", sa.String(64), nullable=False),
        sa.Column("opening_style", sa.String(64), nullable=False),
        sa.Column("publisher_era", sa.String(64), nullable=True),
        sa.Column("red_line_gold_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("full_yaml", sa.Text, nullable=False),
        sa.Column("card_data", sa.JSON, nullable=False),
        sa.Column("extractor_version", sa.String(32), nullable=False, server_default="v1.5"),
        sa.Column("extracted_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_hu_cards_paper_id", "hu_cards", ["paper_id"])

    op.create_table(
        "journal_fingerprints",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("journal_id", sa.String(64), nullable=False, unique=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("publisher_era", sa.String(64), nullable=True),
        sa.Column("maturity_tier", sa.String(32), nullable=False),
        sa.Column("cards_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("min_threshold", sa.Integer, nullable=False, server_default="6"),
        sa.Column("branch_b_authorization", sa.String(32), nullable=False, server_default="denied"),
        sa.Column("fingerprint_yaml", sa.Text, nullable=False),
        sa.Column("fingerprint_data", sa.JSON, nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_journal_fingerprints_journal_id", "journal_fingerprints", ["journal_id"])

    op.create_table(
        "extraction_jobs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", sa.Integer, sa.ForeignKey("uploaded_files.id", ondelete="SET NULL"), nullable=True),
        sa.Column("branch", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("produced_card_id", sa.Integer, sa.ForeignKey("hu_cards.id", ondelete="SET NULL"), nullable=True),
        sa.Column("produced_fingerprint_id", sa.Integer, sa.ForeignKey("journal_fingerprints.id", ondelete="SET NULL"), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_extraction_jobs_user_id", "extraction_jobs", ["user_id"])

    op.create_table(
        "usage_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", sa.Integer, sa.ForeignKey("messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_usage_events_user_id", "usage_events", ["user_id"])
    op.create_index("ix_usage_user_date", "usage_events", ["user_id", "created_at"])


def downgrade() -> None:
    for t in ["usage_events", "extraction_jobs", "journal_fingerprints", "hu_cards",
              "messages", "uploaded_files", "conversations", "invite_codes", "users"]:
        op.drop_table(t)
