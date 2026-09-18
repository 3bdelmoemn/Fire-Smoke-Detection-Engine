"""
Shared FastAPI dependencies.

Injected into route handlers via ``Depends()``.  Centralising them here
means every router gets the same DB session, auth logic, and service
instances without importing concrete implementations.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import decode_access_token
from app.db.session import async_session_factory
from app.models.user import User

logger = logging.getLogger(__name__)

# ── Security scheme ──────────────────────────────────────────────────────
bearer_scheme = HTTPBearer(auto_error=False)


# ── Database session ─────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session that auto-closes after the request."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Settings ─────────────────────────────────────────────────────────────
def get_app_settings() -> Settings:
    return get_settings()


# ── Current user (JWT) ───────────────────────────────────────────────────
async def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    settings: Settings = Depends(get_app_settings),
) -> int:
    """
    Extract and validate the JWT from the Authorization header.
    Returns the user id encoded in the token's ``sub`` claim.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials, settings.JWT_SECRET_KEY)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )
    return int(user_id)


async def get_current_user(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Return the full User object for the authenticated user.
    Needed when endpoints require user details (e.g. WhatsApp phone number).
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


# ── Optional auth (for endpoints that work with or without login) ────────
async def get_optional_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    settings: Settings = Depends(get_app_settings),
) -> Optional[int]:
    """Return user id if a valid token is present, otherwise ``None``."""
    if credentials is None:
        return None
    payload = decode_access_token(credentials.credentials, settings.JWT_SECRET_KEY)
    if payload is None:
        return None
    user_id = payload.get("sub")
    return int(user_id) if user_id else None
