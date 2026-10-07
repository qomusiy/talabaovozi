import os

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ["BOT_TOKEN"] = "123:TEST"
os.environ["DEV_MODE"] = "true"
os.environ["WEBAPP_URL"] = ""
os.environ["TUNNEL"] = "quick"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://feedback:feedback_dev_pw@127.0.0.1:5433/feedback_test"
)

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app import db, settings_store  # noqa: E402

from app.models import Base  # noqa: E402


@pytest.fixture
async def session():
    """Fresh schema for every test."""
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.run_sync(Base.metadata.create_all)
    settings_store.reset_cache()
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()
    await db.engine.dispose()  # the app's engine is bound to this test's event loop
