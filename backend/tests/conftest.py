import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database import Base, engine, AsyncSessionLocal
from backend.app.main import app
from backend.app.seed.seed_data import seed_database

@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Wipes, seeds, and disposes engine cleanly per test."""
    async with engine.connect() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.commit()
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.commit()
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    await seed_database()
    yield
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

@pytest_asyncio.fixture
async def async_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        yield client
