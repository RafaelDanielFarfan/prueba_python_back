from dataclasses import dataclass

import numpy as np

from app.functions.parser import FloatArray
from app.volumes.mesh import TriangleMesh, extract_mesh
from app.volumes.sampling import SampledGrid, sample_function


@dataclass(frozen=True)
class VolumeEstimate:
    voxel_volume: float
    mesh_volume: float
    domain_volume: float


def _trapezoid_weights(samples: int) -> FloatArray:
    """Peso de cada muestra de un eje: las de los extremos solo representan media celda."""
    weights = np.ones(samples)
    weights[[0, -1]] = 0.5
    return weights


def voxel_volume(grid: SampledGrid) -> float:
    """Cuenta las muestras con f ≤ 0 ponderadas por la fracción de celda que representan.

    El peso de una muestra es el producto de los pesos de sus tres ejes: 1 en el interior,
    1/2 en las caras, 1/4 en las aristas y 1/8 en los vértices. Sin esa ponderación, una región
    que toca el borde del dominio se sobrestima.
    """
    inside = grid.values <= 0
    weights = (_trapezoid_weights(n) for n in grid.shape)
    weighted_count = np.einsum("ijk,i,j,k->", inside.astype(np.float64), *weights)
    return float(weighted_count) * float(np.prod(grid.spacing))


def mesh_volume(mesh: TriangleMesh) -> float:
    """Volumen encerrado por una malla cerrada (teorema de la divergencia, tetraedros con el origen).

    Es positivo si las caras apuntan hacia fuera. Un valor negativo indica una malla mal orientada,
    por eso no se oculta con un valor absoluto.
    """
    if mesh.is_empty:
        return 0.0
    v0, v1, v2 = (mesh.vertices[mesh.faces[:, i]] for i in range(3))
    return float(np.einsum("ij,ij->i", v0, np.cross(v1, v2)).sum() / 6.0)


def domain_volume(domain: list[list[float]]) -> float:
    return float(np.prod([upper - lower for lower, upper in domain]))


def estimate_volume(expression: str, domain: list[list[float]], resolution: int) -> VolumeEstimate:
    grid = sample_function(expression, domain, resolution)
    return VolumeEstimate(
        voxel_volume=voxel_volume(grid),
        mesh_volume=mesh_volume(extract_mesh(grid)),
        domain_volume=domain_volume(domain),
    )
