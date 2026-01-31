# Typed Wrapper Design for pydantic-socketio

## Overview

Add a third integration option alongside the existing subclassing and monkey-patching approaches: a thin wrapper that provides typed `emit`, `call`, and `on` methods while passing through all other socketio functionality.

## Goals

1. Least intrusive integration - wrap existing socketio instances
2. Full static type checker support for emit/call/on patterns
3. Automatic event name derivation from model class names
4. FastAPI-style validation from function signatures
5. Support for union and discriminated union response types

## API Surface

### Basic Usage

```python
from pydantic_socketio import wrap, get_event_name
from pydantic import BaseModel
import socketio

sio = socketio.AsyncClient()
typed_sio = wrap(sio)  # IDE knows: AsyncClientWrapper

# All existing methods work via passthrough
await typed_sio.connect("http://localhost:8000")
```

### Emit Pattern

```python
class Ping(BaseModel):
    message: str

# Emit with event name derived from model class
await typed_sio.emit(Ping(message="Hello"))  # event: "ping"

# Emit with explicit event name
await typed_sio.emit("my-ping", Ping(message="Hello"))

# Standard socketio passthrough
await typed_sio.emit("event", {"payload": ...})
```

### Call/RPC Pattern

```python
class Pong(BaseModel):
    reply: str

# Call with typed response
response = await typed_sio.call(Ping(message="Hi"), response_model=Pong)
# IDE knows: response is Pong

# Call with explicit event name
response = await typed_sio.call("my-ping", Ping(...), response_model=Pong)
# IDE knows: response is Pong

# Union response types
response = await typed_sio.call(Ping(...), response_model=Pong | Error)
# IDE knows: response is Pong | Error

# Discriminated union for reliable matching
from typing import Annotated
from pydantic import Discriminator

ResponseType = Annotated[Pong | Error, Discriminator("kind")]
response = await typed_sio.call(Ping(...), response_model=ResponseType)

# Standard passthrough (no response_model)
response = await typed_sio.call("event", {"payload": ...})
```

### Handler Registration

```python
@typed_sio.on(Ping)  # derives event name via get_event_name(Ping) -> "ping"
async def handle_ping(data: Ping) -> Pong:  # validation from signature
    return Pong(reply=data.message)

# Equivalent explicit form
@typed_sio.on("ping")
async def handle_ping(data: Ping) -> Pong:
    return Pong(reply=data.message)

# Equivalent explicit form
@typed_sio.event
async def ping(data: Ping) -> Pong:
    return Pong(reply=data.message)
```

### Event Name Helper

```python
from typing import ClassVar

class Ping(BaseModel):
    message: str

class CustomEvent(BaseModel):
    event_name: ClassVar[str] = "my_custom_event"
    data: str

get_event_name(Ping)         # "ping"
get_event_name(CustomEvent)  # "my_custom_event"
```

## Architecture

### File Structure

```
src/pydantic_socketio/
├── __init__.py          # Add exports: wrap, get_event_name, *Wrapper classes
├── wrapper.py           # NEW: Core wrapper implementation
├── pydantic_socketio.py # Existing subclass/monkeypatch approach
├── fastapi_socketio.py  # Existing FastAPI integration
└── types.py             # Existing type definitions
```

### Components

#### `get_event_name(model: Type[BaseModel] | BaseModel) -> str`

Standalone function:
1. Accept class or instance
2. Check for `event_name` class attribute
3. Fall back to snake_case conversion of class name

#### Wrapper Classes

Five wrapper classes, one for each socketio type:

| Class | Wraps | Methods |
|-------|-------|---------|
| `SyncClientWrapper` | `Client` | sync `emit`, `call`, `on`, `event` |
| `AsyncClientWrapper` | `AsyncClient` | async `emit`, `call`, `on`, `event`  |
| `SyncServerWrapper` | `Server` | sync `emit`, `call`, `on`, `event`  |
| `AsyncServerWrapper` | `AsyncServer` | async `emit`, `call`, `on`, `event`  |

Each wrapper:
- Stores wrapped instance in `self._sio`
- Delegates unknown attributes via `__getattr__`
- Overrides `emit`, `call`, adds `on` and `event` decorator

#### `wrap(sio)` Factory

Factory function with overloads for type inference:

```python
@overload
def wrap(sio: AsyncClient) -> AsyncClientWrapper: ...
@overload
def wrap(sio: AsyncServer) -> AsyncServerWrapper: ...
@overload
def wrap(sio: Client) -> SyncClientWrapper: ...
@overload
def wrap(sio: Server) -> SyncServerWrapper: ...

def wrap(sio):
    if isinstance(sio, AsyncClient):
        return AsyncClientWrapper(sio)
    elif isinstance(sio, AsyncServer):
        return AsyncServerWrapper(sio)
    elif isinstance(sio, Client):
        return SyncClientWrapper(sio)
    elif isinstance(sio, Server):
        return SyncServerWrapper(sio)
    raise TypeError(f"Expected socketio instance, got {type(sio)}")
```

### Type Overloads

#### `emit()` Overloads

```python
# Model instance -> derives event name
@overload
def emit(self, event: BaseModel, **kwargs) -> None: ...

# String + any data -> passthrough
@overload
def emit(self, event: str, data: Any = None, **kwargs) -> None: ...
```

#### `call()` Overloads

```python
T = TypeVar("T")

# Model + response_model -> typed response
@overload
def call(self, event: BaseModel, response_model: Type[T], **kwargs) -> T: ...

# String + model + response_model -> typed response
@overload
def call(self, event: str, data: BaseModel, response_model: Type[T], **kwargs) -> T: ...

# String + data, no response_model -> Any
@overload
def call(self, event: str, data: Any = None, **kwargs) -> Any: ...
```

#### `on()` Overloads

```python
# Model class -> derives event name
@overload
def on(self, event: Type[BaseModel]) -> Callable: ...

# String -> explicit event name
@overload
def on(self, event: str) -> Callable: ...
```

### Shared Logic

To avoid duplication across 4 wrapper classes, extract common logic:

```python
def _resolve_emit_args(event, data):
    """Resolve event name and payload from emit arguments."""
    if isinstance(event, BaseModel):
        return get_event_name(event), to_jsonable_python(event)
    return event, to_jsonable_python(data) if isinstance(data, BaseModel) else data

def _validate_response(response, response_model):
    """Validate response against response_model if provided."""
    if response_model is not None:
        return TypeAdapter(response_model).validate_python(response)
    return response

def _create_handler_wrapper(handler, is_async: bool):
    """Wrap handler with validation and serialization."""
    validated = validate_call(handler, validate_return=True)
    
    if is_async:
        @wraps(handler)
        async def wrapper(*args, **kwargs):
            result = await validated(*args, **kwargs)
            if isinstance(result, BaseModel):
                return to_jsonable_python(result)
            return result
        return wrapper
    else:
        @wraps(handler)
        def wrapper(*args, **kwargs):
            result = validated(*args, **kwargs)
            if isinstance(result, BaseModel):
                return to_jsonable_python(result)
            return result
        return wrapper
```

## Implementation Tasks

### Phase 1: Core Implementation

1. [ ] Create `src/pydantic_socketio/wrapper.py`
2. [ ] Implement `get_event_name()` function
3. [ ] Implement shared helper functions (`_resolve_emit_args`, `_validate_response`, `_create_handler_wrapper`)
4. [ ] Implement `AsyncClientWrapper` with full type overloads
5. [ ] Implement `AsyncServerWrapper`
6. [ ] Implement `SyncClientWrapper`
7. [ ] Implement `SyncServerWrapper`
8. [ ] Implement `wrap()` factory with overloads
9. [ ] Update `__init__.py` with new exports

### Phase 2: Testing

10. [ ] Add unit tests for `get_event_name()`
11. [ ] Add unit tests for emit with model instances
12. [ ] Add unit tests for emit with explicit event names
13. [ ] Add unit tests for call with response_model
14. [ ] Add unit tests for call with union response types
15. [ ] Add unit tests for handler registration with `on()`
16. [ ] Add unit tests for return value validation
17. [ ] Add integration test with real socketio client/server

### Phase 3: Type Checking Verification

18. [ ] Add `typing_extensions>=4.2.0` to dev dependencies
19. [ ] Create `tests/test_typing.py` with `assert_type` assertions
20. [ ] Add assertions for `wrap()` return types (all 4 variants)
21. [ ] Add assertions for `emit()` overload resolution
22. [ ] Add assertions for `call()` with `response_model` returns `T`
23. [ ] Add assertions for `call()` with union types (`Pong | Error`)
24. [ ] Add assertions for `call()` with discriminated unions
25. [ ] Configure CI to run pyright/mypy on test files
26. [ ] Verify py.typed marker exists (already present)

### Phase 4: Configuration & Documentation

27. [ ] Update `pyproject.toml`: change `requires-python = ">=3.8"` to `>=3.10`
28. [ ] Add `typing_extensions>=4.2.0` to dev dependencies in `pyproject.toml`
29. [ ] Update CI workflow to test Python 3.10-3.13 (drop 3.8, 3.9)
30. [ ] Update README with wrapper usage examples
31. [ ] Add docstrings to all public functions/classes
32. [ ] Update CHANGELOG.md with breaking change notice (Python 3.10+ required)

## Dependencies

Required:
- `pydantic>=2.0` (validate_call, TypeAdapter, to_jsonable_python, Discriminator)
- `python-socketio` (Client, AsyncClient, Server, AsyncServer)
- `typing_extensions>=4.2.0` (for `assert_type` backport in tests)

## Compatibility

- Wrapper is additive, does not change existing subclass/monkeypatch behavior
- Works with any existing socketio instance
- **Requires Python 3.10+** (for `|` union syntax at runtime)

### Python Version Rationale

| Feature | Min Version | Notes |
|---------|-------------|-------|
| `@overload` | 3.5 | Available in `typing` |
| `TypeVar` with `bound=` | 3.5 | Available in `typing` |
| `Union` with `\|` syntax | **3.10** | Runtime requirement (PEP 604) |
| `Annotated` | 3.9 | Backport available, but 3.10 covers this |
| `Discriminator` | Pydantic 2.0+ | Not a Python feature |
| `assert_type()` | 3.11 | Backport via `typing_extensions>=4.2.0` |
| `ClassVar` | 3.5.3 | Available in `typing` |

The `|` union syntax at runtime is the binding constraint. Users write `response_model=Pong | Error`, which requires Python 3.10+.

## Type Checking Verification

Use `typing_extensions.assert_type()` in tests to verify static type inference:

```python
from typing_extensions import assert_type
from pydantic import BaseModel

class Ping(BaseModel):
    message: str

class Pong(BaseModel):
    reply: str

# Verify wrap() returns correct type
sio = wrap(socketio.AsyncClient())
assert_type(sio, AsyncClientWrapper)

# Verify call() returns correct type
response = await sio.call(Ping(message="hi"), response_model=Pong)
assert_type(response, Pong)

# Verify union types
response = await sio.call(Ping(message="hi"), response_model=Pong | Error)
assert_type(response, Pong | Error)
```

These assertions are checked by pyright/mypy at type-check time, not runtime.
