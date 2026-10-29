import asyncio
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.core.logging import get_logger
from app.core.time import now_formatted
from app.functions.dependencies import OwnedFunction
from app.functions.schemas import validate_resolution
from app.volumes.binary import encode_mesh
from app.volumes.cache import mesh_cache, volume_cache
from app.volumes.limiter import compute_limiter
from app.volumes.mesh import extract_mesh
from app.volumes.sampling import sample_function
from app.volumes.schemas import VolumeResult
from app.volumes.volume import VolumeEstimate, estimate_volume

router = APIRouter(prefix="/functions", tags=["volumes"])
logger = get_logger(__name__)


@router.get("/{function_id}/volume")
async def get_volume(
    function: OwnedFunction,
    resolution: Annotated[int | None, Query(description="Muestras por eje; por defecto, la de la función")] = None,
) -> VolumeResult:
    if resolution is None:
        resolution = function.resolution
    else:
        try:
            validate_resolution(resolution)
        except ValueError as error:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
    expression, domain = function.expression, function.domain

    def compute() -> VolumeEstimate:
        with compute_limiter.slot():
            return estimate_volume(expression, domain, resolution)

    # El cálculo es CPU puro y síncrono: en un hilo para no bloquear el event loop.
    estimate: VolumeEstimate = await asyncio.to_thread(
        volume_cache.get_or_compute, (function.id, function.version, resolution), compute
    )
    logger.info(
        "volume_computed",
        function_id=function.id,
        resolution=resolution,
        mesh_volume=estimate.mesh_volume,
    )
    return VolumeResult(
        function_id=function.id,
        resolution=resolution,
        voxel_volume=estimate.voxel_volume,
        mesh_volume=estimate.mesh_volume,
        domain_volume=estimate.domain_volume,
        generated_at=now_formatted(),
    )


@router.get("/{function_id}/mesh.bin", response_class=Response)
async def get_mesh(function: OwnedFunction) -> Response:

    expression, domain, resolution = function.expression, function.domain, function.resolution

    def build_payload() -> bytes:
        with compute_limiter.slot():
            grid = sample_function(expression, domain, resolution)
            mesh = extract_mesh(grid)
        logger.info("mesh_generated", function_id=function.id, faces=len(mesh.faces))
        return encode_mesh(mesh)

    payload = await asyncio.to_thread(mesh_cache.get_or_compute, (function.id, function.version), build_payload)
    return Response(content=payload, media_type="application/octet-stream")
