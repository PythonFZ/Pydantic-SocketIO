"""Dependency injection parameters for pydantic-socketio.

Provides a lightweight Depends dataclass compatible with FastAPI's Depends.
When FastAPI is installed, its Depends is used directly instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class Depends:
    """Declare a dependency for a Socket.IO event handler.

    When FastAPI is installed, use ``fastapi.Depends`` instead - it is
    automatically recognised by the wrapper.

    Example::

        from pydantic_socketio.params import Depends

        async def get_redis():
            return Redis()

        @tsio.on(MyEvent)
        async def handler(sid: str, data: MyEvent, redis: Redis = Depends(get_redis)):
            ...
    """

    dependency: Optional[Callable[..., Any]] = None
    use_cache: bool = True
