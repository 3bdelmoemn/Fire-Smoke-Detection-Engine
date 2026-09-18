"""
Auth Service — business logic for user registration and login.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import normalize_phone, validate_phone_number, check_password_strength

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession, secret_key: str, expire_minutes: int):
        self._db = db
        self._secret_key = secret_key
        self._expire_minutes = expire_minutes

    async def register(
        self,
        username: str,
        country_code: str,
        mobile_phone: str,
        password: str,
    ) -> User:
        """Create a new user. Raises ValueError if validation fails or user exists."""
        # Validate password strength (backend enforcement)
        pwd_errors = check_password_strength(password)
        if pwd_errors:
            raise ValueError("; ".join(pwd_errors))

        # Validate and normalize phone number
        normalized = validate_phone_number(country_code, mobile_phone)
        if normalized is None:
            raise ValueError(
                "Invalid phone number. Please check the country code and number."
            )

        # Check uniqueness
        existing = await self._db.execute(
            select(User).where(
                (User.username == username) | (User.mobile_phone == normalized)
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Username or mobile phone already registered")

        user = User(
            username=username,
            mobile_phone=normalized,
            password_hash=hash_password(password),
        )
        self._db.add(user)
        await self._db.flush()
        await self._db.refresh(user)
        logger.info("User registered: %s (id=%d, phone=%s)", username, user.id, normalized)
        return user

    async def login(self, username: str, password: str) -> Optional[tuple[str, User]]:
        """
        Verify credentials and return (access_token, user) or None.
        """
        result = await self._db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        if user is None or not verify_password(password, user.password_hash):
            return None

        token = create_access_token(
            data={"sub": str(user.id), "username": user.username},
            secret_key=self._secret_key,
            expires_minutes=self._expire_minutes,
        )
        logger.info("User logged in: %s (id=%d)", username, user.id)
        return token, user
