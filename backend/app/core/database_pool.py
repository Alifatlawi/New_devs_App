import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from ..config import settings

logger = logging.getLogger(__name__)


def to_async_url(database_url: str) -> str:
    """Point a plain postgresql:// URL at the asyncpg driver."""
    for prefix in ("postgresql://", "postgres://"):
        if database_url.startswith(prefix):
            return "postgresql+asyncpg://" + database_url[len(prefix):]
    return database_url


class DatabasePool:
    """Process-wide async SQLAlchemy engine, created lazily on first use."""

    def __init__(self) -> None:
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    def initialize(self) -> None:
        """Create the engine once. No I/O happens here; connections open on first query."""
        if self.session_factory is not None:
            return
        # The async engine uses AsyncAdaptedQueuePool by default; QueuePool is not allowed with asyncio.
        self.engine = create_async_engine(
            to_async_url(settings.database_url),
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout=settings.database_pool_timeout,
            pool_recycle=settings.database_pool_recycle,
            pool_pre_ping=True,
        )
        self.session_factory = async_sessionmaker(bind=self.engine, class_=AsyncSession, expire_on_commit=False)
        logger.info("Database connection pool initialized")

    async def close(self) -> None:
        if self.engine is not None:
            await self.engine.dispose()
        self.engine = None
        self.session_factory = None

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[AsyncSession]:
        self.initialize()
        if self.session_factory is None:
            raise RuntimeError("Database pool failed to initialize")
        async with self.session_factory() as session:
            yield session


# Global database pool instance (one engine per process, shared by all requests)
db_pool = DatabasePool()


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields a pooled session."""
    async with db_pool.get_session() as session:
        yield session
