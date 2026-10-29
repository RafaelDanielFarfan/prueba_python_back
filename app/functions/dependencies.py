from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.core.logging import get_logger
from app.db.models import ImplicitFunction
from app.functions import service
from app.users.dependencies import CurrentUser, SessionDep

logger = get_logger(__name__)


async def get_owned_function(
    function_id: int, current_user: CurrentUser, session: SessionDep
) -> ImplicitFunction:
    function = await service.get_function(session, function_id, owner_id=current_user.id)
    if function is None:
        logger.warning("function_not_found", function_id=function_id, user_id=current_user.id)
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Función no encontrada")
    return function


OwnedFunction = Annotated[ImplicitFunction, Depends(get_owned_function)]
