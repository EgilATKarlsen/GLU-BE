from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from contextlib import asynccontextmanager
from app.config import settings
from app.client.logger import logger

DATABASE_URL = f"postgresql+asyncpg://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"


class DatabaseClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._engine = create_async_engine(
            DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
        self._async_sessionmaker = async_sessionmaker(
            self._engine, expire_on_commit=True, class_=AsyncSession
        )
        self._initialized = True
        logger.info("Database Client initialized")

    @asynccontextmanager
    async def get_session(self):
        session = self._async_sessionmaker()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise e
        finally:
            await session.close()

    async def cleanup(self):
        await self._engine.dispose()
        logger.info("Database Client cleaned up")
