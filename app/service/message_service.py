from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.model.db import Message
from app.model.schema import Message as MessageSchema


class MessageService:
    @staticmethod
    async def create(session: AsyncSession, data: Dict[str, Any]) -> Message:
        # Convert Pydantic model to dict if needed
        data_dict = data.model_dump() if hasattr(data, "model_dump") else data
        message = Message(**data_dict)
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
    async def to_schema(message: Message) -> MessageSchema:
        return MessageSchema(
            id=message.id,
            user_id=message.user_id,
            integration_id=message.integration_id,
            start_time=message.start_time,
            end_time=message.end_time,
            latency=message.latency,
            initial_input=message.initial_input,
            result=message.result,
            created_at=message.created_at,
            updated_at=message.updated_at,
            deleted=message.deleted,
        )

    @staticmethod
    async def save(session: AsyncSession, message: Message) -> Message:
        await session.merge(message)
        await session.flush()
        await session.refresh(message)
        return message
