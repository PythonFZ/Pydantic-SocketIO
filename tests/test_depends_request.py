"""Tests for Request auto-injection and generator dependencies."""

from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import AsyncIterator

import pytest
import socketio

from pydantic_socketio import wrap
from pydantic_socketio.wrapper import (
    Request,
    SioRequest,
    _resolve_dependencies,
)


@dataclass
class FakeState:
    db_url: str = "sqlite://"


@dataclass
class FakeApp:
    state: FakeState = None

    def __post_init__(self):
        if self.state is None:
            self.state = FakeState()


def test_sio_request_exposes_app():
    """SioRequest.app returns the app instance."""
    app = FakeApp()
    req = SioRequest(app=app)
    assert req.app is app


def test_sio_request_app_state():
    """SioRequest.app.state is accessible."""
    app = FakeApp(state=FakeState(db_url="postgres://localhost/mydb"))
    req = SioRequest(app=app)
    assert req.app.state.db_url == "postgres://localhost/mydb"


def test_sio_request_no_url():
    """Unsupported attrs raise AttributeError."""
    req = SioRequest(app=FakeApp())
    with pytest.raises(AttributeError):
        _ = req.url


# ---------------------------------------------------------------------------
# wrap() app kwarg tests
# ---------------------------------------------------------------------------


def test_wrap_with_app():
    """wrap(sio, app=app) stores app on the wrapper."""
    app = FakeApp()
    tsio = wrap(socketio.AsyncServer(async_mode="asgi"), app=app)
    assert tsio._app is app


def test_wrap_without_app():
    """wrap(sio) without app sets _app to None."""
    tsio = wrap(socketio.AsyncServer(async_mode="asgi"))
    assert tsio._app is None


def test_wrap_app_ignored_for_client():
    """wrap() with app kwarg on a client type ignores it."""
    tsio = wrap(socketio.AsyncClient(), app=FakeApp())
    assert not hasattr(tsio, "_app") or tsio._app is None


# ---------------------------------------------------------------------------
# _resolve_dependencies tests (Request injection & generator support)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_injects_request():
    """Dependencies with Request param get SioRequest injected."""
    app = FakeApp(state=FakeState(db_url="postgres://"))

    def get_db_url(request: Request) -> str:
        return request.app.state.db_url

    deps = {"db_url": get_db_url}
    async with AsyncExitStack() as stack:
        resolved = await _resolve_dependencies(deps, app=app, stack=stack)
    assert resolved["db_url"] == "postgres://"


@pytest.mark.asyncio
async def test_resolve_async_generator():
    """Async generator deps yield value and cleanup runs on stack exit."""
    opened = False
    closed = False

    async def get_resource() -> AsyncIterator[str]:
        nonlocal opened, closed
        opened = True
        yield "resource_value"
        closed = True

    deps = {"res": get_resource}
    async with AsyncExitStack() as stack:
        resolved = await _resolve_dependencies(deps, app=None, stack=stack)
        assert resolved["res"] == "resource_value"
        assert opened is True
        assert closed is False  # not yet cleaned up — stack still open
    assert closed is True  # stack exited, cleanup ran


@pytest.mark.asyncio
async def test_resolve_sync_generator():
    """Sync generator deps yield value and cleanup runs on stack exit."""
    from typing import Iterator

    closed = False

    def get_resource() -> Iterator[str]:
        nonlocal closed
        yield "sync_value"
        closed = True

    deps = {"res": get_resource}
    async with AsyncExitStack() as stack:
        resolved = await _resolve_dependencies(deps, app=None, stack=stack)
        assert resolved["res"] == "sync_value"
        assert closed is False
    assert closed is True


@pytest.mark.asyncio
async def test_resolve_generator_with_request():
    """Generator dep that also takes Request param."""
    app = FakeApp(state=FakeState(db_url="sqlite://"))

    async def get_session(request: Request) -> AsyncIterator[str]:
        url = request.app.state.db_url
        yield f"session:{url}"

    deps = {"session": get_session}
    async with AsyncExitStack() as stack:
        resolved = await _resolve_dependencies(deps, app=app, stack=stack)
        assert resolved["session"] == "session:sqlite://"
