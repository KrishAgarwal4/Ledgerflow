import os
import sys
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from backend.app.config import settings

# Engine configuration: NullPool for testing (prevents cross-event-loop issues), Pool for production
engine_kwargs = {
    "echo": False,
    "future": True,
}

if "pytest" in sys.modules or os.getenv("TESTING") == "1":
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs.update({
        "pool_size": 20,
        "max_overflow": 10,
        "pool_pre_ping": True,
    })

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db() -> None:
    """Initialize tables and create core platform ledger accounts if not existing."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
