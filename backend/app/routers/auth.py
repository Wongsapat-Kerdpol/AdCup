"""Auth endpoints.

[MAIN]     GET  /api/auth/me          -> current user (used by the frontend auth guard)
[MAIN]     POST /api/auth/dev-login   -> one-click login as a seeded user (dev only)
[PERSON 1] POST /api/auth/register    -> TODO
[PERSON 1] POST /api/auth/login       -> TODO
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.user import DevLoginRequest, TokenResponse, UserPublic

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


# TODO(Person 1): POST /register  — validate input, hash_password(), create User, return TokenResponse
# TODO(Person 1): POST /login     — verify_password(), return TokenResponse (use create_access_token)
