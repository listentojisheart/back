"""
Admin routes: invite code management, user management, global usage stats.
"""
import secrets
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.db.session import get_db
from app.models import User, InviteCode, UsageEvent
from app.schemas.schemas import InviteCodeCreate, InviteCodePublic, UserPublic
from app.core.deps import get_current_admin
from app.services.rate_limit import get_global_usage


router = APIRouter(prefix="/admin", tags=["admin"])


def _generate_code() -> str:
    # 12 chars of url-safe base64 ≈ 72 bits entropy
    return secrets.token_urlsafe(9)


# ===== Invite codes =====

@router.get("/invite-codes", response_model=list[InviteCodePublic])
def list_invite_codes(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    codes = db.query(InviteCode).order_by(desc(InviteCode.created_at)).all()
    return [InviteCodePublic.model_validate(c) for c in codes]


@router.post("/invite-codes", response_model=InviteCodePublic)
def create_invite_code(
    req: InviteCodeCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    expires_at = None
    if req.expires_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=req.expires_days)
    code = InviteCode(
        code=_generate_code(),
        note=req.note,
        max_uses=req.max_uses,
        expires_at=expires_at,
    )
    db.add(code)
    db.commit()
    db.refresh(code)
    return InviteCodePublic.model_validate(code)


@router.delete("/invite-codes/{code_id}")
def disable_invite_code(
    code_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    code = db.query(InviteCode).filter(InviteCode.id == code_id).first()
    if not code:
        raise HTTPException(404, "Not found")
    code.is_active = False
    db.commit()
    return {"ok": True}


# ===== Users =====

@router.get("/users", response_model=list[UserPublic])
def list_users(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    users = db.query(User).order_by(desc(User.registered_at)).all()
    return [UserPublic.model_validate(u) for u in users]


@router.patch("/users/{user_id}/deactivate")
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if user_id == admin.id:
        raise HTTPException(400, "Cannot deactivate self")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Not found")
    user.is_active = False
    db.commit()
    return {"ok": True}


@router.patch("/users/{user_id}/reactivate")
def reactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Not found")
    user.is_active = True
    db.commit()
    return {"ok": True}


# ===== Global stats =====

@router.get("/stats")
def global_stats(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    user_count = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0  # noqa
    total_spend = db.query(func.coalesce(func.sum(UsageEvent.cost_usd), 0)).scalar() or 0
    total_tokens_in = db.query(func.coalesce(func.sum(UsageEvent.input_tokens), 0)).scalar() or 0
    total_tokens_out = db.query(func.coalesce(func.sum(UsageEvent.output_tokens), 0)).scalar() or 0

    # Today's spend
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_spend = db.query(func.coalesce(func.sum(UsageEvent.cost_usd), 0)).filter(UsageEvent.created_at >= today_start).scalar() or 0

    return {
        "users": {
            "total": user_count,
            "active": active_users,
        },
        "lifetime_usage": {
            "input_tokens": int(total_tokens_in),
            "output_tokens": int(total_tokens_out),
            "cost_usd": round(float(total_spend), 4),
        },
        "today_spend_db_usd": round(float(today_spend), 4),
        "redis_circuit_breaker": get_global_usage(),
    }
