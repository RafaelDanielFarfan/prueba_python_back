from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.cors import add_cors
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestLoggingMiddleware
from app.db.session import engine, init_db
from app.functions.examples_router import router as examples_router
from app.functions.router import router as functions_router
from app.users.auth_router import router as auth_router
from app.users.router import router as users_router
from app.volumes.limiter import ServerBusyError
from app.volumes.router import router as volumes_router

STATIC_DIR = Path(__file__).parent / "static"

settings = get_settings()
configure_logging(settings.log_level, settings.log_json)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await init_db()
    logger.info("app_started", environment=settings.environment)
    yield
    await engine.dispose()
    logger.info("app_stopped")


app = FastAPI(title=settings.name, version="0.1.0", lifespan=lifespan)
app.add_middleware(RequestLoggingMiddleware)
# Se añade al final para quedar como capa más externa: responde los preflight antes que el resto.
add_cors(app, settings.cors_origin_list)


@app.exception_handler(ServerBusyError)
async def server_busy_handler(request: Request, _: ServerBusyError) -> JSONResponse:
    logger.warning("server_busy", method=request.method, path=request.url.path)
    return JSONResponse(
        status_code=503,
        content={"detail": "El servidor está ocupado calculando; reintenta en unos segundos"},
        headers={"Retry-After": "2"},
    )


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(examples_router)
app.include_router(functions_router)
app.include_router(volumes_router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/viewer", include_in_schema=False)
async def viewer() -> FileResponse:
    return FileResponse(STATIC_DIR / "viewer" / "index.html")
