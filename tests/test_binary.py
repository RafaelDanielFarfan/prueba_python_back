import numpy as np
import pytest

from app.volumes.binary import HEADER, MAGIC, decode_mesh, encode_mesh
from app.volumes.mesh import TriangleMesh, extract_mesh
from app.volumes.sampling import sample_function
from tests.helpers import register_and_login


def sphere_mesh() -> TriangleMesh:
    grid = sample_function("x**2 + y**2 + z**2 - 1", [[-1.5, 1.5]] * 3, 32)
    return extract_mesh(grid)


def test_roundtrip_preserves_mesh():
    mesh = sphere_mesh()

    decoded = decode_mesh(encode_mesh(mesh))

    np.testing.assert_allclose(decoded.vertices, mesh.vertices, atol=1e-5)
    np.testing.assert_array_equal(decoded.faces, mesh.faces)


def test_payload_size_matches_header():
    mesh = sphere_mesh()

    payload = encode_mesh(mesh)

    expected = HEADER.size + mesh.vertices.size * 4 + mesh.faces.size * 2
    assert len(payload) == expected
    assert payload[:4] == MAGIC


def test_empty_mesh_is_encoded():
    empty = TriangleMesh(vertices=np.empty((0, 3)), faces=np.empty((0, 3), dtype=np.int64))

    decoded = decode_mesh(encode_mesh(empty))

    assert decoded.is_empty


def test_decode_rejects_unknown_magic():
    payload = b"XXXX" + encode_mesh(sphere_mesh())[4:]

    with pytest.raises(ValueError):
        decode_mesh(payload)


async def test_mesh_endpoint_returns_binary(client):
    _, headers = await register_and_login(client, "ana")
    created = (await client.post("/functions/examples/esfera", headers=headers)).json()

    response = await client.get(f"/functions/{created['id']}/mesh.bin", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert not decode_mesh(response.content).is_empty


def test_roundtrip_preserves_face_indices_beyond_uint16():
    vertices = np.zeros((70_000, 3))
    mesh = TriangleMesh(vertices=vertices, faces=np.array([[0, 65_536, 69_999]]))

    decoded = decode_mesh(encode_mesh(mesh))

    np.testing.assert_array_equal(decoded.faces, mesh.faces)


def test_roundtrip_far_from_origin_keeps_world_coordinates():
    center = 600_000.1234
    grid = sample_function(f"(x - {center})**2 + y**2 + z**2 - 0.25", [[center - 1, center + 1], [-1, 1], [-1, 1]], 32)
    mesh = extract_mesh(grid)

    decoded = decode_mesh(encode_mesh(mesh))

    np.testing.assert_allclose(decoded.vertices, mesh.vertices, rtol=0, atol=1e-6)
