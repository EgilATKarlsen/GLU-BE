from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from app.model.db import UserRole, IntegrationCategory, AuthType


class UserCreateRequest(BaseModel):
    name: str = Field(..., description="User's full name")
    email: EmailStr = Field(..., description="User's email address")
    role: Optional[UserRole] = Field(
        default=UserRole.user, description="User's role in the system"
    )


class UserUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, description="User's full name")
    email: Optional[EmailStr] = Field(None, description="User's email address")
    role: Optional[UserRole] = Field(None, description="User's role in the system")


class IntegrationCreateRequest(BaseModel):
    name: str = Field(..., description="Name of the integration")
    clerk_name: str = Field(..., description="Clerk identifier for the integration")
    base_host: str = Field(..., description="Base URL for the integration API")
    description: str = Field(..., description="Description of the integration")
    keywords: str = Field(..., description="Comma-separated keywords")
    category: IntegrationCategory = Field(
        ..., description="Category of the integration"
    )
    logo: str = Field(..., description="S3 URL for the integration logo")
    version: str = Field(..., description="Version of the integration")
    schema: str = Field(..., description="S3 URL for the integration schema")
    auth_type: AuthType = Field(
        default=AuthType.none, description="Authentication type"
    )
    spec: str = Field(..., description="S3 URL for the integration specification")


class UserIntegrationCreateRequest(BaseModel):
    integration_id: UUID = Field(..., description="UUID of the integration to connect")
    clerk_id: str = Field(
        ..., description="Clerk identifier for the integration instance"
    )


class UserIntegrationUpdateRequest(BaseModel):
    clerk_id: Optional[str] = Field(None, description="Updated clerk identifier")


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Page number")
    limit: int = Field(default=10, ge=1, le=100, description="Items per page")


# Query parameters for filtering
class IntegrationFilterParams(BaseModel):
    category: Optional[IntegrationCategory] = Field(
        None, description="Filter by category"
    )
    auth_type: Optional[AuthType] = Field(None, description="Filter by auth type")
    search: Optional[str] = Field(None, description="Search in name and description")


class UserFilterParams(BaseModel):
    role: Optional[UserRole] = Field(None, description="Filter by user role")
    search: Optional[str] = Field(None, description="Search in name and email")
