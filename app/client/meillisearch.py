from meilisearch_python_sdk import AsyncClient
from app.config import settings
from app.client.logger import logger


class DependencyNotInitializedError(Exception):
    """Raised when a dependency is accessed before initialization."""

    pass


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
            host = settings.MEILISEARCH_HOST
            try:
                self._client = AsyncClient(host, settings.MEILISEARCH_KEY)
                # Optionally, check that the client is active via a health-check
                health = await self._client.health()
                logger.info("Meilisearch health check: %s", health)
            except Exception as e:
                logger.error("Failed to initialize Meilisearch client: %s", e)
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


# Create a singleton instance of MeilisearchManager
meilisearch_manager = MeilisearchManager()


async def get_meilisearch_client() -> AsyncClient:
    """
    Dependency injection function to return the active Meilisearch async client.
    This function can be used with FastAPI's dependency injection to inject the client.
    """
    try:
        return meilisearch_manager.client.index("tools")
    except DependencyNotInitializedError as e:
        logger.error("Meilisearch client is not initialized: %s", e)
        raise
