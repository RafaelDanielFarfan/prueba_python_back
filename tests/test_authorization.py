import pytest

from tests.helpers import register_and_login

SPHERE = {
    "name": "Esfera",
    "expression": "x**2 + y**2 + z**2 - 1",
    "domain": [[-1.5, 1.5], [-1.5, 1.5], [-1.5, 1.5]],
    "resolution": 16,
}


@pytest.fixture
async def ana_function_and_bob_headers(client):
    """Una función de ana y las credenciales de bob, que no es su dueño."""
    _, ana_headers = await register_and_login(client, "ana")
    _, bob_headers = await register_and_login(client, "bob")
    created = await client.post("/functions", json=SPHERE, headers=ana_headers)
    return created.json()["id"], ana_headers, bob_headers


@pytest.mark.parametrize(
    "path",
    ["", "/evaluate?x=0&y=0&z=0", "/volume", "/mesh.bin"],
    ids=["detalle", "evaluar", "volumen", "malla"],
)
async def test_other_user_cannot_read_function(client, ana_function_and_bob_headers, path):
    function_id, ana_headers, bob_headers = ana_function_and_bob_headers
    url = f"/functions/{function_id}{path}"

    response = await client.get(url, headers=bob_headers)

    assert response.status_code == 404
    assert (await client.get(url, headers=ana_headers)).status_code == 200


async def test_other_user_cannot_edit_function(client, ana_function_and_bob_headers):
    function_id, ana_headers, bob_headers = ana_function_and_bob_headers

    response = await client.patch(f"/functions/{function_id}", json={"name": "Robada"}, headers=bob_headers)

    assert response.status_code == 404
    original = await client.get(f"/functions/{function_id}", headers=ana_headers)
    assert original.json()["name"] == "Esfera"
    assert original.json()["version"] == 1


async def test_unauthenticated_request_is_rejected(client, ana_function_and_bob_headers):
    function_id, _, _ = ana_function_and_bob_headers

    response = await client.get(f"/functions/{function_id}")

    assert response.status_code == 401
