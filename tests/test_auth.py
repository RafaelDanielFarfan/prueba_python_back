from app.core.security import decode_access_token

USER = {"username": "ana", "email": "ana@example.com", "password": "s3cret-pass"}


async def register(client, **overrides):
    return await client.post("/auth/register", json={**USER, **overrides})


async def test_register_returns_user_without_password(client):
    response = await register(client)

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "ana"
    assert "password" not in body
    assert "hashed_password" not in body


async def test_register_rejects_duplicated_username(client):
    await register(client)

    response = await register(client, email="otra@example.com")

    assert response.status_code == 409


async def test_register_conflict_when_duplicate_slips_past_existence_check(client, monkeypatch):
    """Dos registros simultáneos pueden pasar ambos la consulta previa; el índice único decide."""
    await register(client)

    async def never_exists(*_args, **_kwargs):
        return False

    monkeypatch.setattr("app.users.service.exists_user", never_exists)

    response = await register(client)

    assert response.status_code == 409


async def test_register_validates_password_length(client):
    response = await register(client, password="corta")

    assert response.status_code == 422


async def test_login_returns_valid_token(client):
    await register(client)

    response = await client.post("/auth/token", data={"username": "ana", "password": "s3cret-pass"})

    assert response.status_code == 200
    assert decode_access_token(response.json()["access_token"]) == "ana"


async def test_login_rejects_wrong_password(client):
    await register(client)

    response = await client.post("/auth/token", data={"username": "ana", "password": "incorrecta"})

    assert response.status_code == 401
