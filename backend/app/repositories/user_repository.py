"""
User repository — DB access for User entities.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_by_id(self, user_id: int) -> Optional[User]:
        result = await self._db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        result = await self._db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_phone(self, phone: str) -> Optional[User]:
        result = await self._db.execute(
            select(User).where(User.mobile_phone == phone)
        )
        return result.scalar_one_or_none()
