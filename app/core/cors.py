from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware


def add_cors(app: FastAPI, origins: list[str]) -> None:
    """Permite que los navegadores llamen a la API desde ``origins``; con la lista vacía no abre nada.

    La autenticación va en la cabecera ``Authorization`` y no en cookies, por lo que no se
    habilitan credenciales.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["X-Request-ID"],
    )
