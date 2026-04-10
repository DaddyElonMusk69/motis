"""
motis_platform.db
=================
Public interface for all database operations.

Import from here, not from submodules:
    from motis_platform.db import get_db, init_db, dispose_db
    from motis_platform.db import models
    from motis_platform.db.models import User, Operator, AgentMemory  # etc.
"""

from motis_platform.db.session import (
    async_session,
    dispose_db,
    engine,
    get_db,
    init_db,
)
from motis_platform.db import models  # noqa: F401 — re-export for convenience

__all__ = [
    "engine",
    "async_session",
    "get_db",
    "init_db",
    "dispose_db",
    "models",
]
