"""
Pydantic schemas for request/response validation.
"""
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ===== Auth =====

class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    invite_code: str = Field(min_length=1, max_length=64)


class LoginRequest(BaseModel):
    email_or_username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    username: str
    is_admin: bool
    registered_at: datetime


# ===== Conversations =====

class ConversationCreate(BaseModel):
    title: str = Field(default="Untitled", max_length=255)
    mode: str = Field(default="router")  # router | branch_a | branch_b
    model: str = Field(default="claude-opus-4-6")
    language: str = Field(default="auto")


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    mode: Optional[str] = None
    language: Optional[str] = None
    archived: Optional[bool] = None


class ConversationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    mode: str
    model: str
    language: str
    created_at: datetime
    updated_at: datetime
    archived: bool
    message_count: int = 0


# ===== Messages =====

class MessagePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    conversation_id: int
    role: str
    content: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    provenance: Optional[dict] = None
    attached_file_id: Optional[int] = None
    created_at: datetime


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=200000)
    attached_file_id: Optional[int] = None


class SendMessageResponse(BaseModel):
    user_message: MessagePublic
    assistant_message: MessagePublic
    conversation: ConversationPublic
    rate_limit_remaining_today: int


# ===== Files =====

class UploadedFilePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    mime_type: str
    size_bytes: int
    uploaded_at: datetime
    has_extracted_text: bool = False


# ===== Library =====

class HuCardPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    paper_id: str
    title: str
    authors: str
    journal: str
    year: int
    author_position: str
    method_path: str
    opening_style: str
    publisher_era: Optional[str] = None
    red_line_gold_count: int
    extractor_version: str
    created_at: datetime


class HuCardDetail(HuCardPublic):
    full_yaml: str
    card_data: dict


class JournalFingerprintPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    journal_id: str
    full_name: str
    publisher_era: Optional[str] = None
    maturity_tier: str
    cards_count: int
    min_threshold: int
    branch_b_authorization: str
    created_at: datetime


class JournalFingerprintDetail(JournalFingerprintPublic):
    fingerprint_yaml: str
    fingerprint_data: dict


# ===== Extraction =====

class ExtractionJobCreate(BaseModel):
    file_id: int
    branch: str = Field(pattern="^(a|b)$")
    target_journal_id: Optional[str] = None  # for branch b


class ExtractionJobPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    branch: str
    status: str
    produced_card_id: Optional[int] = None
    produced_fingerprint_id: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


# ===== Admin / Invite =====

class InviteCodeCreate(BaseModel):
    note: Optional[str] = None
    max_uses: int = Field(default=1, ge=1, le=100)
    expires_days: Optional[int] = Field(default=None, ge=1, le=365)


class InviteCodePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    note: Optional[str] = None
    max_uses: int
    used_count: int
    is_active: bool
    expires_at: Optional[datetime] = None
    created_at: datetime


# ===== System status =====

class LibraryStatus(BaseModel):
    branch_a: dict
    branch_b: dict
    total_hu_cards: int
    total_journal_fingerprints: int
    committed_fingerprints: int
