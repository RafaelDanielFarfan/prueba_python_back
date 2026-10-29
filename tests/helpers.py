import os

import pytest
from httpx import AsyncClient

from app.core.config import Settings


async def register_and_login(client: AsyncClient, username: str) -> tuple[int, dict[str, str]]:
    response = await client.post(
        "/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": "s3cret-pass"},
    )
    user_id = response.json()["id"]
    token_response = await client.post(
        "/auth/token", data={"username": username, "password": "s3cret-pass"}
    )
    return user_id, {"Authorization": f"Bearer {token_response.json()['access_token']}"}


def settings_from_env(monkeypatch: pytest.MonkeyPatch, **environment: str) -> Settings:
    """Settings leída solo de las variables de entorno indicadas, sin el .env local ni otras APP_*."""
    for name in [name for name in os.environ if name.startswith("APP_")]:
        monkeypatch.delenv(name)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    return Settings(_env_file=None, database_url="postgresql+asyncpg://u:p@localhost/db", secret_key="clave")
