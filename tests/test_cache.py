import math

import pytest

from app.volumes.cache import ResultCache
from tests.helpers import register_and_login

UNIT_SPHERE = {
    "name": "Esfera",
    "expression": "x**2 + y**2 + z**2 - 1",
    "domain": [[-1.5, 1.5], [-1.5, 1.5], [-1.5, 1.5]],
    "resolution": 32,
}


def test_cache_computes_once_per_key():
    cache: ResultCache[int] = ResultCache(max_items=2)
    calls: list[int] = []

    def compute() -> int:
        calls.append(1)
        return 42

    assert cache.get_or_compute(1, compute) == 42
    assert cache.get_or_compute(1, compute) == 42
    assert len(calls) == 1


def test_cache_evicts_least_recently_used():
    cache: ResultCache[int] = ResultCache(max_items=2)
    cache.get_or_compute(1, lambda: 1)
    cache.get_or_compute(2, lambda: 2)
    cache.get_or_compute(1, lambda: 1)
    cache.get_or_compute(3, lambda: 3)

    assert len(cache) == 2
    assert cache.get_or_compute(2, lambda: -2) == -2


def test_invalidate_forces_recompute():
    cache: ResultCache[int] = ResultCache(max_items=2)
    cache.get_or_compute(1, lambda: 1)

    cache.invalidate(1)

    assert cache.get_or_compute(1, lambda: 10) == 10


@pytest.mark.parametrize(
    "change, expected_volume",
    [
        ({"expression": "x**2 + y**2 + z**2 - 0.25"}, 4 / 3 * math.pi * 0.5**3),
        ({"domain": [[-0.5, 0.5], [-0.5, 0.5], [-0.5, 0.5]]}, 1.0),
    ],
    ids=["expresion", "dominio"],
)
async def test_volume_reflects_function_edits(client, change, expected_volume):
    _, headers = await register_and_login(client, "ana")
    created = (await client.post("/functions", json=UNIT_SPHERE, headers=headers)).json()
    url = f"/functions/{created['id']}"
    assert (await client.get(f"{url}/volume", headers=headers)).json()["mesh_volume"] == pytest.approx(
        4 / 3 * math.pi, rel=1e-2
    )

    await client.patch(url, json=change, headers=headers)
    response = await client.get(f"{url}/volume", headers=headers)

    assert response.json()["mesh_volume"] == pytest.approx(expected_volume, rel=5e-2)


async def test_mesh_reflects_function_edits(client):
    _, headers = await register_and_login(client, "ana")
    created = (await client.post("/functions", json=UNIT_SPHERE, headers=headers)).json()
    url = f"/functions/{created['id']}"
    before = (await client.get(f"{url}/mesh.bin", headers=headers)).content

    await client.patch(url, json={"expression": "x**2 + y**2 + z**2 - 0.25"}, headers=headers)
    after = (await client.get(f"{url}/mesh.bin", headers=headers)).content

    assert after != before


async def test_volume_reflects_resolution_edit(client):
    _, headers = await register_and_login(client, "ana")
    created = (await client.post("/functions", json=UNIT_SPHERE, headers=headers)).json()
    url = f"/functions/{created['id']}"
    await client.get(f"{url}/volume", headers=headers)

    await client.patch(url, json={"resolution": 64}, headers=headers)
    response = await client.get(f"{url}/volume", headers=headers)

    assert response.json()["resolution"] == 64
    assert response.json()["mesh_volume"] == pytest.approx(4 / 3 * math.pi, rel=3e-3)
