from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.model.db import User
from app.model.schema import User as UserSchema


class UserService:
    @staticmethod
    async def create(session: AsyncSession, data: Dict[str, Any]) -> User:
        user = User(**data)
        session.add(user)
        await session.flush()
        await session.refresh(user)
        return user

    @staticmethod
    async def get_by_id(session: AsyncSession, user_id: str) -> Optional[User]:
        result = await session.execute(select(User).filter(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def save(session: AsyncSession, user: User) -> User:
        await session.merge(user)
        await session.flush()
        await session.refresh(user)
        return user

    @staticmethod
    def to_schema(user: User) -> UserSchema:
        return UserSchema.model_validate(user)
