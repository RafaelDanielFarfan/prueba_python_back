from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from skimage.measure import marching_cubes

from app.functions.parser import FloatArray
from app.volumes.sampling import SampledGrid

ISO_LEVEL = 0.0
OUTSIDE_FACTOR = 1e6


@dataclass(frozen=True)
class TriangleMesh:
    vertices: FloatArray
    faces: NDArray[np.int64]

    @property
    def is_empty(self) -> bool:
        return len(self.faces) == 0


def _close_at_boundary(values: FloatArray) -> FloatArray:
    """Rodea la rejilla con una capa exterior para que la superficie se cierre en las caras del dominio.

    La capa vale mucho más que cualquier muestra: así el cruce f = 0 entre un punto del borde (f ≤ 0) y
    la capa cae casi sobre la cara del dominio, y el corte queda donde corresponde. Con un valor
    moderado el cruce se desplazaría hacia dentro y deformaría la superficie cerca del borde.
    """
    finite = values[np.isfinite(values)]
    scale = max(float(np.abs(finite).max()), 1.0) if finite.size else 1.0
    return np.pad(values, 1, constant_values=OUTSIDE_FACTOR * scale)


def extract_mesh(grid: SampledGrid) -> TriangleMesh:
    """Extrae la superficie f = 0 con marching cubes; la malla es cerrada aunque toque el borde."""
    values = grid.values
    if values.min() > ISO_LEVEL:
        return TriangleMesh(vertices=np.empty((0, 3)), faces=np.empty((0, 3), dtype=np.int64))

    # f < 0 en el interior: "descent" orienta las normales hacia el exterior.
    vertices, faces, _, _ = marching_cubes(
        _close_at_boundary(values), level=ISO_LEVEL, spacing=grid.spacing, gradient_direction="descent"
    )
    # La capa añadida desplaza el índice 0 de la rejilla una celda hacia fuera.
    padded_origin = np.asarray(grid.origin) - np.asarray(grid.spacing)
    vertices += padded_origin
    return TriangleMesh(vertices=vertices, faces=faces.astype(np.int64))
