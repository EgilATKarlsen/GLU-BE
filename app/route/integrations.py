from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from app.dependencies import get_db
from app.service.integration_service import IntegrationService
from app.service.user_integration_service import UserIntegrationService
from app.model.schema import (
    Integration,
    IntegrationCreate,
    UserIntegration,
    UserIntegrationCreate,
)
from app.types.request import (
    IntegrationCreateRequest,
    UserIntegrationCreateRequest,
    IntegrationFilterParams,
    PaginationParams,
)
from app.types.response import (
    UserIntegrationResponse,
    UserIntegrationListResponse,
    ErrorResponse,
)
from app.client.clerk import ClerkClient

router = APIRouter()


@router.get(
    "/integrations/{user_id}",
    response_model=UserIntegrationListResponse,
    responses={500: {"model": ErrorResponse}},
)
async def get_integrations(user_id: str, db: AsyncSession = Depends(get_db)):
    try:
        integrations = await UserIntegrationService.get_by_user_id(db, user_id)
        return UserIntegrationListResponse(
            user_integrations=[
                UserIntegrationService.to_schema(i) for i in integrations
            ],
            total=len(integrations),
            page=1,
            pages=1,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/integrations/{integration_id}",
    response_model=UserIntegrationResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_integration(integration_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        integration = await UserIntegrationService.get_by_id(db, integration_id)
        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")
        return UserIntegrationService.to_schema(integration)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/users/{user_id}/integrations",
    response_model=UserIntegrationResponse,
    responses={400: {"model": ErrorResponse}},
)
async def create_user_integration(
    user_id: str,
    request: UserIntegrationCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        integration_data = request.model_dump()
        integration_data["user_id"] = user_id
        db_integration = await UserIntegrationService.create(db, integration_data)
        return UserIntegrationService.to_schema(db_integration)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/integrations/{user_id}/sync",
    response_model=UserIntegrationListResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def sync_integrations(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        async with ClerkClient() as clerk:
            # Fetch user details from Clerk to get external accounts
            user = await clerk.get_user(user_id)

            # Create or update UserIntegration for each external account
            synced_integrations = []
            for external_account in user.external_accounts:
                integration_data = {
                    "user_id": user_id,
                    "provider": external_account.provider,
                    "external_id": external_account.provider_user_id,
                    "access_token": None,  # We'll fetch this separately
                }

                try:
                    # Get OAuth tokens for the provider
                    tokens = await clerk.get_user_oauth_access_token(
                        user_id, external_account.provider
                    )
                    print(tokens)
                    if isinstance(tokens, list):
                        integration_data["access_token"] = tokens[0].get("token")
                    else:
                        integration_data["access_token"] = tokens.get("token")
                except Exception as e:
                    print(
                        f"Failed to fetch token for {external_account.provider}: {str(e)}"
                    )
                    continue
            # Create or update the integration
            db_integration = await UserIntegrationService.sync_integrations(
                db, user_id, user.external_accounts
            )

        return UserIntegrationListResponse(
            user_integrations=[
                UserIntegrationService.to_schema(i) for i in db_integration
            ],
            total=len(db_integration),
            page=1,
            pages=1,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
