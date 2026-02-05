# Pydantic-SocketIO

[![GitHub](https://img.shields.io/badge/github-Pydantic--SocketIO-blue?logo=github)](https://github.com/atomiechen/Pydantic-SocketIO)
[![PyPI](https://img.shields.io/pypi/v/Pydantic--SocketIO?logo=pypi&logoColor=white)](https://pypi.org/project/pydantic-socketio/)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/atomiechen/Pydantic-SocketIO)


A Pydantic-enhanced SocketIO library for Python, with FastAPI integration.


## Features

⭐️ **Pydantic-Enhanced SocketIO**: Drop-in replacements for the original [python-socketio](https://github.com/miguelgrinberg/python-socketio) server and client (sync and async), with built-in Pydantic validation for event data. You can also easily monkey patch this validation to the original `socketio` server and client.

🎯 **Typed Wrapper API**: Wrap any existing socketio instance with fully typed `emit`, `call`, and handler registration. Automatic event name derivation from model class names, typed responses with `response_model`, and FastAPI-style validation from type hints.

🪐 **Easy Integration with FastAPI**: Seamlessly integrates `Socket.IO` with FastAPI, allowing you to manage event-driven communication effortlessly.


## Installation

```sh
pip install pydantic-socketio
```

If you want FastAPI integration, you can install the extra dependencies:

```sh
pip install pydantic-socketio[fastapi]
```

Other options of original [python-socketio](https://github.com/miguelgrinberg/python-socketio) are also available: `client`, `asyncio-client`, `docs`.


## Usage

### Recommended: Pydantic-Enhanced SocketIO Server and Client

Drop-in replacements for the original [python-socketio](https://github.com/miguelgrinberg/python-socketio) server and client are provided. 

The enhanced SocketIO server with Pydantic validation:

```python
from pydantic import BaseModel
import pydantic_socketio

class ChatMessage(BaseModel):
    role: str
    content: str

# Create an enhanced SocketIO server; use AsyncServer for async server
sio = pydantic_socketio.Server()

# Define a listen event with Pydantic validation
@sio.event
def message(data: ChatMessage):
    print(f"Received chat message from {data.role}: {data.content}")
    data.content = data.content.upper()
    print(f"Sending uppercase message: {data.content}")
    # Emit an event with Pydantic model without any additional conversion
    sio.emit("message", data)

# `on` decorator is also supported
@sio.on("custom_event")
def handle_custom_event(data: int):
    ...

# Register an emit event with Pydantic validation
sio.register_emit("message", payload_type=ChatMessage)

# Or, use the decorator form
@sio.register_emit("misc")
class MiscData(BaseModel):
    value: int
```

The enhanced SocketIO client with Pydantic validation:

```python
import pydantic_socketio

# Create an enhanced SocketIO client; use AsyncClient for async client
sio = pydantic_socketio.Client()

@sio.register_emit("ping")
class PingData(BaseModel):
    value: int

sio.register_emit("pong", payload_type=int)

@sio.event
def ping(data: PingData):
    ...

@sio.on("pong")
def handle_pong(data: int):
    ...
```


### Typed Wrapper API

The typed wrapper provides a non-intrusive way to add typed emit/call methods to any existing socketio instance:

```python
from pydantic import BaseModel
from pydantic_socketio import wrap
import socketio

class Ping(BaseModel):
    message: str

class Pong(BaseModel):
    reply: str

# Wrap any existing socketio instance (tsio = typed socketio)
tsio = wrap(socketio.AsyncClient())

# Emit with automatic event name derivation (Ping -> "ping")
await tsio.emit(Ping(message="Hello, World!"))

# Emit with explicit event name
await tsio.emit("my-ping", Ping(message="Hello, World!"))

# Call with typed response
response = await tsio.call(Ping(message="Hello"), response_model=Pong)
# response is typed as Pong

# Handler registration with validation from type hints
@tsio.on(Ping)  # Event name derived from Ping -> "ping"
async def handle_ping(data: Ping) -> Pong:
    return Pong(reply=data.message)

# Or use @tsio.event with function name as event name
@tsio.event
async def ping(data: Ping) -> Pong:
    return Pong(reply=data.message)
```

#### Union Response Types

You can use union types for responses that may return different models:

```python
from typing import Annotated, Literal
from pydantic import BaseModel, Discriminator

class Success(BaseModel):
    kind: Literal["success"] = "success"
    data: str

class Error(BaseModel):
    kind: Literal["error"] = "error"
    message: str

# Simple union (Pydantic uses smart matching)
response = await tsio.call(request, response_model=Success | Error)

# Discriminated union for reliable matching
ResponseType = Annotated[Success | Error, Discriminator("kind")]
response = await tsio.call(request, response_model=ResponseType)
```

#### Custom Event Names

By default, event names are derived from model class names in snake_case. You can override this:

```python
from typing import ClassVar

class CustomEvent(BaseModel):
    event_name: ClassVar[str] = "my_custom_event"
    data: str

# Uses "my_custom_event" instead of "custom_event"
await tsio.emit(CustomEvent(data="hello"))
```

#### Exception Handlers

Handle exceptions from Socket.IO event handlers with FastAPI-style exception handlers:

```python
import socketio
from pydantic import BaseModel, ValidationError
from pydantic_socketio import wrap, EventContext

class ErrorResponse(BaseModel):
    error: str
    message: str

# Wrap an AsyncServer
tsio = wrap(socketio.AsyncServer(async_mode="asgi"))

@tsio.on("risky_operation")
async def handle_risky(sid, data: dict):
    if data.get("fail"):
        raise ValueError("Operation failed!")
    return {"status": "success"}

# Register exception handler (global)
@tsio.exception_handler(ValueError)
async def handle_value_error(ctx: EventContext, exc: ValueError):
    # ctx provides: sid, event, namespace, data, sio
    return ErrorResponse(error="value_error", message=str(exc))

# Namespace-specific exception handler
@tsio.exception_handler(ValidationError, namespace="/chat")
async def handle_chat_validation(ctx: EventContext, exc: ValidationError):
    return ErrorResponse(error="validation_error", message="Invalid chat data")
```

The `EventContext` provides full context about the event:
- `sid`: Session ID of the client
- `event`: Event name that raised the exception  
- `namespace`: Namespace where the event occurred
- `data`: Original data sent by the client
- `sio`: Wrapper instance for emitting events

#### Dependency Injection in Event Handlers

Event handlers support FastAPI-style `Depends()` for injecting dependencies. Both `Annotated` type hints and default values are supported:

```python
import socketio
from typing import Annotated
from fastapi import Depends
from pydantic import BaseModel
from pydantic_socketio import wrap

class RoomLeave(BaseModel):
    room_id: str

class RoomLeaveResponse(BaseModel):
    status: str

# Define dependencies
async def get_redis():
    return my_redis_pool

# Create a reusable type alias
RedisDep = Annotated[AsyncRedis, Depends(get_redis)]

tsio = wrap(socketio.AsyncServer(async_mode="asgi"))

# Use Annotated style (recommended)
@tsio.on(RoomLeave)
async def room_leave(sid: str, data: RoomLeave, redis: RedisDep) -> RoomLeaveResponse:
    await redis.delete(f"presence:{data.room_id}:{sid}")
    return RoomLeaveResponse(status="ok")

# Or use default value style
@tsio.on(RoomLeave)
async def room_leave(sid: str, data: RoomLeave, redis = Depends(get_redis)) -> RoomLeaveResponse:
    await redis.delete(f"presence:{data.room_id}:{sid}")
    return RoomLeaveResponse(status="ok")
```

Both sync and async dependency functions are supported. When FastAPI is not installed, you can import `Depends` from `pydantic_socketio` directly:

```python
from pydantic_socketio import Depends
```

#### SimpleClient Support

The wrapper also supports `SimpleClient` and `AsyncSimpleClient`, which use `receive()` instead of event handlers:

```python
from pydantic import BaseModel
from pydantic_socketio import wrap
import socketio

class Ping(BaseModel):
    message: str

class Pong(BaseModel):
    reply: str

# Wrap a SimpleClient
tsio = wrap(socketio.SimpleClient())
tsio.connect("http://localhost:5000")

# Emit with typed model
tsio.emit(Ping(message="Hello"))

# Call with typed response
response = tsio.call(Ping(message="Hello"), response_model=Pong)

# Receive with typed response - returns (event_name, validated_data)
event_name, data = tsio.receive(response_model=Pong)
print(f"Received {event_name}: {data.reply}")

tsio.disconnect()
```

### Alternative: Monkey Patching for Original SocketIO

Alternatively, if you want to apply Pydantic validation to the original [python-socketio](https://github.com/miguelgrinberg/python-socketio) server and client without replacing them, you can use the `monkey_patch()` method:

```python
from pydantic_socketio import monkey_patch
import socketio

# Apply monkey patch to the original socketio server and client
monkey_patch()

# Now, you can use the original socketio server and client with Pydantic validation
sio = socketio.Server()

@sio.event
def ping(data: int):
    print(f"Received ping: {data}")
    data += 1
    print(f"Sending pong: {data}")
    sio.emit("poing", data)
```


### FastAPI Integration

You can easily integrate the enhanced socketio server with FastAPI by using FastAPISocketIO:

```python
from fastapi import FastAPI
from pydantic_socketio import FastAPISocketIO

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}
...

# Create a FastAPI socketio server
sio = FastAPISocketIO(app)

@sio.event
async def ping(data: int):
    print(f"Received ping: {data}")
    data += 1
    print(f"Sending pong: {data}")
    await sio.emit("pong", data)

# Both sync and async event handlers are supported, as per the original python-socketio
@sio.on("custom_event")
def handle_custom_event(data: int):
    ...
```

You can also integrate the SocketIO server manually after FastAPI initialization:

```python
from fastapi import FastAPI
from pydantic_socketio import FastAPISocketIO

sio = FastAPISocketIO()
...
app = FastAPI()
...

# Integrate the SocketIO server to FastAPI
sio.integrate(app)
```


### FastAPI Dependency Injection

You can use `SioDep` as a `FastAPISocketIO` dependency injection in FastAPI applications:

```python
from fastapi import FastAPI
from pydantic_socketio import FastAPISocketIO, SioDep

app = FastAPI()
sio = FastAPISocketIO(app)

# You may define this endpoint in another file, like in a separate router
@app.get("/")
async def root(sio: SioDep):
    await sio.emit("message", "API root called")
    return {"Hello": "World"}
```

#### Using Typed Wrapper with FastAPI

The typed wrapper also supports FastAPI dependency injection:

```python
import socketio
from typing import Annotated
from fastapi import FastAPI, Depends
from pydantic_socketio import wrap, AsyncServerWrapper

app = FastAPI()
tsio = wrap(socketio.AsyncServer(async_mode="asgi"))

# Create type alias for dependency injection
SioServer = Annotated[AsyncServerWrapper, Depends(tsio)]

# Use wrapper with Depends()
@app.post("/notify")
async def notify(server: SioServer):
    # server is the typed wrapper with typed emit/call methods
    await server.emit("notification", {"msg": "hello"})
    return {"status": "sent"}

# Create combined ASGI app with Socket.IO and FastAPI
combined_app = socketio.ASGIApp(tsio, app)
```


## Original Documentation

More details can be found in the original [python-socketio documentation](https://python-socketio.readthedocs.io/en/stable/).


## License

[Pydantic-SocketIO](https://github.com/atomiechen/Pydantic-SocketIO) © 2025 by [Atomie CHEN](https://github.com/atomiechen) is licensed under the [MIT License](https://github.com/atomiechen/Pydantic-SocketIO/blob/main/LICENSE).
