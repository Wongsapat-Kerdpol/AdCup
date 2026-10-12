"""Auth endpoints.

[MAIN]     GET  /api/auth/me          -> current user (used by the frontend auth guard)
[MAIN]     POST /api/auth/dev-login   -> one-click login as a seeded user (dev only)
[PERSON 1] POST /api/auth/register    -> create a brand/creator account, returns TokenResponse
[PERSON 1] POST /api/auth/login       -> email + password, returns TokenResponse
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.models.identity import SignalType
from app.models.user import User
from app.schemas.user import DevLoginRequest, LoginRequest, RegisterRequest, TokenResponse, UserPublic
from app.services.identity import normalize_email, record_request_signals, record_signal

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/dev-login", response_model=TokenResponse)
def dev_login(body: DevLoginRequest, db: Session = Depends(get_db)):
    if not settings.dev_login_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    user = db.scalars(select(User).where(User.role == body.role).order_by(User.id)).first()
    if user is None:
        raise HTTPException(status_code=404, detail=f"No seeded {body.role.value} user")
    return TokenResponse(access_token=create_access_token(user.id, user.role.value), user=user)


# --- Person 1 ---


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db), request: Request = None):
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")

    user = User(
        email=body.email,
        display_name=body.display_name,
        role=body.role,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two sign-ups with the same email at the same moment
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
    db.refresh(user)

    # Linked account detection (services/identity.py); creators only.
    record_signal(db, user, SignalType.email_norm, normalize_email(user.email))
    record_request_signals(db, user, request)
    db.commit()
    return TokenResponse(access_token=create_access_token(user.id, user.role.value), user=user)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db), request: Request = None):
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    # Same message for "no such email" and "wrong password" so attackers can't probe which emails exist.
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    record_request_signals(db, user, request)
    db.commit()
    return TokenResponse(access_token=create_access_token(user.id, user.role.value), user=user)
