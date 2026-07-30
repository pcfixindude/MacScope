from __future__ import annotations

"""Lightweight local cache helpers for collector/UI responsiveness."""

import time
from threading import Lock
from typing import Any, Callable, TypeVar

from macscope.settings import load_settings

T = TypeVar("T")

_LOCK = Lock()
_STORE: dict[str, tuple[float, Any]] = {}


def cache_get(key: str) -> Any | None:
    with _LOCK:
        item = _STORE.get(key)
        if not item:
            return None
        expires_at, value = item
        if time.time() > expires_at:
            _STORE.pop(key, None)
            return None
        return value


def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    settings = load_settings()
    lifetime = ttl if ttl is not None else max(30, int(settings.collector_cache_seconds or 120))
    with _LOCK:
        _STORE[key] = (time.time() + lifetime, value)


def cache_invalidate(prefix: str | None = None) -> None:
    with _LOCK:
        if prefix is None:
            _STORE.clear()
            return
        for key in list(_STORE):
            if key.startswith(prefix):
                _STORE.pop(key, None)


def cached(key: str, factory: Callable[[], T], ttl: int | None = None) -> T:
    hit = cache_get(key)
    if hit is not None:
        return hit
    value = factory()
    cache_set(key, value, ttl=ttl)
    return value
