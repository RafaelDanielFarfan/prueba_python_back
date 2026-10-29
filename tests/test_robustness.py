import math

import pytest

from app.volumes.volume import estimate_volume
from tests.helpers import register_and_login

CUBE = [[-1, 1], [-1, 1], [-1, 1]]


def test_undefined_samples_count_as_outside_the_region():
    """sqrt(x) no existe para x < 0: f ≤ 0 solo en 0 ≤ x ≤ 0.25, que mide 0.25 · 2 · 2 = 1."""
    estimate = estimate_volume("sqrt(x) - 0.5", CUBE, 64)

    assert math.isfinite(estimate.mesh_volume)
    assert estimate.mesh_volume == pytest.approx(1.0, abs=0.2)
    assert estimate.voxel_volume == pytest.approx(1.0, abs=0.2)


@pytest.mark.parametrize("expression", ["log(x) - 1", "sqrt(x) - 0.5", "1/(x*y*z) - 1", "exp(1000*x) - 1"])
async def test_volume_endpoint_returns_finite_numbers(client, expression):
    _, headers = await register_and_login(client, "ana")
    payload = {"name": "Parcial", "expression": expression, "domain": CUBE, "resolution": 32}
    created = (await client.post("/functions", json=payload, headers=headers)).json()

    response = await client.get(f"/functions/{created['id']}/volume", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert all(math.isfinite(body[key]) for key in ("mesh_volume", "voxel_volume", "domain_volume"))


@pytest.mark.parametrize(
    "expression, point",
    [
        ("1/x", (0, 0, 0)),
        ("x**2", (1e200, 0, 0)),
        ("sqrt(x)", (-1, 0, 0)),
        ("log(x)", (0, 0, 0)),
        ("exp(x)", (1000, 0, 0)),
    ],
    ids=["division-por-cero", "desbordamiento", "raiz-negativa", "log-de-cero", "exp-enorme"],
)
async def test_evaluate_rejects_non_finite_values_with_422(client, expression, point):
    _, headers = await register_and_login(client, "ana")
    payload = {"name": "Singular", "expression": expression, "domain": CUBE, "resolution": 16}
    created = (await client.post("/functions", json=payload, headers=headers)).json()
    x, y, z = point

    response = await client.get(
        f"/functions/{created['id']}/evaluate", params={"x": x, "y": y, "z": z}, headers=headers
    )

    assert response.status_code == 422
    assert "finito" in response.json()["detail"]
