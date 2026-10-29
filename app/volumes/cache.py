from collections import OrderedDict
from collections.abc import Callable, Hashable
from threading import Lock

from app.core.config import get_settings


class ResultCache[T]:
    """Cache LRU en memoria de resultados de cálculo.

    La clave debe identificar todo lo que determina el resultado. Para una función es
    ``(id, version)``: cada edición incrementa ``version``, así que produce una clave nueva y
    las entradas anteriores salen solas por antigüedad.
    """

    def __init__(self, max_items: int) -> None:
        self._items: OrderedDict[Hashable, T] = OrderedDict()
        self._max_items = max_items
        self._lock = Lock()

    def get_or_compute(self, key: Hashable, compute: Callable[[], T]) -> T:
        with self._lock:
            if key in self._items:
                self._items.move_to_end(key)
                return self._items[key]

        value = compute()
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self._max_items:
                self._items.popitem(last=False)
        return value

    def invalidate(self, key: Hashable) -> None:
        with self._lock:
            self._items.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def __len__(self) -> int:
        return len(self._items)


mesh_cache: ResultCache[bytes] = ResultCache(get_settings().cache_max_items)
volume_cache: ResultCache[object] = ResultCache(get_settings().cache_max_items)
