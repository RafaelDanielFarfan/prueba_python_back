from collections.abc import Iterator
from contextlib import contextmanager
from threading import BoundedSemaphore

from app.core.config import get_settings


class ServerBusyError(Exception):
    """No hay hueco libre para otro cálculo pesado."""


class ComputeLimiter:
    """Limita cuántos cálculos pesados corren a la vez; si no hay hueco, falla en lugar de esperar."""

    def __init__(self, limit: int) -> None:
        self._slots = BoundedSemaphore(limit)

    @contextmanager
    def slot(self) -> Iterator[None]:
        if not self._slots.acquire(blocking=False):
            raise ServerBusyError
        try:
            yield
        finally:
            self._slots.release()


compute_limiter = ComputeLimiter(get_settings().max_concurrent_computations)
