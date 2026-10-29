"""Formato binario de mallas consumido por el visor.

Little-endian. Cabecera seguida de dos bloques contiguos:

    magic       4s   b"IMSH"
    version     u16
    flags       u16  reservado
    n_vertices  u32
    n_faces     u32
    origin      3 x f64   origen local de la malla (coordenadas de mundo)
    vertices    n_vertices x 3 x f32   relativos a ``origin``
    faces       n_faces x 3 x u32      índices de vértices

Los vértices se envían relativos a ``origin`` para conservar precisión en float32 aunque el
dominio esté lejos del origen de coordenadas. El propio ``origin`` va en float64: en float32 una
coordenada como 600000 solo distingue pasos de 0.06.
"""

import struct

import numpy as np

from app.volumes.mesh import TriangleMesh

MAGIC = b"IMSH"
VERSION = 3
HEADER = struct.Struct("<4sHHII3d")
VERTEX_DTYPE = np.dtype("<f4")
FACE_DTYPE = np.dtype("<u4")


def encode_mesh(mesh: TriangleMesh) -> bytes:
    origin = mesh.vertices.min(axis=0) if not mesh.is_empty else np.zeros(3)
    relative = (mesh.vertices - origin).astype(VERTEX_DTYPE)
    faces = mesh.faces.astype(FACE_DTYPE)

    header = HEADER.pack(MAGIC, VERSION, 0, len(relative), len(faces), *origin)
    return header + relative.tobytes() + faces.tobytes()


def decode_mesh(payload: bytes) -> TriangleMesh:
    magic, version, _, n_vertices, n_faces, *origin = HEADER.unpack_from(payload)
    if magic != MAGIC or version != VERSION:
        raise ValueError("Formato de malla no soportado")

    offset = HEADER.size
    vertices = np.frombuffer(payload, VERTEX_DTYPE, n_vertices * 3, offset).reshape(-1, 3)
    offset += vertices.nbytes
    faces = np.frombuffer(payload, FACE_DTYPE, n_faces * 3, offset).reshape(-1, 3)

    return TriangleMesh(
        vertices=vertices.astype(np.float64) + np.asarray(origin),
        faces=faces.astype(np.int64),
    )
