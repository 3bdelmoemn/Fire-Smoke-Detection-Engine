"""
Auth router — registration, login, and country-codes endpoints.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_app_settings, get_db
from app.core.config import Settings
from app.schemas.auth import (
    COUNTRY_CODES,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/country-codes")
async def list_country_codes():
    """Return the list of supported country codes for the registration form."""
    return COUNTRY_CODES


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    """Register a new user with username, country code, phone, and password."""
    svc = AuthService(db, settings.JWT_SECRET_KEY, settings.JWT_EXPIRE_MINUTES)
    try:
        user = await svc.register(
            body.username,
            body.country_code,
            body.mobile_phone,
            body.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    """Authenticate and receive a JWT access token."""
    svc = AuthService(db, settings.JWT_SECRET_KEY, settings.JWT_EXPIRE_MINUTES)
    result = await svc.login(body.username, body.password)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token, user = result
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
    )
