from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID, uuid4

from app.model.schema import UserIntegration as UserIntegrationSchema

from app.model.db import UserRole, IntegrationCategory, AuthType


# Base response models with common fields
class BaseResponse(BaseModel):
    created_at: datetime
    updated_at: datetime
    deleted: bool = False


# User response models
class UserResponse(BaseResponse):
    id: str = Field(..., description="User's unique identifier")
    name: str = Field(..., description="User's full name")
    email: EmailStr = Field(..., description="User's email address")
    role: UserRole = Field(..., description="User's role in the system")


class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int = Field(..., description="Total number of users")
    page: int = Field(..., description="Current page number")
    pages: int = Field(..., description="Total number of pages")


# Integration response models
class IntegrationResponse(BaseResponse):
    id: UUID = Field(..., description="Integration's unique identifier")
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
    auth_type: AuthType = Field(..., description="Authentication type")
    spec: str = Field(..., description="S3 URL for the integration specification")


class IntegrationListResponse(BaseModel):
    integrations: List[IntegrationResponse]
    total: int = Field(..., description="Total number of integrations")
    page: int = Field(..., description="Current page number")
    pages: int = Field(..., description="Total number of pages")


# User Integration response models
class UserIntegrationResponse(BaseResponse):
    id: UUID = Field(..., description="User integration's unique identifier")
    integration_id: UUID = Field(..., description="Associated integration ID")
    clerk_id: str = Field(
        ..., description="Clerk identifier for the integration instance"
    )
    user_id: str = Field(..., description="Associated user ID")
    integration: IntegrationResponse = Field(..., description="Integration details")


class UserIntegrationListResponse(BaseModel):
    user_integrations: List[UserIntegrationSchema]
    total: int = Field(..., description="Total number of user integrations")
    page: int = Field(..., description="Current page number")
    pages: int = Field(..., description="Total number of pages")


# Status response models
class DatabaseStatus(BaseModel):
    connected: bool
    info: Optional[str]
    async_: bool = False


class HealthCheckResponse(BaseModel):
    database: DatabaseStatus
    message: str
    healthy: bool


# Generic error response
class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error message")
    code: Optional[str] = Field(None, description="Error code")


class Tool(BaseModel):
    name: str
    description: str
    parameters: dict
    strict: bool = True

    def to_json(self) -> dict:
        return self.model_dump()


class Function(BaseModel):
    type: str
    function: Tool

    def to_json(self) -> dict:
        # Automatically converts the nested Tool instance by calling its method.
        data = self.model_dump()
        data["function"] = self.function.to_json()
        return data


class Function_Attributes(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    method: str
    path: str
    tags: list[str]
    description: str
    function: Function

    def to_json(self) -> dict:
        data = self.model_dump()
        # Convert the nested Function instance
        data["function"] = self.function.to_json()
        return data


class ConfirmToolCallRequest(BaseModel):
    tool_hit: dict = Field(
        ...,
        description="Tool hit data (typically the search hit from Meilisearch) needed to setup the tool client.",
    )
    tool_call: dict = Field(
        ...,
        description="Original tool call details with id and tool_name as returned in the verification response.",
    )
    updated_arguments: dict = Field(
        ...,
        description="Updated tool arguments provided by the user for final execution.",
    )
    messages: List[dict] = Field(
        ...,
        description="The conversation messages so far including the pending tool call message.",
    )
