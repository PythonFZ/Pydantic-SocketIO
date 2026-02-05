"""Tests for Request auto-injection and generator dependencies."""

from dataclasses import dataclass

import pytest

from pydantic_socketio.wrapper import SioRequest


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

import socketio

from pydantic_socketio import wrap


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
