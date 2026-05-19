from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session


async def db_session() -> AsyncIterator[AsyncSession]:
    async for session in get_db_session():
        yield session
