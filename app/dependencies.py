from contextlib import asynccontextmanager
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.config import settings
from typing import AsyncGenerator
from meilisearch_python_sdk import AsyncClient, AsyncIndex
import logfire

# Configuration
DATABASE_URL = f"postgresql+asyncpg://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
MEILISEARCH_URL = f"{settings.MEILISEARCH_HOST}"


class MeilisearchManager:
    def __init__(self):
        self._client: AsyncClient | None = None

    async def init(self):
        """
        Initializes the Meilisearch async client using settings from config.
        The host is constructed using MEILISEARCH_HOST and MEILISEARCH_PORT.
        """
        if not self._client:
            # Build the host URL. Note: if your MEILISEARCH_HOST already
            # includes a scheme (http:// or https://), adjust accordingly.
            try:
                self._client = AsyncClient(MEILISEARCH_URL, settings.MEILISEARCH_KEY)
                # Optionally, check that the client is active via a health-check
                health = await self._client.health()
                logfire.info(f"Meilisearch health check: {health}")
            except Exception as e:
                logfire.error(f"Failed to initialize Meilisearch client: {e}")
                raise

    async def close(self):
        """
        Closes the Meilisearch client if applicable.
        Depending on the SDK implementation, the client may need to close its internal session.
        """
        if self._client:
            try:
                await self._client.close()
            except AttributeError:
                # If the client does not support closing, ignore this.
                pass
            self._client = None

    @property
    def client(self) -> AsyncClient:
        """
        Returns the active Meilisearch client if initialized.
        Otherwise, raises a DependencyNotInitializedError.
        """
        if not self._client:
            raise DependencyNotInitializedError(
                "Meilisearch client has not been initialized"
            )
        return self._client


class DatabaseManager:
    def __init__(self):
        self._engine = None
        self._session_maker = None

    def init(self):
        if not self._engine:
            self._engine = create_async_engine(
                DATABASE_URL,
                echo=True,
                pool_pre_ping=True,
                pool_size=20,
                max_overflow=10,
            )
            logfire.instrument_sqlalchemy(self._engine)
            self._session_maker = async_sessionmaker(
                self._engine, expire_on_commit=False, class_=AsyncSession
            )

    async def close(self):
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_maker = None

    @property
    def session_maker(self):
        if not self._session_maker:
            raise DependencyNotInitializedError("Database has not been initialized")
        return self._session_maker

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Creates and returns a new database session with automatic commit/rollback handling"""
        if not self._session_maker:
            raise DependencyNotInitializedError("Database has not been initialized")

        async with self._session_maker() as session:
            try:
                yield session
                logfire.info("Committing database session")
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                logfire.info("Closing database session")
                await session.close()


class OpenAIManager:
    def __init__(self):
        self._client = None

    def init(self):
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        logfire.instrument_openai(self._client)
        logfire.info("OpenAI client initialized")

    async def close(self):
        if self._client:
            self._client = None

    async def get_client(self):
        if not self._client:
            raise DependencyNotInitializedError(
                "OpenAI client has not been initialized"
            )
        return self._client

    @property
    def client(self):
        if not self._client:
            raise DependencyNotInitializedError(
                "OpenAI client has not been initialized"
            )
        return self._client


# Create singleton instances
db_manager = DatabaseManager()
meilisearch_manager = MeilisearchManager()
openai_manager = OpenAIManager()


class DependencyNotInitializedError(Exception):
    """Raised when a dependency is accessed before initialization"""

    pass


async def get_openai() -> AsyncGenerator[AsyncOpenAI, None]:
    client = await openai_manager.get_client()
    try:
        yield client
    finally:
        pass


# Dependency functions
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with db_manager.session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            logfire.info("Closing database session")
            await session.close()


async def get_meilisearch_client() -> AsyncGenerator[AsyncIndex, None]:
    """
    Dependency injection function to return the active Meilisearch async client.
    This function can be used with FastAPI's dependency injection to inject the client.
    """
    try:
        return meilisearch_manager.client.index("tools")
    except Exception as e:
        logfire.error(f"Error accessing meilisearch client: {e}")
        raise
