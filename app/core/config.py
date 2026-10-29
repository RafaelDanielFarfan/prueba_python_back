from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    name: str = "Implicit Volumes API"
    environment: str = "development"
    log_level: str = "INFO"
    log_json: bool = True

    database_url: str
    test_database_url: str | None = None
    database_echo: bool = False

    secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    default_resolution: int = 64
    min_resolution: int = 8
    max_resolution: int = 256
    max_expression_length: int = 500
    max_concurrent_computations: int = Field(default=2, ge=1)

    cache_max_items: int = 128

    cors_origins: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        """Orígenes permitidos, a partir de ``APP_CORS_ORIGINS`` separados por comas."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
