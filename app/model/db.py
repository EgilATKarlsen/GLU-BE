from datetime import datetime, timezone
import uuid
from typing import Optional, List
from sqlalchemy import (
    String,
    Boolean,
    Float,
    JSON,
    Text,
    ForeignKey,
    Enum,
    Integer,
    event,
    select,
    func,
    DateTime,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from enum import Enum as PyEnum


class Base(DeclarativeBase):
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now(tz=timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now(tz=timezone.utc),
        onupdate=datetime.now(tz=timezone.utc),
    )
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    def delete(self):
        self.deleted = True


class UserRole(str, PyEnum):
    admin = "admin"
    premium = "premium"
    user = "user"


class IntegrationCategory(str, PyEnum):
    code = "code"
    tickets = "tickets"
    email = "email"
    storage = "storage"
    calendar = "calendar"
    media = "media"
    communication = "communication"


class AuthType(str, PyEnum):
    api_key = "api_key"
    oauth = "oauth"
    bearer = "bearer"
    none = "none"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String)
    role: Mapped[UserRole] = mapped_column(String, default=UserRole.user)

    integrations: Mapped[List["UserIntegration"]] = relationship(back_populates="user")
    messages: Mapped[List["Message"]] = relationship(back_populates="user")


class Integration(Base):
    __tablename__ = "integrations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String)
    clerk_name: Mapped[str] = mapped_column(String)
    base_host: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    keywords: Mapped[str] = mapped_column(String)
    category: Mapped[IntegrationCategory] = mapped_column(String)
    logo: Mapped[str] = mapped_column(String)  # S3 bucket address
    version: Mapped[str] = mapped_column(String)
    schema: Mapped[str] = mapped_column(String)  # S3 bucket address
    auth_type: Mapped[AuthType] = mapped_column(
        String,
        default=AuthType.none,
    )
    spec: Mapped[str] = mapped_column(String)  # S3 bucket address

    user_integrations: Mapped[List["UserIntegration"]] = relationship(
        back_populates="integration"
    )


class UserIntegration(Base):
    __tablename__ = "user_integrations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("integrations.id")
    )
    clerk_id: Mapped[str] = mapped_column(String)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))

    integration: Mapped["Integration"] = relationship(
        back_populates="user_integrations"
    )
    user: Mapped["User"] = relationship(back_populates="integrations")
    messages: Mapped[List["Message"]] = relationship(back_populates="integration")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    integration_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_integrations.id"), nullable=True
    )  # TODO: Starting integration list @ feature
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now(tz=timezone.utc)
    )
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    latency: Mapped[float] = mapped_column(Float, nullable=True)
    initial_input: Mapped[str] = mapped_column(Text)
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    user: Mapped["User"] = relationship(back_populates="messages")
    integration: Mapped[Optional["UserIntegration"]] = relationship(
        back_populates="messages"
    )


async def populate_sample_integrations(session) -> bool:
    sample_integrations = [
        {
            "name": "slack",
            "clerk_name": "slack",
            "base_host": "https://slack.com/api",
            "description": "Team communication and collaboration platform",
            "keywords": "chat,messaging,team,collaboration",
            "category": IntegrationCategory.communication,
            "logo": "https://your-s3-bucket/logos/slack.png",
            "version": "1.0",
            "schema": "https://your-s3-bucket/schemas/slack.json",
            "auth_type": AuthType.oauth,
            "spec": "https://your-s3-bucket/specs/slack.json",
        },
        {
            "name": "spotify",
            "clerk_name": "spotify",
            "base_host": "https://api.spotify.com/v1",
            "description": "Music streaming service",
            "keywords": "music,streaming,audio,playlist",
            "category": IntegrationCategory.media,
            "logo": "https://your-s3-bucket/logos/spotify.png",
            "version": "1.0",
            "schema": "https://your-s3-bucket/schemas/spotify.json",
            "auth_type": AuthType.oauth,
            "spec": "https://your-s3-bucket/specs/spotify.json",
        },
        {
            "name": "todoist",
            "clerk_name": "custom_todoist",
            "base_host": "https://api.todoist.com/rest/v2",
            "description": "Task management and organization tool",
            "keywords": "tasks,todo,productivity,organization",
            "category": IntegrationCategory.tickets,
            "logo": "https://your-s3-bucket/logos/todoist.png",
            "version": "1.0",
            "schema": "https://your-s3-bucket/schemas/todoist.json",
            "auth_type": AuthType.bearer,
            "spec": "https://your-s3-bucket/specs/todoist.json",
        },
    ]

    for integration_data in sample_integrations:
        # Create new integration
        integration = Integration(**integration_data)
        session.add(integration)
        await session.flush()

    return True
