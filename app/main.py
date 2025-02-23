import logging
import os
import json
import sys
import uuid
from contextlib import asynccontextmanager
import asyncio
import logfire

from fastapi import FastAPI, Depends
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel

from app.config import settings
from app.route.router import api_router

from app.dependencies import (
    get_db,
    db_manager,
    meilisearch_manager,
    openai_manager,
)
from app.model.db import Base, populate_sample_integrations
from app.types.response import HealthCheckResponse

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting FastAPI application")

    # Initialize database
    try:
        db_manager.init()
        # Create database tables if they don't exist
        async with db_manager._engine.begin() as conn:
            logger.info("Creating database tables...")
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")

        # Populate sample integrations with more detailed logging
        async with db_manager.get_session() as session:
            # Check if integrations already exist
            result = await session.execute(text("SELECT COUNT(*) FROM integrations"))
            count = result.scalar()
            logger.info(f"Current integration count: {count}")

            if count == 0:
                logger.info("No existing integrations found, populating samples...")
                await populate_sample_integrations(session)
                logger.info("Sample integrations populated successfully")
            else:
                logger.info(f"Skipping population - {count} integrations already exist")

        logger.info("Database initialization complete")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)

    try:
        openai_manager.init()
        logger.info("OpenAI client connected successfully")
    except Exception as e:
        logger.error(f"Failed to connect to OpenAI: {e}")
        sys.exit(1)

    # Save OpenAPI spec for use in frontend/zodios client
    try:
        openapi_schema = app.openapi()
        spec_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "api-spec")
        os.makedirs(spec_dir, exist_ok=True)

        spec_path = os.path.join(spec_dir, "openapi.json")
        with open(spec_path, "w") as f:
            json.dump(openapi_schema, f, indent=2)
        logger.info(f"OpenAPI specification saved to {spec_path}")
    except Exception as e:
        logger.error(f"Failed to save OpenAPI spec: {e}")

    try:
        await meilisearch_manager.init()
        logger.info("Meilisearch client connected successfully")
    except Exception as e:
        logger.error(f"Failed to connect to Meilisearch: {e}")

    yield

    # Cleanup on shutdown
    logger.info("Shutting down FastAPI application")
    try:
        await db_manager.close()
        logger.info("Database connections closed")

        await meilisearch_manager.close()
        logger.info("Meilisearch connections closed")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_STR}/openapi.json",
    lifespan=lifespan,
)

logfire.configure(
    token=settings.LOGFIRE_TOKEN,
    service_name="glu-server",
    environment=settings.LOGFIRE_ENVIRONMENT,
)
logfire.instrument_fastapi(app)
logfire.instrument_httpx()


# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            str(origin).strip("/") for origin in settings.BACKEND_CORS_ORIGINS
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_STR)


@app.get("/", tags=["root"], response_model=HealthCheckResponse)
async def root(
    db: AsyncSession = Depends(get_db),
) -> HealthCheckResponse:
    status = {
        "database": {
            "connected": False,
            "info": None,
            "async_": False,
        },
        "message": "LifeBloom API Health Check",
    }

    try:
        # Test async database connection with timeout
        async with asyncio.timeout(2.0):
            result = await db.execute(text("SELECT version()"))
            status["database"]["connected"] = True
            status["database"]["async_"] = True
            status["database"]["info"] = (result.scalar()).__str__()
    except Exception as e:
        logger.error(f"Database connection failed: {e}")

    status["healthy"] = all(
        status[service]["connected"] and status[service]["async_"]
        for service in ["database", "redis"]
    )
    return HealthCheckResponse(**status)
