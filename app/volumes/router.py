import asyncio

from fastapi import APIRouter, Response

from app.core.logging import get_logger
from app.core.time import now_formatted
from app.functions.dependencies import OwnedFunction
from app.volumes.binary import encode_mesh
from app.volumes.cache import mesh_cache, volume_cache
from app.volumes.mesh import extract_mesh
from app.volumes.sampling import sample_function
from app.volumes.schemas import VolumeResult
from app.volumes.volume import VolumeEstimate, estimate_volume

router = APIRouter(prefix="/functions", tags=["volumes"])
logger = get_logger(__name__)


@router.get("/{function_id}/volume")
async def get_volume(function: OwnedFunction) -> VolumeResult:
    expression, domain, resolution = function.expression, function.domain, function.resolution
    # El cálculo es CPU puro y síncrono: en un hilo para no bloquear el event loop.
    estimate: VolumeEstimate = await asyncio.to_thread(
        volume_cache.get_or_compute,
        (function.id, function.version),
        lambda: estimate_volume(expression, domain, resolution),
    )
    logger.info(
        "volume_computed",
        function_id=function.id,
        resolution=function.resolution,
        mesh_volume=estimate.mesh_volume,
    )
    return VolumeResult(
        function_id=function.id,
        resolution=function.resolution,
        voxel_volume=estimate.voxel_volume,
        mesh_volume=estimate.mesh_volume,
        domain_volume=estimate.domain_volume,
        generated_at=now_formatted(),
    )


@router.get("/{function_id}/mesh.bin", response_class=Response)
async def get_mesh(function: OwnedFunction) -> Response:

    expression, domain, resolution = function.expression, function.domain, function.resolution

    def build_payload() -> bytes:
        grid = sample_function(expression, domain, resolution)
        mesh = extract_mesh(grid)
        logger.info("mesh_generated", function_id=function.id, faces=len(mesh.faces))
        return encode_mesh(mesh)

    payload = await asyncio.to_thread(mesh_cache.get_or_compute, (function.id, function.version), build_payload)
    return Response(content=payload, media_type="application/octet-stream")
