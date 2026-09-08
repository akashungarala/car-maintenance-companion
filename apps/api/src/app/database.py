"""Database access.

Deliberately thin: an engine, a session factory, and a connectivity check. The
product's models and queries arrive with E2; Phase 0 only needs to prove the
connection works and that readiness reflects it.
"""

from typing import Any

import structlog
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.sql import text

logger = structlog.get_logger()


class Database:
    def __init__(self, url: str, *, pool_size: int = 5, connect_timeout: int = 5) -> None:
        self._engine: AsyncEngine = create_async_engine(
            url,
            pool_size=pool_size,
            # Recycle below any proxy or server idle timeout, so the pool does
            # not hand out a connection the server has already closed — which
            # surfaces as a random query failure rather than a connection error.
            pool_recycle=1800,
            pool_pre_ping=True,
            connect_args={"timeout": connect_timeout},
        )
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._session_factory

    async def execute_scalar(self, statement: str) -> Any:
        async with self._engine.connect() as conn:
            return (await conn.execute(text(statement))).scalar()

    async def is_healthy(self) -> bool:
        """Can we reach the database and run a trivial query?

        Only connectivity failures are absorbed. A health check that returns
        False for *any* exception becomes a sink that hides real bugs, so
        programming errors propagate.
        """
        try:
            return bool(await self.execute_scalar("SELECT 1") == 1)
        # OperationalError and InterfaceError are connectivity; DBAPIError is
        # their *parent* and would also swallow ProgrammingError, i.e. the bugs
        # this check must not hide.
        except (OperationalError, InterfaceError, OSError) as exc:
            logger.warning("database_unreachable", error=str(exc))
            return False

    async def dispose(self) -> None:
        await self._engine.dispose()
