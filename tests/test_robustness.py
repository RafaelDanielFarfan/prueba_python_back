import asyncio
import math
import time
import tracemalloc

import pytest

from app.core.config import Settings, get_settings
from app.volumes import router as volumes_router
from app.volumes.sampling import sample_function
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


async def longest_event_loop_stall(until: asyncio.Task) -> float:
    """Mayor intervalo entre dos pulsos del event loop mientras ``until`` no termina."""
    longest, last = 0.0, time.perf_counter()
    while not until.done():
        await asyncio.sleep(0.01)
        now = time.perf_counter()
        longest, last = max(longest, now - last), now
    return longest


@pytest.mark.parametrize(
    "path, slowed",
    [("volume", "estimate_volume"), ("mesh.bin", "sample_function")],
    ids=["volumen", "malla"],
)
async def test_heavy_computation_does_not_block_the_event_loop(client, monkeypatch, path, slowed):
    original = getattr(volumes_router, slowed)

    def slow(*args, **kwargs):
        time.sleep(0.5)
        return original(*args, **kwargs)

    monkeypatch.setattr(volumes_router, slowed, slow)
    _, headers = await register_and_login(client, "ana")
    payload = {"name": "Esfera", "expression": "x**2 + y**2 + z**2 - 1", "domain": CUBE, "resolution": 16}
    created = (await client.post("/functions", json=payload, headers=headers)).json()

    request = asyncio.create_task(client.get(f"/functions/{created['id']}/{path}", headers=headers))
    stall = await longest_event_loop_stall(request)

    assert (await request).status_code == 200
    assert stall < 0.25


def settings_from(monkeypatch, **environment: str) -> Settings:
    """Settings leída solo de variables de entorno, sin el .env local."""
    for name in ("APP_MAX_RESOLUTION", "APP_MAX_CONCURRENT_COMPUTATIONS"):
        monkeypatch.delenv(name, raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    return Settings(_env_file=None, database_url="postgresql+asyncpg://u:p@localhost/db", secret_key="clave")


def test_default_limits_keep_memory_bounded(monkeypatch):
    """Una rejilla de 2048³ muestras ocupa unos 69 GB; el límite por defecto debe ser razonable."""
    settings = settings_from(monkeypatch)

    assert settings.max_resolution == 256
    assert settings.max_concurrent_computations == 2


def test_limits_are_read_from_environment(monkeypatch):
    settings = settings_from(monkeypatch, APP_MAX_RESOLUTION="64", APP_MAX_CONCURRENT_COMPUTATIONS="1")

    assert settings.max_resolution == 64
    assert settings.max_concurrent_computations == 1


async def test_resolution_above_the_configured_limit_is_rejected(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_resolution", 64)
    _, headers = await register_and_login(client, "ana")
    payload = {"name": "Esfera", "expression": "x**2 + y**2 + z**2 - 1", "domain": CUBE}

    accepted = await client.post("/functions", json={**payload, "resolution": 64}, headers=headers)
    rejected = await client.post("/functions", json={**payload, "resolution": 65}, headers=headers)

    assert accepted.status_code == 201
    assert rejected.status_code == 422


def test_sampling_does_not_materialize_three_full_grids():
    tracemalloc.start()
    grid = sample_function("x**2 + y**2 + z**2 - 1", CUBE, 64)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert peak < 3 * grid.values.nbytes


async def test_busy_server_answers_503_with_retry_after(client, monkeypatch):
    from app.volumes.limiter import ComputeLimiter

    original = volumes_router.estimate_volume

    def slow(*args, **kwargs):
        time.sleep(0.5)
        return original(*args, **kwargs)

    monkeypatch.setattr(volumes_router, "estimate_volume", slow)
    monkeypatch.setattr(volumes_router, "compute_limiter", ComputeLimiter(1))
    _, headers = await register_and_login(client, "ana")
    payload = {"name": "Esfera", "expression": "x**2 + y**2 + z**2 - 1", "domain": CUBE, "resolution": 16}
    first, second = [(await client.post("/functions", json=payload, headers=headers)).json()["id"] for _ in range(2)]

    running = asyncio.create_task(client.get(f"/functions/{first}/volume", headers=headers))
    await asyncio.sleep(0.2)
    busy = await client.get(f"/functions/{second}/volume", headers=headers)

    assert busy.status_code == 503
    assert "Retry-After" in busy.headers
    assert (await running).status_code == 200
    assert (await client.get(f"/functions/{second}/volume", headers=headers)).status_code == 200
