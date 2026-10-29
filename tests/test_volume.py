import json
import math
from pathlib import Path

import numpy as np
import pytest

from app.functions.examples import EXAMPLES_BY_SLUG
from app.volumes.mesh import TriangleMesh, extract_mesh
from app.volumes.sampling import SampledGrid, sample_function
from app.volumes.volume import estimate_volume, mesh_volume, voxel_volume
from tests.helpers import register_and_login

GOLDEN = json.loads((Path(__file__).parent / "golden" / "volumes.json").read_text())


@pytest.mark.parametrize("slug", sorted(GOLDEN))
def test_volume_matches_golden(slug):
    expected = GOLDEN[slug]
    function = EXAMPLES_BY_SLUG[slug].function

    estimate = estimate_volume(function.expression, function.domain, expected["resolution"])

    assert estimate.voxel_volume == pytest.approx(expected["voxel_volume"], rel=1e-6)
    assert estimate.mesh_volume == pytest.approx(expected["mesh_volume"], rel=1e-6)


@pytest.mark.parametrize("slug", ["esfera", "toro"])
def test_voxel_and_mesh_methods_agree(slug):
    function = EXAMPLES_BY_SLUG[slug].function

    estimate = estimate_volume(function.expression, function.domain, 64)

    assert estimate.mesh_volume == pytest.approx(estimate.voxel_volume, rel=0.02)


def test_empty_region_has_zero_volume():
    estimate = estimate_volume("x**2 + y**2 + z**2 + 1", [[-1, 1], [-1, 1], [-1, 1]], 16)

    assert estimate.voxel_volume == 0
    assert estimate.mesh_volume == 0


async def test_volume_endpoint(client):
    _, headers = await register_and_login(client, "ana")
    created = (await client.post("/functions/examples/esfera", headers=headers)).json()

    response = await client.get(f"/functions/{created['id']}/volume", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["mesh_volume"] == pytest.approx(GOLDEN["esfera"]["mesh_volume"], rel=1e-6)
    assert body["domain_volume"] == pytest.approx(27.0)


SPHERE_EXPRESSION = "(x - cx)**2 + (y - cy)**2 + z**2 - 0.25"


@pytest.mark.parametrize(
    "domain",
    [
        [[-1.5, 1.5], [-1.5, 1.5], [-1.5, 1.5]],
        [[-1.5, 1.5], [-1.0, 1.0], [-0.8, 0.8]],
        [[-0.2, 1.2], [-0.7, 0.7], [-0.6, 0.6]],
    ],
    ids=["cubo", "caja-centrada", "caja-desplazada"],
)
def test_sphere_volume_matches_analytic_value(domain):
    """Esfera de radio 0.5 y centro en (0.5, 0, 0): V = 4/3 π r³, sin importar la forma del dominio."""
    expression = SPHERE_EXPRESSION.replace("cx", "0.5").replace("cy", "0.0")
    expected = 4 / 3 * math.pi * 0.5**3

    estimate = estimate_volume(expression, domain, 64)

    assert estimate.mesh_volume == pytest.approx(expected, rel=1e-2)
    assert estimate.voxel_volume == pytest.approx(expected, rel=3e-2)


def test_mesh_volume_of_surface_cut_by_domain_boundary():
    """El gyroide cruza las caras del dominio; por simetría f(p + π) = -f(p), así que f ≤ 0 ocupa la mitad."""
    function = EXAMPLES_BY_SLUG["gyroide"].function
    expected = (2 * math.pi) ** 3 / 2

    estimate = estimate_volume(function.expression, function.domain, 64)

    assert estimate.mesh_volume == pytest.approx(expected, rel=1e-3)


def test_mesh_volume_when_whole_domain_is_inside():
    domain = [[-0.5, 0.5], [-0.5, 0.5], [-0.5, 0.5]]

    estimate = estimate_volume("x**2 + y**2 + z**2 - 1", domain, 16)

    assert estimate.mesh_volume == pytest.approx(1.0, rel=1e-6)


def test_mesh_volume_of_half_space_cut_by_domain():
    """f = x - 0.3 es lineal: la superficie es el plano x = 0.3 y la región ocupa 1.3 × 2 × 2."""
    domain = [[-1, 1], [-1, 1], [-1, 1]]

    estimate = estimate_volume("x - 0.3", domain, 16)

    assert estimate.mesh_volume == pytest.approx(5.2, rel=1e-4)


def test_voxel_volume_of_fully_inside_grid_is_the_box_volume():
    """3 muestras por eje delimitan 2 intervalos: la caja mide (2 · 0.5)³ = 1, no 3³ celdas de 0.5³."""
    grid = SampledGrid(values=-np.ones((3, 3, 3)), origin=(0.0, 0.0, 0.0), spacing=(0.5, 0.5, 0.5))

    assert voxel_volume(grid) == pytest.approx(1.0)


def test_voxel_volume_of_surface_cut_by_domain_boundary():
    function = EXAMPLES_BY_SLUG["gyroide"].function
    expected = (2 * math.pi) ** 3 / 2

    estimate = estimate_volume(function.expression, function.domain, 64)

    assert estimate.voxel_volume == pytest.approx(expected, rel=1e-3)


TETRAHEDRON_VERTICES = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
OUTWARD_FACES = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]])


def test_mesh_volume_is_signed_by_face_orientation():
    outward = TriangleMesh(vertices=TETRAHEDRON_VERTICES, faces=OUTWARD_FACES)
    inward = TriangleMesh(vertices=TETRAHEDRON_VERTICES, faces=OUTWARD_FACES[:, ::-1])

    assert mesh_volume(outward) == pytest.approx(1 / 6)
    assert mesh_volume(inward) == pytest.approx(-1 / 6)


@pytest.mark.parametrize("slug", ["esfera", "toro", "gyroide"])
def test_extracted_mesh_is_oriented_outward(slug):
    function = EXAMPLES_BY_SLUG[slug].function

    mesh = extract_mesh(sample_function(function.expression, function.domain, 32))

    assert mesh_volume(mesh) > 0
