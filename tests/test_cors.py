from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.middleware.cors import CORSMiddleware

from app.main import app as application
from tests.helpers import settings_from_env

FRONT = "http://localhost:5173"


def build_app(origins: list[str]) -> FastAPI:
    from app.core.cors import add_cors

    test_app = FastAPI()
    add_cors(test_app, origins)

    @test_app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    return test_app


def client_for(test_app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test")


def test_no_origins_are_allowed_by_default(monkeypatch):
    assert settings_from_env(monkeypatch).cors_origin_list == []


def test_origins_are_read_from_a_comma_separated_variable(monkeypatch):
    settings = settings_from_env(monkeypatch, APP_CORS_ORIGINS=f"{FRONT}, http://127.0.0.1:5173 ,")

    assert settings.cors_origin_list == [FRONT, "http://127.0.0.1:5173"]


def test_application_registers_the_cors_middleware():
    assert CORSMiddleware in [middleware.cls for middleware in application.user_middleware]


async def test_preflight_from_an_allowed_origin_is_accepted():
    async with client_for(build_app([FRONT])) as client:
        response = await client.options(
            "/ping",
            headers={
                "Origin": FRONT,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == FRONT
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


async def test_preflight_from_another_origin_is_rejected():
    async with client_for(build_app([FRONT])) as client:
        response = await client.options(
            "/ping", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"}
        )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


async def test_response_to_an_allowed_origin_carries_the_cors_header():
    async with client_for(build_app([FRONT])) as client:
        response = await client.get("/ping", headers={"Origin": FRONT})

    assert response.headers["access-control-allow-origin"] == FRONT


async def test_response_without_configured_origins_has_no_cors_header():
    async with client_for(build_app([])) as client:
        response = await client.get("/ping", headers={"Origin": FRONT})

    assert "access-control-allow-origin" not in response.headers
