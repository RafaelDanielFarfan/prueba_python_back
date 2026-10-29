from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.logging import get_logger
from app.core.security import create_access_token
from app.users import service
from app.users.dependencies import SessionDep
from app.users.schemas import Token, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger(__name__)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, session: SessionDep) -> UserRead:
    conflict = HTTPException(status.HTTP_409_CONFLICT, detail="El usuario o el email ya existen")
    if await service.exists_user(session, data.username, data.email):
        logger.warning("register_conflict", username=data.username)
        raise conflict

    try:
        user = await service.create_user(session, data)
    except service.UserAlreadyExistsError:
        logger.warning("register_conflict_concurrent", username=data.username)
        raise conflict from None
    logger.info("user_registered", user_id=user.id)
    return UserRead.model_validate(user)


@router.post("/token")
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
) -> Token:
    user = await service.authenticate_user(session, form.username, form.password)
    if user is None:
        logger.warning("login_failed", username=form.username)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.username))
