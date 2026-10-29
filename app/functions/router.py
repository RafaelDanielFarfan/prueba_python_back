import math

from fastapi import APIRouter, HTTPException, status

from app.core.logging import get_logger
from app.functions import service
from app.functions.dependencies import OwnedFunction
from app.functions.parser import evaluate_point
from app.functions.schemas import FunctionCreate, FunctionRead, FunctionUpdate, PointEvaluation
from app.users.dependencies import CurrentUser, SessionDep

router = APIRouter(prefix="/functions", tags=["functions"])
logger = get_logger(__name__)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_function(data: FunctionCreate, current_user: CurrentUser, session: SessionDep) -> FunctionRead:
    function = await service.create_function(session, current_user.id, data)
    logger.info("function_created", function_id=function.id, user_id=current_user.id)
    return FunctionRead.model_validate(function)


@router.get("")
async def list_functions(current_user: CurrentUser, session: SessionDep) -> list[FunctionRead]:
    functions = await service.list_functions(session, current_user.id)
    return [FunctionRead.model_validate(function) for function in functions]


@router.get("/{function_id}")
async def get_function(function: OwnedFunction) -> FunctionRead:
    return FunctionRead.model_validate(function)


@router.patch("/{function_id}")
async def update_function(function: OwnedFunction, data: FunctionUpdate, session: SessionDep) -> FunctionRead:
    updated = await service.update_function(session, function, data)
    logger.info("function_updated", function_id=updated.id, version=updated.version)
    return FunctionRead.model_validate(updated)


@router.get("/{function_id}/evaluate")
async def evaluate_function(function: OwnedFunction, x: float, y: float, z: float) -> PointEvaluation:
    value = evaluate_point(function.expression, x, y, z)
    if not math.isfinite(value):
        logger.warning("evaluate_non_finite", function_id=function.id, point=[x, y, z])
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="La función no tiene un valor finito en ese punto"
        )
    return PointEvaluation(x=x, y=y, z=z, value=value, is_inside=value <= 0)
