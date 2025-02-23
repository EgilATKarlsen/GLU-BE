from datetime import datetime
import uuid
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    PREMIUM = "premium"
    USER = "user"


class IntegrationCategory(str, Enum):
    CODE = "CODE"
    TICKETS = "TICKETS"
    EMAIL = "EMAIL"
    STORAGE = "STORAGE"
    CALENDAR = "CALENDAR"
    MEDIA = "MEDIA"
    COMMUNICATION = "COMMUNICATION"


class AuthType(str, Enum):
    API_KEY = "API_KEY"
    OAUTH = "OAUTH"
    BEARER = "BEARER"
    NONE = "NONE"


class BaseSchema(BaseModel):
    created_at: datetime
    updated_at: datetime
    deleted: bool = False


class UserBase(BaseModel):
    name: str
    email: str
    role: UserRole = UserRole.USER


class UserCreate(UserBase):
    pass


class User(UserBase, BaseSchema):
    id: str

    class Config:
        from_attributes = True


class IntegrationBase(BaseModel):
    name: str
    clerk_name: str
    base_host: str
    description: str
    keywords: str
    category: IntegrationCategory
    logo: str
    version: str
    schema: str
    auth_type: AuthType = AuthType.NONE
    spec: str


class IntegrationCreate(IntegrationBase):
    pass


class Integration(IntegrationBase, BaseSchema):
    id: uuid.UUID

    class Config:
        from_attributes = True


class UserIntegrationBase(BaseModel):
    integration_id: uuid.UUID
    clerk_id: str
    user_id: str


class UserIntegrationCreate(UserIntegrationBase):
    pass


class UserIntegration(UserIntegrationBase, BaseSchema):
    id: uuid.UUID

    class Config:
        from_attributes = True


class MessageBase(BaseModel):
    user_id: str
    integration_id: Optional[uuid.UUID] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    latency: Optional[float] = None
    initial_input: str
    result: Optional[dict] = None


class MessageCreate(MessageBase):
    pass


class Message(MessageBase, BaseSchema):
    id: uuid.UUID

    class Config:
        from_attributes = True
