"""
Auth routes: register (with invite code), login, refresh, me.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.db.session import get_db
from app.models import User, InviteCode
from app.schemas.schemas import (
    RegisterRequest, LoginRequest, RefreshRequest, TokenResponse, UserPublic
)
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.core.config import settings
from app.core.deps import get_current_user


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    # Invite code required by settings
    if settings.INVITE_CODE_REQUIRED:
        invite = db.query(InviteCode).filter(InviteCode.code == req.invite_code).first()
        if not invite or not invite.is_active:
            raise HTTPException(status_code=400, detail="Invalid or inactive invite code")
        if invite.used_count >= invite.max_uses:
            raise HTTPException(status_code=400, detail="Invite code exhausted")
        if invite.expires_at and invite.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Invite code expired")

    # Check duplicates
    existing = db.query(User).filter(
        or_(User.email == req.email, User.username == req.username)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email or username already registered")

    user = User(
        email=req.email,
        username=req.username,
        password_hash=hash_password(req.password),
        invite_code_used=req.invite_code if settings.INVITE_CODE_REQUIRED else None,
    )
    db.add(user)

    if settings.INVITE_CODE_REQUIRED:
        invite.used_count += 1

    db.commit()
    db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        or_(User.email == req.email_or_username, User.username == req.email_or_username)
    ).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User deactivated")

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(req: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(req.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User invalid")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)):
    return user
