from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from asyncio import gather

from app.model.db import UserIntegration
from app.model.schema import UserIntegration as UserIntegrationSchema
from app.service.integration_service import IntegrationService
from app.client.types.clerk import ExternalAccount


class UserIntegrationService:
    @staticmethod
    async def create(session: AsyncSession, data: Dict[str, Any]) -> UserIntegration:
        user_integration = UserIntegration(**data)
        session.add(user_integration)
        await session.flush()
        await session.refresh(user_integration)
        return user_integration

    @staticmethod
    async def get_by_id(
        session: AsyncSession, user_integration_id: UUID
    ) -> Optional[UserIntegration]:
        result = await session.execute(
            select(UserIntegration).filter(UserIntegration.id == user_integration_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_user_id(
        session: AsyncSession, user_id: str
    ) -> List[UserIntegration]:
        result = await session.execute(
            select(UserIntegration)
            .filter(UserIntegration.user_id == user_id)
            .filter(UserIntegration.deleted == False)
        )
        return list(result.scalars().all())

    @staticmethod
    async def save(
        session: AsyncSession, user_integration: UserIntegration
    ) -> UserIntegration:
        await session.merge(user_integration)
        await session.flush()
        await session.refresh(user_integration)
        return user_integration

    @staticmethod
    def to_schema(user_integration: UserIntegration) -> UserIntegrationSchema:
        # Remove the async since this is a synchronous operation
        return UserIntegrationSchema.model_validate(user_integration)

    @staticmethod
    async def sync_integrations(
        session: AsyncSession,
        user_id: str,
        external_accounts: List[ExternalAccount],
    ) -> List[UserIntegrationSchema]:
        try:
            print(external_accounts)
            # Extract provider names from external accounts
            external_providers = {account.provider for account in external_accounts}

            # Query for matching integrations based on provider
            integrations_in_db = await IntegrationService.get_integrations_by_providers(
                session, list(external_providers)
            )
            integration_map = {
                integration.clerk_name: integration
                for integration in integrations_in_db
            }

            # Fetch current user integrations
            current_integrations = await UserIntegrationService.get_by_user_id(
                session, user_id
            )
            current_integrations_map = {ui.clerk_id: ui for ui in current_integrations}

            # Prepare new integration data
            new_integration_data = []
            for account in external_accounts:
                provider = account.provider
                if provider in integration_map:
                    # Skip if integration already exists for this user
                    if provider in current_integrations_map:
                        continue
                    # Otherwise, prepare new integration data
                    new_integration_data.append(
                        (integration_map[provider].id, provider)
                    )

            # Soft-delete user integrations no longer present in external accounts
            for provider, user_integration in current_integrations_map.items():
                if provider not in external_providers:
                    user_integration.delete()
            await session.flush()

            # Insert new user integrations
            await UserIntegrationService.insert_multiple_user_integrations(
                session, user_id, new_integration_data
            )

            # Return updated list of active user integrations
            user_integrations = await UserIntegrationService.get_by_user_id(
                session, user_id
            )

            # Since to_schema is now sync, we don't need gather
            return [UserIntegrationService.to_schema(ui) for ui in user_integrations]

        except Exception as e:
            await session.rollback()
            import traceback

            print(f"Error in sync_integrations: {str(e)}")
            print("Traceback:")
            print(traceback.format_exc())
            raise

    @staticmethod
    async def insert_multiple_user_integrations(
        session: AsyncSession, user_id: str, integration_data: List[tuple[UUID, str]]
    ) -> None:
        """
        Insert multiple user integrations in bulk.

        Args:
            session: The database session
            user_id: The ID of the user
            integration_data: List of tuples containing (integration_id, provider)
        """
        if not integration_data:
            return

        # Create UserIntegration objects for each new integration
        new_integrations = [
            UserIntegration(
                user_id=user_id,
                integration_id=integration_id,
                clerk_id=provider,
            )
            for integration_id, provider in integration_data
        ]

        # Add all new integrations to the session
        session.add_all(new_integrations)
        await session.flush()
