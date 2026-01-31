# first import everything from socketio
from socketio import *  # type: ignore # noqa: F403

from .pydantic_socketio import (
    Client as Client,
    AsyncClient as AsyncClient,
    Server as Server,
    AsyncServer as AsyncServer,
    monkey_patch as monkey_patch,
)

# Wrapper API
from .wrapper import (
    wrap as wrap,
    get_event_name as get_event_name,
    AsyncClientWrapper as AsyncClientWrapper,
    AsyncServerWrapper as AsyncServerWrapper,
    AsyncSimpleClientWrapper as AsyncSimpleClientWrapper,
    SimpleClientWrapper as SimpleClientWrapper,
    SyncClientWrapper as SyncClientWrapper,
    SyncServerWrapper as SyncServerWrapper,
)

# import only if fastapi is installed
try:
    import fastapi as _fastapi  # noqa: F401
except ImportError:
    pass
else:
    from .fastapi_socketio import (
        FastAPISocketIO as FastAPISocketIO,
        get_sio as get_sio,
        SioDep as SioDep,
    )
