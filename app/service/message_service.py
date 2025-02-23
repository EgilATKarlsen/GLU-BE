from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.model.db import Message


class MessageService:
    @staticmethod
    async def create(session: AsyncSession, data: Dict[str, Any]) -> Message:
        message = Message(**data)
        session.add(message)
        await session.flush()
        await session.refresh(message)
        return message

    @staticmethod
    async def get_by_id(session: AsyncSession, message_id: UUID) -> Optional[Message]:
        result = await session.execute(select(Message).filter(Message.id == message_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_user_id(session: AsyncSession, user_id: str) -> List[Message]:
        result = await session.execute(
            select(Message)
            .filter(Message.user_id == user_id)
            .filter(Message.deleted == False)
        )
        return list(result.scalars().all())

    @staticmethod
    async def save(session: AsyncSession, message: Message) -> Message:
        await session.merge(message)
        await session.flush()
        await session.refresh(message)
        return message
