"""Pytest configuration and shared fixtures for pydantic-socketio tests."""

from typing import ClassVar, Literal
from unittest.mock import AsyncMock, MagicMock

import pytest
import socketio
from pydantic import BaseModel

from pydantic_socketio import (
    AsyncClientWrapper,
    AsyncSimpleClientWrapper,
    SimpleClientWrapper,
    SyncClientWrapper,
)

# =============================================================================
# Shared Test Models
# =============================================================================


class Ping(BaseModel):
    message: str


class Pong(BaseModel):
    reply: str


class CustomEvent(BaseModel):
    event_name: ClassVar[str] = "my_custom_event"
    data: str


class PascalCaseModel(BaseModel):
    value: int


class Error(BaseModel):
    kind: Literal["error"] = "error"
    message: str


class Success(BaseModel):
    kind: Literal["success"] = "success"
    data: str


# =============================================================================
# Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_sync_client():
    """Create a mock sync Client."""
    mock = MagicMock(spec=socketio.Client)
    mock.call.return_value = {"reply": "world"}
    return mock


@pytest.fixture
def mock_async_client():
    """Create a mock async Client."""
    mock = MagicMock(spec=socketio.AsyncClient)
    mock.emit = AsyncMock()
    mock.call = AsyncMock(return_value={"reply": "world"})
    return mock


@pytest.fixture
def mock_sync_server():
    """Create a mock sync Server."""
    mock = MagicMock(spec=socketio.Server)
    mock.call.return_value = {"reply": "world"}
    return mock


@pytest.fixture
def mock_async_server():
    """Create a mock async Server."""
    mock = MagicMock(spec=socketio.AsyncServer)
    mock.emit = AsyncMock()
    mock.call = AsyncMock(return_value={"reply": "world"})
    return mock


@pytest.fixture
def mock_simple_client():
    """Create a mock SimpleClient."""
    mock = MagicMock(spec=socketio.SimpleClient)
    mock.call.return_value = {"reply": "world"}
    mock.receive.return_value = ["pong", {"reply": "world"}]
    return mock


@pytest.fixture
def mock_async_simple_client():
    """Create a mock AsyncSimpleClient."""
    mock = MagicMock(spec=socketio.AsyncSimpleClient)
    mock.emit = AsyncMock()
    mock.call = AsyncMock(return_value={"reply": "world"})
    mock.receive = AsyncMock(return_value=["pong", {"reply": "world"}])
    return mock


# =============================================================================
# Wrapper Fixtures
# =============================================================================


@pytest.fixture
def sync_client_wrapper(mock_sync_client):
    """Create a SyncClientWrapper with mock."""
    return SyncClientWrapper(mock_sync_client)


@pytest.fixture
def async_client_wrapper(mock_async_client):
    """Create an AsyncClientWrapper with mock."""
    return AsyncClientWrapper(mock_async_client)


@pytest.fixture
def simple_client_wrapper(mock_simple_client):
    """Create a SimpleClientWrapper with mock."""
    return SimpleClientWrapper(mock_simple_client)


@pytest.fixture
def async_simple_client_wrapper(mock_async_simple_client):
    """Create an AsyncSimpleClientWrapper with mock."""
    return AsyncSimpleClientWrapper(mock_async_simple_client)
