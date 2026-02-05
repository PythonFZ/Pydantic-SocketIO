# first import everything from socketio
from socketio import *  # type: ignore # noqa: F403

from .pydantic_socketio import (
    AsyncClient as AsyncClient,
)
from .pydantic_socketio import (
    AsyncServer as AsyncServer,
)
from .pydantic_socketio import (
    Client as Client,
)
from .pydantic_socketio import (
    Server as Server,
)
from .pydantic_socketio import (
    monkey_patch as monkey_patch,
)
from .wrapper import (
    AsyncClientWrapper as AsyncClientWrapper,
)
from .wrapper import (
    AsyncServerWrapper as AsyncServerWrapper,
)
from .wrapper import (
    AsyncSimpleClientWrapper as AsyncSimpleClientWrapper,
)
from .wrapper import (
    Depends as Depends,
)
from .wrapper import (
    EventContext as EventContext,
)
from .wrapper import (
    SimpleClientWrapper as SimpleClientWrapper,
)
from .wrapper import (
    SyncClientWrapper as SyncClientWrapper,
)
from .wrapper import (
    SyncServerWrapper as SyncServerWrapper,
)
from .wrapper import (
    get_event_name as get_event_name,
)

# Wrapper API
from .wrapper import (
    wrap as wrap,
)

# import only if fastapi is installed
try:
    import fastapi as _fastapi  # noqa: F401
except ImportError:
    pass
else:
    from .fastapi_socketio import (
        FastAPISocketIO as FastAPISocketIO,
    )
    from .fastapi_socketio import (
        SioDep as SioDep,
    )
    from .fastapi_socketio import (
        get_sio as get_sio,
    )
