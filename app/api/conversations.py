"""
Conversations and messages routes.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.db.session import get_db
from app.models import User, Conversation, Message, UploadedFile, UsageEvent
from app.schemas.schemas import (
    ConversationCreate, ConversationUpdate, ConversationPublic,
    MessagePublic, SendMessageRequest, SendMessageResponse
)
from app.core.deps import get_current_user
from app.services.prompts import build_system_prompt
from app.services.anthropic_proxy import call_anthropic
from app.services.rate_limit import (
    check_and_increment_user_limit, check_global_spend, record_spend,
)


router = APIRouter(prefix="/conversations", tags=["conversations"])


def _attach_counts(db: Session, conv: Conversation) -> ConversationPublic:
    count = db.query(func.count(Message.id)).filter(Message.conversation_id == conv.id).scalar() or 0
    obj = ConversationPublic.model_validate(conv)
    obj.message_count = count
    return obj


@router.get("", response_model=list[ConversationPublic])
def list_conversations(
    archived: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    convs = (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id, Conversation.archived == archived)
        .order_by(desc(Conversation.updated_at))
        .all()
    )
    return [_attach_counts(db, c) for c in convs]


@router.post("", response_model=ConversationPublic)
def create_conversation(
    req: ConversationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = Conversation(
        user_id=user.id,
        title=req.title,
        mode=req.mode,
        model=req.model,
        language=req.language,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return _attach_counts(db, conv)


@router.get("/{conv_id}", response_model=ConversationPublic)
def get_conversation(
    conv_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == user.id).first()
    if not conv:
        raise HTTPException(404, "Not found")
    return _attach_counts(db, conv)


@router.patch("/{conv_id}", response_model=ConversationPublic)
def update_conversation(
    conv_id: int,
    req: ConversationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == user.id).first()
    if not conv:
        raise HTTPException(404, "Not found")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(conv, k, v)
    db.commit()
    db.refresh(conv)
    return _attach_counts(db, conv)


@router.delete("/{conv_id}")
def delete_conversation(
    conv_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == user.id).first()
    if not conv:
        raise HTTPException(404, "Not found")
    db.delete(conv)
    db.commit()
    return {"ok": True}


@router.get("/{conv_id}/messages", response_model=list[MessagePublic])
def get_messages(
    conv_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == user.id).first()
    if not conv:
        raise HTTPException(404, "Not found")
    msgs = db.query(Message).filter(Message.conversation_id == conv_id).order_by(Message.id).all()
    return [MessagePublic.model_validate(m) for m in msgs]


@router.post("/{conv_id}/messages", response_model=SendMessageResponse)
async def send_message(
    conv_id: int,
    req: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Validate conversation
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == user.id).first()
    if not conv:
        raise HTTPException(404, "Conversation not found")

    # Global circuit breaker
    allowed_global, spent, reason_global = check_global_spend()
    if not allowed_global:
        raise HTTPException(503, detail=reason_global)

    # Per-user rate limit
    allowed_user, remaining, reason_user = check_and_increment_user_limit(
        user.id,
        user.daily_limit_override,
        user.monthly_limit_override,
    )
    if not allowed_user:
        raise HTTPException(429, detail=reason_user)

    # Resolve attached file content
    attached_text_block = ""
    attached_file = None
    if req.attached_file_id:
        attached_file = db.query(UploadedFile).filter(
            UploadedFile.id == req.attached_file_id,
            UploadedFile.user_id == user.id,
        ).first()
        if not attached_file:
            raise HTTPException(404, "Attached file not found")
        if attached_file.extracted_text:
            # Clamp to ~30k chars to avoid prompt overflow
            snippet = attached_file.extracted_text[:30000]
            attached_text_block = f"\n\n---\nAttached file: {attached_file.filename}\n\n{snippet}"

    # Build message list from history
    prior = db.query(Message).filter(Message.conversation_id == conv_id).order_by(Message.id).all()
    messages = []
    for m in prior:
        if m.role in ("user", "assistant"):
            messages.append({"role": m.role, "content": m.content})

    # Append current user message (with attached text appended)
    user_full_content = req.content + attached_text_block
    messages.append({"role": "user", "content": user_full_content})

    # Persist user message first
    user_msg = Message(
        conversation_id=conv_id,
        role="user",
        content=req.content,  # store only original user text, not the attachment body (it's in file record)
        attached_file_id=req.attached_file_id,
        mode=conv.mode,
    )
    db.add(user_msg)
    db.flush()

    # Build system prompt
    system_prompt = build_system_prompt(db, mode=conv.mode, language=conv.language)

    # Call Anthropic
    try:
        result = await call_anthropic(
            system_prompt=system_prompt,
            messages=messages,
            model=conv.model,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(502, detail=f"Upstream LLM error: {e}")

    # Record global spend
    record_spend(result["cost_usd"])

    # Persist assistant message
    assistant_msg = Message(
        conversation_id=conv_id,
        role="assistant",
        content=result["content"],
        input_tokens=result["input_tokens"],
        output_tokens=result["output_tokens"],
        cost_usd=result["cost_usd"],
        model=result["model"],
        mode=conv.mode,
    )
    db.add(assistant_msg)
    db.flush()

    # Usage event audit
    db.add(UsageEvent(
        user_id=user.id,
        message_id=assistant_msg.id,
        event_type="chat",
        model=result["model"],
        input_tokens=result["input_tokens"],
        output_tokens=result["output_tokens"],
        cost_usd=result["cost_usd"],
    ))

    # Update conversation timestamp and auto-title
    from datetime import datetime, timezone
    conv.updated_at = datetime.now(timezone.utc)
    if conv.title == "Untitled" and req.content:
        conv.title = req.content[:60].strip().replace("\n", " ")

    db.commit()
    db.refresh(user_msg)
    db.refresh(assistant_msg)
    db.refresh(conv)

    return SendMessageResponse(
        user_message=MessagePublic.model_validate(user_msg),
        assistant_message=MessagePublic.model_validate(assistant_msg),
        conversation=_attach_counts(db, conv),
        rate_limit_remaining_today=remaining,
    )
