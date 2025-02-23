from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    PROJECT_NAME: str = "glu-server"
    BASE_PATH: str = "./tool_lists/tool_list"
    API_STR: str = "/api"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    OPENAI_API_KEY: str
    DB_SSL_MODE: str = "require"
    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"
    DB_NAME: str = "glucx"
    CLERK_SECRET_KEY: str
    MEILISEARCH_HOST: str
    MEILISEARCH_PORT: str = "7700"
    MEILISEARCH_KEY: str
    BACKEND_CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
        ]
    )
    LOGFIRE_TOKEN: str
    LOGFIRE_ENVIRONMENT: str

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )


settings = Settings()
