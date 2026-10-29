"""Tabla de convergencia del volumen frente al valor analítico.

Uso (desde la raíz del repositorio, con ``.env`` configurado):

    uv run python -m scripts.convergence
"""

import math
import time

from app.functions.examples import EXAMPLES_BY_SLUG
from app.volumes.volume import estimate_volume

RESOLUTIONS = (32, 64, 128, 256)

# Esfera: 4/3 π r³ con r = 1. Toro: 2 π² R r² con R = 1 y r = 0.25.
# Gyroide: f(p + (π, π, π)) = -f(p), así que f ≤ 0 ocupa exactamente la mitad del dominio [0, 2π]³.
ANALYTIC_VOLUMES = {
    "esfera": 4 / 3 * math.pi,
    "toro": 2 * math.pi**2 * 0.25**2,
    "gyroide": (2 * math.pi) ** 3 / 2,
}


def relative_error(value: float, reference: float) -> float:
    return abs(value - reference) / reference


def main() -> None:
    print("| Función | n | Volumen malla | Error malla | Volumen vóxel | Error vóxel | Tiempo (s) |")
    print("|---|---|---|---|---|---|---|")
    for slug, reference in ANALYTIC_VOLUMES.items():
        function = EXAMPLES_BY_SLUG[slug].function
        for resolution in RESOLUTIONS:
            started_at = time.perf_counter()
            estimate = estimate_volume(function.expression, function.domain, resolution)
            elapsed = time.perf_counter() - started_at
            print(
                f"| {slug} | {resolution} "
                f"| {estimate.mesh_volume:.6f} | {relative_error(estimate.mesh_volume, reference):.2e} "
                f"| {estimate.voxel_volume:.6f} | {relative_error(estimate.voxel_volume, reference):.2e} "
                f"| {elapsed:.1f} |"
            )


if __name__ == "__main__":
    main()
