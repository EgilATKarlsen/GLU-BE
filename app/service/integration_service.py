from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.model.db import Integration
from app.model.schema import Integration as IntegrationSchema


class IntegrationService:
    @staticmethod
    async def create(session: AsyncSession, data: Dict[str, Any]) -> Integration:
        integration = Integration(**data)
        session.add(integration)
        await session.flush()
        await session.refresh(integration)
        return integration

    @staticmethod
    async def get_by_id(
        session: AsyncSession, integration_id: UUID
    ) -> Optional[Integration]:
        result = await session.execute(
            select(Integration).filter(Integration.id == integration_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def save(session: AsyncSession, integration: Integration) -> Integration:
        await session.merge(integration)
        await session.flush()
        await session.refresh(integration)
        return integration

    @staticmethod
    def to_schema(integration: Integration) -> IntegrationSchema:
        return IntegrationSchema.model_validate(integration)

    async def get_integrations_by_providers(
        session: AsyncSession, providers: List[str]
    ) -> List[Integration]:
        """
        Get integrations by their provider names.
        """
        query = select(Integration).where(Integration.clerk_name.in_(providers))
        result = await session.execute(query)
        return result.scalars().all()
