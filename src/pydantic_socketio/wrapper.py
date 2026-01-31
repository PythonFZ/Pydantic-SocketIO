"""Typed wrapper for python-socketio with Pydantic validation.

This module provides a thin wrapper around socketio instances that adds:
- Typed emit/call methods with automatic event name derivation
- Handler registration with Pydantic validation from type hints
- Support for union and discriminated union response types
"""

from __future__ import annotations

import re
from functools import wraps
from typing import (
    Any,
    Callable,
    Type,
    TypeVar,
    overload,
)

from pydantic import BaseModel, TypeAdapter, validate_call
from pydantic_core import to_jsonable_python
from socketio import AsyncClient, AsyncServer, Client, Server

T = TypeVar("T")


# =============================================================================
# Event Name Helper
# =============================================================================


def get_event_name(model: Type[BaseModel] | BaseModel) -> str:
    """Get event name from a Pydantic model class or instance.

    Checks for an `event_name` class attribute first, then falls back to
    converting the class name from PascalCase to snake_case.

    Args:
        model: A Pydantic model class or instance.

    Returns:
        The event name string.

    Examples:
        >>> class Ping(BaseModel):
        ...     message: str
        >>> get_event_name(Ping)
        'ping'

        >>> from typing import ClassVar
        >>> class CustomEvent(BaseModel):
        ...     event_name: ClassVar[str] = "my_custom_event"
        ...     data: str
        >>> get_event_name(CustomEvent)
        'my_custom_event'
    """
    cls = model if isinstance(model, type) else type(model)

    if hasattr(cls, "event_name"):
        return cls.event_name  # type: ignore[return-value]

    # Convert PascalCase to snake_case
    name = cls.__name__
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


# =============================================================================
# Shared Helper Functions
# =============================================================================


def _resolve_emit_args(event: str | BaseModel, data: Any = None) -> tuple[str, Any]:
    """Resolve event name and payload from emit arguments.

    Args:
        event: Either a string event name or a BaseModel instance.
        data: Optional data payload (used when event is a string).

    Returns:
        Tuple of (event_name, serialized_payload).

    Raises:
        TypeError: If event is a BaseModel and data is also provided.
    """
    if isinstance(event, BaseModel):
        if data is not None:
            raise TypeError(
                "Cannot provide both a BaseModel instance as event and a data argument. "
                "Use emit(MyModel(...)) or emit('event_name', data=...), not both."
            )
        return get_event_name(event), to_jsonable_python(event)
    return event, to_jsonable_python(data) if isinstance(data, BaseModel) else data


def _validate_response(response: Any, response_model: Type[T] | None) -> T | Any:
    """Validate response against response_model if provided.

    Args:
        response: The raw response from socketio.
        response_model: Optional Pydantic model type or union type.

    Returns:
        Validated response if response_model is provided, otherwise raw response.
    """
    if response_model is not None:
        return TypeAdapter(response_model).validate_python(response)
    return response


def _create_async_handler_wrapper(handler: Callable) -> Callable:
    """Wrap async handler with Pydantic validation and serialization.

    Uses pydantic's validate_call to validate input arguments and return value
    based on the function's type annotations.

    Args:
        handler: The async event handler function.

    Returns:
        Wrapped async handler with validation.
    """
    validated = validate_call(validate_return=True)(handler)

    @wraps(handler)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = await validated(*args, **kwargs)
        if isinstance(result, BaseModel):
            return to_jsonable_python(result)
        return result

    return wrapper


def _create_sync_handler_wrapper(handler: Callable) -> Callable:
    """Wrap sync handler with Pydantic validation and serialization.

    Uses pydantic's validate_call to validate input arguments and return value
    based on the function's type annotations.

    Args:
        handler: The sync event handler function.

    Returns:
        Wrapped sync handler with validation.
    """
    validated = validate_call(validate_return=True)(handler)

    @wraps(handler)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = validated(*args, **kwargs)
        if isinstance(result, BaseModel):
            return to_jsonable_python(result)
        return result

    return wrapper


# =============================================================================
# Async Client Wrapper
# =============================================================================


class AsyncClientWrapper:
    """Typed wrapper for socketio.AsyncClient.

    Provides typed emit, call, and on methods while passing through all other
    attributes to the underlying AsyncClient instance.

    Example:
        >>> import socketio
        >>> from pydantic_socketio import wrap
        >>> sio = wrap(socketio.AsyncClient())
        >>> await sio.emit(Ping(message="hello"))
    """

    def __init__(self, sio: AsyncClient) -> None:
        """Initialize wrapper with an AsyncClient instance.

        Args:
            sio: The socketio AsyncClient to wrap.
        """
        self._sio = sio

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the underlying socketio instance."""
        return getattr(self._sio, name)

    # emit overloads
    @overload
    async def emit(
        self,
        event: BaseModel,
        **kwargs: Any,
    ) -> None: ...

    @overload
    async def emit(
        self,
        event: str,
        data: Any = None,
        **kwargs: Any,
    ) -> None: ...

    async def emit(
        self,
        event: str | BaseModel,
        data: Any = None,
        **kwargs: Any,
    ) -> None:
        """Emit an event to the server.

        Args:
            event: Either a string event name or a BaseModel instance.
                If BaseModel, event name is derived from the class name.
            data: Optional data payload (used when event is a string).
            **kwargs: Additional arguments passed to socketio's emit.
        """
        event_name, payload = _resolve_emit_args(event, data)
        await self._sio.emit(event_name, payload, **kwargs)

    # call overloads
    @overload
    async def call(
        self,
        event: BaseModel,
        *,
        response_model: Type[T],
        **kwargs: Any,
    ) -> T: ...

    @overload
    async def call(
        self,
        event: str,
        data: BaseModel,
        *,
        response_model: Type[T],
        **kwargs: Any,
    ) -> T: ...

    @overload
    async def call(
        self,
        event: str,
        data: Any = None,
        **kwargs: Any,
    ) -> Any: ...

    async def call(
        self,
        event: str | BaseModel,
        data: Any = None,
        *,
        response_model: Type[T] | None = None,
        **kwargs: Any,
    ) -> T | Any:
        """Emit an event and wait for a response.

        Args:
            event: Either a string event name or a BaseModel instance.
            data: Optional data payload (used when event is a string).
            response_model: Optional Pydantic model type to validate response.
            **kwargs: Additional arguments passed to socketio's call.

        Returns:
            Validated response if response_model is provided, otherwise raw response.
        """
        event_name, payload = _resolve_emit_args(event, data)
        response = await self._sio.call(event_name, payload, **kwargs)
        return _validate_response(response, response_model)

    # on overloads
    @overload
    def on(self, event: Type[BaseModel]) -> Callable[[Callable], Callable]: ...

    @overload
    def on(self, event: str) -> Callable[[Callable], Callable]: ...

    def on(self, event: str | Type[BaseModel]) -> Callable[[Callable], Callable]:
        """Register an event handler.

        Args:
            event: Either a string event name or a BaseModel class.
                If BaseModel class, event name is derived from the class name.

        Returns:
            Decorator that registers the handler with validation.

        Example:
            >>> @sio.on(Ping)
            ... async def handle_ping(data: Ping) -> Pong:
            ...     return Pong(reply=data.message)
        """
        if isinstance(event, type) and issubclass(event, BaseModel):
            event_name = get_event_name(event)
        else:
            event_name = event

        def decorator(handler: Callable) -> Callable:
            wrapped = _create_async_handler_wrapper(handler)
            self._sio.on(event_name, wrapped)
            return handler

        return decorator

    def event(self, handler: Callable) -> Callable:
        """Register an event handler using the function name as the event name.

        This decorator uses the function name directly as the event name and
        wraps the handler with Pydantic validation based on type annotations.

        Args:
            handler: The event handler function.

        Returns:
            The original handler (unmodified).

        Example:
            >>> @sio.event
            ... async def ping(data: Ping) -> Pong:
            ...     return Pong(reply=data.message)
        """
        event_name = handler.__name__
        wrapped = _create_async_handler_wrapper(handler)
        self._sio.on(event_name, wrapped)
        return handler


# =============================================================================
# Async Server Wrapper
# =============================================================================


class AsyncServerWrapper:
    """Typed wrapper for socketio.AsyncServer.

    Provides typed emit, call, and on methods while passing through all other
    attributes to the underlying AsyncServer instance.
    """

    def __init__(self, sio: AsyncServer) -> None:
        """Initialize wrapper with an AsyncServer instance.

        Args:
            sio: The socketio AsyncServer to wrap.
        """
        self._sio = sio

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the underlying socketio instance."""
        return getattr(self._sio, name)

    # emit overloads
    @overload
    async def emit(
        self,
        event: BaseModel,
        **kwargs: Any,
    ) -> None: ...

    @overload
    async def emit(
        self,
        event: str,
        data: Any = None,
        **kwargs: Any,
    ) -> None: ...

    async def emit(
        self,
        event: str | BaseModel,
        data: Any = None,
        **kwargs: Any,
    ) -> None:
        """Emit an event to connected clients.

        Args:
            event: Either a string event name or a BaseModel instance.
            data: Optional data payload (used when event is a string).
            **kwargs: Additional arguments passed to socketio's emit (to, room, etc).
        """
        event_name, payload = _resolve_emit_args(event, data)
        await self._sio.emit(event_name, payload, **kwargs)

    # call overloads
    @overload
    async def call(
        self,
        event: BaseModel,
        *,
        response_model: Type[T],
        **kwargs: Any,
    ) -> T: ...

    @overload
    async def call(
        self,
        event: str,
        data: BaseModel,
        *,
        response_model: Type[T],
        **kwargs: Any,
    ) -> T: ...

    @overload
    async def call(
        self,
        event: str,
        data: Any = None,
        **kwargs: Any,
    ) -> Any: ...

    async def call(
        self,
        event: str | BaseModel,
        data: Any = None,
        *,
        response_model: Type[T] | None = None,
        **kwargs: Any,
    ) -> T | Any:
        """Emit an event and wait for a response from a client.

        Args:
            event: Either a string event name or a BaseModel instance.
            data: Optional data payload (used when event is a string).
            response_model: Optional Pydantic model type to validate response.
            **kwargs: Additional arguments passed to socketio's call (to, sid, etc).

        Returns:
            Validated response if response_model is provided, otherwise raw response.
        """
        event_name, payload = _resolve_emit_args(event, data)
        response = await self._sio.call(event_name, payload, **kwargs)
        return _validate_response(response, response_model)

    # on overloads
    @overload
    def on(self, event: Type[BaseModel]) -> Callable[[Callable], Callable]: ...

    @overload
    def on(self, event: str) -> Callable[[Callable], Callable]: ...

    def on(self, event: str | Type[BaseModel]) -> Callable[[Callable], Callable]:
        """Register an event handler.

        Args:
            event: Either a string event name or a BaseModel class.

        Returns:
            Decorator that registers the handler with validation.
        """
        if isinstance(event, type) and issubclass(event, BaseModel):
            event_name = get_event_name(event)
        else:
            event_name = event

        def decorator(handler: Callable) -> Callable:
            wrapped = _create_async_handler_wrapper(handler)
            self._sio.on(event_name, wrapped)
            return handler

        return decorator

    def event(self, handler: Callable) -> Callable:
        """Register an event handler using the function name as the event name.

        Args:
            handler: The event handler function.

        Returns:
            The original handler (unmodified).

        Example:
            >>> @sio.event
            ... async def ping(data: Ping) -> Pong:
            ...     return Pong(reply=data.message)
        """
        event_name = handler.__name__
        wrapped = _create_async_handler_wrapper(handler)
        self._sio.on(event_name, wrapped)
        return handler


# =============================================================================
# Sync Client Wrapper
# =============================================================================


class SyncClientWrapper:
    """Typed wrapper for socketio.Client.

    Provides typed emit, call, and on methods while passing through all other
    attributes to the underlying Client instance.
    """

    def __init__(self, sio: Client) -> None:
        """Initialize wrapper with a Client instance.

        Args:
            sio: The socketio Client to wrap.
        """
        self._sio = sio

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the underlying socketio instance."""
        return getattr(self._sio, name)

    # emit overloads
    @overload
    def emit(
        self,
        event: BaseModel,
        **kwargs: Any,
    ) -> None: ...

    @overload
    def emit(
        self,
        event: str,
        data: Any = None,
        **kwargs: Any,
    ) -> None: ...

    def emit(
        self,
        event: str | BaseModel,
        data: Any = None,
        **kwargs: Any,
    ) -> None:
        """Emit an event to the server.

        Args:
            event: Either a string event name or a BaseModel instance.
            data: Optional data payload (used when event is a string).
            **kwargs: Additional arguments passed to socketio's emit.
        """
        event_name, payload = _resolve_emit_args(event, data)
        self._sio.emit(event_name, payload, **kwargs)

    # call overloads
    @overload
    def call(
        self,
        event: BaseModel,
        *,
        response_model: Type[T],
        **kwargs: Any,
    ) -> T: ...

    @overload
    def call(
        self,
        event: str,
        data: BaseModel,
        *,
        response_model: Type[T],
        **kwargs: Any,
    ) -> T: ...

    @overload
    def call(
        self,
        event: str,
        data: Any = None,
        **kwargs: Any,
    ) -> Any: ...

    def call(
        self,
        event: str | BaseModel,
        data: Any = None,
        *,
        response_model: Type[T] | None = None,
        **kwargs: Any,
    ) -> T | Any:
        """Emit an event and wait for a response.

        Args:
            event: Either a string event name or a BaseModel instance.
            data: Optional data payload (used when event is a string).
            response_model: Optional Pydantic model type to validate response.
            **kwargs: Additional arguments passed to socketio's call.

        Returns:
            Validated response if response_model is provided, otherwise raw response.
        """
        event_name, payload = _resolve_emit_args(event, data)
        response = self._sio.call(event_name, payload, **kwargs)
        return _validate_response(response, response_model)

    # on overloads
    @overload
    def on(self, event: Type[BaseModel]) -> Callable[[Callable], Callable]: ...

    @overload
    def on(self, event: str) -> Callable[[Callable], Callable]: ...

    def on(self, event: str | Type[BaseModel]) -> Callable[[Callable], Callable]:
        """Register an event handler.

        Args:
            event: Either a string event name or a BaseModel class.

        Returns:
            Decorator that registers the handler with validation.
        """
        if isinstance(event, type) and issubclass(event, BaseModel):
            event_name = get_event_name(event)
        else:
            event_name = event

        def decorator(handler: Callable) -> Callable:
            wrapped = _create_sync_handler_wrapper(handler)
            self._sio.on(event_name, wrapped)
            return handler

        return decorator

    def event(self, handler: Callable) -> Callable:
        """Register an event handler using the function name as the event name.

        Args:
            handler: The event handler function.

        Returns:
            The original handler (unmodified).

        Example:
            >>> @sio.event
            ... def ping(data: Ping) -> Pong:
            ...     return Pong(reply=data.message)
        """
        event_name = handler.__name__
        wrapped = _create_sync_handler_wrapper(handler)
        self._sio.on(event_name, wrapped)
        return handler


# =============================================================================
# Sync Server Wrapper
# =============================================================================


class SyncServerWrapper:
    """Typed wrapper for socketio.Server.

    Provides typed emit, call, and on methods while passing through all other
    attributes to the underlying Server instance.
    """

    def __init__(self, sio: Server) -> None:
        """Initialize wrapper with a Server instance.

        Args:
            sio: The socketio Server to wrap.
        """
        self._sio = sio

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the underlying socketio instance."""
        return getattr(self._sio, name)

    # emit overloads
    @overload
    def emit(
        self,
        event: BaseModel,
        **kwargs: Any,
    ) -> None: ...

    @overload
    def emit(
        self,
        event: str,
        data: Any = None,
        **kwargs: Any,
    ) -> None: ...

    def emit(
        self,
        event: str | BaseModel,
        data: Any = None,
        **kwargs: Any,
    ) -> None:
        """Emit an event to connected clients.

        Args:
            event: Either a string event name or a BaseModel instance.
            data: Optional data payload (used when event is a string).
            **kwargs: Additional arguments passed to socketio's emit.
        """
        event_name, payload = _resolve_emit_args(event, data)
        self._sio.emit(event_name, payload, **kwargs)

    # call overloads
    @overload
    def call(
        self,
        event: BaseModel,
        *,
        response_model: Type[T],
        **kwargs: Any,
    ) -> T: ...

    @overload
    def call(
        self,
        event: str,
        data: BaseModel,
        *,
        response_model: Type[T],
        **kwargs: Any,
    ) -> T: ...

    @overload
    def call(
        self,
        event: str,
        data: Any = None,
        **kwargs: Any,
    ) -> Any: ...

    def call(
        self,
        event: str | BaseModel,
        data: Any = None,
        *,
        response_model: Type[T] | None = None,
        **kwargs: Any,
    ) -> T | Any:
        """Emit an event and wait for a response from a client.

        Args:
            event: Either a string event name or a BaseModel instance.
            data: Optional data payload (used when event is a string).
            response_model: Optional Pydantic model type to validate response.
            **kwargs: Additional arguments passed to socketio's call.

        Returns:
            Validated response if response_model is provided, otherwise raw response.
        """
        event_name, payload = _resolve_emit_args(event, data)
        response = self._sio.call(event_name, payload, **kwargs)
        return _validate_response(response, response_model)

    # on overloads
    @overload
    def on(self, event: Type[BaseModel]) -> Callable[[Callable], Callable]: ...

    @overload
    def on(self, event: str) -> Callable[[Callable], Callable]: ...

    def on(self, event: str | Type[BaseModel]) -> Callable[[Callable], Callable]:
        """Register an event handler.

        Args:
            event: Either a string event name or a BaseModel class.

        Returns:
            Decorator that registers the handler with validation.
        """
        if isinstance(event, type) and issubclass(event, BaseModel):
            event_name = get_event_name(event)
        else:
            event_name = event

        def decorator(handler: Callable) -> Callable:
            wrapped = _create_sync_handler_wrapper(handler)
            self._sio.on(event_name, wrapped)
            return handler

        return decorator

    def event(self, handler: Callable) -> Callable:
        """Register an event handler using the function name as the event name.

        Args:
            handler: The event handler function.

        Returns:
            The original handler (unmodified).

        Example:
            >>> @sio.event
            ... def ping(data: Ping) -> Pong:
            ...     return Pong(reply=data.message)
        """
        event_name = handler.__name__
        wrapped = _create_sync_handler_wrapper(handler)
        self._sio.on(event_name, wrapped)
        return handler


# =============================================================================
# Factory Function
# =============================================================================


@overload
def wrap(sio: AsyncClient) -> AsyncClientWrapper: ...


@overload
def wrap(sio: AsyncServer) -> AsyncServerWrapper: ...


@overload
def wrap(sio: Client) -> SyncClientWrapper: ...


@overload
def wrap(sio: Server) -> SyncServerWrapper: ...


def wrap(
    sio: AsyncClient | AsyncServer | Client | Server,
) -> AsyncClientWrapper | AsyncServerWrapper | SyncClientWrapper | SyncServerWrapper:
    """Wrap a socketio instance with typed emit, call, and on methods.

    This is the main entry point for the wrapper API. It auto-detects the
    type of socketio instance and returns the appropriate wrapper.

    Args:
        sio: A socketio Client, AsyncClient, Server, or AsyncServer instance.

    Returns:
        The appropriate wrapper class for the given socketio instance.

    Raises:
        TypeError: If sio is not a recognized socketio instance type.

    Example:
        >>> import socketio
        >>> from pydantic_socketio import wrap
        >>>
        >>> sio = socketio.AsyncClient()
        >>> typed_sio = wrap(sio)  # Returns AsyncClientWrapper
        >>>
        >>> # Now use typed methods
        >>> await typed_sio.emit(Ping(message="hello"))
    """
    if isinstance(sio, AsyncClient):
        return AsyncClientWrapper(sio)
    elif isinstance(sio, AsyncServer):
        return AsyncServerWrapper(sio)
    elif isinstance(sio, Client):
        return SyncClientWrapper(sio)
    elif isinstance(sio, Server):
        return SyncServerWrapper(sio)
    raise TypeError(f"Expected socketio instance, got {type(sio)}")
