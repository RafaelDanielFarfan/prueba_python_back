from dataclasses import dataclass

import numpy as np

from app.core.logging import get_logger
from app.functions.parser import FloatArray, compile_expression

logger = get_logger(__name__)

Vector3 = tuple[float, float, float]


@dataclass(frozen=True)
class SampledGrid:
    """Valores de f en una rejilla regular; ``values[i, j, k]`` corresponde a (x_i, y_j, z_k)."""

    values: FloatArray
    origin: Vector3
    spacing: Vector3

    @property
    def shape(self) -> tuple[int, int, int]:
        nx, ny, nz = self.values.shape
        return nx, ny, nz


def grid_origin(domain: list[list[float]]) -> Vector3:
    (x_min, _), (y_min, _), (z_min, _) = domain
    return float(x_min), float(y_min), float(z_min)


def grid_spacing(domain: list[list[float]], resolution: int) -> Vector3:
    """Distancia entre muestras por eje: ``resolution`` puntos delimitan ``resolution - 1`` intervalos."""
    (x_min, x_max), (y_min, y_max), (z_min, z_max) = domain
    return (
        (x_max - x_min) / (resolution - 1),
        (y_max - y_min) / (resolution - 1),
        (z_max - z_min) / (resolution - 1),
    )


def build_axes(domain: list[list[float]], resolution: int) -> list[FloatArray]:
    return [np.linspace(lower, upper, resolution) for lower, upper in domain]


def sample_function(expression: str, domain: list[list[float]], resolution: int) -> SampledGrid:
    axes = build_axes(domain, resolution)
    # Indexado matricial: values[i, j, k] = f(x_i, y_j, z_k), el orden que espera marching_cubes.
    x, y, z = np.meshgrid(*axes, indexing="ij")
    values = compile_expression(expression)(x, y, z)
    non_finite = values.size - int(np.count_nonzero(np.isfinite(values)))
    if non_finite:
        logger.warning("non_finite_samples", count=non_finite, total=values.size, resolution=resolution)

    return SampledGrid(
        values=values,
        origin=grid_origin(domain),
        spacing=grid_spacing(domain, resolution),
    )
